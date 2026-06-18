import json
import re
from datetime import datetime
import os

import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai


# ==========================
# CONFIG
# ==========================

API_KEY = os.environ.get("GEMINI_API_KEY")
NOMBRE_DOCUMENTO = "Cuentas Personales - Pruebas Python - Junio 2026"

genai.configure(api_key=API_KEY)


# ==========================
# MEMORIA SIMPLE (CUENTAS PENDIENTES)
# ==========================

pending_movements = {}


# ==========================
# CONTEXTO (TU MODELO MENTAL COMPLETO)
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
Producción musical o de audio para terceros como mezclas, edición, sesiones de producción.


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

doc = client.open(NOMBRE_DOCUMENTO)

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
# LIMPIEZA ROBUSTA DE JSON
# ==========================

def extraer_json(texto: str):
    """
    Extrae el primer bloque JSON válido aunque venga sucio.
    """
    try:
        texto = texto.strip()

        # quitar markdown
        texto = texto.replace("```json", "").replace("```", "")

        # buscar array JSON
        match = re.search(r"\[\s*{.*}\s*\]", texto, re.DOTALL)

        if match:
            return json.loads(match.group())

        # fallback directo
        return json.loads(texto)

    except Exception:
        raise ValueError(f"No se pudo parsear JSON: {texto}")


# ==========================
# GUARDAR EN SHEETS
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

    if d.get("tipo", "").lower() == "gasto":
        gastos_sheet.append_row(fila)
    else:
        ingresos_sheet.append_row(fila)


# ==========================
# FUNCIÓN PRINCIPAL
# ==========================

def procesar_mensaje(mensaje, chat_id=None):

    try:
        print("📥 MENSAJE:", mensaje)

        # ==========================
        # RESPUESTA A CUENTA PENDIENTE
        # ==========================

        if chat_id and chat_id in pending_movements:
            movimiento = pending_movements.pop(chat_id)

            cuenta = mensaje.lower().strip()
            movimiento["cuenta"] = cuentas_validas.get(cuenta, "No especificada")

            guardar_movimiento(movimiento)

            return "✅ Cuenta registrada y movimiento guardado"

        # ==========================
        # GEMINI
        # ==========================

        prompt = f"""
{contexto_usuario}

Extrae información financiera del mensaje.

Devuelve SOLO una lista JSON.

Mensaje:
{mensaje}
"""

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        raw = response.text.strip()
        print("🤖 RAW GEMINI:", raw)

        movimientos = extraer_json(raw)

        if not isinstance(movimientos, list):
            return "❌ Formato inválido de Gemini"

        resultados = []

        for d in movimientos:

            cuenta = d.get("cuenta", "No especificada").lower().strip()

            # ==========================
            # CUENTA FALTANTE → PREGUNTA
            # ==========================

            if cuenta == "no especificada":
                if chat_id:
                    pending_movements[chat_id] = d
                    return "🤔 ¿Qué cuenta fue? (Nequi, Nu, Davivienda, Bancolombia, Efectivo, Splitwise)"
                else:
                    d["cuenta"] = "No especificada"
            else:
                d["cuenta"] = cuentas_validas.get(cuenta, "No especificada")

            guardar_movimiento(d)
            resultados.append(d)

        return f"✅ Guardado {len(resultados)} movimiento(s)"

    except Exception as e:
        print("❌ ERROR COMPLETO:", str(e))
        return "❌ Error procesando mensaje"