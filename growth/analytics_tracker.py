"""
growth/analytics_tracker.py
Internal analytics event tracker — logs events to DynamoDB.

Tracks growth events (page views, signups, clicks, exports) with
UTM attribution. Provides query endpoints for basic reporting.

This module is part of the ai1stseo.com 5-month growth plan.
It does NOT modify any existing tables or shared logic.

Environment variables:
    GROWTH_ANALYTICS_TABLE  — DynamoDB table name (default: ai1stseo-growth-analytics)
    AWS_REGION              — AWS region (default: us-east-1)
"""

import logging
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("GROWTH_ANALYTICS_TABLE", "ai1stseo-growth-analytics")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EVENT_TYPES = frozenset([
    "auto_pipeline_run",
    "content_repurposed",
    "page_view",
    "email_signup_started",
    "email_signup_completed",
    "lead_magnet_clicked",
    "lead_magnet_downloaded",
    "newsletter_cta_clicked",
    "performance_ingested",
    "publish_attempted",
    "publish_simulated",
    "publish_succeeded",
    "publish_failed",
    "runner_batch_started",
    "runner_batch_completed",
    "subscriber_exported",
    "subscriber_list_viewed",
    "welcome_email_attempted",
    "welcome_email_sent",
    "welcome_email_failed",
])

MAX_STRING_LENGTH = 2048  # Truncation limit for free-text fields

# Rate limiting (in-memory, dev safety guard)
RATE_LIMIT_MAX_EVENTS = 20        # Max events per session_id per window
RATE_LIMIT_WINDOW_SECONDS = 60    # Sliding window size in seconds

# Process-local rate limit state — resets on restart, not shared across instances.
_session_event_log: dict[str, list[float]] = {}

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    return _table


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize(value: str, lowercase: bool = True) -> str:
    """Strip whitespace, optionally lowercase, truncate to MAX_STRING_LENGTH."""
    s = value.strip()
    if lowercase:
        s = s.lower()
    return s[:MAX_STRING_LENGTH]


def _check_rate_limit(session_id: str) -> bool:
    """Check whether session_id is within the rate limit (sliding window).

    Returns True if allowed, False if rate limit exceeded.
    """
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    timestamps = _session_event_log.get(session_id, [])
    timestamps = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= RATE_LIMIT_MAX_EVENTS:
        _session_event_log[session_id] = timestamps
        return False

    timestamps.append(now)
    _session_event_log[session_id] = timestamps
    return True


# ---------------------------------------------------------------------------
# Table init
# ---------------------------------------------------------------------------

def init_analytics_table() -> None:
    """Create the DynamoDB analytics table if it doesn't exist. Idempotent."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.load()
        logger.info("Analytics table %s exists (status=%s)", TABLE_NAME, table.table_status)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating analytics table %s ...", TABLE_NAME)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "event_type", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "event_type", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("Analytics table %s created", TABLE_NAME)
    except Exception as e:
        logger.warning("Analytics table init: %s", e)


# ---------------------------------------------------------------------------
# Track events
# ---------------------------------------------------------------------------

def track_event(
    event_type: str,
    event_data: dict = None,
    source: str = None,
    session_id: str = None,
    page_url: str = None,
    utm_source: str = None,
    utm_medium: str = None,
    utm_campaign: str = None,
    utm_content: str = None,
    utm_term: str = None,
) -> dict:
    """Log an analytics event to DynamoDB with optional UTM attribution.

    Args:
        event_type: Must be one of ALLOWED_EVENT_TYPES.
        event_data: Arbitrary JSON payload (optional).
        source: e.g. "website_main", "landing_page" (optional).
        session_id: Browser session identifier (optional).
        page_url: Full page URL (optional).
        utm_source, utm_medium, utm_campaign, utm_content, utm_term: UTM fields (optional).

    Returns:
        dict with success flag, event_id, and created_at.
    """
    # Validate event_type
    if not event_type:
        return {"success": False, "error": "event_type is required"}

    normalized = event_type.strip().lower()
    if normalized not in ALLOWED_EVENT_TYPES:
        return {
            "success": False,
            "error": f"Invalid event_type: {normalized}. Allowed: {sorted(ALLOWED_EVENT_TYPES)}",
        }

    # Rate limit check
    if session_id:
        if not _check_rate_limit(session_id):
            logger.warning("Rate limit exceeded for session_id=%s", session_id)
            return {"success": False, "error": "Rate limit exceeded"}
    else:
        logger.warning("track_event called without session_id — skipping rate limit check")

    # Server-generated timestamps (never from client)
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "event_type": normalized,
        "created_at": now,
        "event_id": event_id,
    }

    # Optional fields (sanitized)
    if source:
        item["source"] = _sanitize(source, lowercase=True)
    if session_id:
        item["session_id"] = _sanitize(session_id, lowercase=False)
    if page_url:
        item["page_url"] = _sanitize(page_url, lowercase=False)
    if utm_source:
        item["utm_source"] = _sanitize(utm_source, lowercase=True)
    if utm_medium:
        item["utm_medium"] = _sanitize(utm_medium, lowercase=True)
    if utm_campaign:
        item["utm_campaign"] = _sanitize(utm_campaign, lowercase=True)
    if utm_content:
        item["utm_content"] = _sanitize(utm_content, lowercase=True)
    if utm_term:
        item["utm_term"] = _sanitize(utm_term, lowercase=True)

    # Handle event_data
    if event_data:
        cleaned = {}
        for k, v in event_data.items():
            if isinstance(v, float):
                cleaned[k] = Decimal(str(v))
            elif v is not None:
                cleaned[k] = v
        item["event_data"] = cleaned

    try:
        _get_table().put_item(Item=item)
        logger.info("track_event: type=%s id=%s", normalized, event_id)
        return {"success": True, "event_id": event_id, "created_at": now}
    except Exception as e:
        logger.error("track_event error: %s", e)
        return {"success": False, "error": "Analytics unavailable"}


# ---------------------------------------------------------------------------
# Query / reporting
# ---------------------------------------------------------------------------

def get_events(
    event_type: str,
    limit: int = 50,
) -> dict:
    """Get recent events of a specific type."""
    limit = max(1, min(limit, 200))
    try:
        resp = _get_table().query(
            KeyConditionExpression=Key("event_type").eq(event_type.strip().lower()),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = resp.get("Items", [])
        for item in items:
            if isinstance(item.get("event_data"), dict):
                for k, v in item["event_data"].items():
                    if isinstance(v, Decimal):
                        item["event_data"][k] = float(v)
        return {"success": True, "events": items, "count": len(items)}
    except Exception as e:
        logger.error("get_events error: %s", e)
        return {"success": False, "error": "Analytics unavailable", "events": []}


def get_summary(days: int = 7) -> dict:
    """Get event count summary grouped by event_type, date, source, utm_source, utm_campaign.

    Scans the table and aggregates counts. Suitable for small-to-medium
    event volumes. For high-volume production, use a pre-aggregated table.
    """
    days = max(1, min(days, 90))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        all_items = []
        last_key = None
        while True:
            params = {}
            if last_key:
                params["ExclusiveStartKey"] = last_key
            resp = _get_table().scan(**params)
            all_items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break

        by_type = defaultdict(int)
        by_date = defaultdict(int)
        by_source = defaultdict(int)
        by_utm_source = defaultdict(int)
        by_utm_campaign = defaultdict(int)

        for item in all_items:
            created_at = item.get("created_at", "")
            if created_at < cutoff:
                continue

            by_type[item["event_type"]] += 1
            by_date[created_at[:10]] += 1

            src = item.get("source")
            if src:
                by_source[src] += 1

            us = item.get("utm_source")
            if us:
                by_utm_source[us] += 1

            uc = item.get("utm_campaign")
            if uc:
                by_utm_campaign[uc] += 1

        total = sum(by_type.values())
        return {
            "success": True,
            "days": days,
            "total_events": total,
            "by_type": dict(by_type),
            "by_date": dict(by_date),
            "by_source": dict(by_source),
            "by_utm_source": dict(by_utm_source),
            "by_utm_campaign": dict(by_utm_campaign),
        }
    except Exception as e:
        logger.error("get_summary error: %s", e)
        return {"success": False, "error": "Analytics unavailable"}
