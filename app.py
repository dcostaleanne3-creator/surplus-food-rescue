import os  
from dotenv import load_dotenv  
from flask import Flask, request, jsonify, render_template
from model import predict_waste # This now matches the function in model.py
import smtplib
from email.message import EmailMessage
import sqlite3

load_dotenv()
app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('rescue.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS rescues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_type TEXT,
            guests INTEGER,
            quantity REAL,
            event_type TEXT,
            prediction REAL,
            status TEXT,
            assigned_ngo TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Credentials from your .env file
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
RECIPIENT_NGO = os.getenv("RECIPIENT_NGO")

def send_ngo_alert(food_data, amount):
    msg = EmailMessage()
    msg['Subject'] = f"🚨 URGENT: {amount}kg Surplus Food Rescue - Hubballi"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_NGO
    
    content = f"""
    Automatic Surplus Alert
    -----------------------
    Food Type: {food_data.get('Type of Food')}
    Event: {food_data.get('Event Type')}
    Measured Quantity: {food_data.get('Quantity of Food')} kg
    AI Predicted Waste: {amount} kg
    
    This quantity requires immediate pickup.
    """
    msg.set_content(content)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/rescue')
def rescue():
    return render_template('rescue.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect('rescue.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) as total_rescues, SUM(quantity) as total_kg FROM rescues')
    stats = c.fetchone()
    
    c.execute('SELECT * FROM rescues ORDER BY timestamp DESC LIMIT 10')
    recent_rescues = c.fetchall()
    conn.close()
    
    total_rescues = stats['total_rescues'] or 0
    total_kg = round(stats['total_kg'] or 0, 2)
    
    return render_template('dashboard.html', total_rescues=total_rescues, total_kg=total_kg, recent_rescues=recent_rescues)

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    try:
        # Use the trained model to get prediction
        prediction_val = predict_waste(data)
        
        # Define High Waste as anything over 30kg
        is_high = prediction_val > 30
        status = "High Waste" if is_high else "Low Waste"
        
        # Hubballi NGO Partners
        ngo_partners = [
            {"name": "Hubballi Food Rescue", "phone": "+91 94800-12345", "area": "Vidyanagar"},
            {"name": "Akshaya Patra Hubli", "phone": "0836-2233445", "area": "Rayapur"},
            {"name": "Sneha Foundation", "phone": "+91 87621-54321", "area": "Gokul Road"}
        ]

        action = "Logged"
        assigned_ngo = None
        if is_high:
            email_sent = send_ngo_alert(data, prediction_val)
            action = "NGO Notification Sent Successfully" if email_sent else "Email Alert Triggered"
            assigned_ngo = ngo_partners[0]['name']

        conn = sqlite3.connect('rescue.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO rescues (food_type, guests, quantity, event_type, prediction, status, assigned_ngo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data.get('Type of Food'), data.get('Number of Guests'), data.get('Quantity of Food'), data.get('Event Type'), prediction_val, status, assigned_ngo or "None"))
        conn.commit()
        conn.close()

        return jsonify({
            "predicted_waste": prediction_val,
            "status": status,
            "action": action,
            "ngos": ngo_partners if is_high else []
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)