"""
Anthropic (Claude) client for AEO Rank Tracker.
Uses the Anthropic Messages API.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
ANTHROPIC_TIMEOUT = int(os.environ.get("ANTHROPIC_TIMEOUT", "30"))


def query_llm(prompt: str) -> dict:
    """Query Claude and return standardized response."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    t0 = time.time()
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=ANTHROPIC_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["content"][0]["text"]
    logger.info("Claude responded in %.2fs (%d chars)", time.time() - t0, len(text))

    return {"response_text": text, "sources": []}
