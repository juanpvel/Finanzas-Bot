import threading
lock = threading.Lock()
import json
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import os
import re
import time
import random

import gspread
from google.oauth2.service_account import Credentials
from google import genai
import dateparser


# ==========================
# CONFIG
# ==========================

API_KEY = os.environ.get("GEMINI_API_KEY")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

client_genai = genai.Client(api_key=API_KEY)


# ==========================
# MEMORIA SIMPLE
# ==========================

pending_movements = {}


# ==========================
# CONTEXTO
# ==========================

contexto_usuario = """
TASK: Extract financial transactions from text.

OUTPUT (STRICT):
Return ONLY valid JSON array.
No markdown. No explanation.

Schema:
[
  {
    "categoria": "string",
    "descripcion": "string",
    "monto": number,
    "cuenta": "string | null"
  }
]

RULES:
- Can return 1 or multiple transactions
- If no explicit income signal → tipo = "gasto"
- If parsing fails → return []


CATEGORÍAS GASTO:
Antojos: cafés, postres, snacks, jugos, helados, dulces
Comida afuera: restaurantes, almuerzos, domicilios
Deporte: escalada, gimnasio, magnesio, deporte en general
Enfermedades: medicinas, salud, tratamientos
Inversión estudio: audio, equipos, plugins, cables
Mambe: mambe, ambil y domicilios relacionados
Mercado: supermercado, comida para preparar, compras del hogar
Moto: gasolina, mantenimiento, taller
Panaderia: pan
Para mi: compras personales no esenciales, no comida
Regalos: obsequios
Servicios: agua, luz, internet, celular, claro
Transporte: uber, taxi, bus, transporte urbano
Uma: gastos de la perrita
Vivienda: arriendo, administración, vivienda
Planilla: pagos de nómina o seguridad social
Para la Casa: muebles, objetos del hogar
Streaming: suscripciones digitales
Paseos: viajes, salidas
Disco: inversión en proyecto musical Juan Pablo Luna
Aseo: limpieza del hogar
Moshiplanes: ocio con esposa

CATEGORÍAS INGRESO:
P&S: utilidades de préstamos
Diván: eventos de micrófono abierto / talleres del Diván
Peña: eventos musicales de Pedro Bombo / la Peña
Clases: clases universitarias o particulares
Juan Pablo Luna: conciertos, shows, merch del proyecto artístico
Audio: mezcla, producción, masterización, edición de audio

ACCOUNTS:
Nequi, Nu, Davivienda, Bancolombia, Efectivo, Splitwise

ACCOUNT RULE:
If account not recognized → "No especificada"

MONEY NORMALIZATION:
"18 lucas" = 18000
"50k" = 50000
"23 mil" = 23000

STRICT:
- JSON only
- no extra text
- all fields required
"""


# ==========================
# FECHAS NATURALES 🆕 (MEJORA PRO)
# ==========================

def resolver_fecha(mensaje):

    base = datetime.now(ZoneInfo("America/Bogota")).replace(microsecond=0)

    texto = mensaje.lower()

    # 🧠 manejo explícito (más confiable que dateparser)
    if "anteayer" in texto:
        return (base - timedelta(days=2)).strftime("%Y-%m-%d")

    if "ayer" in texto:
        return (base - timedelta(days=1)).strftime("%Y-%m-%d")

    if "hoy" in texto:
        return base.strftime("%Y-%m-%d")

    # fallback: dateparser solo para fechas explícitas tipo "12 de junio"
    fecha = dateparser.parse(
        mensaje,
    languages=["es"],
    settings={
        "RELATIVE_BASE": base,
        "PREFER_DATES_FROM": "past",
        "STRICT_PARSING": False
    }
)

    if fecha:
        return fecha.strftime("%Y-%m-%d")

    return base.strftime("%Y-%m-%d")


# ==========================
# GOOGLE SHEETS
# ==========================

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)

creds = Credentials.from_service_account_info(
    creds_info,
    scopes=scopes
)

gc = gspread.authorize(creds)

doc = gc.open_by_key(SHEET_ID)

gastos_sheet = doc.worksheet("Gastos")
ingresos_sheet = doc.worksheet("Ingresos")


# ==========================
# CUENTAS
# ==========================

cuentas_validas = {
    "nequi": "Nequi",
    "nu": "Nu",
    "davivienda": "Davivienda",
    "bancolombia": "Bancolombia",
    "efectivo": "Efectivo",
    "splitwise": "Splitwise"
}


# ==========================
# JSON ROBUSTO
# ==========================

def extraer_json(texto):
    texto = texto.strip().replace("```json", "").replace("```", "").strip()

    matches = re.findall(r"\[[\s\S]*?\]", texto)

    if not matches:
        raise ValueError("No JSON encontrado")

    # prioriza el más grande (más probable que sea el real)
    matches.sort(key=len, reverse=True)

    for bloque in matches:
        try:
            return json.loads(bloque)
        except json.JSONDecodeError:
            continue

    raise ValueError("Ningún JSON válido encontrado")


# ==========================
# FALLBACK
# ==========================

def reparar(mensaje, d):

    if not isinstance(d, dict):
        return {
            "categoria": "No detectada",
            "descripcion": mensaje,
            "monto": 0,
            "cuenta": "No especificada"
        }

    if not d.get("descripcion"):
        d["descripcion"] = mensaje

    if not d.get("monto"):
        nums = re.findall(r"\d+", mensaje)
        if nums:
            d["monto"] = int(nums[0])

    return d


# ==========================
# TIPO AUTOMÁTICO
# ==========================

def forzar_tipo(mensaje):
    texto = mensaje.lower()

    ingresos = [
        "ingreso", "ingresé", "ingrese",
        "llegaron", "llegó","me llegó", "me llego", "me llegaron",
        "entraron", "entro", "entró", "me entró", "me entro",
        "recibí", "recibi",
        "me pagaron", "me consignaron",
        "depositaron", "me depositaron",
        "cobré", "cobre",
        "gané", "gane",
        "vendí", "vendi",
        "transfirieron", "me transfirieron",
        "me cayó", "me cayo"
    ]

    return "ingreso" if any(x in texto for x in ingresos) else "gasto"


# ==========================
# GUARDAR
# ==========================

def guardar(d, mensaje_original):
    fecha = resolver_fecha(mensaje_original)

    cuenta = (d.get("cuenta") or "No especificada").lower().strip()
    cuenta = cuentas_validas.get(cuenta, "No especificada")

    fila = [
        fecha,
        d.get("categoria", ""),
        d.get("descripcion", ""),
        d.get("monto", 0),
        cuenta
    ]

    print("📤 GUARDANDO:", fila)

    if d["tipo"] == "gasto":
        gastos_sheet.append_row(fila)
    else:
        ingresos_sheet.append_row(fila)

    return {**d, "fecha": fecha, "cuenta": cuenta}


# ==========================
# GEMINI
# ==========================

def llamar_gemini(mensaje, retries=4):

    prompt = f"""
{contexto_usuario}

Mensaje:
{mensaje}

Devuelve SOLO JSON.
"""

    retry_count = 0

    for i in range(retries):

        try:
            response = client_genai.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config={
                    "temperature": 0,
                    "max_output_tokens": 120
                }
            )

            if response and response.text:
                return response.text, i

            raise ValueError("Empty response")

        except Exception as e:

            error_text = str(e)

            errores_temporales = [
                "503",
                "UNAVAILABLE",
                "429",
                "RESOURCE_EXHAUSTED",
                "Deadline Exceeded",
                "Internal Server Error"
            ]

            es_temporal = any(
                x.lower() in error_text.lower()
                for x in errores_temporales
            )

            if not es_temporal:
                print(f"❌ Error no recuperable: {error_text}")
                raise

            retry_count += 1

            if i == retries - 1:
                raise

            wait = (2 ** i) + random.uniform(0.3, 1.2)

            print(f"⚠️ Retry {retry_count}: {error_text}")
            time.sleep(wait)

    raise ValueError("Gemini falló después de varios intentos")


# ==========================
# MAIN
# ==========================

def procesar_mensaje(mensaje, chat_id=None):

    with lock:

        try:
            print("\n📥 MENSAJE:", mensaje)

            # ==========================
            # RESPUESTA A CUENTA PENDIENTE
            # ==========================
            if chat_id and chat_id in pending_movements:

                pendiente = pending_movements.pop(chat_id)

                mov = pendiente["movimiento"]
                mensaje_original = pendiente["mensaje_original"]

                # 1. normalizar primero TODO el movimiento
                mov = reparar(mensaje_original, mov)

                # 2. asignar tipo
                mov["tipo"] = forzar_tipo(mensaje_original)

                # 3. resolver cuenta
                mov["cuenta"] = cuentas_validas.get(
                    mensaje.lower().strip(),
                    "No especificada"
                )

                # 4. guardar
                saved = guardar(mov, mensaje_original)

                return f"""
✅ Movimiento guardado

🧾 {saved['descripcion']}
💰 {saved['monto']}
🏦 {saved['cuenta']}
""".strip()

            # ==========================
            # GEMINI
            # ==========================
            raw, retries = llamar_gemini(mensaje)
            print(f"🔁 Retries usados: {retries}")

            try:
                movimientos = extraer_json(raw)
            except Exception as e:
                print("❌ JSON PARSE ERROR:", e)
                return "⚠️ No pude entender la transacción. Intenta de nuevo."
            
            tipo = forzar_tipo(mensaje)

            resultados = []

            # ==========================
            # PROCESAR MOVIMIENTOS
            # ==========================
            for d in movimientos:

                d = reparar(mensaje, d)
                d["tipo"] = tipo

                cuenta = (
                    (d.get("cuenta") or "No especificada")
                    .lower()
                    .strip()
                )

                d["cuenta"] = cuentas_validas.get(
                    cuenta,
                    "No especificada"
                )

                if d["cuenta"] == "No especificada" and chat_id:

                    pending_movements[chat_id] = {
                        "movimiento": d,
                        "mensaje_original": mensaje
                    }

                    return (
                        "🤔 ¿Qué cuenta fue?\n\n"
                        "Nequi\n"
                        "Nu\n"
                        "Davivienda\n"
                        "Bancolombia\n"
                        "Efectivo\n"
                        "Splitwise"
                    )

                resultados.append(
                    guardar(d, mensaje)
                )

            return "\n\n".join([
                f"""🧾 Movimiento:

📅 {r.get('fecha', '')}
💸 {r['tipo'].capitalize()}

📂 {r['categoria']}
📝 {r['descripcion']}
💰 {r['monto']}
🏦 {r['cuenta']}"""
    for r in resultados
]) + f"\n\n⚙️ retries: {retries}"

        except Exception as e:
            print("❌ ERROR:", repr(e))
            return f"⚠️ Error: {str(e)}"