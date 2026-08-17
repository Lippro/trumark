from flask import Flask, request

app = Flask(__name__)

# Our secret password
VERIFY_TOKEN = "trumark_books_123" 

# Notice we added 'POST' so the bot can receive messages
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # This handles the security check we did earlier
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Failed", 403

    elif request.method == 'POST':
        # This handles incoming text messages!
        data = request.get_json()
        
        # This prints the message to our Render screen
        print("NEW MESSAGE RECEIVED:", data)
        
        # We must tell WhatsApp we got the message, otherwise they keep sending it
        return "OK", 200
