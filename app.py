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

    print("\n🔥 WEBHOOK RECIBIDO")

    try:
        data = request.get_json(force=True, silent=True)

        if not data:
            print("⚠️ No data recibida")
            return "OK", 200

        print("📨 UPDATE:", json.dumps(data, indent=2, ensure_ascii=False))

        # ==========================
        # EXTRAER MENSAJE
        # ==========================

        message = (
            data.get("message")
            or data.get("edited_message")
            or data.get("channel_post")
            or (data.get("callback_query") or {}).get("message")
        )

        if not message:
            print("⚠️ Update sin message")
            return "OK", 200

        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        print("📩 TEXT:", text)
        print("👤 CHAT ID:", chat_id)

        if not chat_id:
            print("⚠️ Sin chat_id")
            return "OK", 200

        # ==========================
        # PROCESAR MENSAJE
        # ==========================

        respuesta = procesar_mensaje(text, chat_id)

        print("🤖 RESPUESTA:", respuesta)

        # ==========================
        # RESPONDER
        # ==========================

        enviar_mensaje(chat_id, respuesta)

    except Exception as e:
        print("❌ ERROR GENERAL:", str(e))

    return "OK", 200


# ==========================
# RUN LOCAL
# ==========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)