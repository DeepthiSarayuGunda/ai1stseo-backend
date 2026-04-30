"""
growth/social_orchestrator.py
Social Publish Orchestrator — routes publish requests to Buffer or Postiz.

Discovers which publisher has valid credentials, normalizes platform names,
routes the publish call, updates post status, and tracks analytics events.

Environment variables:
    SOCIAL_PUBLISHER_PREFERENCE — "buffer" (default) or "postiz"
"""

import logging
import os

logger = logging.getLogger(__name__)

CANONICAL_PLATFORMS = {"linkedin", "x", "instagram", "facebook"}
PLATFORM_ALIASES = {"twitter": "x", "twitter/x": "x"}


def normalize_platform(raw: str) -> tuple:
    """Normalize platform input to canonical value.

    Returns (canonical, None) on success or (None, error_msg) on failure.
    """
    if not raw:
        return None, "platform is required"
    normalized = raw.strip().lower()
    if normalized in PLATFORM_ALIASES:
        normalized = PLATFORM_ALIASES[normalized]
    if normalized in CANONICAL_PLATFORMS:
        return normalized, None
    return None, f"Unsupported platform: {raw.strip()}. Supported: linkedin, x, instagram, facebook"


def discover_publisher() -> tuple:
    """Discover which publisher to use based on credentials and preference.

    Returns (publisher_instance, provider_name) or (None, None).
    """
    preference = os.environ.get("SOCIAL_PUBLISHER_PREFERENCE", "buffer").strip().lower()

    try:
        from buffer_publisher import BufferPublisher
        buffer = BufferPublisher()
    except Exception:
        buffer = None

    try:
        from postiz_publisher import PostizPublisher
        postiz = PostizPublisher()
    except Exception:
        postiz = None

    buffer_ok = buffer and buffer.configured
    postiz_ok = postiz and postiz.configured

    if buffer_ok and postiz_ok:
        if preference == "postiz":
            return postiz, "postiz"
        return buffer, "buffer"
    if buffer_ok:
        return buffer, "buffer"
    if postiz_ok:
        return postiz, "postiz"
    return None, None


def publish_post(payload: dict) -> dict:
    """Orchestrate a social media publish request.

    Args:
        payload: {"post_id": str|None, "content": str, "platform": str, "scheduled_at": str|None}

    Returns:
        {"success": bool, "provider": str|None, "result": dict|None, "error": str|None, "status": str|None}
    """
    content = payload.get("content", "")
    platform_raw = payload.get("platform", "")
    post_id = payload.get("post_id")
    scheduled_at = payload.get("scheduled_at")

    # Normalize platform
    platform, platform_err = normalize_platform(platform_raw)
    if platform_err:
        return {"success": False, "provider": None, "result": None, "error": platform_err, "status": None}

    # Discover publisher
    publisher, provider_name = discover_publisher()
    if not publisher:
        return {
            "success": False,
            "provider": None,
            "result": None,
            "error": "No publisher configured",
            "status": "provider_unavailable",
        }

    # Track attempted (non-blocking)
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="publish_attempted",
            event_data={"platform": platform, "provider": provider_name},
        )
    except Exception:
        logger.warning("Failed to track publish_attempted")

    # Call publisher
    try:
        if provider_name == "buffer":
            result = publisher.publish(
                text=content,
                platform=platform,
                due_at=scheduled_at,
            )
        else:
            result = publisher.publish(
                content=content,
                platform=platform,
                scheduled_at=scheduled_at,
            )
    except Exception as e:
        logger.error("Publisher %s raised exception: %s", provider_name, e)
        _update_status(post_id, "failed")
        _track_outcome(False, platform, provider_name, post_id, str(e))
        return {"success": False, "provider": provider_name, "result": None, "error": str(e), "status": None}

    success = result.get("success", False)

    # Update post status (non-blocking)
    _update_status(post_id, "published" if success else "failed")

    # Track outcome (non-blocking)
    _track_outcome(success, platform, provider_name, post_id, result.get("error"))

    if success:
        return {"success": True, "provider": provider_name, "result": result.get("data", result), "error": None, "status": None}
    return {"success": False, "provider": provider_name, "result": None, "error": result.get("error", "Unknown publisher error"), "status": None}


def _update_status(post_id: str, status: str) -> None:
    """Update scheduled post status in DynamoDB (fire-and-forget)."""
    if not post_id:
        return
    try:
        from growth.social_scheduler_dynamo import update_post
        update_post(post_id, {"status": status})
    except Exception as e:
        logger.warning("Failed to update post %s status to %s: %s", post_id, status, e)


def _track_outcome(success: bool, platform: str, provider: str, post_id: str, error: str = None) -> None:
    """Track publish outcome analytics event (fire-and-forget)."""
    try:
        from growth.analytics_tracker import track_event
        if success:
            track_event(
                event_type="publish_succeeded",
                event_data={"platform": platform, "provider": provider, "post_id": post_id},
            )
        else:
            track_event(
                event_type="publish_failed",
                event_data={"platform": platform, "provider": provider, "post_id": post_id, "error": error or "unknown"},
            )
    except Exception:
        logger.warning("Failed to track publish outcome")
