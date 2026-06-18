from flask import Flask, request
import os
import requests

from Finanzas_bot import procesar_mensaje

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def enviar_mensaje(chat_id, texto):
    url = f"{BASE_URL}/sendMessage"
    requests.post(url, data={
        "chat_id": chat_id,
        "text": texto
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    print("🔥 Telegram webhook recibido")

    data = request.get_json()

    try:
        message = data.get("message")
        if not message:
            return "OK", 200

        text = message.get("text", "")
        chat_id = message["chat"]["id"]

        print("📩", text)

        respuesta = procesar_mensaje(text)

        enviar_mensaje(chat_id, respuesta)

        return "OK", 200

    except Exception as e:
        print("ERROR:", e)
        return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)