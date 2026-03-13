from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajni_kljuc'  # promeni za produkciju
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# MODELI
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

blocked = db.Table('blocked',
    db.Column('blocker_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('blocked_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.String(250))
    is_private = db.Column(db.Boolean, default=False)
    followers = db.relationship(
        'User', secondary=followers,
        primaryjoin=id==followers.c.followed_id,
        secondaryjoin=id==followers.c.follower_id,
        backref='following'
    )
    blocked_users = db.relationship(
        'User', secondary=blocked,
        primaryjoin=id==blocked.c.blocker_id,
        secondaryjoin=id==blocked.c.blocked_id,
        backref='blocked_by'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

