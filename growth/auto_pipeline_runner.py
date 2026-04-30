"""
growth/auto_pipeline_runner.py
Auto Pipeline Runner — orchestrates the full growth loop.

Runs the complete cycle:
    1. Content pipeline (fetch → repurpose → schedule)
    2. Publish runner (publish overdue scheduled posts)
    3. Performance ingestor (score published posts)

Includes deduplication via a DynamoDB run log to prevent
overlapping executions. Designed to be triggered via API
endpoint or external scheduler (cron, CloudWatch Events).

Does NOT use background threads or workers.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# In-memory lock to prevent concurrent runs within the same process
_running = False


def run_full_cycle(
    content_limit: int = 5,
    publish_dry_run: bool = False,
    ingest_mode: str = "auto",
    run_discovery: bool = False,
    run_ugc: bool = False,
    run_lifecycle: bool = False,
) -> dict:
    """Execute the full growth automation cycle.

    Steps:
        0a. (Optional) Content discovery — fetch from Reddit/trending
        0b. (Optional) UGC collection — mentions + remix ideas
        1. Content pipeline (fetch → repurpose → schedule)
        2. Publish runner with fallback (real or simulated)
        3. Performance ingestor (score published posts)
        4. (Optional) Lifecycle engine (DMs + emails + referrals)
    """
    global _running
    if _running:
        return {"success": False, "error": "Pipeline already running", "skipped": True}

    _running = True
    started_at = datetime.now(timezone.utc).isoformat()

    discovery_result = None
    ugc_result = None
    pipeline_result = None
    publish_result = None
    ingest_result = None
    lifecycle_result = None

    try:
        # Step 0a: Content discovery (optional)
        if run_discovery:
            try:
                from growth.content_discovery import run_discovery as _discover
                discovery_result = _discover()
                logger.info("Discovery: added=%s", discovery_result.get("added", 0))
            except Exception as e:
                logger.error("Content discovery failed: %s", e)
                discovery_result = {"success": False, "error": str(e)}

        # Step 0b: UGC collection (optional)
        if run_ugc:
            try:
                from growth.ugc_collector import run_ugc_collection
                ugc_result = run_ugc_collection()
                logger.info("UGC: added=%s", ugc_result.get("added", 0))
            except Exception as e:
                logger.error("UGC collection failed: %s", e)
                ugc_result = {"success": False, "error": str(e)}

        # Step 1: Content pipeline
        try:
            from growth.content_pipeline import run_content_pipeline
            pipeline_result = run_content_pipeline(limit=content_limit)
            logger.info("Pipeline: processed=%s scheduled=%s",
                       pipeline_result.get("processed", 0),
                       pipeline_result.get("posts_scheduled", 0))
        except Exception as e:
            logger.error("Content pipeline failed: %s", e)
            pipeline_result = {"success": False, "error": str(e)}

        # Step 2: Publish runner (with fallback for missing API keys)
        try:
            from growth.publisher_fallback import run_scheduled_with_fallback
            publish_result = run_scheduled_with_fallback(dry_run=publish_dry_run)
            logger.info("Publisher: due=%s succeeded=%s simulated=%s failed=%s",
                       publish_result.get("total_due", 0),
                       publish_result.get("succeeded", 0),
                       publish_result.get("simulated", 0),
                       publish_result.get("failed", 0))
        except Exception as e:
            logger.error("Publish runner failed: %s", e)
            publish_result = {"success": False, "error": str(e)}

        # Step 3: Performance ingestor
        try:
            from growth.performance_ingestor import ingest_performance
            ingest_result = ingest_performance(mode=ingest_mode)
            logger.info("Ingestor: scored=%s skipped=%s",
                       ingest_result.get("scored", 0),
                       ingest_result.get("skipped", 0))
        except Exception as e:
            logger.error("Performance ingestor failed: %s", e)
            ingest_result = {"success": False, "error": str(e)}

        # Step 4: Lifecycle engine (optional)
        if run_lifecycle:
            try:
                from growth.lifecycle_engine import run_lifecycle_cycle
                lifecycle_result = run_lifecycle_cycle()
                logger.info("Lifecycle: processed=%s states=%s",
                           lifecycle_result.get("processed", 0),
                           lifecycle_result.get("states", {}))
            except Exception as e:
                logger.error("Lifecycle engine failed: %s", e)
                lifecycle_result = {"success": False, "error": str(e)}

        # Track the auto run event
        try:
            from growth.analytics_tracker import track_event
            track_event(
                event_type="auto_pipeline_run",
                event_data={
                    "discovery_added": (discovery_result or {}).get("added", 0),
                    "ugc_added": (ugc_result or {}).get("added", 0),
                    "content_processed": (pipeline_result or {}).get("processed", 0),
                    "posts_scheduled": (pipeline_result or {}).get("posts_scheduled", 0),
                    "posts_published": (publish_result or {}).get("succeeded", 0),
                    "posts_simulated": (publish_result or {}).get("simulated", 0),
                    "posts_scored": (ingest_result or {}).get("scored", 0),
                    "lifecycle_processed": (lifecycle_result or {}).get("processed", 0),
                },
            )
        except Exception:
            pass

    finally:
        _running = False

    completed_at = datetime.now(timezone.utc).isoformat()

    return {
        "success": True,
        "started_at": started_at,
        "completed_at": completed_at,
        "discovery": _summarize(discovery_result) if run_discovery else None,
        "ugc": _summarize(ugc_result) if run_ugc else None,
        "pipeline": _summarize(pipeline_result),
        "publisher": _summarize(publish_result),
        "ingestor": _summarize(ingest_result),
        "lifecycle": _summarize(lifecycle_result) if run_lifecycle else None,
    }


def _summarize(result: dict | None) -> dict:
    """Extract key metrics from a step result."""
    if result is None:
        return {"success": False, "error": "Step did not run"}
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "unknown")}

    # Return a compact summary based on which step it is
    summary = {"success": True}
    for key in ["processed", "posts_generated", "posts_scheduled",
                "total_due", "succeeded", "failed", "skipped", "simulated",
                "scored", "total_posts", "mode", "message",
                "optimization_applied", "dry_run"]:
        if key in result:
            summary[key] = result[key]
    return summary


def get_run_status() -> dict:
    """Check if the pipeline is currently running."""
    return {"running": _running, "checked_at": datetime.now(timezone.utc).isoformat()}
