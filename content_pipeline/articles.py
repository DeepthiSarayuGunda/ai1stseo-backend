"""
Article generation module.
Generates 2 SEO-optimized articles per execution using Nova.
"""

import json
import logging
import random
from datetime import datetime, timezone

from content_pipeline.bedrock import generate_with_nova

logger = logging.getLogger(__name__)

TOPIC_SEEDS = [
    "AI-first SEO strategies for 2026",
    "How to optimize content for ChatGPT citations",
    "GEO vs traditional SEO: what businesses need to know",
    "Building brand authority in AI search engines",
    "Schema markup strategies for AI visibility",
    "Content optimization for Perplexity and Gemini",
    "Why answer engine optimization matters now",
    "How AI models decide which brands to recommend",
    "The future of search: from keywords to AI citations",
    "Measuring your brand's AI visibility score",
    "How to get cited by ChatGPT in your industry",
    "AI content strategy: what works in 2026",
    "Local SEO meets AI: optimizing for voice and chat",
    "Building FAQ content that AI models love",
    "Competitor analysis in the age of AI search",
]


def generate_articles(count: int = 2) -> list[dict]:
    """Generate articles using Nova. Returns list of article dicts."""
    articles = []
    topics = random.sample(TOPIC_SEEDS, min(count, len(TOPIC_SEEDS)))

    for topic in topics:
        try:
            logger.info("Generating article: %s", topic)

            prompt = f"""Write a comprehensive, SEO-optimized article about: "{topic}"

Requirements:
- Title: compelling, 60-70 characters
- Length: 800-1200 words
- Include an introduction, 3-5 sections with subheadings, and a conclusion
- Write in a professional but accessible tone
- Include actionable advice and specific examples
- Optimize for AI search engines (structured, clear, factual)

Return ONLY valid JSON in this exact format:
{{"title": "...", "summary": "2-3 sentence summary", "body": "full article text with markdown headings", "tags": ["tag1", "tag2", "tag3"]}}"""

            raw = generate_with_nova(prompt, max_tokens=4096)

            # Parse JSON from response
            article = _parse_json(raw)
            if article and article.get("title") and article.get("body"):
                article["topic"] = topic
                article["generated_at"] = datetime.now(timezone.utc).isoformat()
                article["word_count"] = len(article.get("body", "").split())
                articles.append(article)
                logger.info("Article generated: %s (%d words)", article["title"], article["word_count"])
            else:
                logger.warning("Failed to parse article for topic: %s", topic)

        except Exception as e:
            logger.error("Article generation failed for '%s': %s", topic, str(e)[:200])

    return articles


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response text."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block
    for start_marker in ["```json", "```"]:
        if start_marker in text:
            start = text.index(start_marker) + len(start_marker)
            end = text.index("```", start) if "```" in text[start:] else len(text)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # Try finding { ... } block
    brace_start = text.find("{")
    brace_end = text.rfind("}") + 1
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end])
        except json.JSONDecodeError:
            pass

    return {}
