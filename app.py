from flask import Flask, request
import os
import requests
import json

from Finanzas_bot import procesar_mensaje

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def enviar_mensaje(chat_id, texto):
    if not TELEGRAM_TOKEN:
        print("❌ ERROR: TELEGRAM_TOKEN no está cargado")
        return

    url = f"{BASE_URL}/sendMessage"

    try:
        r = requests.post(url, data={
            "chat_id": chat_id,
            "text": texto
        })
        print("📤 Mensaje enviado:", r.status_code, r.text)
    except Exception as e:
        print("❌ ERROR enviando mensaje:", e)


@app.route("/", methods=["GET"])
def home():
    return "Bot activo 🚀", 200


@app.route("/webhook", methods=["POST"])
def webhook():

    print("\n🔥🔥 WEBHOOK RECIBIDO")

    try:
        # 🔥 Raw request (lo que realmente llega)
        raw = request.data
        print("📦 RAW:", raw)

        data = request.get_json(force=True, silent=True)

        print("📨 JSON:", json.dumps(data, indent=2))

        if not data:
            print("⚠️ No JSON recibido")
            return "OK", 200

        # 🔥 Captura TODOS los tipos posibles
        message = (
            data.get("message")
            or data.get("edited_message")
            or data.get("channel_post")
        )

        if not message:
            print("⚠️ Update sin message:", data)
            return "OK", 200

        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        print("📩 TEXTO:", text)
        print("👤 CHAT ID:", chat_id)

        if not text:
            print("⚠️ Mensaje sin texto")
            return "OK", 200

        # 🔥 tu lógica de negocio
        respuesta = procesar_mensaje(text)

        print("🤖 RESPUESTA:", respuesta)

        enviar_mensaje(chat_id, respuesta)

    except Exception as e:
        print("❌ ERROR GENERAL:", str(e))

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)