"""
month1_api.py
Month 1 Research API — Flask routes for all 8 deliverables.
Registered in app.py under /api/month1/* prefix.

All outputs are returned as JSON AND saved to month1_research/output/.
Long-running tasks run synchronously (no Celery needed on Lambda/App Runner).
"""

import json
import logging
import os
import time
import traceback
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "month1_research", "output")


def _ensure_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _save(name, data):
    """Save result to output dir and return the filename."""
    _ensure_output()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"{name}_{ts}.json"
    path = os.path.join(OUTPUT_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return fname


def _persist_to_rds(table_name, data):
    """Best-effort persist summary to RDS ai_visibility_history."""
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


# ── Deliverable 1: Keyword Universe ──────────────────────────────────────────

def api_keyword_universe(data):
    """Generate 200 categorised natural-language queries."""
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


# ── Deliverable 2: Benchmark Runner ──────────────────────────────────────────

def api_benchmark(data):
    """Run benchmark research across brands."""
    from month1_research.benchmark_runner import run_benchmark
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    url = (data.get("url") or "").strip()
    competitors = data.get("competitors") or []
    visibility_brands = data.get("visibility_brands") or []
    keywords = data.get("keywords") or None

    if not brand:
        return {"error": "brand is required"}, 400
    if not competitors:
        return {"error": "competitors list is required"}, 400

    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.split(",")]
    if isinstance(visibility_brands, str):
        visibility_brands = [v.strip() for v in visibility_brands.split(",")]

    result = run_benchmark(brand, url, competitors, visibility_brands, keywords=keywords)
    fname = _save("benchmark_report", result)
    _persist_to_rds("benchmark_report", {"brand": brand})
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 3: Provider Behaviour ─────────────────────────────────────────

def api_provider_behaviour(data):
    """Analyze provider behaviour across all AI engines."""
    from month1_research.provider_behaviour import analyze_provider_behaviour
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    keywords = data.get("keywords") or None

    if not brand:
        return {"error": "brand is required"}, 400

    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",")]

    result = analyze_provider_behaviour(brand, keywords)
    fname = _save("provider_behaviour_guide", result)
    _persist_to_rds("provider_behaviour", {"brand": brand})
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 4: Answer Format Taxonomy ─────────────────────────────────────

def api_answer_taxonomy(data):
    """Build answer format taxonomy from empirical data."""
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


# ── Deliverable 5: GEO Baseline ──────────────────────────────────────────────

def api_geo_baseline(data):
    """Generate Month 1 GEO baseline vs competitors."""
    from month1_research.geo_baseline import generate_geo_baseline
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    competitors = data.get("competitors") or []
    keywords = data.get("keywords") or None

    if not brand:
        return {"error": "brand is required"}, 400
    if not competitors:
        return {"error": "competitors list is required"}, 400

    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.split(",")]

    result = generate_geo_baseline(brand, competitors, keywords=keywords)
    fname = _save("geo_baseline", result)
    _persist_to_rds("geo_baseline", {
        "brand": brand,
        "geo_score": result.get("primary_brand_results", {}).get("overall_geo_score", 0),
    })
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 6: Monitoring Activation ──────────────────────────────────────

def api_monitoring_activate(data):
    """Activate scheduled monitoring jobs."""
    from month1_research.monitoring_activator import activate_monitoring
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    keywords = data.get("keywords") or None

    if not brand:
        return {"error": "brand is required"}, 400

    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",")]

    result = activate_monitoring(brand, keywords=keywords)
    fname = _save("monitoring_activation", result)
    result["saved_as"] = fname
    return result, 200


# ── Deliverable 7: E-E-A-T Gap Register ──────────────────────────────────────

def api_eeat_register(data):
    """Build E-E-A-T gap register from page audits."""
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


# ── Deliverable 8: Technical Debt Register ────────────────────────────────────

def api_technical_debt(data):
    """Run 236-check audit and build technical debt register."""
    from month1_research.technical_debt_register import generate_technical_debt_register
    url = (data.get("url") or "").strip()

    if not url:
        return {"error": "url is required"}, 400

    result = generate_technical_debt_register(url)
    fname = _save("technical_debt_register", result)
    result["saved_as"] = fname
    return result, 200


# ── Run All ───────────────────────────────────────────────────────────────────

def api_run_all(data):
    """Run all 8 Month 1 deliverables."""
    brand = (data.get("brand") or data.get("brand_name") or "").strip()
    url = (data.get("url") or "").strip()
    topic = (data.get("topic") or "").strip()
    competitors = data.get("competitors") or []
    visibility_brands = data.get("visibility_brands") or []
    pages = data.get("pages") or []

    if not brand or not topic:
        return {"error": "brand and topic are required"}, 400

    if isinstance(competitors, str):
        competitors = [c.strip() for c in competitors.split(",")]
    if isinstance(visibility_brands, str):
        visibility_brands = [v.strip() for v in visibility_brands.split(",")]

    results = {}
    start = time.time()

    tasks = [
        ("keyword_universe", lambda: api_keyword_universe({"brand": brand, "topic": topic})),
        ("benchmark", lambda: api_benchmark({
            "brand": brand, "url": url, "competitors": competitors,
            "visibility_brands": visibility_brands})),
        ("provider_behaviour", lambda: api_provider_behaviour({"brand": brand})),
        ("answer_taxonomy", lambda: api_answer_taxonomy({
            "brand": brand, "topic": topic, "pages": pages})),
        ("geo_baseline", lambda: api_geo_baseline({
            "brand": brand, "competitors": competitors})),
        ("monitoring", lambda: api_monitoring_activate({"brand": brand})),
        ("eeat_register", lambda: api_eeat_register({
            "brand": brand, "pages": pages})),
        ("technical_debt", lambda: api_technical_debt({"url": url})),
    ]

    for name, fn in tasks:
        try:
            result, status = fn()
            results[name] = {"status": "complete" if status == 200 else "failed", "data": result}
        except Exception as e:
            logger.error("Month1 %s failed: %s", name, traceback.format_exc())
            results[name] = {"status": "failed", "error": str(e)}

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
    return summary, 200


# ── Latest Results ────────────────────────────────────────────────────────────

def api_latest_results(deliverable=None):
    """Return the latest output file(s)."""
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
