"""
Anonymous Diary Application Backend

A Flask-based REST API for an anonymous diary with voting, comments,
file uploads, and admin panel features.
"""

from flask import Flask, request, jsonify, send_from_directory, g
import sqlite3
import os
import re
import datetime
from werkzeug.utils import secure_filename
import uuid
import hashlib
import secrets
import json


BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'data.db')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
ADMIN_PASSKEY = os.environ.get('ADMIN_PASSKEY', 'admin123')
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
RECYCLE_BIN_RETENTION_DAYS = 7

os.makedirs(UPLOADS_DIR, exist_ok=True)


ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm'}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')

# Database helpers
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database schema with all required tables and columns."""
    db = get_db()
    
    # Create entries table with all columns
    db.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_id TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            images TEXT,
            video TEXT,
            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            ts TEXT NOT NULL,
            archived INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            is_pinned INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            manipulated INTEGER DEFAULT 0,
            manipulated_at TEXT,
            browser_info TEXT
        )
    ''')
    
    # Ensure columns exist for older databases
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info('entries')").fetchall()]
        if 'archived' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN archived INTEGER DEFAULT 0')
        if 'images' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN images TEXT')
        if 'video' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN video TEXT')
        if 'upvotes' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN upvotes INTEGER DEFAULT 0')
        if 'downvotes' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN downvotes INTEGER DEFAULT 0')
        if 'deleted' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN deleted INTEGER DEFAULT 0')
        if 'unique_id' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN unique_id TEXT')
        if 'deleted_at' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN deleted_at TEXT')
        if 'is_pinned' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN is_pinned INTEGER DEFAULT 0')
        if 'view_count' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN view_count INTEGER DEFAULT 0')
        if 'manipulated' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN manipulated INTEGER DEFAULT 0')
        if 'manipulated_at' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN manipulated_at TEXT')
        if 'browser_info' not in cols:
            db.execute('ALTER TABLE entries ADD COLUMN browser_info TEXT')
    except Exception as e:
        print(f"Migration error: {e}")
    db.commit()
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
    # comments table
    db.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            identifier TEXT NOT NULL,
            identifier_type TEXT NOT NULL,
            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            ts TEXT NOT NULL
        )
    ''')
    # Ensure upvotes, downvotes, deleted columns exist for older DBs
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info('comments')").fetchall()]
        if 'upvotes' not in cols:
            db.execute('ALTER TABLE comments ADD COLUMN upvotes INTEGER DEFAULT 0')
        if 'downvotes' not in cols:
            db.execute('ALTER TABLE comments ADD COLUMN downvotes INTEGER DEFAULT 0')
        if 'deleted' not in cols:
            db.execute('ALTER TABLE comments ADD COLUMN deleted INTEGER DEFAULT 0')
    except:
        pass
    
    db.commit()
    
    # Create comment votes table
    db.execute('''
        CREATE TABLE IF NOT EXISTS comment_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            identifier_type TEXT NOT NULL,
            vote INTEGER NOT NULL,
            ts TEXT NOT NULL
        )
    ''')
    # Create comment reports table
    db.execute('''
        CREATE TABLE IF NOT EXISTS comment_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL,
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
# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Regex patterns for sanitization
SCRIPT_RE = re.compile(r'<script[\s\S]*?>[\s\S]*?<\/script>', re.IGNORECASE)
ONHANDLER_RE = re.compile(r'on\w+=\"?[^\"\s>]+\"?', re.IGNORECASE)


def sanitize(text):
    """Remove potentially dangerous scripts and event handlers from text."""
    if not text:
        return ''
    text = SCRIPT_RE.sub('', text)
    text = ONHANDLER_RE.sub('', text)
    return text.strip()


def allowed_file(filename, file_type):
    """Check if file extension is allowed for given file type."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if file_type == 'image':
        return ext in ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'video':
        return ext in ALLOWED_VIDEO_EXTENSIONS
    return False

def save_uploaded_file(file, file_type):
    """Save an uploaded file and return the filename, or None if invalid"""
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename, file_type):
        return None
    
    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if file_type == 'image' and size > MAX_IMAGE_SIZE:
        return None
    if file_type == 'video' and size > MAX_VIDEO_SIZE:
        return None
    
    # Generate unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    
    try:
        file.save(filepath)
        return filename
    except Exception:
        return None


def get_identifier():
    """Get unique identifier for user (cookie-based or IP-based)."""
    cookie_id = request.cookies.get('user_id')
    if cookie_id:
        return ('cookie', cookie_id)
    
    # Get IP address, preferring X-Forwarded-For header (for proxies)
    xf = request.headers.get('X-Forwarded-For', '')
    if xf:
        ip = xf.split(',')[0].strip()
    else:
        ip = request.remote_addr or '0.0.0.0'
    return ('ip', ip)


def get_browser_info():
    """Collect browser/device information from request headers."""
    browser_info = {
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'ip': request.remote_addr or '0.0.0.0',
        'timestamp': datetime.datetime.now(datetime.UTC).isoformat()
    }
    return json.dumps(browser_info)


def cleanup_deleted_entries():
    """Remove entries from recycle bin older than retention period."""
    db = get_db()
    cutoff_date = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=RECYCLE_BIN_RETENTION_DAYS)).isoformat()
    db.execute(
        'DELETE FROM entries WHERE deleted=1 AND deleted_at < ?',
        (cutoff_date,)
    )
    db.commit()

# ============================================================================
# STATIC FILE ROUTES
# ============================================================================

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# Route to serve uploaded files
@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded files securely"""
    filename = secure_filename(filename)
    if not os.path.exists(os.path.join(UPLOADS_DIR, filename)):
        return jsonify({'message':'File not found'}), 404
    return send_from_directory(UPLOADS_DIR, filename)

# ============================================================================
# ENTRY API ROUTES
# ============================================================================

@app.route('/api/submit', methods=['POST'])
def api_submit():
    init_db()
    
    # Get content and tags from form data
    content = request.form.get('content', '').strip()
    tags = request.form.get('tags', '').strip()
    
    if not content:
        return jsonify({'message':'Contenido vacío'}), 400
    if len(content) > 2000:
        return jsonify({'message':'Contenido demasiado largo'}), 400
    
    content = sanitize(content)
    
    # Handle image uploads (max 3)
    images = []
    image_files = request.files.getlist('images')
    for img_file in image_files[:3]:  # limit to 3 images
        if img_file and img_file.filename:
            filename = save_uploaded_file(img_file, 'image')
            if filename:
                images.append(filename)
    
    # Handle video upload (max 1)
    video = None
    video_file = request.files.get('video')
    if video_file and video_file.filename:
        video = save_uploaded_file(video_file, 'video')
    
    ts = datetime.datetime.now(datetime.UTC).isoformat() + 'Z'
    db = get_db()
    
    # Generate unique identifier and collect browser info
    unique_entry_id = str(uuid.uuid4())
    browser_info = get_browser_info()
    
    # Store images as comma-separated string
    images_str = ','.join(images) if images else None
    
    cur = db.execute(
        '''INSERT INTO entries 
           (unique_id, content, tags, images, video, ts, browser_info, is_pinned) 
           VALUES (?,?,?,?,?,?,?,?)''',
        (unique_entry_id, content, tags, images_str, video, ts, browser_info, 0)
    )
    db.commit()
    entry_id = cur.lastrowid
    return jsonify({'message':'ok', 'id': entry_id, 'unique_id': unique_entry_id}), 201

@app.route('/api/entries', methods=['GET'])
def api_entries():
    """Get list of entries, ordered by pinned status and creation date."""
    init_db()
    cleanup_deleted_entries()  # Clean up old deleted entries
    
    limit = min(100, int(request.args.get('limit', '20') or '20'))
    db = get_db()
    
    cur = db.execute('''
        SELECT e.id, e.unique_id, e.content, e.tags, e.images, e.video, e.ts,
               e.is_pinned,
                             e.view_count,
                             e.manipulated,
          IFNULL((SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as upvotes,
          IFNULL((SELECT SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as downvotes,
          IFNULL((SELECT COUNT(*) FROM reports r WHERE r.entry_id=e.id),0) as reports
        FROM entries e
        WHERE e.archived=0 AND e.deleted=0
        ORDER BY e.is_pinned DESC, e.id DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cur.fetchall()
    entries = []
    for r in rows:
        # Parse images from comma-separated string
        images = r['images'].split(',') if r['images'] else []
        entry_obj = {
            'id': r['id'],
            'unique_id': r['unique_id'],
            'content': r['content'],
            'tags': r['tags'],
            'images': images,
            'video': r['video'],
            'ts': r['ts'],
            'is_pinned': r['is_pinned'],
            'view_count': r['view_count'],
            'manipulated': r['manipulated'],
            'upvotes': r['upvotes'],
            'downvotes': r['downvotes'],
            'reports': r['reports']
        }
        entries.append(entry_obj)
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
    ts = datetime.now(datetime.UTC).isoformat() + 'Z'
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

    ts = datetime.now(datetime.UTC).isoformat() + 'Z'
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
            entry_obj = {'id': entry_id, 'content': row['content'], 'tags': row['tags'], 'ts': row['ts'], 'archived_at': datetime.now(datetime.UTC).isoformat() + 'Z', 'reports': reports_cnt, 'upvotes': up}
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
                    lf.write(f"{datetime.now(datetime.UTC).isoformat()}Z ARCHIVE entry {entry_id} reports={reports_cnt} upvotes={up}\n")
            except Exception:
                pass

    except Exception:
        pass

    return jsonify({'message':'ok','reports':reports_cnt,'archived':archived})


# Comments endpoints
@app.route('/api/comments/<int:entry_id>', methods=['GET'])
def api_get_comments(entry_id):
    init_db()
    db = get_db()
    
    # Get entry
    cur = db.execute('SELECT id FROM entries WHERE id=?', (entry_id,))
    if not cur.fetchone():
        return jsonify({'message':'Entry not found'}), 404
    
    # Get comments
    cur = db.execute('''
        SELECT c.id, c.content, c.ts,
            IFNULL((SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) FROM comment_votes cv WHERE cv.comment_id=c.id),0) as upvotes,
            IFNULL((SELECT SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM comment_votes cv WHERE cv.comment_id=c.id),0) as downvotes
        FROM comments c
        WHERE c.entry_id=?
        ORDER BY c.id DESC
        LIMIT 100
    ''', (entry_id,))
    rows = cur.fetchall()
    comments = []
    for r in rows:
        comments.append({
            'id': r['id'],
            'content': r['content'],
            'ts': r['ts'],
            'upvotes': r['upvotes'],
            'downvotes': r['downvotes']
        })
    return jsonify({'comments': comments})


@app.route('/api/comments', methods=['POST'])
def api_post_comment():
    init_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message':'Invalid JSON'}), 400

    entry_id = int(data.get('entry_id') or 0)
    content = sanitize(data.get('content',''))

    if not content:
        return jsonify({'message':'Comentario vacío'}), 400
    if len(content) > 500:
        return jsonify({'message':'Comentario demasiado largo (máx 500 caracteres)'}), 400

    db = get_db()
    cur = db.execute('SELECT id, archived, deleted FROM entries WHERE id=?', (entry_id,))
    entry = cur.fetchone()
    if not entry:
        return jsonify({'message':'Entry not found'}), 404
    if entry['archived']:
        return jsonify({'message':'Cannot comment on archived entry'}), 410
    if entry['deleted']:
        return jsonify({'message':'Cannot comment on deleted entry'}), 410

    id_type, ident = get_identifier()
    ts = datetime.now(datetime.UTC).isoformat() + 'Z'

    # Insert comment (use default values for upvotes/downvotes/deleted)
    cur = db.execute(
        'INSERT INTO comments (entry_id, content, identifier, identifier_type, ts) VALUES (?,?,?,?,?)',
        (entry_id, content, ident, id_type, ts)
    )
    db.commit()
    comment_id = cur.lastrowid

    return jsonify({'message':'ok','id': comment_id, 'content': content, 'ts': ts}), 201
@app.route('/api/comment-vote', methods=['POST'])
def api_comment_vote():
    init_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message':'Invalid JSON'}), 400

    comment_id = int(data.get('comment_id') or 0)
    vote = int(data.get('vote') or 0)

    if vote not in (1, -1):
        return jsonify({'message':'Invalid vote'}), 400

    db = get_db()
    cur = db.execute('SELECT id FROM comments WHERE id=?', (comment_id,))
    if not cur.fetchone():
        return jsonify({'message':'Comment not found'}), 404

    id_type, ident = get_identifier()
    ts = datetime.now(datetime.UTC).isoformat() + 'Z'

    # Check existing vote
    cur = db.execute(
        'SELECT id, vote FROM comment_votes WHERE comment_id=? AND identifier=? AND identifier_type=?',
        (comment_id, ident, id_type)
    )
    existing = cur.fetchone()

    if existing:
        if existing['vote'] == vote:
            return jsonify({'message':'Already voted','vote':vote}), 200
        db.execute('UPDATE comment_votes SET vote=?, ts=? WHERE id=?', (vote, ts, existing['id']))
    else:
        db.execute(
            'INSERT INTO comment_votes (comment_id, identifier, identifier_type, vote, ts) VALUES (?,?,?,?,?)',
            (comment_id, ident, id_type, vote, ts)
        )
    db.commit()

    # Get vote counts
    cur = db.execute('''
        SELECT 
            IFNULL(SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END),0) as upvotes,
            IFNULL(SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END),0) as downvotes
        FROM comment_votes WHERE comment_id=?
    ''', (comment_id,))
    counts = cur.fetchone()

    return jsonify({
        'message':'ok',
        'upvotes':counts['upvotes'],
        'downvotes':counts['downvotes']
    })


@app.route('/api/comment-report', methods=['POST'])
def api_comment_report():
    init_db()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message':'Invalid JSON'}), 400
    
    comment_id = int(data.get('comment_id') or 0)
    entry_id = int(data.get('entry_id') or 0)
    reason = sanitize(data.get('reason',''))
    
    db = get_db()
    cur = db.execute('SELECT id, entry_id FROM comments WHERE id=?', (comment_id,))
    comment = cur.fetchone()
    if not comment:
        return jsonify({'message':'Comment not found'}), 404
    
    id_type, ident = get_identifier()
    
    # Check if already reported
    cur = db.execute(
        'SELECT id FROM comment_reports WHERE comment_id=? AND identifier=? AND identifier_type=?',
        (comment_id, ident, id_type)
    )
    if cur.fetchone():
        return jsonify({'message':'Already reported'}), 200
    
    ts = datetime.now(datetime.UTC).isoformat() + 'Z'
    db.execute(
        'INSERT INTO comment_reports (comment_id, identifier, identifier_type, reason, ts) VALUES (?,?,?,?,?)',
        (comment_id, ident, id_type, reason, ts)
    )
    db.commit()
    
    # Get report count and upvotes
    cur = db.execute('SELECT COUNT(*) as cnt FROM comment_reports WHERE comment_id=?', (comment_id,))
    reports_cnt = cur.fetchone()['cnt'] or 0
    
    cur = db.execute(
        'SELECT IFNULL(SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END),0) as upvotes FROM comment_votes WHERE comment_id=?',
        (comment_id,)
    )
    upvotes = cur.fetchone()['upvotes'] or 0
    
    # Delete if more than 10% of upvotes reported it
    deleted = False
    if upvotes > 0 and (reports_cnt / upvotes) > 0.1:
        db.execute('DELETE FROM comments WHERE id=?', (comment_id,))
        db.commit()
        deleted = True
    
    return jsonify({'message':'ok','reports':reports_cnt,'deleted':deleted})

# Admin endpoints
admin_tokens = {}  # Simple in-memory token store (use Redis in production)

@app.route('/api/admin/verify-passkey', methods=['POST'])
def verify_passkey():
    data = request.get_json() or {}
    passkey = data.get('passkey', '')
    
    if passkey != ADMIN_PASSKEY:
        return jsonify({'message': 'Contraseña incorrecta'}), 401
    
    # Generate a token
    token = secrets.token_urlsafe(32)
    admin_tokens[token] = datetime.datetime.now().isoformat()
    
    return jsonify({'token': token})

def verify_admin_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    
    token = auth[7:]
    if token in admin_tokens:
        return token
    return None

@app.route('/api/admin/data')
def admin_data():
    if not verify_admin_token():
        return jsonify({'message': 'Unauthorized'}), 401
    
    init_db()
    db = get_db()
    
    # Stats
    entries = db.execute('SELECT COUNT(*) as cnt FROM entries WHERE archived=0 AND deleted=0').fetchone()['cnt']
    archived = db.execute('SELECT COUNT(*) as cnt FROM entries WHERE archived=1 AND deleted=0').fetchone()['cnt']
    deleted_entries = db.execute('SELECT COUNT(*) as cnt FROM entries WHERE deleted=1').fetchone()['cnt']
    comments = db.execute('SELECT COUNT(*) as cnt FROM comments WHERE deleted=0').fetchone()['cnt']
    deleted_comments = db.execute('SELECT COUNT(*) as cnt FROM comments WHERE deleted=1').fetchone()['cnt']
    
    # All entries (not deleted)
    entries_list = db.execute('''
        SELECT e.id, e.content,
               e.is_pinned, e.view_count, e.manipulated,
               IFNULL((SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as upvotes,
               IFNULL((SELECT SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as downvotes,
               (SELECT COUNT(*) FROM reports WHERE entry_id=e.id) as reports
        FROM entries e
        WHERE e.deleted=0
        ORDER BY e.id DESC
    ''').fetchall()
    
    # Deleted entries (for recycle bin)
    deleted_entries_list = db.execute('''
        SELECT e.id, e.content,
               e.is_pinned, e.view_count, e.manipulated,
               IFNULL((SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as upvotes,
               IFNULL((SELECT SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM votes v WHERE v.entry_id=e.id),0) as downvotes,
               (SELECT COUNT(*) FROM reports WHERE entry_id=e.id) as reports
        FROM entries e
        WHERE e.deleted=1
        ORDER BY e.id DESC
    ''').fetchall()
    
    # All comments - calculate votes from comment_votes table
    comments_list = db.execute('''
        SELECT c.id, c.entry_id, c.content,
               IFNULL((SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) FROM comment_votes cv WHERE cv.comment_id=c.id),0) as upvotes,
               IFNULL((SELECT SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM comment_votes cv WHERE cv.comment_id=c.id),0) as downvotes,
               (SELECT COUNT(*) FROM comment_reports WHERE comment_id=c.id) as reports
        FROM comments c
        WHERE c.deleted=0
        ORDER BY c.id DESC
    ''').fetchall()
    
    # Reports
    entry_reports = db.execute('''
        SELECT 'entry' as type, entry_id as target_id, 
               (SELECT upvotes FROM entries WHERE id=entry_id) as upvotes,
               (SELECT COUNT(*) FROM reports WHERE entry_id=entry_id) as report_count,
               reason
        FROM reports
        GROUP BY entry_id
        HAVING report_count > 2
    ''').fetchall()
    
    comment_reports = db.execute('''
        SELECT 'comment' as type, comment_id as target_id,
               IFNULL((SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) FROM comment_votes WHERE comment_id=comment_id),0) as upvotes,
               (SELECT COUNT(*) FROM comment_reports WHERE comment_id=comment_id) as report_count,
               reason
        FROM comment_reports
        GROUP BY comment_id
        HAVING report_count > 1
    ''').fetchall()
    
    reports = list(entry_reports) + list(comment_reports)
    
    return jsonify({
        'stats': {
            'total_entries': entries,
            'archived_entries': archived,
            'deleted_entries': deleted_entries,
            'total_comments': comments,
            'deleted_comments': deleted_comments
        },
        'entries': [dict(e) for e in entries_list],
        'deleted_entries': [dict(e) for e in deleted_entries_list],
        'comments': [dict(c) for c in comments_list],
        'reports': [dict(r) for r in reports]
    })

@app.route('/api/admin/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry_admin(entry_id):
    """Move entry to recycle bin (soft delete)."""
    if not verify_admin_token():
        return jsonify({'message': 'Unauthorized'}), 401
    
    db = get_db()
    now = datetime.datetime.now(datetime.UTC).isoformat()
    db.execute('UPDATE entries SET deleted=1, deleted_at=? WHERE id=?', (now, entry_id))
    db.commit()
    
    return jsonify({'message': 'Entry moved to recycle bin'})

@app.route('/api/admin/entries/<int:entry_id>/restore', methods=['POST'])
def restore_entry_admin(entry_id):
    if not verify_admin_token():
        return jsonify({'message': 'Unauthorized'}), 401
    
    db = get_db()
    db.execute('UPDATE entries SET deleted=0 WHERE id=?', (entry_id,))
    db.commit()
    
    return jsonify({'message': 'Entry restored'})

@app.route('/api/admin/entries/<int:entry_id>/permanent', methods=['DELETE'])
def permanently_delete_entry(entry_id):
    if not verify_admin_token():
        return jsonify({'message': 'Unauthorized'}), 401
    
    db = get_db()
    db.execute('DELETE FROM entries WHERE id=?', (entry_id,))
    db.execute('DELETE FROM comments WHERE entry_id=?', (entry_id,))
    db.commit()
    
    return jsonify({'message': 'Entry permanently deleted'})


@app.route('/api/admin/entries/<int:entry_id>/pin', methods=['POST'])
def pin_entry(entry_id):
    """Pin or unpin an entry (toggle)."""
    if not verify_admin_token():
        return jsonify({'message': 'Unauthorized'}), 401
    
    db = get_db()
    
    # Get current pinned status
    row = db.execute('SELECT is_pinned FROM entries WHERE id=?', (entry_id,)).fetchone()
    if not row:
        return jsonify({'message': 'Entry not found'}), 404
    
    new_status = 1 - row['is_pinned']  # Toggle
    db.execute('UPDATE entries SET is_pinned=? WHERE id=?', (new_status, entry_id))
    db.commit()
    
    action = 'pinned' if new_status else 'unpinned'
    return jsonify({'message': f'Entry {action}', 'is_pinned': new_status})


@app.route('/api/admin/entries/<int:entry_id>/adjust-votes', methods=['POST'])
def adjust_entry_votes(entry_id):
    """Adjust upvotes and downvotes for an entry."""
    if not verify_admin_token():
        return jsonify({'message': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    upvote_change = int(data.get('upvote_change', 0))
    downvote_change = int(data.get('downvote_change', 0))
    
    db = get_db()
    
    # Get current votes
    row = db.execute(
        'SELECT upvotes, downvotes FROM entries WHERE id=?',
        (entry_id,)
    ).fetchone()
    
    if not row:
        return jsonify({'message': 'Entry not found'}), 404
    
    # Calculate new votes (cannot go below 0)
    new_upvotes = max(0, row['upvotes'] + upvote_change)
    new_downvotes = max(0, row['downvotes'] + downvote_change)
    
    # Mark as manipulated and store timestamp
    now = datetime.datetime.now(datetime.UTC).isoformat()
    db.execute(
        'UPDATE entries SET upvotes=?, downvotes=?, manipulated=1, manipulated_at=? WHERE id=?',
        (new_upvotes, new_downvotes, now, entry_id)
    )
    db.commit()
    
    return jsonify({
        'message': 'Votes adjusted',
        'upvotes': new_upvotes,
        'downvotes': new_downvotes
    })


@app.route('/api/admin/entries/<int:entry_id>/browser-info', methods=['GET'])
def get_entry_browser_info(entry_id):
    """Get browser information for an entry (admin only)."""
    if not verify_admin_token():
        return jsonify({'message': 'Unauthorized'}), 401
    
    db = get_db()
    row = db.execute(
        'SELECT browser_info FROM entries WHERE id=?',
        (entry_id,)
    ).fetchone()
    
    if not row:
        return jsonify({'message': 'Entry not found'}), 404
    
    browser_info = {}
    if row['browser_info']:
        try:
            browser_info = json.loads(row['browser_info'])
        except:
            pass
    
    return jsonify({'browser_info': browser_info})


@app.route('/api/entries/<int:entry_id>/view', methods=['POST'])
def increment_entry_view(entry_id):
    """Increment view_count for an entry. Public endpoint called when an entry is viewed."""
    init_db()
    db = get_db()
    row = db.execute('SELECT id FROM entries WHERE id=? AND deleted=0', (entry_id,)).fetchone()
    if not row:
        return jsonify({'message':'Entry not found'}), 404
    db.execute('UPDATE entries SET view_count = IFNULL(view_count,0) + 1 WHERE id=?', (entry_id,))
    db.commit()
    return jsonify({'message':'view incremented'})


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
