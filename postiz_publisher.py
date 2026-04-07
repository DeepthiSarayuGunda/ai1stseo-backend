"""
postiz_publisher.py
Postiz Cloud API publishing bridge for the AI1stSEO social scheduler.

This module provides a clean interface between the existing scheduler
(social_posts table / scheduled_posts SQLite) and the Postiz Cloud API.
It does NOT replace the scheduler — it adds publishing capability.

Usage:
    from postiz_publisher import PostizPublisher

    pub = PostizPublisher()
    result = pub.publish(post_id, content, platform, integration_id)

Environment variables:
    POSTIZ_API_KEY        — API key from Postiz Settings > Developers
    POSTIZ_API_URL        — Base URL (default: https://api.postiz.com/public/v1)
    POSTIZ_INTEGRATION_X  — Integration ID for Twitter/X account
    POSTIZ_INTEGRATION_IG — Integration ID for Instagram account
    POSTIZ_INTEGRATION_FB — Integration ID for Facebook account
    POSTIZ_INTEGRATION_LI — Integration ID for LinkedIn account
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Postiz platform type mapping (our platform names -> Postiz __type values)
PLATFORM_MAP = {
    "twitter/x": "x",
    "twitter": "x",
    "x": "x",
    "instagram": "instagram",
    "facebook": "facebook",
    "linkedin": "linkedin",
}

# Postiz integration ID env var mapping
INTEGRATION_ENV = {
    "x": "POSTIZ_INTEGRATION_X",
    "instagram": "POSTIZ_INTEGRATION_IG",
    "facebook": "POSTIZ_INTEGRATION_FB",
    "linkedin": "POSTIZ_INTEGRATION_LI",
}

# Default platform-specific settings
DEFAULT_SETTINGS = {
    "x": {"__type": "x", "who_can_reply_post": "everyone"},
    "instagram": {"__type": "instagram", "post_type": "post"},
    "facebook": {"__type": "facebook"},
    "linkedin": {"__type": "linkedin"},
}


class PostizPublisher:
    """Thin wrapper around the Postiz Cloud API for publishing social posts."""

    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or os.environ.get("POSTIZ_API_KEY", "")
        self.api_url = (api_url or os.environ.get(
            "POSTIZ_API_URL", "https://api.postiz.com/public/v1"
        )).rstrip("/")

    @property
    def configured(self):
        """Check if the publisher has a valid API key."""
        return bool(self.api_key)

    def _headers(self):
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    def _resolve_platform(self, platform_name):
        """Map our platform name to Postiz __type."""
        key = platform_name.strip().lower()
        return PLATFORM_MAP.get(key)

    def _resolve_integration(self, postiz_type, integration_id=None):
        """Get the integration ID for a platform."""
        if integration_id:
            return integration_id
        env_key = INTEGRATION_ENV.get(postiz_type, "")
        return os.environ.get(env_key, "")

    def build_payload(self, content, platform, integration_id=None,
                      scheduled_at=None, images=None):
        """
        Build a Postiz API payload from scheduler post data.

        Args:
            content: Post text/caption
            platform: Platform name (e.g. "Twitter/X", "Instagram")
            integration_id: Postiz integration ID (or resolved from env)
            scheduled_at: ISO datetime string for scheduling (None = post now)
            images: List of image dicts [{"id": "...", "path": "..."}]

        Returns:
            dict: Postiz API payload ready for POST /posts
        """
        postiz_type = self._resolve_platform(platform)
        if not postiz_type:
            return None, f"Unsupported platform: {platform}"

        int_id = self._resolve_integration(postiz_type, integration_id)
        if not int_id:
            return None, f"No integration ID for {platform}. Set {INTEGRATION_ENV.get(postiz_type, '?')} env var."

        settings = DEFAULT_SETTINGS.get(postiz_type, {"__type": postiz_type})

        post_entry = {
            "integration": {"id": int_id},
            "value": [
                {
                    "content": content,
                    "image": images or [],
                }
            ],
            "settings": settings,
        }

        # Determine publish type
        if scheduled_at:
            publish_type = "schedule"
            date_str = scheduled_at
        else:
            publish_type = "now"
            date_str = datetime.now(timezone.utc).isoformat()

        payload = {
            "type": publish_type,
            "date": date_str,
            "shortLink": False,
            "tags": [],
            "posts": [post_entry],
        }

        return payload, None

    def publish(self, content, platform, integration_id=None,
                scheduled_at=None, images=None, dry_run=False):
        """
        Publish or schedule a post via Postiz API.

        Returns:
            dict: {"success": bool, "data": response_data, "error": error_msg}
        """
        if not self.configured:
            return {"success": False, "error": "POSTIZ_API_KEY not set", "data": None}

        payload, err = self.build_payload(
            content, platform, integration_id, scheduled_at, images
        )
        if err:
            return {"success": False, "error": err, "data": None}

        if dry_run:
            return {"success": True, "error": None, "data": {"dry_run": True, "payload": payload}}

        try:
            import requests
            resp = requests.post(
                f"{self.api_url}/posts",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            data = resp.json() if resp.content else {}

            if resp.status_code in (200, 201):
                logger.info("Postiz publish success: platform=%s status=%d", platform, resp.status_code)
                return {"success": True, "error": None, "data": data}
            else:
                error_msg = data.get("message", data.get("error", f"HTTP {resp.status_code}"))
                logger.error("Postiz publish failed: platform=%s error=%s", platform, error_msg)
                return {"success": False, "error": error_msg, "data": data}

        except Exception as e:
            logger.error("Postiz publish exception: %s", e)
            return {"success": False, "error": str(e), "data": None}

    def list_integrations(self):
        """Fetch connected social accounts from Postiz."""
        if not self.configured:
            return {"success": False, "error": "POSTIZ_API_KEY not set", "data": None}
        try:
            import requests
            resp = requests.get(
                f"{self.api_url}/integrations",
                headers=self._headers(),
                timeout=15,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200:
                return {"success": True, "error": None, "data": data}
            return {"success": False, "error": f"HTTP {resp.status_code}", "data": data}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}


# ── Convenience functions for use from the scheduler ──────────────────────────

_publisher = None

def get_publisher():
    """Get or create the singleton publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = PostizPublisher()
    return _publisher


def publish_post(content, platform, integration_id=None,
                 scheduled_at=None, images=None, dry_run=False):
    """Shortcut: publish a single post."""
    return get_publisher().publish(
        content, platform, integration_id, scheduled_at, images, dry_run
    )


def is_configured():
    """Check if Postiz publishing is available."""
    return get_publisher().configured


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    pub = PostizPublisher()
    print(f"Postiz API URL: {pub.api_url}")
    print(f"API key set: {pub.configured}")

    if not pub.configured:
        print("\nSet POSTIZ_API_KEY to test. Example:")
        print("  set POSTIZ_API_KEY=your-key-here")
        print("  python postiz_publisher.py")
        sys.exit(0)

    # List integrations
    print("\nFetching connected integrations...")
    result = pub.list_integrations()
    if result["success"]:
        integrations = result["data"]
        if isinstance(integrations, list):
            for i in integrations:
                print(f"  {i.get('providerIdentifier', '?'):15s} id={i.get('id', '?')}")
        else:
            print(f"  Response: {integrations}")
    else:
        print(f"  Error: {result['error']}")

    # Dry-run a test post
    print("\nDry-run test post to Twitter/X...")
    result = pub.publish(
        content="Test post from AI1stSEO scheduler bridge",
        platform="Twitter/X",
        dry_run=True,
    )
    if result["success"]:
        print(f"  Payload: {json.dumps(result['data']['payload'], indent=2)}")
    else:
        print(f"  Error: {result['error']}")
