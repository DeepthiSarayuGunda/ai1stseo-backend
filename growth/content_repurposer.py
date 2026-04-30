"""
growth/content_repurposer.py
Content Repurposing Pipeline — transforms blog/article content into
platform-specific social posts, email snippets, and short-form scripts.

Integrates with:
    - ai_provider.generate() for AI-powered transformation
    - utm_manager.generate_utm_url() for auto-tagging outbound links
    - social_orchestrator.publish_post() for direct publishing
    - social_scheduler_dynamo for scheduling

Does NOT modify original content. Only creates new derivative formats.
"""

import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Platform output specs
PLATFORM_SPECS = {
    "x": {"max_chars": 280, "label": "X/Twitter Post"},
    "linkedin": {"max_chars": 3000, "label": "LinkedIn Post"},
    "tiktok_script": {"max_chars": 1000, "label": "TikTok/Reel Script"},
    "email_snippet": {"max_chars": 500, "label": "Email Snippet"},
    "x_thread": {"max_chars": 2000, "label": "X/Twitter Thread"},
}

DEFAULT_PLATFORMS = ["x", "linkedin", "tiktok_script", "email_snippet"]


def _call_ai(prompt: str) -> str:
    """Call AI provider with fallback chain."""
    from ai_provider import generate
    return generate(prompt, provider="nova")


def _tag_links(text: str, source: str, medium: str, campaign: str) -> str:
    """Find URLs in text and append UTM parameters."""
    try:
        from growth.utm_manager import generate_utm_url
    except ImportError:
        return text

    def _replace_url(match):
        url = match.group(0)
        if "ai1stseo.com" not in url:
            return url
        result = generate_utm_url(
            base_url=url, source=source,
            medium=medium, campaign=campaign,
        )
        return result.get("tagged_url", url) if result.get("success") else url

    return re.sub(r'https?://[^\s\)\"\']+', _replace_url, text)



def repurpose_for_platform(
    content: str,
    platform: str,
    brand_name: str = "AI1stSEO",
    source_url: str = "https://ai1stseo.com",
    campaign: str = "content_repurpose",
) -> dict:
    """Transform content into a single platform-specific format.

    Args:
        content: Source blog/article text.
        platform: Target platform key from PLATFORM_SPECS.
        brand_name: Brand name for context.
        source_url: Link back to original content.
        campaign: UTM campaign name.

    Returns:
        {"success": bool, "platform": str, "output": str, "char_count": int}
    """
    if not content or not content.strip():
        return {"success": False, "platform": platform, "error": "content is required"}

    spec = PLATFORM_SPECS.get(platform)
    if not spec:
        return {"success": False, "platform": platform,
                "error": f"Unknown platform: {platform}. Supported: {list(PLATFORM_SPECS.keys())}"}

    prompts = {
        "x": (
            f"Rewrite the following content as a single tweet (max 270 chars). "
            f"Be punchy, use 1-2 relevant hashtags. Include a call to action. "
            f"Brand: {brand_name}. Link: {source_url}\n\nContent:\n{content[:2000]}"
        ),
        "linkedin": (
            f"Rewrite the following content as a LinkedIn post (max 2800 chars). "
            f"Use a hook opening line, bullet points for key insights, and end with "
            f"a question to drive engagement. Professional but approachable tone. "
            f"Brand: {brand_name}. Link: {source_url}\n\nContent:\n{content[:3000]}"
        ),
        "tiktok_script": (
            f"Write a 30-60 second TikTok/Reel script based on this content. "
            f"Format: HOOK (first 3 seconds), BODY (key points), CTA (call to action). "
            f"Keep it conversational and energetic. Brand: {brand_name}.\n\nContent:\n{content[:2000]}"
        ),
        "email_snippet": (
            f"Write a short email snippet (max 400 chars) summarizing this content. "
            f"Include a compelling subject line on the first line. "
            f"Brand: {brand_name}. Link: {source_url}\n\nContent:\n{content[:2000]}"
        ),
        "x_thread": (
            f"Rewrite the following content as a Twitter/X thread of 3-6 tweets. "
            f"Number each tweet. First tweet is the hook. Last tweet has a CTA. "
            f"Brand: {brand_name}. Link: {source_url}\n\nContent:\n{content[:3000]}"
        ),
    }

    prompt = prompts.get(platform)
    if not prompt:
        return {"success": False, "platform": platform, "error": "No prompt template"}

    try:
        output = _call_ai(prompt)
    except Exception as e:
        logger.error("AI generation failed for %s: %s", platform, e)
        return {"success": False, "platform": platform, "error": str(e)}

    # Truncate to platform limit
    max_chars = spec["max_chars"]
    if len(output) > max_chars and platform == "x":
        output = output[:max_chars - 3] + "..."

    # Auto-tag links with UTM
    medium = "email" if platform == "email_snippet" else "social"
    output = _tag_links(output, source=platform, medium=medium, campaign=campaign)

    return {
        "success": True,
        "platform": platform,
        "label": spec["label"],
        "output": output,
        "char_count": len(output),
    }


def repurpose_content(
    content: str,
    platforms: list = None,
    brand_name: str = "AI1stSEO",
    source_url: str = "https://ai1stseo.com",
    campaign: str = "content_repurpose",
) -> dict:
    """Transform content into a multi-platform content pack.

    Args:
        content: Source blog/article/email text.
        platforms: List of platform keys. Defaults to DEFAULT_PLATFORMS.
        brand_name: Brand name for AI context.
        source_url: Link back to original content.
        campaign: UTM campaign name.

    Returns:
        BatchSummary with per-platform results.
    """
    if not content or not content.strip():
        return {"success": False, "error": "content is required", "results": []}

    targets = platforms or DEFAULT_PLATFORMS
    results = []
    succeeded = 0
    failed = 0

    for platform in targets:
        result = repurpose_for_platform(
            content=content, platform=platform,
            brand_name=brand_name, source_url=source_url,
            campaign=campaign,
        )
        results.append(result)
        if result.get("success"):
            succeeded += 1
        else:
            failed += 1

    # Track repurpose event (non-blocking)
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="content_repurposed",
            event_data={
                "platforms": targets,
                "succeeded": succeeded,
                "failed": failed,
                "campaign": campaign,
            },
        )
    except Exception:
        logger.warning("Failed to track content_repurposed event")

    return {
        "success": True,
        "total": len(targets),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def repurpose_and_schedule(
    content: str,
    platforms: list = None,
    brand_name: str = "AI1stSEO",
    source_url: str = "https://ai1stseo.com",
    campaign: str = "content_repurpose",
    schedule_datetime: str = None,
) -> dict:
    """Repurpose content AND schedule the social posts via DynamoDB scheduler.

    Non-social platforms (email_snippet, tiktok_script) are returned but not scheduled.
    Social platforms (x, linkedin) are created as scheduled posts.

    Args:
        content: Source text.
        platforms: Target platforms.
        brand_name: Brand name.
        source_url: Link to original.
        campaign: UTM campaign name.
        schedule_datetime: "YYYY-MM-DD HH:MM" UTC. If None, posts are created as drafts.

    Returns:
        Repurpose results + scheduling info.
    """
    pack = repurpose_content(
        content=content, platforms=platforms,
        brand_name=brand_name, source_url=source_url,
        campaign=campaign,
    )
    if not pack.get("success"):
        return pack

    SCHEDULABLE = {"x", "linkedin", "instagram", "facebook"}
    scheduled_posts = []

    for item in pack["results"]:
        if not item.get("success"):
            continue
        if item["platform"] not in SCHEDULABLE:
            continue

        try:
            from growth.social_scheduler_dynamo import create_post

            if schedule_datetime:
                parts = schedule_datetime.strip().split(" ", 1)
                sched_date = parts[0] if len(parts) >= 1 else ""
                sched_time = parts[1] if len(parts) >= 2 else "00:00"
            else:
                # Drafts still need a placeholder date/time for DynamoDB
                sched_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                sched_time = "00:00"

            result = create_post(
                content=item["output"],
                platforms=[item["platform"]],
                scheduled_date=sched_date,
                scheduled_time=sched_time,
                status="scheduled" if schedule_datetime else "draft",
            )
            if result.get("success"):
                scheduled_posts.append({
                    "platform": item["platform"],
                    "post_id": result.get("id"),
                    "status": "scheduled" if schedule_datetime else "draft",
                })
        except Exception as e:
            logger.warning("Failed to schedule %s post: %s", item["platform"], e)

    pack["scheduled_posts"] = scheduled_posts
    pack["scheduled_count"] = len(scheduled_posts)
    return pack


def repurpose_and_publish(
    content: str,
    platforms: list = None,
    brand_name: str = "AI1stSEO",
    source_url: str = "https://ai1stseo.com",
    campaign: str = "content_repurpose",
) -> dict:
    """Repurpose content AND immediately publish social posts via orchestrator.

    Non-social platforms are returned but not published.

    Args:
        content: Source text.
        platforms: Target platforms.
        brand_name: Brand name.
        source_url: Link to original.
        campaign: UTM campaign name.

    Returns:
        Repurpose results + publish outcomes.
    """
    pack = repurpose_content(
        content=content, platforms=platforms,
        brand_name=brand_name, source_url=source_url,
        campaign=campaign,
    )
    if not pack.get("success"):
        return pack

    PUBLISHABLE = {"x", "linkedin", "instagram", "facebook"}
    publish_results = []

    for item in pack["results"]:
        if not item.get("success"):
            continue
        if item["platform"] not in PUBLISHABLE:
            continue

        try:
            from growth.social_orchestrator import publish_post
            pub = publish_post({
                "content": item["output"],
                "platform": item["platform"],
            })
            publish_results.append({
                "platform": item["platform"],
                "published": pub.get("success", False),
                "provider": pub.get("provider"),
                "error": pub.get("error"),
            })
        except Exception as e:
            logger.warning("Failed to publish %s: %s", item["platform"], e)
            publish_results.append({
                "platform": item["platform"],
                "published": False,
                "error": str(e),
            })

    pack["publish_results"] = publish_results
    pack["published_count"] = sum(1 for r in publish_results if r.get("published"))
    return pack
