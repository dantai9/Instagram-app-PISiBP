from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from functools import wraps
import os, jwt, requests
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajni_kljuc'  # isti ključ kao u User servisu
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB po fajlu

db = SQLAlchemy(app)
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# MODELI
post_files = db.Table('post_files',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
    db.Column('file_id', db.Integer, db.ForeignKey('file.id'))
)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    files = db.relationship('File', secondary=post_files, backref='posts')
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    mimetype = db.Column(db.String(50))

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    text = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# POMOĆNE FUNKCIJE
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['jpg','jpeg','png','gif','mp4','mov','avi']

# DEKORATOR ZA TOKEN I VALIDACIJU KORISNIKA
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        if not token:
            return jsonify({'message':'Token missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = data['id']
        except Exception as e:
            return jsonify({'message':'Token invalid', 'error': str(e)}), 401
        return f(user_id, *args, **kwargs)
    return decorated
