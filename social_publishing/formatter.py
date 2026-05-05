"""
social_publishing/formatter.py
Platform-specific content formatting.

Each platform has different character limits, hashtag conventions,
and media handling. This module adapts a single content payload
into platform-optimized versions.
"""

import re

from social_publishing.config import PLATFORM_LIMITS


def format_for_platform(text: str, platform: str, image_url: str = None, video_url: str = None) -> dict:
    """Format content for a specific platform.

    Returns:
        {"text": str, "image_url": str|None, "video_url": str|None, "truncated": bool}
    """
    platform = platform.strip().lower()
    formatter = _FORMATTERS.get(platform, _format_default)
    return formatter(text, image_url, video_url)


def _format_twitter(text: str, image_url: str = None, video_url: str = None) -> dict:
    """Twitter/X: 280 chars. Shorten text, keep hashtags, strip markdown."""
    limit = PLATFORM_LIMITS["twitter"]
    clean = _strip_markdown(text)
    truncated = False

    # If media is attached, Twitter reserves ~24 chars for the URL
    effective_limit = limit - 24 if (image_url or video_url) else limit

    if len(clean) > effective_limit:
        clean = clean[: effective_limit - 1] + "…"
        truncated = True

    return {"text": clean, "image_url": image_url, "video_url": video_url, "truncated": truncated}


def _format_linkedin(text: str, image_url: str = None, video_url: str = None) -> dict:
    """LinkedIn: 3000 chars. Keep professional tone, preserve line breaks."""
    limit = PLATFORM_LIMITS["linkedin"]
    clean = _strip_markdown(text)
    truncated = False

    if len(clean) > limit:
        clean = clean[: limit - 1] + "…"
        truncated = True

    return {"text": clean, "image_url": image_url, "video_url": video_url, "truncated": truncated}


def _format_facebook(text: str, image_url: str = None, video_url: str = None) -> dict:
    """Facebook: 63k chars. Minimal formatting needed."""
    limit = PLATFORM_LIMITS["facebook"]
    truncated = len(text) > limit
    clean = text[:limit] if truncated else text

    return {"text": clean, "image_url": image_url, "video_url": video_url, "truncated": truncated}


def _format_instagram(text: str, image_url: str = None, video_url: str = None) -> dict:
    """Instagram: 2200 chars. Requires image or video. Move hashtags to end."""
    limit = PLATFORM_LIMITS["instagram"]
    clean = _strip_markdown(text)

    # Extract hashtags and move to end for cleaner captions
    hashtags = re.findall(r"#\w+", clean)
    body = re.sub(r"\s*#\w+", "", clean).strip()
    hashtag_block = "\n\n" + " ".join(hashtags) if hashtags else ""

    full = body + hashtag_block
    truncated = False
    if len(full) > limit:
        # Trim body, keep hashtags
        available = limit - len(hashtag_block) - 1
        body = body[:available] + "…"
        full = body + hashtag_block
        truncated = True

    return {"text": full, "image_url": image_url, "video_url": video_url, "truncated": truncated}


def _format_default(text: str, image_url: str = None, video_url: str = None) -> dict:
    """Fallback: no special formatting."""
    return {"text": text, "image_url": image_url, "video_url": video_url, "truncated": False}


def _strip_markdown(text: str) -> str:
    """Remove common markdown formatting from text."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)        # italic
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)  # links
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headers
    return text.strip()


_FORMATTERS = {
    "twitter": _format_twitter,
    "x": _format_twitter,
    "linkedin": _format_linkedin,
    "facebook": _format_facebook,
    "instagram": _format_instagram,
}
