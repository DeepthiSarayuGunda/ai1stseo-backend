"""
Groq client for AEO Rank Tracker.
Uses the Groq OpenAI-compatible API. Fast and free tier available.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.environ.get("GROQ_TIMEOUT", "30"))


def query_llm(prompt: str) -> dict:
    """Query Groq and return standardized response."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")

    t0 = time.time()
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.7,
        },
        timeout=GROQ_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    logger.info("Groq responded in %.2fs (%d chars)", time.time() - t0, len(text))

    return {"response_text": text, "sources": []}
