"""
growth/ugc_collector.py
UGC Collector — turns user activity and mentions into content.

Monitors for brand mentions, relevant keywords, and community
discussions. Extracts usable content ideas and feeds them into
the content pipeline.

Sources:
    - Reddit comments mentioning AI SEO topics
    - Internal analytics (top-performing content for remix)
    - Manual submission via API

Feeds into: content_source_manager.add_content()
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

BRAND_KEYWORDS = ["ai1stseo", "ai 1st seo", "ai first seo"]
TOPIC_KEYWORDS = [
    "ai seo tool", "geo score", "aeo analyzer", "ai visibility check",
    "chatgpt ranking", "ai citation", "answer engine optimization",
]

REDDIT_USER_AGENT = "ai1stseo-ugc/1.0"


def collect_mentions(subreddits: list = None, limit: int = 25) -> list:
    """Search Reddit for brand and topic mentions.

    Uses Reddit search JSON API (no auth needed for public search).
    """
    subs = subreddits or ["SEO", "digital_marketing", "ChatGPT", "marketing"]
    mentions = []

    search_terms = BRAND_KEYWORDS[:2] + TOPIC_KEYWORDS[:3]

    for term in search_terms:
        try:
            url = f"https://www.reddit.com/search.json?q={term}&sort=new&limit={limit}"
            resp = requests.get(url, headers={"User-Agent": REDDIT_USER_AGENT}, timeout=10)
            if resp.status_code != 200:
                continue

            children = resp.json().get("data", {}).get("children", [])
            for child in children:
                post = child.get("data", {})
                mentions.append({
                    "title": post.get("title", ""),
                    "body": post.get("selftext", "")[:1500],
                    "subreddit": post.get("subreddit", ""),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "score": post.get("score", 0),
                    "search_term": term,
                    "is_brand_mention": any(bk in (post.get("title", "") + post.get("selftext", "")).lower() for bk in BRAND_KEYWORDS),
                })
        except Exception as e:
            logger.warning("Reddit search failed for '%s': %s", term, e)

    return mentions


def collect_top_performing_remix() -> list:
    """Pull top-performing posts and create remix content ideas.

    Takes the best-scoring posts and generates "response" or "follow-up"
    content ideas to ride the momentum.
    """
    items = []
    try:
        from growth.performance_optimizer import get_top_posts
        result = get_top_posts(limit=5)
        if not result.get("success"):
            return []

        for post in result.get("posts", []):
            platform = post.get("platform", "x")
            score = float(post.get("score", 0))
            if score < 5:
                continue

            items.append({
                "content": (
                    f"Follow-up to high-performing {platform} post (score: {score}).\n"
                    f"Original topic resonated with audience. Create a deeper dive, "
                    f"contrarian take, or 'part 2' expanding on the same theme.\n"
                    f"Platform: {platform}. Content type: {post.get('content_type', 'post')}."
                ),
                "title": f"Remix: top {platform} post (score {score})",
                "source_type": "ugc_remix",
                "source_url": "https://ai1stseo.com",
                "platforms": [platform, "email_snippet"],
                "campaign": "ugc_remix",
            })
    except Exception as e:
        logger.warning("Top performing remix failed: %s", e)

    return items


def extract_ugc_content(mentions: list) -> list:
    """Transform raw mentions into content pipeline items.

    Filters for quality and relevance, then formats for the pipeline.
    """
    items = []
    seen_titles = set()

    for m in mentions:
        title = m.get("title", "").strip()
        body = m.get("body", "").strip()

        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        # Skip low-quality
        if m.get("score", 0) < 2 and not m.get("is_brand_mention"):
            continue

        content = f"{title}\n\n{body}" if body else title
        if len(content) < 40:
            continue

        campaign = "ugc_brand_mention" if m.get("is_brand_mention") else "ugc_topic"

        items.append({
            "content": content[:3000],
            "title": title[:200],
            "source_type": "ugc_mention" if m.get("is_brand_mention") else "ugc_topic",
            "source_url": m.get("url", "https://ai1stseo.com"),
            "platforms": ["x", "linkedin"],
            "campaign": campaign,
        })

    return items[:15]


def push_to_pipeline(items: list) -> dict:
    """Push UGC content into the content source manager."""
    from growth.content_source_manager import add_content, list_content

    existing = set()
    try:
        result = list_content(limit=200)
        if result.get("success"):
            existing = {i.get("title", "").lower().strip() for i in result.get("items", [])}
    except Exception:
        pass

    added = 0
    skipped = 0

    for item in items:
        if item.get("title", "").lower().strip() in existing:
            skipped += 1
            continue

        result = add_content(
            content=item["content"],
            title=item.get("title", ""),
            source_type=item.get("source_type", "ugc"),
            source_url=item.get("source_url", "https://ai1stseo.com"),
            platforms=item.get("platforms"),
            campaign=item.get("campaign", "ugc"),
        )
        if result.get("success"):
            added += 1
        else:
            skipped += 1

    return {"success": True, "added": added, "skipped": skipped}


def run_ugc_collection() -> dict:
    """Full UGC cycle: collect mentions + remix top posts → push to pipeline."""
    # Collect external mentions
    mentions = collect_mentions()
    mention_items = extract_ugc_content(mentions)

    # Collect internal remix ideas
    remix_items = collect_top_performing_remix()

    all_items = mention_items + remix_items

    if not all_items:
        return {"success": True, "added": 0, "message": "No UGC content found"}

    result = push_to_pipeline(all_items)
    result["mentions_found"] = len(mentions)
    result["remix_ideas"] = len(remix_items)
    result["collected_at"] = datetime.now(timezone.utc).isoformat()
    return result
