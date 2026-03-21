"""
Cognito authentication helper for Site Monitor.
Validates Cognito access tokens and provides auth decorators.
Mirrors backend/auth.py patterns but lightweight for the monitor service.
"""
import os
import json
import hmac
import hashlib
import base64
from functools import wraps
from datetime import datetime

import boto3
from flask import request, jsonify

# --- Cognito config (env vars, with Secrets Manager fallback) ---
_cognito_config = None


def get_cognito_config():
    """Load Cognito credentials — env vars first, Secrets Manager fallback."""
    global _cognito_config
    if _cognito_config:
        return _cognito_config

    # Try Secrets Manager
    try:
        sm = boto3.client("secretsmanager", region_name="us-east-1")
        resp = sm.get_secret_value(SecretId="ai1stseo/cognito-config")
        _cognito_config = json.loads(resp["SecretString"])
        return _cognito_config
    except Exception:
        pass

    # Fallback to env vars
    _cognito_config = {
        "COGNITO_USER_POOL_ID": os.environ.get("COGNITO_USER_POOL_ID", ""),
        "COGNITO_CLIENT_ID": os.environ.get("COGNITO_CLIENT_ID", ""),
        "COGNITO_CLIENT_SECRET": os.environ.get("COGNITO_CLIENT_SECRET", ""),
        "COGNITO_REGION": os.environ.get("COGNITO_REGION", "us-east-1"),
    }
    return _cognito_config


def _get_cognito_client():
    config = get_cognito_config()
    return boto3.client("cognito-idp", region_name=config["COGNITO_REGION"])


def _compute_secret_hash(email):
    config = get_cognito_config()
    message = email + config["COGNITO_CLIENT_ID"]
    dig = hmac.new(
        config["COGNITO_CLIENT_SECRET"].encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()


def _decode_jwt_payload(token):
    """Decode JWT payload without verification (Cognito already verified)."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    payload += "=" * (4 - len(payload) % 4)
    decoded = base64.b64decode(payload)
    return json.loads(decoded)


def validate_token(req):
    """Extract and validate a Cognito access token from the request.
    Returns user info dict or None."""
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        client = _get_cognito_client()
        user_info = client.get_user(AccessToken=token)
        attrs = {a["Name"]: a["Value"] for a in user_info.get("UserAttributes", [])}
        return {
            "username": user_info["Username"],
            "email": attrs.get("email", user_info["Username"]),
            "name": attrs.get("name", ""),
            "email_verified": attrs.get("email_verified", "false") == "true",
            "sub": attrs.get("sub", ""),
        }
    except Exception:
        return None


def require_auth(f):
    """Decorator — requires valid Cognito access token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = validate_token(request)
        if not user:
            return jsonify({"status": "error", "message": "Not authenticated"}), 401
        request.cognito_user = user
        return f(*args, **kwargs)
    return decorated


# --- Auth routes (signup, login, verify, etc.) ---
# These proxy to Cognito so the monitor frontend can use the same auth flow.

def signup(data):
    """Register a new user via Cognito."""
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "")
    if not email or not password:
        return {"status": "error", "message": "Email and password required"}, 400
    try:
        config = get_cognito_config()
        client = _get_cognito_client()
        attrs = [{"Name": "email", "Value": email}]
        if name:
            attrs.append({"Name": "name", "Value": name})
        client.sign_up(
            ClientId=config["COGNITO_CLIENT_ID"],
            SecretHash=_compute_secret_hash(email),
            Username=email, Password=password, UserAttributes=attrs,
        )
        return {"status": "success", "message": "Account created. Check email for verification code."}, 201
    except client.exceptions.UsernameExistsException:
        return {"status": "error", "message": "Email already registered"}, 409
    except client.exceptions.InvalidPasswordException:
        return {"status": "error", "message": "Password needs 8+ chars, upper, lower, number, special char."}, 400
    except Exception as e:
        return {"status": "error", "message": "Signup failed: {}".format(e)}, 500


def login(data):
    """Authenticate via Cognito and return tokens."""
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return {"status": "error", "message": "Email and password required"}, 400
    try:
        config = get_cognito_config()
        client = _get_cognito_client()
        resp = client.initiate_auth(
            ClientId=config["COGNITO_CLIENT_ID"],
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": email, "PASSWORD": password,
                "SECRET_HASH": _compute_secret_hash(email),
            },
        )
        auth_result = resp["AuthenticationResult"]
        id_payload = _decode_jwt_payload(auth_result["IdToken"])
        return {
            "status": "success",
            "accessToken": auth_result["AccessToken"],
            "idToken": auth_result["IdToken"],
            "refreshToken": auth_result["RefreshToken"],
            "expiresIn": auth_result["ExpiresIn"],
            "user": {
                "email": id_payload.get("email", email),
                "name": id_payload.get("name", ""),
                "emailVerified": id_payload.get("email_verified", False),
                "sub": id_payload.get("sub", ""),
            },
        }, 200
    except Exception as e:
        err_name = type(e).__name__
        if "NotAuthorizedException" in err_name:
            return {"status": "error", "message": "Incorrect email or password"}, 401
        if "UserNotConfirmedException" in err_name:
            return {"status": "error", "message": "Email not verified. Check your email."}, 403
        return {"status": "error", "message": "Login failed"}, 500


def verify_email(data):
    """Confirm signup with verification code."""
    email = data.get("email", "").strip().lower()
    code = data.get("code", "").strip()
    if not email or not code:
        return {"status": "error", "message": "Email and code required"}, 400
    try:
        config = get_cognito_config()
        client = _get_cognito_client()
        client.confirm_sign_up(
            ClientId=config["COGNITO_CLIENT_ID"],
            SecretHash=_compute_secret_hash(email),
            Username=email, ConfirmationCode=code,
        )
        return {"status": "success", "message": "Email verified. You can now log in."}, 200
    except Exception as e:
        err_name = type(e).__name__
        if "CodeMismatchException" in err_name:
            return {"status": "error", "message": "Invalid verification code"}, 400
        if "ExpiredCodeException" in err_name:
            return {"status": "error", "message": "Code expired. Request a new one."}, 400
        return {"status": "error", "message": "Verification failed"}, 500


def resend_code(data):
    """Resend verification code."""
    email = data.get("email", "").strip().lower()
    if not email:
        return {"status": "error", "message": "Email required"}, 400
    try:
        config = get_cognito_config()
        client = _get_cognito_client()
        client.resend_confirmation_code(
            ClientId=config["COGNITO_CLIENT_ID"],
            SecretHash=_compute_secret_hash(email),
            Username=email,
        )
        return {"status": "success", "message": "Code resent."}, 200
    except Exception:
        return {"status": "error", "message": "Failed to resend code"}, 500


def forgot_password(data):
    """Initiate password reset."""
    email = data.get("email", "").strip().lower()
    if not email:
        return {"status": "error", "message": "Email required"}, 400
    try:
        config = get_cognito_config()
        client = _get_cognito_client()
        client.forgot_password(
            ClientId=config["COGNITO_CLIENT_ID"],
            SecretHash=_compute_secret_hash(email),
            Username=email,
        )
        return {"status": "success", "message": "Reset code sent to your email."}, 200
    except Exception:
        return {"status": "success", "message": "If an account exists, a reset code was sent."}, 200


def reset_password(data):
    """Complete password reset."""
    email = data.get("email", "").strip().lower()
    code = data.get("code", "").strip()
    new_password = data.get("newPassword", "")
    if not email or not code or not new_password:
        return {"status": "error", "message": "Email, code, and new password required"}, 400
    try:
        config = get_cognito_config()
        client = _get_cognito_client()
        client.confirm_forgot_password(
            ClientId=config["COGNITO_CLIENT_ID"],
            SecretHash=_compute_secret_hash(email),
            Username=email, ConfirmationCode=code, Password=new_password,
        )
        return {"status": "success", "message": "Password reset. You can now log in."}, 200
    except Exception as e:
        err_name = type(e).__name__
        if "CodeMismatchException" in err_name:
            return {"status": "error", "message": "Invalid reset code"}, 400
        return {"status": "error", "message": "Reset failed"}, 500
