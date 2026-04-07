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

    try:
        from growth.analytics_tracker import init_analytics_table

        init_analytics_table()
    except Exception as e:
        logger.warning("analytics table init deferred: %s", e)

    try:
        from growth.utm_manager import init_utm_table

        init_utm_table()
    except Exception as e:
        logger.warning("utm table init deferred: %s", e)

    try:
        from growth.social_scheduler_dynamo import init_social_table

        init_social_table()
    except Exception as e:
        logger.warning("social table init deferred: %s", e)


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


# ---------------------------------------------------------------------------
# POST /api/growth/track — Public (analytics event tracking)
# ---------------------------------------------------------------------------

@growth_bp.route("/track", methods=["POST"])
def track():
    """Log an analytics event. Public endpoint.

    Accepts: {"event_type": "subscribe", "event_data": {...}, "source": "...", "session_id": "..."}
    Only event_type is required.
    """
    data = request.get_json(silent=True) or {}
    event_type = data.get("event_type")
    if not event_type:
        return jsonify({"success": False, "error": "event_type is required"}), 400

    from growth.analytics_tracker import track_event

    result = track_event(
        event_type=event_type,
        event_data=data.get("event_data"),
        source=data.get("source"),
        session_id=data.get("session_id"),
    )

    if result.get("success"):
        return jsonify(result), 201
    return jsonify(result), 500


# ---------------------------------------------------------------------------
# GET /api/growth/analytics/events — INTERNAL / ADMIN (auth required)
# ---------------------------------------------------------------------------

@growth_bp.route("/analytics/events", methods=["GET"])
@require_auth
def analytics_events():
    """Get recent events by type.

    INTERNAL/ADMIN — requires Authorization: Bearer <cognito_token>.
    Query params: event_type (required), limit (default 50).
    """
    event_type = request.args.get("event_type")
    if not event_type:
        return jsonify({"success": False, "error": "event_type query param is required"}), 400

    try:
        limit = int(request.args.get("limit", 50))
    except (ValueError, TypeError):
        limit = 50

    from growth.analytics_tracker import get_events

    result = get_events(event_type=event_type, limit=limit)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 500


# ---------------------------------------------------------------------------
# GET /api/growth/analytics/summary — INTERNAL / ADMIN (auth required)
# ---------------------------------------------------------------------------

@growth_bp.route("/analytics/summary", methods=["GET"])
@require_auth
def analytics_summary():
    """Get event count summary grouped by type.

    INTERNAL/ADMIN — requires Authorization: Bearer <cognito_token>.
    Query params: days (default 7, max 90).
    """
    try:
        days = int(request.args.get("days", 7))
    except (ValueError, TypeError):
        days = 7

    from growth.analytics_tracker import get_summary

    result = get_summary(days=days)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 500


# ---------------------------------------------------------------------------
# POST /api/growth/utm/generate — Public (UTM link generation)
# ---------------------------------------------------------------------------

@growth_bp.route("/utm/generate", methods=["POST"])
def utm_generate():
    """Generate a UTM-tagged URL. Public endpoint.

    Accepts: {"base_url": "...", "source": "...", "medium": "...", "campaign": "...", "content": "...", "term": "..."}
    Required: base_url, source, medium, campaign.
    """
    data = request.get_json(silent=True) or {}

    from growth.utm_manager import generate_utm_url

    result = generate_utm_url(
        base_url=data.get("base_url", ""),
        source=data.get("source", ""),
        medium=data.get("medium", ""),
        campaign=data.get("campaign", ""),
        content=data.get("content"),
        term=data.get("term"),
    )

    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400


# ---------------------------------------------------------------------------
# POST /api/growth/utm/campaigns — INTERNAL / ADMIN (save campaign)
# ---------------------------------------------------------------------------

@growth_bp.route("/utm/campaigns", methods=["POST"])
@require_auth
def utm_save_campaign():
    """Save a campaign definition. INTERNAL/ADMIN."""
    data = request.get_json(silent=True) or {}

    from growth.utm_manager import save_campaign

    result = save_campaign(
        name=data.get("name", ""),
        source=data.get("source", ""),
        medium=data.get("medium", ""),
        base_url=data.get("base_url", "https://ai1stseo.com"),
        content=data.get("content"),
        term=data.get("term"),
        notes=data.get("notes"),
    )

    if result.get("success"):
        return jsonify(result), 201
    return jsonify(result), 400


# ---------------------------------------------------------------------------
# GET /api/growth/utm/campaigns — INTERNAL / ADMIN (list campaigns)
# ---------------------------------------------------------------------------

@growth_bp.route("/utm/campaigns", methods=["GET"])
@require_auth
def utm_list_campaigns():
    """List saved campaigns. INTERNAL/ADMIN."""
    try:
        limit = int(request.args.get("limit", 50))
    except (ValueError, TypeError):
        limit = 50

    from growth.utm_manager import list_campaigns

    result = list_campaigns(limit=limit)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 500


# ---------------------------------------------------------------------------
# Social Scheduler (DynamoDB) — mirrors /api/social/posts but on DynamoDB
# ---------------------------------------------------------------------------

@growth_bp.route("/social/posts", methods=["GET"])
def social_list():
    """GET /api/growth/social/posts — List all scheduled posts (DynamoDB)."""
    from growth.social_scheduler_dynamo import get_posts
    result = get_posts()
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 500


@growth_bp.route("/social/posts", methods=["POST"])
def social_create():
    """POST /api/growth/social/posts — Create a scheduled post (DynamoDB).

    Accepts JSON: {"content": "...", "platforms": ["LinkedIn", "X"], "scheduled_date": "2026-04-10", "scheduled_time": "14:30"}
    """
    data = request.get_json(silent=True) or {}

    from growth.social_scheduler_dynamo import create_post

    platforms = data.get("platforms", [])
    if isinstance(platforms, str):
        platforms = [p.strip() for p in platforms.split(",")]

    result = create_post(
        content=data.get("content", ""),
        platforms=platforms,
        scheduled_date=data.get("scheduled_date", ""),
        scheduled_time=data.get("scheduled_time", ""),
        image_path=data.get("image_path"),
        status=data.get("status", "scheduled"),
    )

    if result.get("success"):
        return jsonify(result), 201
    return jsonify(result), 400


@growth_bp.route("/social/posts/<post_id>", methods=["PUT"])
def social_update(post_id):
    """PUT /api/growth/social/posts/<id> — Update a post (DynamoDB)."""
    data = request.get_json(silent=True) or {}

    from growth.social_scheduler_dynamo import update_post

    updates = {}
    for field in ["content", "platforms", "scheduled_datetime", "status", "image_path"]:
        if field in data:
            val = data[field]
            if field == "platforms" and isinstance(val, list):
                val = ", ".join(val)
            updates[field] = val

    result = update_post(post_id, updates)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400 if "not found" in result.get("error", "").lower() else 500


@growth_bp.route("/social/posts/<post_id>", methods=["DELETE"])
def social_delete(post_id):
    """DELETE /api/growth/social/posts/<id> — Delete a post (DynamoDB)."""
    from growth.social_scheduler_dynamo import delete_post

    result = delete_post(post_id)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 404 if "not found" in result.get("error", "").lower() else 500
