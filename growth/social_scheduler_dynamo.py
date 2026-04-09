"""
growth/social_scheduler_dynamo.py
Social scheduler backed by DynamoDB — replaces SQLite for App Runner.

Provides the same CRUD operations as the SQLite scheduler but stores
posts in DynamoDB so data persists across cold starts.

This module is part of the ai1stseo.com 5-month growth plan.
It does NOT modify the existing SQLite scheduler in app.py.

Environment variables:
    GROWTH_SOCIAL_TABLE  — DynamoDB table name (default: ai1stseo-social-posts)
    AWS_REGION           — AWS region (default: us-east-1)
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("GROWTH_SOCIAL_TABLE", "ai1stseo-social-posts")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    return _table


def init_social_table() -> None:
    """Create the DynamoDB social posts table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.load()
        logger.info("Social table %s exists", TABLE_NAME)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating social table %s ...", TABLE_NAME)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "post_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "post_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("Social table %s created", TABLE_NAME)
    except Exception as e:
        logger.warning("Social table init: %s", e)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_post(
    content: str,
    platforms: list,
    scheduled_date: str,
    scheduled_time: str,
    image_path: str = None,
    status: str = "scheduled",
) -> dict:
    """Create a new scheduled post."""
    if not content:
        return {"success": False, "error": "Post content is required"}
    if not platforms:
        return {"success": False, "error": "Select at least one platform"}
    if not scheduled_date or not scheduled_time:
        return {"success": False, "error": "Date and time are required"}

    post_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    scheduled_datetime = f"{scheduled_date} {scheduled_time}"

    item = {
        "post_id": post_id,
        "content": content.strip(),
        "platforms": ", ".join(platforms) if isinstance(platforms, list) else str(platforms),
        "scheduled_datetime": scheduled_datetime,
        "status": status,
        "created_at": now,
    }
    if image_path:
        item["image_path"] = image_path

    try:
        _get_table().put_item(Item=item)
        logger.info("create_post: id=%s platforms=%s", post_id, item["platforms"])
        return {"success": True, "status": "success", "id": post_id, "post": item}
    except Exception as e:
        logger.error("create_post error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


def get_posts() -> dict:
    """Get all scheduled posts ordered by scheduled_datetime."""
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

        all_items.sort(key=lambda x: x.get("scheduled_datetime", ""))
        return {"success": True, "posts": all_items, "count": len(all_items)}
    except Exception as e:
        logger.error("get_posts error: %s", e)
        return {"success": False, "error": f"Database error: {e}", "posts": []}


def update_post(post_id: str, updates: dict) -> dict:
    """Update a post by ID."""
    try:
        # Check exists
        resp = _get_table().get_item(Key={"post_id": post_id})
        if not resp.get("Item"):
            return {"success": False, "error": "Post not found"}

        expr_parts, expr_names, expr_values = [], {}, {}
        idx = 0
        for k, v in updates.items():
            if k == "post_id":
                continue
            name_ph = f"#u{idx}"
            val_ph = f":u{idx}"
            expr_parts.append(f"{name_ph} = {val_ph}")
            expr_names[name_ph] = k
            expr_values[val_ph] = v
            idx += 1

        if not expr_parts:
            return {"success": False, "error": "No fields to update"}

        _get_table().update_item(
            Key={"post_id": post_id},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        logger.info("update_post: id=%s", post_id)
        return {"success": True, "status": "success"}
    except Exception as e:
        logger.error("update_post error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}


def delete_post(post_id: str) -> dict:
    """Delete a post by ID."""
    try:
        resp = _get_table().get_item(Key={"post_id": post_id})
        if not resp.get("Item"):
            return {"success": False, "error": "Post not found"}

        _get_table().delete_item(Key={"post_id": post_id})
        logger.info("delete_post: id=%s", post_id)
        return {"success": True, "status": "success"}
    except Exception as e:
        logger.error("delete_post error: %s", e)
        return {"success": False, "error": f"Database error: {e}"}
