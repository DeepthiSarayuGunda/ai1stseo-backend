"""
growth/email_platform_sync.py
Integration hook for syncing subscribers to external email platforms
(Brevo, MailerLite, etc.).

Currently a safe no-op — logs the sync intent without making external
API calls. Replace the placeholder logic when credentials are available.

Environment variables (not required yet):
    EMAIL_PLATFORM          — "brevo" | "mailerlite" | "" (disabled)
    EMAIL_PLATFORM_API_KEY  — API key for the chosen platform
"""

import logging
import os

logger = logging.getLogger(__name__)

PLATFORM = os.environ.get("EMAIL_PLATFORM", "")
API_KEY = os.environ.get("EMAIL_PLATFORM_API_KEY", "")


def sync_subscriber_to_email_platform(subscriber_data: dict) -> dict:
    """Sync a new subscriber to the configured email platform.

    Args:
        subscriber_data: dict with keys:
            - email (str, required)
            - name (str or None)
            - source (str)
            - platform (str or None)
            - campaign (str or None)
            - subscriber_id (str, DB UUID)
            - subscribed_at (str, ISO timestamp)

    Returns:
        dict with "synced" bool and optional "provider" / "error" keys.
    """
    if not PLATFORM or not API_KEY:
        logger.debug(
            "email_platform_sync: no-op (EMAIL_PLATFORM=%s, key_set=%s) — %s",
            PLATFORM or "(not set)", bool(API_KEY), subscriber_data.get("email"),
        )
        return {"synced": False, "provider": None, "reason": "no platform configured"}

    # --- Future: real provider calls go here ---
    # if PLATFORM == "brevo":
    #     return _sync_brevo(subscriber_data)
    # if PLATFORM == "mailerlite":
    #     return _sync_mailerlite(subscriber_data)

    logger.warning("email_platform_sync: unknown platform '%s'", PLATFORM)
    return {"synced": False, "provider": PLATFORM, "reason": "unknown platform"}
