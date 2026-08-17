from flask import Flask, request

app = Flask(__name__)

# This is a secret password we will give to WhatsApp later
VERIFY_TOKEN = "trumark_books_123" 

# This creates the "door" (webhook) for WhatsApp to knock on
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    # Check if WhatsApp is knocking and has the right password
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Trumark Bot is running!", 200
