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
        print("📤 RESPUESTA TELEGRAM:", r.status_code, r.text)
    except Exception as e:
        print("❌ ERROR enviando mensaje:", e)


@app.route("/", methods=["GET"])
def home():
    return "Bot activo 🚀", 200


@app.route("/webhook", methods=["POST"])
def webhook():

    print("\n🔥🔥 WEBHOOK RECIBIDO")

    try:
        data = request.get_json(force=True, silent=True)

        print("📦 RAW:", request.data)

        print("📨 JSON:", json.dumps(data, indent=2, ensure_ascii=False))

        if not data:
            print("⚠️ No data recibida")
            return "OK", 200

        print("🔑 KEYS:", list(data.keys()))

        # 🔥 EXTRACCIÓN ROBUSTA DE MENSAJE
        message = None
        chat_id = None
        text = None

        # CASO 1: mensaje normal
        if "message" in data:
            message = data["message"]

        # CASO 2: editado
        elif "edited_message" in data:
            message = data["edited_message"]

        # CASO 3: canal
        elif "channel_post" in data:
            message = data["channel_post"]

        # CASO 4: callback (botones)
        elif "callback_query" in data:
            message = data["callback_query"].get("message")

        if not message:
            print("⚠️ No message encontrado en update")
            return "OK", 200

        chat_id = message.get("chat", {}).get("id")
        text = message.get("text")

        print("📩 TEXT:", text)
        print("👤 CHAT ID:", chat_id)

        if not chat_id:
            print("⚠️ Sin chat_id")
            return "OK", 200

        if not text:
            print("⚠️ Mensaje sin texto (posible sticker, audio, etc.)")
            text = ""

        # 🔥 TU LÓGICA
        respuesta = procesar_mensaje(text)

        print("🤖 RESPUESTA:", respuesta)

        enviar_mensaje(chat_id, respuesta)

    except Exception as e:
        print("❌ ERROR GENERAL:", str(e))

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)