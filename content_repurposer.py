"""
content_repurposer.py
Content Repurposing Engine — transforms a blog post into 6 platform-specific formats.

Formats:
  1. LinkedIn   — professional, 1300 chars, hook + insight + CTA
  2. Twitter/X  — 280 char post + optional 3-5 tweet thread
  3. Facebook   — conversational, 500 chars, engagement question
  4. Instagram  — caption + 30 hashtags, emoji-rich
  5. Email      — subject + preview + body with CTA
  6. Video      — 60-second script with hook/body/CTA + speaker notes

Uses call_llm() (Nova Lite) by default. Each format gets its own tailored prompt
so the output matches platform conventions exactly.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ── Platform prompt templates ─────────────────────────────────────────────── #

LINKEDIN_PROMPT = """Transform this blog content into a LinkedIn post. Rules:
- Max 1300 characters
- Start with a strong hook (first line grabs attention — use a bold statement, question, or stat)
- Break into short paragraphs (2-3 sentences each)
- Include 1-2 relevant insights or takeaways
- End with a clear CTA (ask a question, invite comments, or link to the full post)
- Professional but conversational tone
- Add 3-5 relevant hashtags at the end
- Use line breaks between paragraphs for readability

Blog content:
{content}

Target audience/keyword: {keyword}

Return ONLY the LinkedIn post text, ready to copy-paste. No explanations."""


TWITTER_PROMPT = """Transform this blog content into Twitter/X content. Produce TWO things:

1. A single standalone tweet (max 280 characters) — punchy, shareable, makes people want to click
2. A thread version (3-5 tweets, each max 280 chars) — numbered 1/5, 2/5 etc.

Rules:
- Use short, punchy sentences
- Include 1-2 relevant hashtags per tweet
- The standalone tweet should work on its own as a hook
- Thread should tell a mini-story: hook → insight → proof → takeaway → CTA
- No fluff, every word earns its place

Blog content:
{content}

Target audience/keyword: {keyword}

Return as JSON:
{{
  "single_tweet": "the standalone tweet",
  "thread": ["tweet 1/5...", "tweet 2/5...", "tweet 3/5..."]
}}"""


FACEBOOK_PROMPT = """Transform this blog content into a Facebook post. Rules:
- Max 500 characters for the main text
- Conversational, warm, relatable tone
- Start with something personal or a question
- Include the key insight in simple language
- End with an engagement question (ask readers to share their experience)
- Add 1-2 relevant emojis (not overdone)
- No hashtags (Facebook doesn't use them effectively)

Blog content:
{content}

Target audience/keyword: {keyword}

Return ONLY the Facebook post text, ready to copy-paste. No explanations."""


INSTAGRAM_PROMPT = """Transform this blog content into an Instagram caption. Rules:
- Caption: 150-300 words, storytelling style
- Start with a hook line (first sentence visible before "more")
- Use short paragraphs with line breaks
- Include a clear CTA (save this, share with a friend, comment below)
- Add emojis naturally throughout (not excessive)
- End with exactly 30 relevant hashtags on a separate line (mix of popular + niche)
- Include 2-3 hashtags with the brand/topic name

Blog content:
{content}

Target audience/keyword: {keyword}

Return as JSON:
{{
  "caption": "the full caption text with emojis and line breaks",
  "hashtags": "#hashtag1 #hashtag2 ... (30 total)"
}}"""


EMAIL_PROMPT = """Transform this blog content into an email newsletter. Rules:
- Subject line: max 50 chars, curiosity-driven, no clickbait
- Preview text: max 90 chars (shows in inbox before opening)
- Body: 150-250 words
  - Open with a personal greeting and hook
  - 2-3 short paragraphs with the key insights
  - Use bullet points for scanability
  - End with ONE clear CTA button text + link description
- Tone: helpful expert writing to a colleague, not salesy
- Include a P.S. line with a secondary CTA or fun fact

Blog content:
{content}

Target audience/keyword: {keyword}

Return as JSON:
{{
  "subject_line": "...",
  "preview_text": "...",
  "body": "full email body with formatting",
  "cta_text": "button text",
  "ps_line": "P.S. ..."
}}"""


VIDEO_PROMPT = """Transform this blog content into a 60-second video script. Rules:
- Total speaking time: ~60 seconds (roughly 150 words)
- Structure:
  - HOOK (0-5s): Bold opening statement or question that stops the scroll
  - PROBLEM (5-15s): What pain point does the audience have?
  - SOLUTION (15-40s): The key insight from the blog, explained simply
  - PROOF (40-50s): One stat, example, or result that backs it up
  - CTA (50-60s): What should the viewer do next?
- Include speaker notes (tone, gestures, emphasis)
- Write for spoken word — short sentences, natural rhythm
- Include suggested B-roll or visual cues in brackets

Blog content:
{content}

Target audience/keyword: {keyword}

Return as JSON:
{{
  "hook": "0-5s script text",
  "problem": "5-15s script text",
  "solution": "15-40s script text",
  "proof": "40-50s script text",
  "cta": "50-60s script text",
  "speaker_notes": "tone and delivery guidance",
  "visual_cues": ["suggested visual 1", "suggested visual 2", "suggested visual 3"]
}}"""


PLATFORM_PROMPTS = {
    "linkedin": LINKEDIN_PROMPT,
    "twitter": TWITTER_PROMPT,
    "facebook": FACEBOOK_PROMPT,
    "instagram": INSTAGRAM_PROMPT,
    "email": EMAIL_PROMPT,
    "video": VIDEO_PROMPT,
}

PLATFORM_LABELS = {
    "linkedin": "LinkedIn",
    "twitter": "Twitter/X",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "email": "Email Newsletter",
    "video": "Video Script (60s)",
}


# ── Helpers ───────────────────────────────────────────────────────────────── #

def _extract_json_safe(text):
    """Try to parse JSON from LLM response, return raw text if it fails."""
    if not text:
        return text
    # Try fenced code block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Try raw JSON
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return text


def _truncate_content(text, max_chars=4000):
    """Truncate blog content to fit within prompt token budget."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Content truncated for processing...]"


# ── Main engine ───────────────────────────────────────────────────────────── #

def repurpose_content(content, keyword="", platforms=None, call_llm_fn=None):
    """
    Transform blog content into multiple platform formats.

    Args:
        content: the blog post text (or extracted text from URL)
        keyword: target audience/keyword context
        platforms: list of platforms to generate (default: all 6)
        call_llm_fn: the LLM calling function (injected from app.py)

    Returns:
        dict with results per platform, timing, and metadata
    """
    if not platforms:
        platforms = list(PLATFORM_PROMPTS.keys())

    # Validate platforms
    platforms = [p.lower().strip() for p in platforms if p.lower().strip() in PLATFORM_PROMPTS]
    if not platforms:
        platforms = list(PLATFORM_PROMPTS.keys())

    content_trimmed = _truncate_content(content)
    results = {}
    total_time = 0

    for platform in platforms:
        t0 = time.time()
        prompt = PLATFORM_PROMPTS[platform].format(
            content=content_trimmed,
            keyword=keyword or "(general audience)",
        )

        try:
            raw_response = call_llm_fn(prompt, timeout=20)
            elapsed = round(time.time() - t0, 2)
            total_time += elapsed

            # Parse structured formats (Twitter, Instagram, Email, Video return JSON)
            if platform in ("twitter", "instagram", "email", "video"):
                parsed = _extract_json_safe(raw_response)
            else:
                parsed = raw_response.strip() if raw_response else ""

            results[platform] = {
                "platform": PLATFORM_LABELS[platform],
                "content": parsed,
                "raw": raw_response if isinstance(parsed, str) and parsed == raw_response else None,
                "elapsed": elapsed,
                "status": "success",
            }
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            total_time += elapsed
            logger.warning("Repurpose failed for %s: %s", platform, e)
            results[platform] = {
                "platform": PLATFORM_LABELS[platform],
                "content": None,
                "error": str(e)[:200],
                "elapsed": elapsed,
                "status": "error",
            }

    word_count = len(content.split())
    return {
        "results": results,
        "platforms_generated": len([r for r in results.values() if r["status"] == "success"]),
        "platforms_failed": len([r for r in results.values() if r["status"] == "error"]),
        "total_time": round(total_time, 2),
        "source_word_count": word_count,
        "keyword": keyword or "(not specified)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
