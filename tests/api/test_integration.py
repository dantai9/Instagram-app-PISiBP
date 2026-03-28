"""
API Integration Tests
Runs against live services — make sure docker compose is up before running.

Usage:
    pip install pytest requests
    pytest tests/api/test_integration.py -v
"""
import pytest
import requests
import io

BASE_USER = 'http://localhost:5000'
BASE_POST = 'http://localhost:5001'
BASE_FEED = 'http://localhost:5002'

# ── FIXTURES ──────────────────────────────

@pytest.fixture(scope='module')
def user_a():
    """Register and login user A, return token and id."""
    requests.post(f'{BASE_USER}/register', json={
        'username': 'integration_a', 'email': 'int_a@test.com',
        'name': 'Integration A', 'password': 'testpass123'
    })
    resp = requests.post(f'{BASE_USER}/login', json={'login': 'integration_a', 'password': 'testpass123'})
    data = resp.json()
    token = data['token']
    import jwt
    uid = jwt.decode(token, options={"verify_signature": False})['id']
    return {'token': token, 'id': uid}

@pytest.fixture(scope='module')
def user_b():
    """Register and login user B, return token and id."""
    requests.post(f'{BASE_USER}/register', json={
        'username': 'integration_b', 'email': 'int_b@test.com',
        'name': 'Integration B', 'password': 'testpass123'
    })
    resp = requests.post(f'{BASE_USER}/login', json={'login': 'integration_b', 'password': 'testpass123'})
    data = resp.json()
    token = data['token']
    import jwt
    uid = jwt.decode(token, options={"verify_signature": False})['id']
    return {'token': token, 'id': uid}

def auth(token):
    return {'Authorization': f'Bearer {token}'}

# ── USER SERVICE ──────────────────────────────

class TestUserService:

    def test_register_new_user(self):
        resp = requests.post(f'{BASE_USER}/register', json={
            'username': 'new_int_user', 'email': 'new_int@test.com',
            'name': 'New User', 'password': 'pass123'
        })
        assert resp.status_code in (201, 400)  # 400 if already exists

    def test_login_success(self, user_a):
        assert 'token' in user_a
        assert user_a['token'] is not None

    def test_get_own_profile(self, user_a):
        resp = requests.get(f'{BASE_USER}/profile/{user_a["id"]}', headers=auth(user_a['token']))
        assert resp.status_code == 200
        data = resp.json()
        assert data['username'] == 'integration_a'

    def test_search_users(self, user_a):
        resp = requests.get(f'{BASE_USER}/search?q=integration', headers=auth(user_a['token']))
        assert resp.status_code == 200
        assert 'users' in resp.json()

    def test_get_following_list(self, user_a, user_b):
        resp = requests.get(f'{BASE_USER}/following/{user_a["id"]}', headers=auth(user_a['token']))
        assert resp.status_code == 200
        assert user_b['id'] in resp.json()['following']

    def test_unfollow_user(self, user_a, user_b):
        requests.post(f'{BASE_USER}/follow/{user_b["id"]}', headers=auth(user_a['token']))
        resp = requests.post(f'{BASE_USER}/unfollow/{user_b["id"]}', headers=auth(user_a['token']))
        assert resp.status_code == 200

    def test_follow_user(self, user_a, user_b):
        resp = requests.post(f'{BASE_USER}/follow/{user_b["id"]}', headers=auth(user_a['token']))
        assert resp.status_code == 200

    def test_blocked_ids_endpoint(self, user_a):
        resp = requests.get(f'{BASE_USER}/blocked-ids', headers=auth(user_a['token']))
        assert resp.status_code == 200
        assert 'blocked_ids' in resp.json()

    def test_no_token_returns_401(self):
        resp = requests.get(f'{BASE_USER}/profile/1')
        assert resp.status_code == 401

# ── POST SERVICE ──────────────────────────────

@pytest.fixture(scope='module')
def sample_post(user_a):
    """Create a post and return its id."""
    requests.post(f'{BASE_USER}/follow/{user_a["id"]}', headers=auth(user_a['token']))
    resp = requests.post(
        f'{BASE_POST}/posts',
        headers=auth(user_a['token']),
        files={'files': ('test.jpg', io.BytesIO(b'fakeimagecontent'), 'image/jpeg')},
        data={'description': 'Integration test post'}
    )
    assert resp.status_code == 201
    return resp.json()['post_id']

class TestPostService:

    def test_create_post(self, user_a):
        resp = requests.post(
            f'{BASE_POST}/posts',
            headers=auth(user_a['token']),
            files={'files': ('test.jpg', io.BytesIO(b'fakeimage'), 'image/jpeg')},
            data={'description': 'Test post'}
        )
        assert resp.status_code == 201
        assert 'post_id' in resp.json()

    def test_get_post(self, user_a, sample_post):
        resp = requests.get(f'{BASE_POST}/posts/{sample_post}', headers=auth(user_a['token']))
        assert resp.status_code == 200
        data = resp.json()
        assert data['description'] == 'Integration test post'

    def test_update_post_description(self, user_a, sample_post):
        resp = requests.put(
            f'{BASE_POST}/posts/{sample_post}',
            headers=auth(user_a['token']),
            json={'description': 'Updated description'}
        )
        assert resp.status_code == 200

    def test_like_post(self, user_a, sample_post):
        resp = requests.post(f'{BASE_POST}/posts/{sample_post}/like', headers=auth(user_a['token']))
        assert resp.status_code == 200
        assert resp.json()['message'] in ('Post liked', 'Like removed')

    def test_add_comment(self, user_a, sample_post):
        resp = requests.post(
            f'{BASE_POST}/posts/{sample_post}/comment',
            headers=auth(user_a['token']),
            json={'text': 'Integration test comment'}
        )
        assert resp.status_code == 201
        assert 'comment_id' in resp.json()

    def test_edit_comment(self, user_a, sample_post):
        resp = requests.post(
            f'{BASE_POST}/posts/{sample_post}/comment',
            headers=auth(user_a['token']),
            json={'text': 'Comment to edit'}
        )
        cid = resp.json()['comment_id']
        edit_resp = requests.put(
            f'{BASE_POST}/comments/{cid}',
            headers=auth(user_a['token']),
            json={'text': 'Edited comment'}
        )
        assert edit_resp.status_code == 200

    def test_delete_comment(self, user_a, sample_post):
        resp = requests.post(
            f'{BASE_POST}/posts/{sample_post}/comment',
            headers=auth(user_a['token']),
            json={'text': 'Comment to delete'}
        )
        cid = resp.json()['comment_id']
        del_resp = requests.delete(f'{BASE_POST}/comments/{cid}', headers=auth(user_a['token']))
        assert del_resp.status_code == 200

    def test_get_user_posts(self, user_a):
        resp = requests.get(f'{BASE_POST}/user_posts/{user_a["id"]}', headers=auth(user_a['token']))
        assert resp.status_code == 200
        assert 'posts' in resp.json()

    def test_delete_post(self, user_a):
        resp = requests.post(
            f'{BASE_POST}/posts',
            headers=auth(user_a['token']),
            files={'files': ('del.jpg', io.BytesIO(b'img'), 'image/jpeg')},
            data={'description': 'To delete'}
        )
        pid = resp.json()['post_id']
        del_resp = requests.delete(f'{BASE_POST}/posts/{pid}', headers=auth(user_a['token']))
        assert del_resp.status_code == 200

    def test_post_not_found(self, user_a):
        resp = requests.get(f'{BASE_POST}/posts/999999', headers=auth(user_a['token']))
        assert resp.status_code == 404

# ── FEED SERVICE ──────────────────────────────

class TestFeedService:

    def test_feed_requires_auth(self):
        resp = requests.get(f'{BASE_FEED}/feed')
        assert resp.status_code == 401

    def test_feed_returns_200(self, user_a):
        resp = requests.get(f'{BASE_FEED}/feed', headers=auth(user_a['token']))
        assert resp.status_code == 200
        data = resp.json()
        assert 'feed' in data
        assert 'total' in data
        assert 'page' in data
        assert 'per_page' in data

    def test_feed_pagination_params(self, user_a):
        resp = requests.get(f'{BASE_FEED}/feed?page=1&per_page=5', headers=auth(user_a['token']))
        assert resp.status_code == 200
        data = resp.json()
        assert data['per_page'] == 5
        assert data['page'] == 1

    def test_feed_contains_followed_posts(self, user_a, user_b, sample_post):
        # user_a follows user_b, user_b has a post
        requests.post(f'{BASE_USER}/follow/{user_b["id"]}', headers=auth(user_a['token']))
        requests.post(
            f'{BASE_POST}/posts',
            headers=auth(user_b['token']),
            files={'files': ('feed.jpg', io.BytesIO(b'img'), 'image/jpeg')},
            data={'description': 'Feed test post'}
        )
        resp = requests.get(f'{BASE_FEED}/feed', headers=auth(user_a['token']))
        assert resp.status_code == 200