"""
eeat_gap_register.py
Deliverable 7: E-E-A-T Gap Register

Runs AI Ranking Recommendations across top pages of primary brand and competitors.
Documents every E-E-A-T signal gap, sorted by frequency and estimated impact,
with proposed remediation actions.

Usage:
  python eeat_gap_register.py --brand "YourBrand" \
    --pages "https://yourbrand.com/page1,https://yourbrand.com/page2"
"""

import argparse
import sys
import os
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from api_client import ai_ranking_recommendations, aeo_analyze, now_iso
from utils import save_json, load_latest, print_header, print_section

REMEDIATION_MAP = {
    "missing_author": {
        "impact": "high", "effort": "hours",
        "fix": "Add named expert author with credentials and bio.",
    },
    "no_date": {
        "impact": "medium", "effort": "hours",
        "fix": "Add publication date and last-updated date.",
    },
    "missing_schema": {
        "impact": "high", "effort": "hours",
        "fix": "Implement JSON-LD structured data.",
    },
    "low_brand_presence": {
        "impact": "high", "effort": "days",
        "fix": "Increase brand mentions in title, H1, H2, meta description.",
    },
    "missing_citations": {
        "impact": "medium", "effort": "hours",
        "fix": "Add data citations with dates and source links.",
    },
    "no_trust_signals": {
        "impact": "high", "effort": "days",
        "fix": "Add certifications, awards, testimonials, case studies.",
    },
    "thin_content": {
        "impact": "high", "effort": "days",
        "fix": "Expand to minimum 1500 words with subtopic coverage.",
    },
    "missing_faq_schema": {
        "impact": "medium", "effort": "hours",
        "fix": "Add FAQPage JSON-LD schema with 5+ Q&A pairs.",
    },
    "weak_meta_description": {
        "impact": "medium", "effort": "hours",
        "fix": "Write 150-160 char meta with brand name and keyword.",
    },
    "no_internal_links": {
        "impact": "medium", "effort": "hours",
        "fix": "Add 3-5 contextual internal links to related pages.",
    },
}



def audit_pages(pages, brand, keywords=None):
    """Run AI Ranking Recommendations on a list of pages."""
    results = []
    for url in pages[:20]:
        print(f"  Auditing: {url}...")
        result = ai_ranking_recommendations(url, brand, keywords=keywords)
        if "error" in result:
            print(f"    Warning: {result['error']}")
            results.append({"url": url, "error": result["error"]})
            continue
        aeo = aeo_analyze(url, brand=brand)
        results.append({
            "url": url,
            "recommendations": result.get("recommendations", []),
            "brand_presence": result.get("brand_presence", {}),
            "total_recommendations": result.get("total_recommendations", 0),
            "aeo_score": aeo.get("aeo_score", 0),
            "aeo_issues": aeo.get("issues", []),
        })
        time.sleep(2)
    return results


def build_gap_register(brand_results, competitor_results, brand):
    """Build the structured E-E-A-T Gap Register."""
    print_section("Building E-E-A-T Gap Register")
    all_gaps = []
    gap_counter = Counter()
    gap_id = 0
    impact_order = {"high": 0, "medium": 1, "low": 2}

    for page in brand_results:
        if "error" in page:
            continue
        url = page["url"]
        for rec in page.get("recommendations", []):
            gap_id += 1
            gap_type = rec.get("category", rec.get("type", "general"))
            gap_counter[gap_type] += 1
            rem = REMEDIATION_MAP.get(gap_type, {
                "impact": "medium", "effort": "days",
                "fix": rec.get("description", "Review and address."),
            })
            all_gaps.append({
                "gap_id": gap_id, "source": "brand", "url": url,
                "gap_type": gap_type, "title": rec.get("title", ""),
                "description": rec.get("description", ""),
                "priority": rec.get("priority", 99),
                "impact": rem["impact"], "effort": rem["effort"],
                "remediation": rem["fix"],
                "status": "open", "assigned_date": None, "resolved_date": None,
            })
        for issue in page.get("aeo_issues", []):
            gap_id += 1
            gap_type = issue.get("type", "aeo_issue")
            gap_counter[gap_type] += 1
            rem = REMEDIATION_MAP.get(gap_type, {
                "impact": issue.get("severity", "medium"), "effort": "hours",
                "fix": issue.get("fix", issue.get("message", "")),
            })
            all_gaps.append({
                "gap_id": gap_id, "source": "brand_aeo", "url": url,
                "gap_type": gap_type, "title": issue.get("message", ""),
                "description": issue.get("fix", ""),
                "priority": {"high": 1, "medium": 2, "low": 3}.get(
                    issue.get("severity", "medium"), 2),
                "impact": rem["impact"], "effort": rem["effort"],
                "remediation": rem["fix"],
                "status": "open", "assigned_date": None, "resolved_date": None,
            })

    comp_gap_counts = {}
    for comp_name, comp_pages in competitor_results.items():
        comp_gaps = Counter()
        for page in comp_pages:
            if "error" in page:
                continue
            for issue in page.get("aeo_issues", []):
                comp_gaps[issue.get("type", "unknown")] += 1
        comp_gap_counts[comp_name] = dict(comp_gaps)

    all_gaps.sort(key=lambda g: (g["priority"], impact_order.get(g["impact"], 1)))

    all_comp_gaps = Counter()
    for cg in comp_gap_counts.values():
        all_comp_gaps.update(cg)

    return {
        "total_gaps": len(all_gaps),
        "gap_frequency": dict(gap_counter.most_common()),
        "gaps": all_gaps,
        "competitor_common_gaps": dict(all_comp_gaps.most_common(10)),
        "highest_leverage_opportunities": [t for t, _ in all_comp_gaps.most_common(5)],
    }


def generate_eeat_register(brand, brand_pages, competitors=None, keywords=None):
    """Main entry point for E-E-A-T Gap Register generation."""
    print_header("DELIVERABLE 7: E-E-A-T Gap Register")
    if not keywords:
        ku = load_latest("keyword_universe")
        if ku:
            keywords = [k["query"] for k in ku["keywords"][:5]]

    print_section(f"Auditing {brand} Pages")
    brand_results = audit_pages(brand_pages, brand, keywords=keywords)

    competitor_results = {}
    if competitors:
        for comp_name, comp_pages in competitors.items():
            print_section(f"Auditing {comp_name} Pages")
            competitor_results[comp_name] = audit_pages(
                comp_pages, comp_name, keywords=keywords)

    register = build_gap_register(brand_results, competitor_results, brand)

    result = {
        "deliverable": "E-E-A-T Gap Register",
        "generated_at": now_iso(),
        "brand": brand,
        "pages_audited": {
            "brand": len(brand_results),
            "competitors": {k: len(v) for k, v in competitor_results.items()},
        },
        "register": register,
        "summary": {
            "total_gaps": register["total_gaps"],
            "high_impact": len([g for g in register["gaps"] if g["impact"] == "high"]),
            "medium_impact": len([g for g in register["gaps"] if g["impact"] == "medium"]),
            "low_impact": len([g for g in register["gaps"] if g["impact"] == "low"]),
            "most_common": list(register["gap_frequency"].keys())[:5],
            "highest_leverage": register["highest_leverage_opportunities"],
        },
        "brand_audit_raw": brand_results,
        "competitor_audit_raw": competitor_results,
    }

    save_json("eeat_gap_register", result)
    print(f"\n  Total gaps: {register['total_gaps']}")
    print(f"  High impact: {result['summary']['high_impact']}")
    print(f"  Most common: {result['summary']['most_common']}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate E-E-A-T Gap Register")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--pages", required=True, help="Comma-separated brand page URLs")
    parser.add_argument("--competitor-pages", default="",
                        help="Format: CompA=url1|url2,CompB=url3|url4")
    args = parser.parse_args()
    brand_pages = [p.strip() for p in args.pages.split(",")]
    competitors = {}
    if args.competitor_pages:
        for entry in args.competitor_pages.split(","):
            if "=" in entry:
                name, urls = entry.split("=", 1)
                competitors[name.strip()] = [u.strip() for u in urls.split("|")]
    generate_eeat_register(args.brand, brand_pages, competitors=competitors)
