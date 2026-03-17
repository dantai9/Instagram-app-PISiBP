from flask import Flask, request, jsonify
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
import os, jwt, requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_fallback_key')

USER_SERVICE_URL = os.environ.get('USER_SERVICE_URL', 'http://user-service:5000')
POST_SERVICE_URL = os.environ.get('POST_SERVICE_URL', 'http://post-service:5001')

# ───────────────────────────── HELPERS ─────────────────────────────

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
        return f(user_id, token, *args, **kwargs)
    return decorated

def fetch_posts_for_user(fid, token):
    """Fetch posts for a single followed user. Returns list of posts."""
    try:
        resp = requests.get(
            f'{POST_SERVICE_URL}/user_posts/{fid}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json().get('posts', [])
    except Exception:
        pass
    return []

if __name__ == '__main__':
    app.run(debug=True, port=5002)

    