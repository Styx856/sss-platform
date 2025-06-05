from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from bson.objectid import ObjectId
from flask_babel import Babel, gettext as _
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "gizli_anahtar"

# Session ayarları
app.permanent_session_lifetime = timedelta(days=30)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Çoklu dil desteği
babel = Babel()
app.config['BABEL_DEFAULT_LOCALE'] = 'tr'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'

LANGUAGES = ['tr', 'en']

def get_locale():
    lang = session.get('lang')
    if lang in LANGUAGES:
        return lang
    return request.accept_languages.best_match(LANGUAGES)

babel.init_app(app, locale_selector=get_locale)

@app.before_request
def before_request():
    g.lang = get_locale()

@app.route('/set-lang/<lang>')
def set_language(lang):
    if lang in LANGUAGES:
        session['lang'] = lang
        # Session'ı kalıcı yap
        session.permanent = True
    return redirect(request.referrer or url_for('faq_list'))

# MongoDB bağlantısı
app.config["MONGO_URI"] = "mongodb://localhost:27017/sss_platform"
mongo = PyMongo(app)

# Yetki kontrolü için decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session.get('role') != 'admin':
            flash("Bu sayfaya erişim yetkiniz yok.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ana Sayfa
@app.route('/')
def home():
    return redirect(url_for('faq_list'))

# Kayıt Ol
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = mongo.db.users
        username = request.form['username'].strip()
        password_raw = request.form['password']
        if not username or not password_raw:
            flash("Kullanıcı adı ve şifre zorunludur.", "warning")
            return render_template('register.html')
        if users.find_one({'username': username}):
            flash("Bu kullanıcı adı zaten alınmış.", "danger")
            return render_template('register.html')
        password = generate_password_hash(password_raw)
        users.insert_one({'username': username, 'password': password, 'role': 'user'})
        # Otomatik giriş
        session['username'] = username
        session['role'] = 'user'
        flash("Kayıt başarılı! Giriş yaptınız.", "success")
        return redirect(url_for('faq_list'))
    return render_template('register.html')

# Giriş Yap
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        username = request.form['username'].strip()
        password = request.form['password']
        user = users.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['role'] = user.get('role', 'user')
            flash("Giriş başarılı!", "success")
            return redirect(url_for('faq_list'))
        flash("Hatalı kullanıcı adı veya şifre.", "danger")
    return render_template('login.html')

# Çıkış Yap
@app.route('/logout')
def logout():
    session.clear()
    flash("Başarıyla çıkış yaptınız.", "info")
    return redirect(url_for('login'))

CATEGORIES = [
    'Çift Anadal', 'Kayıt', 'Yurt', 'Kimlik', 'Ders', 'Not', 'Yaz Okulu', 'Yatay Geçiş', 'Staj'
]

# SSS Listeleme
@app.route('/faq')
def faq_list():
    query = request.args.get('query')
    category = request.args.get('category')
    faqs = mongo.db.faqs
    filter_query = {}
    if query:
        filter_query['question'] = {'$regex': query, '$options': 'i'}
    if category and category in CATEGORIES:
        filter_query['category'] = category
    results = faqs.find(filter_query)
    return render_template('faq_list.html', faqs=results, query=query, category=category, categories=CATEGORIES)

# SSS Sil (Admin)
@app.route('/faq/delete/<faq_id>', methods=['POST'])
@admin_required
def delete_faq(faq_id):
    mongo.db.faqs.delete_one({'_id': ObjectId(faq_id)})
    flash("SSS başarıyla silindi.", "success")
    return redirect(url_for('faq_list'))

# SSS Düzenle (Admin)
@app.route('/faq/edit/<faq_id>', methods=['GET', 'POST'])
@admin_required
def edit_faq(faq_id):
    faqs = mongo.db.faqs
    faq = faqs.find_one({'_id': ObjectId(faq_id)})
    if not faq:
        flash("SSS bulunamadı.", "danger")
        return redirect(url_for('faq_list'))
    if request.method == 'POST':
        question = request.form['question']
        answer = request.form['answer']
        category = request.form.get('category')
        faqs.update_one({'_id': faq['_id']}, {'$set': {'question': question, 'answer': answer, 'category': category}})
        flash("SSS başarıyla güncellendi.", "success")
        return redirect(url_for('faq_list'))
    return render_template('edit_faq.html', faq=faq)

# Soru Öner (Kullanıcı)
@app.route('/ask', methods=['GET', 'POST'])
def ask_question():
    if 'username' not in session:
        flash("Soru önermek için giriş yapmalısınız.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        question_text = request.form['question_text'].strip()
        if not question_text:
            flash("Soru metni boş olamaz.", "warning")
            return render_template('ask_question.html')
        mongo.db.question_requests.insert_one({
            'username': session['username'],
            'question_text': question_text
        })
        flash("Soru öneriniz alınmıştır, teşekkür ederiz!", "success")
        return redirect(url_for('faq_list'))
    return render_template('ask_question.html')

# Kullanıcının önerdiği sorular
@app.route('/my-questions')
def my_questions():
    if 'username' not in session:
        flash("Giriş yapmalısınız.", "warning")
        return redirect(url_for('login'))
    questions = mongo.db.question_requests.find({'username': session['username']})
    return render_template('my_questions.html', questions=questions)

# Yetkili Yeni Soru ve Cevap Ekle
@app.route('/add-faq', methods=['GET', 'POST'])
@admin_required
def add_faq():
    # Diğer kullanıcıların önerdiği soruları çek
    question_requests = list(mongo.db.question_requests.find())
    if request.method == 'POST':
        question = request.form['question'].strip()
        answer = request.form['answer'].strip()
        category = request.form.get('category')
        if not question or not answer:
            flash("Soru ve cevap boş olamaz.", "warning")
            return render_template('add_faq.html', question_requests=question_requests)
        mongo.db.faqs.insert_one({'question': question, 'answer': answer, 'category': category})
        flash("SSS başarıyla eklendi.", "success")
        return redirect(url_for('faq_list'))
    return render_template('add_faq.html', question_requests=question_requests)

# Şifreyi Unuttum
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username'].strip()
        users = mongo.db.users
        user = users.find_one({'username': username})
        if not user:
            flash("Böyle bir kullanıcı bulunamadı.", "danger")
            return render_template('forgot_password.html')
        # Kullanıcı bulunduysa yeni şifreyi sor
        return render_template('reset_password.html', username=username)
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['POST'])
def reset_password():
    username = request.form['username'].strip()
    new_password = request.form['new_password']
    users = mongo.db.users
    user = users.find_one({'username': username})
    if not user:
        flash("Böyle bir kullanıcı bulunamadı.", "danger")
        return redirect(url_for('forgot_password'))
    hashed = generate_password_hash(new_password)
    users.update_one({'username': username}, {'$set': {'password': hashed}})
    flash("Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.", "success")
    return redirect(url_for('login'))

@app.route('/add-suggested-faq/<suggestion_id>', methods=['POST'])
@admin_required
def add_suggested_faq(suggestion_id):
    suggestion = mongo.db.question_requests.find_one({'_id': ObjectId(suggestion_id)})
    if suggestion:
        mongo.db.faqs.insert_one({
            'question': suggestion['question_text'],
            'answer': '',
            'category': ''
        })
        mongo.db.question_requests.delete_one({'_id': ObjectId(suggestion_id)})
        flash("Önerilen soru FAQ'a eklendi.", "success")
    else:
        flash("Öneri bulunamadı.", "danger")
    return redirect(url_for('add_faq'))

@app.route('/delete-suggested-faq/<suggestion_id>', methods=['POST'])
@admin_required
def delete_suggested_faq(suggestion_id):
    result = mongo.db.question_requests.delete_one({'_id': ObjectId(suggestion_id)})
    if result.deleted_count:
        flash("Öneri silindi.", "success")
    else:
        flash("Öneri bulunamadı.", "danger")
    return redirect(url_for('add_faq'))

if __name__ == '__main__':
    app.run(debug=True)
