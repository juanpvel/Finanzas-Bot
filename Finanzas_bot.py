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
NOMBRE_DOCUMENTO = "Cuentas Personales"  # 🔥 CAMBIO AQUÍ

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
Ingresos artísticos por el proyecto personal, ya sea por MERCH o conciertos con Juan Pablo Luna.

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
# GOOGLE SHEETS
# ==========================

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
creds = Credentials.from_service_account_info(creds_info, scopes=scopes)

client = gspread.authorize(creds)

SHEET_ID = os.environ.get("SHEET_ID")

doc = client.open_by_key(SHEET_ID)  # 🔥 SOLO CAMBIA EL NOMBRE DEL SHEET

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
# PARSER ROBUSTO JSON
# ==========================

def extraer_json(texto: str):
    try:
        texto = texto.strip()
        texto = texto.replace("```json", "").replace("```", "")

        start = texto.find("[")
        end = texto.rfind("]")

        if start == -1 or end == -1:
            raise ValueError("No JSON found")

        return json.loads(texto[start:end + 1])

    except Exception as e:
        print("❌ RAW FALLIDO:", texto)
        raise ValueError(f"JSON error: {str(e)}")


# ==========================
# DETECCIÓN INGRESO/GASTO
# ==========================

def forzar_tipo(mensaje: str, tipo_gemini: str):
    texto = mensaje.lower()

    ingresos_keywords = [
        "ingreso", "me llegó", "me llegaron", "me entró", "me entro",
        "recibí", "me pagaron", "me consignaron", "me depositaron"
    ]

    if any(k in texto for k in ingresos_keywords):
        return "ingreso"

    return "gasto"


# ==========================
# FALLBACK MONTOS/DESCRIPCIÓN
# ==========================

def reparar_datos(mensaje, d):
    if not d.get("descripcion"):
        d["descripcion"] = mensaje

    if not d.get("monto") or d.get("monto") == 0:
        nums = re.findall(r"\d+", mensaje)
        if nums:
            d["monto"] = int(nums[0])

    return d


# ==========================
# GUARDAR
# ==========================

def guardar_movimiento(d):
    fecha = datetime.now().strftime("%Y-%m-%d")

    cuenta = d.get("cuenta", "No especificada").lower().strip()
    cuenta = cuentas_validas.get(cuenta, "No especificada")

    fila = [
        fecha,
        d.get("categoria", ""),
        d.get("descripcion", ""),
        d.get("monto", 0),
        cuenta
    ]

    if d.get("tipo") == "gasto":
        gastos_sheet.append_row(fila)
    else:
        ingresos_sheet.append_row(fila)

    return {
        "fecha": fecha,
        **d,
        "cuenta": cuenta
    }


# ==========================
# MAIN
# ==========================

def procesar_mensaje(mensaje, chat_id=None):

    try:
        print("📥 MENSAJE:", mensaje)

        if chat_id and chat_id in pending_movements:
            movimiento = pending_movements.pop(chat_id)

            cuenta = mensaje.lower().strip()
            movimiento["cuenta"] = cuentas_validas.get(cuenta, "No especificada")

            movimiento = reparar_datos(mensaje, movimiento)
            recibido = guardar_movimiento(movimiento)

            return f"""✅ Cuenta registrada y movimiento guardado

🧾 {recibido['descripcion']}
💰 {recibido['monto']}
🏦 {recibido['cuenta']}"""

        prompt = f"""
{contexto_usuario}

Extrae información financiera.

Devuelve SOLO lista JSON válida.

Mensaje:
{mensaje}
"""

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        raw = response.text.strip()
        print("🤖 RAW:", raw)

        movimientos = extraer_json(raw)

        resultados = []

        for d in movimientos:

            d = reparar_datos(mensaje, d)
            d["tipo"] = forzar_tipo(mensaje, d.get("tipo", ""))

            cuenta = d.get("cuenta", "No especificada").lower().strip()
            d["cuenta"] = cuentas_validas.get(cuenta, "No especificada")

            if d["cuenta"] == "No especificada" and chat_id:
                pending_movements[chat_id] = d
                return "🤔 ¿Qué cuenta fue? (Nequi, Nu, Davivienda, Bancolombia, Efectivo, Splitwise)"

            recibido = guardar_movimiento(d)
            resultados.append(recibido)

        return "\n\n".join([
            f"""🧾 Movimiento:
📂 {r['categoria']}
📝 {r['descripcion']}
💰 {r['monto']}
🏦 {r['cuenta']}"""
            for r in resultados
        ])

    except Exception as e:
        print("❌ ERROR:", str(e))
        return "❌ Error procesando mensaje"