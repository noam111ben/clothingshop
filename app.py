from flask import Flask, render_template, request, redirect, session, flash
from dotenv import load_dotenv
import os
from extensions import mysql
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')

# הגדרות מסד הנתונים
app.config['MYSQL_HOST'] = os.getenv('DB_HOST')
app.config['MYSQL_USER'] = os.getenv('DB_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('DB_NAME')

# תיקיית העלאות
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql.init_app(app)

def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.context_processor
def inject_user():
    return dict(
        username=session.get('username'),
        is_admin=session.get('is_admin', False)
    )

@app.route('/')
def home():
    from MySQLdb.cursors import DictCursor
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("SELECT id, name, price, image_url FROM products WHERE is_hot = TRUE")
    hot_products = cursor.fetchall()
    cursor.close()
    return render_template('index.html', hot_products=hot_products)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form['email']
    password = request.form['password']

    from MySQLdb.cursors import DictCursor
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("SELECT id, username, password, is_admin FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    cursor.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = user['is_admin']
        flash('התחברת בהצלחה!', 'success')
        return redirect('/')
    else:
        flash('פרטי התחברות שגויים', 'danger')
        return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    password_confirm = request.form['password_confirm']

    if password != password_confirm:
        flash('הסיסמאות לא תואמות', 'danger')
        return redirect('/register')

    hashed_password = generate_password_hash(password)

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        flash('כתובת אימייל כבר רשומה', 'danger')
        cursor.close()
        return redirect('/register')

    cursor.execute(
        "INSERT INTO users (username, email, password, is_admin) VALUES (%s, %s, %s, %s)",
        (username, email, hashed_password, 0)
    )
    mysql.connection.commit()
    cursor.close()

    flash('נרשמת בהצלחה! אנא התחבר', 'success')
    return redirect('/login')

@app.route('/add-product', methods=['POST'])
def add_product():
    name = request.form['name']
    description = request.form['description']
    price = float(request.form['price'])
    is_hot = 'is_hot' in request.form

    # מידות
    size_clothes = request.form.get('size_clothes')
    size_shoes_min = request.form.get('size_shoes_min')
    size_shoes_max = request.form.get('size_shoes_max')

    sizr_shoes = None
    if size_shoes_min and size_shoes_max:
        sizr_shoes = f"{size_shoes_min}-{size_shoes_max}"

    # טיפול בקובץ תמונה
    file = request.files.get('image_file')
    if not file or file.filename == '' or not allowed_file(file.filename):
        flash('נא להעלות קובץ תמונה תקני (png, jpg, jpeg, gif)', 'danger')
        return redirect('/add-product')

    filename = secure_filename(file.filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    imange_url = '/' + file_path.replace("\\", "/")  # שם העמודה במסד: imange_url

    # הוספה למסד
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO products
            (name, description, price, imange_url, is_hot, size_clothes, sizr_shoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, description, price, imange_url, is_hot, size_clothes, sizr_shoes))
        mysql.connection.commit()
        flash('המוצר נוסף בהצלחה!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'שגיאה בהוספת מוצר: {e}', 'danger')
    finally:
        cursor.close()

    return redirect('/add-product')

@app.route('/logout')
def logout():
    session.clear()
    flash('התנתקת מהמערכת', 'info')
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
