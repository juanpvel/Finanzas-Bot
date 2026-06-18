import json
from datetime import datetime
import os
import re
import traceback

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
# MEMORIA
# ==========================

pending_movements = {}


# ==========================
# CONTEXTO (INTACTO)
# ==========================

contexto_usuario = """(TU CONTEXTO EXACTO SIN CAMBIOS)"""


# ==========================
# SHEETS SAFE INIT
# ==========================

def init_sheets():
    try:
        creds = Credentials.from_service_account_info(
            json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"]),
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )

        client = gspread.authorize(creds)
        doc = client.open_by_key(SHEET_ID)

        return (
            doc.worksheet("Gastos"),
            doc.worksheet("Ingresos")
        )

    except Exception as e:
        print("❌ SHEETS INIT ERROR:", repr(e))
        return None, None


gastos_sheet, ingresos_sheet = init_sheets()


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
# GEMINI ULTRA SAFE
# ==========================

def llamar_gemini(mensaje, retries=2):
    prompt = f"""
{contexto_usuario}

REGLAS ESTRICTAS:
- Devuelve SOLO JSON válido
- SOLO lista de objetos
- Sin texto adicional
- Si hay múltiples acciones, separarlas

Si NO dice ingreso explícito → gasto

Mensaje:
{mensaje}
"""

    model = genai.GenerativeModel("gemini-2.5-flash")

    for i in range(retries):
        try:
            response = model.generate_content(prompt)
            raw = (response.text or "").strip()

            if raw:
                return raw

        except Exception as e:
            print(f"❌ GEMINI ERROR retry {i}:", repr(e))

    return ""


# ==========================
# JSON PARSER BLINDADO
# ==========================

def extraer_json(texto: str):
    texto = (texto or "").strip()
    texto = texto.replace("```json", "").replace("```", "")

    # intento 1: extracción directa
    match = re.search(r"\[[\s\S]*\]", texto)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    # intento 2: json completo
    try:
        return json.loads(texto)
    except:
        pass

    print("❌ JSON FALLIDO RAW:", texto)
    raise ValueError("No se pudo parsear JSON")


# ==========================
# FALLBACK INTELIGENTE
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
# GUARDAR SEGURO
# ==========================

def guardar(d):
    if gastos_sheet is None or ingresos_sheet is None:
        print("❌ SHEETS NO INICIALIZADO")
        return d

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

    try:
        if (d.get("tipo") or "gasto").lower() == "ingreso":
            ingresos_sheet.append_row(fila)
        else:
            gastos_sheet.append_row(fila)
    except Exception as e:
        print("❌ SHEETS WRITE ERROR:", repr(e))

    return {**d, "cuenta": cuenta}


# ==========================
# MAIN (ROBUSTO TOTAL)
# ==========================

def procesar_mensaje(mensaje, chat_id=None):

    try:
        print("📥 MENSAJE:", mensaje)

        # ======================
        # CUENTA PENDIENTE
        # ======================

        if chat_id and chat_id in pending_movements:
            mov = pending_movements.pop(chat_id)

            mov["cuenta"] = cuentas_validas.get(
                mensaje.lower().strip(),
                "No especificada"
            )

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

        if not raw:
            return "⚠️ No recibí respuesta de Gemini"

        print("🤖 RAW GEMINI:", raw)

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
        print("❌ FULL ERROR:\n", traceback.format_exc())
        return "⚠️ Error interno del sistema. Intenta de nuevo o reformula el mensaje."