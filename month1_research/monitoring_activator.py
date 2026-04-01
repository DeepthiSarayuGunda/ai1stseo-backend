"""
monitoring_activator.py
Deliverable 6: Scheduled Monitoring Jobs Activation

Activates visibility trend tracking and scheduled monitoring:
  1. Top 20 keywords on 10,080-minute intervals (weekly) via Nova Lite
  2. High-priority competitive keywords on 4,320-minute intervals (every 3 days)
  3. Activates Visibility Trend tool so trend data accumulates from Month 1

Usage:
  python monitoring_activator.py --brand "YourBrand"
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from api_client import geo_probe_schedule, geo_probe_trend, now_iso
from utils import save_json, load_latest, print_header, print_section


def activate_monitoring(brand: str, keywords: list = None) -> dict:
    """Activate all scheduled monitoring jobs for the primary brand."""
    print_header("DELIVERABLE 6: Scheduled Monitoring Jobs Activation")

    # Load keyword universe if not provided
    if not keywords:
        ku = load_latest("keyword_universe")
        if ku:
            all_kws = ku["keywords"]
            tier1 = [k["query"] for k in all_kws if k.get("priority_tier") == 1]
            tier2 = [k["query"] for k in all_kws if k.get("priority_tier") == 2]
            keywords = tier1 + tier2
            print(f"  Loaded {len(tier1)} Tier 1 + {len(tier2)} Tier 2 keywords")
        else:
            print("  ERROR: No keywords provided and no keyword universe found.")
            return {}

    # ── Schedule 1: Top 20 keywords — Weekly (10,080 min) via Nova Lite ───
    print_section("Schedule 1: Weekly Monitoring (Top 20 Keywords)")
    top20 = keywords[:20]
    weekly_job = geo_probe_schedule(
        brand=brand,
        keywords=top20,
        provider="nova",
        interval_minutes=10080,  # Weekly
    )
    print(f"  Scheduled {len(top20)} keywords for weekly monitoring")
    print(f"  Job: {weekly_job}")

    time.sleep(2)

    # ── Schedule 2: High-priority competitive — Every 3 days (4,320 min) ──
    print_section("Schedule 2: Competitive Monitoring (Every 3 Days)")
    competitive_kws = keywords[:10]  # Top 10 most competitive
    competitive_job = geo_probe_schedule(
        brand=brand,
        keywords=competitive_kws,
        provider="nova",
        interval_minutes=4320,  # Every 3 days
    )
    print(f"  Scheduled {len(competitive_kws)} keywords for 3-day monitoring")
    print(f"  Job: {competitive_job}")

    time.sleep(2)

    # ── Schedule 3: Ollama weekly supplement ──────────────────────────────
    print_section("Schedule 3: Ollama Weekly Supplement")
    ollama_job = geo_probe_schedule(
        brand=brand,
        keywords=top20,
        provider="ollama",
        interval_minutes=10080,  # Weekly
    )
    print(f"  Scheduled {len(top20)} keywords for weekly Ollama monitoring")
    print(f"  Job: {ollama_job}")

    # ── Activate Visibility Trend ─────────────────────────────────────────
    print_section("Activating Visibility Trend Tracking")
    trend = geo_probe_trend(brand)
    print(f"  Current trend data points: {len(trend.get('trend', []))}")
    print(f"  Trend tracking is now active — data will accumulate from today")

    # ── Build activation report ───────────────────────────────────────────
    report = {
        "deliverable": "Scheduled Monitoring Jobs Activation",
        "generated_at": now_iso(),
        "brand": brand,
        "schedules": {
            "weekly_nova": {
                "keywords": top20,
                "provider": "nova",
                "interval_minutes": 10080,
                "interval_human": "weekly",
                "job_response": weekly_job,
            },
            "competitive_nova": {
                "keywords": competitive_kws,
                "provider": "nova",
                "interval_minutes": 4320,
                "interval_human": "every 3 days",
                "job_response": competitive_job,
            },
            "weekly_ollama": {
                "keywords": top20,
                "provider": "ollama",
                "interval_minutes": 10080,
                "interval_human": "weekly",
                "job_response": ollama_job,
            },
        },
        "visibility_trend_status": {
            "activated": True,
            "current_data_points": len(trend.get("trend", [])),
            "note": "By Month 3 you will have 8+ weeks of trend data",
        },
        "monitoring_summary": {
            "total_keywords_monitored": len(set(top20 + competitive_kws)),
            "providers_active": ["nova", "ollama"],
            "schedules_active": 3,
        },
    }

    save_json("monitoring_activation", report)

    print(f"\n  === MONITORING ACTIVATED ===")
    print(f"  Total keywords monitored: {report['monitoring_summary']['total_keywords_monitored']}")
    print(f"  Schedules active: 3 (weekly Nova, 3-day competitive, weekly Ollama)")
    print(f"  Trend tracking: active")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Activate Scheduled Monitoring")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--keywords", default="", help="Comma-separated keywords (or loads from keyword_universe)")
    args = parser.parse_args()
    kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
    activate_monitoring(args.brand, kws)
