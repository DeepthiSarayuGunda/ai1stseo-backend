"""
Authentication module for ai1stseo.com
Uses AWS Cognito for user management + Secrets Manager for credentials
"""

import boto3
import hmac
import hashlib
import base64
import json
import time
from functools import wraps
from flask import Blueprint, jsonify, request

auth_bp = Blueprint('auth', __name__)

# --- Secrets Manager: load Cognito config ---
_cognito_config = None

def get_cognito_config():
    """Load Cognito credentials from AWS Secrets Manager (cached)."""
    global _cognito_config
    if _cognito_config:
        return _cognito_config

    try:
        sm = boto3.client('secretsmanager', region_name='us-east-1')
        resp = sm.get_secret_value(SecretId='ai1stseo/cognito-config')
        _cognito_config = json.loads(resp['SecretString'])
        return _cognito_config
    except Exception as e:
        print(f"⚠️ Failed to load Cognito config from Secrets Manager: {e}")
        # Fallback to env vars if Secrets Manager unavailable
        import os
        _cognito_config = {
            'COGNITO_USER_POOL_ID': os.environ.get('COGNITO_USER_POOL_ID', ''),
            'COGNITO_CLIENT_ID': os.environ.get('COGNITO_CLIENT_ID', ''),
            'COGNITO_CLIENT_SECRET': os.environ.get('COGNITO_CLIENT_SECRET', ''),
            'COGNITO_REGION': os.environ.get('COGNITO_REGION', 'us-east-1')
        }
        return _cognito_config


def _get_cognito_client():
    """Get a Cognito IDP client."""
    config = get_cognito_config()
    return boto3.client('cognito-idp', region_name=config['COGNITO_REGION'])


def _compute_secret_hash(email):
    """Compute the SECRET_HASH required by Cognito when client has a secret."""
    config = get_cognito_config()
    message = email + config['COGNITO_CLIENT_ID']
    dig = hmac.new(
        config['COGNITO_CLIENT_SECRET'].encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()


def _decode_jwt_payload(token):
    """Decode JWT payload without verification (Cognito already verified it)."""
    parts = token.split('.')
    if len(parts) != 3:
        return None
    payload = parts[1]
    # Add padding
    payload += '=' * (4 - len(payload) % 4)
    decoded = base64.b64decode(payload)
    return json.loads(decoded)


def require_auth(f):
    """Decorator to protect routes — expects Authorization: Bearer <access_token>."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            client = _get_cognito_client()
            user_info = client.get_user(AccessToken=token)
            attrs = {
                attr['Name']: attr['Value']
                for attr in user_info.get('UserAttributes', [])
            }
            # Attach user info to request context
            request.cognito_user = {
                'username': user_info['Username'],
                'attributes': attrs,
                'email': attrs.get('email', user_info['Username']),
                'sub': attrs.get('sub', ''),
                'name': attrs.get('name', ''),
            }
            # Look up role from DB
            request.cognito_user['role'] = _get_user_role(attrs.get('email', ''))
            return f(*args, **kwargs)
        except client.exceptions.NotAuthorizedException:
            return jsonify({'error': 'Token expired or invalid'}), 401
        except Exception as e:
            return jsonify({'error': 'Authentication failed: {}'.format(str(e))}), 401

    return decorated


def require_admin(f):
    """Decorator — requires valid Cognito token AND admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            client = _get_cognito_client()
            user_info = client.get_user(AccessToken=token)
            attrs = {
                attr['Name']: attr['Value']
                for attr in user_info.get('UserAttributes', [])
            }
            email = attrs.get('email', user_info['Username'])
            role = _get_user_role(email)
            if role != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
            request.cognito_user = {
                'username': user_info['Username'],
                'attributes': attrs,
                'email': email,
                'sub': attrs.get('sub', ''),
                'name': attrs.get('name', ''),
                'role': role,
            }
            return f(*args, **kwargs)
        except client.exceptions.NotAuthorizedException:
            return jsonify({'error': 'Token expired or invalid'}), 401
        except Exception as e:
            return jsonify({'error': 'Authentication failed: {}'.format(str(e))}), 401

    return decorated


def _get_user_role(email):
    """Look up user role from DynamoDB. Returns 'admin' if any record for this email is admin."""
    try:
        import boto3
        from boto3.dynamodb.conditions import Key
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        table = ddb.Table('ai1stseo-users')
        resp = table.query(
            IndexName='email-index',
            KeyConditionExpression=Key('email').eq(email),
        )
        items = resp.get('Items', [])
        for item in items:
            if item.get('role') == 'admin':
                return 'admin'
        return 'member' if not items else items[0].get('role', 'member')
    except Exception:
        return 'member'


def _sync_user_to_db(email, cognito_sub, name=''):
    """Upsert user to DynamoDB on login."""
    try:
        import boto3, uuid
        from boto3.dynamodb.conditions import Key
        from datetime import datetime, timezone
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        table = ddb.Table('ai1stseo-users')
        resp = table.query(
            IndexName='email-index',
            KeyConditionExpression=Key('email').eq(email),
            Limit=1,
        )
        items = resp.get('Items', [])
        now = datetime.now(timezone.utc).isoformat()
        if items:
            table.update_item(
                Key={'userId': items[0]['userId']},
                UpdateExpression='SET last_login = :ll, cognito_sub = :cs, #n = :nm',
                ExpressionAttributeNames={'#n': 'name'},
                ExpressionAttributeValues={':ll': now, ':cs': cognito_sub, ':nm': name},
            )
            # Return admin if any record is admin
            for item in items:
                if item.get('role') == 'admin':
                    return 'admin'
            return items[0].get('role', 'member')
        else:
            table.put_item(Item={
                'userId': str(uuid.uuid4()),
                'email': email, 'cognito_sub': cognito_sub, 'name': name,
                'role': 'member', 'project_id': '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2',
                'created_at': now, 'last_login': now,
            })
            return 'member'
    except Exception:
        return 'member'
    except Exception as e:
        print("User sync failed: {}".format(e))
        return 'member'


# ============== AUTH ROUTES ==============

@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    """Register a new user with email and password."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    name = data.get('name', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        config = get_cognito_config()
        client = _get_cognito_client()

        attrs = [{'Name': 'email', 'Value': email}]
        if name:
            attrs.append({'Name': 'name', 'Value': name})

        client.sign_up(
            ClientId=config['COGNITO_CLIENT_ID'],
            SecretHash=_compute_secret_hash(email),
            Username=email,
            Password=password,
            UserAttributes=attrs
        )

        return jsonify({
            'status': 'success',
            'message': 'Account created. Check your email for a verification code.',
            'email': email
        }), 201

    except client.exceptions.UsernameExistsException:
        return jsonify({'error': 'An account with this email already exists'}), 409
    except client.exceptions.InvalidPasswordException as e:
        return jsonify({'error': 'Password must be at least 8 characters with uppercase, lowercase, number, and special character.'}), 400
    except Exception as e:
        return jsonify({'error': 'Signup failed. Please try again.'}), 500


@auth_bp.route('/api/auth/verify', methods=['POST'])
def verify_email():
    """Verify email with the confirmation code sent by Cognito."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()

    if not email or not code:
        return jsonify({'error': 'Email and verification code are required'}), 400

    try:
        config = get_cognito_config()
        client = _get_cognito_client()

        client.confirm_sign_up(
            ClientId=config['COGNITO_CLIENT_ID'],
            SecretHash=_compute_secret_hash(email),
            Username=email,
            ConfirmationCode=code
        )

        return jsonify({
            'status': 'success',
            'message': 'Email verified. You can now log in.'
        })

    except client.exceptions.CodeMismatchException:
        return jsonify({'error': 'Invalid verification code'}), 400
    except client.exceptions.ExpiredCodeException:
        return jsonify({'error': 'Verification code has expired. Request a new one.'}), 400
    except Exception as e:
        print(f"Verification error: {e}")
        return jsonify({'error': 'Verification failed. Please try again.'}), 500


@auth_bp.route('/api/auth/resend-code', methods=['POST'])
def resend_verification():
    """Resend the email verification code."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    try:
        config = get_cognito_config()
        client = _get_cognito_client()

        client.resend_confirmation_code(
            ClientId=config['COGNITO_CLIENT_ID'],
            SecretHash=_compute_secret_hash(email),
            Username=email
        )

        return jsonify({
            'status': 'success',
            'message': 'Verification code resent. Check your email.'
        })

    except Exception as e:
        print(f"Resend code error: {e}")
        return jsonify({'error': 'Failed to resend code. Please try again.'}), 500


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate user and return JWT tokens."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    try:
        config = get_cognito_config()
        client = _get_cognito_client()

        resp = client.initiate_auth(
            ClientId=config['COGNITO_CLIENT_ID'],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password,
                'SECRET_HASH': _compute_secret_hash(email)
            }
        )

        auth_result = resp['AuthenticationResult']
        # Decode the ID token to get user info
        id_payload = _decode_jwt_payload(auth_result['IdToken'])

        # Sync user to RDS and get role
        user_email = id_payload.get('email', email)
        user_sub = id_payload.get('sub', '')
        user_name = id_payload.get('name', '')
        role = _sync_user_to_db(user_email, user_sub, user_name)

        return jsonify({
            'status': 'success',
            'accessToken': auth_result['AccessToken'],
            'idToken': auth_result['IdToken'],
            'refreshToken': auth_result['RefreshToken'],
            'expiresIn': auth_result['ExpiresIn'],
            'user': {
                'email': user_email,
                'name': user_name,
                'emailVerified': id_payload.get('email_verified', False),
                'sub': user_sub,
                'role': role,
            }
        })

    except client.exceptions.NotAuthorizedException:
        return jsonify({'error': 'Incorrect email or password'}), 401
    except client.exceptions.UserNotConfirmedException:
        return jsonify({'error': 'Email not verified. Please check your email for a verification code.'}), 403
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Login failed. Please try again.'}), 500


@auth_bp.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh an expired access token using a refresh token."""
    data = request.get_json()
    refresh = data.get('refreshToken', '')
    email = data.get('email', '').strip().lower()

    if not refresh or not email:
        return jsonify({'error': 'Refresh token and email are required'}), 400

    try:
        config = get_cognito_config()
        client = _get_cognito_client()

        resp = client.initiate_auth(
            ClientId=config['COGNITO_CLIENT_ID'],
            AuthFlow='REFRESH_TOKEN_AUTH',
            AuthParameters={
                'REFRESH_TOKEN': refresh,
                'SECRET_HASH': _compute_secret_hash(email)
            }
        )

        auth_result = resp['AuthenticationResult']
        return jsonify({
            'status': 'success',
            'accessToken': auth_result['AccessToken'],
            'idToken': auth_result['IdToken'],
            'expiresIn': auth_result['ExpiresIn']
        })

    except Exception as e:
        print(f"Token refresh error: {e}")
        return jsonify({'error': 'Session expired. Please sign in again.'}), 401


@auth_bp.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Initiate password reset — sends code to email."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    try:
        config = get_cognito_config()
        client = _get_cognito_client()

        client.forgot_password(
            ClientId=config['COGNITO_CLIENT_ID'],
            SecretHash=_compute_secret_hash(email),
            Username=email
        )

        return jsonify({
            'status': 'success',
            'message': 'Password reset code sent to your email.'
        })

    except client.exceptions.UserNotFoundException:
        # Don't reveal whether the email exists
        return jsonify({
            'status': 'success',
            'message': 'If an account exists with this email, a reset code has been sent.'
        })
    except Exception as e:
        print(f"Forgot password error: {e}")
        return jsonify({'error': 'Password reset request failed. Please try again.'}), 500


@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Complete password reset with the code from email."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    new_password = data.get('newPassword', '')

    if not email or not code or not new_password:
        return jsonify({'error': 'Email, code, and new password are required'}), 400

    try:
        config = get_cognito_config()
        client = _get_cognito_client()

        client.confirm_forgot_password(
            ClientId=config['COGNITO_CLIENT_ID'],
            SecretHash=_compute_secret_hash(email),
            Username=email,
            ConfirmationCode=code,
            Password=new_password
        )

        return jsonify({
            'status': 'success',
            'message': 'Password reset successful. You can now log in.'
        })

    except client.exceptions.CodeMismatchException:
        return jsonify({'error': 'That reset code is incorrect. Please double-check and try again.'}), 400
    except client.exceptions.InvalidPasswordException as e:
        return jsonify({'error': 'Password must be at least 8 characters with uppercase, lowercase, number, and special character.'}), 400
    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({'error': 'Password reset failed. Please try again.'}), 500


@auth_bp.route('/api/auth/me', methods=['GET'])
@require_auth
def get_profile():
    """Get the current user's profile (requires auth)."""
    return jsonify({
        'status': 'success',
        'user': request.cognito_user
    })


@auth_bp.route('/api/auth/delete-account', methods=['DELETE'])
@require_auth
def delete_account():
    """Delete the current user's account (requires auth)."""
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.split(' ', 1)[1]

    try:
        client = _get_cognito_client()
        client.delete_user(AccessToken=token)

        return jsonify({
            'status': 'success',
            'message': 'Account deleted successfully.'
        })

    except Exception as e:
        print(f"Account deletion error: {e}")
        return jsonify({'error': 'Account deletion failed. Please try again.'}), 500
