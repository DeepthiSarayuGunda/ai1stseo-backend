"""
api_client.py
Shared HTTP client for all Month 1 research scripts.
Wraps the AI1stSEO backend API with retry logic and structured responses.
"""

import json
import os
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:5001")
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def _url(path: str) -> str:
    return f"{API_BASE.rstrip('/')}{path}"


def _request(method: str, path: str, payload: dict = None, params: dict = None, retries: int = MAX_RETRIES) -> dict:
    """Make an API request with retry logic."""
    for attempt in range(retries):
        try:
            if method == "GET":
                resp = requests.get(_url(path), params=params, timeout=120)
            else:
                resp = requests.post(_url(path), json=payload, timeout=120)

            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 503:
                logger.warning("Service unavailable on %s, retry %d/%d", path, attempt + 1, retries)
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            else:
                logger.error("API error %d on %s: %s", resp.status_code, path, resp.text[:200])
                return {"error": resp.text, "status_code": resp.status_code}
        except requests.exceptions.Timeout:
            logger.warning("Timeout on %s, retry %d/%d", path, attempt + 1, retries)
            time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError:
            logger.error("Connection error on %s", path)
            time.sleep(RETRY_DELAY)

    return {"error": f"Failed after {retries} retries", "path": path}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── GEO Probe APIs ───────────────────────────────────────────────────────────

def geo_probe_single(brand: str, keyword: str, provider: str = "nova") -> dict:
    return _request("POST", "/api/geo-probe", {"brand_name": brand, "keyword": keyword, "provider": provider})


def geo_probe_batch(brand: str, keywords: list, provider: str = "nova") -> dict:
    return _request("POST", "/api/geo-probe/batch", {"brand_name": brand, "keywords": keywords, "provider": provider})


def geo_probe_compare(brand: str, keyword: str) -> dict:
    return _request("POST", "/api/geo-probe/compare", {"brand_name": brand, "keyword": keyword})


def geo_probe_site(site_url: str, keyword: str, provider: str = "nova") -> dict:
    return _request("POST", "/api/geo-probe/site", {"site_url": site_url, "keyword": keyword, "provider": provider})


def geo_probe_trend(brand: str, limit: int = 30) -> dict:
    return _request("GET", "/api/geo-probe/trend", params={"brand": brand, "limit": limit})


def geo_probe_history(brand: str = None, ai_model: str = None, limit: int = 50) -> dict:
    params = {"limit": limit}
    if brand:
        params["brand"] = brand
    if ai_model:
        params["ai_model"] = ai_model
    return _request("GET", "/api/geo-probe/history", params=params)


def geo_probe_schedule(brand: str, keywords: list, provider: str = "nova", interval_minutes: int = 10080) -> dict:
    return _request("POST", "/api/geo-probe/schedule", {
        "brand_name": brand, "keywords": keywords, "provider": provider, "interval_minutes": interval_minutes
    })


# ── AEO & Ranking APIs ───────────────────────────────────────────────────────

def aeo_analyze(url: str, brand: str = None) -> dict:
    payload = {"url": url}
    if brand:
        payload["brand_name"] = brand
    return _request("POST", "/api/aeo/analyze", payload)


def ai_ranking_recommendations(url: str, brand: str, keywords: list = None) -> dict:
    payload = {"url": url, "brand_name": brand}
    if keywords:
        payload["keywords"] = keywords
    return _request("POST", "/api/ai/ranking-recommendations", payload)


# ── Content Generation ────────────────────────────────────────────────────────

def content_generate(brand: str, content_type: str, topic: str, competitors: list = None, count: int = 5) -> dict:
    payload = {"brand_name": brand, "content_type": content_type, "topic": topic, "count": count}
    if competitors:
        payload["competitors"] = competitors
    return _request("POST", "/api/content/generate", payload)


# ── Full SEO Audit ────────────────────────────────────────────────────────────

def full_seo_audit(url: str) -> dict:
    return _request("POST", "/api/analyze", {"url": url})


# ── LLM Multi-Provider ───────────────────────────────────────────────────────

def llm_providers() -> dict:
    return _request("GET", "/api/llm/providers")


def llm_citation_probe(keyword: str, provider: str = "claude") -> dict:
    return _request("POST", "/api/llm/citation-probe", {"keyword": keyword, "provider": provider})


# ── Advanced Features ─────────────────────────────────────────────────────────

def model_comparison(brand: str, keyword: str) -> dict:
    return _request("POST", "/api/geo/model-comparison", {"brand_name": brand, "keyword": keyword})


def share_of_voice(brand: str, competitors: list, keywords: list, provider: str = "nova") -> dict:
    return _request("POST", "/api/geo/share-of-voice", {
        "brand": brand, "competitors": competitors, "keywords": keywords, "provider": provider
    })


def prompt_simulator(brand: str, keyword: str, provider: str = "nova") -> dict:
    return _request("POST", "/api/geo/prompt-simulator", {"brand": brand, "keyword": keyword, "provider": provider})


def geo_scanner_scan(brand: str, url: str = None, keywords: list = None, provider: str = "nova") -> dict:
    payload = {"brand_name": brand, "provider": provider}
    if url:
        payload["url"] = url
    if keywords:
        payload["keywords"] = keywords
    return _request("POST", "/api/geo-scanner/scan", payload)
