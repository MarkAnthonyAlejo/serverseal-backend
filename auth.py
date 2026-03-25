import os
import jwt
from functools import wraps
from datetime import datetime, timedelta, timezone
from flask import request, jsonify, g

SECRET_KEY = os.getenv('JWT_SECRET', 'dev-secret-change-in-production')
TOKEN_EXPIRY_HOURS = 8


def create_token(user_id: str, role: str) -> str:
    payload = {
        'sub': user_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])


def require_auth(f):
    """Decorator: rejects requests without a valid Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'AUTH_REQUIRED'}), 401
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            g.current_user = {'user_id': payload['sub'], 'role': payload['role']}
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'TOKEN_EXPIRED'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'TOKEN_INVALID'}), 401
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Decorator: must be used after @require_auth. Rejects if role not in allowed list."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user') or g.current_user['role'] not in roles:
                return jsonify({'error': 'FORBIDDEN'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
