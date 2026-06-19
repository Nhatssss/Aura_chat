from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from datetime import datetime
from threading import Lock
import json, os, uuid, hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'aura_chat_secret_key_2024!')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

# Use eventlet for production, threading for dev
ASYNC_MODE = os.environ.get('ASYNC_MODE', 'threading')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=ASYNC_MODE)

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR    = 'data'
ACCOUNTS_F  = os.path.join(DATA_DIR, 'accounts.json')
MESSAGES_F  = os.path.join(DATA_DIR, 'messages.json')
UPLOAD_DIR  = os.path.join('static', 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_MSGS    = 300

os.makedirs(DATA_DIR,   exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

file_lock    = Lock()
online_users = {}          # sid -> {user_id, username, avatar_color}

# ── Helpers ────────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def allowed(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def unique_online():
    """Deduplicate online_users by user_id (same user, multiple tabs)."""
    seen, out = set(), []
    for u in online_users.values():
        if u['user_id'] not in seen:
            seen.add(u['user_id'])
            out.append(u)
    return out

# ── Seed JSON files if missing ─────────────────────────────────────────────
if not os.path.exists(ACCOUNTS_F):
    save_json(ACCOUNTS_F, {"users": []})
if not os.path.exists(MESSAGES_F):
    save_json(MESSAGES_F, {"messages": []})

# ── Routes ─────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('chat') if 'user_id' in session else url_for('login'))

# ---------- Login ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    d = request.get_json()
    uname = d.get('username', '').strip()
    pw    = d.get('password', '')
    accounts = load_json(ACCOUNTS_F, {"users": []})
    for u in accounts['users']:
        if u['username'].lower() == uname.lower() and u['password'] == hash_pw(pw):
            session['user_id']      = u['id']
            session['username']     = u['username']
            session['avatar_color'] = u.get('avatar_color', '#00e5ff')
            return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Sai tên đăng nhập hoặc mật khẩu'})

# ---------- Register ----------
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
    with file_lock:
        accounts = load_json(ACCOUNTS_F, {"users": []})
        if any(u['username'].lower() == uname.lower() for u in accounts['users']):
            return jsonify({'success': False, 'message': 'Tên đăng nhập đã tồn tại'})
        color = COLORS[len(accounts['users']) % len(COLORS)]
        new_u = {
            'id': str(uuid.uuid4()),
            'username': uname,
            'password': hash_pw(pw),
            'avatar_color': color,
            'created_at': datetime.now().isoformat()
        }
        accounts['users'].append(new_u)
        save_json(ACCOUNTS_F, accounts)

    session['user_id']      = new_u['id']
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

# ---------- API ----------
@app.route('/api/messages')
def api_messages():
    if 'user_id' not in session:
        return jsonify([]), 401
    data = load_json(MESSAGES_F, {"messages": []})
    return jsonify(data['messages'][-100:])

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
    with file_lock:
        data = load_json(MESSAGES_F, {"messages": []})
        data['messages'].append(msg)
        if len(data['messages']) > MAX_MSGS:
            data['messages'] = data['messages'][-MAX_MSGS:]
        save_json(MESSAGES_F, data)
    socketio.emit('new_message', msg, room='chat_room')
    return jsonify({'success': True, 'message': msg})

# ── Socket.IO ──────────────────────────────────────────────────────────────
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
    with file_lock:
        data2 = load_json(MESSAGES_F, {"messages": []})
        data2['messages'].append(msg)
        if len(data2['messages']) > MAX_MSGS:
            data2['messages'] = data2['messages'][-MAX_MSGS:]
        save_json(MESSAGES_F, data2)
    emit('new_message', msg, room='chat_room')

@socketio.on('typing')
def on_typing(data):
    if 'user_id' not in session:
        return
    emit('user_typing', {
        'username':  session['username'],
        'is_typing': data.get('is_typing', False)
    }, room='chat_room', include_self=False)

# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "=" * 52)
    print("  ⬡  AURA CHAT  –  Server khởi động")
    print("  Mở trình duyệt: http://localhost:5000")
    print("=" * 52 + "\n")
    PORT = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False,
                 allow_unsafe_werkzeug=True)
