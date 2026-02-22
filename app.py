from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
import qrcode
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'ton_secret_key_ici'

# Configuration MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'useradmin001',
    'database': 'gestion_stock'
}

def get_db():
    return mysql.connector.connect(**db_config)

# Configuration uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# PAGE PRINCIPALE - Liste des articles
@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM articles")
    articles = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', articles=articles)

# AJOUTER UN ARTICLE
@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if request.method == 'POST':
        nom = request.form['nom']
        description = request.form['description']
        prix = request.form['prix']
        stock = request.form['stock']

        photo_filename = None
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and allowed_file(photo.filename):
                photo_filename = secure_filename(photo.filename)
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO articles (nom, description, prix, stock, photo)
            VALUES (%s, %s, %s, %s, %s)
        """, (nom, description, prix, stock, photo_filename))
        conn.commit()
        article_id = cur.lastrowid

        url_article = f"http://192.168.1.79:5000/article/{article_id}"
        qr = qrcode.make(url_article)
        qr_filename = f"qr_{article_id}.png"
        qr.save(os.path.join('static/qrcodes', qr_filename))

        cur.execute("UPDATE articles SET qr_code = %s WHERE id = %s", (qr_filename, article_id))
        conn.commit()
        cur.close()
        conn.close()

        flash('Article ajouté avec succès !', 'success')
        return redirect(url_for('index'))

    return render_template('ajouter.html')

# MODIFIER UN ARTICLE
@app.route('/modifier/<int:id>', methods=['GET', 'POST'])
def modifier(id):
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        nom = request.form['nom']
        description = request.form['description']
        prix = request.form['prix']
        stock = request.form['stock']
        cur.execute("""
            UPDATE articles SET nom=%s, description=%s, prix=%s, stock=%s WHERE id=%s
        """, (nom, description, prix, stock, id))
        conn.commit()
        cur.close()
        conn.close()
        flash('Article modifié avec succès !', 'success')
        return redirect(url_for('index'))

    cur.execute("SELECT * FROM articles WHERE id = %s", (id,))
    article = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('modifier.html', article=article)

# SUPPRIMER UN ARTICLE
@app.route('/supprimer/<int:id>')
def supprimer(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM articles WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Article supprimé !', 'danger')
    return redirect(url_for('index'))

# PAGE PUBLIQUE - Scan QR code
@app.route('/article/<int:id>')
def article_public(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM articles WHERE id = %s", (id,))
    article = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('article_public.html', article=article)

# ENREGISTRER UNE VENTE
@app.route('/vendre/<int:id>', methods=['POST'])
def vendre(id):
    quantite = int(request.form['quantite'])
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT stock FROM articles WHERE id = %s", (id,))
    article = cur.fetchone()

    if article and article[0] >= quantite:
        cur.execute("UPDATE articles SET stock = stock - %s WHERE id = %s", (quantite, id))
        cur.execute("INSERT INTO ventes (article_id, quantite) VALUES (%s, %s)", (id, quantite))
        conn.commit()
        flash('Vente enregistrée avec succès !', 'success')
    else:
        flash('Stock insuffisant !', 'danger')

    cur.close()
    conn.close()
    return redirect(url_for('article_public', id=id))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))