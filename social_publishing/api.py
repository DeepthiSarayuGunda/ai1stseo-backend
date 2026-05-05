"""
social_publishing/api.py
Standalone Flask Blueprint for the social publishing queue and pipeline.

Provides REST endpoints for:
  - Publish queue management (enqueue, status, flush, recover)
  - Auto-publish pipeline (content generation → queue → publish)
  - Content bridge (generate-and-publish)

This Blueprint is self-contained. It does NOT modify growth_api.py or
any other existing module. Register it in app.py with:

    from social_publishing.api import register_blueprint
    register_blueprint(app)

All endpoints require authentication via the same Cognito token pattern
used by the growth Blueprint.

Endpoints:
  POST /api/publish/queue/enqueue         — Add content to publish queue
  GET  /api/publish/queue/status          — Queue metrics
  GET  /api/publish/queue/items           — List queue items
  POST /api/publish/queue/flush           — Process all pending items
  POST /api/publish/queue/recover         — Re-queue stale DynamoDB items
  POST /api/publish/queue/worker/start    — Start background worker
  POST /api/publish/pipeline/run          — Full cycle with auto-publish
  POST /api/publish/content/submit        — Submit content for auto-publish
"""

import logging
from functools import wraps

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

publish_bp = Blueprint("social_publish", __name__, url_prefix="/api/publish")


# ---------------------------------------------------------------------------
# Auth — replicates the growth_api pattern without importing from it
# ---------------------------------------------------------------------------

def _get_require_auth():
    """Resolve require_auth from app.py, with local Cognito fallback."""
    try:
        from app import require_auth
        return require_auth
    except ImportError:
        pass

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
                import boto3
                import os
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

    return _local_require_auth


def _lazy_auth(f):
    """Resolve require_auth on first call, not at import time."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_decorator = _get_require_auth()
        return auth_decorator(f)(*args, **kwargs)
    return decorated


require_auth = _lazy_auth


# ---------------------------------------------------------------------------
# Lazy table init — runs once on first request to this Blueprint
# ---------------------------------------------------------------------------

_tables_initialized = False


@publish_bp.before_app_request
def _ensure_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    _tables_initialized = True

    try:
        from social_publishing.queue import init_queue_table
        init_queue_table()
    except Exception as e:
        logger.warning("publish queue table init deferred: %s", e)

    try:
        from social_publishing.post_logger import init_post_log_table
        init_post_log_table()
    except Exception as e:
        logger.warning("post log table init deferred: %s", e)


# ---------------------------------------------------------------------------
# Queue endpoints
# ---------------------------------------------------------------------------

@publish_bp.route("/queue/enqueue", methods=["POST"])
@require_auth
def queue_enqueue():
    """POST /api/publish/queue/enqueue — Add content to the publish queue.

    Accepts: {"text": "...", "image_url": "...", "video_url": "...",
              "platforms": [...], "scheduled_at": "...", "priority": 5}
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text and not data.get("image_url") and not data.get("video_url"):
        return jsonify({"success": False, "error": "text, image_url, or video_url required"}), 400

    from social_publishing.queue import enqueue
    content = {
        "text": text,
        "image_url": data.get("image_url"),
        "video_url": data.get("video_url"),
        "platforms": data.get("platforms"),
        "scheduled_at": data.get("scheduled_at"),
    }
    result = enqueue(content, priority=int(data.get("priority", 5)), source="api")
    return jsonify(result), 201 if result.get("success") else 500


@publish_bp.route("/queue/status", methods=["GET"])
@require_auth
def queue_status():
    """GET /api/publish/queue/status — Get publish queue metrics."""
    from social_publishing.queue import get_queue_status
    return jsonify(get_queue_status()), 200


@publish_bp.route("/queue/items", methods=["GET"])
@require_auth
def queue_items():
    """GET /api/publish/queue/items — List queue items. ?status=queued|completed|failed"""
    status = request.args.get("status")
    limit = int(request.args.get("limit", 20))
    from social_publishing.queue import get_queue_items
    items = get_queue_items(status=status, limit=limit)
    return jsonify({"success": True, "items": items, "count": len(items)}), 200


@publish_bp.route("/queue/flush", methods=["POST"])
@require_auth
def queue_flush():
    """POST /api/publish/queue/flush — Process all pending queue items now."""
    from social_publishing.queue import flush_queue
    result = flush_queue()
    return jsonify(result), 200 if result.get("success") else 500


@publish_bp.route("/queue/recover", methods=["POST"])
@require_auth
def queue_recover():
    """POST /api/publish/queue/recover — Re-queue stale items from DynamoDB."""
    from social_publishing.queue import recover_stale_items
    result = recover_stale_items()
    return jsonify(result), 200 if result.get("success") else 500


@publish_bp.route("/queue/worker/start", methods=["POST"])
@require_auth
def queue_worker_start():
    """POST /api/publish/queue/worker/start — Start the background queue worker."""
    from social_publishing.queue import start_worker, get_queue_status
    start_worker()
    return jsonify({"success": True, **get_queue_status()}), 200


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

@publish_bp.route("/pipeline/run", methods=["POST"])
@require_auth
def pipeline_run():
    """POST /api/publish/pipeline/run — Full cycle with queue-based publishing.

    Accepts: {"content_limit": 5, "auto_publish": true}
    """
    data = request.get_json(silent=True) or {}
    from social_publishing.pipeline_hook import run_full_cycle_with_auto_publish
    try:
        result = run_full_cycle_with_auto_publish(
            content_limit=int(data.get("content_limit", 5)),
            auto_publish=data.get("auto_publish", True),
        )
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error("Auto-publish pipeline failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@publish_bp.route("/content/submit", methods=["POST"])
@require_auth
def content_submit():
    """POST /api/publish/content/submit — Submit content for auto-publish.

    Accepts content from any source, auto-selects platforms, and queues.
    Accepts: {"caption": "...", "image_url": "...", "video_url": "...",
              "platforms": [...], "source": "api", "priority": 5}
    """
    data = request.get_json(silent=True) or {}
    caption = (data.get("caption") or data.get("text") or data.get("content") or "").strip()
    if not caption and not data.get("image_url") and not data.get("video_url"):
        return jsonify({"success": False, "error": "caption, image_url, or video_url required"}), 400

    from social_publishing.content_bridge import on_content_generated
    result = on_content_generated({
        "caption": caption,
        "image_url": data.get("image_url"),
        "video_url": data.get("video_url"),
        "platforms": data.get("platforms"),
        "source": data.get("source", "api"),
        "priority": int(data.get("priority", 5)),
    })
    return jsonify(result), 201 if result.get("success") else 400


# ---------------------------------------------------------------------------
# Dashboard endpoints — read-only monitoring
# ---------------------------------------------------------------------------

@publish_bp.route("/dashboard/summary", methods=["GET"])
@require_auth
def dashboard_summary():
    """GET /api/publish/dashboard/summary — Today's publishing metrics.

    Returns:
        total_posts_processed, total_success, total_failed,
        total_duplicates_skipped, current_queue_size
    """
    from datetime import datetime, timezone

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_processed = 0
    total_success = 0
    total_failed = 0
    total_duplicates = 0
    queue_size = 0

    # Post logs — count today's publish attempts
    try:
        from social_publishing.post_logger import get_logs
        logs = get_logs(limit=200)
        for log in logs:
            created = log.get("created_at", "")
            if not created.startswith(today_str):
                continue
            total_processed += 1
            if log.get("success"):
                total_success += 1
            else:
                total_failed += 1
    except Exception as e:
        logger.debug("Dashboard: post_logger read failed: %s", e)

    # Queue items — count duplicates from completed items with error marker
    try:
        from social_publishing.queue import get_queue_items
        completed = get_queue_items(status="completed", limit=200)
        for item in completed:
            created = item.get("created_at", "")
            if not created.startswith(today_str):
                continue
            if "duplicate" in (item.get("error") or "").lower():
                total_duplicates += 1
    except Exception as e:
        logger.debug("Dashboard: queue duplicate count failed: %s", e)

    # Current queue size
    try:
        from social_publishing.queue import get_queue_status
        status = get_queue_status()
        queue_size = status.get("in_memory_pending", 0)
        db_counts = status.get("db_counts", {})
        queue_size += db_counts.get("queued", 0) + db_counts.get("processing", 0)
    except Exception as e:
        logger.debug("Dashboard: queue status failed: %s", e)

    return jsonify({
        "success": True,
        "date": today_str,
        "total_posts_processed": total_processed,
        "total_success": total_success,
        "total_failed": total_failed,
        "total_duplicates_skipped": total_duplicates,
        "current_queue_size": queue_size,
    }), 200


@publish_bp.route("/dashboard/recent", methods=["GET"])
@require_auth
def dashboard_recent():
    """GET /api/publish/dashboard/recent — Last 10 processed items.

    Returns list of items with content preview, status, and timestamp.
    """
    items = []

    # Pull from post_logger (publish attempts)
    try:
        from social_publishing.post_logger import get_logs
        logs = get_logs(limit=10)
        for log in logs:
            content_raw = log.get("content", "")
            items.append({
                "content_preview": (content_raw[:80] + "...") if len(content_raw) > 80 else content_raw,
                "platform": log.get("platform", ""),
                "status": "success" if log.get("success") else "failed",
                "error": log.get("error") or None,
                "timestamp": log.get("created_at", ""),
            })
    except Exception as e:
        logger.debug("Dashboard recent: post_logger failed: %s", e)

    # Pull duplicate-skipped items from queue completed list
    try:
        from social_publishing.queue import get_queue_items
        completed = get_queue_items(status="completed", limit=20)
        for item in completed:
            if "duplicate" not in (item.get("error") or "").lower():
                continue
            items.append({
                "content_preview": (item.get("content_text", "")[:80] + "...") if len(item.get("content_text", "")) > 80 else item.get("content_text", ""),
                "platform": item.get("content_platforms", ""),
                "status": "duplicate_skipped",
                "error": None,
                "timestamp": item.get("created_at", ""),
            })
    except Exception as e:
        logger.debug("Dashboard recent: queue items failed: %s", e)

    # Sort by timestamp descending, take 10
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    items = items[:10]

    return jsonify({
        "success": True,
        "count": len(items),
        "items": items,
    }), 200


@publish_bp.route("/dashboard/system-status", methods=["GET"])
@require_auth
def dashboard_system_status():
    """GET /api/publish/dashboard/system-status — System health check.

    Returns worker state, queue state, and feature flags.
    """
    queue_running = False
    worker_active = False
    queue_pending = 0
    queue_db_counts = {}
    duplicate_detection_enabled = False

    # Queue / worker status
    try:
        from social_publishing.queue import get_queue_status
        status = get_queue_status()
        worker_active = status.get("worker_running", False)
        queue_running = worker_active or status.get("in_memory_pending", 0) > 0
        queue_pending = status.get("in_memory_pending", 0)
        queue_db_counts = status.get("db_counts", {})
    except Exception as e:
        logger.debug("Dashboard system-status: queue failed: %s", e)

    # Duplicate detection — check if the module is importable and functional
    try:
        from social_publishing.duplicate_detector import generate_content_hash
        test_hash = generate_content_hash({"text": "health_check"})
        duplicate_detection_enabled = bool(test_hash)
    except Exception:
        duplicate_detection_enabled = False

    # Publisher configuration status
    publishers = {}
    try:
        from social_publishing.config import (
            TWITTER_API_KEY, LINKEDIN_ACCESS_TOKEN,
            FACEBOOK_ACCESS_TOKEN, INSTAGRAM_ACCESS_TOKEN,
        )
        publishers = {
            "twitter": bool(TWITTER_API_KEY),
            "linkedin": bool(LINKEDIN_ACCESS_TOKEN),
            "facebook": bool(FACEBOOK_ACCESS_TOKEN),
            "instagram": bool(INSTAGRAM_ACCESS_TOKEN),
        }
    except Exception:
        pass

    return jsonify({
        "success": True,
        "queue_running": queue_running,
        "worker_active": worker_active,
        "duplicate_detection_enabled": duplicate_detection_enabled,
        "queue_pending": queue_pending,
        "queue_db_counts": queue_db_counts,
        "publishers_configured": publishers,
    }), 200


# ---------------------------------------------------------------------------
# Control endpoints — pause, resume, clear, retry
# ---------------------------------------------------------------------------

@publish_bp.route("/control/pause", methods=["POST"])
@require_auth
def control_pause():
    """POST /api/publish/control/pause — Pause queue processing.

    Signals the worker to stop picking up new items.
    Items already in the queue are preserved.
    """
    try:
        from social_publishing.queue import stop_worker, get_queue_status
        stop_worker()
        status = get_queue_status()
        return jsonify({
            "success": True,
            "status": "paused",
            "worker_active": status.get("worker_running", False),
            "items_pending": status.get("in_memory_pending", 0),
        }), 200
    except Exception as e:
        logger.error("Control pause failed: %s", e)
        return jsonify({"success": False, "status": "error", "error": str(e)}), 500


@publish_bp.route("/control/resume", methods=["POST"])
@require_auth
def control_resume():
    """POST /api/publish/control/resume — Resume queue processing.

    Restarts the worker thread. If already running, this is a no-op.
    """
    try:
        from social_publishing.queue import start_worker, get_queue_status
        start_worker()
        status = get_queue_status()
        return jsonify({
            "success": True,
            "status": "running",
            "worker_active": status.get("worker_running", False),
            "items_pending": status.get("in_memory_pending", 0),
        }), 200
    except Exception as e:
        logger.error("Control resume failed: %s", e)
        return jsonify({"success": False, "status": "error", "error": str(e)}), 500


@publish_bp.route("/control/clear-queue", methods=["POST"])
@require_auth
def control_clear_queue():
    """POST /api/publish/control/clear-queue — Remove all pending items.

    Drains the in-memory queue. Does NOT affect processed history
    or DynamoDB records of completed/failed items.
    """
    try:
        import queue as queue_mod
        from social_publishing.queue import _mem_queue

        cleared = 0
        while True:
            try:
                _mem_queue.get_nowait()
                _mem_queue.task_done()
                cleared += 1
            except queue_mod.Empty:
                break

        return jsonify({
            "success": True,
            "status": "queue_cleared",
            "cleared_count": cleared,
        }), 200
    except Exception as e:
        logger.error("Control clear-queue failed: %s", e)
        return jsonify({"success": False, "status": "error", "error": str(e)}), 500


@publish_bp.route("/control/retry-failed", methods=["POST"])
@require_auth
def control_retry_failed():
    """POST /api/publish/control/retry-failed — Requeue failed items.

    Reads items with status 'failed' from DynamoDB and re-enqueues them.
    Skips items marked as duplicate_skipped.
    """
    try:
        from social_publishing.queue import get_queue_items, enqueue

        failed_items = get_queue_items(status="failed", limit=50)
        requeued = 0

        for item in failed_items:
            # Skip duplicate-skipped items (they have "duplicate" in error)
            error_text = (item.get("error") or "").lower()
            if "duplicate" in error_text:
                continue

            # Rebuild content from stored fields
            content = {
                "text": item.get("content_text", ""),
                "platforms": [
                    p.strip() for p in (item.get("content_platforms") or "").split(",")
                    if p.strip()
                ],
            }

            result = enqueue(content, priority=3, source="retry")
            if result.get("success"):
                requeued += 1

        return jsonify({
            "success": True,
            "status": "retry_started",
            "items_requeued": requeued,
            "total_failed_found": len(failed_items),
        }), 200
    except Exception as e:
        logger.error("Control retry-failed failed: %s", e)
        return jsonify({"success": False, "status": "error", "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_blueprint(app):
    """Register the social publishing Blueprint with a Flask app.

    Call this from app.py:
        from social_publishing.api import register_blueprint
        register_blueprint(app)

    Safe to call multiple times — Blueprint registration is idempotent
    when the name hasn't been registered yet.
    """
    if "social_publish" not in app.blueprints:
        app.register_blueprint(publish_bp)
        logger.info("Registered social_publishing Blueprint at /api/publish")
