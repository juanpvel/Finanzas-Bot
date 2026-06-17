import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from google import genai


# ==========================
# CONFIG
# ==========================

API_KEY = "TU_API_KEY"

NOMBRE_DOCUMENTO = "Cuentas Personales - Pruebas Python - Junio 2026"
ARCHIVO_CREDENCIALES = "asistente-finanzas-499718-bf933bb92551.json"


# ==========================
# GEMINI
# ==========================

gemini = genai.Client(api_key=API_KEY)


# ==========================
# GOOGLE SHEETS
# ==========================

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    ARCHIVO_CREDENCIALES,
    scopes=scopes
)

client = gspread.authorize(creds)

documento = client.open(NOMBRE_DOCUMENTO)

gastos_sheet = documento.worksheet("Gastos")
ingresos_sheet = documento.worksheet("Ingresos")


# ==========================
# FUNCIÓN PRINCIPAL (WHATSAPP)
# ==========================

def procesar_mensaje(mensaje):

    prompt = f"""
Extrae información financiera del mensaje.

Devuelve SOLO JSON en lista.

Mensaje:
{mensaje}
"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    texto = response.text.replace("```json", "").replace("```", "").strip()

    movimientos = json.loads(texto)

    resultados = []

    for datos in movimientos:

        fecha = datetime.now().strftime("%Y-%m-%d")

        fila = [
            fecha,
            datos["categoria"],
            datos["descripcion"],
            datos["monto"],
            datos["cuenta"]
        ]

        if datos["tipo"].lower() == "gasto":
            gastos_sheet.append_row(fila)
        else:
            ingresos_sheet.append_row(fila)

        resultados.append(datos)

    return f"✅ Guardado {len(resultados)} movimiento(s)"