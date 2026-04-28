"""
scheduler.py
Background scheduler — runs scraper + GEO monitoring probes on a timer.
Starts as a daemon thread inside the Flask app so it runs continuously on App Runner.

Schedules:
  - Business directory scraper: every 24 hours
  - GEO brand monitoring probes: every 6 hours (for registered brands)

Monitored brands are persisted to DynamoDB so they survive restarts
and are shared across all gunicorn workers.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_scheduler_started = False
_lock = threading.Lock()

# DynamoDB table for persisting monitored brands
# Uses the existing geo-probes table with a special record type prefix
MONITOR_TABLE = 'ai1stseo-geo-probes'
MONITOR_PREFIX = 'MONITOR#'


def _get_dynamo_table():
    """Get the DynamoDB table for monitored brands."""
    try:
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        return dynamodb.Table(MONITOR_TABLE)
    except Exception as e:
        logger.warning("DynamoDB monitor table unavailable: %s", e)
        return None


def register_brand(brand_name: str, keywords: list, provider: str = "nova"):
    """Register a brand for continuous GEO monitoring. Persists to DynamoDB."""
    table = _get_dynamo_table()
    if table:
        try:
            table.put_item(Item={
                'id': MONITOR_PREFIX + brand_name,
                'keyword': '__monitor__',
                'brand_name': brand_name,
                'keywords': keywords,
                'provider': provider,
                'registered_at': datetime.now(timezone.utc).isoformat(),
                'active': True,
                'record_type': 'monitor',
            })
            logger.info("Registered brand for monitoring (DynamoDB): %s (%d keywords)",
                        brand_name, len(keywords))
            return
        except Exception as e:
            logger.warning("DynamoDB save failed, using in-memory: %s", e)

    # Fallback: in-memory only
    _monitored_brands_mem = _load_from_memory()
    for b in _monitored_brands_mem:
        if b["brand"] == brand_name:
            b["keywords"] = keywords
            b["provider"] = provider
            return
    _monitored_brands_mem.append({
        "brand": brand_name,
        "keywords": keywords,
        "provider": provider,
    })
    logger.info("Registered brand for monitoring (in-memory): %s (%d keywords)",
                brand_name, len(keywords))


# In-memory fallback
_monitored_brands_mem_store = []


def _load_from_memory():
    return _monitored_brands_mem_store


def get_monitored_brands():
    """Get all monitored brands — from DynamoDB first, fallback to in-memory."""
    table = _get_dynamo_table()
    if table:
        try:
            from boto3.dynamodb.conditions import Attr
            resp = table.scan(
                FilterExpression=Attr('record_type').eq('monitor') & Attr('active').eq(True),
                Limit=50,
            )
            items = resp.get('Items', [])
            brands = []
            for item in items:
                brands.append({
                    'brand': item.get('brand_name', ''),
                    'keywords': item.get('keywords', []),
                    'provider': item.get('provider', 'nova'),
                    'registered_at': item.get('registered_at', ''),
                })
            return brands
        except Exception as e:
            logger.warning("DynamoDB read failed, using in-memory: %s", e)
    return list(_monitored_brands_mem_store)


def unregister_brand(brand_name: str):
    """Remove a brand from continuous monitoring."""
    table = _get_dynamo_table()
    if table:
        try:
            table.update_item(
                Key={'id': MONITOR_PREFIX + brand_name},
                UpdateExpression='SET active = :val',
                ExpressionAttributeValues={':val': False},
            )
            logger.info("Unregistered brand: %s", brand_name)
            return True
        except Exception as e:
            logger.warning("DynamoDB unregister failed: %s", e)
    return False


def _run_scraper():
    """Run the business directory scraper."""
    try:
        from directory.database import DirectoryDatabase
        from directory.scraper import BusinessScraper
        db = DirectoryDatabase()
        scraper = BusinessScraper(db=db)
        result = scraper.scrape_all()
        logger.info("Scraper complete: found=%s added=%s errors=%s",
                     result.get("found", 0), result.get("added", 0),
                     len(result.get("errors", [])))
    except Exception as e:
        logger.error("Scheduled scraper failed: %s", e)


def _run_sports_sync():
    """Sync live sports data from TheSportsDB — today's events + major leagues."""
    try:
        from directory.sports_fetcher import sync_todays_events, sync_all_sports
        # Always sync today's events (quick, covers all sports)
        today_count = sync_todays_events()
        logger.info("Sports sync: %d events synced for today", today_count)
        # Full league sync (teams, matches, standings) — runs less frequently
        results = sync_all_sports()
        for sport, r in results.items():
            logger.info("Sports sync [%s]: matches=%d standings=%d teams=%d",
                        sport, r.get("matches", 0), r.get("standings", 0), r.get("teams", 0))
    except Exception as e:
        logger.error("Scheduled sports sync failed: %s", e)


def _run_geo_probes():
    """Run GEO probes for all registered brands, then transform to Month 3 tables."""
    brands = get_monitored_brands()
    if not brands:
        logger.info("No brands registered for monitoring, skipping GEO probes")
        return

    logger.info("Running GEO probes for %d registered brands", len(brands))
    try:
        from geo_probe_service import geo_probe_batch
        for entry in brands:
            try:
                brand = entry.get("brand", "")
                keywords = entry.get("keywords", [])
                provider = entry.get("provider", "nova")
                if not brand or not keywords:
                    continue
                result = geo_probe_batch(brand, keywords, ai_model=provider)
                score = result.get("geo_score", 0)
                cited = result.get("cited_count", 0)
                total = result.get("total_prompts", 0)
                logger.info("GEO probe [%s]: score=%.2f cited=%d/%d",
                            brand, score, cited, total)
            except Exception as e:
                logger.error("GEO probe failed for %s: %s", entry.get("brand"), e)
    except Exception as e:
        logger.error("Scheduled GEO probes failed: %s", e)

    # Transform raw probes → Month 3 intelligence tables
    try:
        from probe_to_intelligence import transform_probes_to_intelligence
        for entry in brands:
            brand = entry.get("brand", "")
            if brand:
                result = transform_probes_to_intelligence(brand)
                logger.info("Probe→Intelligence transform [%s]: %s", brand, result.get("status"))
    except Exception as e:
        logger.error("Probe→Intelligence transform failed: %s", e)


def _scheduler_loop():
    """Main scheduler loop — runs forever in a background thread."""
    SCRAPER_INTERVAL = 24 * 3600       # 24 hours
    GEO_PROBE_INTERVAL = 6 * 3600      # 6 hours
    SPORTS_SYNC_INTERVAL = 4 * 3600    # 4 hours — keeps scores fresh

    last_scrape = 0
    last_geo = 0
    last_sports = 0

    # Wait 60s after startup before first run to let the app fully initialize
    time.sleep(60)
    logger.info("Scheduler started — scraper every 24h, GEO probes every 6h, sports sync every 4h")

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

            if now - last_sports >= SPORTS_SYNC_INTERVAL:
                logger.info("Running scheduled sports sync...")
                _run_sports_sync()
                last_sports = now
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
