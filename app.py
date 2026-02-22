from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
import qrcode
import os
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

db_config = {
    'host': os.environ.get('MYSQL_HOST'),
    'user': os.environ.get('MYSQL_USER'),
    'password': os.environ.get('MYSQL_PASSWORD'),
    'database': os.environ.get('MYSQL_DATABASE'),
    'port': int(os.environ.get('MYSQL_PORT', 3306))
}
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
    host = os.environ.get('MYSQL_HOST')
    user = os.environ.get('MYSQL_USER')
    password = os.environ.get('MYSQL_PASSWORD')
    database = os.environ.get('MYSQL_DATABASE')
    port = int(os.environ.get('MYSQL_PORT', 3306))
    
    print(f"Connexion à : {host}:{port} user={user} db={database}")
    
    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port
    )

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
                upload_result = cloudinary.uploader.upload(photo)
                photo_filename = upload_result['secure_url']

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO articles (nom, description, prix, stock, photo)
            VALUES (%s, %s, %s, %s, %s)
        """, (nom, description, prix, stock, photo_filename))
        conn.commit()
        article_id = cur.lastrowid

        import io
        base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
        url_article = f"{base_url}/article/{article_id}"
        qr = qrcode.make(url_article)
        buffer = io.BytesIO()
        qr.save(buffer, format='PNG')
        buffer.seek(0)
        qr_upload = cloudinary.uploader.upload(buffer, resource_type='image', public_id=f"qr_{article_id}")
        qr_url = qr_upload['secure_url']

        cur.execute("UPDATE articles SET qr_code = %s WHERE id = %s", (qr_url, article_id))
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
    cur.execute("DELETE FROM ventes WHERE article_id = %s", (id,))
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

# AJOUTER TABLEAU DE BORD
@app.route('/dashboard')
def dashboard():
    conn = get_db()
    cur = conn.cursor()

    # Total des articles
    cur.execute("SELECT COUNT(*) FROM articles")
    total_articles = cur.fetchone()[0]

    # Total des ventes
    cur.execute("SELECT COUNT(*), SUM(quantite) FROM ventes")
    ventes_stats = cur.fetchone()
    total_ventes = ventes_stats[0]
    total_quantite = ventes_stats[1] or 0

    # Chiffre d'affaires total
    cur.execute("""
        SELECT SUM(a.prix * v.quantite) 
        FROM ventes v 
        JOIN articles a ON v.article_id = a.id
    """)
    chiffre_affaires = cur.fetchone()[0] or 0

    # Articles avec stock bas (<=5)
    cur.execute("SELECT * FROM articles WHERE stock <= 5")
    stock_bas = cur.fetchall()

    # Historique des ventes
    cur.execute("""
        SELECT v.id, a.nom, v.quantite, a.prix, (v.quantite * a.prix) as total, v.date_vente
        FROM ventes v
        JOIN articles a ON v.article_id = a.id
        ORDER BY v.date_vente DESC
    """)
    historique = cur.fetchall()

    # Articles les plus vendus
    cur.execute("""
        SELECT a.nom, SUM(v.quantite) as total_vendu
        FROM ventes v
        JOIN articles a ON v.article_id = a.id
        GROUP BY a.id, a.nom
        ORDER BY total_vendu DESC
        LIMIT 5
    """)
    top_articles = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('dashboard.html',
        total_articles=total_articles,
        total_ventes=total_ventes,
        total_quantite=total_quantite,
        chiffre_affaires=chiffre_affaires,
        stock_bas=stock_bas,
        historique=historique,
        top_articles=top_articles
    )

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
        flash('success', 'vente_ok')
    else:
        flash('Stock insuffisant !', 'danger')

    cur.close()
    conn.close()
    return redirect(url_for('article_public', id=id))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))