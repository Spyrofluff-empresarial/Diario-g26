from flask import Flask, request, jsonify, send_from_directory, g
import sqlite3
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'data.db')
SITE_DIR = os.path.join(BASE_DIR, '')  # 'sitio' files are in the same folder

app = Flask(__name__, static_folder='sitio', static_url_path='')

# Database helpers
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            tags TEXT,
            ts TEXT NOT NULL,
            archived INTEGER DEFAULT 0
        )
    ''')
    # Ensure 'archived' column exists for older DBs
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info('entries')").fetchall()]
        if 'archived' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN archived INTEGER DEFAULT 0')
    except Exception:
        pass
    # votes table
    db.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            identifier_type TEXT NOT NULL,
            vote INTEGER NOT NULL,
            ts TEXT NOT NULL
        )
    ''')
    # reports table
    db.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            identifier_type TEXT NOT NULL,
            reason TEXT,
            ts TEXT NOT NULL
        )
    ''')
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Simple sanitization
SCRIPT_RE = re.compile(r'<script[\s\S]*?>[\s\S]*?<\/script>', re.IGNORECASE)
ONHANDLER_RE = re.compile(r'on\w+=\"?[^\"\s>]+\"?', re.IGNORECASE)

def sanitize(text):
    if not text:
        return ''
    text = SCRIPT_RE.sub('', text)
    text = ONHANDLER_RE.sub('', text)
    return text.strip()


def get_identifier():
    # Prefer cookie-based identifier (per-device if user consented), fallback to IP
    cookie_id = request.cookies.get('user_id')
    if cookie_id:
        return ('cookie', cookie_id)
    # Try X-Forwarded-For header first
    xf = request.headers.get('X-Forwarded-For', '')
    if xf:
        # take first
        ip = xf.split(',')[0].strip()
    else:
        ip = request.remote_addr or '0.0.0.0'
    return ('ip', ip)

# Routes to serve static files
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# API endpoints
@app.route('/api/submit', methods=['POST'])
def api_submit():
    init_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message':'Invalid JSON'}), 400
    content = sanitize(data.get('content',''))
    tags = data.get('tags','')
    if not content:
        return jsonify({'message':'Contenido vacío'}), 400
    if len(content) > 2000:
        return jsonify({'message':'Contenido demasiado largo'}), 400
    ts = datetime.utcnow().isoformat() + 'Z'
    db = get_db()
    cur = db.execute('INSERT INTO entries (content,tags,ts) VALUES (?,?,?)', (content, tags, ts))
    db.commit()
    entry_id = cur.lastrowid
    return jsonify({'message':'ok','id':entry_id}), 201

@app.route('/api/entries', methods=['GET'])
def api_entries():
    init_db()
    limit = min(100, int(request.args.get('limit', '20') or '20'))
    db = get_db()
    cur = db.execute('''
        SELECT e.id, e.content, e.tags, e.ts,
          IFNULL((SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as upvotes,
          IFNULL((SELECT SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as downvotes,
          IFNULL((SELECT COUNT(*) FROM reports r WHERE r.entry_id=e.id),0) as reports
        FROM entries e
        WHERE e.archived=0
        ORDER BY e.id DESC
        LIMIT ?
    ''', (limit,))
    rows = cur.fetchall()
    entries = []
    for r in rows:
        entries.append({'id': r['id'], 'content': r['content'], 'tags': r['tags'], 'ts': r['ts'], 'upvotes': r['upvotes'], 'downvotes': r['downvotes'], 'reports': r['reports']})
    return jsonify({'entries': entries})


@app.route('/api/vote', methods=['POST'])
def api_vote():
    init_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message':'Invalid JSON'}), 400
    entry_id = int(data.get('entry_id') or 0)
    vote = int(data.get('vote') or 0)
    if vote not in (1, -1):
        return jsonify({'message':'Invalid vote'}), 400
    db = get_db()
    cur = db.execute('SELECT id, archived FROM entries WHERE id=?', (entry_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({'message':'Entry not found'}), 404
    if row['archived']:
        return jsonify({'message':'Entry archived'}), 410

    id_type, ident = get_identifier()
    ts = datetime.utcnow().isoformat() + 'Z'
    # check existing vote
    cur = db.execute('SELECT id, vote FROM votes WHERE entry_id=? AND identifier=? AND identifier_type=?', (entry_id, ident, id_type))
    existing = cur.fetchone()
    if existing:
        if existing['vote'] == vote:
            return jsonify({'message':'Already voted','vote':vote}), 200
        # update
        db.execute('UPDATE votes SET vote=?, ts=? WHERE id=?', (vote, ts, existing['id']))
    else:
        db.execute('INSERT INTO votes (entry_id, identifier, identifier_type, vote, ts) VALUES (?,?,?,?,?)', (entry_id, ident, id_type, vote, ts))
    db.commit()

    # compute counts
    cur = db.execute('SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) as upvotes, SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) as downvotes FROM votes WHERE entry_id=?', (entry_id,))
    counts = cur.fetchone()
    up = counts['upvotes'] or 0
    down = counts['downvotes'] or 0
    return jsonify({'message':'ok','upvotes':up,'downvotes':down})


@app.route('/api/report', methods=['POST'])
def api_report():
    init_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message':'Invalid JSON'}), 400
    entry_id = int(data.get('entry_id') or 0)
    reason = sanitize(data.get('reason',''))
    db = get_db()
    cur = db.execute('SELECT id, content, tags, ts, archived FROM entries WHERE id=?', (entry_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({'message':'Entry not found'}), 404
    if row['archived']:
        return jsonify({'message':'Entry already archived'}), 200

    id_type, ident = get_identifier()
    # prevent duplicate reports from same identifier
    cur = db.execute('SELECT id FROM reports WHERE entry_id=? AND identifier=? AND identifier_type=?', (entry_id, ident, id_type))
    if cur.fetchone():
        return jsonify({'message':'Already reported'}), 200

    ts = datetime.utcnow().isoformat() + 'Z'
    db.execute('INSERT INTO reports (entry_id, identifier, identifier_type, reason, ts) VALUES (?,?,?,?,?)', (entry_id, ident, id_type, reason, ts))
    db.commit()

    # compute counts
    cur = db.execute('SELECT COUNT(*) as cnt FROM reports WHERE entry_id=?', (entry_id,))
    reports_cnt = cur.fetchone()['cnt'] or 0
    cur = db.execute('SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) as upvotes FROM votes WHERE entry_id=?', (entry_id,))
    up = (cur.fetchone()['upvotes'] or 0)

    # If more than 25% of the upvotes reported the post -> archive
    archived = False
    try:
        if up > 0 and (reports_cnt / up) > 0.25:
            # archive entry: mark archived and write to archive dir outside static folder
            db.execute('UPDATE entries SET archived=1 WHERE id=?', (entry_id,))
            db.commit()
            archived = True
            # write archive file outside static folder
            parent = os.path.dirname(BASE_DIR)
            archive_dir = os.path.join(parent, 'archive')
            os.makedirs(archive_dir, exist_ok=True)
            archive_path = os.path.join(archive_dir, f'entry-{entry_id}.json')
            entry_obj = {'id': entry_id, 'content': row['content'], 'tags': row['tags'], 'ts': row['ts'], 'archived_at': datetime.utcnow().isoformat() + 'Z', 'reports': reports_cnt, 'upvotes': up}
            try:
                import json
                with open(archive_path, 'w', encoding='utf-8') as f:
                    json.dump(entry_obj, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            # write a log entry
            log_dir = os.path.join(parent, 'archive_logs')
            os.makedirs(log_dir, exist_ok=True)
            try:
                with open(os.path.join(log_dir, 'archive.log'), 'a', encoding='utf-8') as lf:
                    lf.write(f"{datetime.utcnow().isoformat()}Z ARCHIVE entry {entry_id} reports={reports_cnt} upvotes={up}\n")
            except Exception:
                pass

    except Exception:
        pass

    return jsonify({'message':'ok','reports':reports_cnt,'archived':archived})

if __name__ == '__main__':
    # Create DB file if missing
    if not os.path.exists(DB_PATH):
        open(DB_PATH, 'a').close()
    # If you have cert.pem and key.pem in the project root, Flask will use them
    cert = os.path.join(BASE_DIR, 'cert.pem')
    key = os.path.join(BASE_DIR, 'key.pem')
    ssl_context = None
    if os.path.exists(cert) and os.path.exists(key):
        ssl_context = (cert, key)
        print('Using SSL cert and key for HTTPS')
    else:
        print('No cert/key found — starting without HTTPS')
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=ssl_context)
