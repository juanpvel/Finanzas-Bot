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

if not TELEGRAM_TOKEN:
    print("❌ FALTA TELEGRAM_TOKEN EN VARIABLES DE ENTORNO")

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ==========================
# TELEGRAM SEND
# ==========================

def enviar_mensaje(chat_id, texto):
    try:
        url = f"{BASE_URL}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": texto
        }

        r = requests.post(url, data=payload, timeout=10)

        print("📤 Telegram response:", r.status_code)

        if r.status_code != 200:
            print("⚠️ Telegram error:", r.text)

    except Exception as e:
        print("❌ Error enviando mensaje:", str(e))


# ==========================
# HEALTH CHECK
# ==========================

@app.route("/", methods=["GET"])
def home():
    return "Bot activo 🚀", 200


# ==========================
# WEBHOOK
# ==========================

@app.route("/webhook", methods=["POST"])
def webhook():

    try:
        data = request.get_json(force=True, silent=True)

        print("\n🔥 WEBHOOK RECIBIDO")
        print("📦 DATA:", json.dumps(data, indent=2))

        if not data:
            return "OK", 200

        message = data.get("message") or data.get("edited_message")

        if not message:
            return "OK", 200

        text = message.get("text")
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            return "OK", 200

        print("📩 Mensaje:", text)
        print("👤 Chat:", chat_id)

        # ==========================
        # BOT CORE
        # ==========================

        respuesta = procesar_mensaje(text, chat_id)

        print("🤖 Respuesta:", respuesta)

        enviar_mensaje(chat_id, respuesta)

        return "OK", 200

    except Exception as e:
        print("❌ ERROR WEBHOOK:", str(e))
        return "OK", 200


# ==========================
# RUN LOCAL
# ==========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)