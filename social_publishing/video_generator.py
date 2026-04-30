"""
social_publishing/video_generator.py
Simulated video generation module.

Accepts a topic, generates a short-form video script (30-60 seconds),
and returns a fake video URL. No real API calls — designed to
demonstrate the video pipeline capability and integrate with the
existing content bridge and publish queue.

Usage:
    from social_publishing.video_generator import generate_video

    result = generate_video("5 SEO tips for small businesses")
    print(result["script"])
    print(result["video_url"])

    # Feed directly into the publish queue:
    from social_publishing.content_bridge import on_content_generated
    on_content_generated({
        "caption": result["script"],
        "video_url": result["video_url"],
    })
"""

import hashlib
import logging
import random
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Script templates — short-form video structures (30-60 sec)
# ---------------------------------------------------------------------------

_HOOKS = [
    "Stop scrolling — this changes everything about {topic}.",
    "Most people get {topic} completely wrong. Here's why.",
    "I tested {topic} for 30 days. The results shocked me.",
    "Here's what nobody tells you about {topic}.",
    "Want to master {topic}? Watch this.",
    "The #1 mistake people make with {topic}.",
]

_BODY_TEMPLATES = [
    (
        "Here's the thing — {topic} isn't as complicated as people make it.\n"
        "Step 1: Start with the basics and build a solid foundation.\n"
        "Step 2: Focus on consistency over perfection.\n"
        "Step 3: Measure what matters and adjust weekly."
    ),
    (
        "Let me break down {topic} in 30 seconds.\n"
        "First, understand your audience — what do they actually need?\n"
        "Second, create content that solves real problems.\n"
        "Third, distribute it where your audience already hangs out."
    ),
    (
        "The secret to {topic}? It's simpler than you think.\n"
        "Most people overcomplicate this. Here's the framework:\n"
        "Identify one core problem. Build one clear solution.\n"
        "Ship it fast. Learn from the data. Repeat."
    ),
]

_CTAS = [
    "Follow for more tips on {topic}. Link in bio.",
    "Save this for later. Share it with someone who needs it.",
    "Drop a comment if you want a deep dive on {topic}.",
    "Like and follow — new {topic} content every week.",
]


def generate_video(topic: str, duration_hint: str = "short") -> dict:
    """Generate a simulated video from a topic.

    Args:
        topic: The subject matter for the video.
        duration_hint: "short" (30s) or "medium" (60s). Default "short".

    Returns:
        {
            "success": True,
            "topic": str,
            "script": str,              # Full script text
            "hook": str,                # Opening hook line
            "duration_seconds": int,    # Estimated duration
            "video_url": str,           # Simulated CDN URL
            "thumbnail_url": str,       # Simulated thumbnail
            "generated_at": str,        # ISO timestamp
            "word_count": int,
        }
    """
    if not topic or not topic.strip():
        return {"success": False, "error": "Topic is required"}

    topic = topic.strip()
    logger.info("Generating video for topic: %s", topic[:60])

    # Simulate processing time
    time.sleep(random.uniform(0.3, 0.8))

    # Build script
    hook = random.choice(_HOOKS).format(topic=topic)
    body = random.choice(_BODY_TEMPLATES).format(topic=topic)
    cta = random.choice(_CTAS).format(topic=topic)

    script = f"{hook}\n\n{body}\n\n{cta}"

    # Estimate duration from word count (~2.5 words/sec for spoken content)
    word_count = len(script.split())
    duration = max(30, min(60, int(word_count / 2.5)))

    # Generate deterministic fake URLs from topic hash
    topic_hash = hashlib.md5(topic.lower().encode()).hexdigest()[:12]
    video_url = f"https://cdn.ai1stseo.com/videos/{topic_hash}.mp4"
    thumbnail_url = f"https://cdn.ai1stseo.com/thumbnails/{topic_hash}.jpg"

    result = {
        "success": True,
        "topic": topic,
        "script": script,
        "hook": hook,
        "duration_seconds": duration,
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "word_count": word_count,
    }

    logger.info("Video generated: %d words, ~%ds, url=%s", word_count, duration, video_url)
    return result


def generate_and_queue(topic: str) -> dict:
    """Generate a video and feed it into the publish queue.

    Combines generate_video() with the content bridge for a single-call
    video-to-social pipeline.

    Returns:
        Video generation result merged with queue result.
    """
    video = generate_video(topic)
    if not video.get("success"):
        return video

    try:
        from social_publishing.content_bridge import on_content_generated
        queue_result = on_content_generated({
            "caption": video["script"],
            "video_url": video["video_url"],
            "source": "video_generator",
        })
        video["queue_result"] = queue_result
        video["queued"] = queue_result.get("queued", False)
        video["platforms"] = queue_result.get("platforms", [])
    except Exception as e:
        logger.warning("Failed to queue video: %s", e)
        video["queue_result"] = {"success": False, "error": str(e)}
        video["queued"] = False

    return video
