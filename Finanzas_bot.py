import json
from datetime import datetime
import os
import re

import gspread
from google.oauth2.service_account import Credentials
from google import genai


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
Conciertos en peñas con Pedro Bombo.

Clases:
Ingresos por clases.

Juan Pablo Luna:
Ingresos artísticos del proyecto personal.

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

- Devuelve SOLO una lista JSON válida
- Puede haber uno o varios movimientos

- Cada movimiento debe tener:

tipo
categoria
descripcion
monto
cuenta

- Si NO se menciona ingreso explícitamente:
asume SIEMPRE "gasto"

- Considera ingreso frases como:

"ingreso"
"me llegó"
"me llegaron"
"me entró"
"me entro"
"recibí"
"me pagaron"
"me consignaron"
"me depositaron"

- Si no se especifica cuenta:

"cuenta": "No especificada"

- Convierte:

18 lucas → 18000
50k → 50000
23 mil → 23000

"""


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

    texto = texto.strip()

    texto = (
        texto
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    start = texto.find("[")
    end = texto.rfind("]")

    if start == -1 or end == -1:
        raise ValueError(f"No encontré JSON:\n{texto}")

    json_text = texto[start:end+1]

    return json.loads(json_text)


# ==========================
# FALLBACK
# ==========================

def reparar(mensaje, d):

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

        "ingreso",

        "me llegó",
        "me llego",

        "me llegaron",

        "me entró",
        "me entro",

        "recibí",
        "recibi",

        "me pagaron",

        "me consignaron",

        "me depositaron"

    ]

    if any(x in texto for x in ingresos):
        return "ingreso"

    return "gasto"


# ==========================
# GUARDAR
# ==========================

def guardar(d):

    fecha = datetime.now().strftime("%Y-%m-%d")

    cuenta = d.get(
        "cuenta",
        "No especificada"
    ).lower().strip()

    cuenta = cuentas_validas.get(
        cuenta,
        "No especificada"
    )

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

    return {

        **d,

        "fecha": fecha,

        "cuenta": cuenta

    }


# ==========================
# GEMINI
# ==========================

def llamar_gemini(mensaje):

    prompt = f"""

{contexto_usuario}

Extrae la información financiera.

Devuelve SOLO una lista JSON válida.

Mensaje:

{mensaje}

"""

    response = client_genai.models.generate_content(

        model="gemini-2.5-flash",

        contents=prompt

    )

    if not response:

        raise ValueError("Gemini no respondió")

    if not response.text:

        raise ValueError("Gemini respondió vacío")

    return response.text


# ==========================
# MAIN
# ==========================

def procesar_mensaje(mensaje, chat_id=None):

    try:

        print("\n📥 MENSAJE:", mensaje)

        # =====================
        # RESPUESTA CUENTA
        # =====================

        if chat_id and chat_id in pending_movements:

            mov = pending_movements.pop(chat_id)

            cuenta = mensaje.lower().strip()

            mov["cuenta"] = cuentas_validas.get(

                cuenta,

                "No especificada"

            )

            saved = guardar(mov)

            return f"""

✅ Cuenta registrada y movimiento guardado

🧾 {saved['descripcion']}
💰 {saved['monto']}
🏦 {saved['cuenta']}

""".strip()

        # =====================
        # GEMINI
        # =====================

        raw = llamar_gemini(mensaje)

        print("🤖 RAW GEMINI:")

        print(raw)

        movimientos = extraer_json(raw)

        resultados = []

        for d in movimientos:

            d = reparar(mensaje, d)

            d["tipo"] = forzar_tipo(mensaje)

            cuenta = d.get(

                "cuenta",

                "No especificada"

            ).lower().strip()

            cuenta = cuentas_validas.get(

                cuenta,

                "No especificada"

            )

            d["cuenta"] = cuenta

            if cuenta == "No especificada":

                if chat_id:

                    pending_movements[chat_id] = d

                    return (

                        "🤔 ¿Qué cuenta fue?\n\n"

                        "Nequi\n"

                        "Nu\n"

                        "Davivienda\n"

                        "Bancolombia\n"

                        "Efectivo\n"

                        "Splitwise"

                    )

            saved = guardar(d)

            resultados.append(saved)

        return "\n\n".join([

            f"""🧾 Movimiento:

📂 {r['categoria']}

📝 {r['descripcion']}

💰 {r['monto']}

🏦 {r['cuenta']}"""

            for r in resultados

        ])

    except Exception as e:

        print("❌ ERROR COMPLETO:")

        print(repr(e))

        return f"⚠️ Error real: {str(e)}"