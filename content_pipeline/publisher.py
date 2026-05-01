"""
Postiz publishing integration for the content pipeline.
Supports both Postiz Cloud and self-hosted (GitHub) instances.

Env vars:
    POSTIZ_API_KEY   — API key from Postiz Settings > Developers
    POSTIZ_API_URL   — Base URL (self-hosted: http://<IP>:4007/api/public/v1)
    POSTIZ_INTEGRATION_X  — Integration ID for Twitter/X
    POSTIZ_INTEGRATION_LI — Integration ID for LinkedIn
    POSTIZ_INTEGRATION_FB — Integration ID for Facebook
    POSTIZ_INTEGRATION_IG — Integration ID for Instagram
"""

import logging
import os
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

POSTIZ_API_KEY = os.environ.get("POSTIZ_API_KEY", "")
POSTIZ_API_URL = os.environ.get("POSTIZ_API_URL", "https://api.postiz.com/public/v1").rstrip("/")

# Integration IDs per platform
INTEGRATION_IDS = {
    "x": os.environ.get("POSTIZ_INTEGRATION_X", ""),
    "linkedin": os.environ.get("POSTIZ_INTEGRATION_LI", ""),
    "facebook": os.environ.get("POSTIZ_INTEGRATION_FB", ""),
    "instagram": os.environ.get("POSTIZ_INTEGRATION_IG", ""),
}

PLATFORM_SETTINGS = {
    "x": {"__type": "x", "who_can_reply_post": "everyone"},
    "linkedin": {"__type": "linkedin"},
    "facebook": {"__type": "facebook"},
    "instagram": {"__type": "instagram", "post_type": "post"},
}


def _headers():
    return {"Authorization": POSTIZ_API_KEY, "Content-Type": "application/json"}


def is_configured() -> bool:
    return bool(POSTIZ_API_KEY)


def list_integrations() -> list[dict]:
    """Fetch connected social accounts from Postiz."""
    if not POSTIZ_API_KEY:
        return []
    try:
        resp = requests.get(f"{POSTIZ_API_URL}/integrations", headers=_headers(), timeout=15)
        if resp.status_code == 200:
            return resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
    except Exception as e:
        logger.error("Failed to list integrations: %s", e)
    return []


def upload_image(image_bytes: bytes, filename: str = "image.png") -> dict:
    """Upload image to Postiz. Returns {"id": "...", "path": "..."}."""
    if not POSTIZ_API_KEY:
        return None
    try:
        resp = requests.post(
            f"{POSTIZ_API_URL}/upload",
            headers={"Authorization": POSTIZ_API_KEY},
            files={"file": (filename, image_bytes, "image/png")},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            logger.info("Image uploaded to Postiz: %s", data.get("path", "?"))
            return data
        logger.error("Postiz upload failed: %d %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("Postiz upload error: %s", e)
    return None


def publish_to_postiz(social_post: dict, image_url: str = None,
                      image_bytes: bytes = None, scheduled_at: str = None,
                      platforms: list[str] = None) -> dict:
    """Publish a social post via Postiz API.

    Args:
        social_post: dict with hook, caption, hashtags, cta, platform_variants
        image_url: public URL of image (for S3 presigned URLs)
        image_bytes: raw image bytes (will upload to Postiz first)
        scheduled_at: ISO datetime for scheduling (None = post now)
        platforms: list of platforms to post to (default: all configured)
    """
    if not POSTIZ_API_KEY:
        return {"success": False, "error": "POSTIZ_API_KEY not set"}

    # Upload image if bytes provided
    image_payload = []
    if image_bytes:
        uploaded = upload_image(image_bytes)
        if uploaded:
            image_payload = [{"id": uploaded.get("id", ""), "path": uploaded.get("path", "")}]
    elif image_url:
        image_payload = [{"url": image_url}]

    # Determine which platforms to post to
    target_platforms = platforms or [p for p, iid in INTEGRATION_IDS.items() if iid]
    if not target_platforms:
        # If no integration IDs configured, post without specifying integration
        return _publish_simple(social_post, image_payload, scheduled_at)

    # Build multi-platform payload
    posts = []
    variants = social_post.get("platform_variants", {})

    for platform in target_platforms:
        int_id = INTEGRATION_IDS.get(platform, "")
        if not int_id:
            continue

        # Use platform-specific content if available
        content = variants.get(platform) or _build_content(social_post)
        settings = PLATFORM_SETTINGS.get(platform, {"__type": platform})

        posts.append({
            "integration": {"id": int_id},
            "value": [{"content": content, "image": image_payload}],
            "settings": settings,
        })

    if not posts:
        return _publish_simple(social_post, image_payload, scheduled_at)

    payload = {
        "type": "schedule" if scheduled_at else "now",
        "date": scheduled_at or datetime.now(timezone.utc).isoformat(),
        "shortLink": False,
        "tags": [],
        "posts": posts,
    }

    return _send_to_postiz(payload)


def _publish_simple(social_post: dict, image_payload: list, scheduled_at: str = None) -> dict:
    """Publish without integration IDs (basic mode)."""
    content = _build_content(social_post)
    payload = {
        "type": "schedule" if scheduled_at else "now",
        "date": scheduled_at or datetime.now(timezone.utc).isoformat(),
        "shortLink": False,
        "posts": [{"value": [{"content": content, "image": image_payload}]}],
    }
    return _send_to_postiz(payload)


def _build_content(social_post: dict) -> str:
    """Build full post content from social post dict."""
    hook = social_post.get("hook", "")
    caption = social_post.get("caption", "")
    hashtags = " ".join(social_post.get("hashtags", []))
    cta = social_post.get("cta", "")
    return f"{hook}\n\n{caption}\n\n{cta}\n\n{hashtags}".strip()


def _send_to_postiz(payload: dict) -> dict:
    """Send payload to Postiz API."""
    try:
        resp = requests.post(
            f"{POSTIZ_API_URL}/posts",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        data = resp.json() if resp.content else {}

        if resp.status_code in (200, 201):
            logger.info("Published to Postiz successfully")
            return {"success": True, "data": data}
        else:
            error = data.get("message", f"HTTP {resp.status_code}")
            logger.error("Postiz publish failed: %s", error)
            return {"success": False, "error": error, "data": data}
    except Exception as e:
        logger.error("Postiz publish exception: %s", e)
        return {"success": False, "error": str(e)}


def schedule_posts_throughout_day(social_posts: list[dict], image_bytes_list: list = None,
                                  start_hour: int = 9, end_hour: int = 18) -> list[dict]:
    """Schedule posts spread across the day instead of posting all at once.

    Args:
        social_posts: list of social post dicts
        image_bytes_list: optional list of image bytes (parallel to social_posts)
        start_hour: first post hour (UTC)
        end_hour: last post hour (UTC)
    """
    if not social_posts:
        return []

    now = datetime.now(timezone.utc)
    interval = (end_hour - start_hour) / max(len(social_posts), 1)
    results = []

    for i, post in enumerate(social_posts):
        scheduled_time = now.replace(hour=start_hour, minute=0, second=0) + timedelta(hours=interval * i)
        if scheduled_time < now:
            scheduled_time += timedelta(days=1)

        img = image_bytes_list[i] if image_bytes_list and i < len(image_bytes_list) else None
        result = publish_to_postiz(post, image_bytes=img, scheduled_at=scheduled_time.isoformat())
        results.append({
            "article": post.get("article_title", "")[:50],
            "scheduled_at": scheduled_time.isoformat(),
            **result,
        })

    return results
