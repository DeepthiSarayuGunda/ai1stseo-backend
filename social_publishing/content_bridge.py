"""
social_publishing/content_bridge.py
Content Pipeline → Publish Queue bridge.

Connects the content generation system to the publish queue.
Accepts output from the content generator (caption, image, video),
dynamically selects platforms based on content type, and enqueues
for automatic publishing.

Flow:
    content_generator → on_content_generated() → queue → publish_content() → logger

Usage:
    from social_publishing.content_bridge import on_content_generated

    # After content generation completes:
    on_content_generated({
        "caption": "Check out our new SEO tool!",
        "image_url": "https://cdn.example.com/img.png",
        "video_url": None,
        "source": "content_pipeline",
        "campaign": "weekly_content",
        "platforms": None,  # auto-select based on content type
    })
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform selection rules based on content type
# ---------------------------------------------------------------------------

# Content type → eligible platforms
PLATFORM_RULES = {
    "text_only": ["twitter", "linkedin", "facebook"],
    "text_with_image": ["twitter", "linkedin", "facebook", "instagram"],
    "text_with_video": ["twitter", "linkedin", "facebook", "instagram"],
    "image_only": ["instagram", "facebook"],
    "video_only": ["instagram", "facebook"],
}

# Platform-specific constraints
PLATFORM_CONSTRAINTS = {
    "instagram": {"requires_media": True},
    "twitter": {"requires_media": False},
    "linkedin": {"requires_media": False},
    "facebook": {"requires_media": False},
}


def detect_content_type(content: dict) -> str:
    """Determine content type from the input payload."""
    has_text = bool(content.get("caption") or content.get("text"))
    has_image = bool(content.get("image_url"))
    has_video = bool(content.get("video_url"))

    if has_video and has_text:
        return "text_with_video"
    if has_video:
        return "video_only"
    if has_image and has_text:
        return "text_with_image"
    if has_image:
        return "image_only"
    return "text_only"


def select_platforms(content: dict, requested_platforms: list = None) -> list:
    """Dynamically select platforms based on content type and constraints.

    If platforms are explicitly requested, filters them against constraints.
    Otherwise, auto-selects based on content type rules.
    """
    content_type = detect_content_type(content)
    eligible = PLATFORM_RULES.get(content_type, ["twitter", "linkedin", "facebook"])

    if requested_platforms:
        # Filter requested platforms against eligibility
        selected = [p for p in requested_platforms if p in eligible]
        if not selected:
            logger.warning("No requested platforms eligible for %s content. Using all eligible.", content_type)
            selected = eligible
        return selected

    return eligible


def normalize_content_input(raw: dict) -> dict:
    """Normalize content generator output to publish_content() format.

    Accepts flexible input keys (caption/text, image/image_url, etc.)
    and produces the standard publish_content() payload.
    """
    text = raw.get("caption") or raw.get("text") or raw.get("content") or ""
    image_url = raw.get("image_url") or raw.get("image") or None
    video_url = raw.get("video_url") or raw.get("video") or None
    scheduled_at = raw.get("scheduled_at") or raw.get("schedule") or None

    # Clean up empty strings
    if image_url and not image_url.strip():
        image_url = None
    if video_url and not video_url.strip():
        video_url = None

    return {
        "text": text.strip() if text else "",
        "image_url": image_url,
        "video_url": video_url,
        "scheduled_at": scheduled_at,
    }


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def on_content_generated(content: dict, auto_publish: bool = True) -> dict:
    """Called automatically when content generation completes.

    This is the primary hook for the content pipeline. It:
    1. Normalizes the input
    2. Selects platforms dynamically
    3. Enqueues for publishing (or publishes immediately)

    Args:
        content: Raw content from the generator:
            {
                "caption": str,          # or "text" or "content"
                "image_url": str | None,  # or "image"
                "video_url": str | None,  # or "video"
                "platforms": list | None, # explicit platforms, or auto-select
                "scheduled_at": str | None,
                "source": str,           # origin label
                "campaign": str,         # UTM campaign
                "priority": int,         # queue priority (1-10)
            }
        auto_publish: If True, enqueue for automatic publishing.
                      If False, just return the normalized payload.

    Returns:
        {"success": bool, "queue_id": str, "platforms": list, "content_type": str}
    """
    normalized = normalize_content_input(content)

    if not normalized["text"] and not normalized["image_url"] and not normalized["video_url"]:
        return {"success": False, "error": "No publishable content (need text, image, or video)"}

    # Dynamic platform selection
    requested = content.get("platforms")
    platforms = select_platforms(normalized, requested)
    normalized["platforms"] = platforms

    content_type = detect_content_type(normalized)
    source = content.get("source", "content_generator")
    priority = content.get("priority", 5)

    logger.info("Content generated: type=%s platforms=%s source=%s",
                content_type, platforms, source)

    if not auto_publish:
        return {
            "success": True,
            "content_type": content_type,
            "platforms": platforms,
            "payload": normalized,
            "queued": False,
        }

    # Enqueue for automatic publishing
    from social_publishing.queue import enqueue
    result = enqueue(normalized, priority=priority, source=source)

    return {
        "success": result.get("success", False),
        "queue_id": result.get("queue_id"),
        "content_type": content_type,
        "platforms": platforms,
        "queued": True,
    }


def on_batch_generated(items: list, source: str = "content_pipeline") -> dict:
    """Called when the content pipeline produces multiple items.

    Enqueues all items for automatic publishing.

    Args:
        items: List of raw content dicts from the generator.
        source: Origin label.

    Returns:
        {"success": bool, "queued": int, "results": list}
    """
    results = []
    queued = 0

    for item in items:
        item["source"] = item.get("source", source)
        result = on_content_generated(item)
        results.append(result)
        if result.get("queued"):
            queued += 1

    return {
        "success": True,
        "total": len(items),
        "queued": queued,
        "results": results,
    }


def publish_from_repurposer(repurpose_pack: dict, source: str = "repurposer") -> dict:
    """Bridge from content_repurposer output to the publish queue.

    Accepts the output of repurpose_content() and enqueues each
    platform-specific result for publishing.

    Args:
        repurpose_pack: Output from content_repurposer.repurpose_content()
        source: Origin label.

    Returns:
        {"success": bool, "queued": int, "results": list}
    """
    if not repurpose_pack.get("success"):
        return {"success": False, "error": repurpose_pack.get("error", "Repurpose failed")}

    PUBLISHABLE = {"x", "linkedin", "instagram", "facebook", "twitter"}
    items = []

    for r in repurpose_pack.get("results", []):
        if not r.get("success"):
            continue
        platform = r.get("platform", "")
        if platform not in PUBLISHABLE:
            continue

        items.append({
            "text": r.get("output", ""),
            "platforms": [platform],
            "source": source,
        })

    if not items:
        return {"success": True, "queued": 0, "results": [], "message": "No publishable items"}

    return on_batch_generated(items, source=source)
