import os
import json
import re
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from google import genai


# ==========================
# CONFIG
# ==========================

SHEET_ID = os.environ["SHEET_ID"]

GOOGLE_CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

client = gspread.authorize(
    Credentials.from_service_account_info(
        GOOGLE_CREDENTIALS,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ],
    )
)

doc = client.open_by_key(SHEET_ID)

gastos_sheet = doc.worksheet("Gastos")
ingresos_sheet = doc.worksheet("Ingresos")


# ==========================
# GEMINI (NUEVO SDK)
# ==========================

ai = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)


# ==========================
# CONTEXTO (EL TUYO, INTACTO)
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


REGLAS IMPORTANTES:

- Devuelve SOLO JSON
- Puede haber uno o varios movimientos
- Si NO hay cuenta: "No especificada"
- Si NO dice ingreso → asumir gasto
- Convierte:
  - 18 lucas → 18000
  - 50k → 50000
  - 23 mil → 23000

Formato obligatorio:

[
  {
    "tipo": "gasto | ingreso",
    "categoria": "",
    "descripcion": "",
    "monto": 0,
    "cuenta": ""
  }
]

"""


# ==========================
# HELPERS
# ==========================

def limpiar_json(texto: str):
    texto = texto.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\[.*\]", texto, re.DOTALL)
    return json.loads(match.group()) if match else []


def detectar_tipo(texto: str):
    t = texto.lower()

    ingresos = [
        "ingreso", "me llegó", "me llegaron", "recibí",
        "me entró", "me entro", "me pagaron", "me consignaron"
    ]

    return "ingreso" if any(k in t for k in ingresos) else "gasto"


def normalizar_monto(texto: str):
    t = texto.lower()

    if m := re.findall(r"(\d+)\s*k", t):
        return int(m[0]) * 1000

    if m := re.findall(r"(\d+)\s*mil", t):
        return int(m[0]) * 1000

    if m := re.findall(r"\d+", t):
        return int(m[0])

    return 0


def guardar(d):
    fecha = datetime.now().strftime("%Y-%m-%d")

    fila = [
        fecha,
        d.get("categoria", ""),
        d.get("descripcion", ""),
        d.get("monto", 0),
        d.get("cuenta", "No especificada")
    ]

    if d["tipo"] == "ingreso":
        ingresos_sheet.append_row(fila)
    else:
        gastos_sheet.append_row(fila)


# ==========================
# GEMINI
# ==========================

def llamar_gemini(mensaje: str):

    prompt = f"""
{contexto_usuario}

Analiza el mensaje y extrae movimientos financieros.

IMPORTANTE:
- Si NO dice ingreso explícito → es gasto
- Puede haber varios movimientos
- Devuelve SOLO JSON válido

Mensaje:
{mensaje}
"""

    response = ai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text if response else None


# ==========================
# MAIN
# ==========================

def procesar_mensaje(mensaje: str):

    try:
        raw = llamar_gemini(mensaje)

        if not raw:
            return "⚠️ No recibí respuesta de Gemini"

        movimientos = limpiar_json(raw)

        if not movimientos:
            movimientos = [{
                "tipo": detectar_tipo(mensaje),
                "categoria": "No especificada",
                "descripcion": mensaje,
                "monto": normalizar_monto(mensaje),
                "cuenta": "No especificada"
            }]

        resultados = []

        for m in movimientos:

            m["tipo"] = detectar_tipo(mensaje)
            m["monto"] = m.get("monto") or normalizar_monto(mensaje)
            m["descripcion"] = m.get("descripcion") or mensaje
            m["cuenta"] = m.get("cuenta") or "No especificada"

            guardar(m)
            resultados.append(m)

        return "\n\n".join([
            f"""🧾 {r['descripcion']}
📂 {r['categoria']}
💰 {r['monto']}
🏦 {r['cuenta']}"""
            for r in resultados
        ])

    except Exception as e:
        print("❌ ERROR:", e)
        return "⚠️ Error procesando mensaje"