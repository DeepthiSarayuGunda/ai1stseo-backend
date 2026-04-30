"""
social_publishing/platforms/base.py
Abstract base class for all platform publishers.
"""

from abc import ABC, abstractmethod


class BasePlatformPublisher(ABC):
    """Interface that every platform publisher must implement."""

    platform_name: str = ""

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Return True if all required credentials are present."""

    @abstractmethod
    def publish(self, text: str, image_url: str = None, video_url: str = None) -> dict:
        """Publish content to the platform.

        Returns:
            {"success": bool, "platform": str, "post_id": str|None, "error": str|None, "raw": dict|None}
        """

    def _success(self, post_id: str = None, raw: dict = None) -> dict:
        return {"success": True, "platform": self.platform_name, "post_id": post_id, "error": None, "raw": raw}

    def _failure(self, error: str, raw: dict = None) -> dict:
        return {"success": False, "platform": self.platform_name, "post_id": None, "error": error, "raw": raw}
