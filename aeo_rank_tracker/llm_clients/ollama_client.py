"""
Ollama (local LLM) client for AEO Rank Tracker.
Connects to a local or remote Ollama instance.
FREE — no API key required.

Env vars:
    OLLAMA_URL   — default http://localhost:11434
    OLLAMA_MODEL — default llama3
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))


def is_available() -> bool:
    """Check if Ollama is reachable and has a model loaded."""
    try:
        resp = requests.get(
            f"{OLLAMA_URL.rstrip('/')}/api/tags",
            timeout=5,
        )
        if resp.status_code != 200:
            return False
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        # Accept if any model is available (prefer configured one)
        return len(models) > 0
    except Exception:
        return False


def get_models() -> list[str]:
    """Return list of available Ollama model names."""
    try:
        resp = requests.get(
            f"{OLLAMA_URL.rstrip('/')}/api/tags",
            timeout=5,
        )
        if resp.status_code == 200:
            return [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def query_llm(prompt: str) -> dict:
    """Query Ollama and return standardized response."""
    base = OLLAMA_URL.rstrip("/")
    model = OLLAMA_MODEL

    # Verify connectivity
    try:
        resp = requests.get(f"{base}/api/tags", timeout=5)
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama returned {resp.status_code}")
        # Auto-detect model if configured one isn't available
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        if model not in models and models:
            # Try partial match (e.g. "llama3" matches "llama3:latest")
            matched = [m for m in models if model in m]
            model = matched[0] if matched else models[0]
            logger.info("Ollama model auto-selected: %s", model)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Ollama not reachable at {base}")

    t0 = time.time()
    resp = requests.post(
        f"{base}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=OLLAMA_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text[:300]}")

    text = resp.json().get("response", "")
    logger.info("Ollama (%s) responded in %.2fs (%d chars)", model, time.time() - t0, len(text))

    return {"response_text": text, "sources": []}
