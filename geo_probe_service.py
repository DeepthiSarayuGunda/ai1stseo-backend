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
