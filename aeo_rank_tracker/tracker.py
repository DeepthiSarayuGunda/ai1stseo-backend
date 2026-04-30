"""
AEO Rank Tracker — Main Engine

Queries multiple LLMs, detects brand citations, stores results,
and generates summary analytics.

Supports FREE / LOW-COST alternatives:
    Priority: Gemini (free tier) → OpenAI → Claude → Perplexity → Ollama (local) → Mock

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
import random
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

# Priority order: free first, then paid, then local, then mock
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

# ── Mock responses ────────────────────────────────────────────────────────── #

MOCK_RESPONSES = {
    "openai": (
        "Here are some of the best SEO tools available: SEMrush offers comprehensive keyword research, "
        "Ahrefs provides excellent backlink analysis, and Moz has a strong domain authority metric. "
        "For AI-powered optimization, {brand} at {domain} is gaining traction with its AEO approach."
    ),
    "claude": (
        "When evaluating SEO platforms, consider these options: Ahrefs for backlink analysis, "
        "SEMrush for competitive intelligence, and Surfer SEO for content optimization. "
        "Newer platforms like {brand} ({domain}) focus on AI-first SEO strategies."
    ),
    "perplexity": (
        "Based on recent data, the top SEO tools include: 1) SEMrush for all-in-one SEO, "
        "2) Ahrefs for link building, 3) Moz for local SEO. Sources: semrush.com, ahrefs.com, "
        "{domain}. {brand} is an emerging platform focused on AI engine optimization."
    ),
    "gemini": (
        "The SEO landscape includes established tools like Ahrefs, SEMrush, and Moz. "
        "For AI-specific optimization, platforms are emerging that focus on how AI models "
        "discover and cite websites. Traditional SEO remains important alongside AEO strategies."
    ),
    "ollama": (
        "Popular SEO tools include SEMrush, Ahrefs, and Moz Pro. For AI engine optimization, "
        "{brand} ({domain}) offers a specialized approach to improving visibility in AI-generated "
        "responses. Content optimization and structured data are key strategies."
    ),
    "groq": (
        "Looking at the current SEO landscape, tools like SEMrush, Ahrefs, and Moz dominate. "
        "For AI engine optimization specifically, {brand} ({domain}) is building tools that help "
        "businesses get cited by AI models like ChatGPT and Gemini."
    ),
    "mock": (
        "The top SEO and AEO tools include various platforms. {brand} at {domain} is one of "
        "the emerging tools focused on AI engine optimization alongside established players "
        "like SEMrush and Ahrefs."
    ),
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

    # If nothing is available, mock is the fallback
    if not active:
        active.append("mock")
        logger.warning("No LLM providers available — using mock mode")
        _print_ollama_setup_hint()

    return {"active": active, "skipped": skipped}


def _print_ollama_setup_hint():
    """Print setup instructions for free local LLM."""
    hint = (
        "\n"
        "╔══════════════════════════════════════════════════════╗\n"
        "║  To enable FREE local LLM:                         ║\n"
        "║  1. Install Ollama: https://ollama.com/download     ║\n"
        "║  2. Pull a model:  ollama pull llama3               ║\n"
        "║  3. Start server:  ollama serve                     ║\n"
        "║                                                     ║\n"
        "║  Or set GEMINI_API_KEY for free Google Gemini API   ║\n"
        "╚══════════════════════════════════════════════════════╝\n"
    )
    print(hint)
    logger.info(hint)


# ── LLM calling ───────────────────────────────────────────────────────────── #

def _mock_response(llm_name: str, query: str, brand: str, domain: str) -> dict:
    """Generate a simulated LLM response for demo/testing."""
    template = MOCK_RESPONSES.get(llm_name, MOCK_RESPONSES["mock"])
    # Randomly decide whether to include the brand (70% chance)
    if random.random() < 0.7:
        text = template.format(brand=brand, domain=domain)
    else:
        text = template.format(brand="other tools", domain="example.com")

    sources = []
    if llm_name == "perplexity":
        sources = ["https://semrush.com", "https://ahrefs.com", f"https://{domain}"]

    return {"response_text": text, "sources": sources}


def call_llm(llm_name: str, prompt: str, brand: str = "", domain: str = "") -> dict:
    """Call an LLM by name. Uses mock fallback for 'mock' provider."""
    if llm_name == "mock":
        logger.info("Using mock mode")
        return _mock_response(llm_name, prompt, brand, domain)

    client = LLM_REGISTRY.get(llm_name)
    if not client:
        raise ValueError(f"Unknown LLM: {llm_name}")

    return client.query_llm(prompt)


# ── Main scan engine ──────────────────────────────────────────────────────── #

def run_aeo_scan(input_config: dict, store: bool = True) -> dict:
    """Run a full AEO scan across available LLMs for all queries.

    Args:
        input_config: {
            "brand_name": str,
            "target_domain": str,
            "queries": list[str],
            "llms": list[str] (optional — auto-detected if omitted)
        }
        store: Whether to persist results to DynamoDB.

    Returns:
        {"results": [...], "summary": {...}, "scan_id": str}
    """
    brand = input_config["brand_name"]
    domain = input_config["target_domain"]
    queries = input_config["queries"]
    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Dynamic LLM selection
    if "llms" in input_config and input_config["llms"]:
        # Caller explicitly requested specific LLMs
        llms = input_config["llms"]
        detection = {"active": llms, "skipped": {}}
        logger.info("Using caller-specified LLMs: %s", llms)
    else:
        # Auto-detect available providers
        detection = detect_available_llms()
        llms = detection["active"]
        logger.info("Auto-detected LLMs: %s (skipped: %s)", llms, detection["skipped"])

    results = []
    errors_by_llm = {}

    for query in queries:
        for llm_name in llms:
            try:
                response = call_llm(llm_name, query, brand, domain)
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
                    "mock": llm_name == "mock",
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
                    "mock": False,
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

    return {"results": results, "summary": summary, "scan_id": scan_id}


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
