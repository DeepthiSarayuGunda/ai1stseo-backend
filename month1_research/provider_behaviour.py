"""
provider_behaviour.py
Deliverable 3: Provider Behaviour Guide

Empirically analyses how each AI provider (Nova Lite, Ollama, Claude, Groq,
OpenAI, Gemini, Perplexity) behaves differently when probed with identical keywords.

Measures:
  - Citation frequency per provider
  - Content format preferences (lists, paragraphs, tables)
  - Confidence score distribution
  - Brand mention consistency
  - Provider agreement/disagreement patterns

Usage:
  python provider_behaviour.py --brand "YourBrand" --keywords "kw1,kw2,kw3,..."
"""

import argparse
import sys
import os
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from api_client import (
    geo_probe_single, geo_probe_compare, llm_citation_probe,
    model_comparison, now_iso
)
from utils import save_json, load_latest, print_header, print_section

PROVIDERS = ["nova", "ollama", "groq", "claude", "openai", "gemini", "perplexity"]
CORE_PROVIDERS = ["nova", "ollama"]  # Direct providers (always available)


def analyze_provider_behaviour(brand: str, keywords: list) -> dict:
    """Run identical keyword sets across all providers and analyze differences."""
    print_header("DELIVERABLE 3: Provider Behaviour Guide")

    if not keywords:
        ku = load_latest("keyword_universe")
        if ku:
            keywords = [k["query"] for k in ku["keywords"][:20]]
        else:
            print("  ERROR: No keywords provided and no keyword universe found.")
            return {}

    keywords = keywords[:20]  # Cap at 20 for manageable research
    print(f"  Analyzing {len(keywords)} keywords across providers...")

    # ── Phase 1: Cross-Model Compare (all providers at once) ──────────────
    print_section("Phase 1: Cross-Model Visibility Compare")
    compare_results = []
    for kw in keywords:
        print(f"  Comparing: '{kw}'...")
        result = geo_probe_compare(brand, kw)
        compare_results.append({"keyword": kw, **result})
        time.sleep(3)

    # ── Phase 2: Individual probes on core providers ──────────────────────
    print_section("Phase 2: Core Provider Deep Probes (Nova vs Ollama)")
    core_results = {"nova": [], "ollama": []}
    for kw in keywords:
        for provider in CORE_PROVIDERS:
            print(f"  Probing: '{kw}' on {provider}...")
            result = geo_probe_single(brand, kw, provider=provider)
            core_results[provider].append({"keyword": kw, **result})
            time.sleep(2)

    # ── Phase 3: LLM Citation Probes (external providers) ─────────────────
    print_section("Phase 3: External Provider Citation Probes")
    external_providers = ["claude", "groq", "openai", "gemini", "perplexity"]
    external_results = {p: [] for p in external_providers}
    for kw in keywords[:10]:  # Limit external to 10 keywords (API cost)
        for provider in external_providers:
            print(f"  Citation probe: '{kw}' on {provider}...")
            result = llm_citation_probe(kw, provider=provider)
            external_results[provider].append({"keyword": kw, **result})
            time.sleep(2)

    # ── Phase 4: Model Comparison (disagreement detection) ────────────────
    print_section("Phase 4: Model Disagreement Analysis")
    disagreement_results = []
    for kw in keywords[:10]:
        print(f"  Model comparison: '{kw}'...")
        result = model_comparison(brand, kw)
        disagreement_results.append({"keyword": kw, **result})
        time.sleep(3)

    # ── Analysis ──────────────────────────────────────────────────────────
    print_section("Analyzing Provider Behaviour Patterns")

    provider_stats = {}
    for provider in PROVIDERS:
        stats = {
            "citation_count": 0,
            "total_probes": 0,
            "citation_rate": 0,
            "avg_confidence": 0,
            "confidence_scores": [],
            "cited_keywords": [],
            "missed_keywords": [],
        }

        # Aggregate from cross-model compare
        for cr in compare_results:
            results = cr.get("results", {})
            if provider in results:
                stats["total_probes"] += 1
                pr = results[provider]
                if pr.get("cited") or pr.get("brand_present"):
                    stats["citation_count"] += 1
                    stats["cited_keywords"].append(cr["keyword"])
                else:
                    stats["missed_keywords"].append(cr["keyword"])
                conf = pr.get("confidence", 0)
                stats["confidence_scores"].append(conf)

        if stats["total_probes"] > 0:
            stats["citation_rate"] = stats["citation_count"] / stats["total_probes"]
            stats["avg_confidence"] = sum(stats["confidence_scores"]) / len(stats["confidence_scores"]) if stats["confidence_scores"] else 0

        provider_stats[provider] = stats

    # Nova vs Ollama agreement analysis
    agreement_count = 0
    disagreement_count = 0
    nova_only = []
    ollama_only = []

    for kw in keywords:
        nova_cited = kw in [r["keyword"] for r in core_results["nova"] if r.get("cited") or r.get("brand_present")]
        ollama_cited = kw in [r["keyword"] for r in core_results["ollama"] if r.get("cited") or r.get("brand_present")]

        if nova_cited == ollama_cited:
            agreement_count += 1
        else:
            disagreement_count += 1
            if nova_cited and not ollama_cited:
                nova_only.append(kw)
            elif ollama_cited and not nova_cited:
                ollama_only.append(kw)

    # Build the guide
    guide = {
        "deliverable": "Provider Behaviour Guide",
        "generated_at": now_iso(),
        "brand": brand,
        "keywords_tested": len(keywords),
        "provider_profiles": {},
        "nova_vs_ollama": {
            "agreement_rate": agreement_count / len(keywords) if keywords else 0,
            "disagreement_rate": disagreement_count / len(keywords) if keywords else 0,
            "nova_only_citations": nova_only,
            "ollama_only_citations": ollama_only,
            "interpretation": (
                "High agreement = strong model consensus (reliable signal). "
                "High disagreement = noisy results (need more content reinforcement)."
            ),
        },
        "cross_model_compare_raw": compare_results,
        "core_provider_raw": core_results,
        "external_provider_raw": external_results,
        "disagreement_analysis_raw": disagreement_results,
    }

    # Build provider profiles
    for provider, stats in provider_stats.items():
        profile = {
            "citation_rate": round(stats["citation_rate"], 3),
            "avg_confidence": round(stats["avg_confidence"], 3),
            "total_probes": stats["total_probes"],
            "citations": stats["citation_count"],
            "top_cited_keywords": stats["cited_keywords"][:5],
            "top_missed_keywords": stats["missed_keywords"][:5],
        }

        # Classify provider behaviour
        if stats["citation_rate"] > 0.6:
            profile["behaviour"] = "high_citation"
            profile["recommendation"] = "Primary monitoring target — responsive to content changes"
        elif stats["citation_rate"] > 0.3:
            profile["behaviour"] = "moderate_citation"
            profile["recommendation"] = "Secondary monitoring — may respond to authority signals"
        else:
            profile["behaviour"] = "low_citation"
            profile["recommendation"] = "Experimental target — use for testing content variations"

        guide["provider_profiles"][provider] = profile

    # Rank providers by citation rate
    guide["provider_ranking"] = sorted(
        [{"provider": p, "citation_rate": s["citation_rate"]} for p, s in provider_stats.items()],
        key=lambda x: x["citation_rate"], reverse=True
    )

    save_json("provider_behaviour_guide", guide)

    print(f"\n  Provider ranking by citation rate:")
    for r in guide["provider_ranking"]:
        print(f"    {r['provider']}: {r['citation_rate']:.1%}")
    print(f"  Nova vs Ollama agreement: {guide['nova_vs_ollama']['agreement_rate']:.1%}")

    return guide


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Provider Behaviour Guide")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--keywords", default="", help="Comma-separated keywords (or loads from keyword_universe)")
    args = parser.parse_args()
    kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
    analyze_provider_behaviour(args.brand, kws)
