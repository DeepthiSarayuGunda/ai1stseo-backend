"""
Developer API Key System — Generate, validate, and rate-limit API keys.

Keys are prefixed with 'ai1st_' for easy identification.
Only the SHA-256 hash is stored; the raw key is shown once at creation.

Scopes: read, write, admin
Rate limiting: per-key, configurable, tracked in the database.

Usage:
  Clients send: Authorization: Bearer ai1st_xxxxxxxxxxxx
  Or: X-API-Key: ai1st_xxxxxxxxxxxx

Middleware:
  from apikey_api import require_api_access
  @require_api_access('read')  # accepts Cognito token OR API key
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from database import query, query_one, execute, insert_returning
from functools import wraps
import hashlib
import secrets
import datetime

apikey_bp = Blueprint('apikeys', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


def _hash_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_key():
    """Generate a prefixed API key: ai1st_ + 40 hex chars."""
    raw = 'ai1st_' + secrets.token_hex(20)
    return raw


def _get_user_id():
    if hasattr(request, 'cognito_user') and request.cognito_user:
        return request.cognito_user.get('user_id')
    return None


# === Validation Middleware ===

def validate_api_key(required_scope='read'):
    """
    Check for a valid API key in the request.
    Returns the key row dict if valid, None otherwise.
    """
    raw_key = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer ai1st_'):
        raw_key = auth_header[7:]
    if not raw_key:
        raw_key = request.headers.get('X-API-Key', '')
    if not raw_key or not raw_key.startswith('ai1st_'):
        return None

    key_hash = _hash_key(raw_key)
    try:
        row = query_one(
            "SELECT * FROM api_keys WHERE key_hash = %s AND is_active = true",
            (key_hash,),
        )
        if not row:
            return None

        # Check scope
        scopes = row.get('scopes', [])
        if required_scope not in scopes and 'admin' not in scopes:
            return None

        # Rate limiting
        now = datetime.datetime.utcnow()
        hour_window = row.get('hour_window')
        requests_this_hour = row.get('requests_this_hour', 0)
        rate_limit = row.get('rate_limit_per_hour', 100)

        if hour_window and (now - hour_window).total_seconds() < 3600:
            if requests_this_hour >= rate_limit:
                return 'rate_limited'
            execute(
                "UPDATE api_keys SET requests_this_hour = requests_this_hour + 1, last_used_at = NOW() WHERE id = %s",
                (row['id'],),
            )
        else:
            execute(
                "UPDATE api_keys SET requests_this_hour = 1, hour_window = NOW(), last_used_at = NOW() WHERE id = %s",
                (row['id'],),
            )

        return row
    except Exception:
        return None


def require_api_access(scope='read'):
    """
    Decorator: accepts either Cognito token OR API key.
    Use this instead of @require_auth on endpoints you want to expose via API keys.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Try Cognito first
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer ') and not auth_header.startswith('Bearer ai1st_'):
                # Cognito token path — use existing auth
                from auth import require_auth as _ra
                @_ra
                def _inner(*a, **kw):
                    return f(*a, **kw)
                return _inner(*args, **kwargs)

            # Try API key
            result = validate_api_key(scope)
            if result == 'rate_limited':
                return jsonify({'status': 'error', 'message': 'Rate limit exceeded. Try again later.'}), 429
            if result is None:
                return jsonify({'status': 'error', 'message': 'Valid API key or auth token required'}), 401

            # Attach key info to request for downstream use
            request.api_key = result
            request.cognito_user = {
                'user_id': result.get('created_by'),
                'email': 'apikey:' + result.get('key_prefix', ''),
                'role': 'member',
            }
            return f(*args, **kwargs)
        return wrapper
    return decorator


# === CRUD Endpoints ===

@apikey_bp.route('/api/keys', methods=['POST'])
@require_auth
def create_api_key():
    """Generate a new API key. The raw key is returned ONCE."""
    d = request.get_json() or {}
    label = d.get('label', 'Untitled Key').strip()
    scopes = d.get('scopes', ['read'])
    rate_limit = d.get('rate_limit_per_hour', 100)

    valid_scopes = {'read', 'write', 'admin'}
    invalid = [s for s in scopes if s not in valid_scopes]
    if invalid:
        return jsonify({'status': 'error', 'message': 'Invalid scopes: ' + ', '.join(invalid)}), 400

    raw_key = _generate_key()
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:12]

    try:
        scopes_pg = '{' + ','.join(scopes) + '}'
        key_id = insert_returning(
            "INSERT INTO api_keys (project_id, key_hash, key_prefix, label, scopes, rate_limit_per_hour, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (DEFAULT_PROJECT_ID, key_hash, key_prefix, label, scopes_pg, rate_limit, _get_user_id()),
        )
        return jsonify({
            'status': 'success',
            'id': str(key_id),
            'key': raw_key,
            'prefix': key_prefix,
            'label': label,
            'scopes': scopes,
            'rate_limit_per_hour': rate_limit,
            'warning': 'Save this key now. It cannot be retrieved again.',
        }), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apikey_bp.route('/api/keys', methods=['GET'])
@require_auth
def list_api_keys():
    """List API keys (shows prefix only, not the full key)."""
    try:
        rows = query(
            "SELECT id, key_prefix, label, scopes, rate_limit_per_hour, is_active, "
            "requests_this_hour, last_used_at, created_at "
            "FROM api_keys WHERE project_id = %s ORDER BY created_at DESC",
            (DEFAULT_PROJECT_ID,),
        )
        return jsonify({'status': 'success', 'keys': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apikey_bp.route('/api/keys/<key_id>', methods=['DELETE'])
@require_auth
def revoke_api_key(key_id):
    """Revoke (delete) an API key."""
    try:
        deleted = execute(
            "DELETE FROM api_keys WHERE id = %s AND project_id = %s",
            (key_id, DEFAULT_PROJECT_ID),
        )
        if deleted == 0:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apikey_bp.route('/api/keys/<key_id>/toggle', methods=['POST'])
@require_auth
def toggle_api_key(key_id):
    """Enable or disable an API key."""
    try:
        execute(
            "UPDATE api_keys SET is_active = NOT is_active WHERE id = %s AND project_id = %s",
            (key_id, DEFAULT_PROJECT_ID),
        )
        row = query_one("SELECT is_active FROM api_keys WHERE id = %s", (key_id,))
        return jsonify({'status': 'success', 'is_active': row['is_active'] if row else False})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
