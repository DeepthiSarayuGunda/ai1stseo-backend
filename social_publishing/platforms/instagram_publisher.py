"""
social_publishing/platforms/instagram_publisher.py
Instagram Graph API publisher (via Facebook Business).

Instagram API requires media (image or video) for every post.
Text-only posts are not supported by the API.

Env vars: INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID
"""

import logging
import time

import requests

from social_publishing.config import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID
from social_publishing.platforms.base import BasePlatformPublisher

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"


class InstagramPublisher(BasePlatformPublisher):
    """Publish posts via Instagram Graph API (Content Publishing API)."""

    platform_name = "instagram"

    @property
    def configured(self) -> bool:
        return bool(INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID)

    def publish(self, text: str, image_url: str = None, video_url: str = None) -> dict:
        if not self.configured:
            return self._failure("Instagram credentials not configured")

        if not image_url and not video_url:
            return self._failure("Instagram requires an image_url or video_url")

        try:
            # Step 1: Create media container
            container_id = self._create_container(text, image_url, video_url)
            if not container_id:
                return self._failure("Failed to create Instagram media container")

            # Step 2: Wait for container to be ready (video processing)
            if video_url:
                if not self._wait_for_container(container_id):
                    return self._failure("Instagram media container processing timed out")

            # Step 3: Publish the container
            return self._publish_container(container_id)

        except Exception as e:
            logger.error("Instagram publish error: %s", e)
            return self._failure(str(e))

    def _create_container(self, text: str, image_url: str = None, video_url: str = None) -> str | None:
        """Create a media container. Returns container ID."""
        url = f"{GRAPH_API}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
        params = {
            "caption": text,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }

        if video_url:
            params["video_url"] = video_url
            params["media_type"] = "REELS"
        elif image_url:
            params["image_url"] = image_url

        resp = requests.post(url, data=params, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("id")

        logger.error("Instagram container creation failed: %s", resp.text)
        return None

    def _wait_for_container(self, container_id: str, max_wait: int = 60) -> bool:
        """Poll container status until FINISHED or timeout."""
        url = f"{GRAPH_API}/{container_id}"
        start = time.time()

        while time.time() - start < max_wait:
            resp = requests.get(url, params={
                "fields": "status_code",
                "access_token": INSTAGRAM_ACCESS_TOKEN,
            }, timeout=15)

            if resp.status_code == 200:
                status = resp.json().get("status_code")
                if status == "FINISHED":
                    return True
                if status == "ERROR":
                    return False

            time.sleep(3)

        return False

    def _publish_container(self, container_id: str) -> dict:
        """Publish a ready media container."""
        url = f"{GRAPH_API}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
        resp = requests.post(url, data={
            "creation_id": container_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }, timeout=30)

        if resp.status_code == 200:
            return self._success(post_id=resp.json().get("id"), raw=resp.json())
        return self._failure(f"Instagram publish API {resp.status_code}: {resp.text}")
