from flask import Flask, request
import os
import requests
import json

from Finanzas_bot import procesar_mensaje

app = Flask(__name__)

# ==========================
# CONFIG
# ==========================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ==========================
# ENVIAR MENSAJE TELEGRAM
# ==========================

def enviar_mensaje(chat_id, texto):
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN no cargado")
        return

    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": texto
            }
        )
        print("📤 TELEGRAM RESPONSE:", r.status_code, r.text)

    except Exception as e:
        print("❌ ERROR enviando mensaje:", e)


# ==========================
# HEALTH CHECK
# ==========================

@app.route("/", methods=["GET"])
def home():
    return "Bot activo 🚀", 200


# ==========================
# WEBHOOK TELEGRAM
# ==========================

@app.route("/webhook", methods=["POST"])
def webhook():

    print("\n🔥🔥 WEBHOOK HIT REAL")

    raw = request.data
    print("📦 RAW:", raw)

    data = request.get_json(force=True, silent=True)
    print("📨 JSON:", data)

    return "OK", 200


# ==========================
# RUN LOCAL (IGNORADO EN RENDER)
# ==========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)