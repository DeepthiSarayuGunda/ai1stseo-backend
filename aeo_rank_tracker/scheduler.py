"""
AEO Rank Tracker — Automated Scan Scheduler

Runs citation scans automatically every N hours for configured brands.
Runs as a background thread inside the Flask app.

Configuration via DynamoDB table or environment variables.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default scan interval: 6 hours (in seconds)
SCAN_INTERVAL = int(os.environ.get("AEO_SCAN_INTERVAL_HOURS", "6")) * 3600

# Default brands to track (can be overridden via API)
DEFAULT_TRACKED_BRANDS = [
    {"brand_name": "AI1stSEO", "target_domain": "ai1stseo.com"},
]

# Default queries for automated scans
DEFAULT_QUERIES = [
    "best SEO tools",
    "top AI marketing platforms",
    "best content optimization tools",
]

_scheduler_thread = None
_scheduler_running = False


def _run_scheduled_scan():
    """Execute a single round of scheduled scans for all tracked brands."""
    from aeo_rank_tracker.tracker import run_aeo_scan, detect_available_llms

    # Check if any LLM providers are available
    detection = detect_available_llms()
    if not detection["active"]:
        logger.warning("Scheduled scan skipped — no LLM providers available")
        return 0

    brands = _get_tracked_brands()
    if not brands:
        logger.info("Scheduled scan skipped — no brands configured")
        return 0

    total_scans = 0
    for brand_info in brands:
        try:
            logger.info(
                "Scheduled scan: %s (%s)",
                brand_info["brand_name"],
                brand_info["target_domain"],
            )
            result = run_aeo_scan(
                {
                    "brand_name": brand_info["brand_name"],
                    "target_domain": brand_info["target_domain"],
                    "queries": brand_info.get("queries", DEFAULT_QUERIES),
                },
                store=True,
            )
            cited = result.get("summary", {}).get("total_cited", 0)
            total = result.get("summary", {}).get("total_scanned", 0)
            logger.info(
                "Scheduled scan complete: %s — %d/%d cited",
                brand_info["brand_name"],
                cited,
                total,
            )
            total_scans += 1
        except Exception as e:
            logger.error(
                "Scheduled scan failed for %s: %s",
                brand_info["brand_name"],
                str(e)[:200],
            )

    return total_scans


def _get_tracked_brands():
    """Get the list of brands to scan automatically."""
    # Try to load from DynamoDB (brands that have been scanned before)
    try:
        from aeo_rank_tracker.utils.db import get_tracked_brands

        brands = get_tracked_brands(limit=10)
        if brands:
            return [
                {"brand_name": b["brand"], "target_domain": b["domain"]}
                for b in brands
                if b.get("brand") and b.get("domain")
            ]
    except Exception as e:
        logger.warning("Could not load tracked brands from DB: %s", e)

    return DEFAULT_TRACKED_BRANDS


def _scheduler_loop():
    """Background loop that runs scans at the configured interval."""
    global _scheduler_running
    logger.info(
        "AEO scheduler started — scanning every %d hours",
        SCAN_INTERVAL // 3600,
    )

    # Wait 60 seconds on startup before first scan (let the app fully initialize)
    time.sleep(60)

    while _scheduler_running:
        try:
            now = datetime.now(timezone.utc).isoformat()
            logger.info("Scheduled scan starting at %s", now)
            count = _run_scheduled_scan()
            logger.info("Scheduled scan complete — %d brands scanned", count)
        except Exception as e:
            logger.error("Scheduler error: %s", str(e)[:300])

        # Sleep for the interval, checking every 30s if we should stop
        elapsed = 0
        while elapsed < SCAN_INTERVAL and _scheduler_running:
            time.sleep(30)
            elapsed += 30


def start_scheduler():
    """Start the background scan scheduler."""
    global _scheduler_thread, _scheduler_running

    if _scheduler_running:
        logger.info("Scheduler already running")
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("AEO scan scheduler started (interval: %dh)", SCAN_INTERVAL // 3600)


def stop_scheduler():
    """Stop the background scan scheduler."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("AEO scan scheduler stopped")


def get_scheduler_status():
    """Return current scheduler status."""
    return {
        "running": _scheduler_running,
        "interval_hours": SCAN_INTERVAL // 3600,
        "tracked_brands": len(_get_tracked_brands()),
        "default_queries": DEFAULT_QUERIES,
    }
