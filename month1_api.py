"""
month1_api.py
Month 1 Research API — Flask routes for all 8 deliverables.

Long-running tasks (benchmark, provider behaviour, run-all) use a
thread-based async job pattern: POST returns a job_id immediately,
GET /api/month1/job/<job_id> polls for results.
"""

import json
import logging
import os
import time
import threading
import traceback
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "month1_research", "output")

# ── In-memory job store ───────────────────────────────────────────────────────
# job_id -> {status, result, error, started_at, finished_at}
_jobs: dict[str, dict] = {}
_MAX_JOBS = 50  # keep last N jobs in memory


def _ensure_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _save(name, data):
    _ensure_output()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"{name}_{ts}.json"
    path = os.path.join(OUTPUT_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return fname


def _persist_to_rds(table_name, data):
    try:
        from db import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ai_visibility_history
                (brand_name, ai_model, keyword, geo_score, batch_results, measured_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (
                data.get("brand", "month1"),
                "month1_research",
                table_name,
                data.get("geo_score", 0),
                json.dumps(data, default=str),
            ))
            conn.commit()
    except Exception as e:
        logger.warning("RDS persist failed for %s: %s", table_name, e)

# ── Async Job Infrastructure ──────────────────────────────────────────────────

def _start_job(job_type, fn, args=()):
    """Start a background job. Returns job_id immediately."""
    job_id = str(uuid.uuid4())[:12]
    _jobs[job_id] = {
        "status": "pending",
        "job_type": job_type,
        "result": None,
        "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    # Prune old jobs
    if len(_jobs) > _MAX_JOBS:
        oldest = sorted(_jobs.keys(), key=lambda k: _jobs[k]["started_at"])
        for k in oldest[:len(_jobs) - _MAX_JOBS]:
            del _jobs[k]

    def _worker():
        try:
            result = fn(*args)
            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["result"] = result
        except Exception as e:
            logger.error("Job %s (%s) failed: %s", job_id, job_type, traceback.format_exc())
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
        finally:
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return job_id


def api_job_status(job_id):
    """Check status of an async job."""
    job = _jobs.get(job_id)
    if not job:
        return {"error": "Job not found", "job_id": job_id}, 404
    resp = {
        "job_id": job_id,
        "status": job["status"],
        "job_type": job["job_type"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
    }
    if job["status"] == "complete":
        resp["result"] = job["result"]
    elif job["status"] == "failed":
        resp["error"] = job["error"]
    return resp, 200


# ── Deliverable 1: Keyword Universe (sync — fast) ────────────────────────────

def api_keyword_universe(data):
    from month1_research.keyword_universe import generate_keyword_universe
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    topic = (data.get("topic") or "").strip()
    if not brand or not topic:
        return {"error": "brand and topic are required"}, 400
    result = generate_keyword_universe(brand, topic)
    fname = _save("keyword_universe", result)
    _persist_to_rds("keyword_universe", {"brand": brand, "geo_score": 0})
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 2: Benchmark Runner (ASYNC — long running) ───────────────────

def _run_benchmark_job(data):
    from month1_research.benchmark_runner import run_benchmark
    brand = data["brand"]
    result = run_benchmark(
        brand, data.get("url", ""),
        data["competitors"], data.get("visibility_brands", []),
        keywords=data.get("keywords"))
    fname = _save("benchmark_report", result)
    _persist_to_rds("benchmark_report", {"brand": brand})
    result["saved_as"] = fname
    return result


def api_benchmark(data):
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    competitors = data.get("competitors") or []
    if not brand:
        return {"error": "brand is required"}, 400
    if not competitors:
        return {"error": "competitors list is required"}, 400
    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.split(",")]
    vis = data.get("visibility_brands") or []
    if isinstance(vis, str):
        vis = [v.strip() for v in vis.split(",")]
    job_data = {
        "brand": brand, "url": (data.get("url") or "").strip(),
        "competitors": competitors, "visibility_brands": vis,
        "keywords": data.get("keywords"),
    }
    job_id = _start_job("benchmark", _run_benchmark_job, (job_data,))
    return {"job_id": job_id, "status": "pending", "message": "Benchmark job started"}, 202


# ── Deliverable 3: Provider Behaviour (ASYNC — long running) ──────────────────

def _run_provider_behaviour_job(data):
    from month1_research.provider_behaviour import analyze_provider_behaviour
    brand = data["brand"]
    result = analyze_provider_behaviour(brand, data.get("keywords"))
    fname = _save("provider_behaviour_guide", result)
    _persist_to_rds("provider_behaviour", {"brand": brand})
    result["saved_as"] = fname
    return result


def api_provider_behaviour(data):
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    if not brand:
        return {"error": "brand is required"}, 400
    keywords = data.get("keywords")
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",")]
    job_data = {"brand": brand, "keywords": keywords}
    job_id = _start_job("provider_behaviour", _run_provider_behaviour_job, (job_data,))
    return {"job_id": job_id, "status": "pending", "message": "Provider behaviour job started"}, 202


# ── Deliverable 4: Answer Format Taxonomy (sync — moderate) ───────────────────

def api_answer_taxonomy(data):
    from month1_research.answer_format_taxonomy import generate_answer_format_taxonomy
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    topic = (data.get("topic") or "").strip()
    pages = data.get("pages") or []
    if not brand or not topic:
        return {"error": "brand and topic are required"}, 400
    result = generate_answer_format_taxonomy(brand, topic, pages=pages or None)
    fname = _save("answer_format_taxonomy", result)
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 5: GEO Baseline (ASYNC — long running) ───────────────────────

def _run_geo_baseline_job(data):
    from month1_research.geo_baseline import generate_geo_baseline
    brand = data["brand"]
    result = generate_geo_baseline(brand, data["competitors"], keywords=data.get("keywords"))
    fname = _save("geo_baseline", result)
    _persist_to_rds("geo_baseline", {
        "brand": brand,
        "geo_score": result.get("primary_brand_results", {}).get("overall_geo_score", 0),
    })
    result["saved_as"] = fname
    return result


def api_geo_baseline(data):
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    competitors = data.get("competitors") or []
    if not brand:
        return {"error": "brand is required"}, 400
    if not competitors:
        return {"error": "competitors list is required"}, 400
    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.split(",")]
    job_data = {"brand": brand, "competitors": competitors, "keywords": data.get("keywords")}
    job_id = _start_job("geo_baseline", _run_geo_baseline_job, (job_data,))
    return {"job_id": job_id, "status": "pending", "message": "GEO baseline job started"}, 202


# ── Deliverable 6: Monitoring Activation (sync — fast) ────────────────────────

def api_monitoring_activate(data):
    from month1_research.monitoring_activator import activate_monitoring
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    keywords = data.get("keywords")
    if not brand:
        return {"error": "brand is required"}, 400
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",")]
    result = activate_monitoring(brand, keywords=keywords)
    fname = _save("monitoring_activation", result)
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 7: E-E-A-T Gap Register (sync — moderate) ────────────────────

def api_eeat_register(data):
    from month1_research.eeat_gap_register import generate_eeat_register
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    pages = data.get("pages") or []
    if not brand:
        return {"error": "brand is required"}, 400
    if not pages:
        return {"error": "pages list is required"}, 400
    result = generate_eeat_register(brand, pages)
    fname = _save("eeat_gap_register", result)
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 8: Technical Debt Register (sync — moderate) ──────────────────

def api_technical_debt(data):
    from month1_research.technical_debt_register import generate_technical_debt_register
    url = (data.get("url") or "").strip()
    if not url:
        return {"error": "url is required"}, 400
    result = generate_technical_debt_register(url)
    fname = _save("technical_debt_register", result)
    result["saved_as"] = fname
    return result, 200


# ── Run All (ASYNC — very long running) ───────────────────────────────────────

def _run_all_job(data):
    brand = data["brand"]
    url = data.get("url", "")
    topic = data["topic"]
    competitors = data.get("competitors", [])
    visibility_brands = data.get("visibility_brands", [])
    pages = data.get("pages", [])

    results = {}
    start = time.time()

    # Sync tasks run inline
    sync_tasks = [
        ("keyword_universe", lambda: api_keyword_universe({"brand": brand, "topic": topic})),
        ("answer_taxonomy", lambda: api_answer_taxonomy({"brand": brand, "topic": topic, "pages": pages})),
        ("monitoring", lambda: api_monitoring_activate({"brand": brand})),
    ]
    for name, fn in sync_tasks:
        try:
            result, status = fn()
            results[name] = {"status": "complete" if status == 200 else "failed", "data": result}
        except Exception as e:
            results[name] = {"status": "failed", "error": str(e)}

    # Long tasks run with individual error handling
    long_tasks = [
        ("benchmark", lambda: _run_benchmark_job({
            "brand": brand, "url": url, "competitors": competitors,
            "visibility_brands": visibility_brands})),
        ("provider_behaviour", lambda: _run_provider_behaviour_job({"brand": brand})),
        ("geo_baseline", lambda: _run_geo_baseline_job({
            "brand": brand, "competitors": competitors})),
    ]
    for name, fn in long_tasks:
        try:
            result = fn()
            results[name] = {"status": "complete", "data": result}
        except Exception as e:
            results[name] = {"status": "failed", "error": str(e)}

    # Optional tasks (may fail if no pages/url provided)
    if pages:
        try:
            result, status = api_eeat_register({"brand": brand, "pages": pages})
            results["eeat_register"] = {"status": "complete" if status == 200 else "failed", "data": result}
        except Exception as e:
            results["eeat_register"] = {"status": "failed", "error": str(e)}
    if url:
        try:
            result, status = api_technical_debt({"url": url})
            results["technical_debt"] = {"status": "complete" if status == 200 else "failed", "data": result}
        except Exception as e:
            results["technical_debt"] = {"status": "failed", "error": str(e)}

    elapsed = time.time() - start
    summary = {
        "month1_execution": "complete",
        "brand": brand,
        "elapsed_seconds": round(elapsed, 1),
        "deliverables": {k: v["status"] for k, v in results.items()},
        "completed": sum(1 for v in results.values() if v["status"] == "complete"),
        "failed": sum(1 for v in results.values() if v["status"] == "failed"),
        "results": results,
    }
    _save("month1_full_run", summary)
    return summary


def api_run_all(data):
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    topic = (data.get("topic") or "").strip()
    competitors = data.get("competitors") or []
    if not brand or not topic:
        return {"error": "brand and topic are required"}, 400
    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.split(",")]
    vis = data.get("visibility_brands") or []
    if isinstance(vis, str):
        vis = [v.strip() for v in vis.split(",")]
    job_data = {
        "brand": brand, "url": (data.get("url") or "").strip(),
        "topic": topic, "competitors": competitors,
        "visibility_brands": vis, "pages": data.get("pages") or [],
    }
    job_id = _start_job("run_all", _run_all_job, (job_data,))
    return {"job_id": job_id, "status": "pending", "message": "Month 1 full run started"}, 202


# ── Latest Results ────────────────────────────────────────────────────────────

def api_latest_results(deliverable=None):
    _ensure_output()
    files = sorted(os.listdir(OUTPUT_DIR), reverse=True)
    if deliverable:
        files = [f for f in files if f.startswith(deliverable)]
    if not files:
        return {"results": [], "message": "No results found"}, 200
    latest = files[0]
    path = os.path.join(OUTPUT_DIR, latest)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"filename": latest, "data": data}, 200
