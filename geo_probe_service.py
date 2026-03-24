"""
geo_probe_service.py
GEO / AEO Monitoring Engine — Multi-Provider with Tracking & Storage

Routes AI probe requests to the EC2 geo_engine (multi-provider),
performs scoring across batches, stores results, and keeps history.

Architecture: App Runner (API gateway) → EC2 (AI engine) → Bedrock/OpenAI/Gemini/Perplexity
"""

import collections
import logging
import os
import sqlite3
import threading

import requests

logger = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────

EC2_GEO_ENGINE_URL = os.environ.get("GEO_ENGINE_URL", "http://54.226.251.216:5005")
EC2_TIMEOUT = int(os.environ.get("GEO_ENGINE_TIMEOUT", "120"))
DB_PATH = os.environ.get("GEO_PROBE_DB", "/tmp/geo_probe.db")

# ── in-memory history (last 20 batch results) ────────────────────────────────

_history: collections.deque = collections.deque(maxlen=20)

# ── SQLite storage ────────────────────────────────────────────────────────────

_db_lock = threading.Lock()


def _init_db():
    """Create the probe_results table if it doesn't exist."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS probe_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                brand TEXT NOT NULL,
                ai_model TEXT NOT NULL,
                cited INTEGER NOT NULL,
                citation_context TEXT,
                confidence REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    logger.info("GEO probe DB initialized at %s", DB_PATH)


_init_db()


def _store_result(result: dict):
    """Persist a single probe result to SQLite."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO probe_results (keyword, brand, ai_model, cited, citation_context, confidence, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    result.get("keyword", ""),
                    result.get("brand_name", result.get("brand", "")),
                    result.get("ai_model", "nova"),
                    1 if result.get("brand_present") else 0,
                    result.get("citation_context"),
                    result.get("confidence", 0.0),
                    result.get("timestamp", _now_iso()),
                ),
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error("Failed to store probe result: %s", e)


def get_stored_history(limit: int = 50, brand: str = None, ai_model: str = None) -> list[dict]:
    """Fetch stored probe results from SQLite with optional filters."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM probe_results WHERE 1=1"
            params = []
            if brand:
                query += " AND brand = ?"
                params.append(brand)
            if ai_model:
                query += " AND ai_model = ?"
                params.append(ai_model)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error("Failed to read stored history: %s", e)
        return []


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


# ── single probe (routes to EC2) ─────────────────────────────────────────────

def geo_probe(brand_name: str, keyword: str, ai_model: str = "nova") -> dict:
    """
    Probe by calling the EC2 geo_engine endpoint.
    Supports provider selection: nova (default), ollama (fallback).
    """
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

    result = {
        "keyword": keyword,
        "brand_name": brand_name,
        "ai_model": data.get("ai_model", ai_model),
        "brand_present": data["cited"],
        "citation_context": data.get("citation_context"),
        "confidence": data.get("confidence", 0.0),
        "cited_sources": [],
        "timestamp": data.get("timestamp", _now_iso()),
    }

    # Store to DB
    _store_result(result)

    return result


# ── batch probe with scoring ─────────────────────────────────────────────────

def geo_probe_batch(
    brand_name: str,
    keywords: list[str],
    ai_model: str = "nova",
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
    logger.info("GEO batch: brand=%s provider=%s score=%.2f (%d/%d)", brand_name, ai_model, geo_score, cited_count, total)
    return batch_result


# ── history ───────────────────────────────────────────────────────────────────

def get_history() -> list[dict]:
    """Return the last 20 batch probe results (newest first)."""
    return list(reversed(_history))


# ── scheduled monitoring placeholder ──────────────────────────────────────────

_scheduled_jobs = []


def schedule_probe(brand_name: str, keywords: list[str], ai_model: str = "nova",
                   interval_minutes: int = 60) -> dict:
    """
    Register a scheduled probe job (placeholder — runs in-memory only).
    In production, replace with APScheduler, Celery, or CloudWatch Events.
    """
    job = {
        "id": len(_scheduled_jobs) + 1,
        "brand_name": brand_name,
        "keywords": keywords,
        "ai_model": ai_model,
        "interval_minutes": interval_minutes,
        "status": "registered",
        "created": _now_iso(),
        "note": "Placeholder — periodic execution not yet wired. Use batch endpoint manually or integrate with cron/CloudWatch.",
    }
    _scheduled_jobs.append(job)
    logger.info("Scheduled job registered: %s", job)
    return job


def get_scheduled_jobs() -> list[dict]:
    return list(_scheduled_jobs)


# ── multi-model comparison ────────────────────────────────────────────────────

def geo_probe_compare(brand_name: str, keyword: str) -> dict:
    """
    Probe the SAME keyword across ALL available providers simultaneously.
    Returns per-provider results + cross-model visibility score.
    """
    import concurrent.futures

    # Get available providers from EC2
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

    # Cross-model visibility score
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


# ── URL/site detection in AI outputs ─────────────────────────────────────────

def geo_probe_site(site_url: str, keyword: str, ai_model: str = "nova") -> dict:
    """
    Detect if a specific website/URL is mentioned in AI output.
    Sends keyword to AI, then checks if the site domain appears in the response.
    """
    from urllib.parse import urlparse
    domain = urlparse(site_url).netloc or site_url
    # Strip www. for matching
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

    # Check for domain mention
    import re
    pattern = re.compile(re.escape(domain_clean), re.IGNORECASE)
    mentioned = bool(pattern.search(text))

    # Extract the sentence containing the mention
    context = None
    if mentioned:
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        for s in sentences:
            if pattern.search(s):
                context = s.strip()
                break

    result = {
        "site_url": site_url,
        "domain": domain_clean,
        "keyword": keyword,
        "ai_model": ai_model,
        "site_mentioned": mentioned,
        "mention_context": context,
        "timestamp": _now_iso(),
    }

    # Store to DB as well
    _store_result({
        "keyword": keyword,
        "brand_name": domain_clean,
        "ai_model": ai_model,
        "brand_present": mentioned,
        "citation_context": context,
        "confidence": 1.0 if mentioned else 0.0,
        "timestamp": _now_iso(),
    })

    return result


# ── visibility trend ──────────────────────────────────────────────────────────

def get_visibility_trend(brand: str, limit: int = 30) -> dict:
    """
    Get visibility trend for a brand over time from stored results.
    Returns daily aggregated scores.
    """
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT timestamp, cited, confidence, ai_model FROM probe_results "
                "WHERE brand = ? ORDER BY id DESC LIMIT ?",
                (brand, limit),
            ).fetchall()
            conn.close()

        if not rows:
            return {"brand": brand, "trend": [], "total_probes": 0}

        # Group by date
        from collections import defaultdict
        daily = defaultdict(lambda: {"cited": 0, "total": 0, "providers": set()})
        for r in rows:
            date = r["timestamp"][:10] if r["timestamp"] else "unknown"
            daily[date]["total"] += 1
            if r["cited"]:
                daily[date]["cited"] += 1
            daily[date]["providers"].add(r["ai_model"])

        trend = []
        for date in sorted(daily.keys()):
            d = daily[date]
            trend.append({
                "date": date,
                "visibility_score": round((d["cited"] / d["total"]) * 100) if d["total"] else 0,
                "cited": d["cited"],
                "total": d["total"],
                "providers": list(d["providers"]),
            })

        return {
            "brand": brand,
            "trend": trend,
            "total_probes": len(rows),
        }
    except Exception as e:
        logger.error("Failed to get visibility trend: %s", e)
        return {"brand": brand, "trend": [], "error": str(e)}
