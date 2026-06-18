import json
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
# MEMORIA TEMPORAL (CUENTAS PENDIENTES)
# ==========================

pending_movements = {}


# ==========================
# CONTEXTO (EXACTAMENTE EL TUYO)
# ==========================

contexto_usuario = """

Soy Juan Pablo Luna.

Soy músico, compositor y productor.

Tengo dos tipos de movimientos:

- Gasto
- Ingreso


CATEGORÍAS DE GASTOS:

Antojos:
Compras impulsivas o pequeños gustos de comida, tipo postres, gustos, antojos, etc.

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
Son ingresos relacionados con los préstamos que hago a través de mis papás.

Divan:
Pago por el evento "El divan" (micrófono abierto, talleres de storytelling, etc.)

Peña:
Presentaciones y conciertos en peñas con la banda Pedro Bombo.

Clases:
Ingresos por clases.

Juan Pablo Luna:
Ingresos del proyecto artístico (conciertos, merch, etc.)

Audio:
Grabación, mezcla y producción para terceros.


CUENTAS POSIBLES:

Splitwise
Nequi
Davivienda
Nu
Efectivo
Bancolombia


REGLAS IMPORTANTES:

- Devuelve SOLO una lista JSON válida
- Puede haber uno o varios movimientos
- Si no se especifica cuenta: "No especificada"
- Convierte:
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
# CUENTAS VALIDAS
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
# LIMPIEZA JSON
# ==========================

def limpiar_json(texto: str) -> str:
    return (
        texto.replace("```json", "")
        .replace("```", "")
        .strip()
    )


# ==========================
# GUARDAR EN SHEETS
# ==========================

def guardar_movimiento(d):
    fecha = datetime.now().strftime("%Y-%m-%d")

    cuenta = d.get("cuenta", "No especificada").lower().strip()

    if cuenta in cuentas_validas:
        cuenta = cuentas_validas[cuenta]
    else:
        cuenta = "No especificada"

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
        # CASO: RESPONDIENDO CUENTA PENDIENTE
        # ==========================

        if chat_id and chat_id in pending_movements:
            movimiento = pending_movements.pop(chat_id)

            cuenta = mensaje.lower().strip()

            if cuenta in cuentas_validas:
                movimiento["cuenta"] = cuentas_validas[cuenta]
            else:
                movimiento["cuenta"] = "No especificada"

            guardar_movimiento(movimiento)

            return "✅ Cuenta registrada y movimiento guardado"

        # ==========================
        # CASO NORMAL
        # ==========================

        prompt = f"""
{contexto_usuario}

Extrae la información financiera del mensaje.

Puede haber uno o varios movimientos.

Devuelve SOLO JSON válido (lista).

Mensaje:
{mensaje}
"""

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        raw = response.text.strip()
        print("🤖 RAW GEMINI:", raw)

        clean = limpiar_json(raw)

        movimientos = json.loads(clean)

        if not isinstance(movimientos, list):
            return "❌ Gemini no devolvió una lista válida"

        resultados = []

        for d in movimientos:

            cuenta = d.get("cuenta", "No especificada").lower().strip()

            # ==========================
            # SI NO HAY CUENTA → PREGUNTAR
            # ==========================

            if cuenta == "no especificada":
                if chat_id:
                    pending_movements[chat_id] = d
                    return "🤔 ¿Qué cuenta fue? (Nequi, Nu, Davivienda, Bancolombia, Efectivo, Splitwise)"
                else:
                    d["cuenta"] = "No especificada"
            else:
                if cuenta in cuentas_validas:
                    d["cuenta"] = cuentas_validas[cuenta]
                else:
                    d["cuenta"] = "No especificada"

            guardar_movimiento(d)
            resultados.append(d)

        return f"✅ Guardado {len(resultados)} movimiento(s)"

    except json.JSONDecodeError:
        return "❌ Error: JSON inválido desde Gemini"

    except Exception as e:
        print("❌ ERROR GENERAL:", str(e))
        return "❌ Error procesando mensaje"