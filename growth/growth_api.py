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

    try:
        from growth.content_source_manager import init_content_table

        init_content_table()
    except Exception as e:
        logger.warning("content table init deferred: %s", e)

    try:
        from growth.performance_optimizer import init_scores_table

        init_scores_table()
    except Exception as e:
        logger.warning("scores table init deferred: %s", e)

    try:
        from growth.dm_engine import init_dm_table

        init_dm_table()
    except Exception as e:
        logger.warning("dm table init deferred: %s", e)

    try:
        from growth.referral_engine import init_referral_table

        init_referral_table()
    except Exception as e:
        logger.warning("referral table init deferred: %s", e)


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
        # Optionally attach lead magnet if lead_magnet_slug is provided
        lead_magnet = None
        lead_magnet_slug = data.get("lead_magnet_slug")
        if lead_magnet_slug:
            try:
                from growth.lead_magnet import get_lead_magnet_by_slug
                lm = get_lead_magnet_by_slug(lead_magnet_slug)
                if lm:
                    lead_magnet = {
                        "id": lm["id"],
                        "title": lm["title"],
                        "slug": lm["slug"],
                        "download_url": lm["download_url"],
                    }
                    result["lead_magnet"] = lead_magnet
                    try:
                        from growth.analytics_tracker import track_event
                        track_event(
                            event_type="lead_magnet_clicked",
                            event_data={"slug": lm["slug"], "id": lm["id"]},
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        # Send welcome email (non-blocking, failure-safe)
        try:
            from growth.analytics_tracker import track_event as _track
            try:
                _track(
                    event_type="welcome_email_attempted",
                    event_data={"lead_magnet_slug": lead_magnet_slug},
                )
            except Exception:
                pass

            from growth.email_platform_sync import sync_subscriber_to_email_platform
            email_result = sync_subscriber_to_email_platform({
                "email": email,
                "name": data.get("name"),
                "lead_magnet": lead_magnet,
            })

            try:
                if email_result.get("sent"):
                    _track(
                        event_type="welcome_email_sent",
                        event_data={"lead_magnet_slug": lead_magnet_slug},
                    )
                else:
                    _track(
                        event_type="welcome_email_failed",
                        event_data={
                            "error": email_result.get("error", "unknown"),
                            "lead_magnet_slug": lead_magnet_slug,
                        },
                    )
            except Exception:
                pass
        except Exception as exc:
            logger.warning("Welcome email failed for subscriber: %s", exc)

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

    Accepts JSON with event_type (required), plus optional UTM fields.
    Client-provided created_at and event_id are silently ignored.
    """
    data = request.get_json(silent=True) or {}
    event_type = data.get("event_type")
    if not event_type:
        return jsonify({"success": False, "error": "event_type is required"}), 400

    from growth.analytics_tracker import track_event

    # Pass only allowed fields — ignore created_at and event_id from client
    result = track_event(
        event_type=event_type,
        event_data=data.get("event_data"),
        source=data.get("source"),
        session_id=data.get("session_id"),
        page_url=data.get("page_url"),
        utm_source=data.get("utm_source"),
        utm_medium=data.get("utm_medium"),
        utm_campaign=data.get("utm_campaign"),
        utm_content=data.get("utm_content"),
        utm_term=data.get("utm_term"),
    )

    if result.get("success"):
        return jsonify(result), 201

    error = result.get("error", "")
    if "Rate limit exceeded" in error:
        return jsonify(result), 429
    if "Analytics unavailable" in error:
        return jsonify(result), 503
    return jsonify(result), 400


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
    if "Analytics unavailable" in result.get("error", ""):
        return jsonify(result), 503
    return jsonify(result), 500


# ---------------------------------------------------------------------------
# GET /api/growth/dashboard — INTERNAL / ADMIN (KPI summary)
# ---------------------------------------------------------------------------

@growth_bp.route("/dashboard", methods=["GET"])
@require_auth
def dashboard():
    """Aggregated growth KPI dashboard.

    INTERNAL/ADMIN — requires Authorization: Bearer <cognito_token>.
    Query params: days (int, default 7, clamped to 1-90).
    """
    try:
        days = int(request.args.get("days", 7))
    except (ValueError, TypeError):
        days = 7

    from growth.growth_dashboard import get_dashboard_kpis
    result = get_dashboard_kpis(days=days)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 500


# ---------------------------------------------------------------------------
# GET /api/growth/lead-magnet — Public (list lead magnets)
# ---------------------------------------------------------------------------

@growth_bp.route("/lead-magnet", methods=["GET"])
def lead_magnet_list():
    """List all available lead magnets. Public, no auth."""
    from growth.lead_magnet import get_lead_magnets
    magnets = get_lead_magnets()
    return jsonify({"success": True, "lead_magnets": magnets, "count": len(magnets)}), 200


# ---------------------------------------------------------------------------
# POST /api/growth/lead-magnet/download — Public (log download + return URL)
# ---------------------------------------------------------------------------

@growth_bp.route("/lead-magnet/download", methods=["POST"])
def lead_magnet_download():
    """Log a download event and return the download URL. Public, no auth.

    Accepts: {"slug": "...", "session_id": "..."}
    slug is required, session_id is optional (used for rate limiting).
    """
    data = request.get_json(silent=True) or {}
    slug = data.get("slug")
    if not slug:
        return jsonify({"success": False, "error": "slug is required"}), 400

    from growth.lead_magnet import get_lead_magnet_by_slug
    lm = get_lead_magnet_by_slug(slug)
    if not lm:
        return jsonify({"success": False, "error": "Lead magnet not found"}), 404

    # Rate limit check (reuse analytics tracker logic)
    session_id = data.get("session_id")
    if session_id:
        from growth.analytics_tracker import _check_rate_limit
        if not _check_rate_limit(session_id):
            return jsonify({"success": False, "error": "Rate limit exceeded"}), 429
    else:
        logger.warning("lead_magnet_download called without session_id")

    # Track download event (non-blocking)
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="lead_magnet_downloaded",
            event_data={"slug": lm["slug"], "id": lm["id"]},
            session_id=session_id,
        )
    except Exception:
        logger.warning("Failed to track lead_magnet_downloaded event")

    return jsonify({
        "success": True,
        "download_url": lm["download_url"],
        "title": lm["title"],
        "slug": lm["slug"],
    }), 200


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

# ---------------------------------------------------------------------------
# POST /api/growth/social/run-scheduled — INTERNAL / ADMIN (batch publish runner)
# ---------------------------------------------------------------------------

@growth_bp.route("/social/run-scheduled", methods=["POST"])
@require_auth
def social_run_scheduled():
    """Trigger batch publish of due scheduled posts. Auth required.

    Accepts: {"dry_run": true/false}
    dry_run defaults to false.
    """
    data = request.get_json(silent=True) or {}
    dry_run = bool(data.get("dry_run", False))

    try:
        from growth.publish_runner import run_scheduled_posts
        result = run_scheduled_posts(dry_run=dry_run)
        return jsonify(result), 200
    except Exception as e:
        logger.error("Run-scheduled failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/growth/social/publish — INTERNAL / ADMIN (publish via orchestrator)
# ---------------------------------------------------------------------------

@growth_bp.route("/social/publish", methods=["POST"])
@require_auth
def social_publish():
    """Publish a post via the social orchestrator. Auth required.

    Accepts: {"content": "...", "platform": "linkedin", "post_id": "...", "scheduled_at": "..."}
    content and platform are required.
    """
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    platform = (data.get("platform") or "").strip()

    if not content:
        return jsonify({"success": False, "error": "content is required"}), 400
    if not platform:
        return jsonify({"success": False, "error": "platform is required"}), 400

    from growth.social_orchestrator import publish_post
    result = publish_post({
        "content": content,
        "platform": platform,
        "post_id": data.get("post_id"),
        "scheduled_at": data.get("scheduled_at"),
    })

    if result.get("success"):
        return jsonify(result), 200
    if result.get("status") == "provider_unavailable":
        return jsonify(result), 503
    return jsonify(result), 502


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


# ---------------------------------------------------------------------------
# Content Repurposer — transform content into multi-platform posts
# ---------------------------------------------------------------------------

@growth_bp.route("/content/repurpose", methods=["POST"])
@require_auth
def content_repurpose():
    """POST /api/growth/content/repurpose — Repurpose content into platform-specific formats.

    Accepts: {"content": "...", "platforms": ["x","linkedin"], "brand_name": "...",
              "source_url": "...", "campaign": "..."}
    """
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"success": False, "error": "content is required"}), 400

    from growth.content_repurposer import repurpose_content
    result = repurpose_content(
        content=content,
        platforms=data.get("platforms"),
        brand_name=data.get("brand_name", "AI1stSEO"),
        source_url=data.get("source_url", "https://ai1stseo.com"),
        campaign=data.get("campaign", "content_repurpose"),
    )
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/content/repurpose-and-schedule", methods=["POST"])
@require_auth
def content_repurpose_and_schedule():
    """POST /api/growth/content/repurpose-and-schedule — Repurpose + schedule social posts.

    Accepts: {"content": "...", "platforms": [...], "schedule_datetime": "2026-05-01 10:00", ...}
    """
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"success": False, "error": "content is required"}), 400

    from growth.content_repurposer import repurpose_and_schedule
    result = repurpose_and_schedule(
        content=content,
        platforms=data.get("platforms"),
        brand_name=data.get("brand_name", "AI1stSEO"),
        source_url=data.get("source_url", "https://ai1stseo.com"),
        campaign=data.get("campaign", "content_repurpose"),
        schedule_datetime=data.get("schedule_datetime"),
    )
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/content/repurpose-and-publish", methods=["POST"])
@require_auth
def content_repurpose_and_publish():
    """POST /api/growth/content/repurpose-and-publish — Repurpose + immediately publish.

    Accepts: {"content": "...", "platforms": [...], ...}
    """
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"success": False, "error": "content is required"}), 400

    from growth.content_repurposer import repurpose_and_publish
    result = repurpose_and_publish(
        content=content,
        platforms=data.get("platforms"),
        brand_name=data.get("brand_name", "AI1stSEO"),
        source_url=data.get("source_url", "https://ai1stseo.com"),
        campaign=data.get("campaign", "content_repurpose"),
    )
    return jsonify(result), 200 if result.get("success") else 500


# ---------------------------------------------------------------------------
# Content Source Manager — queue content for the pipeline
# ---------------------------------------------------------------------------

@growth_bp.route("/content/sources", methods=["POST"])
@require_auth
def content_add_source():
    """POST /api/growth/content/sources — Add content to the pipeline queue.

    Accepts: {"content": "...", "title": "...", "source_type": "blog",
              "source_url": "...", "platforms": ["x","linkedin"], "campaign": "..."}
    """
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"success": False, "error": "content is required"}), 400

    from growth.content_source_manager import add_content
    result = add_content(
        content=content,
        title=data.get("title", ""),
        source_type=data.get("source_type", "manual"),
        source_url=data.get("source_url", "https://ai1stseo.com"),
        platforms=data.get("platforms"),
        campaign=data.get("campaign", "content_repurpose"),
    )
    return jsonify(result), 201 if result.get("success") else 400


@growth_bp.route("/content/sources", methods=["GET"])
@require_auth
def content_list_sources():
    """GET /api/growth/content/sources — List content items. ?status=new|processed|failed"""
    status = request.args.get("status")
    from growth.content_source_manager import list_content
    result = list_content(status=status)
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/content/sources/<content_id>", methods=["GET"])
@require_auth
def content_get_source(content_id):
    """GET /api/growth/content/sources/<id> — Get a single content item."""
    from growth.content_source_manager import get_content
    result = get_content(content_id)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 404


# ---------------------------------------------------------------------------
# Content Pipeline — automated content production
# ---------------------------------------------------------------------------

@growth_bp.route("/content/pipeline/run", methods=["POST"])
@require_auth
def content_pipeline_run():
    """POST /api/growth/content/pipeline/run — Run the content pipeline.

    Accepts: {"limit": 5, "dry_run": false}
    Fetches unprocessed content, repurposes it, and schedules social posts.
    """
    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit", 5))
    dry_run = bool(data.get("dry_run", False))

    from growth.content_pipeline import run_content_pipeline
    try:
        result = run_content_pipeline(limit=limit, dry_run=dry_run)
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Pipeline run failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@growth_bp.route("/content/pipeline/import-seeds", methods=["POST"])
@require_auth
def content_pipeline_import_seeds():
    """POST /api/growth/content/pipeline/import-seeds — Import social_media_posts.json into pipeline.

    One-time import of existing seed content into the content source table.
    """
    from growth.content_pipeline import import_json_to_pipeline
    try:
        result = import_json_to_pipeline()
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Seed import failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Performance Optimizer — scoring, analysis, and feedback loop
# ---------------------------------------------------------------------------

@growth_bp.route("/performance/score", methods=["POST"])
@require_auth
def performance_score_post():
    """POST /api/growth/performance/score — Score a post's performance.

    Accepts: {"post_id": "...", "clicks": 10, "impressions": 500,
              "engagements": 25, "conversions": 2, "platform": "x",
              "content_type": "thread"}
    """
    data = request.get_json(silent=True) or {}
    post_id = data.get("post_id", "").strip()
    if not post_id:
        return jsonify({"success": False, "error": "post_id is required"}), 400

    from growth.performance_optimizer import score_post
    result = score_post(post_id, data)
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/performance/top-posts", methods=["GET"])
@require_auth
def performance_top_posts():
    """GET /api/growth/performance/top-posts — Get top performing posts. ?limit=10"""
    try:
        limit = int(request.args.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10

    from growth.performance_optimizer import get_top_posts
    result = get_top_posts(limit=limit)
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/performance/platforms", methods=["GET"])
@require_auth
def performance_platforms():
    """GET /api/growth/performance/platforms — Platform performance analysis."""
    from growth.performance_optimizer import analyze_platform_performance
    result = analyze_platform_performance()
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/performance/patterns", methods=["GET"])
@require_auth
def performance_patterns():
    """GET /api/growth/performance/patterns — Content pattern analysis."""
    from growth.performance_optimizer import analyze_content_patterns
    result = analyze_content_patterns()
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/performance/signals", methods=["GET"])
@require_auth
def performance_signals():
    """GET /api/growth/performance/signals — Optimization signals for the pipeline."""
    from growth.performance_optimizer import generate_optimization_signals
    result = generate_optimization_signals()
    return jsonify(result), 200


@growth_bp.route("/performance/dashboard", methods=["GET"])
@require_auth
def performance_dashboard():
    """GET /api/growth/performance/dashboard — Full performance dashboard.

    ?days=30 (default 30, max 90)
    """
    try:
        days = int(request.args.get("days", 30))
    except (ValueError, TypeError):
        days = 30

    from growth.performance_optimizer import get_performance_dashboard
    result = get_performance_dashboard(days=days)
    return jsonify(result), 200 if result.get("success") else 500


# ---------------------------------------------------------------------------
# Auto Pipeline Runner — full growth automation cycle
# ---------------------------------------------------------------------------

@growth_bp.route("/automation/run", methods=["POST"])
@require_auth
def automation_run():
    """POST /api/growth/automation/run — Run the full growth cycle.

    Steps: content pipeline → publish (with fallback) → performance ingest.
    Accepts: {"content_limit": 5, "publish_dry_run": false, "ingest_mode": "auto"}
    """
    data = request.get_json(silent=True) or {}

    from growth.auto_pipeline_runner import run_full_cycle
    try:
        result = run_full_cycle(
            content_limit=int(data.get("content_limit", 5)),
            publish_dry_run=bool(data.get("publish_dry_run", False)),
            ingest_mode=data.get("ingest_mode", "auto"),
            run_discovery=bool(data.get("run_discovery", False)),
            run_ugc=bool(data.get("run_ugc", False)),
            run_lifecycle=bool(data.get("run_lifecycle", False)),
        )
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Automation run failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@growth_bp.route("/automation/status", methods=["GET"])
@require_auth
def automation_status():
    """GET /api/growth/automation/status — Check if pipeline is running."""
    from growth.auto_pipeline_runner import get_run_status
    return jsonify(get_run_status()), 200


# ---------------------------------------------------------------------------
# Performance Ingestor — auto-score published posts
# ---------------------------------------------------------------------------

@growth_bp.route("/performance/ingest", methods=["POST"])
@require_auth
def performance_ingest():
    """POST /api/growth/performance/ingest — Ingest performance metrics.

    Accepts: {"mode": "auto"} — "auto", "simulate", or "real"
    """
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "auto")

    from growth.performance_ingestor import ingest_performance
    try:
        result = ingest_performance(mode=mode)
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Performance ingest failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Publisher Fallback — publish with simulation fallback
# ---------------------------------------------------------------------------

@growth_bp.route("/social/publish-with-fallback", methods=["POST"])
@require_auth
def social_publish_fallback():
    """POST /api/growth/social/publish-with-fallback — Publish with simulation fallback.

    Same as /social/publish but simulates if no API keys configured.
    Accepts: {"content": "...", "platform": "linkedin", "post_id": "...", "scheduled_at": "..."}
    """
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    platform = (data.get("platform") or "").strip()

    if not content:
        return jsonify({"success": False, "error": "content is required"}), 400
    if not platform:
        return jsonify({"success": False, "error": "platform is required"}), 400

    from growth.publisher_fallback import publish_with_fallback
    result = publish_with_fallback({
        "content": content,
        "platform": platform,
        "post_id": data.get("post_id"),
        "scheduled_at": data.get("scheduled_at"),
    })
    return jsonify(result), 200 if result.get("success") else 502


@growth_bp.route("/social/run-scheduled-fallback", methods=["POST"])
@require_auth
def social_run_scheduled_fallback():
    """POST /api/growth/social/run-scheduled-fallback — Batch publish with fallback.

    Same as /social/run-scheduled but simulates when no API keys.
    Accepts: {"dry_run": false}
    """
    data = request.get_json(silent=True) or {}
    dry_run = bool(data.get("dry_run", False))

    from growth.publisher_fallback import run_scheduled_with_fallback
    try:
        result = run_scheduled_with_fallback(dry_run=dry_run)
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Scheduled fallback failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Content Discovery — auto-feed pipeline from Reddit + trending
# ---------------------------------------------------------------------------

@growth_bp.route("/discovery/run", methods=["POST"])
@require_auth
def discovery_run():
    """POST /api/growth/discovery/run — Run content discovery cycle.

    Accepts: {"subreddits": [...], "limit": 10, "min_relevance": 0.2}
    """
    data = request.get_json(silent=True) or {}

    from growth.content_discovery import run_discovery
    try:
        result = run_discovery(
            subreddits=data.get("subreddits"),
            limit=int(data.get("limit", 10)),
            min_relevance=float(data.get("min_relevance", 0.2)),
        )
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Discovery run failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# UGC Collector — turn mentions into content
# ---------------------------------------------------------------------------

@growth_bp.route("/ugc/collect", methods=["POST"])
@require_auth
def ugc_collect():
    """POST /api/growth/ugc/collect — Run UGC collection cycle."""
    from growth.ugc_collector import run_ugc_collection
    try:
        result = run_ugc_collection()
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("UGC collection failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# DM Engine — engagement messaging
# ---------------------------------------------------------------------------

@growth_bp.route("/dm/welcome", methods=["POST"])
@require_auth
def dm_welcome():
    """POST /api/growth/dm/welcome — Queue welcome DMs for new followers.

    Accepts: {"followers": ["user1", "user2"], "platform": "x"}
    """
    data = request.get_json(silent=True) or {}
    followers = data.get("followers", [])
    if not followers:
        return jsonify({"success": False, "error": "followers list required"}), 400

    from growth.dm_engine import process_new_followers
    result = process_new_followers(followers, data.get("platform", "x"))
    return jsonify(result), 200


@growth_bp.route("/dm/engage", methods=["POST"])
@require_auth
def dm_engage():
    """POST /api/growth/dm/engage — Queue engagement DMs.

    Accepts: {"users": [{"user": "name", "topic": "AI SEO"}], "platform": "x"}
    """
    data = request.get_json(silent=True) or {}
    users = data.get("users", [])
    if not users:
        return jsonify({"success": False, "error": "users list required"}), 400

    from growth.dm_engine import process_engaged_users
    result = process_engaged_users(users, data.get("platform", "x"))
    return jsonify(result), 200


@growth_bp.route("/dm/queue", methods=["GET"])
@require_auth
def dm_queue():
    """GET /api/growth/dm/queue — List queued DMs. ?status=queued"""
    from growth.dm_engine import get_queued_dms
    status = request.args.get("status", "queued")
    result = get_queued_dms(status=status)
    return jsonify(result), 200 if result.get("success") else 500


# ---------------------------------------------------------------------------
# Referral Engine — viral email growth
# ---------------------------------------------------------------------------

@growth_bp.route("/referral/link", methods=["POST"])
@require_auth
def referral_link():
    """POST /api/growth/referral/link — Generate referral link.

    Accepts: {"user_id": "subscriber_email_or_id"}
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400

    from growth.referral_engine import generate_referral_link
    result = generate_referral_link(user_id)
    return jsonify(result), 200 if result.get("success") else 400


@growth_bp.route("/referral/track", methods=["POST"])
def referral_track():
    """POST /api/growth/referral/track — Track a referral conversion. Public.

    Accepts: {"ref_code": "abc123", "new_user_email": "..."}
    """
    data = request.get_json(silent=True) or {}
    ref_code = data.get("ref_code", "").strip()
    email = data.get("new_user_email", "").strip()
    if not ref_code or not email:
        return jsonify({"success": False, "error": "ref_code and new_user_email required"}), 400

    from growth.referral_engine import track_referral
    result = track_referral(ref_code, email)
    return jsonify(result), 200 if result.get("success") else 400


@growth_bp.route("/referral/stats/<user_id>", methods=["GET"])
@require_auth
def referral_stats(user_id):
    """GET /api/growth/referral/stats/<user_id> — Get referral stats."""
    from growth.referral_engine import get_referral_count
    result = get_referral_count(user_id)
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/referral/leaderboard", methods=["GET"])
@require_auth
def referral_leaderboard():
    """GET /api/growth/referral/leaderboard — Top referrers."""
    from growth.referral_engine import get_leaderboard
    result = get_leaderboard()
    return jsonify(result), 200 if result.get("success") else 500


# ---------------------------------------------------------------------------
# Email Automation — newsletters, segmentation, re-engagement
# ---------------------------------------------------------------------------

@growth_bp.route("/email/newsletter", methods=["POST"])
@require_auth
def email_newsletter():
    """POST /api/growth/email/newsletter — Send weekly newsletter."""
    from growth.email_automation_engine import send_weekly_newsletter
    try:
        result = send_weekly_newsletter()
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Newsletter failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@growth_bp.route("/email/newsletter/preview", methods=["GET"])
@require_auth
def email_newsletter_preview():
    """GET /api/growth/email/newsletter/preview — Preview newsletter content."""
    from growth.email_automation_engine import generate_newsletter_content
    result = generate_newsletter_content()
    return jsonify(result), 200


@growth_bp.route("/email/segments", methods=["GET"])
@require_auth
def email_segments():
    """GET /api/growth/email/segments — Get subscriber segmentation."""
    from growth.email_automation_engine import segment_subscribers
    result = segment_subscribers()
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/email/reengage", methods=["POST"])
@require_auth
def email_reengage():
    """POST /api/growth/email/reengage — Send re-engagement emails to inactive subscribers."""
    from growth.email_automation_engine import send_reengagement
    try:
        result = send_reengagement()
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Re-engagement failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Lifecycle Engine — automated user engagement
# ---------------------------------------------------------------------------

@growth_bp.route("/lifecycle/run", methods=["POST"])
@require_auth
def lifecycle_run():
    """POST /api/growth/lifecycle/run — Run lifecycle engine for all subscribers."""
    from growth.lifecycle_engine import run_lifecycle_cycle
    try:
        result = run_lifecycle_cycle()
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Lifecycle run failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Content Prioritizer — what to create next
# ---------------------------------------------------------------------------

@growth_bp.route("/content/priorities", methods=["GET"])
@require_auth
def content_priorities():
    """GET /api/growth/content/priorities — Get content recommendations."""
    try:
        count = int(request.args.get("count", 5))
    except (ValueError, TypeError):
        count = 5

    from growth.content_prioritizer import recommend_next_content
    result = recommend_next_content(count=count)
    return jsonify(result), 200 if result.get("success") else 500


@growth_bp.route("/content/type-rankings", methods=["GET"])
@require_auth
def content_type_rankings():
    """GET /api/growth/content/type-rankings — Content type performance rankings."""
    from growth.content_prioritizer import rank_content_types
    result = rank_content_types()
    return jsonify(result), 200


@growth_bp.route("/content/platform-weights", methods=["GET"])
@require_auth
def content_platform_weights():
    """GET /api/growth/content/platform-weights — Platform allocation weights."""
    from growth.content_prioritizer import adjust_platform_weights
    result = adjust_platform_weights()
    return jsonify(result), 200
