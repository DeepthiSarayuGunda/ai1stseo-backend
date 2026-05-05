"""
Google Gemini client for AEO Rank Tracker.
Uses the Gemini generateContent API.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "30"))


def query_llm(prompt: str) -> dict:
    """Query Gemini and return standardized response."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    t0 = time.time()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.7},
        },
        timeout=GEMINI_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    logger.info("Gemini responded in %.2fs (%d chars)", time.time() - t0, len(text))

    return {"response_text": text, "sources": []}
