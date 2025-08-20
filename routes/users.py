# routes/users.py

from flask import Blueprint, request, jsonify
from extensions import mysql

users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
        (username, password, email)
    )
    mysql.connection.commit()
    cursor.close()

    return jsonify({"message": "User registered successfully"}), 201

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    # בדיקת אימייל + סיסמה במסד הנתונים
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, is_admin FROM users WHERE email=%s AND password=%s", (email, password))
    user = cursor.fetchone()
    cursor.close()

    if user:
        return jsonify({
            "message": "Login successful",
            "user_id": user[0],
            "username": user[1],
            "is_admin": bool(user[2])
        }), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401
