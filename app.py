@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        print("🔥 VERIFICACIÓN WEBHOOK")

        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge

        return "Error", 403

    if request.method == "POST":
        print("🔥 WEBHOOK POST RECIBIDO")

        data = request.get_json()

        try:
            value = data["entry"][0]["changes"][0]["value"]

            if "messages" not in value:
                return "OK", 200

            message = value["messages"][0]["text"]["body"]
            sender = value["messages"][0]["from"]

            print("📩 Mensaje:", message)
            print("👤 Usuario:", sender)

            respuesta = procesar_mensaje(message)

            enviar_mensaje(sender, respuesta)

            return "OK", 200

        except Exception as e:
            print("❌ Error:", e)
            return "OK", 200