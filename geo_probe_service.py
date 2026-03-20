"""
geo_probe_service.py
GEO Monitoring Engine — Multi-model AI Scanner

Probes AI models with a natural user query, then performs a deterministic
case-insensitive check for brand mentions.

Supported models:
  - claude-bedrock  (live — AWS Bedrock, no API keys)
  - gemini          (placeholder)
  - perplexity      (placeholder)
"""

import logging
import re
from datetime import datetime, timezone

from bedrock_helper import invoke_claude

logger = logging.getLogger(__name__)

# ── model registry ────────────────────────────────────────────────────────────

def _invoke_gemini(prompt: str) -> str:
    """Placeholder — will use Gemini API when integrated."""
    raise NotImplementedError(
        "Gemini model is not yet configured. Set GEMINI_API_KEY and complete integration."
    )


def _invoke_perplexity(prompt: str) -> str:
    """Placeholder — will use Perplexity API when integrated."""
    raise NotImplementedError(
        "Perplexity model is not yet configured. Set PERPLEXITY_API_KEY and complete integration."
    )


MODEL_REGISTRY: dict[str, dict] = {
    "claude-bedrock": {
        "invoke": lambda prompt: invoke_claude(prompt),
        "label": "claude-bedrock",
        "status": "live",
    },
    "gemini": {
        "invoke": _invoke_gemini,
        "label": "gemini",
        "status": "placeholder",
    },
    "perplexity": {
        "invoke": _invoke_perplexity,
        "label": "perplexity",
        "status": "placeholder",
    },
}

DEFAULT_MODEL = "claude-bedrock"


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_prompt(keyword: str) -> str:
    return (
        f"You are a helpful assistant. A user is researching the following topic.\n\n"
        f"User query: {keyword}\n\n"
        f"Provide a thorough, natural answer. Mention specific brands, tools, "
        f"and products where relevant."
    )


def _extract_context(text: str, brand: str, window: int = 150) -> str | None:
    """Return 1-2 lines of surrounding context around the first brand mention."""
    match = re.search(re.escape(brand), text, re.IGNORECASE)
    if not match:
        return None
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    snippet = text[start:end].strip()
    first_dot = snippet.find('. ')
    last_dot = snippet.rfind('.')
    if first_dot != -1 and start > 0:
        snippet = snippet[first_dot + 2:]
    if last_dot != -1 and last_dot > 0 and end < len(text):
        snippet = snippet[:last_dot + 1]
    return snippet or None


def _detect_citation(response_text: str, brand_name: str) -> tuple[bool, str | None]:
    """Case-insensitive brand match + context extraction."""
    cited = bool(re.search(re.escape(brand_name), response_text, re.IGNORECASE))
    context = _extract_context(response_text, brand_name) if cited else None
    return cited, context


def available_models() -> list[dict]:
    """Return list of registered models with their status."""
    return [
        {"model": key, "status": cfg["status"]}
        for key, cfg in MODEL_REGISTRY.items()
    ]


# ── public API ────────────────────────────────────────────────────────────────

def geo_probe(brand_name: str, keyword: str, ai_model: str = DEFAULT_MODEL) -> dict:
    """
    Probe an AI model with a natural query and check for brand citation.

    Args:
        brand_name: Brand to detect in the AI response.
        keyword:    Natural language query to send.
        ai_model:   Model key from MODEL_REGISTRY (default: claude-bedrock).

    Returns:
        {
            "keyword": str,
            "ai_model": str,
            "cited": bool,
            "citation_context": str | None,
            "timestamp": str (ISO 8601)
        }

    Raises:
        ValueError:          Unknown model key.
        NotImplementedError: Model is a placeholder (not yet integrated).
        RuntimeError:        Model invocation failed.
    """
    model_cfg = MODEL_REGISTRY.get(ai_model)
    if not model_cfg:
        raise ValueError(
            f"Unknown ai_model: {ai_model!r}. "
            f"Available: {list(MODEL_REGISTRY.keys())}"
        )

    prompt = _build_prompt(keyword)
    logger.info("GEO probe: model=%s brand=%s keyword=%s", ai_model, brand_name, keyword)

    try:
        response_text = model_cfg["invoke"](prompt)
    except NotImplementedError:
        raise
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"{ai_model} invocation failed: {e}") from e

    if not response_text or not response_text.strip():
        raise RuntimeError(f"Empty response from {ai_model}")

    cited, context = _detect_citation(response_text, brand_name)
    logger.info("GEO probe result: model=%s cited=%s", ai_model, cited)

    return {
        "keyword": keyword,
        "ai_model": ai_model,
        "cited": cited,
        "citation_context": context,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

def geo_probe_batch(
    brand_name: str,
    keywords: list[str],
    ai_model: str = DEFAULT_MODEL,
) -> list[dict]:
    """
    Probe an AI model with multiple keywords and return results for each.

    Keywords that fail individually return an error entry instead of
    aborting the entire batch.
    """
    results = []
    for kw in keywords:
        try:
            results.append(geo_probe(brand_name, kw, ai_model=ai_model))
        except Exception as e:
            results.append({
                "keyword": kw,
                "ai_model": ai_model,
                "cited": None,
                "citation_context": None,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
    return results



def geo_probe_batch(
    brand_name: str,
    keywords: list[str],
    ai_model: str = DEFAULT_MODEL,
) -> list[dict]:
    """
    Probe an AI model with multiple keywords and return results for each.

    Keywords that fail individually return an error entry instead of
    aborting the entire batch.
    """
    results = []
    for kw in keywords:
        try:
            results.append(geo_probe(brand_name, kw, ai_model=ai_model))
        except Exception as e:
            results.append({
                "keyword": kw,
                "ai_model": ai_model,
                "cited": None,
                "citation_context": None,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
    return results


def geo_probe_batch(
    brand_name: str,
    keywords: list[str],
    ai_model: str = DEFAULT_MODEL,
) -> list[dict]:
    """
    Probe an AI model with multiple keywords and return results for each.

    Keywords that fail individually return an error entry instead of
    aborting the entire batch.
    """
    results = []
    for kw in keywords:
        try:
            results.append(geo_probe(brand_name, kw, ai_model=ai_model))
        except Exception as e:
            results.append({
                "keyword": kw,
                "ai_model": ai_model,
                "cited": None,
                "citation_context": None,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
    return results
