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

SPREADSHEET_ID = "1DlRusdmea8CxpbCaHJmyMXYcJiqF83On"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv"

client = Groq(api_key=GROQ_API_KEY)

def fetch_live_inventory():
    """Parses consolidated Google Sheet inventory cleanly for Groq AI."""
    try:
        # Enforce utf-8 encoding when fetching CSV
        df = pd.read_csv(CSV_URL, header=None, encoding='utf-8')
        
        inventory_summary = ""
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        for index, row in df.iterrows():
            vals = [str(x).strip() for x in row.values if pd.notna(x)]
            
            if len(vals) >= 2:
                possible_price = vals[-1].replace(',', '').replace('.0', '')
                
                if possible_price.isdigit() and int(possible_price) > 500:
                    clean_parts = []
                    for v in vals[:-1]:
                        if v.isdigit() or v.lower() in ['no.', 'level', 'subject', 'price (tzs)']:
                            continue
                        clean_parts.append(v)
                    
                    title = " ".join(clean_parts)
                    
                    if "TOTAL" not in title.upper() and title:
                        inventory_summary += f"- {title}: {possible_price} TZS (In Stock)\n"
                        
        if not inventory_summary:
            return "Inventory data currently unavailable."
            
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
                
                # Safe printing for logs
                print(f"User ({sender_id}) said: {incoming_msg.encode('utf-8', errors='ignore').decode('utf-8')}")

                live_inventory = fetch_live_inventory()

                system_prompt = f"""
You are the official bilingual AI customer service assistant for Trumark Bookshop & Stationery in Dar es Salaam.

=== LANGUAGE & TRANSLATION RULES ===
- You MUST respond in the EXACT same language used by the customer (Kiswahili or English).
- If the customer asks in Kiswahili, reply in natural, polite, customer-friendly Kiswahili.
- MAPPING SEARCH TERMS: The inventory catalog below is written in English. You must translate Kiswahili queries to English terms BEFORE searching:
  * "Hisabati" -> "Mathematics" or "Arithmetic"
  * "Kiingereza" -> "English" or "Learn English"
  * "Afya na Mazingira" -> "Health and Environment"
  * "Sayansi" -> "Science"
  * "Jiografia" -> "Geography"
  * "Lugha" / "Sanaa" -> "Literature" / "Creative Arts"
  * "Darasa la Kwanza / Pili..." -> "Standard One / Two..."
  * "Kidato cha Kwanza / Pili / Tatu / Nne / Tano / Sita" -> "Form One / Two / Three / Four / Five / Six"

=== STORE INFORMATION ===
- Location: Kimara Stopover Saranga, Dar es Salaam
- Operating Hours: Lunes - Jumapili / Mon - Sun (7:30 AM - 9:00 PM)
- Contact: +255 753 611 005
- Website: http://www.trumark.co.tz/

=== LIVE INVENTORY CATALOG ===
{live_inventory}

=== BOT GUIDELINES ===
- Check the catalog carefully using translated terms.
- If the requested book is found in stock, state the exact price in TZS and invite them to visit or buy.
- If the requested book is NOT listed, state politely (in their language) that it can be special-ordered within 3 business days.
"""

                response = client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": incoming_msg}
                    ],
                    max_tokens=300
                )
                reply_text = response.choices[0].message.content

                # Send WhatsApp Response via POST request
                url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
                headers = {
                    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                    "Content-Type": "application/json; charset=utf-8"
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
