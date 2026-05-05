"""
social_publishing/duplicate_detector.py
Content duplicate detection — prevents the same content from being
published multiple times within a configurable time window.

Generates a SHA-256 hash from the content payload (text + image_url +
video_url), stores it in a dedicated DynamoDB table with a timestamp,
and checks for duplicates within a sliding time window.

This module is fully isolated. It does NOT modify any existing files.
Other modules can optionally import and call is_duplicate() before
publishing — the integration point is the caller's choice.

Environment variables:
    DUPLICATE_HASH_TABLE       — DynamoDB table name (default: social-content-hashes)
    DUPLICATE_WINDOW_HOURS     — Default time window in hours (default: 24)
    AWS_REGION                 — AWS region (default: us-east-1)

Usage:
    from social_publishing.duplicate_detector import is_duplicate, store_hash

    content = {"text": "Hello world!", "image_url": "https://example.com/img.png"}

    if is_duplicate(content):
        print("Skipping duplicate")
    else:
        store_hash(content)
        # proceed with publishing
"""

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("DUPLICATE_HASH_TABLE", "social-content-hashes")
DEFAULT_WINDOW_HOURS = int(os.environ.get("DUPLICATE_WINDOW_HOURS", "24"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    """Lazy singleton for the DynamoDB table resource."""
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    return _table


# ---------------------------------------------------------------------------
# Table initialisation (idempotent)
# ---------------------------------------------------------------------------

def init_hash_table() -> None:
    """Create the DynamoDB content hashes table if it doesn't exist.

    Schema:
        PK: content_hash  (S)  — SHA-256 hex digest
        SK: created_at    (S)  — ISO-8601 UTC timestamp

    The composite key allows the same hash to appear multiple times
    (one row per publish attempt), and the SK enables time-range queries
    for the duplicate window check.
    """
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.load()
        logger.info("Hash table %s exists", TABLE_NAME)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating hash table %s ...", TABLE_NAME)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "content_hash", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "content_hash", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.meta.client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
        logger.info("Hash table %s created", TABLE_NAME)
    except Exception as e:
        logger.warning("Hash table init failed: %s", e)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def generate_content_hash(content: dict) -> str:
    """Generate a deterministic SHA-256 hash from a content payload.

    The hash is built from three fields, normalised and concatenated
    in a fixed order so that equivalent payloads always produce the
    same digest regardless of key ordering or extra fields.

    Args:
        content: Dict with optional keys "text"/"caption"/"content",
                 "image_url"/"image", "video_url"/"video".

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    text = (content.get("text")
            or content.get("caption")
            or content.get("content")
            or "")
    image_url = content.get("image_url") or content.get("image") or ""
    video_url = content.get("video_url") or content.get("video") or ""

    # Normalise: strip whitespace, lowercase for case-insensitive matching
    normalised = "\n".join([
        text.strip().lower(),
        image_url.strip().lower(),
        video_url.strip().lower(),
    ])

    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def is_duplicate(content: dict, time_window_hours: int = None) -> bool:
    """Check whether identical content was already stored within the time window.

    Args:
        content: The content payload to check.
        time_window_hours: Lookback window in hours.
                           Defaults to DUPLICATE_WINDOW_HOURS env var (24).

    Returns:
        True if a matching hash exists within the window, False otherwise.
        Also returns False on any DynamoDB error (fail-open so publishing
        is never blocked by a detector outage).
    """
    if time_window_hours is None:
        time_window_hours = DEFAULT_WINDOW_HOURS

    content_hash = generate_content_hash(content)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=time_window_hours)).isoformat()

    try:
        resp = _get_table().query(
            KeyConditionExpression=(
                Key("content_hash").eq(content_hash)
                & Key("created_at").gte(cutoff)
            ),
            Limit=1,
            ScanIndexForward=False,  # newest first
        )
        items = resp.get("Items", [])
        if items:
            logger.info("Duplicate detected: hash=%s…%s last_seen=%s",
                        content_hash[:8], content_hash[-4:],
                        items[0].get("created_at"))
            return True
        return False

    except ClientError as e:
        logger.warning("Duplicate check failed (DynamoDB): %s — allowing publish", e)
        return False
    except Exception as e:
        logger.warning("Duplicate check failed: %s — allowing publish", e)
        return False


def store_hash(content: dict) -> str:
    """Store a content hash with the current timestamp.

    Call this after a successful publish (or enqueue) to record
    that this content has been processed.

    Args:
        content: The content payload that was published.

    Returns:
        The SHA-256 hex digest that was stored.
    """
    content_hash = generate_content_hash(content)
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "content_hash": content_hash,
        "created_at": now,
    }

    try:
        _get_table().put_item(Item=item)
        logger.debug("Stored hash %s…%s", content_hash[:8], content_hash[-4:])
    except ClientError as e:
        logger.warning("Failed to store content hash: %s", e)
    except Exception as e:
        logger.warning("Hash store failed (table may not exist): %s", e)

    return content_hash
