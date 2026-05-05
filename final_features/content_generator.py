"""
final_features/content_generator.py
Full content generator — produces ready-to-post social media content.

Combines template_generator output into a complete caption with
auto-generated hashtags. Supports professional and engaging styles.

Usage:
    from final_features.content_generator import generate_full_content
    result = generate_full_content("AI SEO Tips", style="engaging")
    print(result["caption"])
"""

import re
import random


# ---------------------------------------------------------------------------
# Hashtag pools by category
# ---------------------------------------------------------------------------

_HASHTAG_POOLS = {
    "seo": ["#SEO", "#SearchEngine", "#GoogleRanking", "#OrganicTraffic", "#SEOTips", "#SEOStrategy"],
    "ai": ["#AI", "#ArtificialIntelligence", "#AITools", "#MachineLearning", "#AIMarketing"],
    "marketing": ["#DigitalMarketing", "#ContentMarketing", "#MarketingTips", "#GrowthHacking", "#OnlineMarketing"],
    "business": ["#SmallBusiness", "#Entrepreneur", "#StartupLife", "#BusinessGrowth", "#BusinessTips"],
    "content": ["#ContentCreation", "#ContentStrategy", "#Copywriting", "#SocialMediaTips", "#ContentIsKing"],
    "tech": ["#TechTrends", "#Innovation", "#Automation", "#SaaS", "#MarTech"],
    "general": ["#Tips", "#HowTo", "#LearnDaily", "#GrowthMindset", "#Success"],
}

_TITLE_PATTERNS = [
    "{topic}: What You Need to Know",
    "The Complete Guide to {topic}",
    "{topic} — Tips That Actually Work",
    "Why {topic} Matters More Than Ever",
    "Master {topic} in 2026",
]


def _extract_hashtags(topic, count=8):
    """Generate relevant hashtags from the topic string."""
    topic_lower = topic.lower()
    selected = []

    # Match topic words against hashtag pools
    for category, tags in _HASHTAG_POOLS.items():
        if category in topic_lower or any(category in w for w in topic_lower.split()):
            selected.extend(tags)

    # Always include general tags
    selected.extend(_HASHTAG_POOLS["general"])

    # Deduplicate, shuffle, and trim
    seen = set()
    unique = []
    for tag in selected:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique.append(tag)
    random.shuffle(unique)
    return unique[:count]


def generate_full_content(topic, style="engaging"):
    """Generate complete ready-to-post social media content.

    Args:
        topic: The subject matter.
        style: "professional" or "engaging" (default).

    Returns:
        {
            "success": bool,
            "title": str,
            "caption": str,          # Full post text ready to copy-paste
            "hashtags": list[str],
            "hashtag_string": str,    # Space-separated for easy pasting
            "style": str,
            "topic": str,
            "hook": str,
            "bullets": list[str],
            "cta": str,
        }
    """
    if not topic or not topic.strip():
        return {"success": False, "error": "Topic is required"}

    topic = topic.strip()
    style = (style or "engaging").strip().lower()
    if style not in ("professional", "engaging"):
        style = "engaging"

    # Generate template
    from final_features.template_generator import generate_template
    tpl = generate_template(topic, style=style)
    if not tpl.get("success"):
        return tpl

    # Build title
    title = random.choice(_TITLE_PATTERNS).format(topic=topic)

    # Build caption from template parts
    hook = tpl["hook"]
    bullets = tpl["bullets"]
    cta = tpl["cta"]

    if style == "engaging":
        bullet_block = "\n".join(bullets)
    else:
        bullet_block = "\n".join("  - " + b for b in bullets)

    caption = hook + "\n\n" + bullet_block + "\n\n" + cta

    # Generate hashtags
    hashtags = _extract_hashtags(topic)
    hashtag_string = " ".join(hashtags)

    # Append hashtags to caption
    full_caption = caption + "\n\n" + hashtag_string

    return {
        "success": True,
        "title": title,
        "caption": full_caption,
        "hashtags": hashtags,
        "hashtag_string": hashtag_string,
        "style": style,
        "topic": topic,
        "hook": hook,
        "bullets": bullets,
        "cta": cta,
    }
