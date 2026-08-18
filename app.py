import os
from flask import Flask, request
from groq import Groq

app = Flask(__name__)

VERIFY_TOKEN = "trumark_books_123"
# Initialize Groq client using your saved environment variable
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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
                
                # Ask Groq (Llama 3) for a response
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are an enthusiastic AI assistant for Trumark Books. Keep responses helpful, direct, and concise for WhatsApp."},
                        {"role": "user", "content": incoming_msg}
                    ],
                    max_tokens=300
                )
                
                reply_text = response.choices[0].message.content
                print(f"Bot replied: {reply_text}")

        except Exception as e:
            print(f"Error processing message: {e}")
            
        return "OK", 200
