"""
Perplexity client for AEO Rank Tracker.
Uses the Perplexity Chat Completions API (OpenAI-compatible).
Perplexity returns citations in the response.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL = os.environ.get("PERPLEXITY_MODEL", "sonar")
PERPLEXITY_TIMEOUT = int(os.environ.get("PERPLEXITY_TIMEOUT", "30"))


def query_llm(prompt: str) -> dict:
    """Query Perplexity and return standardized response with sources."""
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY not set")

    t0 = time.time()
    resp = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": PERPLEXITY_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
        },
        timeout=PERPLEXITY_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Perplexity returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    # Perplexity includes citations in the response
    sources = data.get("citations", [])
    logger.info("Perplexity responded in %.2fs (%d chars, %d sources)",
                time.time() - t0, len(text), len(sources))

    return {"response_text": text, "sources": sources}
