"""
growth/email_subscriber.py
Email Subscriber Capture — core module.

Handles validation, sanitization, CRUD, export, and table initialization
for the email_subscribers DynamoDB table. Zero Flask dependencies.

This module is part of the ai1stseo.com 5-month growth plan.
It does NOT modify any existing tables or shared logic.
"""

import csv
import io
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

TABLE_NAME = os.environ.get("GROWTH_SUBSCRIBERS_TABLE", "ai1stseo-email-subscribers")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

CSV_HEADERS = [
    "id", "email", "name", "source", "platform",
    "campaign", "utm_source", "utm_medium", "utm_campaign", "utm_content",
    "opted_in", "status", "subscribed_at",
]

_dynamodb = None
_table = None


def _get_table():
    """Get the DynamoDB table resource (cached)."""
    global _dynamodb, _table
    if _table is None:
        _dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        _table = _dynamodb.Table(TABLE_NAME)
    return _table


# ---------------------------------------------------------------------------
# Table initialisation — creates DynamoDB table if it doesn't exist
# ---------------------------------------------------------------------------

def init_subscriber_table() -> None:
    """Create the DynamoDB table if it doesn't exist. Idempotent."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = _dynamodb.Table(TABLE_NAME)
        table.load()
        logger.info("DynamoDB table %s exists (status=%s)", TABLE_NAME, table.table_status)
    except _dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating DynamoDB table %s ...", TABLE_NAME)
        table = _dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "email", "AttributeType": "S"},
                {"AttributeName": "source", "AttributeType": "S"},
                {"AttributeName": "subscribed_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "source-subscribed_at-index",
                    "KeySchema": [
                        {"AttributeName": "source", "KeyType": "HASH"},
                        {"AttributeName": "subscribed_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        logger.info("DynamoDB table %s created", TABLE_NAME)
    except Exception as e:
        logger.warning("DynamoDB table init check: %s", e)


# ---------------------------------------------------------------------------
# Validation & sanitisation helpers
# ---------------------------------------------------------------------------

def validate_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def sanitize_input(value, max_length: int = 255):
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:max_length]


def normalize_filter(value):
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def add_subscriber(
    email: str,
    name=None,
    source: str = "unknown",
    platform=None,
    campaign=None,
    opted_in: bool = True,
    utm_source=None,
    utm_medium=None,
    utm_campaign=None,
    utm_content=None,
) -> dict:
    """Validate, sanitise, and insert a subscriber. Returns result dict."""
    if not validate_email(email):
        return {"success": False, "error": "Invalid email format"}

    clean_email = email.strip().lower()
    clean_name = sanitize_input(name)
    clean_source = (sanitize_input(source, 100) or "unknown").lower()
    clean_platform = sanitize_input(platform, 100)
    if clean_platform:
        clean_platform = clean_platform.lower()
    clean_campaign = sanitize_input(campaign)
    if clean_campaign:
        clean_campaign = clean_campaign.lower()

    now = datetime.now(timezone.utc).isoformat()
    subscriber_id = str(uuid.uuid4())

    item = {
        "email": clean_email,
        "id": subscriber_id,
        "source": clean_source,
        "opted_in": opted_in,
        "status": "active",
        "subscribed_at": now,
        "updated_at": now,
    }
    if clean_name:
        item["name"] = clean_name
    if clean_platform:
        item["platform"] = clean_platform
    if clean_campaign:
        item["campaign"] = clean_campaign
    if sanitize_input(utm_source):
        item["utm_source"] = sanitize_input(utm_source)
    if sanitize_input(utm_medium):
        item["utm_medium"] = sanitize_input(utm_medium)
    if sanitize_input(utm_campaign):
        item["utm_campaign"] = sanitize_input(utm_campaign)
    if sanitize_input(utm_content):
        item["utm_content"] = sanitize_input(utm_content)

    try:
        table = _get_table()
        # Conditional put — fails if email already exists (duplicate protection)
        table.put_item(
            Item=item,
            ConditionExpression=Attr("email").not_exists(),
        )

        # Integration hook
        try:
            from growth.email_platform_sync import sync_subscriber_to_email_platform
            sync_subscriber_to_email_platform({
                "email": clean_email,
                "name": clean_name,
                "source": clean_source,
                "platform": clean_platform,
                "campaign": clean_campaign,
                "subscriber_id": subscriber_id,
                "subscribed_at": now,
            })
        except Exception as sync_err:
            logger.warning("email platform sync failed (non-blocking): %s", sync_err)

        return {
            "success": True,
            "subscriber": {
                "id": subscriber_id,
                "email": clean_email,
                "subscribed_at": now,
            },
        }
    except _get_table().meta.client.exceptions.ConditionalCheckFailedException:
        return {"success": False, "error": "Email already subscribed", "duplicate": True}
    except Exception as e:
        logger.error("add_subscriber error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


def list_subscribers(
    page: int = 1,
    per_page: int = 25,
    source=None,
    platform=None,
    campaign=None,
) -> dict:
    """Paginated subscriber list with optional filters."""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    try:
        table = _get_table()

        # Build filter expression
        filters = []
        expr_values = {}
        expr_names = {}
        idx = 0
        for val, col in [
            (normalize_filter(source), "source"),
            (normalize_filter(platform), "platform"),
            (normalize_filter(campaign), "campaign"),
        ]:
            if val:
                placeholder = f":fv{idx}"
                name_ph = f"#fn{idx}"
                filters.append(f"{name_ph} = {placeholder}")
                expr_values[placeholder] = val
                expr_names[name_ph] = col
                idx += 1

        scan_params = {}
        if filters:
            scan_params["FilterExpression"] = " AND ".join(filters)
            scan_params["ExpressionAttributeValues"] = expr_values
            scan_params["ExpressionAttributeNames"] = expr_names

        # Scan all matching items (DynamoDB doesn't support SQL-style OFFSET)
        all_items = []
        last_key = None
        while True:
            if last_key:
                scan_params["ExclusiveStartKey"] = last_key
            resp = table.scan(**scan_params)
            all_items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break

        # Sort by subscribed_at descending
        all_items.sort(key=lambda x: x.get("subscribed_at", ""), reverse=True)

        total = len(all_items)
        start = (page - 1) * per_page
        page_items = all_items[start : start + per_page]

        # Serialize
        for r in page_items:
            if isinstance(r.get("opted_in"), Decimal):
                r["opted_in"] = bool(r["opted_in"])

        return {
            "success": True,
            "subscribers": page_items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }
    except Exception as e:
        logger.error("list_subscribers error: %s", e)
        return {"success": False, "error": f"Database error: {e}", "subscribers": []}


def export_subscribers(
    fmt: str = "json",
    source=None,
    platform=None,
    campaign=None,
):
    """Export ALL matching subscribers. Returns CSV string or list of dicts."""
    result = list_subscribers(page=1, per_page=10000, source=source,
                              platform=platform, campaign=campaign)
    rows = result.get("subscribers", [])

    # Normalize for CSV — ensure all headers present
    for r in rows:
        for h in CSV_HEADERS:
            if h not in r:
                r[h] = ""
        if isinstance(r.get("opted_in"), (Decimal, bool)):
            r["opted_in"] = str(r["opted_in"])

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    return rows
