"""
AEO Rank Tracker — Main Engine

Queries multiple LLMs, detects brand citations, stores results,
and generates summary analytics. Returns ONLY real AI data.

Priority: Gemini → Groq → OpenAI → Claude → Perplexity → Ollama

Usage:
    from aeo_rank_tracker.tracker import run_aeo_scan
    results = run_aeo_scan({
        "brand_name": "YourBrand",
        "target_domain": "yourdomain.com",
        "queries": ["best SEO tools", "top AI marketing platforms"]
    })
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from aeo_rank_tracker.llm_clients import (
    openai_client,
    anthropic_client,
    perplexity_client,
    gemini_client,
    ollama_client,
    groq_client,
)
from aeo_rank_tracker.utils.citation_detector import detect_citation
from aeo_rank_tracker.utils.db import save_results

logger = logging.getLogger(__name__)

# ── LLM registry ─────────────────────────────────────────────────────────── #

LLM_REGISTRY = {
    "gemini": gemini_client,
    "groq": groq_client,
    "openai": openai_client,
    "claude": anthropic_client,
    "perplexity": perplexity_client,
    "ollama": ollama_client,
}

# Priority order: free first, then paid, then local
LLM_PRIORITY = ["gemini", "groq", "openai", "claude", "perplexity", "ollama"]

# Env var required for each provider (empty string = no key needed)
LLM_KEY_MAP = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "ollama": "",  # no key needed
}


# ── Provider detection ────────────────────────────────────────────────────── #

def detect_available_llms() -> dict:
    """Detect which LLM providers are available.

    Returns:
        {
            "active": ["gemini", ...],
            "skipped": {"openai": "OPENAI_API_KEY not set", ...},
        }
    """
    active = []
    skipped = {}

    for llm_name in LLM_PRIORITY:
        env_var = LLM_KEY_MAP.get(llm_name, "")

        if llm_name == "ollama":
            # Ollama: check if server is running (no key needed)
            if ollama_client.is_available():
                models = ollama_client.get_models()
                active.append(llm_name)
                logger.info("✓ %s available (models: %s)", llm_name, ", ".join(models[:3]))
            else:
                skipped[llm_name] = "Ollama not running"
                logger.info("✗ %s skipped — not running at %s", llm_name, ollama_client.OLLAMA_URL)
        elif env_var and os.environ.get(env_var, ""):
            active.append(llm_name)
            logger.info("✓ %s available (key: %s)", llm_name, env_var)
        else:
            skipped[llm_name] = f"{env_var} not set"
            logger.info("✗ %s skipped — %s not set", llm_name, env_var)

    # No mock fallback — require at least one real provider
    if not active:
        logger.error("No LLM providers available — scan will fail")

    return {"active": active, "skipped": skipped}


# ── LLM calling ───────────────────────────────────────────────────────────── #

def call_llm(llm_name: str, prompt: str) -> dict:
    """Call a real LLM by name. No mock fallback."""
    client = LLM_REGISTRY.get(llm_name)
    if not client:
        raise ValueError(f"Unknown LLM: {llm_name}")
    return client.query_llm(prompt)


# ── Main scan engine ──────────────────────────────────────────────────────── #

def run_aeo_scan(input_config: dict, store: bool = True) -> dict:
    """Run a full AEO scan across available LLMs for all queries.
    Returns ONLY real AI data. Raises error if no providers available.

    Args:
        input_config: {
            "brand_name": str,
            "target_domain": str,
            "queries": list[str],
            "llms": list[str] (optional — auto-detected if omitted)
        }
        store: Whether to persist results to DynamoDB.

    Returns:
        {"results": [...], "summary": {...}, "scan_id": str, "data_source": "real"}
    """
    brand = input_config["brand_name"]
    domain = input_config["target_domain"]
    queries = input_config["queries"]
    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Dynamic LLM selection
    if "llms" in input_config and input_config["llms"]:
        llms = input_config["llms"]
        detection = {"active": llms, "skipped": {}}
        logger.info("Using caller-specified LLMs: %s", llms)
    else:
        detection = detect_available_llms()
        llms = detection["active"]
        logger.info("Auto-detected LLMs: %s (skipped: %s)", llms, detection["skipped"])

    # Require at least one real provider
    if not llms:
        raise RuntimeError(
            "No active LLM provider. Configure at least one API key "
            "(GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or PERPLEXITY_API_KEY)."
        )

    logger.info("AEO scan running with: %s", llms)

    results = []
    errors_by_llm = {}

    for query in queries:
        for llm_name in llms:
            try:
                response = call_llm(llm_name, query)
                response_text = response.get("response_text", "")
                sources = response.get("sources", [])

                citation = detect_citation(response_text, brand, domain)

                # Also check sources list (Perplexity returns URLs)
                if not citation["found"] and sources:
                    domain_clean = domain.lower().replace("www.", "")
                    for src in sources:
                        if domain_clean in str(src).lower():
                            citation["found"] = True
                            citation["match_type"] = "source_citation"
                            citation["matches"].append(f"source:{src}")
                            break

                results.append({
                    "query": query,
                    "llm": llm_name,
                    "citation_found": citation["found"],
                    "match_type": citation.get("match_type"),
                    "matches": citation.get("matches", []),
                    "response_snippet": response_text[:300],
                    "sources": sources[:5],
                    "brand_name": brand,
                    "target_domain": domain,
                    "timestamp": now,
                    "scan_id": scan_id,
                    "data_source": "real",
                })

            except Exception as e:
                logger.error("Error querying %s for '%s': %s", llm_name, query, e)
                errors_by_llm.setdefault(llm_name, []).append(str(e)[:100])
                results.append({
                    "query": query,
                    "llm": llm_name,
                    "citation_found": False,
                    "response_snippet": "",
                    "error": str(e)[:200],
                    "brand_name": brand,
                    "target_domain": domain,
                    "timestamp": now,
                    "scan_id": scan_id,
                    "data_source": "error",
                })

    # Store results
    if store:
        try:
            save_results(results)
        except Exception as e:
            logger.warning("Failed to store results: %s", e)

    summary = generate_summary(results)
    summary["scan_id"] = scan_id
    summary["brand_name"] = brand
    summary["target_domain"] = domain
    summary["active_llms"] = llms
    summary["skipped_llms"] = detection["skipped"]
    summary["errors_by_llm"] = errors_by_llm
    summary["timestamp"] = now
    summary["data_source"] = "real"

    return {"results": results, "summary": summary, "scan_id": scan_id, "data_source": "real"}


# ── Summary generation ────────────────────────────────────────────────────── #

def generate_summary(results: list[dict]) -> dict:
    """Generate analytics summary from scan results.

    Returns:
        {
            "visibility_score": float,
            "best_llm": str,
            "top_query": str,
            "llm_performance": {llm: {total, cited, rate}},
            "query_performance": {query: {total, cited, rate}},
            "total_scanned": int,
            "total_cited": int,
        }
    """
    if not results:
        return {
            "visibility_score": 0,
            "best_llm": None,
            "top_query": None,
            "llm_performance": {},
            "query_performance": {},
            "total_scanned": 0,
            "total_cited": 0,
        }

    # Group by LLM
    llm_stats = {}
    for r in results:
        llm = r.get("llm", "unknown")
        if llm not in llm_stats:
            llm_stats[llm] = {"total": 0, "cited": 0}
        llm_stats[llm]["total"] += 1
        if r.get("citation_found"):
            llm_stats[llm]["cited"] += 1

    for llm, stats in llm_stats.items():
        stats["rate"] = round((stats["cited"] / stats["total"]) * 100, 1) if stats["total"] else 0

    # Group by query
    query_stats = {}
    for r in results:
        q = r.get("query", "unknown")
        if q not in query_stats:
            query_stats[q] = {"total": 0, "cited": 0}
        query_stats[q]["total"] += 1
        if r.get("citation_found"):
            query_stats[q]["cited"] += 1

    for q, stats in query_stats.items():
        stats["rate"] = round((stats["cited"] / stats["total"]) * 100, 1) if stats["total"] else 0

    total = len(results)
    cited = sum(1 for r in results if r.get("citation_found"))
    visibility_score = round((cited / total) * 100, 1) if total else 0

    best_llm = max(llm_stats, key=lambda k: llm_stats[k]["rate"]) if llm_stats else None
    top_query = max(query_stats, key=lambda k: query_stats[k]["rate"]) if query_stats else None

    return {
        "visibility_score": visibility_score,
        "best_llm": best_llm,
        "top_query": top_query,
        "llm_performance": llm_stats,
        "query_performance": query_stats,
        "total_scanned": total,
        "total_cited": cited,
    }
