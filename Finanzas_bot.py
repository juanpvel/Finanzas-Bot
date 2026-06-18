import json
from datetime import datetime
import os
import re

import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai


# ==========================
# CONFIG
# ==========================

API_KEY = os.environ.get("GEMINI_API_KEY")
SHEET_ID = os.environ.get("SHEET_ID")

genai.configure(api_key=API_KEY)


# ==========================
# MEMORIA SIMPLE
# ==========================

pending_movements = {}


# ==========================
# CONTEXTO (INTACTO)
# ==========================

contexto_usuario = """

Soy Juan Pablo Luna.

Soy músico, compositor y productor.

Tengo dos tipos de movimientos:

- Gasto
- Ingreso


CATEGORÍAS DE GASTOS:

Antojos:
Compras impulsivas, cafés, pasteles o pequeños gustos de comida, tipo postres, gustos, antojos, etc.

Comida afuera:
Restaurantes, cenas, desayunos y almuerzos y comidas fuera de casa.

Deporte:
Actividad física como el pago de la membresía de Trepa, o compra de magnesio.

Enfermedades:
Medicamentos y gastos médicos.

Inversión para el estudio:
Si compro cables, micrófonos, parlantes, plugins de audio, cuerdas de guitarra o tiple, o similares.

Mambe:
Gastos relacionados con compra de mambe y ambil, también incluye el transporte del domicilio.

Mercado:
Supermercado y compras para cocinar o con productos de aseo para la casa.

Moto:
Gasolina y gastos de la moto como revisión en taller, cambio de aceite, impuestos, etc.

Panaderia:
Pan y compras de panadería.

Para mi:
Compras personales como ropa u objetos para mi, no comida.

Regalos:
Regalos para otras personas.

Servicios:
Internet, agua, luz, celular, etc.

Transporte:
Bus, taxi, Uber y transporte.

Uma:
Uma es nuestra perrita, son gastos relacionados con su cuidado, comida, veterinario, etc.

Vivienda:
Arriendo, administración del edificio.

Planilla:
Seguridad social.

Para la casa:
Objetos y mejoras para la casa.

Plataformas video:
Netflix, Disney Plus YouTube Premium y similares.

Paseos:
Viajes y salidas fuera de la ciudad.

Intereses:
Intereses bancarios.

Inversión disco:
Gastos relacionados con la producción y promoción del disco de mi proyecto personal.

Aseo:
Cuando viene una persona a la casa a hacer el aseo del apartamento.

Moshiplanes:
Conciertos, planes y actividades de ocio con mi esposa.


CATEGORÍAS DE INGRESOS:

P&S:
Préstamos que hago a través de mis papás.

Divan:
Ingresos por evento "El divan".

Peña:
Conciertos en peñas o eventos con Pedro Bombo.

Clases:
Ingresos por clases independientes o en la universidad del bosque.

Juan Pablo Luna:
Ingresos artísticos por el proyecto personal.

Audio:
Producción musical o de audio para terceros.


CUENTAS POSIBLES:

Splitwise
Nequi
Davivienda
Nu
Efectivo
Bancolombia


REGLAS:

- Devuelve SOLO una lista JSON
- Puede haber uno o varios movimientos
- Si no hay cuenta: "No especificada"
- 18 lucas → 18000
- 50k → 50000
- 23 mil → 23000

"""


# ==========================
# SHEETS
# ==========================

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"]),
    scopes=scopes
)

client = gspread.authorize(creds)

doc = client.open_by_key(SHEET_ID)

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
# JSON PARSER ULTRA ROBUSTO
# ==========================

def extraer_json(texto: str):
    try:
        texto = (texto or "").strip()
        texto = texto.replace("```json", "").replace("```", "")

        start = texto.find("[")
        end = texto.rfind("]")

        if start == -1 or end == -1:
            print("❌ RAW SIN JSON:", texto)
            raise ValueError("No JSON array found")

        return json.loads(texto[start:end + 1])

    except Exception as e:
        print("❌ JSON FALLIDO RAW:", texto)
        raise ValueError(f"JSON parse error: {repr(e)}")


# ==========================
# FALLBACK DE DATOS
# ==========================

def reparar(mensaje, d):
    if not isinstance(d, dict):
        return {
            "tipo": "gasto",
            "categoria": "",
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
# GUARDAR EN SHEETS
# ==========================

def guardar(d):
    fecha = datetime.now().strftime("%Y-%m-%d")

    cuenta = (d.get("cuenta") or "No especificada").lower().strip()
    cuenta = cuentas_validas.get(cuenta, "No especificada")

    fila = [
        fecha,
        d.get("categoria", ""),
        d.get("descripcion", ""),
        d.get("monto", 0),
        cuenta
    ]

    tipo = (d.get("tipo") or "gasto").lower()

    if tipo == "ingreso":
        ingresos_sheet.append_row(fila)
    else:
        gastos_sheet.append_row(fila)

    return {**d, "cuenta": cuenta}


# ==========================
# GEMINI
# ==========================

def llamar_gemini(mensaje):
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
{contexto_usuario}

IMPORTANTE:
- Un mensaje puede tener múltiples movimientos (ej: ayer gasté 20k en café y hoy 30k en transporte)
- Divide cada acción en un objeto separado

REGLA CRÍTICA:
- Si NO dice "ingreso", asumir "gasto"

Devuelve SOLO JSON lista.

Mensaje:
{mensaje}
"""

    response = model.generate_content(prompt)
    return response.text or ""


# ==========================
# MAIN
# ==========================

def procesar_mensaje(mensaje, chat_id=None):

    try:
        print("📥 MENSAJE:", mensaje)

        # ======================
        # CUENTA PENDIENTE
        # ======================

        if chat_id and chat_id in pending_movements:
            mov = pending_movements.pop(chat_id)

            mov["cuenta"] = cuentas_validas.get(mensaje.lower().strip(), "No especificada")

            mov = reparar(mensaje, mov)
            saved = guardar(mov)

            return f"""✅ Guardado

🧾 {saved['descripcion']}
💰 {saved['monto']}
🏦 {saved['cuenta']}"""

        # ======================
        # GEMINI
        # ======================

        raw = llamar_gemini(mensaje)
        print("🤖 GEMINI RAW:", raw)

        movimientos = extraer_json(raw)

        if isinstance(movimientos, dict):
            movimientos = [movimientos]

        resultados = []

        for d in movimientos:

            d = reparar(mensaje, d)

            if not d.get("tipo"):
                d["tipo"] = "gasto"

            cuenta = (d.get("cuenta") or "No especificada").lower().strip()
            d["cuenta"] = cuentas_validas.get(cuenta, "No especificada")

            if d["cuenta"] == "No especificada" and chat_id:
                pending_movements[chat_id] = d
                return "🤔 ¿Qué cuenta fue? (Nequi, Nu, Davivienda, Bancolombia, Efectivo, Splitwise)"

            saved = guardar(d)
            resultados.append(saved)

        if not resultados:
            return "⚠️ No se detectaron movimientos"

        return "\n\n".join([
            f"""🧾 Movimiento
📂 {r.get('categoria','')}
📝 {r.get('descripcion','')}
💰 {r.get('monto','')}
🏦 {r.get('cuenta','')}"""
            for r in resultados
        ])

    except Exception as e:
        print("❌ ERROR COMPLETO:", repr(e))
        return "⚠️ Error procesando mensaje. Intenta de nuevo con algo como: 'gasté 20k en café'"