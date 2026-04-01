"""
ai_provider.py
Unified AI provider abstraction — calls Bedrock Nova and Ollama directly.
No EC2 dependency.

Providers:
  - nova:   AWS Bedrock Nova Lite (boto3, uses Lambda IAM role)
  - ollama: Direct HTTPS call to Ollama API
"""

import json
import logging
import os
import time

import boto3
import requests

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://ollama.sageaios.com")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:30b-a3b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "15"))

NOVA_MODEL = os.environ.get("NOVA_MODEL", "us.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
BEDROCK_TIMEOUT = int(os.environ.get("BEDROCK_TIMEOUT", "120"))

_bedrock_client = None


# ── Bedrock Nova ──────────────────────────────────────────────────────────────

def _get_bedrock():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        logger.info("Bedrock client initialized (region=%s)", BEDROCK_REGION)
    return _bedrock_client


def call_nova(prompt: str) -> str:
    """Call Amazon Nova Lite via Bedrock. Returns response text."""
    client = _get_bedrock()
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.7},
    })
    t0 = time.time()
    resp = client.invoke_model(
        modelId=NOVA_MODEL,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(resp["body"].read())
    text = result["output"]["message"]["content"][0]["text"]
    logger.info("Nova responded in %.2fs (%d chars)", time.time() - t0, len(text))
    return text


# ── Ollama ────────────────────────────────────────────────────────────────────

def call_ollama(prompt: str) -> str:
    """Call Ollama API directly. Returns response text."""
    base = OLLAMA_URL.rstrip("/")
    model = OLLAMA_MODEL

    # Quick connectivity check — fail fast if server is unreachable
    try:
        requests.get(f"{base}/api/tags", timeout=5)
    except Exception:
        raise RuntimeError(f"Ollama server unreachable at {base}")

    if not model:
        try:
            tags = requests.get(f"{base}/api/tags", timeout=10).json()
            for m in tags.get("models", []):
                if "embed" not in m.get("name", ""):
                    model = m["name"]
                    break
        except Exception:
            pass
        if not model:
            raise RuntimeError("No Ollama model configured or detected")

    logger.info("Ollama call: model=%s", model)
    t0 = time.time()
    resp = requests.post(
        f"{base}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=OLLAMA_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text[:300]}")
    text = resp.json().get("response", "")
    logger.info("Ollama responded in %.2fs (%d chars)", time.time() - t0, len(text))
    return text


# ── Groq (fast cloud fallback) ────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def call_groq(prompt: str) -> str:
    """Call Groq API. Fast cloud LLM fallback."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    t0 = time.time()
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq returned {resp.status_code}: {resp.text[:300]}")
    text = resp.json()["choices"][0]["message"]["content"]
    logger.info("Groq responded in %.2fs (%d chars)", time.time() - t0, len(text))
    return text


# ── Unified interface ─────────────────────────────────────────────────────────

def generate(prompt: str, provider: str = "nova") -> str:
    """Call the specified AI provider with automatic fallback chain.

    Fallback order: requested provider → Groq → Ollama → Nova (skipping the one already tried).
    """
    # Build fallback chain based on requested provider
    if provider == "ollama":
        chain = [("ollama", call_ollama), ("groq", call_groq), ("nova", call_nova)]
    elif provider == "groq":
        chain = [("groq", call_groq), ("nova", call_nova), ("ollama", call_ollama)]
    else:  # nova (default)
        chain = [("nova", call_nova), ("groq", call_groq), ("ollama", call_ollama)]

    errors = []
    for name, fn in chain:
        try:
            return fn(prompt)
        except Exception as e:
            logger.warning("Provider '%s' failed: %s", name, str(e)[:200])
            errors.append(f"{name}: {str(e)[:100]}")

    raise RuntimeError(f"All AI providers failed. " + "; ".join(errors))


def get_available_providers() -> list[dict]:
    """Check which providers are available."""
    providers = []

    # Check Groq (fastest)
    if GROQ_API_KEY:
        providers.append({"name": "groq", "available": True, "reason": f"model: {GROQ_MODEL}"})
    else:
        providers.append({"name": "groq", "available": False, "reason": "GROQ_API_KEY not set"})

    # Check Ollama
    try:
        resp = requests.get(f"{OLLAMA_URL.rstrip('/')}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            providers.append({"name": "ollama", "available": True,
                              "reason": f"model: {OLLAMA_MODEL}", "models": models})
        else:
            providers.append({"name": "ollama", "available": False, "reason": f"HTTP {resp.status_code}"})
    except Exception as e:
        providers.append({"name": "ollama", "available": False, "reason": str(e)[:100]})

    # Check Bedrock Nova
    try:
        _get_bedrock()
        providers.append({"name": "nova", "available": True, "reason": f"model: {NOVA_MODEL}"})
    except Exception as e:
        providers.append({"name": "nova", "available": False, "reason": str(e)[:100]})

    return providers
