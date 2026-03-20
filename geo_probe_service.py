"""
geo_probe_service.py
GEO / AEO Monitoring Engine — Multi-model AI Scanner

Probes AI models with natural user queries, performs deterministic
case-insensitive brand detection, computes a geo_score across batches,
and keeps a lightweight in-memory history of recent results.

Supported models:
  - claude-bedrock  (live — AWS Bedrock, IAM role)
  - gemini          (placeholder)
  - perplexity      (placeholder)
"""

import collections
import logging
import re
from datetime import datetime, timezone

from bedrock_helper import invoke_claude

logger = logging.getLogger(__name__)

# ── in-memory history (last 20 batch results) ────────────────────────────────

_history: collections.deque = collections.deque(maxlen=20)

# ── model registry ────────────────────────────────────────────────────────────

def _invoke_gemini(prompt: str) -> str:
    raise NotImplementedError(
        "Gemini model is not yet configured. Set GEMINI_API_KEY and complete integration."
    )

def _invoke_perplexity(prompt: str) -> str:
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
        f"and products where relevant. Cite sources where possible."
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


def _extract_sources(text: str) -> list[str]:
    """Extract URLs and named source references from the response."""
    urls = re.findall(r'https?://[^\s\)\]\"\']+', text)
    refs = re.findall(
        r'(?:Source|Reference|According to|Cited from)[:\s]+([^\n.]+)',
        text, re.IGNORECASE,
    )
    return list(dict.fromkeys(urls + [r.strip() for r in refs]))[:10]


def _detect_citation(response_text: str, brand_name: str) -> tuple[bool, str | None]:
    cited = bool(re.search(re.escape(brand_name), response_text, re.IGNORECASE))
    context = _extract_context(response_text, brand_name) if cited else None
    return cited, context


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def available_models() -> list[dict]:
    return [{"model": k, "status": v["status"]} for k, v in MODEL_REGISTRY.items()]


# ── single probe ──────────────────────────────────────────────────────────────

def geo_probe(brand_name: str, keyword: str, ai_model: str = DEFAULT_MODEL) -> dict:
    """Probe one keyword and return citation result."""
    model_cfg = MODEL_REGISTRY.get(ai_model)
    if not model_cfg:
        raise ValueError(
            f"Unknown ai_model: {ai_model!r}. Available: {list(MODEL_REGISTRY.keys())}"
        )

    prompt = _build_prompt(keyword)
    logger.info("GEO probe: model=%s brand=%s keyword=%s", ai_model, brand_name, keyword)

    try:
        response_text = model_cfg["invoke"](prompt)
    except (NotImplementedError, RuntimeError):
        raise
    except Exception as e:
        raise RuntimeError(f"{ai_model} invocation failed: {e}") from e

    if not response_text or not response_text.strip():
        raise RuntimeError(f"Empty response from {ai_model}")

    cited, context = _detect_citation(response_text, brand_name)
    sources = _extract_sources(response_text)
    logger.info("GEO probe result: model=%s cited=%s", ai_model, cited)

    return {
        "keyword": keyword,
        "ai_model": ai_model,
        "brand_present": cited,
        "citation_context": context,
        "cited_sources": sources,
        "timestamp": _now_iso(),
    }


# ── batch probe with scoring ─────────────────────────────────────────────────

def geo_probe_batch(
    brand_name: str,
    keywords: list[str],
    ai_model: str = DEFAULT_MODEL,
) -> dict:
    """
    Probe multiple keywords, compute geo_score, store in history.

    Returns:
        {
            "brand_name": str,
            "ai_model": str,
            "results": [...],
            "geo_score": float (0.0 – 1.0),
            "total_prompts": int,
            "cited_count": int,
            "timestamp": str
        }
    """
    results = []
    for kw in keywords:
        try:
            results.append(geo_probe(brand_name, kw, ai_model=ai_model))
        except Exception as e:
            results.append({
                "keyword": kw,
                "ai_model": ai_model,
                "brand_present": None,
                "citation_context": None,
                "cited_sources": [],
                "error": str(e),
                "timestamp": _now_iso(),
            })

    total = len(results)
    cited_count = sum(1 for r in results if r.get("brand_present") is True)
    geo_score = round(cited_count / total, 2) if total else 0.0

    batch_result = {
        "brand_name": brand_name,
        "ai_model": ai_model,
        "results": results,
        "geo_score": geo_score,
        "total_prompts": total,
        "cited_count": cited_count,
        "timestamp": _now_iso(),
    }

    _history.append(batch_result)
    logger.info(
        "GEO batch: brand=%s score=%.2f (%d/%d)",
        brand_name, geo_score, cited_count, total,
    )
    return batch_result


# ── history ───────────────────────────────────────────────────────────────────

def get_history() -> list[dict]:
    """Return the last 20 batch probe results (newest first)."""
    return list(reversed(_history))
