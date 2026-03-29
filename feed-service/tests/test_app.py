import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret'
    yield app.test_client()

def make_token(user_id=1):
    import jwt, datetime
    return jwt.encode(
        {'id': user_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
        'test_secret', algorithm='HS256'
    )

def auth(user_id=1):
    return {'Authorization': f'Bearer {make_token(user_id)}'}

def make_post(author_id, i):
    return {
        'id': i,
        'author_id': author_id,
        'description': f'Post {i}',
        'timestamp': f'2024-01-{i+1:02d}T10:00:00',
        'files': [],
        'likes_count': 0,
        'comments_count': 0
    }

# ── AUTH ──────────────────────────────

def test_feed_no_token(client):
    resp = client.get('/feed')
    assert resp.status_code == 401

def test_feed_invalid_token(client):
    resp = client.get('/feed', headers={'Authorization': 'Bearer invalidtoken'})
    assert resp.status_code == 401

# ── FEED ──────────────────────────────

@patch('app.requests.get')
def test_feed_empty_following(mock_get, client):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'following': []})
    resp = client.get('/feed', headers=auth())
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['feed'] == []
    assert data['total'] == 0

@patch('app.requests.get')
def test_feed_following_service_fails(mock_get, client):
    mock_get.return_value = MagicMock(status_code=500)
    resp = client.get('/feed', headers=auth())
    assert resp.status_code == 500

@patch('app.fetch_posts_for_user')
@patch('app.requests.get')
def test_feed_returns_posts_sorted(mock_get, mock_fetch, client):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'following': [2, 3]})
    mock_fetch.side_effect = [
        [make_post(2, 1)],  # older
        [make_post(3, 2)],  # newer
    ]
    resp = client.get('/feed', headers=auth())
    assert resp.status_code == 200
    feed = resp.get_json()['feed']
    assert len(feed) == 2
    # Sorted descending by timestamp — post 2 (2024-01-02) should be first
    assert feed[0]['id'] == 2
    assert feed[1]['id'] == 1

@patch('app.fetch_posts_for_user')
@patch('app.requests.get')
def test_feed_pagination(mock_get, mock_fetch, client):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'following': [2]})
    posts = [make_post(2, i) for i in range(15)]
    mock_fetch.return_value = posts
    resp = client.get('/feed?page=1&per_page=10', headers=auth())
    data = resp.get_json()
    assert len(data['feed']) == 10
    assert data['has_next'] == True
    assert data['total'] == 15

@patch('app.fetch_posts_for_user')
@patch('app.requests.get')
def test_feed_pagination_page_2(mock_get, mock_fetch, client):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'following': [2]})
    posts = [make_post(2, i) for i in range(15)]
    mock_fetch.return_value = posts
    resp = client.get('/feed?page=2&per_page=10', headers=auth())
    data = resp.get_json()
    assert len(data['feed']) == 5
    assert data['has_next'] == False

@patch('app.fetch_posts_for_user')
@patch('app.requests.get')
def test_feed_has_next_false_when_all_loaded(mock_get, mock_fetch, client):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'following': [2]})
    posts = [make_post(2, i) for i in range(5)]
    mock_fetch.return_value = posts
    resp = client.get('/feed?page=1&per_page=10', headers=auth())
    data = resp.get_json()
    assert data['has_next'] == False

@patch('app.fetch_posts_for_user')
@patch('app.requests.get')
def test_feed_invalid_pagination_defaults(mock_get, mock_fetch, client):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'following': [2]})
    mock_fetch.return_value = [make_post(2, 1)]
    resp = client.get('/feed?page=abc&per_page=xyz', headers=auth())
    assert resp.status_code == 200

@patch('app.fetch_posts_for_user', return_value=[])
@patch('app.requests.get')
def test_feed_post_service_down(mock_get, mock_fetch, client):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'following': [2, 3]})
    resp = client.get('/feed', headers=auth())
    assert resp.status_code == 200
    assert resp.get_json()['feed'] == []

# ── FETCH POSTS FOR USER ──────────────────────────────

@patch('app.requests.get')
def test_fetch_posts_for_user_success(mock_get, client):
    from app import fetch_posts_for_user
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {'posts': [make_post(2, 1)]})
    result = fetch_posts_for_user(2, 'token')
    assert len(result) == 1

@patch('app.requests.get')
def test_fetch_posts_for_user_failure(mock_get, client):
    from app import fetch_posts_for_user
    mock_get.return_value = MagicMock(status_code=403)
    result = fetch_posts_for_user(2, 'token')
    assert result == []

@patch('app.requests.get', side_effect=Exception('timeout'))
def test_fetch_posts_for_user_exception(mock_get, client):
    from app import fetch_posts_for_user
    result = fetch_posts_for_user(2, 'token')
    assert result == []
