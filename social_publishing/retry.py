"""
social_publishing/retry.py
Retry wrapper with exponential backoff for platform publish calls.
"""

import logging
import time

from social_publishing.config import SOCIAL_RETRY_ATTEMPTS, SOCIAL_RETRY_DELAY

logger = logging.getLogger(__name__)


def retry_publish(publisher, text: str, image_url: str = None, video_url: str = None) -> dict:
    """Call publisher.publish() with automatic retries on failure.

    Uses exponential backoff: delay * 2^attempt (e.g. 2s, 4s, 8s).

    Returns the final result dict from the publisher.
    """
    last_result = None

    for attempt in range(1, SOCIAL_RETRY_ATTEMPTS + 1):
        result = publisher.publish(text, image_url=image_url, video_url=video_url)

        if result.get("success"):
            if attempt > 1:
                logger.info("%s succeeded on attempt %d", publisher.platform_name, attempt)
            return result

        last_result = result
        error = result.get("error", "unknown")

        # Don't retry on auth/config errors — they won't self-resolve
        if _is_permanent_error(error):
            logger.warning("%s permanent error, skipping retry: %s", publisher.platform_name, error)
            return result

        if attempt < SOCIAL_RETRY_ATTEMPTS:
            delay = SOCIAL_RETRY_DELAY * (2 ** (attempt - 1))
            logger.info("%s attempt %d/%d failed (%s), retrying in %.1fs",
                        publisher.platform_name, attempt, SOCIAL_RETRY_ATTEMPTS, error, delay)
            time.sleep(delay)

    logger.error("%s failed after %d attempts: %s",
                 publisher.platform_name, SOCIAL_RETRY_ATTEMPTS, last_result.get("error"))
    return last_result


def _is_permanent_error(error: str) -> bool:
    """Detect errors that won't resolve with retries."""
    permanent_keywords = [
        "not configured",
        "credentials",
        "unauthorized",
        "forbidden",
        "401",
        "403",
        "requires an image",
    ]
    error_lower = error.lower()
    return any(kw in error_lower for kw in permanent_keywords)
