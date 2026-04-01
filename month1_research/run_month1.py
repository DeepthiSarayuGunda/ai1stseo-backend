"""
run_month1.py
Master Orchestrator — Runs All Month 1 Research Tasks

Executes all 8 deliverables in the correct order:
  1. Master Keyword Universe (200 queries)
  2. Benchmark Brand Research Report (5 brands)
  3. Provider Behaviour Guide (all providers)
  4. Answer Format Taxonomy (8 formats)
  5. Month 1 GEO Baseline (brand vs competitors)
  6. Scheduled Monitoring Activation
  7. E-E-A-T Gap Register
  8. Technical Debt Register

Usage:
  python run_month1.py \
    --brand "YourBrand" \
    --url "https://yourbrand.com" \
    --topic "your industry" \
    --competitors "CompA,CompB" \
    --visibility-brands "VisA,VisB" \
    --brand-pages "https://yourbrand.com/p1,https://yourbrand.com/p2"

Environment:
  API_BASE_URL=http://localhost:5000  (or your deployed backend URL)
"""

import argparse
import sys
import os
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from utils import save_json, print_header, ensure_output_dir


def run_all(brand, url, topic, competitors, visibility_brands, brand_pages):
    """Execute all Month 1 deliverables in sequence."""
    print_header("MONTH 1 — RESEARCH & PLATFORM MASTERY")
    print(f"  Brand: {brand}")
    print(f"  URL: {url}")
    print(f"  Topic: {topic}")
    print(f"  Competitors: {competitors}")
    print(f"  Visibility brands: {visibility_brands}")
    print(f"  Brand pages: {len(brand_pages)} pages")
    print()

    ensure_output_dir()
    results = {}
    start = time.time()

    # ── Deliverable 1: Master Keyword Universe ────────────────────────────
    try:
        print("\n[1/8] Generating Master Keyword Universe...")
        from keyword_universe import generate_keyword_universe
        results["keyword_universe"] = generate_keyword_universe(brand, topic)
        print("  ✓ Keyword Universe complete")
    except Exception as e:
        print(f"  ✗ Keyword Universe failed: {e}")
        results["keyword_universe"] = {"error": str(e)}

    # ── Deliverable 2: Benchmark Brand Research ───────────────────────────
    try:
        print("\n[2/8] Running Benchmark Brand Research...")
        from benchmark_runner import run_benchmark
        results["benchmark"] = run_benchmark(
            brand, url, competitors, visibility_brands)
        print("  ✓ Benchmark Research complete")
    except Exception as e:
        print(f"  ✗ Benchmark Research failed: {e}")
        results["benchmark"] = {"error": str(e)}

    # ── Deliverable 3: Provider Behaviour Guide ───────────────────────────
    try:
        print("\n[3/8] Analyzing Provider Behaviour...")
        from provider_behaviour import analyze_provider_behaviour
        results["provider_behaviour"] = analyze_provider_behaviour(brand, None)
        print("  ✓ Provider Behaviour Guide complete")
    except Exception as e:
        print(f"  ✗ Provider Behaviour failed: {e}")
        results["provider_behaviour"] = {"error": str(e)}

    # ── Deliverable 4: Answer Format Taxonomy ─────────────────────────────
    try:
        print("\n[4/8] Building Answer Format Taxonomy...")
        from answer_format_taxonomy import generate_answer_format_taxonomy
        results["answer_taxonomy"] = generate_answer_format_taxonomy(
            brand, topic, pages=brand_pages)
        print("  ✓ Answer Format Taxonomy complete")
    except Exception as e:
        print(f"  ✗ Answer Format Taxonomy failed: {e}")
        results["answer_taxonomy"] = {"error": str(e)}

    # ── Deliverable 5: GEO Baseline ───────────────────────────────────────
    try:
        print("\n[5/8] Generating GEO Baseline...")
        from geo_baseline import generate_geo_baseline
        results["geo_baseline"] = generate_geo_baseline(brand, competitors)
        print("  ✓ GEO Baseline complete")
    except Exception as e:
        print(f"  ✗ GEO Baseline failed: {e}")
        results["geo_baseline"] = {"error": str(e)}

    # ── Deliverable 6: Monitoring Activation ──────────────────────────────
    try:
        print("\n[6/8] Activating Scheduled Monitoring...")
        from monitoring_activator import activate_monitoring
        results["monitoring"] = activate_monitoring(brand)
        print("  ✓ Monitoring Activation complete")
    except Exception as e:
        print(f"  ✗ Monitoring Activation failed: {e}")
        results["monitoring"] = {"error": str(e)}

    # ── Deliverable 7: E-E-A-T Gap Register ───────────────────────────────
    try:
        print("\n[7/8] Building E-E-A-T Gap Register...")
        from eeat_gap_register import generate_eeat_register
        results["eeat_register"] = generate_eeat_register(
            brand, brand_pages)
        print("  ✓ E-E-A-T Gap Register complete")
    except Exception as e:
        print(f"  ✗ E-E-A-T Gap Register failed: {e}")
        results["eeat_register"] = {"error": str(e)}

    # ── Deliverable 8: Technical Debt Register ────────────────────────────
    try:
        print("\n[8/8] Building Technical Debt Register...")
        from technical_debt_register import generate_technical_debt_register
        results["technical_debt"] = generate_technical_debt_register(url)
        print("  ✓ Technical Debt Register complete")
    except Exception as e:
        print(f"  ✗ Technical Debt Register failed: {e}")
        results["technical_debt"] = {"error": str(e)}

    # ── Summary ───────────────────────────────────────────────────────────
    elapsed = time.time() - start
    summary = {
        "month1_execution": "complete",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brand": brand,
        "elapsed_seconds": round(elapsed, 1),
        "deliverables": {},
    }

    for name, data in results.items():
        if "error" in data:
            summary["deliverables"][name] = {"status": "failed", "error": data["error"]}
        else:
            summary["deliverables"][name] = {"status": "complete"}

    completed = sum(1 for d in summary["deliverables"].values() if d["status"] == "complete")
    failed = sum(1 for d in summary["deliverables"].values() if d["status"] == "failed")

    save_json("month1_summary", summary)

    print_header("MONTH 1 EXECUTION COMPLETE")
    print(f"  Completed: {completed}/8 deliverables")
    print(f"  Failed: {failed}/8 deliverables")
    print(f"  Elapsed: {elapsed:.0f} seconds")
    print(f"\n  All outputs saved to: month1_research/output/")
    print()

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Month 1 Master Orchestrator — Run All Research Tasks")
    parser.add_argument("--brand", required=True, help="Primary brand name")
    parser.add_argument("--url", required=True, help="Primary brand URL")
    parser.add_argument("--topic", required=True, help="Core topic/industry")
    parser.add_argument("--competitors", required=True,
                        help="Comma-separated competitor names")
    parser.add_argument("--visibility-brands", required=True,
                        help="Comma-separated high-visibility brand names")
    parser.add_argument("--brand-pages", default="",
                        help="Comma-separated brand page URLs for AEO/E-E-A-T audit")
    args = parser.parse_args()

    comps = [c.strip() for c in args.competitors.split(",")]
    vis = [v.strip() for v in args.visibility_brands.split(",")]
    pages = [p.strip() for p in args.brand_pages.split(",") if p.strip()]

    run_all(args.brand, args.url, args.topic, comps, vis, pages)
