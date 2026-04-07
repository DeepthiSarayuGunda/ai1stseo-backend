"""
growth/analytics_tracker.py
Internal analytics event tracker — logs events to DynamoDB.

Tracks subscribe events, page views, button clicks, and campaign
conversions. Provides query endpoints for basic reporting.

This module is part of the ai1stseo.com 5-month growth plan.
It does NOT modify any existing tables or shared logic.

Environment variables:
    GROWTH_ANALYTICS_TABLE  — DynamoDB table name (default: ai1stseo-growth-analytics)
    AWS_REGION              — AWS region (default: us-east-1)
"""

import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("GROWTH_ANALYTICS_TABLE", "ai1stseo-growth-analytics")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    return _table


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
) -> dict:
    """Log an analytics event to DynamoDB.

    Args:
        event_type: e.g. "subscribe", "page_view", "button_click", "export"
        event_data: arbitrary JSON payload (optional)
        source: e.g. "website_main", "landing_page", "social_campaign"
        session_id: browser session identifier (optional)

    Returns:
        dict with success flag and event_id.
    """
    if not event_type:
        return {"success": False, "error": "event_type is required"}

    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "event_type": event_type.strip().lower(),
        "created_at": now,
        "event_id": event_id,
    }
    if source:
        item["source"] = source.strip().lower()
    if session_id:
        item["session_id"] = session_id.strip()
    if event_data:
        # Convert floats to Decimal for DynamoDB
        cleaned = {}
        for k, v in event_data.items():
            if isinstance(v, float):
                cleaned[k] = Decimal(str(v))
            elif v is not None:
                cleaned[k] = v
        item["event_data"] = cleaned

    try:
        _get_table().put_item(Item=item)
        logger.info("track_event: type=%s id=%s", event_type, event_id)
        return {"success": True, "event_id": event_id, "created_at": now}
    except Exception as e:
        logger.error("track_event error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


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
        return {"success": False, "error": f"Database error: {e}", "events": []}


def get_summary(days: int = 7) -> dict:
    """Get event count summary grouped by event_type for the last N days.

    Scans the table and aggregates counts. Suitable for small-to-medium
    event volumes. For high-volume production, use a pre-aggregated table.
    """
    days = max(1, min(days, 90))
    cutoff = datetime.now(timezone.utc)
    from datetime import timedelta
    cutoff = (cutoff - timedelta(days=days)).isoformat()

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

        # Filter by date and aggregate
        counts = defaultdict(int)
        for item in all_items:
            if item.get("created_at", "") >= cutoff:
                counts[item["event_type"]] += 1

        total = sum(counts.values())
        return {
            "success": True,
            "days": days,
            "total_events": total,
            "by_type": dict(counts),
        }
    except Exception as e:
        logger.error("get_summary error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}
