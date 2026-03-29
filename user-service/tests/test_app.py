import pytest
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import app, db, User, FollowRequest

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test_secret'
    app.config['UPLOAD_FOLDER'] = '/tmp/test_uploads'
    os.makedirs('/tmp/test_uploads', exist_ok=True)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()

def register(client, username='testuser', email='test@test.com', password='pass123', name='Test User'):
    return client.post('/register', json={
        'username': username,
        'email': email,
        'password': password,
        'name': name
    })

def login(client, login='testuser', password='pass123'):
    resp = client.post('/login', json={'login': login, 'password': password})
    return resp.get_json()['token']

# ── REGISTER ──────────────────────────────

def test_register_success(client):
    resp = register(client)
    assert resp.status_code == 201
    assert resp.get_json()['message'] == 'User created'

def test_register_duplicate_username(client):
    register(client)
    resp = register(client, email='other@test.com')
    assert resp.status_code == 400
    assert 'Username' in resp.get_json()['message']

def test_register_duplicate_email(client):
    register(client)
    resp = register(client, username='otheruser')
    assert resp.status_code == 400
    assert 'Email' in resp.get_json()['message']

def test_register_missing_field(client):
    resp = client.post('/register', json={'username': 'a', 'email': 'a@a.com'})
    assert resp.status_code == 400

# ── LOGIN ──────────────────────────────

def test_login_success_username(client):
    register(client)
    resp = client.post('/login', json={'login': 'testuser', 'password': 'pass123'})
    assert resp.status_code == 200
    assert 'token' in resp.get_json()

def test_login_success_email(client):
    register(client)
    resp = client.post('/login', json={'login': 'test@test.com', 'password': 'pass123'})
    assert resp.status_code == 200
    assert 'token' in resp.get_json()

def test_login_wrong_password(client):
    register(client)
    resp = client.post('/login', json={'login': 'testuser', 'password': 'wrongpass'})
    assert resp.status_code == 401

def test_login_nonexistent_user(client):
    resp = client.post('/login', json={'login': 'nobody', 'password': 'pass'})
    assert resp.status_code == 401

# ── PROFILE ──────────────────────────────

def test_get_own_profile(client):
    register(client)
    token = login(client)
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        uid = user.id
    resp = client.get(f'/profile/{uid}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['username'] == 'testuser'
    assert data['name'] == 'Test User'

def test_get_profile_no_token(client):
    register(client)
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        uid = user.id
    resp = client.get(f'/profile/{uid}')
    assert resp.status_code == 401

def test_get_private_profile_not_following(client):
    register(client, username='private_user', email='priv@test.com')
    register(client, username='viewer', email='viewer@test.com')
    token = login(client, login='viewer')
    with app.app_context():
        priv = User.query.filter_by(username='private_user').first()
        priv.is_private = True
        db.session.commit()
        uid = priv.id
    resp = client.get(f'/profile/{uid}', headers={'Authorization': f'Bearer {token}'})
    data = resp.get_json()
    assert 'followers' not in data

def test_get_nonexistent_profile(client):
    register(client)
    token = login(client)
    resp = client.get('/profile/99999', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 404

# ── FOLLOW ──────────────────────────────

def test_follow_public_user(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token = login(client, login='user1')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        uid2 = u2.id
    resp = client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['message'] == 'Now following'

def test_follow_private_user_sends_request(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token = login(client, login='user1')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        u2.is_private = True
        db.session.commit()
        uid2 = u2.id
    resp = client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert 'request' in resp.get_json()['message'].lower()

def test_follow_self_not_allowed(client):
    register(client)
    token = login(client)
    with app.app_context():
        u = User.query.filter_by(username='testuser').first()
        uid = u.id
    resp = client.post(f'/follow/{uid}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400

def test_unfollow_user(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token = login(client, login='user1')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        uid2 = u2.id
    client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token}'})
    resp = client.post(f'/unfollow/{uid2}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200

def test_follow_already_following(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token = login(client, login='user1')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        uid2 = u2.id
    client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token}'})
    resp = client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400

# ── FOLLOW REQUESTS ──────────────────────────────

def test_accept_follow_request(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token1 = login(client, login='user1')
    token2 = login(client, login='user2')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        u2.is_private = True
        db.session.commit()
        uid2 = u2.id
    client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token1}'})
    with app.app_context():
        req = FollowRequest.query.first()
        req_id = req.id
    resp = client.post(f'/follow-requests/{req_id}/accept', headers={'Authorization': f'Bearer {token2}'})
    assert resp.status_code == 200

def test_reject_follow_request(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token1 = login(client, login='user1')
    token2 = login(client, login='user2')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        u2.is_private = True
        db.session.commit()
        uid2 = u2.id
    client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token1}'})
    with app.app_context():
        req = FollowRequest.query.first()
        req_id = req.id
    resp = client.post(f'/follow-requests/{req_id}/reject', headers={'Authorization': f'Bearer {token2}'})
    assert resp.status_code == 200

# ── BLOCK ──────────────────────────────

def test_block_user(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token = login(client, login='user1')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        uid2 = u2.id
    resp = client.post(f'/block/{uid2}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200

def test_block_removes_follow(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token1 = login(client, login='user1')
    token2 = login(client, login='user2')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        uid2 = u2.id
        u1 = User.query.filter_by(username='user1').first()
        uid1 = u1.id
    client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token1}'})
    client.post(f'/block/{uid1}', headers={'Authorization': f'Bearer {token2}'})
    with app.app_context():
        u1 = User.query.get(uid1)
        u2 = User.query.get(uid2)
        assert u2 not in u1.following

def test_blocked_user_not_in_search(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token1 = login(client, login='user1')
    with app.app_context():
        u2 = User.query.filter_by(username='user2').first()
        uid2 = u2.id
    client.post(f'/block/{uid2}', headers={'Authorization': f'Bearer {token1}'})
    resp = client.get('/search?q=user2', headers={'Authorization': f'Bearer {token1}'})
    users = resp.get_json()['users']
    assert all(u['id'] != uid2 for u in users)

# ── SEARCH ──────────────────────────────

def test_search_by_username(client):
    register(client, username='findme', email='find@test.com', name='Find Me')
    register(client, username='searcher', email='search@test.com')
    token = login(client, login='searcher')
    resp = client.get('/search?q=findme', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    users = resp.get_json()['users']
    assert any(u['username'] == 'findme' for u in users)

def test_search_by_name(client):
    register(client, username='findme', email='find@test.com', name='Unique Name')
    register(client, username='searcher', email='search@test.com')
    token = login(client, login='searcher')
    resp = client.get('/search?q=Unique', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    users = resp.get_json()['users']
    assert any(u['username'] == 'findme' for u in users)

def test_search_empty_query(client):
    register(client)
    token = login(client)
    resp = client.get('/search?q=', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['users'] == []

# ── FOLLOWING LIST ──────────────────────────────

def test_get_following_list(client):
    register(client, username='user1', email='u1@test.com')
    register(client, username='user2', email='u2@test.com')
    token1 = login(client, login='user1')
    with app.app_context():
        u1 = User.query.filter_by(username='user1').first()
        u2 = User.query.filter_by(username='user2').first()
        uid1, uid2 = u1.id, u2.id
    client.post(f'/follow/{uid2}', headers={'Authorization': f'Bearer {token1}'})
    resp = client.get(f'/following/{uid1}', headers={'Authorization': f'Bearer {token1}'})
    assert resp.status_code == 200
    assert uid2 in resp.get_json()['following']
