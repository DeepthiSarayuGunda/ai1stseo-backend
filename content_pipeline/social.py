"""
Social media content generation using Claude Haiku.
Generates hooks, captions, hashtags, and CTAs for each article.
"""

import json
import logging

from content_pipeline.bedrock import generate_with_haiku

logger = logging.getLogger(__name__)


def generate_social_posts(articles: list[dict]) -> list[dict]:
    """Generate social media posts for each article."""
    posts = []

    for article in articles:
        title = article.get("title", "")
        summary = article.get("summary", "")

        prompt = f"""Create a social media post for this article:
Title: {title}
Summary: {summary}

Generate content for LinkedIn/Twitter/Instagram with:
- A hook (first line that grabs attention)
- Caption (2-3 sentences)
- 5 relevant hashtags
- A call-to-action

Return ONLY valid JSON:
{{"hook": "...", "caption": "...", "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"], "cta": "...", "platform_variants": {{"twitter": "short version under 280 chars", "linkedin": "professional version", "instagram": "engaging version with emojis"}}}}"""

        try:
            raw = generate_with_haiku(prompt)
            post = _parse_json(raw)
            if post and post.get("hook"):
                post["article_title"] = title
                posts.append(post)
                logger.info("Social post generated for: %s", title)
            else:
                logger.warning("Failed to parse social post for: %s", title)
        except Exception as e:
            logger.error("Social post generation failed for '%s': %s", title, str(e)[:200])

    return posts


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    brace_start = text.find("{")
    brace_end = text.rfind("}") + 1
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end])
        except json.JSONDecodeError:
            pass
    return {}
