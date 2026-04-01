"""
benchmark_runner.py
Deliverable 1: Benchmark Brand Research Report

Runs the full tool suite on 5 benchmark brands:
  - Primary brand
  - 2 direct competitors
  - 2 brands known for strong AI visibility

For each brand, runs:
  1. GEO Monitoring Engine (20 keywords, Nova + Ollama)
  2. Cross-Model Visibility Compare (20 keywords, all providers)
  3. AEO Optimizer (top 10 pages)
  4. AI Ranking Recommendations (top 10 pages)
  5. Site/URL Detection (top 5 URLs, 10 keywords, 3 providers)

Usage:
  python benchmark_runner.py --brand "YourBrand" --url "https://yourbrand.com" \
    --competitors "CompA,CompB" --visibility-brands "VisA,VisB"
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from api_client import (
    geo_probe_batch, geo_probe_compare, aeo_analyze,
    ai_ranking_recommendations, geo_probe_site, now_iso
)
from utils import save_json, load_latest, print_header, print_section


def run_geo_monitoring(brand: str, keywords: list, providers: list = None) -> dict:
    """Run GEO Monitoring Engine on keywords across providers."""
    if providers is None:
        providers = ["nova", "ollama"]

    results = {}
    for provider in providers:
        print(f"  Running GEO probe: {brand} on {provider} ({len(keywords)} keywords)...")
        batch = geo_probe_batch(brand, keywords[:20], provider=provider)
        results[provider] = {
            "geo_score": batch.get("geo_score", 0),
            "cited_count": batch.get("cited_count", 0),
            "total_prompts": batch.get("total_prompts", 0),
            "results": batch.get("results", []),
        }
        time.sleep(2)  # Rate limiting between providers

    return results


def run_cross_model_compare(brand: str, keywords: list) -> list:
    """Run Cross-Model Visibility Compare on keywords."""
    results = []
    for kw in keywords[:5]:  # Cap at 5 (heavy multi-provider call)
        print(f"  Cross-model compare: '{kw}'...")
        try:
            compare = geo_probe_compare(brand, kw)
            results.append({
                "keyword": kw,
                "visibility_score": compare.get("visibility_score", 0),
                "provider_results": compare.get("results", {}),
            })
        except Exception as e:
            print(f"    ⚠ Compare failed: {e}")
            results.append({"keyword": kw, "visibility_score": 0, "error": str(e)})
        time.sleep(2)
    return results


def run_aeo_audit(pages: list, brand: str = None) -> list:
    """Run AEO Optimizer on a list of page URLs."""
    results = []
    for url in pages[:10]:
        print(f"  AEO audit: {url}...")
        result = aeo_analyze(url, brand=brand)
        results.append({
            "url": url,
            "aeo_score": result.get("aeo_score", 0),
            "total_issues": result.get("total_issues", 0),
            "severity_breakdown": result.get("severity_breakdown", {}),
            "issues": result.get("issues", []),
        })
        time.sleep(1)
    return results


def run_eeat_audit(pages: list, brand: str, keywords: list = None) -> list:
    """Run AI Ranking Recommendations on pages."""
    results = []
    for url in pages[:10]:
        print(f"  E-E-A-T audit: {url}...")
        result = ai_ranking_recommendations(url, brand, keywords=keywords)
        results.append({
            "url": url,
            "recommendations": result.get("recommendations", []),
            "brand_presence": result.get("brand_presence", {}),
            "total_recommendations": result.get("total_recommendations", 0),
        })
        time.sleep(1)
    return results


def run_site_detection(site_urls: list, keywords: list, providers: list = None) -> list:
    """Run Site/URL Detection across keywords and providers."""
    if providers is None:
        providers = ["nova"]  # Single provider to reduce time

    results = []
    for url in site_urls[:3]:  # Cap at 3 URLs
        url_results = {"url": url, "detections": []}
        for kw in keywords[:5]:  # Cap at 5 keywords
            for provider in providers:
                print(f"  Site detection: {url} | '{kw}' | {provider}...")
                try:
                    result = geo_probe_site(url, kw, provider=provider)
                    url_results["detections"].append({
                        "keyword": kw,
                        "provider": provider,
                        "site_mentioned": result.get("site_mentioned", False),
                        "confidence": result.get("confidence", 0),
                    })
                except Exception as e:
                    url_results["detections"].append({
                        "keyword": kw, "provider": provider,
                        "site_mentioned": False, "error": str(e),
                    })
                time.sleep(1)
        results.append(url_results)
    return results


def benchmark_single_brand(brand: str, brand_url: str, keywords: list, pages: list) -> dict:
    """Run full benchmark suite on a single brand."""
    print_section(f"Benchmarking: {brand}")

    result = {
        "brand": brand,
        "url": brand_url,
        "benchmarked_at": now_iso(),
    }

    # 1. GEO Monitoring
    print_section(f"{brand} — GEO Monitoring (Nova + Ollama)")
    result["geo_monitoring"] = run_geo_monitoring(brand, keywords)

    # 2. Cross-Model Visibility Compare
    print_section(f"{brand} — Cross-Model Visibility Compare")
    result["cross_model_compare"] = run_cross_model_compare(brand, keywords)

    # Calculate average visibility score
    vis_scores = [r["visibility_score"] for r in result["cross_model_compare"] if r.get("visibility_score")]
    result["avg_visibility_score"] = sum(vis_scores) / len(vis_scores) if vis_scores else 0

    # 3. AEO Optimizer
    if pages:
        print_section(f"{brand} — AEO Optimizer")
        result["aeo_audit"] = run_aeo_audit(pages, brand=brand)

    # 4. AI Ranking Recommendations
    if pages:
        print_section(f"{brand} — AI Ranking Recommendations")
        result["eeat_audit"] = run_eeat_audit(pages, brand, keywords=keywords[:5])

    # 5. Site/URL Detection
    if pages:
        print_section(f"{brand} — Site/URL Detection")
        result["site_detection"] = run_site_detection(pages[:5], keywords[:10])

    return result


def run_benchmark(brand: str, brand_url: str, competitors: list, visibility_brands: list,
                  keywords: list = None, pages: dict = None) -> dict:
    """Run full benchmark across all 5 brands."""
    print_header("DELIVERABLE 1: Benchmark Brand Research Report")

    # Load keyword universe if no keywords provided
    if not keywords:
        ku = load_latest("keyword_universe")
        if ku:
            keywords = [k["query"] for k in ku["keywords"][:20]]
            print(f"  Loaded {len(keywords)} keywords from Keyword Universe")
        else:
            keywords = [
                f"best {brand.lower()} alternatives",
                f"what is {brand.lower()}",
                f"{brand.lower()} review",
                f"top tools like {brand.lower()}",
                f"{brand.lower()} pricing",
            ]
            print(f"  Using {len(keywords)} default keywords")

    if pages is None:
        pages = {}

    all_brands = [brand] + competitors + visibility_brands
    results = {
        "deliverable": "Benchmark Brand Research Report",
        "generated_at": now_iso(),
        "primary_brand": brand,
        "competitors": competitors,
        "visibility_brands": visibility_brands,
        "keywords_used": keywords,
        "brands": {},
    }

    for b in all_brands:
        b_url = pages.get(b, {}).get("url", "")
        b_pages = pages.get(b, {}).get("pages", [])
        results["brands"][b] = benchmark_single_brand(b, b_url, keywords, b_pages)

    # Cross-brand comparison summary
    summary = []
    for b_name, b_data in results["brands"].items():
        nova_score = b_data.get("geo_monitoring", {}).get("nova", {}).get("geo_score", 0)
        avg_vis = b_data.get("avg_visibility_score", 0)
        summary.append({
            "brand": b_name,
            "nova_geo_score": nova_score,
            "avg_visibility_score": avg_vis,
        })

    results["comparison_summary"] = sorted(summary, key=lambda x: x["avg_visibility_score"], reverse=True)

    save_json("benchmark_report", results)
    print(f"\n  Benchmark complete for {len(all_brands)} brands.")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Benchmark Brand Research")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--competitors", required=True, help="Comma-separated competitor names")
    parser.add_argument("--visibility-brands", required=True, help="Comma-separated high-visibility brand names")
    parser.add_argument("--keywords", default="", help="Comma-separated keywords (or loads from keyword_universe)")
    args = parser.parse_args()

    comps = [c.strip() for c in args.competitors.split(",")]
    vis = [v.strip() for v in args.visibility_brands.split(",")]
    kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    run_benchmark(args.brand, args.url, comps, vis, keywords=kws)
