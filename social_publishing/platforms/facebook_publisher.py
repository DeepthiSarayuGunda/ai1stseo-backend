"""
social_publishing/platforms/facebook_publisher.py
Facebook Graph API publisher.

Supports text posts, photo posts, and video posts to a Facebook Page.
Uses Page Access Token.

Env vars: FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID
"""

import logging

import requests

from social_publishing.config import FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID
from social_publishing.platforms.base import BasePlatformPublisher

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"


class FacebookPublisher(BasePlatformPublisher):
    """Publish posts via Facebook Graph API."""

    platform_name = "facebook"

    @property
    def configured(self) -> bool:
        return bool(FACEBOOK_ACCESS_TOKEN and FACEBOOK_PAGE_ID)

    def publish(self, text: str, image_url: str = None, video_url: str = None) -> dict:
        if not self.configured:
            return self._failure("Facebook credentials not configured")

        try:
            if video_url:
                return self._publish_video(text, video_url)
            if image_url:
                return self._publish_photo(text, image_url)
            return self._publish_text(text)

        except Exception as e:
            logger.error("Facebook publish error: %s", e)
            return self._failure(str(e))

    def _publish_text(self, text: str) -> dict:
        url = f"{GRAPH_API}/{FACEBOOK_PAGE_ID}/feed"
        resp = requests.post(url, data={
            "message": text,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        }, timeout=30)

        if resp.status_code == 200:
            return self._success(post_id=resp.json().get("id"), raw=resp.json())
        return self._failure(f"Facebook API {resp.status_code}: {resp.text}")

    def _publish_photo(self, text: str, image_url: str) -> dict:
        url = f"{GRAPH_API}/{FACEBOOK_PAGE_ID}/photos"
        resp = requests.post(url, data={
            "url": image_url,
            "caption": text,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        }, timeout=30)

        if resp.status_code == 200:
            return self._success(post_id=resp.json().get("id"), raw=resp.json())
        return self._failure(f"Facebook photo API {resp.status_code}: {resp.text}")

    def _publish_video(self, text: str, video_url: str) -> dict:
        url = f"{GRAPH_API}/{FACEBOOK_PAGE_ID}/videos"
        resp = requests.post(url, data={
            "file_url": video_url,
            "description": text,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        }, timeout=60)

        if resp.status_code == 200:
            return self._success(post_id=resp.json().get("id"), raw=resp.json())
        return self._failure(f"Facebook video API {resp.status_code}: {resp.text}")
