"""
growth/growth_api.py
Flask Blueprint for the ai1stseo.com growth plan.

Endpoints:
  POST /api/growth/subscribe          — Public. Add email subscriber.
  GET  /api/growth/subscribers         — INTERNAL/ADMIN. Paginated list.
  GET  /api/growth/subscribers/export  — INTERNAL/ADMIN. CSV or JSON export.

Table initialisation is lazy — runs once on first request via
before_app_request, NOT from app.py.
"""

import logging
import os
from datetime import datetime

from flask import Blueprint, Response, jsonify, request, send_from_directory

logger = logging.getLogger(__name__)

_GROWTH_DIR = os.path.dirname(os.path.abspath(__file__))

growth_bp = Blueprint("growth", __name__, url_prefix="/api/growth")


# ---------------------------------------------------------------------------
# UI page — serves growth/subscribers.html
# ---------------------------------------------------------------------------

@growth_bp.route("/ui", methods=["GET"])
def subscribers_ui():
    """Serve the subscriber capture UI page."""
    return send_from_directory(_GROWTH_DIR, "subscribers.html")


# ---------------------------------------------------------------------------
# Lazy table initialisation (runs once, not in app.py)
# ---------------------------------------------------------------------------

_table_initialized = False


@growth_bp.before_app_request
def _ensure_table():
    global _table_initialized
    if _table_initialized:
        return
    try:
        from growth.email_subscriber import init_subscriber_table

        init_subscriber_table()
        _table_initialized = True
    except Exception as e:
        logger.warning("email_subscribers table init deferred: %s", e)


# ---------------------------------------------------------------------------
# Auth helper — late-import to avoid circular dependency
# ---------------------------------------------------------------------------

def _get_require_auth():
    """Return the require_auth decorator from app.py via late import.

    If the import fails (circular or missing), fall back to a local
    Cognito token check that replicates the same behaviour.
    """
    try:
        from app import require_auth
        return require_auth
    except ImportError:
        pass

    # Fallback: minimal local auth check (same logic as app.require_auth)
    from functools import wraps

    def _local_require_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = ""
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
            if not token:
                data = request.get_json(silent=True) or {}
                token = data.get("token", "")
            if not token:
                return jsonify({"status": "error", "message": "Authentication required"}), 401
            try:
                import boto3, os
                client = boto3.client(
                    "cognito-idp",
                    region_name=os.environ.get("COGNITO_REGION", os.environ.get("AWS_REGION", "us-east-1")),
                )
                result = client.get_user(AccessToken=token)
                attrs = {a["Name"]: a["Value"] for a in result.get("UserAttributes", [])}
                request.cognito_user = {"username": result.get("Username", ""), "attributes": attrs}
                request.access_token = token
            except Exception:
                return jsonify({"status": "error", "message": "Invalid or expired token"}), 401
            return f(*args, **kwargs)
        return decorated

    logger.info("Using local auth fallback for growth endpoints")
    return _local_require_auth


def _lazy_auth(f):
    """Wrapper that resolves require_auth on first call, not at import time."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        # Late-resolve on every call (cheap after first success)
        auth_decorator = _get_require_auth()
        # Apply the real decorator and call the wrapped function
        return auth_decorator(f)(*args, **kwargs)
    return decorated


require_auth = _lazy_auth


# ---------------------------------------------------------------------------
# POST /api/growth/subscribe — Public
# ---------------------------------------------------------------------------

@growth_bp.route("/subscribe", methods=["POST"])
def subscribe():
    """Add a new email subscriber. Public endpoint — no auth required."""
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    from growth.email_subscriber import add_subscriber

    result = add_subscriber(
        email=email,
        name=data.get("name"),
        source=data.get("source", "unknown"),
        platform=data.get("platform"),
        campaign=data.get("campaign"),
        opted_in=data.get("opted_in", True),
        utm_source=data.get("utm_source"),
        utm_medium=data.get("utm_medium"),
        utm_campaign=data.get("utm_campaign"),
        utm_content=data.get("utm_content"),
    )

    if result.get("success"):
        return jsonify(result), 201
    if result.get("duplicate"):
        return jsonify(result), 409
    return jsonify(result), 400


# ---------------------------------------------------------------------------
# GET /api/growth/subscribers — INTERNAL / ADMIN (auth required)
# ---------------------------------------------------------------------------

@growth_bp.route("/subscribers", methods=["GET"])
@require_auth
def get_subscribers():
    """Paginated subscriber list with optional filters.

    INTERNAL/ADMIN — requires Authorization: Bearer <cognito_token>.
    Query params: page, per_page, source, platform, campaign.
    """
    from growth.email_subscriber import list_subscribers

    try:
        page = int(request.args.get("page", 1))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", 25))
    except (ValueError, TypeError):
        per_page = 25

    result = list_subscribers(
        page=page,
        per_page=per_page,
        source=request.args.get("source"),
        platform=request.args.get("platform"),
        campaign=request.args.get("campaign"),
    )

    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 500


# ---------------------------------------------------------------------------
# GET /api/growth/subscribers/export — INTERNAL / ADMIN (auth required)
# ---------------------------------------------------------------------------

@growth_bp.route("/subscribers/export", methods=["GET"])
@require_auth
def export():
    """Export subscribers as JSON (default) or CSV.

    INTERNAL/ADMIN — requires Authorization: Bearer <cognito_token>.
    Query params: format (json|csv), source, platform, campaign.
    Export returns ALL filtered rows (no pagination).
    """
    fmt = (request.args.get("format") or "json").strip().lower()
    if fmt not in ("csv", "json"):
        return jsonify({"success": False, "error": "Invalid format. Use csv or json"}), 400

    from growth.email_subscriber import export_subscribers

    try:
        data = export_subscribers(
            fmt=fmt,
            source=request.args.get("source"),
            platform=request.args.get("platform"),
            campaign=request.args.get("campaign"),
        )
    except Exception as e:
        logger.error("export error: %s", e)
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500

    if fmt == "csv":
        today = datetime.utcnow().strftime("%Y%m%d")
        return Response(
            data,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="subscribers_export_{today}.csv"'
            },
        )

    return jsonify(data), 200
