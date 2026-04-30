"""
growth/content_pipeline.py
Content Pipeline Runner — automated content production loop.

Fetches unprocessed content from the content source manager,
repurposes it into platform-specific posts, schedules them via
DynamoDB, and tracks analytics. Designed to run on-demand via API
or on a schedule.

Full flow:
    Content Source → Repurposer → UTM Tagger → Scheduler → (Runner → Publisher)

Scheduling strategy:
    - X/Twitter: 3-5 posts/day (spread across time slots)
    - LinkedIn: 1 post/day
    - TikTok scripts: generated but not auto-scheduled
    - Email snippets: generated but not auto-scheduled

Does NOT modify any existing modules.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Default time slots (UTC) for each platform
SCHEDULE_SLOTS = {
    "x": ["09:00", "12:00", "15:00", "18:00", "21:00"],
    "linkedin": ["10:00"],
}

# Platforms that get auto-scheduled vs just generated
SCHEDULABLE_PLATFORMS = {"x", "linkedin"}
GENERATE_ONLY_PLATFORMS = {"tiktok_script", "email_snippet", "x_thread"}


def _next_available_slot(platform: str, base_date: datetime, existing_times: set) -> str:
    """Find the next available time slot for a platform on a given date.

    Returns "YYYY-MM-DD HH:MM" or None if all slots are taken.
    """
    slots = SCHEDULE_SLOTS.get(platform, ["12:00"])
    date_str = base_date.strftime("%Y-%m-%d")

    for slot in slots:
        candidate = f"{date_str} {slot}"
        if candidate not in existing_times:
            return candidate

    # All slots taken for this date — try next day
    next_day = base_date + timedelta(days=1)
    next_date_str = next_day.strftime("%Y-%m-%d")
    for slot in slots:
        candidate = f"{next_date_str} {slot}"
        if candidate not in existing_times:
            return candidate

    return None


def _get_existing_scheduled_times() -> set:
    """Get all scheduled_datetime values from existing posts to avoid conflicts."""
    try:
        from growth.social_scheduler_dynamo import get_posts
        result = get_posts()
        if result.get("success"):
            return {
                p.get("scheduled_datetime", "")
                for p in result.get("posts", [])
                if p.get("status") in ("scheduled", "draft")
            }
    except Exception as e:
        logger.warning("Could not fetch existing schedule: %s", e)
    return set()


def run_content_pipeline(
    limit: int = 5,
    dry_run: bool = False,
    schedule_start: datetime = None,
) -> dict:
    """Run the full content pipeline: fetch → repurpose → schedule.

    Args:
        limit: Max content items to process in this run.
        dry_run: If True, repurpose but don't schedule.
        schedule_start: Base date for scheduling. Defaults to tomorrow UTC.

    Returns:
        Pipeline run summary.
    """
    from growth.content_source_manager import fetch_unprocessed_content, mark_content_status
    from growth.content_repurposer import repurpose_content

    # Fetch optimization signals to adjust platform selection
    opt_signals = None
    try:
        from growth.performance_optimizer import generate_optimization_signals
        opt_signals = generate_optimization_signals()
        if opt_signals.get("has_data"):
            logger.info("Pipeline using optimization signals: preferred=%s",
                       opt_signals.get("preferred_platforms"))
    except Exception:
        pass

    # Fetch unprocessed content
    fetch_result = fetch_unprocessed_content(limit=limit)
    if not fetch_result.get("success"):
        return {
            "success": False,
            "error": f"Failed to fetch content: {fetch_result.get('error')}",
        }

    items = fetch_result.get("items", [])
    if not items:
        return {
            "success": True,
            "message": "No unprocessed content found",
            "processed": 0,
            "posts_generated": 0,
            "posts_scheduled": 0,
        }

    # Track analytics (non-blocking)
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="content_repurposed",
            event_data={"pipeline_run": True, "items_found": len(items), "dry_run": dry_run},
        )
    except Exception:
        pass

    if schedule_start is None:
        schedule_start = datetime.now(timezone.utc) + timedelta(days=1)

    existing_times = _get_existing_scheduled_times() if not dry_run else set()

    total_processed = 0
    total_generated = 0
    total_scheduled = 0
    total_failed = 0
    results = []

    for item in items:
        content_id = item.get("content_id", "unknown")
        content = item.get("content", "")
        platforms_str = item.get("platforms", "x, linkedin")
        campaign = item.get("campaign", "content_repurpose")
        source_url = item.get("source_url", "https://ai1stseo.com")

        # Parse platforms
        platforms = [p.strip().lower() for p in platforms_str.split(",") if p.strip()]

        # Apply optimization signals: reorder platforms by performance
        if opt_signals and opt_signals.get("has_data") and opt_signals.get("preferred_platforms"):
            preferred = opt_signals["preferred_platforms"]
            # Move preferred platforms to front, keep others
            reordered = [p for p in preferred if p in platforms]
            reordered += [p for p in platforms if p not in reordered]
            platforms = reordered

        # Mark as processing
        if not dry_run:
            mark_content_status(content_id, "processing")

        # Repurpose
        try:
            pack = repurpose_content(
                content=content,
                platforms=platforms,
                brand_name="AI1stSEO",
                source_url=source_url,
                campaign=campaign,
            )
        except Exception as e:
            logger.error("Repurpose failed for %s: %s", content_id, e)
            if not dry_run:
                mark_content_status(content_id, "failed", str(e))
            total_failed += 1
            results.append({"content_id": content_id, "success": False, "error": str(e)})
            continue

        if not pack.get("success"):
            if not dry_run:
                mark_content_status(content_id, "failed", pack.get("error", "unknown"))
            total_failed += 1
            results.append({"content_id": content_id, "success": False, "error": pack.get("error")})
            continue

        # Schedule social posts
        scheduled_ids = []
        for r in pack.get("results", []):
            if not r.get("success"):
                continue
            total_generated += 1
            plat = r.get("platform", "")

            if plat not in SCHEDULABLE_PLATFORMS or dry_run:
                continue

            slot = _next_available_slot(plat, schedule_start, existing_times)
            if not slot:
                logger.warning("No available slot for %s", plat)
                continue

            try:
                from growth.social_scheduler_dynamo import create_post
                parts = slot.split(" ", 1)
                sched_date = parts[0]
                sched_time = parts[1] if len(parts) > 1 else "12:00"

                post_result = create_post(
                    content=r["output"],
                    platforms=[plat],
                    scheduled_date=sched_date,
                    scheduled_time=sched_time,
                    status="scheduled",
                )
                if post_result.get("success"):
                    total_scheduled += 1
                    existing_times.add(slot)
                    scheduled_ids.append(post_result.get("id"))
            except Exception as e:
                logger.warning("Failed to schedule %s post: %s", plat, e)

        # Mark processed
        total_processed += 1
        summary = f"generated={pack.get('succeeded', 0)}, scheduled={len(scheduled_ids)}"
        if not dry_run:
            mark_content_status(content_id, "processed", summary)

        results.append({
            "content_id": content_id,
            "success": True,
            "generated": pack.get("succeeded", 0),
            "scheduled": len(scheduled_ids),
            "scheduled_post_ids": scheduled_ids,
        })

    return {
        "success": True,
        "dry_run": dry_run,
        "processed": total_processed,
        "failed": total_failed,
        "posts_generated": total_generated,
        "posts_scheduled": total_scheduled,
        "optimization_applied": bool(opt_signals and opt_signals.get("has_data")),
        "optimization_hints": (opt_signals or {}).get("generation_hints", []),
        "results": results,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


def import_json_to_pipeline(json_path: str = "social_media_posts.json") -> dict:
    """Import existing social_media_posts.json into the content source table.

    Each post becomes a content item that can be repurposed for additional platforms.
    Only imports posts not already in the pipeline.
    """
    import json
    from growth.content_source_manager import add_content

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            posts = json.load(f)
    except Exception as e:
        return {"success": False, "error": f"Failed to read {json_path}: {e}"}

    imported = 0
    skipped = 0

    for post in posts:
        caption = post.get("caption", "")
        if not caption:
            skipped += 1
            continue

        platform = post.get("platform", "").lower().replace("twitter/x", "x")
        title = post.get("title", "")
        category = post.get("category", "")

        result = add_content(
            content=caption,
            title=title,
            source_type="seed_post",
            source_url="https://ai1stseo.com",
            platforms=["x", "linkedin", "email_snippet"],
            campaign=f"seed_{category.lower().replace(' ', '_')}" if category else "seed_content",
        )
        if result.get("success"):
            imported += 1
        else:
            skipped += 1

    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "total": len(posts),
    }
