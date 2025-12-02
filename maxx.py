from flask import Flask, jsonify, request, render_template, session, redirect, url_for, flash
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta, date
import random
from bson.objectid import ObjectId
import uuid
import re
import bcrypt
import base64
import os

app = Flask(__name__)
app.secret_key = "q1w2e3r4t5y6u7i8o9p0zaxscdvfbgnhmjkl"

# Session configuration for HTTPS
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=1)
)

CORS(app, supports_credentials=True)

# MongoDB connection
client = MongoClient("mongodb+srv://umatiyaaziz2004_db_user:umatiyaaziz2004@coinmining.evt4i93.mongodb.net/")
db = client["crypto_mining"]
users_collection = db["users"]
user_data_collection = db["user_data"]

# Level rewards configuration
LEVEL_REWARDS = {
    1: 10.0, 2: 20.0, 3: 30.0, 4: 40.0, 5: 50.0,
    6: 60.0, 7: 70.0, 8: 80.0, 9: 90.0, 10: 100.0,
    11: 110.0, 12: 120.0, 13: 130.0, 14: 140.0, 15: 150.0,
    16: 160.0, 17: 170.0, 18: 180.0, 19: 190.0, 20: 200.0,
    21: 210.0, 22: 220.0, 23: 230.0, 24: 240.0, 25: 250.0
}

# Valid codes for claiming
VALID_CODES = ["AZIZ7860ZXCV", "WXYZ5678LKJH", "TEST0000CODE"]

# Helper function to convert ObjectId to string for JSON serialization
def serialize_user(user):
    user_copy = user.copy()
    if "_id" in user_copy:
        user_copy["_id"] = str(user_copy["_id"])
    return user_copy

# Helper function to format seconds into HH:MM:SS
def format_time(seconds):
    if seconds <= 0:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

# Helper function to trim transactions to last 10
def trim_transactions(user):
    if "transactions" in user and len(user["transactions"]) > 10:
        user["transactions"] = user["transactions"][-10:]

# Initialize user data in MongoDB for a specific email
def initialize_user(email):
    user = users_collection.find_one({"email": email})
    if not user:
        default_user = {
            "email": email,
            "level": 1,
            "exp": 0,
            "expThreshold": 500,
            "balance": 0.0,
            "miningActive": False,
            "lastMining": None,
            "miningStartTime": None,
            "lastBonus": None,
            "totalMined": 0.0,
            "miningTime": 0,
            "transactions": [],
            "receiveNotifications": True,
            "referralId": str(uuid.uuid4()),
            "referredUsers": [],
            "totalReferralBonus": 0.0,
            "miningBoost": {"active": False, "multiplier": 1.0, "expiresAt": None},
            "timeReduction": {"active": False, "reductionMinutes": 0, "expiresAt": None},
            "levelShield": {"active": False, "expiresAt": None},
            "lastMiningBoost": None,
            "lastScratch": None,
            "lastSpin": None,
            "lastQuiz": None,
            "gifts": {
                "channel": {"opened": None, "claimed": None},
                "video": {"opened": None, "claimed": None},
                "instagram": {"opened": None, "claimed": None}
            },
            "claimed_level_rewards": [],
            "claimed_codes": [],
            "lastActiveDate": None,
            "activeStreak": 0
        }
        users_collection.insert_one(default_user)
        user = users_collection.find_one({"email": email})
    else:
        updates = {}
        if "miningBoost" not in user:
            updates["miningBoost"] = {"active": False, "multiplier": 1.0, "expiresAt": None}
        if "timeReduction" not in user:
            updates["timeReduction"] = {"active": False, "reductionMinutes": 0, "expiresAt": None}
        if "levelShield" not in user:
            updates["levelShield"] = {"active": False, "expiresAt": None}
        if "lastMiningBoost" not in user:
            updates["lastMiningBoost"] = None
        if "lastScratch" not in user:
            updates["lastScratch"] = None
        if "lastSpin" not in user:
            updates["lastSpin"] = None
        if "lastQuiz" not in user:
            updates["lastQuiz"] = None
        if "gifts" not in user:
            updates["gifts"] = {
                "channel": {"opened": None, "claimed": None},
                "video": {"opened": None, "claimed": None},
                "instagram": {"opened": None, "claimed": None}
            }
        if "claimed_level_rewards" not in user:
            updates["claimed_level_rewards"] = []
        if "claimed_codes" not in user:
            updates["claimed_codes"] = []
        if "lastActiveDate" not in user:
            updates["lastActiveDate"] = None
        if "activeStreak" not in user:
            updates["activeStreak"] = 0
        if "balancePurchaseTier" in user:
            updates.pop("balancePurchaseTier", None)
        if updates:
            users_collection.update_one({"email": email}, {"$set": updates, "$unset": {"balancePurchaseTier": ""}})
            user = users_collection.find_one({"email": email})
    
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    
    return user

# Email validation function
def validate_email(email):
    email_pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    return bool(email_pattern.match(email))

# Password validation function
def validate_password(password, confirm_password):
    if password != confirm_password:
        return False, "Passwords do not match."
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number."
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character."
    
    return True, "Password is valid."

# Routes
@app.route('/', methods=['GET'])
def root():
    if session.get('user_id'):
        return redirect(url_for('serve_dashboard'))
    return redirect(url_for('serve_registration'))

@app.route('/home1', methods=['GET'])
def serve_home1():
    return render_template('home.html')

@app.route('/blog', methods=['GET'])
def serve_blog():
    return render_template('blog.html')

@app.route('/aboutus', methods=['GET'])
def serve_aboutus():
    return render_template('aboutus.html')

@app.route('/contact', methods=['GET'])
def serve_contact():
    return render_template('contact.html')

@app.route('/support', methods=['GET'])
def serve_support():
    return render_template('support.html')

@app.route('/dashboard', methods=['GET'])
def serve_dashboard():
    if not session.get('user_id'):
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('serve_login'))
    
    print(f"Session user_id: {session.get('user_id')}")
    print(f"Session email: {session.get('email')}")
    
    return render_template('dashboard/index.html')

@app.route('/login', methods=['GET', 'POST'])
def serve_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not validate_email(email):
            flash("Invalid email format.", "error")
            return redirect(url_for('serve_login'))

        user = user_data_collection.find_one({"email": email})
        if not user:
            flash("Email not found. Please register first.", "error")
            return redirect(url_for('serve_login'))

        if not bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            flash("Incorrect password.", "error")
            return redirect(url_for('serve_login'))

        session.permanent = True
        session['user_id'] = str(user["_id"])
        session['email'] = email
        
        flash("Login successful! Redirecting to dashboard...", "success")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                "success": True, 
                "message": "Login successful!", 
                "redirect": url_for('serve_dashboard')
            })
        
        return redirect(url_for('serve_dashboard'))

    return render_template('login.html')

@app.route('/logout', methods=['GET'])
def logout_user():
    session.pop('user_id', None)
    session.pop('email', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('serve_login'))

@app.route('/registration', methods=['GET'])
def serve_registration():
    return render_template('registration.html')

@app.route('/register_user', methods=['POST'])
def register_user():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('cpassword')
    refercode = request.form.get('refercode')

    if not validate_email(email):
        flash("Invalid email format.", "error")
        return redirect(url_for('serve_registration'))

    if user_data_collection.find_one({"email": email}):
        flash("Email is already registered.", "error")
        return redirect(url_for('serve_registration'))

    is_valid, message = validate_password(password, confirm_password)
    if not is_valid:
        flash(message, "error")
        return redirect(url_for('serve_registration'))

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    user_data = {
        "name": name,
        "email": email,
        "password": hashed_password,
        "created_at": datetime.now().timestamp(),
        "profile_image": None
    }
    user_data_collection.insert_one(user_data)

    new_user = initialize_user(email)

    if refercode:
        referrer = users_collection.find_one({"referralId": refercode})
        if referrer:
            referral_bonus = random.uniform(7.0, 20.0)
            referrer["totalReferralBonus"] = referrer.get("totalReferralBonus", 0.0) + referral_bonus
            referrer["balance"] = referrer.get("balance", 0.0) + referral_bonus
            referrer["referredUsers"].append({
                "email": email,
                "joinDate": datetime.now().timestamp() * 1000,
                "bonus": referral_bonus,
                "name": name
            })
            referrer["transactions"].append({
                "type": "REFERRAL",
                "date": datetime.now().timestamp() * 1000,
                "amount": referral_bonus
            })
            trim_transactions(referrer)
            users_collection.update_one({"referralId": refercode}, {"$set": referrer})
            new_user["balance"] += referral_bonus
            new_user["transactions"].append({
                "type": "REFERRAL_SIGNUP",
                "date": datetime.now().timestamp() * 1000,
                "amount": referral_bonus
            })
            trim_transactions(new_user)
            users_collection.update_one({"email": email}, {"$set": new_user})
            flash(f"Referral code applied! You and the referrer earned {referral_bonus:.2f} coins.", "success")
        else:
            flash("Invalid referral code.", "error")

    user = user_data_collection.find_one({"email": email})
    session['user_id'] = str(user["_id"])
    session['email'] = email

    flash("Registration successful! You are now logged in.", "success")
    return redirect(url_for('serve_dashboard'))

# Other dashboard routes...
@app.route('/profile', methods=['GET'])
def serve_profile():
    if not session.get('user_id'):
        flash("Please log in to access the profile page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/profile.html')

@app.route('/desh1', methods=['GET'])
def index():
    if not session.get('user_id'):
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/index.html')

@app.route('/gift', methods=['GET'])
def gift():
    if not session.get('user_id'):
        flash("Please log in to access the gift.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/gift.html')

@app.route('/statistics', methods=['GET'])
def statistics():
    if not session.get('user_id'):
        flash("Please log in to access the statistics page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/statistics.html')

@app.route('/speen', methods=['GET'])
def speen():
    if not session.get('user_id'):
        flash("Please log in to access the speen page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/speen.html')

@app.route('/settings', methods=['GET'])
def settings():
    if not session.get('user_id'):
        flash("Please log in to access the settings page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/settings.html')

@app.route('/referrals', methods=['GET'])
def referrals():
    if not session.get('user_id'):
        flash("Please log in to access the referrals page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/referrals.html')

@app.route('/help', methods=['GET'])
def help():
    if not session.get('user_id'):
        flash("Please log in to access the help page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/help.html')

@app.route('/shop', methods=['GET'])
def shop():
    if not session.get('user_id'):
        flash("Please log in to access the shop page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/shop.html')

@app.route('/rankings', methods=['GET'])
def rankings():
    if not session.get('user_id'):
        flash("Please log in to access the rankings page.", "error")
        return redirect(url_for('serve_login'))

    users = list(users_collection.find({}))
    rankings_data = []
    for user in users:
        email = user.get("email")
        user_data = user_data_collection.find_one({"email": email})
        username = user_data.get("name", "Unknown") if user_data else "Unknown"
        balance = user.get("balance", 0.0)
        rankings_data.append({
            "username": username,
            "balance": balance
        })
    
    rankings_data.sort(key=lambda x: x["balance"], reverse=True)
    for index, user in enumerate(rankings_data):
        user["rank"] = index + 1
    
    current_user_email = session.get('email', '')
    current_user_data = user_data_collection.find_one({"email": current_user_email})
    current_user_name = current_user_data.get("name", "Unknown") if current_user_data else "Unknown"
    
    return render_template('dashboard/rankings.html', rankings=rankings_data, current_user_name=current_user_name)

@app.route('/levels', methods=['GET'])
def levels():
    if not session.get('user_id'):
        flash("Please log in to access the levels page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/levels.html')

@app.route('/code-claim', methods=['GET'])
def code_claim():
    if not session.get('user_id'):
        flash("Please log in to access the code claim page.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/code_claim.html')

@app.route('/chatbot', methods=['GET'])
def serve_chatbot():
    if not session.get('user_id'):
        flash("Please log in to access the chatbot.", "error")
        return redirect(url_for('serve_login'))
    return render_template('dashboard/chatbot.html')

# API Routes (તમારા બાકીના API routes અહીં add કરો)

def update_level(user):
    while user["exp"] >= user["expThreshold"]:
        user["exp"] -= user["expThreshold"]
        user["level"] += 1
        user["expThreshold"] = 500 * (2 ** (user["level"] - 1))
    users_collection.update_one({"email": user["email"]}, {"$set": user})

@app.route('/api/user', methods=['GET'])
def get_user():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    
    # તમારો બાકીનો user data processing code અહીં add કરો
    # ...
    
    response = jsonify(serialize_user(user_copy))
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# તમારા બાકીના API routes અહીં add કરો...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8110))
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=False
    )