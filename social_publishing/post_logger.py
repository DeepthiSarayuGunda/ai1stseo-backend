"""
social_publishing/post_logger.py
DynamoDB post logger — records every publish attempt with timestamp,
platform, content, and result.

Table: social-post-log (configurable via SOCIAL_POST_LOG_TABLE)
Schema:
    PK: log_id (UUID)
    SK: created_at (ISO timestamp)
    GSI: platform-index (platform + created_at) for per-platform queries
"""

import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from social_publishing.config import AWS_REGION, SOCIAL_POST_LOG_TABLE

logger = logging.getLogger(__name__)

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(SOCIAL_POST_LOG_TABLE)
    return _table


def init_post_log_table() -> None:
    """Create the DynamoDB post log table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(SOCIAL_POST_LOG_TABLE)
        table.load()
        logger.info("Post log table %s exists", SOCIAL_POST_LOG_TABLE)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating post log table %s ...", SOCIAL_POST_LOG_TABLE)
        dynamodb.create_table(
            TableName=SOCIAL_POST_LOG_TABLE,
            KeySchema=[
                {"AttributeName": "log_id", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "log_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
                {"AttributeName": "platform", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "platform-index",
                "KeySchema": [
                    {"AttributeName": "platform", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.meta.client.get_waiter("table_exists").wait(TableName=SOCIAL_POST_LOG_TABLE)
        logger.info("Post log table %s created", SOCIAL_POST_LOG_TABLE)


def log_post(platform: str, content: str, result: dict, scheduled_at: str = None) -> str:
    """Log a publish attempt to DynamoDB.

    Args:
        platform: Platform name (twitter, linkedin, facebook, instagram).
        content: The text content that was published.
        result: The result dict from the publisher.
        scheduled_at: Optional scheduled datetime string.

    Returns:
        The log_id of the created record.
    """
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "log_id": log_id,
        "created_at": now,
        "platform": platform,
        "content": content[:2000],  # Truncate for DynamoDB item size
        "success": result.get("success", False),
        "post_id": result.get("post_id") or "",
        "error": result.get("error") or "",
        "provider": result.get("platform", platform),
    }

    if scheduled_at:
        item["scheduled_at"] = scheduled_at

    try:
        _get_table().put_item(Item=item)
        logger.debug("Logged post %s to %s", log_id, platform)
    except ClientError as e:
        logger.warning("Failed to log post to DynamoDB: %s", e)
    except Exception as e:
        logger.warning("Post log write failed (table may not exist): %s", e)

    return log_id


def get_logs(platform: str = None, limit: int = 50) -> list:
    """Retrieve recent post logs, optionally filtered by platform."""
    try:
        table = _get_table()
        if platform:
            from boto3.dynamodb.conditions import Key
            resp = table.query(
                IndexName="platform-index",
                KeyConditionExpression=Key("platform").eq(platform),
                ScanIndexForward=False,
                Limit=limit,
            )
        else:
            resp = table.scan(Limit=limit)
        return resp.get("Items", [])
    except Exception as e:
        logger.warning("Failed to read post logs: %s", e)
        return []
