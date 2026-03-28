from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from functools import wraps
import os, jwt, uuid, requests
from datetime import datetime
from flask_cors import CORS


app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_fallback_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///posts.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')

db = SQLAlchemy(app)

USER_SERVICE_URL = os.environ.get('USER_SERVICE_URL', 'http://user-service:5000')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ───────────────────────────── MODELS ─────────────────────────────

post_files = db.Table('post_files',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('file_id', db.Integer, db.ForeignKey('file.id'), primary_key=True)
)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    files = db.relationship('File', secondary=post_files, backref='posts', cascade='all')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    mimetype = db.Column(db.String(50))

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id'),)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ───────────────────────────── HELPERS ─────────────────────────────

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi', 'webp'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        if not token:
            return jsonify({'message': 'Token missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = data['id']
        except Exception as e:
            return jsonify({'message': 'Token invalid', 'error': str(e)}), 401
        return f(user_id, *args, **kwargs)
    return decorated

def get_token():
    parts = request.headers.get('Authorization', '').split()
    return parts[1] if len(parts) == 2 else None

def get_blocked_ids(user_id, token):
    """Fetch list of user IDs blocked by or blocking the current user."""
    try:
        resp = requests.get(
            f'{USER_SERVICE_URL}/blocked-ids',
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        if resp.status_code == 200:
            return set(resp.json().get('blocked_ids', []))
    except Exception:
        pass
    return set()

def can_view_posts_of(viewer_id, author_id, token):
    """
    Returns True if viewer_id is allowed to see author_id's posts.
    Calls user-service /profile endpoint which returns full data
    for public profiles or profiles the viewer follows.
    """
    if viewer_id == author_id:
        return True
    try:
        resp = requests.get(
            f'{USER_SERVICE_URL}/profile/{author_id}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        if resp.status_code == 404:
            # Blocked or not found
            return False
        if resp.status_code == 200:
            data = resp.json()
            # Profile returned full data → viewer can see posts
            # (user-service only returns followers list if viewer is allowed)
            is_private = data.get('is_private', False)
            is_following = data.get('is_following', False)
            return (not is_private) or is_following
    except Exception:
        pass
    return False

def serialize_post(post, blocked_ids, full_comments=False, viewer_id=None):
    visible_likes = [l for l in post.likes if l.user_id not in blocked_ids]
    visible_comments = [c for c in post.comments if c.user_id not in blocked_ids]
    result = {
        'id': post.id,
        'author_id': post.author_id,
        'description': post.description,
        'timestamp': post.timestamp.isoformat(),
        'files': [{'id': f.id, 'filename': f.filename, 'mimetype': f.mimetype} for f in post.files],
        'likes_count': len(visible_likes),
        'comments_count': len(visible_comments),
        'liked_by_me': any(l.user_id == viewer_id for l in visible_likes) if viewer_id else False,
    }
    if full_comments:
        result['comments'] = [
            {'id': c.id, 'user_id': c.user_id, 'text': c.text, 'timestamp': c.timestamp.isoformat()}
            for c in visible_comments
        ]
    return result

# ───────────────────────────── POSTS CRUD ─────────────────────────────

@app.route('/posts', methods=['POST'])
@token_required
def create_post(user_id):
    description = request.form.get('description', '')
    files = request.files.getlist('files')

    if not files or all(f.filename == '' for f in files):
        return jsonify({'message': 'At least one file is required'}), 400
    if len(files) > 20:
        return jsonify({'message': 'Max 20 files per post'}), 400

    post = Post(author_id=user_id, description=description)

    for f in files:
        if not f or not allowed_file(f.filename):
            return jsonify({'message': f'Invalid file type: {f.filename}'}), 400

        # Check individual file size
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify({'message': f'File {f.filename} exceeds 50MB limit'}), 400

        filename = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(filepath)
        file_entry = File(filename=filename, mimetype=f.mimetype)
        db.session.add(file_entry)
        post.files.append(file_entry)

    db.session.add(post)
    db.session.commit()
    return jsonify({'message': 'Post created', 'post_id': post.id}), 201

@app.route('/posts/<int:post_id>', methods=['GET'])
@token_required
def get_post(user_id, post_id):
    token = get_token()
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404

    if not can_view_posts_of(user_id, post.author_id, token):
        return jsonify({'message': 'Cannot view this post'}), 403

    blocked_ids = get_blocked_ids(user_id, token)
    return jsonify(serialize_post(post, blocked_ids, full_comments=True, viewer_id=user_id))

@app.route('/posts/<int:post_id>', methods=['PUT'])
@token_required
def update_post(user_id, post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404
    if post.author_id != user_id:
        return jsonify({'message': 'Not allowed'}), 403

    data = request.json or {}
    description = data.get('description')
    if description is None:
        return jsonify({'message': 'No description provided'}), 400
    post.description = description
    db.session.commit()
    return jsonify({'message': 'Description updated'})

@app.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post(user_id, post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404
    if post.author_id != user_id:
        return jsonify({'message': 'Not allowed'}), 403
    for f in post.files:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f.filename))
        except OSError:
            pass
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'})

@app.route('/posts/<int:post_id>/files/<int:file_id>', methods=['DELETE'])
@token_required
def delete_file(user_id, post_id, file_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404
    if post.author_id != user_id:
        return jsonify({'message': 'Not allowed'}), 403
    file = File.query.get(file_id)
    if not file or file not in post.files:
        return jsonify({'message': 'File not found in post'}), 404
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    except OSError:
        pass
    post.files.remove(file)
    db.session.delete(file)
    db.session.commit()
    return jsonify({'message': 'File removed'})

# ───────────────────────────── LIKES ─────────────────────────────

@app.route('/posts/<int:post_id>/like', methods=['POST'])
@token_required
def like_post(user_id, post_id):
    token = get_token()
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404

    if not can_view_posts_of(user_id, post.author_id, token):
        return jsonify({'message': 'Cannot like this post'}), 403

    like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'message': 'Like removed'})

    new_like = Like(user_id=user_id, post_id=post_id)
    db.session.add(new_like)
    db.session.commit()
    return jsonify({'message': 'Post liked'})

# ───────────────────────────── COMMENTS ─────────────────────────────

@app.route('/posts/<int:post_id>/comment', methods=['POST'])
@token_required
def add_comment(user_id, post_id):
    token = get_token()
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404

    if not can_view_posts_of(user_id, post.author_id, token):
        return jsonify({'message': 'Cannot comment on this post'}), 403

    data = request.json or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'message': 'Comment text is required'}), 400

    comment = Comment(user_id=user_id, post_id=post_id, text=text)
    db.session.add(comment)
    db.session.commit()
    return jsonify({'message': 'Comment added', 'comment_id': comment.id}), 201

@app.route('/comments/<int:comment_id>', methods=['PUT'])
@token_required
def edit_comment(user_id, comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'message': 'Comment not found'}), 404
    if comment.user_id != user_id:
        return jsonify({'message': 'Not allowed'}), 403

    data = request.json or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'message': 'Comment text is required'}), 400
    comment.text = text
    db.session.commit()
    return jsonify({'message': 'Comment updated'})

@app.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(user_id, comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'message': 'Comment not found'}), 404
    if comment.user_id != user_id:
        return jsonify({'message': 'Not allowed'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': 'Comment deleted'})

# ───────────────────────────── USER POSTS (used by feed-service) ─────────────────────────────

@app.route('/user_posts/<int:author_id>', methods=['GET'])
@token_required
def user_posts(user_id, author_id):
    token = get_token()

    if not can_view_posts_of(user_id, author_id, token):
        return jsonify({'posts': []})

    blocked_ids = get_blocked_ids(user_id, token)
    posts = Post.query.filter_by(author_id=author_id).order_by(Post.timestamp.desc()).all()
    return jsonify({'posts': [serialize_post(p, blocked_ids, viewer_id=user_id) for p in posts]})

# ───────────────────────────── STATIC FILES ─────────────────────────────

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)