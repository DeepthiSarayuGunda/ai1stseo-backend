"""
api_client.py
Shared client for all Month 1 research scripts.
Calls the backend service functions DIRECTLY (no HTTP) when running
inside the same process. Falls back to HTTP for standalone usage.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── GEO Probe APIs ───────────────────────────────────────────────────────────

def geo_probe_single(brand: str, keyword: str, provider: str = "nova") -> dict:
    from geo_probe_service import geo_probe as _geo_probe
    try:
        return _geo_probe(brand, keyword, ai_model=provider)
    except Exception as e:
        logger.warning("geo_probe_single failed: %s", e)
        return {"error": str(e), "cited": False, "confidence": 0}


def geo_probe_batch(brand: str, keywords: list, provider: str = "nova") -> dict:
    from geo_probe_service import geo_probe_batch as _batch
    try:
        return _batch(brand, keywords, ai_model=provider)
    except Exception as e:
        logger.warning("geo_probe_batch failed: %s", e)
        return {"error": str(e), "geo_score": 0, "results": []}


def geo_probe_compare(brand: str, keyword: str) -> dict:
    from geo_probe_service import geo_probe_compare as _compare
    try:
        return _compare(brand, keyword)
    except Exception as e:
        logger.warning("geo_probe_compare failed: %s", e)
        return {"error": str(e), "visibility_score": 0, "results": {}}


def geo_probe_site(site_url: str, keyword: str, provider: str = "nova") -> dict:
    from geo_probe_service import geo_probe_site as _site
    try:
        return _site(site_url, keyword, ai_model=provider)
    except Exception as e:
        logger.warning("geo_probe_site failed: %s", e)
        return {"error": str(e), "site_mentioned": False}


def geo_probe_trend(brand: str, limit: int = 30) -> dict:
    from geo_probe_service import get_visibility_trend
    try:
        return get_visibility_trend(brand, limit=limit)
    except Exception as e:
        logger.warning("geo_probe_trend failed: %s", e)
        return {"error": str(e), "trend": []}


def geo_probe_schedule(brand: str, keywords: list, provider: str = "nova", interval_minutes: int = 10080) -> dict:
    from geo_probe_service import schedule_probe
    try:
        return schedule_probe(brand, keywords, ai_model=provider, interval_minutes=interval_minutes)
    except Exception as e:
        logger.warning("geo_probe_schedule failed: %s", e)
        return {"error": str(e)}


# ── AEO & Ranking APIs ───────────────────────────────────────────────────────

def aeo_analyze(url: str, brand: str = None) -> dict:
    from aeo_optimizer import analyze_aeo
    try:
        return analyze_aeo(url, brand_name=brand)
    except Exception as e:
        logger.warning("aeo_analyze failed: %s", e)
        return {"error": str(e), "aeo_score": 0, "issues": []}


def ai_ranking_recommendations(url: str, brand: str, keywords: list = None) -> dict:
    from ai_ranking_service import get_ranking_recommendations
    geo_results = []
    if keywords:
        try:
            from geo_probe_service import geo_probe_batch as _batch
            batch = _batch(brand, keywords[:5])
            geo_results = batch.get("results", [])
        except Exception:
            pass
    try:
        return get_ranking_recommendations(url, brand, geo_results=geo_results)
    except Exception as e:
        logger.warning("ai_ranking_recommendations failed: %s", e)
        return {"error": str(e), "recommendations": []}


# ── Content Generation ────────────────────────────────────────────────────────

def content_generate(brand: str, content_type: str, topic: str, competitors: list = None, count: int = 5) -> dict:
    from content_generator import generate_content
    try:
        return generate_content(brand, content_type, topic=topic, competitors=competitors, count=count)
    except Exception as e:
        logger.warning("content_generate failed: %s", e)
        return {"error": str(e)}


# ── Full SEO Audit ────────────────────────────────────────────────────────────

def full_seo_audit(url: str) -> dict:
    """Run the 236-check audit. This one we call via HTTP since it's complex."""
    import requests as _req
    import os
    base = os.environ.get("API_BASE_URL", "http://localhost:8080")
    try:
        resp = _req.post(f"{base}/api/analyze", json={"url": url}, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}", "checks": []}
    except Exception as e:
        logger.warning("full_seo_audit failed: %s", e)
        return {"error": str(e), "checks": []}


# ── LLM Multi-Provider ───────────────────────────────────────────────────────

def llm_citation_probe(keyword: str, provider: str = "claude") -> dict:
    from llm_service import citation_probe
    try:
        return citation_probe(keyword, provider=provider)
    except Exception as e:
        logger.warning("llm_citation_probe failed for %s: %s", provider, e)
        return {"error": str(e), "status": "timeout", "provider": provider}


# ── Advanced Features ─────────────────────────────────────────────────────────

def model_comparison(brand: str, keyword: str) -> dict:
    try:
        from model_comparison import probe_all_models
        return probe_all_models(brand, keyword)
    except Exception as e:
        logger.warning("model_comparison failed: %s", e)
        return {"error": str(e), "status": "timeout"}


def share_of_voice(brand: str, competitors: list, keywords: list, provider: str = "nova") -> dict:
    try:
        from share_of_voice import calculate_sov
        return calculate_sov(brand, competitors[:5], keywords[:10], provider=provider)
    except Exception as e:
        logger.warning("share_of_voice failed: %s", e)
        return {"error": str(e)}


def prompt_simulator(brand: str, keyword: str, provider: str = "nova") -> dict:
    try:
        from prompt_simulator import run_simulation
        return run_simulation(brand, keyword, provider=provider)
    except Exception as e:
        logger.warning("prompt_simulator failed: %s", e)
        return {"error": str(e)}


def geo_scanner_scan(brand: str, url: str = None, keywords: list = None, provider: str = "nova") -> dict:
    try:
        from geo_scanner_agent import run_full_scan
        return run_full_scan(brand_name=brand, url=url, keywords=keywords or [], provider=provider)
    except Exception as e:
        logger.warning("geo_scanner_scan failed: %s", e)
        return {"error": str(e)}
