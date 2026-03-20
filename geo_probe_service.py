"""
geo_probe_service.py
GEO / AEO Monitoring Engine — EC2-routed AI Scanner

Routes AI probe requests to the EC2 geo_engine (which has Bedrock access),
performs scoring across batches, and keeps in-memory history.

Architecture: App Runner (API gateway) → EC2 (AI engine) → Bedrock (Claude)
"""

import collections
import logging
import os

import requests

logger = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────

EC2_GEO_ENGINE_URL = os.environ.get("GEO_ENGINE_URL", "http://54.226.251.216:5005")
EC2_TIMEOUT = int(os.environ.get("GEO_ENGINE_TIMEOUT", "30"))

# ── in-memory history (last 20 batch results) ────────────────────────────────

_history: collections.deque = collections.deque(maxlen=20)


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def available_models() -> list[dict]:
    return [
        {"model": "claude", "status": "live", "engine": "ec2-bedrock"},
    ]


# ── single probe (routes to EC2) ─────────────────────────────────────────────

def geo_probe(brand_name: str, keyword: str, ai_model: str = "claude") -> dict:
    """
    Probe by calling the EC2 geo_engine endpoint.

    Sends the raw keyword to EC2 — the geo_engine prompt already asks
    Claude to include the brand *only if genuinely relevant*, so we
    don't bias the keyword here (avoids false positives for fake brands).
    """
    url = f"{EC2_GEO_ENGINE_URL}/geo-probe"
    payload = {"brand_name": brand_name, "keyword": keyword}

    logger.info("GEO probe → EC2: brand=%s keyword=%s url=%s", brand_name, keyword, url)

    try:
        resp = requests.post(url, json=payload, timeout=EC2_TIMEOUT)
    except requests.ConnectionError as e:
        raise RuntimeError(f"EC2 geo_engine unreachable at {url}: {e}") from e
    except requests.Timeout:
        raise RuntimeError(f"EC2 geo_engine timed out after {EC2_TIMEOUT}s")

    if resp.status_code != 200:
        error_msg = resp.json().get("error", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise RuntimeError(f"EC2 geo_engine returned {resp.status_code}: {error_msg}")

    data = resp.json()
    logger.info("GEO probe ← EC2: cited=%s confidence=%s", data.get("cited"), data.get("confidence"))

    return {
        "keyword": keyword,
        "ai_model": data.get("ai_model", "claude"),
        "brand_present": data["cited"],
        "citation_context": data.get("citation_context"),
        "confidence": data.get("confidence", 0.0),
        "cited_sources": [],
        "timestamp": data.get("timestamp", _now_iso()),
    }


# ── batch probe with scoring ─────────────────────────────────────────────────

def geo_probe_batch(
    brand_name: str,
    keywords: list[str],
    ai_model: str = "claude",
) -> dict:
    """Probe multiple keywords via EC2, compute geo_score, store in history."""
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
                "confidence": 0.0,
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
    logger.info("GEO batch: brand=%s score=%.2f (%d/%d)", brand_name, geo_score, cited_count, total)
    return batch_result


# ── history ───────────────────────────────────────────────────────────────────

def get_history() -> list[dict]:
    """Return the last 20 batch probe results (newest first)."""
    return list(reversed(_history))
