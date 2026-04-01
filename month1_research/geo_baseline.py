"""
geo_baseline.py
Deliverable 5: Month 1 GEO Baseline

Produces a complete baseline visibility map:
  1. Full 200-keyword Batch GEO Probe for primary brand → geo_score per keyword
  2. Cross-Model Visibility Compare on top 50 keywords → visibility_score per keyword
  3. Same batch probe on 2 primary competitors → three-way comparison table
  4. Summary: your brand vs competitor A vs competitor B, by keyword and geo_score

Usage:
  python geo_baseline.py --brand "YourBrand" --competitors "CompA,CompB"
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from api_client import geo_probe_batch, geo_probe_compare, now_iso
from utils import save_json, load_latest, print_header, print_section


def run_full_batch_probe(brand: str, keywords: list, provider: str = "nova") -> dict:
    """Run batch GEO probe across all keywords (in chunks of 20)."""
    all_results = []
    total_cited = 0
    total_probed = 0

    chunks = [keywords[i:i+20] for i in range(0, len(keywords), 20)]

    for i, chunk in enumerate(chunks):
        print(f"  Batch {i+1}/{len(chunks)}: {len(chunk)} keywords on {provider}...")
        result = geo_probe_batch(brand, chunk, provider=provider)

        if "error" not in result:
            batch_results = result.get("results", [])
            all_results.extend(batch_results)
            total_cited += result.get("cited_count", 0)
            total_probed += result.get("total_prompts", 0)
        else:
            print(f"    ⚠ Error: {result.get('error', 'unknown')}")

        time.sleep(3)  # Rate limiting between batches

    overall_geo_score = total_cited / total_probed if total_probed > 0 else 0

    return {
        "brand": brand,
        "provider": provider,
        "total_keywords": len(keywords),
        "total_probed": total_probed,
        "total_cited": total_cited,
        "overall_geo_score": round(overall_geo_score, 4),
        "results": all_results,
    }


def run_cross_model_compare_top50(brand: str, keywords: list) -> list:
    """Run Cross-Model Visibility Compare on top 50 keywords."""
    results = []
    for kw in keywords[:50]:
        print(f"  Cross-model: '{kw}'...")
        result = geo_probe_compare(brand, kw)
        results.append({
            "keyword": kw,
            "visibility_score": result.get("visibility_score", 0),
            "provider_results": result.get("results", {}),
        })
        time.sleep(3)
    return results


def generate_geo_baseline(brand: str, competitors: list, keywords: list = None) -> dict:
    """Generate the complete Month 1 GEO Baseline."""
    print_header("DELIVERABLE 5: Month 1 GEO Baseline")

    # Load keyword universe if not provided
    if not keywords:
        ku = load_latest("keyword_universe")
        if ku:
            keywords = [k["query"] for k in ku["keywords"]]
            print(f"  Loaded {len(keywords)} keywords from Keyword Universe")
        else:
            print("  ERROR: No keywords provided and no keyword universe found.")
            print("  Run keyword_universe.py first.")
            return {}

    # ── Phase 1: Full batch probe for primary brand ───────────────────────
    print_section(f"Phase 1: Full Batch Probe — {brand}")
    primary_batch = run_full_batch_probe(brand, keywords)

    # ── Phase 2: Cross-Model Compare on top 50 ───────────────────────────
    # Select top 50 by priority (high commercial value first)
    ku = load_latest("keyword_universe")
    if ku:
        tier1_kws = [k["query"] for k in ku["keywords"] if k.get("priority_tier") == 1]
        tier2_kws = [k["query"] for k in ku["keywords"] if k.get("priority_tier") == 2]
        top50 = (tier1_kws + tier2_kws)[:50]
    else:
        top50 = keywords[:50]

    print_section(f"Phase 2: Cross-Model Visibility Compare — Top 50 Keywords")
    cross_model = run_cross_model_compare_top50(brand, top50)

    avg_visibility = sum(r["visibility_score"] for r in cross_model) / len(cross_model) if cross_model else 0

    # ── Phase 3: Competitor batch probes ──────────────────────────────────
    competitor_batches = {}
    for comp in competitors[:2]:
        print_section(f"Phase 3: Competitor Batch Probe — {comp}")
        competitor_batches[comp] = run_full_batch_probe(comp, keywords)

    # ── Phase 4: Three-way comparison table ───────────────────────────────
    print_section("Phase 4: Building Three-Way Comparison")

    comparison_table = []
    primary_results_map = {r.get("keyword", ""): r for r in primary_batch.get("results", [])}

    comp_results_maps = {}
    for comp, batch in competitor_batches.items():
        comp_results_maps[comp] = {r.get("keyword", ""): r for r in batch.get("results", [])}

    for kw in keywords:
        row = {
            "keyword": kw,
            brand: {
                "cited": primary_results_map.get(kw, {}).get("cited", False),
                "confidence": primary_results_map.get(kw, {}).get("confidence", 0),
            },
        }
        for comp in competitors[:2]:
            comp_map = comp_results_maps.get(comp, {})
            row[comp] = {
                "cited": comp_map.get(kw, {}).get("cited", False),
                "confidence": comp_map.get(kw, {}).get("confidence", 0),
            }
        comparison_table.append(row)

    # ── Build baseline report ─────────────────────────────────────────────
    baseline = {
        "deliverable": "Month 1 GEO Baseline",
        "generated_at": now_iso(),
        "primary_brand": brand,
        "competitors": competitors[:2],
        "total_keywords": len(keywords),
        "primary_brand_results": {
            "overall_geo_score": primary_batch["overall_geo_score"],
            "total_cited": primary_batch["total_cited"],
            "total_probed": primary_batch["total_probed"],
            "cross_model_avg_visibility": round(avg_visibility, 2),
        },
        "competitor_results": {
            comp: {
                "overall_geo_score": batch["overall_geo_score"],
                "total_cited": batch["total_cited"],
                "total_probed": batch["total_probed"],
            }
            for comp, batch in competitor_batches.items()
        },
        "comparison_summary": {
            brand: primary_batch["overall_geo_score"],
            **{comp: batch["overall_geo_score"] for comp, batch in competitor_batches.items()},
        },
        "gap_analysis": {
            "keywords_where_competitors_lead": [],
            "keywords_where_brand_leads": [],
            "keywords_where_nobody_cited": [],
        },
        "three_way_comparison": comparison_table,
        "cross_model_results": cross_model,
        "raw_primary_batch": primary_batch,
        "raw_competitor_batches": competitor_batches,
    }

    # Gap analysis
    for row in comparison_table:
        brand_cited = row[brand]["cited"]
        any_comp_cited = any(row.get(c, {}).get("cited", False) for c in competitors[:2])

        if not brand_cited and any_comp_cited:
            baseline["gap_analysis"]["keywords_where_competitors_lead"].append(row["keyword"])
        elif brand_cited and not any_comp_cited:
            baseline["gap_analysis"]["keywords_where_brand_leads"].append(row["keyword"])
        elif not brand_cited and not any_comp_cited:
            baseline["gap_analysis"]["keywords_where_nobody_cited"].append(row["keyword"])

    save_json("geo_baseline", baseline)

    # Print summary
    print(f"\n  === GEO BASELINE SUMMARY ===")
    print(f"  {brand}: geo_score = {primary_batch['overall_geo_score']:.2%}")
    for comp, batch in competitor_batches.items():
        print(f"  {comp}: geo_score = {batch['overall_geo_score']:.2%}")
    print(f"  Cross-model avg visibility: {avg_visibility:.1f}%")
    print(f"  Keywords where competitors lead: {len(baseline['gap_analysis']['keywords_where_competitors_lead'])}")
    print(f"  Keywords where brand leads: {len(baseline['gap_analysis']['keywords_where_brand_leads'])}")
    print(f"  Keywords unclaimed by anyone: {len(baseline['gap_analysis']['keywords_where_nobody_cited'])}")

    return baseline


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Month 1 GEO Baseline")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--competitors", required=True, help="Comma-separated competitor names")
    parser.add_argument("--keywords", default="", help="Comma-separated keywords (or loads from keyword_universe)")
    args = parser.parse_args()
    comps = [c.strip() for c in args.competitors.split(",")]
    kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
    generate_geo_baseline(args.brand, comps, kws)
