"""
geo_probe_service.py
GEO / AEO Monitoring Engine — Multi-Provider with RDS Persistence

Routes AI probe requests to the EC2 geo_engine (multi-provider),
performs scoring across batches, stores results in RDS (geo_probes +
ai_visibility_history tables), and returns persisted history.

Architecture: Lambda (API) → EC2 (AI engine) → Bedrock/OpenAI/Gemini/Perplexity
              Lambda (API) → RDS PostgreSQL (persistence)
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────

EC2_GEO_ENGINE_URL = os.environ.get("GEO_ENGINE_URL", "http://54.226.251.216:5005")
EC2_TIMEOUT = int(os.environ.get("GEO_ENGINE_TIMEOUT", "120"))


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def available_models() -> list[dict]:
    """Query EC2 for available providers, fallback to static list."""
    try:
        resp = requests.get(f"{EC2_GEO_ENGINE_URL}/geo-probe/providers", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("providers", [])
    except Exception:
        pass
    return [
        {"name": "nova", "available": True, "reason": "ready"},
        {"name": "ollama", "available": True, "reason": "free fallback"},
    ]


# ── single probe (routes to EC2, persists to RDS) ────────────────────────────

def geo_probe(brand_name: str, keyword: str, ai_model: str = "nova") -> dict:
    """
    Probe by calling the EC2 geo_engine endpoint.
    Persists result to RDS geo_probes table.
    """
    from db import insert_probe

    url = f"{EC2_GEO_ENGINE_URL}/geo-probe"
    payload = {"brand_name": brand_name, "keyword": keyword, "provider": ai_model}

    logger.info("GEO probe → EC2: brand=%s keyword=%s provider=%s", brand_name, keyword, ai_model)

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
    logger.info("GEO probe ← EC2: provider=%s cited=%s confidence=%s", ai_model, data.get("cited"), data.get("confidence"))

    cited = bool(data.get("cited"))
    context = data.get("citation_context")
    confidence = data.get("confidence", 0.0)

    # Persist to RDS
    try:
        insert_probe(
            keyword=keyword,
            brand=brand_name,
            ai_model=data.get("ai_model", ai_model),
            cited=cited,
            citation_context=context,
            confidence=confidence,
            response_snippet=data.get("ai_summary", data.get("text", ""))[:2000] if data.get("ai_summary") or data.get("text") else None,
            query_text=keyword,
        )
    except Exception as e:
        logger.error("Failed to persist probe to RDS: %s", e)

    return {
        "keyword": keyword,
        "brand_name": brand_name,
        "ai_model": data.get("ai_model", ai_model),
        "brand_present": cited,
        "citation_context": context,
        "confidence": confidence,
        "cited_sources": [],
        "timestamp": data.get("timestamp", _now_iso()),
    }


# ── batch probe with scoring (persists to RDS) ───────────────────────────────

def geo_probe_batch(brand_name: str, keywords: list[str], ai_model: str = "nova") -> dict:
    """Probe multiple keywords via EC2, compute geo_score, persist batch to RDS."""
    from db import insert_visibility_batch

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

    # Persist batch summary to RDS
    try:
        insert_visibility_batch(
            brand=brand_name,
            ai_model=ai_model,
            keyword=", ".join(keywords),
            geo_score=geo_score,
            cited_count=cited_count,
            total_prompts=total,
            batch_results=batch_result,
        )
    except Exception as e:
        logger.error("Failed to persist batch to RDS: %s", e)

    logger.info("GEO batch: brand=%s provider=%s score=%.2f (%d/%d)", brand_name, ai_model, geo_score, cited_count, total)
    return batch_result


# ── history (reads from RDS) ──────────────────────────────────────────────────

def get_history() -> list[dict]:
    """Return recent batch probe results from RDS ai_visibility_history."""
    from db import get_visibility_history
    return get_visibility_history(limit=20)


def get_stored_history(limit: int = 50, brand: str = None, ai_model: str = None) -> list[dict]:
    """Fetch stored probe results from RDS geo_probes table."""
    from db import get_probes
    return get_probes(limit=limit, brand=brand, ai_model=ai_model)


# ── scheduled monitoring placeholder ──────────────────────────────────────────

_scheduled_jobs = []


def schedule_probe(brand_name: str, keywords: list[str], ai_model: str = "nova",
                   interval_minutes: int = 60) -> dict:
    """
    Register a scheduled probe job (placeholder).
    In production, replace with EventBridge + SQS.
    """
    job = {
        "id": len(_scheduled_jobs) + 1,
        "brand_name": brand_name,
        "keywords": keywords,
        "ai_model": ai_model,
        "interval_minutes": interval_minutes,
        "status": "registered",
        "created": _now_iso(),
        "note": "Placeholder — periodic execution not yet wired. Use batch endpoint manually or integrate with EventBridge.",
    }
    _scheduled_jobs.append(job)
    logger.info("Scheduled job registered: %s", job)
    return job


def get_scheduled_jobs() -> list[dict]:
    return list(_scheduled_jobs)


# ── multi-model comparison (persists each probe to RDS) ──────────────────────

def geo_probe_compare(brand_name: str, keyword: str) -> dict:
    """
    Probe the SAME keyword across ALL available providers simultaneously.
    Each individual probe is persisted to RDS via geo_probe().
    """
    import concurrent.futures

    providers = []
    try:
        resp = requests.get(f"{EC2_GEO_ENGINE_URL}/geo-probe/providers", timeout=5)
        if resp.status_code == 200:
            providers = [p["name"] for p in resp.json().get("providers", []) if p.get("available")]
    except Exception:
        providers = ["nova", "ollama"]

    results = {}

    def _probe(provider):
        try:
            return provider, geo_probe(brand_name, keyword, ai_model=provider)
        except Exception as e:
            return provider, {
                "keyword": keyword,
                "ai_model": provider,
                "brand_present": None,
                "citation_context": None,
                "confidence": 0.0,
                "error": str(e),
                "timestamp": _now_iso(),
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(_probe, p): p for p in providers}
        for f in concurrent.futures.as_completed(futures):
            provider, result = f.result()
            results[provider] = result

    total = len(results)
    cited_count = sum(1 for r in results.values() if r.get("brand_present") is True)
    avg_confidence = round(
        sum(r.get("confidence", 0) for r in results.values()) / total, 2
    ) if total else 0.0
    visibility_score = round((cited_count / total) * 100) if total else 0

    return {
        "brand_name": brand_name,
        "keyword": keyword,
        "providers_queried": list(results.keys()),
        "results": results,
        "visibility_score": visibility_score,
        "cited_count": cited_count,
        "total_providers": total,
        "avg_confidence": avg_confidence,
        "timestamp": _now_iso(),
    }


# ── URL/site detection in AI outputs (persists to RDS) ───────────────────────

def geo_probe_site(site_url: str, keyword: str, ai_model: str = "nova") -> dict:
    """
    Detect if a specific website/URL is mentioned in AI output.
    Persists result to RDS geo_probes table.
    """
    from urllib.parse import urlparse
    from db import insert_probe
    import re

    domain = urlparse(site_url).netloc or site_url
    domain_clean = domain.replace("www.", "")

    url = f"{EC2_GEO_ENGINE_URL}/generate"
    prompt = (
        f"A user asks: \"{keyword}\"\n\n"
        f"Provide a comprehensive answer with specific website recommendations, "
        f"tools, and resources. Include URLs where relevant."
    )

    try:
        resp = requests.post(url, json={"prompt": prompt, "provider": ai_model}, timeout=EC2_TIMEOUT)
        if resp.status_code != 200:
            raise RuntimeError(f"EC2 returned {resp.status_code}")
        text = resp.json().get("text", "")
    except Exception as e:
        return {
            "site_url": site_url,
            "keyword": keyword,
            "ai_model": ai_model,
            "site_mentioned": None,
            "error": str(e),
            "timestamp": _now_iso(),
        }

    pattern = re.compile(re.escape(domain_clean), re.IGNORECASE)
    mentioned = bool(pattern.search(text))

    context = None
    if mentioned:
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        for s in sentences:
            if pattern.search(s):
                context = s.strip()
                break

    # Persist to RDS
    try:
        insert_probe(
            keyword=keyword,
            brand=domain_clean,
            ai_model=ai_model,
            cited=mentioned,
            citation_context=context,
            confidence=1.0 if mentioned else 0.0,
            site_url=site_url,
            response_snippet=text[:2000] if text else None,
            query_text=prompt,
        )
    except Exception as e:
        logger.error("Failed to persist site probe to RDS: %s", e)

    return {
        "site_url": site_url,
        "domain": domain_clean,
        "keyword": keyword,
        "ai_model": ai_model,
        "site_mentioned": mentioned,
        "mention_context": context,
        "timestamp": _now_iso(),
    }


# ── visibility trend (reads from RDS) ────────────────────────────────────────

def get_visibility_trend(brand: str, limit: int = 30) -> dict:
    """Get visibility trend for a brand over time from RDS."""
    from db import get_probe_trend
    try:
        trend = get_probe_trend(brand, limit=limit)
        return {
            "brand": brand,
            "trend": trend,
            "total_probes": sum(t.get("total", 0) for t in trend),
        }
    except Exception as e:
        logger.error("Failed to get visibility trend: %s", e)
        return {"brand": brand, "trend": [], "error": str(e)}
