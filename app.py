from flask import Flask, render_template, request, redirect, session, flash, url_for
from dotenv import load_dotenv
import os, uuid
from pathlib import Path
from extensions import mysql
from werkzeug.security import generate_password_hash, check_password_hash
from MySQLdb.cursors import DictCursor

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')

# ===== DB Config =====
app.config['MYSQL_HOST'] = os.getenv('DB_HOST')
app.config['MYSQL_USER'] = os.getenv('DB_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('DB_NAME')

mysql.init_app(app)

# ===== Consts =====
GENDERS = {
    "men": "גברים",
    "women": "נשים",
    "kids": "ילדים",
}
CATEGORIES = {
    "shirt": "חולצה",
    "pants": "מכנסיים",
    "shoes": "נעליים",
    "leggings": "טייאצ׳",
    "hat": "כובע",
    "accessories": "אקססוריז"
}

# ===== Helpers =====
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png','jpg','jpeg','gif','webp'}

@app.context_processor
def inject_globals():
    return dict(
        username=session.get('username'),
        is_admin=session.get('is_admin', False),
        genders=GENDERS,
        categories=CATEGORIES
    )

# ===== Home =====
@app.route('/')
def home():
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("""
        SELECT id, name, price, image_url
        FROM products
        WHERE is_hot=1
        ORDER BY id DESC
        LIMIT 12
    """)
    hot_products = cur.fetchall()
    cur.close()
    return render_template('index.html', hot_products=hot_products)

# ===== Auth =====
@app.route('/login', methods=['GET','POST'])
def login_page():
    if request.method == 'GET':
        return render_template('login.html')
    email = request.form['email'].strip()
    password = request.form['password']
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT id,username,password,is_admin FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    if user and check_password_hash(user['password'], password):
        session.update(user_id=user['id'], username=user['username'], is_admin=user['is_admin'])
        flash("התחברת בהצלחה!", "success")
        return redirect(url_for('home'))
    flash("פרטי ההתחברות שגויים", "danger")
    return redirect(url_for('login_page'))

@app.route('/register', methods=['GET','POST'])
def register_page():
    if request.method == 'GET':
        return render_template('register.html')
    username = request.form['username'].strip()
    email = request.form['email'].strip()
    password = request.form['password']
    password_confirm = request.form['password_confirm']
    if password != password_confirm:
        flash("הסיסמאות לא תואמות", "danger")
        return redirect(url_for('register_page'))
    hashed = generate_password_hash(password)
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        flash("האימייל כבר רשום", "danger")
        cur.close()
        return redirect(url_for('register_page'))
    cur.execute("INSERT INTO users (username,email,password,is_admin) VALUES (%s,%s,%s,%s)",
                (username,email,hashed,0))
    mysql.connection.commit()
    cur.close()
    flash("נרשמת בהצלחה! עכשיו תוכל להתחבר", "success")
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear()
    flash("התנתקת", "info")
    return redirect(url_for('home'))

# ===== Add Product =====
@app.route('/add-product', methods=['GET','POST'])
def add_product():
    if request.method == 'GET':
        return render_template('add_product.html')

    name = request.form.get('name','').strip()
    description = request.form.get('description','').strip()
    price_raw = request.form.get('price','').strip()
    category = request.form.get('category')
    gender = request.form.get('gender')
    is_hot = 1 if 'is_hot' in request.form else 0

    if not name or not description or not price_raw:
        flash("נא למלא את כל השדות החובה", "danger")
        return redirect(url_for('add_product'))
    try:
        price = float(price_raw)
    except ValueError:
        flash("מחיר לא תקין", "danger")
        return redirect(url_for('add_product'))

    if category not in CATEGORIES:
        flash("סוג פריט לא תקין", "danger")
        return redirect(url_for('add_product'))
    if gender not in GENDERS:
        flash("קהל יעד לא תקין", "danger")
        return redirect(url_for('add_product'))

    size_clothes = (request.form.get('size_clothes') or '').strip() or None
    smin = (request.form.get('size_shoes_min') or '').strip()
    smax = (request.form.get('size_shoes_max') or '').strip()
    size_shoes = f"{smin}-{smax}" if (smin and smax) else None

    if category == "shoes":
        size_clothes = None
        if not size_shoes:
            flash("לנעליים חובה להזין טווח מידות", "danger")
            return redirect(url_for('add_product'))
    else:
        size_shoes = None
        if not size_clothes:
            flash("לפריט זה חובה להזין מידה", "danger")
            return redirect(url_for('add_product'))

    file = request.files.get('image_file')
    if not file or not allowed_file(file.filename):
        flash("נא להעלות קובץ תמונה תקני", "danger")
        return redirect(url_for('add_product'))
    ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join("static/uploads", unique_name)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)
    image_url = "/" + save_path.replace("\\", "/")

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO products (name,description,price,image_url,is_hot,
                              size_clothes,size_shoes,category,gender)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (name,description,price,image_url,is_hot,
          size_clothes,size_shoes,category,gender))
    mysql.connection.commit()
    cur.close()

    flash("המוצר נוסף בהצלחה!", "success")
    return redirect(url_for('add_product'))

# ===== Gender Pages with Category Filter =====
@app.route('/men')
def men_page():
    category = request.args.get('category')
    cur = mysql.connection.cursor(DictCursor)
    if category:
        cur.execute("SELECT id,name,price,image_url FROM products WHERE gender='men' AND category=%s ORDER BY id DESC", (category,))
    else:
        cur.execute("SELECT id,name,price,image_url FROM products WHERE gender='men' ORDER BY id DESC")
    products = cur.fetchall()
    cur.close()
    return render_template('men.html', products=products, gender_name=GENDERS['men'], selected_category=category)

@app.route('/women')
def women_page():
    category = request.args.get('category')
    cur = mysql.connection.cursor(DictCursor)
    if category:
        cur.execute("SELECT id,name,price,image_url FROM products WHERE gender='women' AND category=%s ORDER BY id DESC", (category,))
    else:
        cur.execute("SELECT id,name,price,image_url FROM products WHERE gender='women' ORDER BY id DESC")
    products = cur.fetchall()
    cur.close()
    return render_template('women.html', products=products, gender_name=GENDERS['women'], selected_category=category)

@app.route('/kids')
def kids_page():
    category = request.args.get('category')
    cur = mysql.connection.cursor(DictCursor)
    if category:
        cur.execute("SELECT id,name,price,image_url FROM products WHERE gender='kids' AND category=%s ORDER BY id DESC", (category,))
    else:
        cur.execute("SELECT id,name,price,image_url FROM products WHERE gender='kids' ORDER BY id DESC")
    products = cur.fetchall()
    cur.close()
    return render_template('kids.html', products=products, gender_name=GENDERS['kids'], selected_category=category)

# ===== Product Details =====
@app.route('/products/<int:pid>')
def product_detail(pid):
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("""
        SELECT id,name,description,price,image_url,is_hot,
               size_clothes,size_shoes,category,gender,created_at
        FROM products WHERE id=%s
    """, (pid,))
    product = cur.fetchone()
    cur.close()
    if not product:
        flash("מוצר לא נמצא", "danger")
        return redirect(url_for('home'))
    return render_template('product_detail.html', product=product)

if __name__ == '__main__':
    app.run(debug=True)
