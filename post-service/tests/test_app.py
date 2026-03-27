import pytest
import io
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import app, db, Post, File, Like, Comment

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test_secret'
    app.config['UPLOAD_FOLDER'] = '/tmp/test_post_uploads'
    os.makedirs('/tmp/test_post_uploads', exist_ok=True)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()

def make_token(user_id=1):
    import jwt, datetime
    return jwt.encode(
        {'id': user_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
        'test_secret', algorithm='HS256'
    )

def auth(user_id=1):
    return {'Authorization': f'Bearer {make_token(user_id)}'}

def mock_can_view(viewer_id, author_id, token):
    return True

def fake_image():
    return (io.BytesIO(b'fakeimagedata'), 'test.jpg')

# ── CREATE POST ──────────────────────────────

@patch('api.can_view_posts_of', side_effect=mock_can_view)
def test_create_post_success(mock_view, client):
    data = {'description': 'Hello', 'files': fake_image()}
    resp = client.post('/posts', data=data, content_type='multipart/form-data', headers=auth())
    assert resp.status_code == 201
    assert 'post_id' in resp.get_json()

def test_create_post_no_token(client):
    data = {'description': 'Hello', 'files': fake_image()}
    resp = client.post('/posts', data=data, content_type='multipart/form-data')
    assert resp.status_code == 401

def test_create_post_no_files(client):
    resp = client.post('/posts', data={'description': 'No files'}, content_type='multipart/form-data', headers=auth())
    assert resp.status_code == 400

@patch('api.can_view_posts_of', side_effect=mock_can_view)
def test_create_post_invalid_file_type(mock_view, client):
    data = {'description': 'Bad file', 'files': (io.BytesIO(b'data'), 'file.exe')}
    resp = client.post('/posts', data=data, content_type='multipart/form-data', headers=auth())
    assert resp.status_code == 400

# ── GET POST ──────────────────────────────

@patch('api.can_view_posts_of', side_effect=mock_can_view)
@patch('api.get_blocked_ids', return_value=set())
def test_get_post_success(mock_blocked, mock_view, client):
    with app.app_context():
        post = Post(author_id=1, description='Test post')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.get(f'/posts/{pid}', headers=auth())
    assert resp.status_code == 200
    assert resp.get_json()['description'] == 'Test post'

def test_get_post_not_found(client):
    resp = client.get('/posts/99999', headers=auth())
    assert resp.status_code == 404

# ── UPDATE POST ──────────────────────────────

def test_update_post_description(client):
    with app.app_context():
        post = Post(author_id=1, description='Old desc')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.put(f'/posts/{pid}', json={'description': 'New desc'}, headers=auth())
    assert resp.status_code == 200

def test_update_post_not_owner(client):
    with app.app_context():
        post = Post(author_id=2, description='Not mine')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.put(f'/posts/{pid}', json={'description': 'Hacked'}, headers=auth(user_id=1))
    assert resp.status_code == 403

def test_update_post_no_description(client):
    with app.app_context():
        post = Post(author_id=1, description='Desc')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.put(f'/posts/{pid}', json={}, headers=auth())
    assert resp.status_code == 400

# ── DELETE POST ──────────────────────────────

def test_delete_post_success(client):
    with app.app_context():
        post = Post(author_id=1, description='To delete')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.delete(f'/posts/{pid}', headers=auth())
    assert resp.status_code == 200

def test_delete_post_not_owner(client):
    with app.app_context():
        post = Post(author_id=2, description='Not mine')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.delete(f'/posts/{pid}', headers=auth(user_id=1))
    assert resp.status_code == 403

# ── LIKES ──────────────────────────────

@patch('api.can_view_posts_of', side_effect=mock_can_view)
def test_like_post(mock_view, client):
    with app.app_context():
        post = Post(author_id=2, description='Like me')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.post(f'/posts/{pid}/like', headers=auth())
    assert resp.status_code == 200
    assert resp.get_json()['message'] == 'Post liked'

@patch('api.can_view_posts_of', side_effect=mock_can_view)
def test_unlike_post(mock_view, client):
    with app.app_context():
        post = Post(author_id=2, description='Like me')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    client.post(f'/posts/{pid}/like', headers=auth())
    resp = client.post(f'/posts/{pid}/like', headers=auth())
    assert resp.get_json()['message'] == 'Like removed'

@patch('api.can_view_posts_of', return_value=False)
def test_like_private_post_not_following(mock_view, client):
    with app.app_context():
        post = Post(author_id=2, description='Private')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.post(f'/posts/{pid}/like', headers=auth())
    assert resp.status_code == 403

# ── COMMENTS ──────────────────────────────

@patch('api.can_view_posts_of', side_effect=mock_can_view)
def test_add_comment(mock_view, client):
    with app.app_context():
        post = Post(author_id=2, description='Comment me')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.post(f'/posts/{pid}/comment', json={'text': 'Great post!'}, headers=auth())
    assert resp.status_code == 201

@patch('api.can_view_posts_of', side_effect=mock_can_view)
def test_add_empty_comment(mock_view, client):
    with app.app_context():
        post = Post(author_id=2, description='Post')
        db.session.add(post)
        db.session.commit()
        pid = post.id
    resp = client.post(f'/posts/{pid}/comment', json={'text': ''}, headers=auth())
    assert resp.status_code == 400

def test_edit_comment(client):
    with app.app_context():
        post = Post(author_id=1, description='Post')
        db.session.add(post)
        db.session.commit()
        comment = Comment(user_id=1, post_id=post.id, text='Original')
        db.session.add(comment)
        db.session.commit()
        cid = comment.id
    resp = client.put(f'/comments/{cid}', json={'text': 'Edited'}, headers=auth())
    assert resp.status_code == 200

def test_edit_comment_not_owner(client):
    with app.app_context():
        post = Post(author_id=1, description='Post')
        db.session.add(post)
        db.session.commit()
        comment = Comment(user_id=2, post_id=post.id, text='Not mine')
        db.session.add(comment)
        db.session.commit()
        cid = comment.id
    resp = client.put(f'/comments/{cid}', json={'text': 'Hacked'}, headers=auth(user_id=1))
    assert resp.status_code == 403

def test_delete_comment(client):
    with app.app_context():
        post = Post(author_id=1, description='Post')
        db.session.add(post)
        db.session.commit()
        comment = Comment(user_id=1, post_id=post.id, text='Delete me')
        db.session.add(comment)
        db.session.commit()
        cid = comment.id
    resp = client.delete(f'/comments/{cid}', headers=auth())
    assert resp.status_code == 200

def test_delete_comment_not_owner(client):
    with app.app_context():
        post = Post(author_id=1, description='Post')
        db.session.add(post)
        db.session.commit()
        comment = Comment(user_id=2, post_id=post.id, text='Not mine')
        db.session.add(comment)
        db.session.commit()
        cid = comment.id
    resp = client.delete(f'/comments/{cid}', headers=auth(user_id=1))
    assert resp.status_code == 403

# ── USER POSTS ──────────────────────────────

@patch('api.can_view_posts_of', side_effect=mock_can_view)
@patch('api.get_blocked_ids', return_value=set())
def test_get_user_posts(mock_blocked, mock_view, client):
    with app.app_context():
        for i in range(3):
            db.session.add(Post(author_id=1, description=f'Post {i}'))
        db.session.commit()
    resp = client.get('/user_posts/1', headers=auth())
    assert resp.status_code == 200
    assert len(resp.get_json()['posts']) == 3

@patch('api.can_view_posts_of', return_value=False)
def test_get_user_posts_private(mock_view, client):
    with app.app_context():
        db.session.add(Post(author_id=2, description='Private'))
        db.session.commit()
    resp = client.get('/user_posts/2', headers=auth(user_id=1))
    assert resp.status_code == 200
    assert resp.get_json()['posts'] == []

# ── BLOCKED USERS FILTER ──────────────────────────────

@patch('api.can_view_posts_of', side_effect=mock_can_view)
@patch('api.get_blocked_ids', return_value={99})
def test_blocked_likes_not_counted(mock_blocked, mock_view, client):
    with app.app_context():
        post = Post(author_id=2, description='Post')
        db.session.add(post)
        db.session.commit()
        like1 = Like(user_id=1, post_id=post.id)
        like2 = Like(user_id=99, post_id=post.id)
        db.session.add_all([like1, like2])
        db.session.commit()
        pid = post.id
    resp = client.get(f'/posts/{pid}', headers=auth())
    assert resp.get_json()['likes_count'] == 1
