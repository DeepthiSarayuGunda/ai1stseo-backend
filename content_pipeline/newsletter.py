"""
Newsletter content generation using Claude Haiku.
Generates summary, key insights, and CTA from articles.
"""

import json
import logging

from content_pipeline.bedrock import generate_with_haiku

logger = logging.getLogger(__name__)


def generate_newsletter(articles: list[dict]) -> dict:
    """Generate newsletter content from a list of articles."""
    if not articles:
        return {"error": "No articles provided"}

    article_summaries = ""
    for i, a in enumerate(articles, 1):
        title = a.get("title", "Untitled")
        summary = a.get("summary", "")
        article_summaries += f"\nArticle {i}: {title}\nSummary: {summary}\n"

    prompt = f"""Based on these articles, create newsletter content:
{article_summaries}

Generate a newsletter with:
1. A compelling subject line
2. A brief intro paragraph (2-3 sentences)
3. 3-5 key insights (one sentence each)
4. A call-to-action

Return ONLY valid JSON:
{{"subject_line": "...", "intro": "...", "insights": ["insight1", "insight2", "insight3"], "cta_text": "...", "cta_url": "https://ai1stseo.com"}}"""

    try:
        raw = generate_with_haiku(prompt)
        newsletter = _parse_json(raw)
        if newsletter and newsletter.get("subject_line"):
            logger.info("Newsletter generated: %s", newsletter["subject_line"])
            return newsletter
        logger.warning("Failed to parse newsletter content")
        return {"error": "Parse failed", "raw": raw[:500]}
    except Exception as e:
        logger.error("Newsletter generation failed: %s", str(e)[:200])
        return {"error": str(e)[:200]}


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response."""
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
