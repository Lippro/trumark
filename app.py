import os
import requests
from flask import Flask, request
from groq import Groq

app = Flask(__name__)

VERIFY_TOKEN = "trumark_books_123"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = "255733130059"

client = Groq(api_key=GROQ_API_KEY)

@app.route('/', methods=['GET'])
def home():
    return "Trumark Bot is Live!", 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Failed", 403

    elif request.method == 'POST':
        data = request.get_json()
        
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' in value:
                incoming_msg = value['messages'][0]['text']['body']
                sender_id = value['messages'][0]['from']
                
                print(f"User ({sender_id}) said: {incoming_msg}")

                # 1. Ask Groq for an answer
                response = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": "You are an enthusiastic AI assistant for Trumark Books. Keep responses helpful, direct, and short for WhatsApp."},
                        {"role": "user", "content": incoming_msg}
                    ],
                    max_tokens=300
                )
                reply_text = response.choices[0].message.content

                # 2. Send response back to WhatsApp
                url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
                headers = {
                    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "to": sender_id,
                    "type": "text",
                    "text": {"body": reply_text}
                }
                wa_response = requests.post(url, json=payload, headers=headers)
                print(f"WhatsApp Delivery Status: {wa_response.text}")

        except Exception as e:
            print(f"Error processing message: {e}")
            
        return "OK", 200
