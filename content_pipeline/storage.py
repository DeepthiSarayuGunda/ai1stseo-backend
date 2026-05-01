"""
S3 storage for pipeline outputs.
Saves articles, newsletters, social posts, and images.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)

BUCKET = os.environ.get("S3_BUCKET", "ai-content-output")
REGION = os.environ.get("AWS_REGION", "us-east-1")

_s3 = None


def _get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=REGION)
    return _s3


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


def save_articles(articles: list[dict]) -> list[str]:
    """Save articles to S3. Returns list of S3 keys."""
    s3 = _get_s3()
    keys = []
    for i, article in enumerate(articles):
        key = f"articles/{_timestamp()}_{i}.json"
        s3.put_object(
            Bucket=BUCKET, Key=key,
            Body=json.dumps(article, indent=2, ensure_ascii=False),
            ContentType="application/json",
        )
        keys.append(key)
        logger.info("Saved article: s3://%s/%s", BUCKET, key)
    return keys


def save_newsletter(newsletter: dict) -> str:
    """Save newsletter to S3. Returns S3 key."""
    s3 = _get_s3()
    key = f"newsletter/{_timestamp()}.json"
    s3.put_object(
        Bucket=BUCKET, Key=key,
        Body=json.dumps(newsletter, indent=2, ensure_ascii=False),
        ContentType="application/json",
    )
    logger.info("Saved newsletter: s3://%s/%s", BUCKET, key)
    return key


def save_social_posts(posts: list[dict]) -> list[str]:
    """Save social posts to S3. Returns list of S3 keys."""
    s3 = _get_s3()
    keys = []
    for i, post in enumerate(posts):
        key = f"social/{_timestamp()}_{i}.json"
        s3.put_object(
            Bucket=BUCKET, Key=key,
            Body=json.dumps(post, indent=2, ensure_ascii=False),
            ContentType="application/json",
        )
        keys.append(key)
    logger.info("Saved %d social posts to S3", len(keys))
    return keys


def save_image(image_bytes: bytes, article_index: int) -> str:
    """Save image to S3. Returns S3 key and public URL."""
    if not image_bytes:
        return None
    s3 = _get_s3()
    key = f"images/{_timestamp()}_{article_index}.png"
    s3.put_object(
        Bucket=BUCKET, Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )
    logger.info("Saved image: s3://%s/%s", BUCKET, key)
    return key


def get_image_url(key: str) -> str:
    """Generate a presigned URL for an image."""
    if not key:
        return None
    s3 = _get_s3()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=86400,  # 24 hours
    )
