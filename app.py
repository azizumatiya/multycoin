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
import hashlib

app = Flask(__name__)
app.secret_key = "q1w2e3r4t5y6u7i8o9p0zaxscdvfbgnhmjkl"
app.config['SESSION_COOKIE_SECURE'] = True  # Enable for HTTPS (deployed tunnel); set to False for local HTTP
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
CORS(app)

# MongoDB connection
client = MongoClient("mongodb+srv://umatiyaaziz2004_db_user:umatiyaaziz2004@coinmining.evt4i93.mongodb.net/")
db = client["crypto_mining"]
users_collection = db["users"]
user_data_collection = db["user_data"]

# Level rewards configuration
LEVEL_REWARDS = {
    1: 10.0,
    2: 20.0,
    3: 30.0,
    4: 40.0,
    5: 50.0,
    6: 60.0,
    7: 70.0,
    8: 80.0,
    9: 90.0,
    10: 100.0,
    11: 110.0,
    12: 120.0,
    13: 130.0,
    14: 140.0,
    15: 150.0,
    16: 160.0,
    17: 170.0,
    18: 180.0,
    19: 190.0,
    20: 200.0,
    21: 210.0,
    22: 220.0,
    23: 230.0,
    24: 240.0,
    25: 250.0
}

# Valid codes for claiming - Added a new code: "NEWCLAIM2025" for testing/perfect working
VALID_CODES = ["QWERTYUIOPAS"]

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
    user_data_doc = user_data_collection.find_one({"email": email})
    if not user_data_doc:
        # If no user_data, create a basic one? But assume it exists for now.
        pass

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
        # Sync auth fields
        if user_data_doc:
            default_user["name"] = user_data_doc.get("name", "Unknown")
            default_user["username"] = user_data_doc.get("name", "Unknown")
            default_user["profile_image"] = user_data_doc.get("profile_image")
            default_user["user_id"] = str(user_data_doc["_id"])
            default_user["created_at"] = user_data_doc.get("created_at")
        else:
            default_user["name"] = "Unknown"
            default_user["username"] = "Unknown"
            default_user["profile_image"] = None
            default_user["user_id"] = None
            default_user["created_at"] = None
        users_collection.insert_one(default_user)
        user = default_user
    else:
        # Sync fields from user_data if changed
        changes = False
        if user_data_doc:
            if user.get("name") != user_data_doc.get("name"):
                user["name"] = user_data_doc.get("name", user.get("name", "Unknown"))
                user["username"] = user["name"]
                changes = True
            if user.get("profile_image") != user_data_doc.get("profile_image"):
                user["profile_image"] = user_data_doc.get("profile_image", user.get("profile_image"))
                changes = True
            if user.get("user_id") != str(user_data_doc["_id"]):
                user["user_id"] = str(user_data_doc["_id"])
                changes = True
            if user.get("created_at") != user_data_doc.get("created_at"):
                user["created_at"] = user_data_doc.get("created_at", user.get("created_at"))
                changes = True
        if changes:
            users_collection.update_one({"email": email}, {"$set": user})

    # Update missing fields in users
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
    if "name" not in user:
        updates["name"] = "Unknown"
    if "username" not in user:
        updates["username"] = "Unknown"
    if "profile_image" not in user:
        updates["profile_image"] = None
    if "user_id" not in user:
        updates["user_id"] = None if not user_data_doc else str(user_data_doc["_id"])
    if "created_at" not in user:
        updates["created_at"] = None if not user_data_doc else user_data_doc.get("created_at")
    if "receiveNotifications" not in user:
        updates["receiveNotifications"] = True
    if "balancePurchaseTier" in user:
        updates.pop("balancePurchaseTier", None)  # Remove tier system
    if updates:
        users_collection.update_one({"email": email}, {"$set": updates, "$unset": {"balancePurchaseTier": ""}})
        # Refresh user after updates
        user = users_collection.find_one({"email": email})
    
    # Trim transactions to last 10
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": {"transactions": user["transactions"]}})
    
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

# Redirect root route to dashboard if logged in, else to registration page
@app.route('/', methods=['GET'])
def root():
    if session.get('user_id'):
        return redirect(url_for('serve_dashboard'))
    return redirect(url_for('serve_registration'))

# Routes for serving HTML pages
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

        session['user_id'] = str(user["_id"])
        session['email'] = email
        
        flash("", "success")
        
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
        "profile_image": None,
        "receiveNotifications": True,
        "username": name,
        "reset_expiry": None
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
        username = user.get("name", "Unknown")
        balance = user.get("balance", 0.0)
        level = user.get("level", 1)
        rankings_data.append({
            "id": user.get("email"),
            "username": username,
            "level": level,
            "balance": balance  # Fixed: Changed from "coins" to "balance" to match template
        })
    
    rankings_data.sort(key=lambda x: x["balance"], reverse=True)  # Fixed: Sort by "balance"
    for index, user in enumerate(rankings_data):
        user["rank"] = index + 1
    
    current_user_email = session.get('email', '')
    current_user_data = next((u for u in rankings_data if u["id"] == current_user_email), None)
    
    # Fixed: Pass as current_user (dict), template will handle checks
    return render_template('dashboard/rankings.html', rankings=rankings_data, current_user=current_user_data)

@app.route('/api/rankings', methods=['GET'])
def api_rankings():
    if not session.get('user_id'):
        return jsonify({"error": "Not logged in"}), 401

    users = list(users_collection.find({}))
    rankings_data = []
    for user in users:
        username = user.get("name", "Unknown")
        balance = user.get("balance", 0.0)
        level = user.get("level", 1)
        rankings_data.append({
            "id": user.get("email"),
            "username": username,
            "level": level,
            "balance": balance  # Fixed: Changed from "coins" to "balance"
        })
    
    rankings_data.sort(key=lambda x: x["balance"], reverse=True)  # Fixed: Sort by "balance"
    for index, user in enumerate(rankings_data):
        user["rank"] = index + 1
    
    current_user_email = session['email']
    current_user = next((u for u in rankings_data if u["id"] == current_user_email), None)
    
    return jsonify({
        "rankings": rankings_data,
        "currentUser": current_user
    })

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

def update_level(user):
    while user["exp"] >= user["expThreshold"]:
        user["exp"] -= user["expThreshold"]
        user["level"] += 1
        user["expThreshold"] = 500 * (2 ** (user["level"] - 1))
    users_collection.update_one({"email": user["email"]}, {"$set": user})

def apply_boost_effects(user, current_time):
    mining_boost = user.get("miningBoost", {"active": False, "multiplier": 1.0, "expiresAt": None})
    time_reduction = user.get("timeReduction", {"active": False, "reductionMinutes": 0, "expiresAt": None})
    level_shield = user.get("levelShield", {"active": False, "expiresAt": None})

    if mining_boost["active"]:
        expires_at = datetime.fromtimestamp(mining_boost["expiresAt"])
        if current_time > expires_at:
            user["miningBoost"] = {"active": False, "multiplier": 1.0, "expiresAt": None}
        else:
            user["miningBoost"]["multiplier"] = 2.0

    if time_reduction["active"]:
        expires_at = datetime.fromtimestamp(time_reduction["expiresAt"])
        if current_time > expires_at:
            user["timeReduction"] = {"active": False, "reductionMinutes": 0, "expiresAt": None}

    if level_shield["active"]:
        expires_at = datetime.fromtimestamp(level_shield["expiresAt"])
        if current_time > expires_at:
            user["levelShield"] = {"active": False, "expiresAt": None}

    return user

@app.route('/api/user', methods=['GET'])
def get_user():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now()

    # Update active streak
    today = date.today().isoformat()
    if user.get("lastActiveDate") != today:
        user["activeStreak"] = user.get("activeStreak", 0) + 1
        user["lastActiveDate"] = today
        users_collection.update_one({"email": email}, {"$set": {"activeStreak": user["activeStreak"], "lastActiveDate": today}})

    user = apply_boost_effects(user, current_time)

    referral_coins = sum(
        ref["bonus"] for ref in user.get("referredUsers", [])
    ) + sum(
        tx["amount"] for tx in user.get("transactions", [])
        if tx["type"] in ["REFERRAL", "REFERRAL_SIGNUP"]
    )

    total_balance = user.get("balance", 0.0)

    bonus_coins = sum(
        tx["amount"] for tx in user.get("transactions", [])
        if tx["type"] == "BONUS"
    )

    game_earnings = sum(
        tx["amount"] for tx in user.get("transactions", [])
        if tx["type"].startswith("GAME_")
    )

    if user["miningActive"] and user["miningStartTime"]:
        mining_start = datetime.fromtimestamp(user["miningStartTime"])
        elapsed = current_time - mining_start
        total_duration = timedelta(hours=24)
        time_reduction = user.get("timeReduction", {"reductionMinutes": 0})
        if time_reduction.get("active", False):
            reduction = timedelta(minutes=time_reduction["reductionMinutes"])
            total_duration -= reduction
        remaining = total_duration - elapsed
        user["miningTimeRemaining"] = max(0, remaining.total_seconds())
        
        if remaining.total_seconds() <= 0:
            user["miningActive"] = False
            base_amount = 1.0
            mining_boost = user.get("miningBoost", {"multiplier": 1.0})
            if mining_boost.get("active", False):
                base_amount *= mining_boost["multiplier"]
            user["balance"] += base_amount
            user["totalMined"] += base_amount
            user["miningTime"] += 24 * 3600
            user["exp"] += 100
            update_level(user)
            user["transactions"].append({
                "type": "Mining",
                "date": current_time.timestamp() * 1000,
                "amount": base_amount
            })
            trim_transactions(user)
            users_collection.update_one({"email": email}, {"$set": user})

    user_copy = user.copy()
    user_copy["referral_coins"] = referral_coins
    user_copy["balance"] = total_balance
    user_copy["bonus_coins"] = bonus_coins
    user_copy["gameEarnings"] = game_earnings
    user_copy["activeStreak"] = user.get("activeStreak", 0)
    user_copy["referralCount"] = len(user.get("referredUsers", []))
    user_copy["referredUsers"] = user.get("referredUsers", [])
    if user_copy["miningBoost"]["active"] and user_copy["miningBoost"]["expiresAt"]:
        user_copy["boostTimeRemaining"] = max(0, user_copy["miningBoost"]["expiresAt"] - current_time.timestamp())
    else:
        user_copy["boostTimeRemaining"] = 0
    return jsonify(serialize_user(user_copy))

@app.route('/api/get-levels-data', methods=['GET'])
def get_levels_data():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)

    levels_data = {
        "userLevel": user.get("level", 1),
        "userCoins": user.get("balance", 0.0),
        "claimedLevels": user.get("claimed_level_rewards", []),
        "levelRewards": LEVEL_REWARDS
    }
    return jsonify(levels_data)

@app.route('/api/claim-level-reward', methods=['POST'])
def claim_level_reward():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    data = request.get_json()
    level = data.get('level')

    if not isinstance(level, int) or level < 1 or level > 25:
        return jsonify({"error": "Invalid level"}), 400

    if level > user["level"]:
        return jsonify({"error": "Level not unlocked yet"}), 400

    claimed_levels = user.get("claimed_level_rewards", [])
    if level in claimed_levels:
        return jsonify({"error": "Level reward already claimed"}), 400

    reward = LEVEL_REWARDS.get(level, 0.0)
    if reward <= 0:
        return jsonify({"error": "No reward for this level"}), 400

    current_time = datetime.now().timestamp() * 1000
    user["balance"] += reward
    user["claimed_level_rewards"].append(level)
    user["transactions"].append({
        "type": "LEVEL_CLAIM",
        "date": current_time,
        "amount": reward,
        "level": level
    })
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify({
        "success": True,
        "message": f"Level {level} reward claimed: +{reward} coins",
        "newBalance": user["balance"]
    })

@app.route('/api/get-code-claim-data', methods=['GET'])
def get_code_claim_data():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    return jsonify({
        "coins": user.get("balance", 0.0),
        "claimedCodes": user.get("claimed_codes", [])
    })

@app.route('/api/claim-code', methods=['POST'])
def claim_code():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    data = request.get_json()
    fullCode = data.get('code', '').upper().strip()

    if not fullCode or fullCode not in VALID_CODES:
        return jsonify({"error": "Invalid code"}), 400

    claimed_codes = user.get("claimed_codes", [])
    if fullCode in claimed_codes:
        return jsonify({"error": "Code already claimed"}), 400

    reward = 5.0
    current_time = datetime.now().timestamp() * 1000
    user["balance"] += reward
    user["claimed_codes"].append(fullCode)
    user["transactions"].append({
        "type": "CODE_CLAIM",
        "date": current_time,
        "amount": reward,
        "code": fullCode
    })
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify({
        "success": True,
        "message": f"Code accepted! You earned {reward} coins.",
        "newCoins": user["balance"],
        "coinsAwarded": reward
    })

@app.route('/api/start-game', methods=['POST'])
def start_game():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now().timestamp()
    data = request.get_json()
    gtype = data.get('type')
    if not gtype or gtype not in ['scratch', 'spin', 'quiz']:
        return jsonify({"error": "Invalid game type"}), 400

    last_key = f"last{gtype.capitalize()}"
    if user.get(last_key) and current_time - user[last_key] < 86400:
        return jsonify({"error": "Cooldown active"}), 400

    # Generate unique prize based on email for scratch and spin
    prize = 0
    segment = None
    if gtype == 'scratch':
        # Unique scratch prize: hash email + today for seed
        today_str = date.today().isoformat()
        seed = int(hashlib.md5((email + today_str).encode()).hexdigest(), 16) % 7 + 1
        prize = seed
    elif gtype == 'spin':
        # Unique spin prize: prizes list, seed with email + today
        today_str = date.today().isoformat()
        random.seed(hashlib.md5((email + today_str).encode()).hexdigest())
        prizes = [1,1,1, 5,5,5, 10,10,10, 30, 60, 100]
        prize = random.choice(prizes)
        # Also compute the segment for client animation
        segment = prizes.index(prize) if prize in prizes else 0
    elif gtype == 'quiz':
        # For quiz, no prize yet, client handles
        prize = 0

    return jsonify({"success": True, "prize": prize, "segment": segment})

@app.route('/api/claim-game', methods=['POST'])
def claim_game():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now().timestamp()
    data = request.get_json()
    gtype = data.get('type')
    prize = data.get('prize', 0)
    if not gtype or gtype not in ['scratch', 'spin', 'quiz'] or prize <= 0:
        return jsonify({"error": "Invalid type or prize"}), 400

    if gtype == 'scratch' and not (1 <= prize <= 7):
        return jsonify({"error": "Invalid prize for scratch"}), 400
    elif gtype == 'spin' and prize not in [1, 5, 10, 30, 60, 100]:
        return jsonify({"error": "Invalid prize for spin"}), 400
    elif gtype == 'quiz' and not (0 <= prize <= 5):
        return jsonify({"error": "Invalid prize for quiz"}), 400

    last_key = f"last{gtype.capitalize()}"
    if user.get(last_key) and current_time - user[last_key] < 86400:
        return jsonify({"error": "Cooldown active"}), 400

    tx_type = f"GAME_{gtype.upper()}"
    user["balance"] += prize
    user["transactions"].append({
        "type": tx_type,
        "date": current_time * 1000,
        "amount": prize,
        "game_type": gtype
    })
    user[last_key] = current_time
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify({"success": True, "prize": prize})

@app.route('/api/gift/open', methods=['POST'])
def gift_open():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    data = request.get_json()
    gift_type = data.get('type')
    if not gift_type or gift_type not in ['channel', 'video', 'instagram']:
        return jsonify({"error": "Invalid gift type"}), 400

    user = initialize_user(email)
    now = datetime.now().timestamp() * 1000
    user['gifts'][gift_type]['opened'] = now
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify(serialize_user(user))

@app.route('/api/gift/claim', methods=['POST'])
def gift_claim():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    data = request.get_json()
    gift_type = data.get('type')
    if not gift_type or gift_type not in ['channel', 'video', 'instagram']:
        return jsonify({"error": "Invalid gift type"}), 400

    user = initialize_user(email)
    now = datetime.now().timestamp() * 1000
    RESET_TIME_MS = 24 * 60 * 60 * 1000

    opened = user['gifts'][gift_type]['opened']
    claimed = user['gifts'][gift_type]['claimed']

    if not opened or (now - opened) >= RESET_TIME_MS:
        return jsonify({"error": "Please open and complete the task first."}), 400

    if claimed and (now - claimed) < RESET_TIME_MS:
        return jsonify({"error": "Already claimed today."}), 400

    reward = random.uniform(1, 5)
    user['balance'] += reward
    user['gifts'][gift_type]['claimed'] = now
    user['transactions'].append({
        "type": "GIFT_CLAIM",
        "date": now,
        "amount": reward,
        "gift_type": gift_type
    })
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify({
        "reward": reward,
        **serialize_user(user)
    })

@app.route('/api/upload-profile-image', methods=['POST'])
def upload_profile_image():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    data = request.get_json()
    image_data = data.get('image')

    if not image_data:
        return jsonify({"error": "No image provided"}), 400

    if not image_data.startswith('data:image'):
        return jsonify({"error": "Invalid image format"}), 400

    try:
        user_data_collection.update_one(
            {"email": email},
            {"$set": {"profile_image": image_data}}
        )
        # Sync to users collection
        user = users_collection.find_one({"email": email})
        if user:
            user["profile_image"] = image_data
            users_collection.update_one({"email": email}, {"$set": {"profile_image": image_data}})
        return jsonify({"message": "Profile image uploaded successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to upload image: {str(e)}"}), 500

@app.route('/api/start-mining', methods=['POST'])
def start_mining():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now()

    if user["miningActive"]:
        return jsonify({"error": "Mining is already active"}), 400

    if user["lastMining"]:
        last_mining_time = datetime.fromtimestamp(user["lastMining"])
        if current_time - last_mining_time < timedelta(hours=24):
            return jsonify({"error": "Can only start mining once every 24 hours"}), 400

    user["miningActive"] = True
    user["lastMining"] = current_time.timestamp()
    user["miningStartTime"] = current_time.timestamp()
    user["miningTimeRemaining"] = 24 * 3600
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify(serialize_user(user))

@app.route('/api/activate-mining-boost', methods=['POST'])
def activate_mining_boost():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now()

    if user["miningBoost"]["active"]:
        return jsonify({"error": "Mining boost is already active"}), 400

    if user["lastMiningBoost"]:
        last_boost_time = datetime.fromtimestamp(user["lastMiningBoost"])
        if current_time - last_boost_time < timedelta(hours=24):
            return jsonify({"error": "Can only activate mining boost once every 24 hours"}), 400

    user["miningBoost"] = {
        "active": True,
        "multiplier": 2.0,
        "expiresAt": (current_time + timedelta(minutes=30)).timestamp()
    }
    user["lastMiningBoost"] = current_time.timestamp()
    user["transactions"].append({
        "type": "BOOST_ACTIVATION",
        "date": current_time.timestamp() * 1000,
        "amount": 0,
        "item": "mining_boost"
    })
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify(serialize_user(user))

@app.route('/api/claim-reward', methods=['POST'])
def claim_reward():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now()

    if not user["miningActive"]:
        return jsonify({"error": "Mining is not active"}), 400

    if user["miningStartTime"]:
        mining_start = datetime.fromtimestamp(user["miningStartTime"])
        elapsed = current_time - mining_start
        total_duration = timedelta(hours=24)

        time_reduction = user.get("timeReduction", {"reductionMinutes": 0})
        if time_reduction.get("active", False):
            reduction = timedelta(minutes=time_reduction["reductionMinutes"])
            total_duration -= reduction
        remaining = total_duration - elapsed

        if remaining.total_seconds() > 0:
            return jsonify({"error": "Mining is not yet complete"}), 400

    base_amount = 1.0
    mining_boost = user.get("miningBoost", {"multiplier": 1.0})
    if mining_boost.get("active", False) or (mining_boost.get("expiresAt") and datetime.fromtimestamp(mining_boost["expiresAt"]) > mining_start):
        base_amount *= 2.0

    user["balance"] += base_amount
    user["totalMined"] += base_amount
    user["miningTime"] += 24 * 3600
    user["exp"] += 100
    user["miningActive"] = False
    user["lastMining"] = current_time.timestamp()
    user["miningStartTime"] = None
    user["miningTimeRemaining"] = 0

    update_level(user)

    user["transactions"].append({
        "type": "Mining",
        "date": current_time.timestamp() * 1000,
        "amount": base_amount
    })
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify({
        "message": "Reward claimed successfully",
        "amount": base_amount,
        **serialize_user(user)
    })

@app.route('/api/claim-bonus', methods=['POST'])
def claim_bonus():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now()

    if user["lastBonus"]:
        last_bonus_time = datetime.fromtimestamp(user["lastBonus"])
        if current_time - last_bonus_time < timedelta(days=1):
            return jsonify({"error": "Can only claim bonus once per day"}), 400

    bonus = random.uniform(0.1, 0.9) if user["level"] < 5 else random.uniform(1.0, 2.0)
    user["transactions"].append({
        "type": "BONUS",
        "date": current_time.timestamp() * 1000,
        "amount": bonus
    })
    user["lastBonus"] = current_time.timestamp()
    user["exp"] += 50
    update_level(user)
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify(serialize_user(user))

@app.route('/api/save_progress', methods=['POST'])
def save_progress():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    data = request.get_json()
    level = data.get('level')
    coins = data.get('coins')

    if not isinstance(level, int) or level < 1 or level > 25:
        return jsonify({"error": "Invalid level"}), 400

    if level != user["level"]:
        return jsonify({"error": "Can only complete the current level"}), 400

    if level in user.get("claimed_level_rewards", []):
        return jsonify({"error": "Level reward already claimed"}), 400

    user["balance"] += coins
    user["exp"] += 100
    user["level"] += 1
    user["claimed_level_rewards"].append(level)
    user["transactions"].append({
        "type": "LEVEL_REWARD",
        "date": datetime.now().timestamp() * 1000,
        "amount": coins,
        "level": level
    })

    update_level(user)
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify({"success": True, "message": f"Level {level} completed, {coins} coins added"})

@app.route('/api/update-settings', methods=['POST'])
def update_settings():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    data = request.get_json()

    user = users_collection.find_one({"email": email})
    user_data_doc = user_data_collection.find_one({"email": email})

    if not user or not user_data_doc:
        return jsonify({"error": "User not found"}), 404

    updated = False

    if "username" in data:
        new_name = data["username"]
        user_data_collection.update_one(
            {"email": email},
            {"$set": {"name": new_name, "username": new_name}}
        )
        user["name"] = new_name
        user["username"] = new_name
        updated = True

    if "receiveNotifications" in data:
        user["receiveNotifications"] = data["receiveNotifications"]
        # Also sync to user_data if needed, but since it's in users primarily
        user_data_collection.update_one(
            {"email": email},
            {"$set": {"receiveNotifications": data["receiveNotifications"]}}
        )
        updated = True

    if updated:
        users_collection.update_one({"email": email}, {"$set": user})

    return jsonify(serialize_user(user))

@app.route('/api/register', methods=['POST'])
def register():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    data = request.get_json()
    referral_id = data.get("referralId")
    new_email = data.get("email", email)

    if users_collection.find_one({"email": new_email}):
        return jsonify({"error": "Email already exists"}), 400

    new_user = {
        "email": new_email,
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
    users_collection.insert_one(new_user)

    if referral_id:
        referrer = users_collection.find_one({"referralId": referral_id})
        if referrer:
            referral_bonus = random.uniform(7.0, 20.0)
            referrer["totalReferralBonus"] = referrer.get("totalReferralBonus", 0.0) + referral_bonus
            referrer["balance"] = referrer.get("balance", 0.0) + referral_bonus
            referrer["referredUsers"].append({
                "email": new_email,
                "joinDate": datetime.now().timestamp() * 1000,
                "bonus": referral_bonus
            })
            referrer["transactions"].append({
                "type": "REFERRAL",
                "date": datetime.now().timestamp() * 1000,
                "amount": referral_bonus
            })
            trim_transactions(referrer)
            users_collection.update_one({"referralId": referral_id}, {"$set": referrer})
            new_user["balance"] += referral_bonus
            new_user["transactions"].append({
                "type": "REFERRAL_SIGNUP",
                "date": datetime.now().timestamp() * 1000,
                "amount": referral_bonus
            })
            trim_transactions(new_user)
            users_collection.update_one({"email": new_email}, {"$set": new_user})

    return jsonify(serialize_user(new_user))

@app.route('/api/purchase', methods=['POST'])
def purchase():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    data = request.get_json()
    item = data.get("item")
    payment_method = data.get("payment_method")
    current_time = datetime.now()

    shop_items = {
        "mining_boost": {"cost": 1.0, "duration_hours": 1, "multiplier": 2.0},
        "time_reduction": {"cost": 750.0, "duration_hours": 1, "reduction_minutes": 15},
        "level_shield": {"cost": 2000.0, "duration_hours": 24}
    }

    if item not in shop_items:
        return jsonify({"error": "Invalid item"}), 400

    item_details = shop_items[item]
    cost = item_details["cost"]

    bonus_coins = sum(
        tx["amount"] for tx in user.get("transactions", [])
        if tx["type"] == "BONUS"
    )

    if item == "mining_boost":
        if payment_method == "your_balance":
            total_balance = user["balance"]
            if total_balance < cost:
                return jsonify({"error": "Insufficient Your Balance coins"}), 400
            user["balance"] -= cost
            user["transactions"].append({
                "type": "PURCHASE",
                "date": current_time.timestamp() * 1000,
                "amount": -cost,
                "item": item
            })
        elif payment_method == "shopping_coins":
            if bonus_coins < cost:
                return jsonify({"error": "Insufficient Shopping Coins"}), 400
            user["transactions"].append({
                "type": "BONUS",
                "date": current_time.timestamp() * 1000,
                "amount": -cost,
                "item": item
            })
        else:
            return jsonify({"error": "Invalid payment method"}), 400
    else:
        total_balance = user["balance"]
        if total_balance < cost:
            return jsonify({"error": "Insufficient Your Balance coins"}), 400
        user["balance"] -= cost
        user["transactions"].append({
            "type": "PURCHASE",
            "date": current_time.timestamp() * 1000,
            "amount": -cost,
            "item": item
        })

    if item == "mining_boost":
        expires_at = (current_time + timedelta(hours=item_details["duration_hours"])).timestamp()
        user["miningBoost"] = {
            "active": True,
            "multiplier": item_details["multiplier"],
            "expiresAt": expires_at
        }
    elif item == "time_reduction":
        expires_at = (current_time + timedelta(hours=item_details["duration_hours"])).timestamp()
        user["timeReduction"] = {
            "active": True,
            "reductionMinutes": item_details["reduction_minutes"],
            "expiresAt": expires_at
        }
    elif item == "level_shield":
        expires_at = (current_time + timedelta(hours=item_details["duration_hours"])).timestamp()
        user["levelShield"] = {
            "active": True,
            "expiresAt": expires_at
        }

    update_level(user)
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify(serialize_user(user))

@app.route('/api/purchase-balance', methods=['POST'])
def purchase_balance():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    data = request.get_json()
    item = data.get("item")
    current_time = datetime.now()

    if item != "your_balance":
        return jsonify({"error": "Invalid item"}), 400

    shopping_cost = 5.0
    balance_gain = 15.0

    bonus_coins = sum(
        tx["amount"] for tx in user.get("transactions", [])
        if tx["type"] == "BONUS"
    )

    if bonus_coins < shopping_cost:
        return jsonify({"error": "Insufficient Shopping Coins"}), 400

    user["transactions"].append({
        "type": "BONUS",
        "date": current_time.timestamp() * 1000,
        "amount": -shopping_cost,
        "item": "your_balance"
    })

    user["balance"] += balance_gain
    user["transactions"].append({
        "type": "BALANCE_PURCHASE",
        "date": current_time.timestamp() * 1000,
        "amount": balance_gain,
        "item": "your_balance"
    })

    update_level(user)
    trim_transactions(user)
    users_collection.update_one({"email": email}, {"$set": user})
    return jsonify(serialize_user(user))

# Improved Chatbot with more patterns, regex, and better responses
def match_pattern(query, patterns):
    for pattern, response in patterns.items():
        if re.search(pattern, query, re.IGNORECASE):
            return response
    return None

CHATBOT_PATTERNS = {
    r'mining.*(kaam|kare|works?|how|काम|करें)': (
        "🚀 Mining is your daily coin earner! You get 1 coin every 24 hours. "
        "Click 'Start Mining' on the dashboard to begin. Boost it for 2x rewards! 💎 "
        "Pro tip: Combine with referrals for explosive growth! 📈"
    ),
    r'(timer|time|reset).*mining': (
        "⏰ The mining timer resets every 24 hours from your last start. "
        "Check remaining time on the dashboard. Don't miss your daily cycle! ⚡"
    ),
    r'(withdraw|deposit|withdrawal).*coin': (
        "💳 Withdrawals and deposits are coming soon! Stay tuned via /blog for updates. "
        "In the meantime, stack those coins with mining and games! 🎮"
    ),
    r'coin.*(mine|mined)': (
        "💰 Your total mined coins: {total_mined:.4f}. Keep digging deeper! "
        "Visit dashboard for full stats and next mine. 🛠️"
    ),
    r'mining.*(status|active|time|समय)': (
        "🔍 Mining status: {'Active' if mining_active else 'Inactive'}. "
        "{remaining_time if mining_active else 'Start now on dashboard!'} "
        "Level up your game! 🌟"
    ),
    r'referral.*(id|code|आईडी)': (
        "👥 Your referral ID: {referral_id}. Share it with friends to earn 7-20 bonus coins per signup! "
        "Track earnings on /referrals. Let's build your network! 🔗"
    ),
    r'referral.*(benefit|earn|फायदा)': (
        "🎁 Referrals = Bonus coins! Earn 7-20 coins instantly when friends join with your ID. "
        "Unlimited potential – more friends, more rewards! Check /referrals for your list. 📊"
    ),
    r'(login|log in).*issue|problem': (
        "🔑 Login trouble? Double-check email/password. Use 'Forgot Password' on /login for reset. "
        "Still stuck? Hit /support – we're here 24/7! 😊"
    ),
    r'password.*(reset|change|भूल गया)': (
        "🔄 Forgot password? Click 'Forgot Password' on /login – we'll email reset instructions. "
        "Secure your account and mine on! 🛡️"
    ),
    r'(dashboard|डैशबोर्ड).*(where|कहाँ|find|location)': (
        "🏠 Dashboard at /dashboard: Balance, mining timer, transactions, and quick actions. "
        "Your command center – log in and conquer! 🚀"
    ),
    r'(profile|प्रोफाइल).*(where|कहाँ|find|location|edit)': (
        "👤 Profile at /profile: Update name, image, notifications. Personalize your mining empire! "
        "Access via sidebar or bottom nav. ✨"
    ),
    r'(hi|hello|hey|namaste|हाय|नमस्ते|sup)': (
        "👋 Hey {username}! Ready to mine some crypto magic? Ask me about mining, referrals, or anything app-related. "
        "What's up? 😄"
    ),
    r'balance.*(check|देखें|कितना)': (
        "💎 Your balance: {balance:.4f} coins. Growing strong! View full breakdown on /dashboard. "
        "Time to claim a bonus? 🎁"
    ),
    r'account.*(created|when|कब|जब)|joined': (
        "📅 Account created: {created_at}. Level {level} with {exp} EXP – you're on fire! 🔥 "
        "Profile has all deets. Keep leveling up!"
    ),
    r'daily.*(bonus|claim|दैनिक|बोनस)': (
        "🎉 Daily bonus time! Claim on dashboard for 0.1-2 coins (based on level). "
        "One per day – don't sleep on it! 😴➡️💰 Shop upgrades with them too!"
    ),
    r'mining.*(boost|बूस्ट|double|increase|how|कैसे)': (
        "⚡ Mining boost: Doubles your 1 coin to 2! Free daily activation or buy in shop for 1 coin. "
        "Activate on dashboard – lasts 30 mins. Power up! 🚀"
    ),
    r'(support|help|सहायता|contact|number|नंबर|कौन|team)': (
        "🆘 Support at /support. Email: support@zerocoin.com | Call: +1-800-555-1234. "
        "We're miners like you – quick replies guaranteed! 💪 Or ask me here!"
    ),
    r'(username|name|नाम|email|ईमेल|id|आईडी)': (
        "📝 Username: {username} | Email: {email} | User ID: {user_id}. "
        "Edit on /profile. Secure and simple! 🔒"
    ),
    r'(level|लेवल|exp|experience|अनुभव|progress)': (
        "📈 Current level: {level} | EXP: {exp}/{exp_threshold}. Earn via mining/games! "
        "Next level unlocks bigger rewards. Grind on! 🏆"
    ),
    r'(shop|दुकान|buy|purchase|खरीदें|items|उपकरण)': (
        "🛒 Shop at /shop: Boosts (1 coin), Time reducers (750 coins), Shields (2000 coins). "
        "Pay with balance or bonus coins. Upgrade your strategy! 🛠️"
    ),
    r'(game|गेम|spin|scratch|quiz|खेल|play)': (
        "🎮 Games on dashboard: Scratch (1-7 coins), Spin (1-100), Quiz (0-5). Daily cooldown! "
        "Fun way to earn – no mining wait. Try your luck! 🍀"
    ),
    r'(gift|गिफ्ट|reward|claim|दावा|subscribe|follow)': (
        "🎁 Gifts at /gift: Subscribe/watch/follow for 1-5 coins daily. "
        "Open link, complete, claim! Easy extras. 📱➡️💰"
    ),
    r'(ranking|रैंक|leaderboard|टॉप|top|best)': (
        "🏆 Check rankings at /rankings. Compete on balance! Climb with mining & referrals. "
        "You're at rank {user_rank} – aim higher! 🔥"
    ),
    r'(code|कोड|claim|redeem|रिडीम|promo)': (
        "🎫 Redeem codes at /code-claim. Valid: AZIZ7860ZXCV, WXYZ5678LKJH, TEST0000CODE, NEWCLAIM2025 (5 coins each). "
        "One-time per code. Hunt for more in blog! 🔑"
    ),
    r'(level.*reward|claim|दावा|unlock)': (
        "⭐ Level rewards: Claim unclaimed levels on /levels (10-250 coins). "
        "Earn EXP via activities to unlock. Milestone magic! 🌟"
    ),
    r'(transaction|history|ट्रांजेक्शन|log|record)': (
        "📋 View transactions on dashboard. Last 10 shown – mining, bonuses, purchases. "
        "Full history in your account. Transparent mining! 🔍"
    ),
    r'(notification|नोटिफिकेशन|alert|सूचना|settings)': (
        "🔔 Toggle notifications in /settings. Stay updated on bonuses/mining without spam. "
        "Your control, your flow! ⚙️"
    )
}

DEFAULT_RESPONSES = [
    "🤔 Hmm, that's a new one! Try asking about 'mining status', 'balance check', or 'referral ID'. ",
    "❓ Not sure? Common queries: 'How to start mining?', 'What's my balance?', 'Help with login'. ",
    "🔮 Crystal ball says: Check /help or /support for guides. What else can I assist with? ",
    "😊 I'm here to help with app features! Examples: 'Daily bonus?', 'Game how to?', 'Shop items'."
]

@app.route('/api/chatbot', methods=['POST'])
def chatbot_query():
    if not session.get('email'):
        return jsonify({"error": "Not logged in"}), 401

    email = session['email']
    user = initialize_user(email)
    current_time = datetime.now()

    data = request.get_json()
    query = data.get('query', '').lower().strip()

    if not query:
        return jsonify({"response": "👋 Hi! Ask me anything about mining, balance, or features. What's up?"}), 200

    # Apply mining auto-complete if needed (moved from end to here for consistency)
    if user["miningActive"] and user.get("miningTimeRemaining", 0) <= 0:
        base_amount = 1.0
        mining_boost = user.get("miningBoost", {"multiplier": 1.0})
        if mining_boost.get("active", False):
            base_amount *= mining_boost["multiplier"]
        user["balance"] += base_amount
        user["totalMined"] += base_amount
        user["miningTime"] += 24 * 3600
        user["exp"] += 100
        user["miningActive"] = False
        user["lastMining"] = current_time.timestamp()
        user["miningStartTime"] = None
        user["miningTimeRemaining"] = 0
        update_level(user)
        user["transactions"].append({
            "type": "Mining",
            "date": current_time.timestamp() * 1000,
            "amount": base_amount
        })
        trim_transactions(user)
        users_collection.update_one({"email": email}, {"$set": user})
        mining_complete_msg = f" 🎉 Auto-mined {base_amount} coins! Total mined: {user['totalMined']:.4f}. Start new on dashboard!"
    else:
        mining_complete_msg = ""

    username = user.get("name", "Miner")

    # Enhanced pattern matching with regex
    response = match_pattern(query, CHATBOT_PATTERNS)

    if not response:
        # Fallback to random default
        import random
        response = random.choice(DEFAULT_RESPONSES)

    # Dynamic replacements
    replacements = {
        '{username}': username,
        '{balance}': f"{user.get('balance', 0):.4f}",
        '{total_mined}': f"{user.get('totalMined', 0):.4f}",
        '{referral_id}': user.get('referralId', 'N/A'),
        '{level}': user.get('level', 1),
        '{exp}': user.get('exp', 0),
        '{exp_threshold}': user.get('expThreshold', 500),
        '{email}': email,
        '{user_id}': user.get('user_id', 'N/A'),
        '{created_at}': datetime.fromtimestamp(user.get('created_at', 0)).strftime("%Y-%m-%d %H:%M:%S") if user.get('created_at') else 'Unknown',
        '{remaining_time}': format_time(user.get('miningTimeRemaining', 0)) if user.get('miningActive', False) else '',
        '{mining_active}': 'Active' if user.get('miningActive', False) else 'Inactive',
        '{user_rank}': 'TBD'  # Can compute if needed
    }

    for key, value in replacements.items():
        response = response.replace(key, str(value))

    response += mining_complete_msg

    # Add helpful suggestion if query seems confused
    if len(query.split()) < 2:
        response += " 💡 Quick tips: 'balance check', 'start mining?', 'referral benefit'."

    return jsonify({"response": response})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8110))  # Railway $PORT use કરે
    app.run(host='0.0.0.0', port=port, debug=False)  # Debug=False for prod