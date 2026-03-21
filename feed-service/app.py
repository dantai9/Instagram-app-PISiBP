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

# ───────────────────────────── FEED ─────────────────────────────

@app.route('/feed', methods=['GET'])
@token_required
def get_feed(user_id, token):
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 20
    except ValueError:
        page, per_page = 1, 20

    # 1. Get list of followed user IDs
    try:
        resp = requests.get(
            f'{USER_SERVICE_URL}/following/{user_id}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )
        if resp.status_code != 200:
            return jsonify({'message': 'Failed to get following list'}), 500
        following_ids = resp.json().get('following', [])
    except Exception as e:
        return jsonify({'message': 'Error contacting user service', 'error': str(e)}), 500

    if not following_ids:
        return jsonify({'feed': [], 'page': page, 'per_page': per_page, 'total': 0})

if __name__ == '__main__':
    app.run(debug=True, port=5002)

    