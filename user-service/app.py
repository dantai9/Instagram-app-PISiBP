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

# DEKORATOR ZA TOKEN
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-access-token')
        if not token:
            return jsonify({'message':'Token missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['id'])
        except:
            return jsonify({'message':'Token invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# REGISTRACIJA
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message':'Username exists'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message':'Email exists'}), 400
    user = User(username=data['username'], email=data['email'], name=data['name'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message':'User created'}), 201

# PRIJAVA
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter((User.username==data['login']) | (User.email==data['login'])).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message':'Invalid credentials'}), 401
    token = jwt.encode({'id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)},
                       app.config['SECRET_KEY'], algorithm='HS256')
    return jsonify({'token': token}) 