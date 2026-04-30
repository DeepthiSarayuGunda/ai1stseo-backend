"""
growth/content_source_manager.py
Content Source Manager — feeds the repurposing pipeline.

Manages a DynamoDB table of content items (blog posts, articles, manual input)
that flow through the repurposer → scheduler → publisher pipeline.

Each content item has a processing status:
    new         — just added, not yet repurposed
    processing  — currently being repurposed
    processed   — repurposed and scheduled
    failed      — repurposing failed

Does NOT modify any existing modules. Only reads from content sources
and writes to its own table.

Environment variables:
    GROWTH_CONTENT_TABLE  — DynamoDB table name (default: ai1stseo-content-sources)
    AWS_REGION            — AWS region (default: us-east-1)
"""

import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("GROWTH_CONTENT_TABLE", "ai1stseo-content-sources")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    return _table


def init_content_table() -> None:
    """Create the DynamoDB content sources table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.load()
        logger.info("Content table %s exists", TABLE_NAME)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating content table %s ...", TABLE_NAME)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "content_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "content_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("Content table %s created", TABLE_NAME)
    except Exception as e:
        logger.warning("Content table init: %s", e)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def add_content(
    content: str,
    title: str = "",
    source_type: str = "manual",
    source_url: str = "https://ai1stseo.com",
    platforms: list = None,
    campaign: str = "content_repurpose",
) -> dict:
    """Add a new content item to the pipeline queue.

    Args:
        content: The raw text (blog post, article, etc.)
        title: Optional title/label.
        source_type: "manual", "blog", "article", "rss".
        source_url: Link back to original.
        platforms: Target platforms for repurposing.
        campaign: UTM campaign name.

    Returns:
        {"success": bool, "content_id": str}
    """
    if not content or not content.strip():
        return {"success": False, "error": "content is required"}

    content_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "content_id": content_id,
        "content": content.strip(),
        "title": (title or "").strip(),
        "source_type": source_type,
        "source_url": source_url,
        "platforms": ", ".join(platforms) if platforms else "x, linkedin",
        "campaign": campaign,
        "status": "new",
        "created_at": now,
        "processed_at": "",
        "result_summary": "",
    }

    try:
        _get_table().put_item(Item=item)
        logger.info("add_content: id=%s type=%s", content_id, source_type)
        return {"success": True, "content_id": content_id, "item": item}
    except Exception as e:
        logger.error("add_content error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


def get_content(content_id: str) -> dict:
    """Get a single content item by ID."""
    try:
        resp = _get_table().get_item(Key={"content_id": content_id})
        item = resp.get("Item")
        if not item:
            return {"success": False, "error": "Content not found"}
        return {"success": True, "item": item}
    except Exception as e:
        return {"success": False, "error": f"Database error: {e}"}


def list_content(status: str = None, limit: int = 50) -> dict:
    """List content items, optionally filtered by status."""
    limit = max(1, min(limit, 200))
    try:
        resp = _get_table().scan(Limit=limit)
        items = resp.get("Items", [])
        if status:
            items = [i for i in items if i.get("status") == status]
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"success": True, "items": items, "count": len(items)}
    except Exception as e:
        return {"success": False, "error": f"Database error: {e}", "items": []}


def fetch_unprocessed_content(limit: int = 10) -> dict:
    """Fetch content items with status 'new' — ready for the pipeline."""
    return list_content(status="new", limit=limit)


def mark_content_status(content_id: str, status: str, summary: str = "") -> dict:
    """Update a content item's processing status."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        _get_table().update_item(
            Key={"content_id": content_id},
            UpdateExpression="SET #s = :s, processed_at = :p, result_summary = :r",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": status,
                ":p": now,
                ":r": summary,
            },
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Database error: {e}"}


def mark_content_processed(content_id: str, summary: str = "") -> dict:
    """Mark a content item as processed."""
    return mark_content_status(content_id, "processed", summary)
