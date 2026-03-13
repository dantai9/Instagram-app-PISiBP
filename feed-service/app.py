from flask import Flask, request, jsonify
import requests
from functools import wraps
import jwt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajni_kljuc'  # isti ključ kao u ostalim servisima

USER_SERVICE_URL = 'http://user-service:5000'
POST_SERVICE_URL = 'http://post-service:5001'

# DEKORATOR ZA TOKEN
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
        return f(user_id, token, *args, **kwargs)
    return decorated

if __name__ == '__main__':
    app.run(debug=True, port=5002)