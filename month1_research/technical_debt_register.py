"""
technical_debt_register.py
Deliverable 8: Technical Debt Register

Runs the AI1stSEO 236-check full audit on the primary domain.
Categorises all findings by:
  - Severity: critical / high / medium / low
  - Effort to fix: hours / days / weeks
  - AI crawlability impact: whether the issue affects AI citation probability

Usage:
  python technical_debt_register.py --url "https://yourbrand.com"
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from api_client import full_seo_audit, now_iso
from utils import save_json, print_header, print_section

# Categories from the 236-check audit
AUDIT_CATEGORIES = [
    "technical", "onpage", "content", "mobile",
    "performance", "security", "social", "local",
    "geo_aeo", "citation_gap",
]

# AI crawlability impact classification
AI_IMPACT_KEYWORDS = {
    "high": [
        "schema", "structured data", "json-ld", "faq", "howto",
        "meta description", "title tag", "h1", "canonical",
        "robots", "noindex", "crawl", "sitemap", "indexing",
        "ai", "aeo", "geo", "citation", "snippet",
    ],
    "medium": [
        "heading", "alt text", "internal link", "anchor",
        "content length", "readability", "keyword", "duplicate",
        "redirect", "broken link", "404", "ssl", "https",
    ],
    "low": [
        "social", "og:", "twitter:", "favicon", "viewport",
        "font", "image size", "lazy load", "minif",
    ],
}


def _classify_ai_impact(check_name, check_desc):
    """Classify whether a check affects AI crawlability and citation."""
    text = f"{check_name} {check_desc}".lower()
    for keyword in AI_IMPACT_KEYWORDS["high"]:
        if keyword in text:
            return "high"
    for keyword in AI_IMPACT_KEYWORDS["medium"]:
        if keyword in text:
            return "medium"
    return "low"


def _estimate_effort(check_status, category):
    """Estimate fix effort based on check type."""
    if category in ("technical", "security"):
        return "days"
    if category in ("content", "geo_aeo", "citation_gap"):
        return "days"
    return "hours"


def _map_severity(status, category):
    """Map check status to severity level."""
    if status == "fail":
        if category in ("technical", "security", "geo_aeo"):
            return "critical"
        return "high"
    elif status == "warning":
        return "medium"
    return "low"


def generate_technical_debt_register(url):
    """Run full 236-check audit and build the Technical Debt Register."""
    print_header("DELIVERABLE 8: Technical Debt Register")

    print_section(f"Running 236-Check Full Audit: {url}")
    audit = full_seo_audit(url)

    if "error" in audit:
        print(f"  ERROR: {audit['error']}")
        return {"error": audit["error"]}

    # Extract all checks from audit results
    all_checks = []
    categories_data = audit.get("categories", {})
    overall_score = audit.get("overall_score", 0)

    # The audit returns checks grouped by category
    checks_list = audit.get("checks", [])
    if not checks_list and categories_data:
        # Try extracting from categories
        for cat_name, cat_data in categories_data.items():
            cat_checks = cat_data if isinstance(cat_data, list) else cat_data.get("checks", [])
            for check in cat_checks:
                check["_category"] = cat_name
                checks_list.append(check)

    print(f"  Total checks found: {len(checks_list)}")

    # Build the register
    debt_items = []
    debt_id = 0
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    category_counts = {}
    ai_impact_counts = {"high": 0, "medium": 0, "low": 0}

    for check in checks_list:
        status = check.get("status", "").lower()
        if status in ("pass", "passed", "ok", "good"):
            continue  # Only register failures and warnings

        debt_id += 1
        name = check.get("name", check.get("check", f"Check #{debt_id}"))
        desc = check.get("description", check.get("desc", ""))
        recommendation = check.get("recommendation", check.get("rec", ""))
        category = check.get("_category", check.get("category", "general"))
        impact = check.get("impact", "")

        severity = _map_severity(status, category)
        effort = _estimate_effort(status, category)
        ai_impact = _classify_ai_impact(name, desc)

        severity_counts[severity] += 1
        category_counts[category] = category_counts.get(category, 0) + 1
        ai_impact_counts[ai_impact] += 1

        debt_items.append({
            "debt_id": debt_id,
            "check_name": name,
            "description": desc,
            "recommendation": recommendation,
            "category": category,
            "status": status,
            "severity": severity,
            "effort": effort,
            "ai_crawlability_impact": ai_impact,
            "fix_status": "open",
            "assigned_date": None,
            "resolved_date": None,
        })

    # Sort: critical first, then high AI impact
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ai_order = {"high": 0, "medium": 1, "low": 2}
    debt_items.sort(key=lambda d: (
        severity_order.get(d["severity"], 3),
        ai_order.get(d["ai_crawlability_impact"], 2),
    ))

    result = {
        "deliverable": "Technical Debt Register",
        "generated_at": now_iso(),
        "url": url,
        "overall_seo_score": overall_score,
        "total_checks_run": len(checks_list),
        "total_issues": len(debt_items),
        "severity_breakdown": severity_counts,
        "category_breakdown": category_counts,
        "ai_impact_breakdown": ai_impact_counts,
        "priority_actions": {
            "critical_ai_high": [
                d for d in debt_items
                if d["severity"] == "critical" and d["ai_crawlability_impact"] == "high"
            ],
            "high_ai_high": [
                d for d in debt_items
                if d["severity"] == "high" and d["ai_crawlability_impact"] == "high"
            ],
        },
        "register": debt_items,
        "raw_audit": audit,
    }

    save_json("technical_debt_register", result)

    print(f"\n  === TECHNICAL DEBT REGISTER ===")
    print(f"  Overall SEO Score: {overall_score}")
    print(f"  Total issues: {len(debt_items)}")
    print(f"  Critical: {severity_counts['critical']}")
    print(f"  High: {severity_counts['high']}")
    print(f"  Medium: {severity_counts['medium']}")
    print(f"  Low: {severity_counts['low']}")
    print(f"  High AI impact issues: {ai_impact_counts['high']}")
    crit_ai = len(result['priority_actions']['critical_ai_high'])
    print(f"  Critical + High AI impact (fix first): {crit_ai}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Technical Debt Register")
    parser.add_argument("--url", required=True, help="Primary domain URL to audit")
    args = parser.parse_args()
    generate_technical_debt_register(args.url)
