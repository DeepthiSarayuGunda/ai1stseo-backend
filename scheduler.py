"""
scheduler.py
Background scheduler — runs scraper + GEO monitoring probes on a timer.
Starts as a daemon thread inside the Flask app so it runs continuously on App Runner.

Schedules:
  - Business directory scraper: every 24 hours
  - GEO brand monitoring probes: every 6 hours (for registered brands)
"""

import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_scheduler_started = False
_lock = threading.Lock()

# In-memory registry of brands to monitor (populated via API or on startup)
_monitored_brands = []


def register_brand(brand_name: str, keywords: list, provider: str = "nova"):
    """Register a brand for continuous GEO monitoring."""
    for b in _monitored_brands:
        if b["brand"] == brand_name:
            b["keywords"] = keywords
            b["provider"] = provider
            return
    _monitored_brands.append({
        "brand": brand_name,
        "keywords": keywords,
        "provider": provider,
    })
    logger.info("Registered brand for monitoring: %s (%d keywords)", brand_name, len(keywords))


def get_monitored_brands():
    return list(_monitored_brands)


def _run_scraper():
    """Run the business directory scraper."""
    try:
        from directory.database import DirectoryDatabase
        from directory.scraper import BusinessScraper
        db = DirectoryDatabase()
        scraper = BusinessScraper(db=db)
        result = scraper.scrape_all()
        logger.info("Scraper complete: found=%s added=%s errors=%s",
                     result["found"], result["added"], len(result["errors"]))
    except Exception as e:
        logger.error("Scheduled scraper failed: %s", e)


def _run_geo_probes():
    """Run GEO probes for all registered brands."""
    if not _monitored_brands:
        logger.info("No brands registered for monitoring, skipping GEO probes")
        return
    try:
        from geo_probe_service import geo_probe_batch
        for entry in _monitored_brands:
            try:
                result = geo_probe_batch(
                    entry["brand"], entry["keywords"], ai_model=entry["provider"]
                )
                score = result.get("geo_score", 0)
                cited = result.get("cited_count", 0)
                total = result.get("total_prompts", 0)
                logger.info("GEO probe [%s]: score=%.2f cited=%d/%d",
                            entry["brand"], score, cited, total)
            except Exception as e:
                logger.error("GEO probe failed for %s: %s", entry["brand"], e)
    except Exception as e:
        logger.error("Scheduled GEO probes failed: %s", e)


def _scheduler_loop():
    """Main scheduler loop — runs forever in a background thread."""
    SCRAPER_INTERVAL = 24 * 3600   # 24 hours
    GEO_PROBE_INTERVAL = 6 * 3600  # 6 hours

    last_scrape = 0
    last_geo = 0

    # Wait 60s after startup before first run to let the app fully initialize
    time.sleep(60)
    logger.info("Scheduler started — scraper every 24h, GEO probes every 6h")

    while True:
        now = time.time()
        try:
            if now - last_scrape >= SCRAPER_INTERVAL:
                logger.info("Running scheduled scraper...")
                _run_scraper()
                last_scrape = now

            if now - last_geo >= GEO_PROBE_INTERVAL:
                logger.info("Running scheduled GEO probes...")
                _run_geo_probes()
                last_geo = now
        except Exception as e:
            logger.error("Scheduler loop error: %s", e)

        # Sleep 5 minutes between checks
        time.sleep(300)


def start_scheduler():
    """Start the background scheduler thread (idempotent)."""
    global _scheduler_started
    with _lock:
        if _scheduler_started:
            return
        _scheduler_started = True
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="bg-scheduler")
    t.start()
    logger.info("Background scheduler thread started")
