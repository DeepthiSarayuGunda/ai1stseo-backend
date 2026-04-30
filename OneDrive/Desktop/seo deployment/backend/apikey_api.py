"""
Developer API Key System ΓÇö DynamoDB version.
Keys prefixed with 'ai1st_', SHA-256 hashed storage, scopes, rate limiting.
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from dynamodb_helper import put_item, get_item, scan_table, update_item, delete_item
from functools import wraps
import hashlib
import secrets
import datetime
import uuid

apikey_bp = Blueprint('apikeys', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'


def _hash_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_key():
    return 'ai1st_' + secrets.token_hex(20)


def _get_user_id():
    if hasattr(request, 'cognito_user') and request.cognito_user:
        return request.cognito_user.get('user_id')
    return None


def validate_api_key(required_scope='read'):
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
        row = get_item('ai1stseo-api-keys', {'key_hash': key_hash})
        if not row or not row.get('is_active', True):
            return None
        scopes = row.get('scopes', [])
        if required_scope not in scopes and 'admin' not in scopes:
            return None
        # Rate limiting
        now = datetime.datetime.utcnow()
        hour_window = row.get('hour_window')
        requests_this_hour = row.get('requests_this_hour', 0)
        rate_limit = row.get('rate_limit_per_hour', 100)

        # Credit metering (if credits field exists and is not unlimited)
        credits_remaining = row.get('credits')
        if credits_remaining is not None and credits_remaining != -1:
            if credits_remaining <= 0:
                return 'no_credits'
            # Decrement credits
            try:
                update_item('ai1stseo-api-keys', {'key_hash': key_hash},
                            {'credits': max(0, credits_remaining - 1)})
            except Exception:
                pass

        if hour_window:
            try:
                hw = datetime.datetime.fromisoformat(hour_window) if isinstance(hour_window, str) else hour_window
                if (now - hw).total_seconds() < 3600:
                    if requests_this_hour >= rate_limit:
                        return 'rate_limited'
                    update_item('ai1stseo-api-keys', {'key_hash': key_hash},
                                {'requests_this_hour': requests_this_hour + 1,
                                 'last_used_at': now.isoformat()})
                else:
                    update_item('ai1stseo-api-keys', {'key_hash': key_hash},
                                {'requests_this_hour': 1, 'hour_window': now.isoformat(),
                                 'last_used_at': now.isoformat()})
            except Exception:
                pass
        else:
            update_item('ai1stseo-api-keys', {'key_hash': key_hash},
                        {'requests_this_hour': 1, 'hour_window': now.isoformat(),
                         'last_used_at': now.isoformat()})
        return row
    except Exception:
        return None


def require_api_access(scope='read'):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer ') and not auth_header.startswith('Bearer ai1st_'):
                from auth import require_auth as _ra
                @_ra
                def _inner(*a, **kw):
                    return f(*a, **kw)
                return _inner(*args, **kwargs)
            result = validate_api_key(scope)
            if result == 'rate_limited':
                return jsonify({'status': 'error', 'message': 'Rate limit exceeded.'}), 429
            if result == 'no_credits':
                return jsonify({'status': 'error', 'message': 'API credits exhausted. Purchase more at /api/stripe/create-checkout.'}), 402
            if result is None:
                return jsonify({'status': 'error', 'message': 'Valid API key or auth token required'}), 401
            request.api_key = result
            request.cognito_user = {
                'user_id': result.get('created_by'),
                'email': 'apikey:' + result.get('key_prefix', ''),
                'role': 'member',
            }
            return f(*args, **kwargs)
        return wrapper
    return decorator


@apikey_bp.route('/api/keys', methods=['POST'])
@require_auth
def create_api_key():
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
    credits = d.get('credits', -1)  # -1 = unlimited, positive int = metered
    try:
        put_item('ai1stseo-api-keys', {
            'key_hash': key_hash, 'key_prefix': key_prefix,
            'project_id': DEFAULT_PROJECT_ID, 'label': label,
            'scopes': scopes, 'rate_limit_per_hour': rate_limit,
            'credits': credits,
            'is_active': True, 'created_by': _get_user_id(),
            'requests_this_hour': 0,
        })
        return jsonify({
            'status': 'success', 'id': key_hash[:16],
            'key': raw_key, 'prefix': key_prefix,
            'label': label, 'scopes': scopes,
            'rate_limit_per_hour': rate_limit,
            'credits': credits,
            'warning': 'Save this key now. It cannot be retrieved again.',
        }), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apikey_bp.route('/api/keys', methods=['GET'])
@require_auth
def list_api_keys():
    try:
        items = scan_table('ai1stseo-api-keys', 50)
        safe = [{k: v for k, v in i.items() if k != 'key_hash'} for i in items]
        return jsonify({'status': 'success', 'keys': safe})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apikey_bp.route('/api/keys/<key_id>', methods=['DELETE'])
@require_auth
def revoke_api_key(key_id):
    try:
        items = scan_table('ai1stseo-api-keys', 100)
        target = next((i for i in items if i.get('key_hash', '').startswith(key_id)), None)
        if not target:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        delete_item('ai1stseo-api-keys', {'key_hash': target['key_hash']})
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apikey_bp.route('/api/keys/<key_id>/toggle', methods=['POST'])
@require_auth
def toggle_api_key(key_id):
    try:
        items = scan_table('ai1stseo-api-keys', 100)
        target = next((i for i in items if i.get('key_hash', '').startswith(key_id)), None)
        if not target:
            return jsonify({'status': 'error', 'message': 'Not found'}), 404
        new_state = not target.get('is_active', True)
        update_item('ai1stseo-api-keys', {'key_hash': target['key_hash']}, {'is_active': new_state})
        return jsonify({'status': 'success', 'is_active': new_state})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
