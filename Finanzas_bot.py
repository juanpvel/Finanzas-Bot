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
# GOOGLE SHEETS
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
# UTIL: LIMPIAR RESPUESTA GEMINI
# ==========================

def limpiar_json(texto: str) -> str:
    return (
        texto.replace("```json", "")
        .replace("```", "")
        .strip()
    )


# ==========================
# FUNCIÓN PRINCIPAL
# ==========================

def procesar_mensaje(mensaje):

    try:
        print("📥 MENSAJE:", mensaje)

        prompt = f"""
Extrae información financiera del mensaje.

Devuelve SOLO JSON válido (sin texto adicional).

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

Mensaje:
{mensaje}
"""

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        raw_text = response.text.strip()

        print("🤖 RAW GEMINI:", raw_text)

        clean_text = limpiar_json(raw_text)

        movimientos = json.loads(clean_text)

        if not isinstance(movimientos, list):
            return "❌ Gemini no devolvió una lista válida"

        resultados = []

        for datos in movimientos:

            fecha = datetime.now().strftime("%Y-%m-%d")

            fila = [
                fecha,
                datos.get("categoria", ""),
                datos.get("descripcion", ""),
                datos.get("monto", 0),
                datos.get("cuenta", "")
            ]

            tipo = datos.get("tipo", "").lower()

            if tipo == "gasto":
                gastos_sheet.append_row(fila)
            elif tipo == "ingreso":
                ingresos_sheet.append_row(fila)
            else:
                print("⚠️ Tipo desconocido:", tipo)

            resultados.append(datos)

        return f"✅ Guardado {len(resultados)} movimiento(s)"

    except json.JSONDecodeError as e:
        print("❌ JSON ERROR:", str(e))
        return "❌ Error: Gemini devolvió JSON inválido"

    except Exception as e:
        print("❌ ERROR GENERAL:", str(e))
        return "❌ Error procesando mensaje"