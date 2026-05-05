"""
visitor_tracking/tracker_api.py
Lightweight visitor tracking — standalone Flask Blueprint.

Stores visits in-memory (with optional DynamoDB persistence).
Does NOT modify any existing modules.

Endpoints:
    POST /api/track/visit   — Record a page visit (public, no auth)
    GET  /api/track/stats   — Return visit counts (public, no auth)

Register in app.py:
    from visitor_tracking.tracker_api import register_blueprint
    register_blueprint(app)
"""

import logging
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

track_bp = Blueprint("visitor_tracking", __name__, url_prefix="/api/track")

# ---------------------------------------------------------------------------
# In-memory store — survives for the lifetime of the process.
# For production, swap with DynamoDB writes.
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_visits: list[dict] = []                    # all visit records
_daily_counts: dict[str, int] = defaultdict(int)  # "YYYY-MM-DD" -> count
_total_count: int = 0


# ---------------------------------------------------------------------------
# POST /api/track/visit
# ---------------------------------------------------------------------------

@track_bp.route("/visit", methods=["POST"])
def track_visit():
    """Record a page visit. Public endpoint — no auth required.

    Accepts JSON:
        {
            "page": "/some/path",
            "timestamp": "2026-04-30T12:00:00Z",  (optional, server generates if missing)
            "referrer": "https://google.com",
            "visitor_id": "abc-123"                (optional, server generates if missing)
        }

    Returns:
        {"success": true, "visitor_id": "..."}
    """
    global _total_count

    data = request.get_json(silent=True) or {}

    page = (data.get("page") or "").strip() or "/"
    referrer = (data.get("referrer") or "").strip()
    visitor_id = (data.get("visitor_id") or "").strip()
    client_ts = (data.get("timestamp") or "").strip()

    # Generate visitor_id if not provided
    if not visitor_id:
        visitor_id = str(uuid.uuid4())[:12]

    now = datetime.now(timezone.utc)
    server_ts = now.isoformat()
    today = now.strftime("%Y-%m-%d")

    record = {
        "visitor_id": visitor_id,
        "page": page[:500],
        "referrer": referrer[:500],
        "timestamp": server_ts,
        "client_timestamp": client_ts,
        "date": today,
    }

    with _lock:
        _visits.append(record)
        _daily_counts[today] += 1
        _total_count += 1

    logger.debug("Visit recorded: page=%s visitor=%s", page[:60], visitor_id)

    return jsonify({
        "success": True,
        "visitor_id": visitor_id,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/track/stats
# ---------------------------------------------------------------------------

@track_bp.route("/stats", methods=["GET"])
def track_stats():
    """Return visit statistics. Public endpoint — no auth required.

    Returns:
        {
            "success": true,
            "total_visits": 42,
            "visits_today": 7,
            "date": "2026-04-30",
            "top_pages": [{"page": "/", "count": 10}, ...],
            "checked_at": "2026-04-30T12:00:00+00:00"
        }
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    with _lock:
        total = _total_count
        today_count = _daily_counts.get(today, 0)

        # Top pages (from all visits)
        page_counts: dict[str, int] = defaultdict(int)
        for v in _visits:
            page_counts[v["page"]] += 1
        top_pages = sorted(
            [{"page": p, "count": c} for p, c in page_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

    return jsonify({
        "success": True,
        "total_visits": total,
        "visits_today": today_count,
        "date": today,
        "top_pages": top_pages,
        "checked_at": now.isoformat(),
    }), 200


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_blueprint(app):
    """Register the visitor tracking Blueprint with a Flask app."""
    if "visitor_tracking" not in app.blueprints:
        app.register_blueprint(track_bp)
        logger.info("Registered visitor_tracking Blueprint at /api/track")
