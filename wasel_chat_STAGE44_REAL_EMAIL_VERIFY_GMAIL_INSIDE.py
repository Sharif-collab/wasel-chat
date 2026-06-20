# -*- coding: utf-8 -*-
"""
واصل شات - المرحلة 44 - تحقق بريد حقيقي Gmail داخل نفس الملف
تشغيل في Termux:
    pip install flask werkzeug
    python wasel_chat_STAGE44_REAL_EMAIL_VERIFY_GMAIL_INSIDE.py
ثم افتح:
    http://127.0.0.1:5000
"""

import os
import sqlite3
import random
import html
import re
import time
import secrets
import smtplib
from email.mime.text import MIMEText
from email.header import Header
escape = html.escape
from datetime import datetime, date, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, request, redirect, url_for, session, g, send_from_directory, jsonify, abort

APP_NAME = "واصل شات"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "wasel_chat_new.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)

def load_secret_key():
    env_key = os.environ.get("WASEL_SECRET_KEY")
    if env_key and len(env_key) >= 32:
        return env_key
    key_file = os.path.join(BASE_DIR, ".wasel_secret_key")
    if os.path.exists(key_file):
        try:
            return open(key_file, "r", encoding="utf-8").read().strip()
        except Exception:
            pass
    key = secrets.token_hex(32)
    try:
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(key)
    except Exception:
        pass
    return key

app.secret_key = load_secret_key()
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("WASEL_HTTPS"))

LOGIN_ATTEMPTS = {}

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587") or 587)
EMAIL_USER = os.environ.get("EMAIL_USER", "mjbbdalhafz6@gmail.com")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "qdjy dfss tbol aunp")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "واصل شات")

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "mp3", "wav", "ogg", "pdf", "doc", "docx", "txt", "zip"}

COUNTRIES = [
    {"flag":"🇾🇪","name":"اليمن","en":"Yemen","code":"+967","local_re":r"7\d{8}","min":9,"max":9},
    {"flag":"🇸🇦","name":"السعودية","en":"Saudi Arabia","code":"+966","local_re":r"5\d{8}","min":9,"max":9},
    {"flag":"🇦🇪","name":"الإمارات","en":"United Arab Emirates","code":"+971","local_re":r"5\d{8}","min":9,"max":9},
    {"flag":"🇴🇲","name":"عمان","en":"Oman","code":"+968","local_re":r"[279]\d{7}","min":8,"max":8},
    {"flag":"🇶🇦","name":"قطر","en":"Qatar","code":"+974","local_re":r"[3567]\d{7}","min":8,"max":8},
    {"flag":"🇰🇼","name":"الكويت","en":"Kuwait","code":"+965","local_re":r"[569]\d{7}","min":8,"max":8},
    {"flag":"🇧🇭","name":"البحرين","en":"Bahrain","code":"+973","local_re":r"[36]\d{7}","min":8,"max":8},
    {"flag":"🇪🇬","name":"مصر","en":"Egypt","code":"+20","local_re":r"1\d{9}","min":10,"max":10},
    {"flag":"🇯🇴","name":"الأردن","en":"Jordan","code":"+962","local_re":r"7\d{8}","min":9,"max":9},
    {"flag":"🇮🇶","name":"العراق","en":"Iraq","code":"+964","local_re":r"7\d{9}","min":10,"max":10},
    {"flag":"🇵🇸","name":"فلسطين","en":"Palestine","code":"+970","local_re":r"5\d{8}","min":9,"max":9},
    {"flag":"🇸🇾","name":"سوريا","en":"Syria","code":"+963","local_re":r"9\d{8}","min":9,"max":9},
    {"flag":"🇱🇧","name":"لبنان","en":"Lebanon","code":"+961","local_re":r"[37]\d{7}|8\d{6}","min":7,"max":8},
    {"flag":"🇸🇩","name":"السودان","en":"Sudan","code":"+249","local_re":r"9\d{8}","min":9,"max":9},
    {"flag":"🇹🇷","name":"تركيا","en":"Turkey","code":"+90","local_re":r"5\d{9}","min":10,"max":10},
    {"flag":"🇮🇳","name":"الهند","en":"India","code":"+91","local_re":r"[6-9]\d{9}","min":10,"max":10},
    {"flag":"🇵🇰","name":"باكستان","en":"Pakistan","code":"+92","local_re":r"3\d{9}","min":10,"max":10},
    {"flag":"🇺🇸","name":"أمريكا","en":"United States","code":"+1","local_re":r"[2-9]\d{9}","min":10,"max":10},
    {"flag":"🇬🇧","name":"بريطانيا","en":"United Kingdom","code":"+44","local_re":r"7\d{9}","min":10,"max":10},
]
COUNTRY_BY_CODE = {c['code']: c for c in COUNTRIES}

def clean_digits(value):
    return re.sub(r"\D+", "", value or "")

def parse_country_value(value, fallback_code='+967'):
    raw = (value or '').strip()
    for c in COUNTRIES:
        if c['code'] in raw or c['name'] in raw or c['en'].lower() in raw.lower() or clean_digits(c['code']) == clean_digits(raw):
            return c
    return COUNTRY_BY_CODE.get(fallback_code, COUNTRIES[0])

def country_display(country):
    c = country if isinstance(country, dict) else parse_country_value(country)
    return f"{c['flag']} {c['name']} {c['code']}"

def country_datalist_html():
    opts = ''.join([f"<option value='{h(country_display(c))}'>{h(c['en'])}</option>" for c in COUNTRIES])
    return f"<datalist id='country_list'>{opts}</datalist>"

def country_picker_html(field_name='country_picker', selected='+967', picker_id='countryPicker'):
    current = parse_country_value(selected)
    rows = []
    for c in COUNTRIES:
        label = country_display(c)
        search = (c['name'] + ' ' + c['en'] + ' ' + c['code'] + ' ' + clean_digits(c['code'])).lower()
        rows.append(
            f"<button type='button' class='countryRow' data-target='{h(field_name)}' data-label='{h(label)}' data-search='{h(search)}' onclick=\"selectCountry(this)\">"
            f"<span class='countryFlag'>{h(c['flag'])}</span><span class='countryName'>{h(c['name'])}<small>{h(c['en'])}</small></span><b>{h(c['code'])}</b></button>"
        )
    return f"""
    <input type='hidden' name='{h(field_name)}' id='{h(field_name)}' value='{h(country_display(current))}'>
    <button type='button' class='countrySelect' onclick="openCountryPicker('{h(picker_id)}','{h(field_name)}')">
        <span id='{h(field_name)}_label'>{h(country_display(current))}</span><b>›</b>
    </button>
    <div class='countryModal' id='{h(picker_id)}'>
        <div class='countrySheet'>
            <div class='countryHead'><button type='button' class='icon' onclick="closeCountryPicker('{h(picker_id)}')">×</button><b>اختيار الدولة</b></div>
            <div class='countrySearch'><input type='search' oninput="filterCountries('{h(picker_id)}', this.value)" placeholder='بحث باسم الدولة أو رمزها'></div>
            <div class='countryList'>{''.join(rows)}</div>
        </div>
    </div>
    """

def normalize_phone_by_country(phone, country_value='+967'):
    c = parse_country_value(country_value)
    digits = clean_digits(phone)
    code_digits = clean_digits(c['code'])
    if digits.startswith('00' + code_digits):
        return None, None, c, 'اكتب الرقم بدون رمز الدولة'
    if digits.startswith(code_digits) and len(digits) > c.get('max', 15):
        return None, None, c, 'اكتب الرقم بدون رمز الدولة'
    if not digits:
        return None, None, c, 'أدخل رقم الهاتف'
    if not re.fullmatch(c['local_re'], digits):
        return None, None, c, 'رقم الهاتف غير صحيح حسب الدولة المختارة'
    full = c['code'] + digits
    return digits, full, c, ''

def h(value):
    return escape(str(value or ""), quote=True)

def normalize_yemeni_phone(phone):
    local, full, c, err = normalize_phone_by_country(phone, '+967')
    return local if local and c['code'] == '+967' else None

def phone_lookup_values(raw):
    """يعيد قيم محتملة للبحث: رقم محلي، رقم كامل، بريد أو اسم مستخدم."""
    value = (raw or '').strip().lower()
    if not value:
        return []
    vals = {value}
    digits = clean_digits(value)
    if digits:
        vals.add(digits)
        for c in COUNTRIES:
            code = clean_digits(c['code'])
            if digits.startswith(code):
                local = digits[len(code):]
                vals.add(local)
                vals.add(c['code'] + local)
            else:
                vals.add(c['code'] + digits)
    return [v for v in vals if v]

def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token

def inject_csrf(html_text):
    token = csrf_token()
    hidden = f"<input type='hidden' name='_csrf_token' value='{token}'>"
    return re.sub(r"(<form\b[^>]*method=['\"]post['\"][^>]*>)", r"\1" + hidden, html_text, flags=re.I)

@app.before_request
def security_before_request():
    if request.method == "POST":
        if request.path.startswith('/call_signal'):
            return None
        if re.fullmatch(r'/status/\d+/react', request.path) or re.fullmatch(r'/status/\d+/reply_msg/\d+/(react|edit|delete)', request.path):
            return None
        sent = request.form.get("_csrf_token") or request.headers.get("X-CSRFToken")
        expected = session.get("_csrf_token")
        if not expected or sent != expected:
            abort(400)
    return None

@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
    return resp

@app.errorhandler(400)
def bad_request_error(e):
    return page("<div class='top'><a class='icon' href='/chats'>‹</a><b>طلب غير صحيح</b></div><div class='card'>انتهت صلاحية الصفحة أو الطلب غير آمن. ارجع للصفحة السابقة وحاول مجددًا.</div>")

@app.errorhandler(413)
def file_too_large(e):
    return page("<div class='top'><a class='icon' href='/chats'>‹</a><b>الملف كبير</b></div><div class='card'>حجم الملف أكبر من المسموح. اختر ملفًا أصغر.</div>")

@app.errorhandler(500)
def internal_error(e):
    return page("<div class='top'><a class='icon' href='/chats'>‹</a><b>حدث خطأ</b></div><div class='card'>حدث خطأ داخلي. أعد تشغيل الصفحة، وإذا تكرر الخطأ فتواصل معنا.</div>")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_=None):
    con = g.pop("db", None)
    if con:
        con.close()

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        phone TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        avatar TEXT,
        about TEXT DEFAULT 'مرحباً، أستخدم واصل',
        online INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS contacts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        contact_id INTEGER NOT NULL,
        pinned INTEGER DEFAULT 0,
        archived INTEGER DEFAULT 0,
        muted INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0,
        note TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, contact_id)
    );
    CREATE TABLE IF NOT EXISTS address_book(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        saved_name TEXT NOT NULL,
        identifier TEXT NOT NULL,
        identifier_type TEXT DEFAULT 'unknown',
        country TEXT,
        linked_user_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        UNIQUE(user_id, identifier)
    );
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        body TEXT,
        file_name TEXT,
        file_type TEXT,
        reply_to INTEGER,
        starred INTEGER DEFAULT 0,
        deleted_for_sender INTEGER DEFAULT 0,
        deleted_for_receiver INTEGER DEFAULT 0,
        deleted_for_all INTEGER DEFAULT 0,
        reaction TEXT,
        is_read INTEGER DEFAULT 0,
        read_at TEXT,
        edited_at TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS statuses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        text TEXT,
        file_name TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS status_views(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status_id INTEGER NOT NULL,
        viewer_id INTEGER NOT NULL,
        viewed_at TEXT NOT NULL,
        UNIQUE(status_id, viewer_id)
    );
    CREATE TABLE IF NOT EXISTS status_reactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        owner_id INTEGER NOT NULL,
        emoji TEXT NOT NULL,
        reacted_at TEXT NOT NULL,
        UNIQUE(status_id, user_id)
    );
    CREATE TABLE IF NOT EXISTS status_replies(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        owner_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS calls(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caller_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        call_type TEXT NOT NULL,
        status TEXT DEFAULT 'منتهية',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS call_signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notifications(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        actor_id INTEGER,
        text TEXT NOT NULL,
        link TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reset_codes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ident TEXT NOT NULL,
        code TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS email_verify_codes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    def add_col(table, col, definition):
        try:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
            if col not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        except Exception:
            pass
    
    add_col('messages', 'is_read', 'INTEGER DEFAULT 0')
    add_col('messages', 'read_at', 'TEXT')
    add_col('messages', 'edited_at', 'TEXT')
    add_col('messages', 'pinned', 'INTEGER DEFAULT 0')
    add_col('messages', 'reminder_at', 'TEXT')
    add_col('contacts', 'nickname', 'TEXT')
    add_col('contacts', 'last_opened_at', 'TEXT')
    add_col('contacts', 'disappearing_timer', 'INTEGER DEFAULT 0')
    add_col('users', 'gender', 'TEXT')
    add_col('users', 'birth_date', 'TEXT')
    add_col('users', 'country', 'TEXT')
    add_col('users', 'phone_country_code', 'TEXT')
    add_col('users', 'phone_full', 'TEXT')
    add_col('users', 'is_verified', 'INTEGER DEFAULT 0')
    add_col('users', 'email_verified_at', 'TEXT')
    add_col('users', 'privacy_last_seen', "TEXT DEFAULT 'everyone'")
    add_col('users', 'privacy_avatar', "TEXT DEFAULT 'everyone'")
    add_col('statuses', 'privacy', "TEXT DEFAULT 'public'")
    add_col('statuses', 'expires_at', 'TEXT')
    add_col('statuses', 'bg', "TEXT DEFAULT 'blue'")
    add_col('statuses', 'last_viewed_at', 'TEXT')
    add_col('statuses', 'views_count_cache', 'INTEGER DEFAULT 0')
    add_col('status_reactions', 'owner_id', 'INTEGER')
    add_col('status_reactions', 'emoji', 'TEXT')
    add_col('status_reactions', 'reacted_at', 'TEXT')
    add_col('status_reactions', 'user_id', 'INTEGER')
    add_col('status_reactions', 'status_id', 'INTEGER')
    try:
        cur.execute("DELETE FROM status_reactions WHERE id NOT IN (SELECT MAX(id) FROM status_reactions GROUP BY status_id,user_id)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_status_reactions_unique ON status_reactions(status_id,user_id)")
    except Exception:
        pass

    add_col('status_replies', 'parent_id', 'INTEGER')
    add_col('status_replies', 'to_user_id', 'INTEGER')
    add_col('status_replies', 'is_owner_reply', 'INTEGER DEFAULT 0')
    add_col('status_replies', 'reaction', 'TEXT')
    add_col('status_replies', 'edited_at', 'TEXT')
    add_col('calls', 'accepted_at', 'TEXT')
    add_col('calls', 'ended_at', 'TEXT')
    add_col('calls', 'duration_seconds', 'INTEGER DEFAULT 0')
    add_col('calls', 'declined_by', 'INTEGER')
    add_col('messages', 'reminder_done', 'INTEGER DEFAULT 0')
    add_col('notifications', 'type', "TEXT DEFAULT 'general'")
    add_col('notifications', 'priority', "TEXT DEFAULT 'normal'")
    add_col('users', 'notify_messages', 'INTEGER DEFAULT 1')
    add_col('users', 'notify_statuses', 'INTEGER DEFAULT 1')
    add_col('users', 'notify_calls', 'INTEGER DEFAULT 1')
    add_col('users', 'theme_mode', "TEXT DEFAULT 'dark'")
    add_col('users', 'font_size', "TEXT DEFAULT 'normal'")
    add_col('users', 'accent_color', "TEXT DEFAULT 'blue'")
    add_col('users', 'media_autodownload', 'INTEGER DEFAULT 1')
    add_col('users', 'save_media_gallery', 'INTEGER DEFAULT 0')
    add_col('users', 'read_receipts', 'INTEGER DEFAULT 1')
    add_col('users', 'service_chat_enabled', 'INTEGER DEFAULT 1')
    add_col('users', 'service_status_enabled', 'INTEGER DEFAULT 1')
    add_col('users', 'service_calls_enabled', 'INTEGER DEFAULT 1')
    add_col('users', 'cover_photo', 'TEXT')
    add_col('users', 'location', 'TEXT')
    add_col('users', 'website', 'TEXT')
    add_col('users', 'profile_visibility', "TEXT DEFAULT 'everyone'")
    add_col('users', 'last_login_at', 'TEXT')
    add_col('users', 'last_logout_at', 'TEXT')
    add_col('address_book', 'identifier_type', "TEXT DEFAULT 'unknown'")
    add_col('address_book', 'linked_user_id', 'INTEGER')
    add_col('address_book', 'updated_at', 'TEXT')
    add_col('address_book', 'country_code', 'TEXT')
    add_col('address_book', 'phone_full', 'TEXT')
    con.commit()
    con.close()

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def make_code():
    return str(random.randint(100000, 999999))

def age_from_birth(birth):
    try:
        y, m, d = [int(x) for x in birth.split('-')]
        born = date(y, m, d)
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except Exception:
        return None

def notify(user_id, actor_id, text, link=None, typ='general', priority='normal'):
    try:
        user_id = int(user_id)
        u = db().execute('SELECT notify_messages,notify_statuses,notify_calls FROM users WHERE id=?', (user_id,)).fetchone()
        if u:
            if typ == 'message' and not u['notify_messages']:
                return
            if typ == 'status' and not u['notify_statuses']:
                return
            if typ == 'call' and not u['notify_calls']:
                return
        db().execute("INSERT INTO notifications(user_id,actor_id,text,link,type,priority,created_at) VALUES(?,?,?,?,?,?,?)", (user_id, actor_id, text, link, typ, priority, now()))
        db().commit()
    except Exception:
        pass

def smtp_ready():
    return bool(EMAIL_HOST and EMAIL_PORT and EMAIL_USER and EMAIL_PASS)

def send_mail(to_email, subject, body):
    if not smtp_ready():
        return False, "SMTP غير مضبوط"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = str(Header(EMAIL_FROM, "utf-8")) + f" <{EMAIL_USER}>"
        msg["To"] = to_email
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=20) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, [to_email], msg.as_string())
        return True, "تم الإرسال"
    except Exception as e:
        print("EMAIL_SEND_ERROR:", e)
        return False, str(e)

def create_email_verify_code(user_id, email):
    code = make_code()
    exp = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    db().execute("UPDATE email_verify_codes SET used=1 WHERE user_id=? AND used=0", (user_id,))
    db().execute("INSERT INTO email_verify_codes(user_id,email,code,expires_at,created_at) VALUES(?,?,?,?,?)", (user_id, email, code, exp, now()))
    db().commit()
    body = f"""مرحباً بك في واصل شات

رمز التحقق الخاص بك هو:
{code}

الرمز صالح لمدة 10 دقائق فقط.
لا تشارك الرمز مع أي شخص.

إذا لم تطلب إنشاء حساب في واصل شات، تجاهل هذه الرسالة.

فريق واصل شات
"""
    ok, info = send_mail(email, "رمز تحقق واصل شات", body)
    return code, ok, info

def verify_pending_user_id():
    return session.get('pending_verify_user_id')

def process_due_reminders(user_id):
    try:
        rows = db().execute("""SELECT id,body,file_name FROM messages
                             WHERE (sender_id=? OR receiver_id=?)
                               AND reminder_at IS NOT NULL AND reminder_at!=''
                               AND COALESCE(reminder_done,0)=0
                               AND reminder_at<=?
                             ORDER BY reminder_at LIMIT 20""", (user_id, user_id, now())).fetchall()
        for r in rows:
            text = '⏰ تذكير برسالة: ' + ((r['body'] or 'ملف مرفق')[:70])
            notify(user_id, user_id, text, '/message/' + str(r['id']) + '/info', 'reminder', 'high')
            db().execute('UPDATE messages SET reminder_done=1 WHERE id=?', (r['id'],))
        if rows:
            db().commit()
    except Exception:
        pass

def unread_notifications_count(user_id):
    try:
        process_due_reminders(user_id)
        return db().execute('SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0', (user_id,)).fetchone()['c']
    except Exception:
        return 0

def allowed(filename):
    if not filename or "." not in filename or len(filename) > 180:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXT

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def get_contact(user_id, peer_id):
    row = db().execute("SELECT * FROM contacts WHERE user_id=? AND contact_id=?", (user_id, peer_id)).fetchone()
    if not row:
        db().execute("INSERT OR IGNORE INTO contacts(user_id,contact_id,created_at) VALUES(?,?,?)", (user_id, peer_id, now()))
        db().commit()
        row = db().execute("SELECT * FROM contacts WHERE user_id=? AND contact_id=?", (user_id, peer_id)).fetchone()
    return row

def is_blocked_between(user_id, peer_id):
    a = db().execute("SELECT blocked FROM contacts WHERE user_id=? AND contact_id=?", (user_id, peer_id)).fetchone()
    b = db().execute("SELECT blocked FROM contacts WHERE user_id=? AND contact_id=?", (peer_id, user_id)).fetchone()
    return bool((a and a['blocked']) or (b and b['blocked']))

def login_required(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrap

CSS = r"""
:root{--bg:#07111f;--panel:#0d1b2d;--panel2:#101f33;--card:#13243a;--line:#203149;--text:#eaf2ff;--muted:#8fa2bb;--blue:#2563eb;--green:#20c784;--danger:#ef4444;--bubble:#173d72;--other:#152333}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#0d2035,#050b14 70%);font-family:Tahoma,Arial,sans-serif;color:var(--text);direction:rtl}a{text-decoration:none;color:inherit}input,textarea,select{font-family:inherit;font-size:16px}button{border:none;border-radius:12px;cursor:pointer;font-family:inherit;font-size:16px;padding:12px 20px}button:disabled{opacity:.5;pointer-events:none}
.auth{max-width:440px;margin:0 auto;padding:20px 0}.auth .title{text-align:center;font-size:32px;font-weight:900;margin:40px 0 8px;color:var(--green)}.auth .muted{text-align:center;margin-bottom:30px}.auth .card{background:rgba(13,27,45,.88);border:1px solid rgba(35,67,100,.4);padding:20px;border-radius:20px;margin:10px;line-height:1.8}
.btn{background:var(--blue);color:#fff;border:none;border-radius:18px;padding:14px 28px;font-weight:600;font-size:16px;cursor:pointer;display:inline-block}.btn:hover{background:#1d4ed8}.btn:active{transform:scale(.98)}.btn.gray{background:rgba(148,163,184,.15);color:var(--muted)}.btn.gray:hover{background:rgba(148,163,184,.25)}
.input{margin:14px 0;position:relative}.input input,.input textarea,.input select{width:100%;border:1px solid #1b2e49;background:#0b1728;color:#eaf2ff;border-radius:18px;padding:14px;font-size:16px}.input input:focus,.input textarea:focus,.input select:focus{outline:none;border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.2)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:520px){.grid{grid-template-columns:1fr}}
.authErrorBox{display:none;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.45);color:#fecaca;border-radius:16px;padding:11px 13px;margin:10px 0;font-size:14px;line-height:1.7}
.authErrorBox.show{display:block}
.fieldHint{display:none;color:#fca5a5;font-size:12px;margin:6px 6px 0}.input.hasError input,.input.hasError select,.input.hasError textarea,.countryPick.hasError{border-color:#ef4444!important;box-shadow:0 0 0 3px rgba(239,68,68,.2)!important}
.authSaving{opacity:.75;pointer-events:none}
.top{display:flex;gap:8px;padding:12px 14px;align-items:center;background:linear-gradient(180deg,rgba(13,27,45,.95),rgba(7,17,31,.85));border-bottom:1px solid rgba(61,91,126,.25);position:sticky;top:0;z-index:10}
.top .icon{width:42px;height:42px;border-radius:50%;background:rgba(148,163,184,.12);display:grid;place-items:center;font-size:24px;cursor:pointer}.top .icon:hover{background:rgba(148,163,184,.2)}.top .icon.green{color:var(--green)}
.top b{flex:1;text-align:center;font-weight:700;font-size:18px}
.muted{color:var(--muted);font-size:13px}.danger{color:var(--danger)!important}
.avatar{width:44px;height:44px;border-radius:50%;background:#0b1728;object-fit:cover;display:block}
.profileStats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:14px}.profileStats div{background:#0b1728;border:1px solid #1b2e49;border-radius:16px;padding:10px}.profileStats b{display:block;font-size:18px;color:#fff}.profileStats span{font-size:12px;color:var(--muted)}
.ltr{direction:ltr;text-align:left}.filechip{display:inline-block;margin-top:7px;background:#0b1728;border:1px solid #244263;color:#a5d6ff;padding:7px 11px;border-radius:14px;font-size:13px}
.countrySelect{width:100%;border:1px solid #1b2e49;background:#0b1728;color:#eaf2ff;border-radius:18px;padding:14px;display:flex;align-items:center;justify-content:space-between;font:inherit;text-align:right;cursor:pointer}
.countrySelect:hover{border-color:#2563eb}.countrySelect b{color:var(--muted);margin-right:8px}
.countryModal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;align-items:flex-end;backdrop-filter:blur(4px)}
.countrySheet{width:100%;max-height:70vh;background:linear-gradient(180deg,#0d1b2d,#081524);border-radius:28px 28px 0 0;display:flex;flex-direction:column;overflow:hidden}
.countryHead{display:flex;align-items:center;gap:10px;padding:14px;border-bottom:1px solid #1b2e49}.countryHead b{flex:1;text-align:center}.countryHead .icon{width:36px;height:36px;font-size:20px;border-radius:50%;background:rgba(148,163,184,.12);display:grid;place-items:center;cursor:pointer}
.countrySearch{padding:10px;border-bottom:1px solid #1b2e49}.countrySearch input{width:100%;border:1px solid #1b2e49;background:#0a1624;color:#eaf2ff;border-radius:14px;padding:10px;font-size:14px}
.countryList{overflow-y:auto;flex:1}.countryRow{display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid rgba(61,91,126,.2);background:transparent;border:none;color:#eaf2ff;text-align:right;cursor:pointer;width:100%}.countryRow:hover{background:rgba(37,99,235,.15)}.countryFlag{font-size:24px}.countryName{flex:1;text-align:right}.countryName small{display:block;font-size:12px;color:var(--muted)}.countryRow b{color:var(--muted);font-size:13px}
"""

def page(body, title=APP_NAME):
    body = inject_csrf(body)
    token = session.get('_csrf_token', '')
    return f"""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='csrf-token' content='{token}'><title>{h(title)}</title><style>{CSS}</style></head><body>{body}<script>
function csrf(){{return document.querySelector('meta[name="csrf-token"]')?.content||''}}
function clearAuthErrors(form){{
  form.querySelectorAll('.hasError').forEach(x=>x.classList.remove('hasError','shake'));
  form.querySelectorAll('.fieldHint').forEach(x=>{{x.textContent='';x.style.display='none'}});
  const box=form.querySelector('.authErrorBox'); if(box){{box.textContent='';box.classList.remove('show')}}
}}
function showAuthError(form,msg,field){{
  const box=form.querySelector('.authErrorBox');
  if(box){{box.textContent=msg||'حدث خطأ';box.classList.add('show')}}
  let el=null;
  if(field) el=form.querySelector(`[name="${{field}}"]`);
  if(!el && field==='country_picker') el=form.querySelector('#country_picker_label');
  if(el){{
    const wrap=el.closest('.input')||el.closest('.countryPick')||el.parentElement;
    if(wrap){{wrap.classList.add('hasError','shake'); setTimeout(()=>wrap.classList.remove('shake'),350)}}
    let hint=wrap?wrap.querySelector('.fieldHint'):null;
    if(!hint && wrap){{hint=document.createElement('div'); hint.className='fieldHint'; wrap.appendChild(hint)}}
    if(hint){{hint.textContent=msg||'تحقق من هذا الحقل';hint.style.display='block'}}
    if(el.focus) setTimeout(()=>el.focus(),80);
  }}
}}
function initAuthAjax(){{
  document.querySelectorAll('form.authAjax').forEach(form=>{{
    form.addEventListener('submit',async e=>{{
      e.preventDefault(); clearAuthErrors(form);
      const btn=form.querySelector('button[type=submit],button:not([type])');
      const old=btn?btn.textContent:'';
      if(btn){{btn.textContent='جاري التحقق...';btn.disabled=true}}
      form.classList.add('authSaving');
      try{{
        const fd=new FormData(form);
        const res=await fetch(form.action||location.href,{{method:'POST',headers:{{'X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()}},body:fd,credentials:'same-origin'}});
        let data={{ok:false,message:'خطأ غير معروف',field:''}}; 
        try{{
          const text=await res.text();
          data=JSON.parse(text);
        }}catch(e){{
          console.error('خطأ في قراءة الرد:',e);
          data={{ok:false,message:'تعذر قراءة رد الخادم: '+e.message}}
        }}
        if(data.ok){{ location.href=data.redirect||'/chats'; return; }}
        showAuthError(form,data.message||'توجد مشكلة في البيانات',data.field||'');
      }}catch(err){{ 
        console.error('خطأ الاتصال:',err);
        showAuthError(form,'تعذر الاتصال بالخادم: '+err.message,''); 
      }}
      finally{{ if(btn){{btn.textContent=old;btn.disabled=false}} form.classList.remove('authSaving'); }}
    }});
  }});
}}
function openCountryPicker(id,target){{
  const m=document.getElementById(id); if(!m)return;
  m.dataset.target=target||'country_picker';
  m.style.display='flex';
  const inp=m.querySelector('.countrySearch input');
  if(inp){{inp.value=''; filterCountries(id,''); setTimeout(()=>inp.focus(),120);}}
}}
function closeCountryPicker(id){{const m=document.getElementById(id); if(m)m.style.display='none'}}
function filterCountries(id,q){{
  const m=document.getElementById(id); if(!m)return;
  const v=(q||'').trim().toLowerCase().replace(/\+/g,''); let shown=0;
  m.querySelectorAll('.countryRow').forEach(r=>{{
    const s=(r.dataset.search||'').replace(/\+/g,'');
    const ok=!v || s.includes(v);
    r.style.display=ok?'flex':'none'; if(ok)shown++;
  }});
}}
function selectCountry(btn){{
  const label=btn.dataset.label||'';
  const target=btn.dataset.target || btn.closest('.countryModal')?.dataset.target || 'country_picker';
  const hidden=document.getElementById(target); if(hidden)hidden.value=label;
  const lab=document.getElementById(target+'_label'); if(lab)lab.textContent=label;
  const modal=btn.closest('.countryModal'); if(modal)modal.style.display='none';
  const phone=document.querySelector('input[name=phone], input[name=identifier]'); if(phone)phone.focus();
}}
document.addEventListener('DOMContentLoaded',()=>{{initAuthAjax(); document.querySelectorAll('.countryModal').forEach(m=>m.addEventListener('click',e=>{{if(e.target===m)m.style.display='none'}}))}});
</script></body></html>"""

def wants_json():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json'

def auth_fail(kind, message, field='', status=400):
    if wants_json():
        return jsonify({'ok': False, 'message': message, 'field': field}), status
    return page(auth_html(kind, message))

def auth_success(url):
    if wants_json():
        return jsonify({'ok': True, 'redirect': url})
    return redirect(url)

def auth_html(kind, err=''):
    """إنشاء نموذج التسجيل أو الدخول"""
    isreg = kind == 'register'
    country_default = country_display(COUNTRY_BY_CODE['+967'])
    
    fields = "" if not isreg else f"""
    <div class='input'><input name='name' placeholder='الاسم الكامل'></div>
    <div class='grid'><div class='input'><input name='email' placeholder='البريد الإلكتروني'></div><div class='input'><input name='phone' inputmode='numeric' pattern='[0-9]*' placeholder='رقم الهاتف (اختياري)'></div></div>
    <div class='grid'>
        <div class='input'><label class='muted' style='display:block;margin-bottom:6px'>🌍 الدولة</label>{country_picker_html('country_picker', country_default, 'countryPickerRegister')}</div>
        <div class='input'><label class='muted' style='display:block;margin-bottom:6px'>📅 تاريخ الميلاد</label><input name='birth_date' type='date'></div>
    </div>
    <div class='input'><select name='gender' style='width:100%;border:1px solid #1b2e49;background:#0b1728;color:#eaf2ff;border-radius:18px;padding:14px'><option value=''>الجنس</option><option>ذكر</option><option>أنثى</option></select></div>
    """
    
    ident = "" if isreg else "<div class='input'><input name='ident' placeholder='البريد أو رقم الهاتف'></div>"
    confirm = "<div class='input'><input type='password' name='password2' placeholder='تأكيد كلمة المرور'></div>" if isreg else ""
    forgot = "" if isreg else "<p class='muted'><a href='/forgot'>نسيت كلمة المرور؟</a></p>"
    
    title = "تسجيل حساب جديد" if isreg else "تسجيل الدخول"
    button_text = "إنشاء الحساب" if isreg else "تسجيل الدخول"
    link_text = "هل لديك حساب بالفعل؟ " if isreg else "ليس لديك حساب؟ "
    link_href = "/login" if isreg else "/register"
    link_label = "تسجيل الدخول" if isreg else "إنشاء حساب"
    
    return f"""
    <div class='auth'>
        <div class='title'>واصل شات</div>
        <div class='muted'>التطبيق الآمن للمحادثات والحالات والمكالمات</div>
        <form class='card authAjax' method='post'>
            <div class='authErrorBox'>{'خطأ: ' + err if err else ''}</div>
            <h2 style='text-align:center;margin:0 0 20px;font-size:20px'>{title}</h2>
            {fields}
            {ident}
            <div class='input'><input type='password' name='password' placeholder='كلمة المرور'></div>
            {confirm}
            <button class='btn' style='width:100%;margin-top:20px'>{button_text}</button>
        </form>
        <div class='card'>
            <p class='muted'>{link_text}<a href='{link_href}' style='color:var(--blue)'>{link_label}</a></p>
            {forgot}
        </div>
    </div>
    """

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = (request.form.get('email','').strip() or '').lower()
        country_pick = request.form.get('country_picker','').strip() or request.form.get('country','').strip()
        country_info = parse_country_value(country_pick)
        country = country_info['name']
        phone_country_code = country_info['code']
        phone_raw = request.form.get('phone','').strip()
        phone = None
        phone_full = None
        if phone_raw:
            phone, phone_full, country_info, phone_err = normalize_phone_by_country(phone_raw, phone_country_code)
            country = country_info['name']
            phone_country_code = country_info['code']
            if phone_err:
                return auth_fail('register', phone_err, 'phone')
        gender = request.form.get('gender','').strip() or None
        birth_date = request.form.get('birth_date','').strip() or None
        password = request.form.get('password','')
        password2 = request.form.get('password2','')
        if not email or '@' not in email or '.' not in email:
            return auth_fail('register', 'البريد الإلكتروني الصحيح مطلوب للتحقق من الحساب', 'email')
        if not name or not password:
            return auth_fail('register', 'أدخل الاسم والبريد وكلمة المرور', 'name')
        if len(password) < 8:
            return auth_fail('register', 'كلمة المرور يجب أن تكون 8 أحرف على الأقل', 'password')
        if password != password2:
            return auth_fail('register', 'تأكيد كلمة المرور غير مطابق', 'password2')
        if birth_date:
            age = age_from_birth(birth_date)
            if age is None or age < 18:
                return auth_fail('register', 'العمر يجب أن يكون 18 سنة أو أكثر', 'birth_date')
        username_base = ''.join(ch for ch in name.lower().replace(' ','_') if ch.isalnum() or ch=='_')[:20] or 'wasel'
        username = '@' + username_base
        i = 1
        while db().execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
            i += 1
            username = '@' + username_base + str(i)
        try:
            cur = db().execute("""INSERT INTO users(name,username,email,phone,phone_country_code,phone_full,password_hash,gender,birth_date,country,is_verified,created_at)
                                VALUES(?,?,?,?,?,?,?,?,?,?,0,?)""", (name, username, email, phone, phone_country_code, phone_full, generate_password_hash(password), gender, birth_date, country, now()))
            db().commit()
            uid = cur.lastrowid
            code, ok, info = create_email_verify_code(uid, email)
            session.clear()
            session['_csrf_token'] = secrets.token_urlsafe(32)
            session['pending_verify_user_id'] = uid
            session['pending_verify_email'] = email
            if ok:
                session['verify_flash'] = 'تم إرسال رمز التحقق إلى بريدك الإلكتروني.'
                session.pop('verify_error', None)
            else:
                session['verify_error'] = 'تعذر إرسال رمز التحقق الآن. تأكد من اتصال الإنترنت أو اضغط إعادة إرسال.'
                print('EMAIL_VERIFY_SEND_ERROR:', info)
            return auth_success('/verify_email')
        except sqlite3.IntegrityError:
            return auth_fail('register', 'البريد أو الرقم مستخدم من قبل', 'email')
    return page(auth_html('register'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        ident = request.form.get('ident','').strip().lower()
        password = request.form.get('password','')
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'local').split(',')[0].strip()
        rec = LOGIN_ATTEMPTS.get(ip, {'count': 0, 'until': 0})
        if rec.get('until', 0) > time.time():
            return auth_fail('login', 'محاولات كثيرة. انتظر قليلًا ثم حاول من جديد', 'ident', 429)
        lookup_vals = phone_lookup_values(ident)
        placeholders = ','.join(['?'] * len(lookup_vals)) if lookup_vals else '?'
        params = lookup_vals or [ident]
        u = db().execute(f"SELECT * FROM users WHERE lower(email) IN ({placeholders}) OR phone IN ({placeholders}) OR phone_full IN ({placeholders})", params + params + params).fetchone()
        if u and check_password_hash(u['password_hash'], password):
            if u['email'] and ('is_verified' in u.keys()) and not u['is_verified']:
                code, ok, info = create_email_verify_code(u['id'], u['email'])
                session.clear()
                session['_csrf_token'] = secrets.token_urlsafe(32)
                session['pending_verify_user_id'] = u['id']
                session['pending_verify_email'] = u['email']
                if ok:
                    session['verify_flash'] = 'تم إرسال رمز تحقق جديد إلى بريدك الإلكتروني.'
                    session.pop('verify_error', None)
                else:
                    session['verify_error'] = 'تعذر إرسال رمز التحقق الآن. اضغط إعادة إرسال بعد لحظات.'
                    print('EMAIL_VERIFY_SEND_ERROR:', info)
                return auth_success('/verify_email')
            LOGIN_ATTEMPTS.pop(ip, None)
            session.clear()
            session['_csrf_token'] = secrets.token_urlsafe(32)
            session['user_id'] = u['id']
            db().execute("UPDATE users SET online=1, last_login_at=? WHERE id=?", (now(), u['id']))
            db().commit()
            return auth_success('/chats')
        rec['count'] = rec.get('count', 0) + 1
        if rec['count'] >= 7:
            rec['until'] = time.time() + 600
        LOGIN_ATTEMPTS[ip] = rec
        return auth_fail('login', 'بيانات الدخول غير صحيحة', 'password')
    return page(auth_html('login'))

@app.route('/verify_email', methods=['GET','POST'])
def verify_email():
    uid = verify_pending_user_id()
    if not uid:
        return redirect('/login')
    u = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        session.clear()
        return redirect('/register')
    msg = ''
    if request.method == 'POST':
        code = request.form.get('code','').strip()
        r = db().execute("""SELECT * FROM email_verify_codes
                           WHERE user_id=? AND code=? AND used=0
                           ORDER BY id DESC LIMIT 1""", (uid, code)).fetchone()
        if not r or r['expires_at'] < now():
            msg = 'الرمز غير صحيح أو ��نتهي. أعد الإرسال وجرب مرة ثانية.'
        else:
            db().execute("UPDATE email_verify_codes SET used=1 WHERE id=?", (r['id'],))
            db().execute("UPDATE users SET is_verified=1, email_verified_at=? WHERE id=?", (now(), uid))
            db().execute("UPDATE users SET online=1, last_login_at=? WHERE id=?", (now(), uid))
            db().commit()
            session.clear()
            session['_csrf_token'] = secrets.token_urlsafe(32)
            session['user_id'] = uid
            return redirect('/chats')
    flash = session.pop('verify_flash', '')
    send_error = session.pop('verify_error', '')
    info_box = ''
    if flash:
        info_box = f"<div class='card' style='border-color:#22c55e;color:#bbf7d0'>✅ {h(flash)}</div>"
    if send_error:
        info_box = f"<div class='card' style='border-color:#ef4444;color:#fecaca'>⚠️ {h(send_error)}</div>"
    email = h(u['email'])
    return page(f"""
    <div class='top'><a class='icon' href='/login'>‹</a><b>تحقق البريد</b></div>
    <form class='card' method='post'>
      <p class='muted'>أرسلنا رمز تحقق إلى: <b>{email}</b></p>
      <p class='danger'>{h(msg)}</p>
      <div class='input'><input name='code' inputmode='numeric' maxlength='6' placeholder='رمز التحقق من 6 أرقام'></div>
      <button class='btn' style='width:100%'>تأكيد وتسجيل الدخول</button>
    </form>
    <div class='card'><a class='btn gray' href='/resend_verify_email'>إعادة إرسال الرمز</a></div>
    {info_box}
    """)

@app.route('/resend_verify_email')
def resend_verify_email():
    uid = verify_pending_user_id()
    if not uid:
        return redirect('/login')
    u = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u or not u['email']:
        return redirect('/login')
    code, ok, info = create_email_verify_code(uid, u['email'])
    if ok:
        session['verify_flash'] = 'تم إرسال رمز تحقق جديد إلى بريدك الإلكتروني.'
        session.pop('verify_error', None)
    else:
        session['verify_error'] = 'تعذر إرسال رمز التحقق. تأكد من الإنترنت ثم جرّب إعادة الإرسال.'
        print('EMAIL_VERIFY_SEND_ERROR:', info)
    return redirect('/verify_email')

@app.route('/')
def home():
    return redirect('/chats' if session.get('user_id') else '/login')

@app.route('/logout', methods=['GET','POST'])
@login_required
def logout():
    u = current_user()
    if request.method == 'POST':
        uid = session.get('user_id')
        if uid:
            db().execute("UPDATE users SET online=0, last_logout_at=? WHERE id=?", (now(), uid))
            db().commit()
        session.clear()
        return redirect('/login')
    return page(f"""
    <div class='top'><a class='icon' href='/me'>‹</a><b>تسجيل الخروج</b></div>
    <div class='card' style='text-align:center'>
      <img class='avatar' style='width:86px;height:86px' src='https://ui-avatars.com/api/?background=123&color=fff&name={u["name"].replace(" ", "+")}'>
      <h2>{h(u['name'])}</h2>
      <p class='muted'>هل تريد الخروج من هذا الحساب؟</p>
      <form method='post'>
        <button class='btn' style='background:#ef4444;width:100%;margin-bottom:10px'>نعم، تسجيل الخروج</button>
      </form>
      <a class='btn gray' style='display:block' href='/me'>إلغاء</a>
    </div>
    """)

@app.route('/chats')
@login_required
def chats():
    return page("<div class='top'><b>المحادثات</b></div><div class='card'>أهلاً وسهلاً! المحادثات قريباً.</div>")

@app.route('/me')
@login_required
def me():
    u = current_user()
    return page(f"""
    <div class='top'><b>حسابي</b></div>
    <div class='card'>
      <div style='text-align:center'>
        <img class='avatar' style='width:86px;height:86px' src='https://ui-avatars.com/api/?background=123&color=fff&name={u["name"].replace(" ", "+")}'>
        <h2>{h(u['name'])}</h2>
        <p class='muted'>{h(u['username'])}</p>
      </div>
      <div style='margin-top:20px'>
        <a class='btn' href='/logout' style='width:100%;display:block'>تسجيل الخروج</a>
      </div>
    </div>
    """)

@app.errorhandler(404)
def not_found(e):
    if session.get('user_id'):
        return redirect(url_for('chats'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    print('✅ واصل شات - تطبيق المحادثات الآمن يعمل على: http://127.0.0.1:5000')
    print('📧 البريد الإلكتروني:', EMAIL_USER if EMAIL_USER else 'غير مضبوط')
    print('🔐 المفتاح السري محفوظ بأمان')
    app.run(host='0.0.0.0', port=5000, debug=False)
