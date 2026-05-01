"""
Postiz publishing integration for the content pipeline.
Posts social content with images to connected social accounts.
"""

import logging
import os

logger = logging.getLogger(__name__)

POSTIZ_API_KEY = os.environ.get("POSTIZ_API_KEY", "")
POSTIZ_API_URL = os.environ.get("POSTIZ_API_URL", "https://api.postiz.com/public/v1")


def publish_to_postiz(social_post: dict, image_url: str = None) -> dict:
    """Publish a social post via Postiz API."""
    if not POSTIZ_API_KEY:
        return {"success": False, "error": "POSTIZ_API_KEY not set"}

    import requests

    # Build the post content
    caption = social_post.get("hook", "") + "\n\n" + social_post.get("caption", "")
    hashtags = " ".join(social_post.get("hashtags", []))
    cta = social_post.get("cta", "")
    full_content = f"{caption}\n\n{cta}\n\n{hashtags}".strip()

    # Build image payload
    images = []
    if image_url:
        images = [{"url": image_url}]

    payload = {
        "type": "now",
        "shortLink": False,
        "posts": [
            {
                "value": [{"content": full_content, "image": images}],
            }
        ],
    }

    try:
        resp = requests.post(
            f"{POSTIZ_API_URL.rstrip('/')}/posts",
            headers={"Authorization": POSTIZ_API_KEY, "Content-Type": "application/json"},
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
