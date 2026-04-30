"""
growth/content_discovery.py
Content Discovery Engine — feeds fresh content into the pipeline.

Discovers trending topics and discussions from Reddit and AI/SEO
communities, extracts content ideas, and pushes them into the
content_source_manager for repurposing.

Uses Reddit's public JSON API (no credentials needed for read-only).
Falls back to curated topic generation via AI when Reddit is unreachable.

Does NOT modify any existing modules.
"""

import logging
import re
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

# Target subreddits for AI SEO content discovery
DEFAULT_SUBREDDITS = [
    "SEO", "digital_marketing", "ChatGPT", "artificial",
    "startups", "marketing", "content_marketing",
]

# Keywords that signal high-relevance posts
RELEVANCE_KEYWORDS = [
    "ai seo", "chatgpt seo", "aeo", "geo score", "ai visibility",
    "answer engine", "ai search", "perplexity", "gemini seo",
    "schema markup", "faq schema", "ai citation", "ai ranking",
    "content optimization", "ai discovery", "llm", "ai overviews",
]

REDDIT_USER_AGENT = "ai1stseo-discovery/1.0"


def fetch_reddit_posts(subreddits: list = None, limit: int = 10) -> list:
    """Fetch recent posts from target subreddits via Reddit JSON API.

    No authentication needed — uses public .json endpoints.
    Returns list of raw post dicts.
    """
    subs = subreddits or DEFAULT_SUBREDDITS
    all_posts = []

    for sub in subs:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
            resp = requests.get(url, headers={"User-Agent": REDDIT_USER_AGENT}, timeout=10)
            if resp.status_code != 200:
                logger.warning("Reddit r/%s returned %d", sub, resp.status_code)
                continue

            data = resp.json()
            children = data.get("data", {}).get("children", [])
            for child in children:
                post = child.get("data", {})
                if post.get("stickied") or post.get("is_video"):
                    continue
                all_posts.append({
                    "title": post.get("title", ""),
                    "selftext": post.get("selftext", "")[:2000],
                    "subreddit": sub,
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "created_utc": post.get("created_utc", 0),
                })
        except Exception as e:
            logger.warning("Failed to fetch r/%s: %s", sub, e)

    return all_posts


def _score_relevance(post: dict) -> float:
    """Score a post's relevance to AI SEO topics. 0-1 scale."""
    text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
    hits = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)
    keyword_score = min(hits / 3, 1.0)

    # Engagement signal
    score = post.get("score", 0)
    comments = post.get("num_comments", 0)
    engagement_score = min((score + comments * 2) / 100, 1.0)

    return round(keyword_score * 0.7 + engagement_score * 0.3, 3)


def extract_content_items(raw_posts: list, min_relevance: float = 0.2) -> list:
    """Filter and transform raw posts into content pipeline items.

    Returns list of dicts ready for content_source_manager.add_content().
    """
    items = []
    for post in raw_posts:
        relevance = _score_relevance(post)
        if relevance < min_relevance:
            continue

        title = post.get("title", "").strip()
        body = post.get("selftext", "").strip()
        content = f"{title}\n\n{body}" if body else title

        if len(content) < 50:
            continue

        items.append({
            "content": content,
            "title": title[:200],
            "source_type": "reddit_discovery",
            "source_url": post.get("url", "https://ai1stseo.com"),
            "platforms": ["x", "linkedin", "email_snippet"],
            "campaign": f"discovery_{post.get('subreddit', 'general').lower()}",
            "relevance": relevance,
            "subreddit": post.get("subreddit", ""),
        })

    # Sort by relevance, take top items
    items.sort(key=lambda x: x["relevance"], reverse=True)
    return items[:20]


def fetch_trending_topics() -> list:
    """Generate trending AI SEO topic ideas via the AI provider.

    Fallback when Reddit is unreachable or returns low-relevance content.
    """
    try:
        from ai_provider import generate
        prompt = (
            "List 5 trending topics in AI SEO, AEO (Answer Engine Optimization), "
            "and GEO (Generative Engine Optimization) for April 2026. "
            "For each, write a 2-3 sentence content brief that could be turned into "
            "a social media post. Format: TOPIC: [title]\\nBRIEF: [content]\\n\\n"
        )
        raw = generate(prompt, provider="nova")

        items = []
        blocks = re.split(r'\n\n+', raw.strip())
        for block in blocks:
            lines = block.strip().split("\n")
            title = ""
            brief = ""
            for line in lines:
                if line.upper().startswith("TOPIC:"):
                    title = line.split(":", 1)[1].strip()
                elif line.upper().startswith("BRIEF:"):
                    brief = line.split(":", 1)[1].strip()
            if title and brief:
                items.append({
                    "content": f"{title}\n\n{brief}",
                    "title": title[:200],
                    "source_type": "ai_trending",
                    "source_url": "https://ai1stseo.com",
                    "platforms": ["x", "linkedin"],
                    "campaign": "trending_topics",
                })
        return items
    except Exception as e:
        logger.error("Trending topics generation failed: %s", e)
        return []


def push_to_pipeline(items: list) -> dict:
    """Push discovered content items into the content source manager.

    Deduplicates by checking existing content titles.
    """
    from growth.content_source_manager import add_content, list_content

    # Get existing titles to avoid duplicates
    existing = set()
    try:
        result = list_content(limit=200)
        if result.get("success"):
            existing = {
                i.get("title", "").lower().strip()
                for i in result.get("items", [])
            }
    except Exception:
        pass

    added = 0
    skipped = 0

    for item in items:
        title_key = item.get("title", "").lower().strip()
        if title_key in existing:
            skipped += 1
            continue

        result = add_content(
            content=item["content"],
            title=item.get("title", ""),
            source_type=item.get("source_type", "discovery"),
            source_url=item.get("source_url", "https://ai1stseo.com"),
            platforms=item.get("platforms"),
            campaign=item.get("campaign", "content_discovery"),
        )
        if result.get("success"):
            added += 1
            existing.add(title_key)
        else:
            skipped += 1

    # Track discovery event
    try:
        from growth.analytics_tracker import track_event
        track_event(
            event_type="content_repurposed",
            event_data={"discovery_run": True, "added": added, "skipped": skipped},
        )
    except Exception:
        pass

    return {
        "success": True,
        "added": added,
        "skipped": skipped,
        "total_candidates": len(items),
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }


def run_discovery(subreddits: list = None, limit: int = 10, min_relevance: float = 0.2) -> dict:
    """Full discovery cycle: fetch → filter → push to pipeline.

    Tries Reddit first, falls back to AI-generated trending topics.
    """
    # Try Reddit
    raw_posts = fetch_reddit_posts(subreddits=subreddits, limit=limit)
    items = extract_content_items(raw_posts, min_relevance=min_relevance)

    # If Reddit yielded too few, supplement with AI trending topics
    if len(items) < 3:
        trending = fetch_trending_topics()
        items.extend(trending)

    if not items:
        return {"success": True, "added": 0, "message": "No relevant content discovered"}

    return push_to_pipeline(items)
