"""
social_publishing/config.py
Centralized configuration — all secrets from environment variables.

Required env vars per platform:
  Twitter/X:   TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
  LinkedIn:    LINKEDIN_ACCESS_TOKEN
  Facebook:    FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID
  Instagram:   INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

Optional:
  SOCIAL_POST_LOG_TABLE  — DynamoDB table for post logs (default: social-post-log)
  SOCIAL_RETRY_ATTEMPTS  — Max retries per platform (default: 3)
  SOCIAL_RETRY_DELAY     — Base delay in seconds between retries (default: 2)
  AWS_REGION             — AWS region (default: us-east-1)
"""

import os

# ---------------------------------------------------------------------------
# Twitter / X  (OAuth 1.0a for v2 tweet creation)
# ---------------------------------------------------------------------------
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET", "")
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")

# ---------------------------------------------------------------------------
# LinkedIn  (OAuth 2.0 access token)
# ---------------------------------------------------------------------------
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "")  # urn:li:person:xxx

# ---------------------------------------------------------------------------
# Facebook  (Page access token)
# ---------------------------------------------------------------------------
FACEBOOK_ACCESS_TOKEN = os.environ.get("FACEBOOK_ACCESS_TOKEN", "")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "")

# ---------------------------------------------------------------------------
# Instagram  (via Facebook Graph API)
# ---------------------------------------------------------------------------
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
SOCIAL_POST_LOG_TABLE = os.environ.get("SOCIAL_POST_LOG_TABLE", "social-post-log")
SOCIAL_RETRY_ATTEMPTS = int(os.environ.get("SOCIAL_RETRY_ATTEMPTS", "3"))
SOCIAL_RETRY_DELAY = float(os.environ.get("SOCIAL_RETRY_DELAY", "2"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# ---------------------------------------------------------------------------
# Queue / Pipeline automation
# ---------------------------------------------------------------------------
PUBLISH_QUEUE_TABLE = os.environ.get("PUBLISH_QUEUE_TABLE", "social-publish-queue")
PUBLISH_QUEUE_WORKERS = int(os.environ.get("PUBLISH_QUEUE_WORKERS", "1"))
PUBLISH_QUEUE_ENABLED = os.environ.get("PUBLISH_QUEUE_ENABLED", "0") == "1"
AUTO_PUBLISH_ENABLED = os.environ.get("AUTO_PUBLISH_ENABLED", "0") == "1"
AUTO_PUBLISH_MODE = os.environ.get("AUTO_PUBLISH_MODE", "queue").strip().lower()

# ---------------------------------------------------------------------------
# Character limits per platform
# ---------------------------------------------------------------------------
PLATFORM_LIMITS = {
    "twitter": 280,
    "linkedin": 3000,
    "facebook": 63206,
    "instagram": 2200,
}
