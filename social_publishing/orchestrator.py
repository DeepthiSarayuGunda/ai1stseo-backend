"""
social_publishing/orchestrator.py
Unified publish_content() function — the single entry point.

Accepts content, formats it per platform, publishes with retry,
logs results, and supports scheduling.

Usage:
    from social_publishing import publish_content

    result = publish_content({
        "text": "Hello world!",
        "image_url": "https://example.com/img.png",
        "platforms": ["twitter", "linkedin", "facebook", "instagram"],
        "scheduled_at": "2026-05-01 10:00",  # optional
    })
"""

import logging
from datetime import datetime, timezone

from social_publishing.formatter import format_for_platform
from social_publishing.platforms.twitter_publisher import TwitterPublisher
from social_publishing.platforms.linkedin_publisher import LinkedInPublisher
from social_publishing.platforms.facebook_publisher import FacebookPublisher
from social_publishing.platforms.instagram_publisher import InstagramPublisher
from social_publishing.post_logger import log_post
from social_publishing.retry import retry_publish

logger = logging.getLogger(__name__)

ALL_PLATFORMS = ["twitter", "linkedin", "facebook", "instagram"]

# Lazy-initialized publisher instances
_publishers = {}


def _get_publisher(platform: str):
    """Get or create a publisher instance for the given platform."""
    if platform not in _publishers:
        _publishers[platform] = {
            "twitter": TwitterPublisher,
            "x": TwitterPublisher,
            "linkedin": LinkedInPublisher,
            "facebook": FacebookPublisher,
            "instagram": InstagramPublisher,
        }.get(platform, lambda: None)()
    return _publishers.get(platform)


def publish_content(content: dict) -> dict:
    """Publish content to one or more social media platforms.

    Args:
        content: {
            "text": str,                          # Required
            "image_url": str | None,              # Optional
            "video_url": str | None,              # Optional
            "platforms": list[str] | None,        # Default: all 4 platforms
            "scheduled_at": str | None,           # "YYYY-MM-DD HH:MM" UTC, optional
        }

    Returns:
        {
            "success": bool,          # True if ALL platforms succeeded
            "published": int,         # Count of successful publishes
            "failed": int,            # Count of failed publishes
            "scheduled": bool,        # Whether this was scheduled for later
            "results": {              # Per-platform results
                "twitter": {"success": bool, "post_id": str, "error": str},
                "linkedin": {...},
                ...
            }
        }
    """
    text = content.get("text", "")
    image_url = content.get("image_url")
    video_url = content.get("video_url")
    platforms = content.get("platforms") or ALL_PLATFORMS
    scheduled_at = content.get("scheduled_at")

    if not text and not image_url and not video_url:
        return {"success": False, "published": 0, "failed": 0, "scheduled": False,
                "results": {}, "error": "No content provided (text, image_url, or video_url required)"}

    # Normalize platform names
    platforms = [_normalize(p) for p in platforms]

    # If scheduled for the future, defer to the scheduler
    if scheduled_at:
        return _schedule_post(text, image_url, video_url, platforms, scheduled_at)

    # Publish immediately to each platform
    results = {}
    published = 0
    failed = 0

    for platform in platforms:
        publisher = _get_publisher(platform)
        if not publisher:
            result = {"success": False, "platform": platform, "post_id": None,
                      "error": f"Unknown platform: {platform}"}
            results[platform] = result
            failed += 1
            log_post(platform, text, result)
            continue

        if not publisher.configured:
            result = {"success": False, "platform": platform, "post_id": None,
                      "error": f"{platform} credentials not configured"}
            results[platform] = result
            failed += 1
            log_post(platform, text, result)
            continue

        # Format content for this platform
        formatted = format_for_platform(text, platform, image_url, video_url)

        # Publish with retry
        result = retry_publish(
            publisher,
            text=formatted["text"],
            image_url=formatted["image_url"],
            video_url=formatted["video_url"],
        )

        results[platform] = result
        if result.get("success"):
            published += 1
        else:
            failed += 1

        # Log to database
        log_post(platform, text, result)

    return {
        "success": failed == 0 and published > 0,
        "published": published,
        "failed": failed,
        "scheduled": False,
        "results": results,
    }


def _schedule_post(text: str, image_url: str, video_url: str,
                   platforms: list, scheduled_at: str) -> dict:
    """Store post in DynamoDB scheduler for future publishing."""
    try:
        # Validate the datetime
        dt = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        if dt <= datetime.now(timezone.utc):
            # If in the past, publish immediately instead
            return publish_content({
                "text": text, "image_url": image_url, "video_url": video_url,
                "platforms": platforms, "scheduled_at": None,
            })
    except ValueError:
        return {"success": False, "published": 0, "failed": 0, "scheduled": False,
                "results": {}, "error": f"Invalid scheduled_at format: {scheduled_at}. Use YYYY-MM-DD HH:MM"}

    try:
        from growth.social_scheduler_dynamo import create_post
        result = create_post(
            content=text,
            platforms=", ".join(platforms),
            scheduled_datetime=scheduled_at,
            image_path=image_url or "",
        )
        if result.get("success"):
            return {
                "success": True,
                "published": 0,
                "failed": 0,
                "scheduled": True,
                "post_id": result.get("post_id"),
                "scheduled_at": scheduled_at,
                "platforms": platforms,
                "results": {},
            }
        return {"success": False, "published": 0, "failed": 0, "scheduled": False,
                "results": {}, "error": result.get("error", "Failed to schedule post")}
    except Exception as e:
        logger.error("Failed to schedule post: %s", e)
        return {"success": False, "published": 0, "failed": 0, "scheduled": False,
                "results": {}, "error": str(e)}


def _normalize(platform: str) -> str:
    """Normalize platform name."""
    p = platform.strip().lower()
    aliases = {"x": "twitter", "twitter/x": "twitter"}
    return aliases.get(p, p)
