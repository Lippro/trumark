import os
import requests
import pandas as pd
from flask import Flask, request
from groq import Groq

app = Flask(__name__)

VERIFY_TOKEN = "trumark_books_123"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = "1331551090031101"

# Replace this with your actual Google Spreadsheet ID
SPREADSHEET_ID = "1iVDKEyo1R8sUOd5h_XpEdXWYgBbj16Kl"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv"

client = Groq(api_key=GROQ_API_KEY)

def fetch_live_inventory():
    """Fetches real-time inventory from Google Sheets."""
    try:
        df = pd.read_csv(CSV_URL)
        
        # Clean up hidden spaces in column headers to prevent KeyErrors
        df.columns = df.columns.str.strip()
        
        # Convert spreadsheet rows into a readable summary for AI
        inventory_summary = ""
        for _, row in df.iterrows():
            inventory_summary += f"- {row['Title']} by {row['Author']}: {row['Price']} TZS (Stock: {row['Stock']})\n"
        return inventory_summary
    except Exception as e:
        print(f"Error fetching inventory from Google Sheets: {e}")
        return "Inventory data currently unavailable."

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

                # Get real-time inventory from Google Sheet
                def fetch_live_inventory():
    """Fetches real-time inventory from Google Sheets."""
    try:
        df = pd.read_csv(CSV_URL)
        
        # Clean up hidden spaces in column headers to prevent KeyErrors
        df.columns = df.columns.str.strip()
        
        # Convert spreadsheet rows into a readable summary for AI
        inventory_summary = ""
        for _, row in df.iterrows():
            inventory_summary += f"- {row['Title']} by {row['Author']}: {row['Price']} TZS (Stock: {row['Stock']})\n"
        return inventory_summary
    except Exception as e:
        print(f"Error fetching inventory from Google Sheets: {e}")
        return "Inventory data currently unavailable."
You are the official AI assistant for Trumark Bookshop & Stationery.

# Make sure your system_prompt looks like this string block:
system_prompt = f"""
You are the official AI assistant for Trumark Bookshop & Stationery.

=== STORE INFORMATION ===
- Location: Kimara Stopover Saranga, Dar es Salaam
- Operating Hours: Monday - Sunday (7:30 AM - 9:00 PM)
- Contact: +255 753 611 005
- Website: http://www.trumark.co.tz/

=== LIVE INVENTORY CATALOG ===
{live_inventory}
"""

=== BOT GUIDELINES ===
- Answer customer questions accurately using the LIVE INVENTORY list above.
- If a book is in stock (Stock > 0), provide the price and invite them to place an order or visit the shop.
- If a book has 0 stock or is not listed, inform the customer that it can be special-ordered within 3 business days.
- Keep WhatsApp replies polite, helpful, and concise.
"""

                # Call Groq AI
                response = client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": incoming_msg}
                    ],
                    max_tokens=300
                )
                reply_text = response.choices[0].message.content

                # Send WhatsApp Response
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
