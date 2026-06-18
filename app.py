from flask import Flask, request
import os
import requests

from Finanzas_bot import procesar_mensaje

app = Flask(__name__)

VERIFY_TOKEN = "mi_bot_whatsapp_123"

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge
        return "Error", 403

    if request.method == "POST":
        print("🔥 WEBHOOK POST")

        data = request.get_json()

        try:
            value = data["entry"][0]["changes"][0]["value"]

            if "messages" not in value:
                return "OK", 200

            message = value["messages"][0]["text"]["body"]
            sender = value["messages"][0]["from"]

            print("📩", message)

            respuesta = procesar_mensaje(message)

            enviar_mensaje(sender, respuesta)

            return "OK", 200

        except Exception as e:
            print("ERROR:", e)
            return "OK", 200


def enviar_mensaje(numero, texto):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }

    requests.post(url, headers=headers, json=payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)