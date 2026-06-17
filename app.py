from flask import Flask, request
import os
import requests

from Finanzas_bot import procesar_mensaje

app = Flask(__name__)

# 🔐 Token de verificación (lo defines tú y lo pones también en Meta)
VERIFY_TOKEN = "mi_bot_whatsapp_123"

# 📦 Variables de entorno (Render)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")


# -----------------------------
# 🔐 VERIFICACIÓN WEBHOOK (META)
# -----------------------------
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge
    return "Error", 403


# -----------------------------
# 📩 RECIBIR MENSAJES WHATSAPP
# -----------------------------
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()

    try:
        value = data["entry"][0]["changes"][0]["value"]

        # Si no hay mensaje, no hacer nada
        if "messages" not in value:
            return "OK", 200

        message = value["messages"][0]["text"]["body"]
        sender = value["messages"][0]["from"]

        print("📩 Mensaje:", message)
        print("👤 Usuario:", sender)

        # 🤖 Procesar con tu lógica (Gemini + Sheets)
        respuesta = procesar_mensaje(message)

        # 📤 Responder por WhatsApp
        enviar_mensaje(sender, respuesta)

        return "OK", 200

    except Exception as e:
        print("❌ Error:", e)
        return "OK", 200


# -----------------------------
# 📤 ENVIAR MENSAJE WHATSAPP
# -----------------------------
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
        "text": {
            "body": texto
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    print("📤 WhatsApp response:", response.status_code, response.text)


# -----------------------------
# 🚀 RUN SERVER
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)