"""
social_publishing/platforms/twitter_publisher.py
Twitter/X API v2 publisher using OAuth 1.0a (User Context).

Supports text tweets and media uploads (images/video).
Uses requests_oauthlib for OAuth signing.

Env vars: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
"""

import logging
import time

import requests
from requests_oauthlib import OAuth1

from social_publishing.config import (
    TWITTER_ACCESS_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
)
from social_publishing.platforms.base import BasePlatformPublisher

logger = logging.getLogger(__name__)

TWEET_URL = "https://api.twitter.com/2/tweets"
MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"


class TwitterPublisher(BasePlatformPublisher):
    """Publish tweets via Twitter API v2."""

    platform_name = "twitter"

    def __init__(self):
        self._auth = None
        if self.configured:
            self._auth = OAuth1(
                TWITTER_API_KEY,
                TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN,
                TWITTER_ACCESS_SECRET,
            )

    @property
    def configured(self) -> bool:
        return all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET])

    def publish(self, text: str, image_url: str = None, video_url: str = None) -> dict:
        if not self.configured:
            return self._failure("Twitter credentials not configured")

        try:
            media_id = None
            media_url = video_url or image_url
            if media_url:
                media_id = self._upload_media(media_url)

            payload = {"text": text}
            if media_id:
                payload["media"] = {"media_ids": [media_id]}

            resp = requests.post(TWEET_URL, json=payload, auth=self._auth, timeout=30)

            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                return self._success(post_id=data.get("id"), raw=data)

            return self._failure(f"Twitter API {resp.status_code}: {resp.text}", raw={"status": resp.status_code})

        except Exception as e:
            logger.error("Twitter publish error: %s", e)
            return self._failure(str(e))

    def _upload_media(self, url: str) -> str | None:
        """Download media from URL and upload to Twitter. Returns media_id_string."""
        try:
            # Download media
            media_resp = requests.get(url, timeout=30)
            media_resp.raise_for_status()
            content_type = media_resp.headers.get("Content-Type", "image/jpeg")

            # Simple upload (images < 5MB, GIFs < 15MB)
            files = {"media_data": None}
            import base64
            media_data = base64.b64encode(media_resp.content).decode()

            resp = requests.post(
                MEDIA_UPLOAD_URL,
                data={"media_data": media_data, "media_category": self._media_category(content_type)},
                auth=self._auth,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json().get("media_id_string")

        except Exception as e:
            logger.warning("Twitter media upload failed: %s", e)
            return None

    @staticmethod
    def _media_category(content_type: str) -> str:
        if "video" in content_type:
            return "tweet_video"
        if "gif" in content_type:
            return "tweet_gif"
        return "tweet_image"
