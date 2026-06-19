from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
from pywebpush import webpush, WebPushException
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
import sqlite3, json, os, uuid, hashlib, base64

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'aura_chat_secret_key_2024!')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

socketio = SocketIO(app, cors_allowed_origins="*")

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, 'data')
DB_PATH     = os.path.join(DATA_DIR, 'aura.db')
UPLOAD_DIR  = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_MSGS    = 300

os.makedirs(DATA_DIR,   exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

online_users = {}  # sid -> {user_id, username, avatar_color}

# ── VAPID Keys for Push Notification ───────────────────────
VAPID_KEYS_FILE = os.path.join(BASE_DIR, '.vapid_keys.json')

def load_or_generate_vapid():
    # 1. Try env vars
    priv = os.environ.get('VAPID_PRIVATE_KEY')
    pub  = os.environ.get('VAPID_PUBLIC_KEY_B64')
    if priv and pub:
        return priv, pub

    # 2. Try file
    if os.path.exists(VAPID_KEYS_FILE):
        with open(VAPID_KEYS_FILE) as f:
            d = json.load(f)
            return d['private_key'], d['public_key']

    # 3. Generate new keys (first run)
    print("  -> Generating VAPID keys...")
    v = Vapid()
    v.generate_keys()
    priv_pem = v.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    pub_raw = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    pub_b64 = base64.urlsafe_b64encode(pub_raw).rstrip(b'=').decode()

    with open(VAPID_KEYS_FILE, 'w') as f:
        json.dump({"private_key": priv_pem, "public_key": pub_b64}, f)
    print("  -> VAPID keys saved to", VAPID_KEYS_FILE)
    return priv_pem, pub_b64

VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY_B64 = load_or_generate_vapid()

# ── Database ───────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id        TEXT PRIMARY KEY,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL,
            avatar_color TEXT NOT NULL DEFAULT '#00e5ff',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id          TEXT PRIMARY KEY,
            sender_id   TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            avatar_color TEXT NOT NULL,
            content     TEXT DEFAULT '',
            type        TEXT NOT NULL DEFAULT 'text',
            image_url   TEXT,
            timestamp   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            endpoint TEXT PRIMARY KEY,
            p256dh   TEXT NOT NULL,
            auth     TEXT NOT NULL,
            user_id  TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_msg_time ON messages(timestamp);
    """)
    db.commit()
    db.close()

# ── Migrate JSON -> SQLite ─────────────────────────────────
def migrate_json_to_sqlite():
    accounts_f = os.path.join(DATA_DIR, 'accounts.json')
    messages_f = os.path.join(DATA_DIR, 'messages.json')
    if not os.path.exists(accounts_f) and not os.path.exists(messages_f):
        return

    db = get_db()
    cur = db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    if cur > 0:
        db.close()
        return
    print("  -> Migrating JSON to SQLite ...")

    if os.path.exists(accounts_f):
        try:
            with open(accounts_f, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
            for u in accounts.get('users', []):
                db.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)",
                    (u['id'], u['username'], u['password'],
                     u.get('avatar_color', '#00e5ff'), u.get('created_at', '')))
        except: pass

    if os.path.exists(messages_f):
        try:
            with open(messages_f, 'r', encoding='utf-8') as f:
                msgs = json.load(f)
            for m in msgs.get('messages', []):
                db.execute("INSERT OR IGNORE INTO messages VALUES (?,?,?,?,?,?,?,?)",
                    (m['id'], m['sender_id'], m['sender_name'], m['avatar_color'],
                     m.get('content', ''), m.get('type', 'text'), m.get('image_url'), m['timestamp']))
        except: pass

    db.commit()
    db.close()
    for f in [accounts_f, messages_f]:
        if os.path.exists(f):
            os.rename(f, f + '.bak')
    print("  OK - Migration done")

init_db()
migrate_json_to_sqlite()

# ── Push Notification Helper ──────────────────────────────
def send_push_notification(title, body, url='/'):
    db = get_db()
    subs = db.execute("SELECT * FROM push_subscriptions").fetchall()
    db.close()
    if not subs:
        return

    payload = json.dumps({"title": title, "body": body, "url": url})
    stale = []

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub['endpoint'],
                    "keys": {"p256dh": sub['p256dh'], "auth": sub['auth']}
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:aura@aura-chat.local"}
            )
        except WebPushException as ex:
            if ex.response and ex.response.status_code in (410, 404):
                stale.append(sub['endpoint'])

    if stale:
        db = get_db()
        for ep in stale:
            db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (ep,))
        db.commit()
        db.close()

# ── Helpers ─────────────────────────────────────────────────
def hash_pw(pw):
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def allowed(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def unique_online():
    seen, out = set(), []
    for u in online_users.values():
        if u['user_id'] not in seen:
            seen.add(u['user_id'])
            out.append(u)
    return out

# ── Routes ─────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('chat') if 'user_id' in session else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    d = request.get_json()
    uname = d.get('username', '').strip()
    pw    = d.get('password', '')

    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE LOWER(username)=? AND password=?",
        (uname.lower(), hash_pw(pw))
    ).fetchone()
    db.close()

    if row:
        session['user_id']      = row['id']
        session['username']     = row['username']
        session['avatar_color'] = row['avatar_color']
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Sai tên đăng nhập hoặc mật khẩu'})

@app.route('/register', methods=['POST'])
def register():
    d     = request.get_json()
    uname = d.get('username', '').strip()
    pw    = d.get('password', '')
    if len(uname) < 3:
        return jsonify({'success': False, 'message': 'Tên đăng nhập tối thiểu 3 ký tự'})
    if len(pw) < 6:
        return jsonify({'success': False, 'message': 'Mật khẩu tối thiểu 6 ký tự'})

    COLORS = ['#00e5ff','#7c3aed','#10b981','#f59e0b','#ef4444','#ec4899','#06b6d4','#8b5cf6']

    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM users WHERE LOWER(username)=?", (uname.lower(),)
    ).fetchone()
    if exists:
        db.close()
        return jsonify({'success': False, 'message': 'Tên đăng nhập đã tồn tại'})

    count = db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    color = COLORS[count % len(COLORS)]
    uid   = str(uuid.uuid4())
    now   = datetime.now().isoformat()

    db.execute("INSERT INTO users VALUES (?,?,?,?,?)", (uid, uname, hash_pw(pw), color, now))
    db.commit()
    db.close()

    session['user_id']      = uid
    session['username']     = uname
    session['avatar_color'] = color
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html',
        username=session['username'],
        user_id=session['user_id'],
        avatar_color=session['avatar_color'])

# ── Push Notification API ─────────────────────────────────
@app.route('/api/vapid-public-key')
def api_vapid_public_key():
    return jsonify({'key': VAPID_PUBLIC_KEY_B64})

@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    d = request.get_json()
    endpoint = d.get('endpoint', '')
    keys = d.get('keys', {})
    if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
        return jsonify({'error': 'Invalid subscription'}), 400

    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO push_subscriptions VALUES (?,?,?,?,?)",
        (endpoint, keys['p256dh'], keys['auth'],
         session['user_id'], datetime.now().isoformat())
    )
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/unsubscribe', methods=['POST'])
def api_unsubscribe():
    d = request.get_json()
    endpoint = d.get('endpoint', '')
    if endpoint:
        db = get_db()
        db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))
        db.commit()
        db.close()
    return jsonify({'success': True})

# ── Chat API ──────────────────────────────────────────────
@app.route('/api/messages')
def api_messages():
    if 'user_id' not in session:
        return jsonify([]), 401
    db = get_db()
    rows = db.execute(
        "SELECT * FROM messages ORDER BY timestamp DESC LIMIT 100"
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in reversed(rows)])

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    f = request.files.get('file')
    if not f or not allowed(f.filename):
        return jsonify({'error': 'File không hợp lệ'}), 400
    ext   = f.filename.rsplit('.', 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOAD_DIR, fname))

    msg = {
        'id':           str(uuid.uuid4()),
        'sender_id':    session['user_id'],
        'sender_name':  session['username'],
        'avatar_color': session['avatar_color'],
        'content':      '',
        'type':         'image',
        'image_url':    f'/static/uploads/{fname}',
        'timestamp':    datetime.now().isoformat()
    }

    db = get_db()
    trim_messages(db)
    db.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)",
        (msg['id'], msg['sender_id'], msg['sender_name'], msg['avatar_color'],
         msg['content'], msg['type'], msg['image_url'], msg['timestamp'])
    )
    db.commit()
    db.close()

    socketio.emit('new_message', msg, room='chat_room')
    send_push_notification(
        title=f"📷 {session['username']}",
        body="Đã gửi một ảnh",
        url='/'
    )
    return jsonify({'success': True, 'message': msg})

# ── Socket.IO ──────────────────────────────────────────────
def trim_messages(db):
    count = db.execute("SELECT COUNT(*) as c FROM messages").fetchone()['c']
    if count >= MAX_MSGS:
        to_delete = count - MAX_MSGS + 1
        db.execute(
            "DELETE FROM messages WHERE id IN (SELECT id FROM messages ORDER BY timestamp ASC LIMIT ?)",
            (to_delete,)
        )

@socketio.on('connect')
def on_connect():
    if 'user_id' not in session:
        return False
    online_users[request.sid] = {
        'user_id':      session['user_id'],
        'username':     session['username'],
        'avatar_color': session['avatar_color']
    }
    join_room('chat_room')
    users = unique_online()
    emit('online_users', users)
    emit('user_joined', {
        'user_id':      session['user_id'],
        'username':     session['username'],
        'avatar_color': session['avatar_color'],
        'online_users': users
    }, room='chat_room')

@socketio.on('disconnect')
def on_disconnect():
    if request.sid not in online_users:
        return
    user = online_users.pop(request.sid)
    leave_room('chat_room')
    emit('user_left', {
        'user_id':      user['user_id'],
        'username':     user['username'],
        'online_users': unique_online()
    }, room='chat_room')

@socketio.on('send_message')
def on_message(data):
    if 'user_id' not in session:
        return
    content = data.get('content', '').strip()
    if not content or len(content) > 2000:
        return
    msg = {
        'id':           str(uuid.uuid4()),
        'sender_id':    session['user_id'],
        'sender_name':  session['username'],
        'avatar_color': session['avatar_color'],
        'content':      content,
        'type':         'text',
        'image_url':    None,
        'timestamp':    datetime.now().isoformat()
    }

    db = get_db()
    trim_messages(db)
    db.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)",
        (msg['id'], msg['sender_id'], msg['sender_name'], msg['avatar_color'],
         msg['content'], msg['type'], msg['image_url'], msg['timestamp'])
    )
    db.commit()
    db.close()

    emit('new_message', msg, room='chat_room')
    send_push_notification(
        title=f"💬 {session['username']}",
        body=content[:100] + ('...' if len(content) > 100 else ''),
        url='/'
    )

@socketio.on('typing')
def on_typing(data):
    if 'user_id' not in session:
        return
    emit('user_typing', {
        'username':  session['username'],
        'is_typing': data.get('is_typing', False)
    }, room='chat_room', include_self=False)

# ── Entry point ────────────────────────────────────────────
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 5000))
    print("=" * 52)
    print("  AURA CHAT  -  SQLite + Push Notifications")
    print("  Open browser: http://localhost:%d" % PORT)
    print("=" * 52 + "\n")
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False,
                 allow_unsafe_werkzeug=True)
