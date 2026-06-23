import json
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import os
import re

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
Extrae movimientos financieros y devuelve SOLO JSON válido (lista).

Campos:
- categoria
- descripcion
- monto
- cuenta

Reglas:
- Puede haber uno o varios movimientos
- Si no hay ingreso explícito → gasto
- NO texto adicional
- Si falla, devuelve []

REGLA PRIORITARIA:
Si el texto indica ingreso (ej: ingresé, llegó, entró, recibí, pagaron, consignaron, depositaron, cobré, gané, vendí, transfirieron) → tipo = ingreso

INGRESOS:
ingreso, ingresé, me llegó, me llegaron, me entró, recibí, me pagaron, me consignaron, me depositaron, cobré, gané, vendí, me transfirieron, me cayó

CATEGORÍAS GASTO:
Antojos (cafés, postres)
Comida afuera (restaurantes)
Deporte (escalada, magnesio)
Enfermedades (medicinas)
Inversión estudio (audio, equipos)
Mambe (mambe, ambil y domicilios relacionados)
Mercado (supermercado)
Moto (gasolina, taller)
Panaderia (pan)
Para mi (Compras de objetos personales)
Regalos
Servicios (Agua, luz, internet, celular)
Transporte (Uber, taxi, bus)
Uma (Gastos de la perrita)
Vivienda (Arriendo y administración)
Planilla
Casa
Streaming
Paseos
Disco (inversión por disco)
Aseo (Alguien viene a hacer aseo a la casa)
Moshiplanes (Ocio con mi esposa)

CATEGORÍAS INGRESO:
P&S (Utilidades de prestamos)
Diván (Por eventos de micrófono abierto y muestras del taller del diván)
Peña (eventos, conciertos y actividades de Pedro Bombo y la Peña)
Clases (Clases universidad del bosque, y clases particulares)
Juan Pablo Luna (Eventos, conciertos y merch de Juan Pablo Luna)
Audio (Mezcla, producción, masterización y edición de audio)

CUENTAS:
Nequi, Nu, Davivienda, Bancolombia, Efectivo, Splitwise

Si no hay cuenta:
"cuenta": "No especificada"

CONVERSIONES:
18 lucas → 18000
50k → 50000
23 mil → 23000
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

    cuenta = d.get("cuenta", "No especificada").lower().strip()
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

def llamar_gemini(mensaje):

    prompt = f"""
{contexto_usuario}

Mensaje:
{mensaje}

Devuelve SOLO JSON.
"""

    response = client_genai.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config={
            "temperature": 0,
            "max_output_tokens": 200
        }
    )

    if not response or not response.text:
        raise ValueError("Gemini no respondió")

    return response.text


# ==========================
# MAIN
# ==========================

def procesar_mensaje(mensaje, chat_id=None):

    try:

        print("\n📥 MENSAJE:", mensaje)

        if chat_id and chat_id in pending_movements:

            mov = pending_movements.pop(chat_id)

            cuenta = mensaje.lower().strip()
            mov["cuenta"] = cuentas_validas.get(cuenta, "No especificada")

            saved = guardar(mov)

            return f"""
✅ Movimiento guardado

🧾 {saved['descripcion']}
💰 {saved['monto']}
🏦 {saved['cuenta']}
""".strip()

        raw = llamar_gemini(mensaje)
        print("🤖 RAW:", raw)

        movimientos = extraer_json(raw)

        tipo = forzar_tipo(mensaje)
        resultados = []

        for d in movimientos:

            d = reparar(mensaje, d)
            d["tipo"] = tipo

            cuenta = d.get("cuenta", "No especificada").lower().strip()
            d["cuenta"] = cuentas_validas.get(cuenta, "No especificada")

            if d["cuenta"] == "No especificada" and chat_id:
                pending_movements[chat_id] = d

                return (
                    "🤔 ¿Qué cuenta fue?\n\n"
                    "Nequi\nNu\nDavivienda\nBancolombia\nEfectivo\nSplitwise"
                )

            resultados.append(guardar(d, mensaje))

        return "\n\n".join([
            f"""🧾 Movimiento:

📅 {r.get('fecha', '')}
💸 {r['tipo'].capitalize()}

📂 {r['categoria']}
📝 {r['descripcion']}
💰 {r['monto']}
🏦 {r['cuenta']}"""
            for r in resultados
        ])

    except Exception as e:
        print("❌ ERROR:", repr(e))
        return f"⚠️ Error: {str(e)}"