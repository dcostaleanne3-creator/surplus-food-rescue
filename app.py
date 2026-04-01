import os  
from dotenv import load_dotenv  
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from model import predict_waste # This now matches the function in model.py
import smtplib
from email.message import EmailMessage
import sqlite3
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super_secret_professional_key_develop")

# Configure Gemini for Chatbot
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    chat_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    chat_model = None

# Handle dynamic database path for Vercel vs Local
DB_PATH = '/tmp/rescue.db' if os.environ.get('VERCEL') else 'rescue.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS rescues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        c.execute('ALTER TABLE rescues ADD COLUMN user_id INTEGER')
    except:
        pass
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

# Initialize the database immediately
init_db()

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password)
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', (name, email, hashed_pw))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered. Try logging in.', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access your dashboard.', 'error')
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) as total_rescues, SUM(quantity) as total_kg FROM rescues WHERE user_id = ?', (session['user_id'],))
    stats = c.fetchone()
    
    c.execute('SELECT SUM(amount) as total_funds FROM donations WHERE user_id = ?', (session['user_id'],))
    funds_stats = c.fetchone()
    
    c.execute('SELECT * FROM rescues WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10', (session['user_id'],))
    recent_rescues = c.fetchall()
    conn.close()
    
    total_rescues = stats['total_rescues'] or 0
    total_kg = round(stats['total_kg'] or 0, 2)
    total_funds = round(funds_stats['total_funds'] or 0, 2)
    
    return render_template('dashboard.html', total_rescues=total_rescues, total_kg=total_kg, total_funds=total_funds, recent_rescues=recent_rescues)

@app.route('/donate', methods=['GET', 'POST'])
def donate():
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        message = request.form.get('message', '')
        user_id = session.get('user_id')
        
        if amount > 0:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO donations (user_id, amount, message) VALUES (?, ?, ?)', (user_id, amount, message))
            conn.commit()
            conn.close()
            flash(f'Thank you! Your donation of ₹{amount} has been received successfully.', 'success')
            return redirect(url_for('dashboard') if user_id else url_for('home'))
        else:
            flash('Please enter a valid amount.', 'error')
            
    return render_template('donate.html')

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

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        user_id = session.get('user_id')
        c.execute('''
            INSERT INTO rescues (user_id, food_type, guests, quantity, event_type, prediction, status, assigned_ngo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, data.get('Type of Food'), data.get('Number of Guests'), data.get('Quantity of Food'), data.get('Event Type'), prediction_val, status, assigned_ngo or "None"))
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

@app.route('/chat', methods=['POST'])
def chat():
    """Personal Communication Agent endpoint"""
    data = request.json
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return jsonify({"reply": "I'm here to help! What's on your mind?"})
        
    if chat_model:
        try:
            prompt = f"You are a helpful, extremely concise, and professional Personal Communication Agent for 'Hubballi Rescue', a surplus food rescue platform. Be polite and give short answers. User says: {user_msg}"
            response = chat_model.generate_content(prompt)
            reply = response.text
        except Exception as e:
            reply = "I'm sorry, I am currently experiencing an issue connecting to my AI processing servers."
    else:
        # Fallback simplistic responses if no API key is provided
        lower_msg = user_msg.lower()
        if 'money' in lower_msg or 'fund' in lower_msg or 'financial' in lower_msg:
            reply = "To make a financial contribution, please click on 'Donate Funds' in the navigation menu."
        elif 'food' in lower_msg or 'rescue' in lower_msg or 'surplus' in lower_msg:
            reply = "To log surplus food, simply click on the 'Rescue Food' button in the navigation bar."
        elif 'donate' in lower_msg:
            reply = "We accept both food and financial donations! Use 'Rescue Food' to log food, or 'Donate Funds' for a monetary contribution."
        elif 'hi' in lower_msg or 'hello' in lower_msg:
            reply = "Hello! I am your Hubballi Rescue Personal Agent. How can I assist you with your mission today?"
        elif 'contact' in lower_msg:
            reply = "You can reach our team via the Contact menu or directly drop an email at hello@hubballirescue.org."
        else:
            reply = ("Thank you for reaching out! I'm currently running in limited offline mode "
                     "(add GEMINI_API_KEY to the .env file to unlock my full AI potential). "
                     "Is there anything specific about Hubballi Rescue I can help with?")
            
    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(debug=True, port=5001)