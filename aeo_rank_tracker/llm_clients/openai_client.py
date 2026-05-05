"""
OpenAI (ChatGPT) client for AEO Rank Tracker.
Uses the OpenAI Chat Completions API.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = int(os.environ.get("OPENAI_TIMEOUT", "30"))


def query_llm(prompt: str) -> dict:
    """Query ChatGPT and return standardized response."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    t0 = time.time()
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.7,
        },
        timeout=OPENAI_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    logger.info("OpenAI responded in %.2fs (%d chars)", time.time() - t0, len(text))

    return {"response_text": text, "sources": []}
