from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import jwt, datetime, os, uuid
from flask_cors import CORS

from flask import send_from_directory



app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_fallback_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB for profile pics

db = SQLAlchemy(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ───────────────────────────── MODELS ─────────────────────────────

followers_table = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

blocked_table = db.Table('blocked',
    db.Column('blocker_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('blocked_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.String(250))
    profile_picture = db.Column(db.String(300))
    is_private = db.Column(db.Boolean, default=False)

    followers = db.relationship(
        'User', secondary=followers_table,
        primaryjoin=id == followers_table.c.followed_id,
        secondaryjoin=id == followers_table.c.follower_id,
        backref='following'
    )
    blocked_users = db.relationship(
        'User', secondary=blocked_table,
        primaryjoin=id == blocked_table.c.blocker_id,
        secondaryjoin=id == blocked_table.c.blocked_id,
        backref='blocked_by'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class FollowRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending / accepted / rejected
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

with app.app_context():
    db.create_all()

# ───────────────────────────── HELPERS ─────────────────────────────

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

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
            current_user = User.query.get(data['id'])
            if not current_user:
                return jsonify({'message': 'User not found'}), 401
        except Exception as e:
            return jsonify({'message': 'Token invalid', 'error': str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated

def is_blocked(user_a, user_b):
    """Returns True if either user has blocked the other."""
    return user_b in user_a.blocked_users or user_a in user_b.blocked_users

# ───────────────────────────── AUTH ─────────────────────────────

@app.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    for field in ('username', 'email', 'name', 'password'):
        if not data.get(field):
            return jsonify({'message': f'Missing field: {field}'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already taken'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400
    user = User(
        username=data['username'],
        email=data['email'],
        name=data['name'],
        bio=data.get('bio'),
        is_private=data.get('is_private', False)
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User created', 'id': user.id}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    login_val = data.get('login', '')
    password = data.get('password', '')
    user = User.query.filter(
        (User.username == login_val) | (User.email == login_val)
    ).first()
    if not user or not user.check_password(password):
        return jsonify({'message': 'Invalid credentials'}), 401
    token = jwt.encode(
        {'id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)},
        app.config['SECRET_KEY'], algorithm='HS256'
    )
    return jsonify({'token': token})

# ───────────────────────────── PROFILE ─────────────────────────────

@app.route('/profile/<int:user_id>', methods=['GET'])
@token_required
def get_profile(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Blocked check
    if is_blocked(current_user, user):
        return jsonify({'message': 'User not found'}), 404

    is_following = current_user in user.followers
    can_see_full = (not user.is_private) or is_following or (current_user.id == user_id)

    base = {
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'bio': user.bio,
        'profile_picture': user.profile_picture,
        'is_private': user.is_private,
        'followers_count': len(user.followers),
        'following_count': len(user.following),
        'is_following': is_following,
    }

    if can_see_full:
        base['followers'] = [u.id for u in user.followers]
        base['following'] = [u.id for u in user.following]

    return jsonify(base)

@app.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.form if request.files else request.json or {}

    if 'name' in data and data['name']:
        current_user.name = data['name']
    if 'bio' in data:
        current_user.bio = data['bio']
    if 'is_private' in data:
        val = data['is_private']
        current_user.is_private = val if isinstance(val, bool) else val.lower() == 'true'

    # Profile picture upload
    if 'profile_picture' in request.files:
        f = request.files['profile_picture']
        if f and allowed_image(f.filename):
            filename = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.profile_picture = filename
        else:
            return jsonify({'message': 'Invalid image format'}), 400

    db.session.commit()
    return jsonify({'message': 'Profile updated'})

# ───────────────────────────── FOLLOW ─────────────────────────────

@app.route('/follow/<int:user_id>', methods=['POST'])
@token_required
def follow(current_user, user_id):
    if current_user.id == user_id:
        return jsonify({'message': 'Cannot follow yourself'}), 400

    target = User.query.get(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if is_blocked(current_user, target):
        return jsonify({'message': 'User not found'}), 404

    if current_user in target.followers:
        return jsonify({'message': 'Already following'}), 400

    if target.is_private:
        # Check if request already exists
        existing = FollowRequest.query.filter_by(
            sender_id=current_user.id, receiver_id=target.id, status='pending'
        ).first()
        if existing:
            return jsonify({'message': 'Follow request already sent'}), 400
        req = FollowRequest(sender_id=current_user.id, receiver_id=target.id)
        db.session.add(req)
        db.session.commit()
        return jsonify({'message': 'Follow request sent'}), 200
    else:
        target.followers.append(current_user)
        db.session.commit()
        return jsonify({'message': 'Now following'}), 200

@app.route('/unfollow/<int:user_id>', methods=['POST'])
@token_required
def unfollow(current_user, user_id):
    target = User.query.get(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404
    if current_user not in target.followers:
        return jsonify({'message': 'Not following this user'}), 400
    target.followers.remove(current_user)
    db.session.commit()
    return jsonify({'message': 'Unfollowed'})

@app.route('/remove-follower/<int:user_id>', methods=['POST'])
@token_required
def remove_follower(current_user, user_id):
    """Remove someone from your followers list."""
    follower = User.query.get(user_id)
    if not follower:
        return jsonify({'message': 'User not found'}), 404
    if follower not in current_user.followers:
        return jsonify({'message': 'This user is not following you'}), 400
    current_user.followers.remove(follower)
    db.session.commit()
    return jsonify({'message': 'Follower removed'})

@app.route('/following/<int:user_id>', methods=['GET'])
@token_required
def get_following(current_user, user_id):
    """Returns list of user IDs that user_id is following. Used by feed-service."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'following': [u.id for u in user.following]})

# ───────────────────────────── FOLLOW REQUESTS ─────────────────────────────

@app.route('/follow-requests', methods=['GET'])
@token_required
def get_follow_requests(current_user):
    """Incoming pending follow requests for current user."""
    reqs = FollowRequest.query.filter_by(receiver_id=current_user.id, status='pending').all()
    return jsonify({'requests': [
        {'id': r.id, 'sender_id': r.sender_id, 'timestamp': r.timestamp.isoformat()}
        for r in reqs
    ]})

@app.route('/follow-requests/<int:req_id>/accept', methods=['POST'])
@token_required
def accept_follow_request(current_user, req_id):
    req = FollowRequest.query.get(req_id)
    if not req or req.receiver_id != current_user.id:
        return jsonify({'message': 'Request not found'}), 404
    if req.status != 'pending':
        return jsonify({'message': 'Request already handled'}), 400
    req.status = 'accepted'
    sender = User.query.get(req.sender_id)
    if sender:
        current_user.followers.append(sender)
    db.session.commit()
    return jsonify({'message': 'Follow request accepted'})

@app.route('/follow-requests/<int:req_id>/reject', methods=['POST'])
@token_required
def reject_follow_request(current_user, req_id):
    req = FollowRequest.query.get(req_id)
    if not req or req.receiver_id != current_user.id:
        return jsonify({'message': 'Request not found'}), 404
    if req.status != 'pending':
        return jsonify({'message': 'Request already handled'}), 400
    req.status = 'rejected'
    db.session.commit()
    return jsonify({'message': 'Follow request rejected'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)