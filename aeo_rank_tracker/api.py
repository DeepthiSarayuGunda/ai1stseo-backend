"""
AEO Rank Tracker — Flask API Blueprint

Endpoints:
    POST /api/aeo-tracker/run     — trigger a scan
    GET  /api/aeo-tracker/history — stored results
    GET  /api/aeo-tracker/summary — aggregated analytics
"""

import logging

from flask import Blueprint, jsonify, request

from aeo_rank_tracker.tracker import run_aeo_scan, generate_summary, detect_available_llms
from aeo_rank_tracker.utils.db import get_history, get_velocity_data, get_tracked_brands

logger = logging.getLogger(__name__)

aeo_tracker_bp = Blueprint("aeo_tracker", __name__)


@aeo_tracker_bp.route("/api/aeo-tracker/run", methods=["POST"])
def run_scan():
    """Trigger an AEO rank scan.

    Body JSON:
        {
            "brand_name": "YourBrand",
            "target_domain": "yourdomain.com",
            "queries": ["best SEO tools", ...],
            "llms": ["openai", "claude", "perplexity", "gemini"]  (optional)
        }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    brand = data.get("brand_name")
    domain = data.get("target_domain")
    queries = data.get("queries")

    if not brand or not domain or not queries:
        return jsonify({
            "error": "brand_name, target_domain, and queries are required"
        }), 400

    if not isinstance(queries, list) or len(queries) == 0:
        return jsonify({"error": "queries must be a non-empty list"}), 400

    if len(queries) > 20:
        return jsonify({"error": "Maximum 20 queries per scan"}), 400

    try:
        result = run_aeo_scan(data)
        return jsonify({
            "status": "ok",
            "scan_id": result["scan_id"],
            "results": result["results"],
            "summary": result["summary"],
            "active_llms": result["summary"].get("active_llms", []),
        })
    except Exception as e:
        logger.exception("AEO scan failed")
        return jsonify({"error": str(e), "status": "error"}), 500


@aeo_tracker_bp.route("/api/aeo-tracker/history", methods=["GET"])
def scan_history():
    """Get stored scan results.

    Query params: query, llm, brand, limit (default 50)
    """
    try:
        rows = get_history(
            query=request.args.get("query"),
            llm=request.args.get("llm"),
            brand=request.args.get("brand"),
            limit=int(request.args.get("limit", 50)),
        )
        return jsonify({"status": "ok", "count": len(rows), "results": rows})
    except Exception as e:
        logger.warning("Failed to fetch history: %s", e)
        return jsonify({
            "status": "ok",
            "count": 0,
            "results": [],
            "db_error": str(e)[:200],
        })


@aeo_tracker_bp.route("/api/aeo-tracker/summary", methods=["GET"])
def scan_summary():
    """Get aggregated summary from stored results.

    Query params: brand, limit (default 100)

    Returns:
        - citation rate per LLM
        - best performing queries
        - overall visibility score
    """
    try:
        brand = request.args.get("brand")
        limit = int(request.args.get("limit", 100))
        rows = get_history(brand=brand, limit=limit)

        if not rows:
            return jsonify({
                "status": "ok",
                "summary": {
                    "visibility_score": 0,
                    "best_llm": None,
                    "top_query": None,
                    "llm_performance": {},
                    "query_performance": {},
                    "total_scanned": 0,
                    "total_cited": 0,
                },
                "message": "No scan data found. Run a scan first.",
            })

        summary = generate_summary(rows)
        return jsonify({"status": "ok", "summary": summary})
    except Exception as e:
        logger.warning("Failed to generate summary: %s", e)
        return jsonify({
            "status": "ok",
            "summary": {
                "visibility_score": 0,
                "best_llm": None,
                "top_query": None,
                "llm_performance": {},
                "query_performance": {},
                "total_scanned": 0,
                "total_cited": 0,
            },
            "message": "No scan data available.",
            "db_error": str(e)[:200],
        })


@aeo_tracker_bp.route("/api/aeo-tracker/providers", methods=["GET"])
def provider_status():
    """Get status of all LLM providers.

    Returns which providers are active, skipped, and why.
    """
    try:
        detection = detect_available_llms()
        return jsonify({
            "status": "ok",
            "active": detection["active"],
            "skipped": detection["skipped"],
            "priority_order": ["gemini", "openai", "claude", "perplexity", "ollama", "mock"],
        })
    except Exception as e:
        logger.exception("Failed to detect providers")
        return jsonify({"error": str(e), "status": "error"}), 500


# ── Citation Velocity Tracker endpoints ───────────────────────────────────── #

@aeo_tracker_bp.route("/api/aeo-tracker/velocity", methods=["GET"])
def citation_velocity():
    """Get citation velocity data for a brand over time.

    Query params: brand (required), limit (default 500)

    Returns daily citation rates, per-LLM trends, per-query trends, and totals.
    """
    brand = request.args.get("brand")
    if not brand:
        return jsonify({"error": "brand parameter is required"}), 400

    try:
        limit = int(request.args.get("limit", 500))
        data = get_velocity_data(brand=brand, limit=limit)
        return jsonify({"status": "ok", "brand": brand, **data})
    except Exception as e:
        logger.warning("Failed to get velocity data: %s", e)
        return jsonify({
            "status": "ok",
            "brand": brand,
            "daily": [],
            "by_llm": {},
            "by_query": {},
            "totals": {"total": 0, "cited": 0, "rate": 0, "scans": 0},
            "db_error": str(e)[:200],
        })


@aeo_tracker_bp.route("/api/aeo-tracker/brands", methods=["GET"])
def tracked_brands():
    """Get all brands that have been scanned with their stats."""
    try:
        brands = get_tracked_brands(limit=int(request.args.get("limit", 50)))
        return jsonify({"status": "ok", "count": len(brands), "brands": brands})
    except Exception as e:
        logger.warning("Failed to get brands: %s", e)
        return jsonify({"status": "ok", "count": 0, "brands": [], "db_error": str(e)[:200]})
