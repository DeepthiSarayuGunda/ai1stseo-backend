"""
social_publishing/platforms/linkedin_publisher.py
LinkedIn API v2 publisher.

Supports text posts and image shares via the LinkedIn Marketing API.
Uses OAuth 2.0 bearer token.

Env vars: LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN
"""

import json
import logging

import requests

from social_publishing.config import LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN
from social_publishing.platforms.base import BasePlatformPublisher

logger = logging.getLogger(__name__)

API_BASE = "https://api.linkedin.com/v2"
POSTS_URL = f"{API_BASE}/ugcPosts"
REGISTER_UPLOAD_URL = f"{API_BASE}/assets?action=registerUpload"


class LinkedInPublisher(BasePlatformPublisher):
    """Publish posts via LinkedIn API v2."""

    platform_name = "linkedin"

    @property
    def configured(self) -> bool:
        return bool(LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def publish(self, text: str, image_url: str = None, video_url: str = None) -> dict:
        if not self.configured:
            return self._failure("LinkedIn credentials not configured")

        try:
            media_asset = None
            if image_url:
                media_asset = self._upload_image(image_url)

            payload = self._build_payload(text, media_asset)
            resp = requests.post(POSTS_URL, json=payload, headers=self._headers(), timeout=30)

            if resp.status_code in (200, 201):
                post_id = resp.headers.get("x-restli-id", resp.json().get("id"))
                return self._success(post_id=post_id, raw=resp.json())

            return self._failure(f"LinkedIn API {resp.status_code}: {resp.text}", raw={"status": resp.status_code})

        except Exception as e:
            logger.error("LinkedIn publish error: %s", e)
            return self._failure(str(e))

    def _build_payload(self, text: str, media_asset: str = None) -> dict:
        """Build UGC post payload."""
        author = LINKEDIN_PERSON_URN

        specific_content = {"com.linkedin.ugc.ShareContent": {
            "shareCommentary": {"text": text},
            "shareMediaCategory": "NONE",
        }}

        if media_asset:
            specific_content["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
            specific_content["com.linkedin.ugc.ShareContent"]["media"] = [{
                "status": "READY",
                "media": media_asset,
            }]

        return {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": specific_content,
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

    def _upload_image(self, url: str) -> str | None:
        """Register and upload an image to LinkedIn. Returns asset URN."""
        try:
            # Register upload
            register_payload = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": LINKEDIN_PERSON_URN,
                    "serviceRelationships": [{
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }],
                }
            }
            reg_resp = requests.post(REGISTER_UPLOAD_URL, json=register_payload, headers=self._headers(), timeout=30)
            reg_resp.raise_for_status()
            reg_data = reg_resp.json()

            upload_url = reg_data["value"]["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]
            asset = reg_data["value"]["asset"]

            # Download and upload image
            img_resp = requests.get(url, timeout=30)
            img_resp.raise_for_status()

            upload_resp = requests.put(
                upload_url,
                data=img_resp.content,
                headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"},
                timeout=60,
            )
            upload_resp.raise_for_status()
            return asset

        except Exception as e:
            logger.warning("LinkedIn image upload failed: %s", e)
            return None
