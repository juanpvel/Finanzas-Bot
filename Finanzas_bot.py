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


# ==========================
# GEMINI
# ==========================

genai.configure(api_key=API_KEY)


# ==========================
# GOOGLE SHEETS (SIN ARCHIVO LOCAL)
# ==========================

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

creds = Credentials.from_service_account_info(
    creds_info,
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

Devuelve SOLO una lista JSON.

Mensaje:
{mensaje}

Formato:
[
  {{
    "tipo": "Gasto o Ingreso",
    "categoria": "",
    "descripcion": "",
    "monto": 0,
    "cuenta": "Nequi / Nu / Davivienda / Bancolombia / Efectivo / Splitwise / No especificada"
  }}
]
"""

    response = genai.GenerativeModel(
        "gemini-2.5-flash"
    ).generate_content(prompt)

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