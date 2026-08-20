import os
import json
import requests
import pandas as pd
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, session
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "trumark_secret_key_987")

VERIFY_TOKEN = "trumark_books_123"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = "1331551090031101"
OWNER_PHONE_NUMBER = os.environ.get("OWNER_PHONE_NUMBER", "255753611005")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "Trumark2026!")

SPREADSHEET_ID = "1DlRusdmea8CxpbCaHJmyMXYcJiqF83On"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv"

client = Groq(api_key=GROQ_API_KEY)

# Store recent conversations in memory for the dashboard
CONVERSATIONS = {}

def get_gspread_client():
    """Connects to Google Sheets using the JSON credentials stored in Render."""
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            print("ERROR: GOOGLE_CREDENTIALS_JSON environment variable is missing!")
            return None
        
        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Google Sheets Auth Error: {e}")
        return None

def log_order_to_sheet(customer_number, items_requested):
    """Appends a new order row to the 'Orders' tab in Google Sheets."""
    try:
        gc = get_gspread_client()
        if gc:
            sh = gc.open_by_key(SPREADSHEET_ID)
            try:
                worksheet = sh.worksheet("Orders")
            except Exception:
                worksheet = sh.add_worksheet(title="Orders", rows="100", cols="4")
                worksheet.append_row(["Timestamp", "Customer WhatsApp Number", "Item(s)", "Status"])
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            worksheet.append_row([now_str, str(customer_number), items_requested, "Pending"])
            print(f"SUCCESS: Order logged to Google Sheet for {customer_number}")
            return True
        else:
            print("FAILED: Could not authenticate with Google Sheets.")
    except Exception as e:
        print(f"Error logging order to sheet: {e}")
    return False

def send_whatsapp_message(to_number, text_content):
    """Sends a WhatsApp text message via Meta Graph API."""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_content}
    }
    res = requests.post(url, json=payload, headers=headers)
    print(f"WhatsApp Delivery Status: {res.text}")
    return res

def send_owner_notification(customer_number, items):
    """Sends an immediate order notification alert to the shop owner's WhatsApp."""
    if OWNER_PHONE_NUMBER:
        msg = f"🚨 *NEW CONFIRMED ORDER!*\n\n• *Customer:* +{customer_number}\n• *Item(s):* {items}\n• *Status:* Pending\n\nThe customer has confirmed their order. Please contact them to finalize delivery!"
        send_whatsapp_message(OWNER_PHONE_NUMBER, msg)

def fetch_live_inventory():
    """Parses consolidated Google Sheet inventory cleanly for Groq AI."""
    try:
        df = pd.read_csv(CSV_URL, header=None)
        inventory_summary = ""
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        for index, row in df.iterrows():
            vals = [str(x).strip() for x in row.values if pd.notna(x)]
            if len(vals) >= 2:
                possible_price = vals[-1].replace(',', '').replace('.0', '')
                if possible_price.isdigit() and int(possible_price) > 500:
                    clean_parts = [v for v in vals[:-1] if not v.isdigit() and v.lower() not in ['no.', 'level', 'subject', 'price (tzs)']]
                    title = " ".join(clean_parts)
                    if "TOTAL" not in title.upper() and title:
                        inventory_summary += f"- {title}: {possible_price} TZS (In Stock)\n"
        return inventory_summary if inventory_summary else "Inventory data currently unavailable."
    except Exception as e:
        print(f"Error fetching inventory: {e}")
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

                # Log conversation for live dashboard
                CONVERSATIONS[sender_id] = {
                    "last_message": incoming_msg,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }

                live_inventory = fetch_live_inventory()

                system_prompt = f"""
You are the official customer service assistant for Trumark Bookshop & Stationery in Kimara Stopover, Dar es Salaam.

=== LANGUAGE INSTRUCTION ===
Respond in the EXACT same language used by the customer (English or Kiswahili).

=== LIVE INVENTORY CATALOG ===
{live_inventory}

=== GUIDELINES & TWO-STEP ORDER CONFIRMATION ===
1. If a customer asks for a book or price, provide the price and ask if they would like to place an order.
2. STEP 1 (Asking for Confirmation): If the customer expresses interest in buying (e.g. "nataka kununua", "I want to buy"), DO NOT submit the order yet. First state the book title and total price, then explicitly ask them to reply with "YES" / "NDIO" to confirm their order.
3. STEP 2 (Customer Confirms): IF AND ONLY IF the customer explicitly confirms (e.g., says "yes", "ndio", "thibitisha", "confirm", "sawa ninaomba"), thank them, state that our shop team will contact them shortly, AND append `[ORDER_CONFIRMED: book names]` at the very end of your response.

DO NOT append `[ORDER_CONFIRMED:]` until the customer has explicitly said YES / NDIO / CONFIRM.
"""

                response = client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": incoming_msg}
                    ],
                    max_tokens=300
                )
                
                reply_text = response.choices[0].message.content or ""

                # Check if an order was explicitly confirmed by the user
                if "[ORDER_CONFIRMED:" in reply_text:
                    try:
                        order_details = reply_text.split("[ORDER_CONFIRMED:")[1].split("]")[0].strip()
                    except Exception:
                        order_details = incoming_msg
                    
                    # Clean tag from customer reply
                    reply_text = reply_text.split("[ORDER_CONFIRMED:")[0].strip()
                    
                    # 1. Log to Google Sheets
                    log_order_to_sheet(sender_id, order_details)
                    
                    # 2. Alert the owner on WhatsApp
                    send_owner_notification(sender_id, order_details)

                if not reply_text.strip():
                    reply_text = "Habari! Karibu Trumark Bookshop. Tunaomba kurudia ujumbe wako au tupigie +255 753 611 005 kwa msaada zaidi."

                send_whatsapp_message(sender_id, reply_text.strip())

        except Exception as e:
            print(f"Error processing message: {e}")
            
        return "OK", 200

# ================= LIVE DASHBOARD ROUTES =================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Trumark Live Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 20px; }
        h1, h2 { color: #1a252f; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #2c3e50; color: white; }
        .status-pending { background: #ffeaa7; color: #d63031; font-weight: bold; padding: 4px 8px; border-radius: 4px; }
        .status-confirmed { background: #55efc4; color: #00b894; font-weight: bold; padding: 4px 8px; border-radius: 4px; }
        .btn { background: #0984e3; color: white; border: none; padding: 8px 12px; border-radius: 4px; text-decoration: none; font-size: 14px; }
    </style>
</head>
<body>
    <h1>📚 Trumark Bookshop — Live Dashboard</h1>
    <p>Auto-refreshes every 30 seconds. <a href="/dashboard" class="btn">🔄 Refresh Now</a> <a href="/logout" style="margin-left:10px; color:red;">Logout</a></p>

    <div class="card">
        <h2>🛍️ Pending Confirmed Orders</h2>
        <table>
            <tr><th>Timestamp</th><th>Customer Number</th><th>Item(s)</th><th>Status</th></tr>
            {% for order in pending_orders %}
            <tr>
                <td>{{ order.Timestamp }}</td>
                <td><a href="https://wa.me/{{ order['Customer WhatsApp Number'] }}" target="_blank" class="btn">💬 Chat +{{ order['Customer WhatsApp Number'] }}</a></td>
                <td>{{ order['Item(s)'] }}</td>
                <td><span class="status-pending">{{ order.Status }}</span></td>
            </tr>
            {% else %}
            <tr><td colspan="4">No pending confirmed orders found in Google Sheet.</td></tr>
            {% endfor %}
        </table>
    </div>

    <div class="card">
        <h2>✅ Completed Orders</h2>
        <table>
            <tr><th>Timestamp</th><th>Customer Number</th><th>Item(s)</th><th>Status</th></tr>
            {% for order in confirmed_orders %}
            <tr>
                <td>{{ order.Timestamp }}</td>
                <td>+{{ order['Customer WhatsApp Number'] }}</td>
                <td>{{ order['Item(s)'] }}</td>
                <td><span class="status-confirmed">{{ order.Status }}</span></td>
            </tr>
            {% else %}
            <tr><td colspan="4">No completed orders yet.</td></tr>
            {% endfor %}
        </table>
    </div>

    <div class="card">
        <h2>💬 Active WhatsApp Conversations</h2>
        <table>
            <tr><th>Customer Number</th><th>Last Message</th><th>Time</th></tr>
            {% for phone, data in conversations.items() %}
            <tr>
                <td><a href="https://wa.me/{{ phone }}" target="_blank" class="btn">+{{ phone }}</a></td>
                <td>{{ data.last_message }}</td>
                <td>{{ data.timestamp }}</td>
            </tr>
            {% else %}
            <tr><td colspan="3">No active chats recorded yet.</td></tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Login — Trumark</title>
    <style>
        body { font-family: Arial; background: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-card { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 300px; text-align: center; }
        input[type="password"] { width: 90%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 4px; }
        button { background: #2c3e50; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; width: 100%; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>🔐 Trumark Admin Login</h2>
        {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
        <form method="POST" action="/login">
            <input type="password" name="password" placeholder="Enter Password" required><br>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == DASHBOARD_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid password. Try again."
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    pending_orders = []
    confirmed_orders = []
    
    try:
        gc = get_gspread_client()
        if gc:
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.worksheet("Orders")
            records = worksheet.get_all_records()
            
            for row in records:
                status = str(row.get("Status", "")).strip().capitalize()
                if status == "Pending":
                    pending_orders.append(row)
                elif status in ["Confirmed", "Completed"]:
                    confirmed_orders.append(row)
    except Exception as e:
        print(f"Error loading dashboard orders: {e}")

    return render_template_string(
        DASHBOARD_HTML,
        pending_orders=pending_orders,
        confirmed_orders=confirmed_orders,
        conversations=CONVERSATIONS
    )
