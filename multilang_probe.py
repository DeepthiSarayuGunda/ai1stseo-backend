"""
multilang_probe.py
Feature 3: Multi-Language GEO Probing

Extends GEO probing to support multiple languages.
Translates prompts, fires probes per language, and returns per-language visibility.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import psycopg2.extras

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"

LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "pt": "Portuguese", "it": "Italian", "nl": "Dutch", "ja": "Japanese",
    "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "hi": "Hindi",
    "ru": "Russian", "tr": "Turkish", "pl": "Polish", "sv": "Swedish",
}


def init_multilang_columns():
    """Add language column to geo_probes table if not exists."""
    from db import get_conn, _safe_add_columns
    with get_conn() as conn:
        cur = conn.cursor()
        _safe_add_columns(cur, "geo_probes", {
            "language": "VARCHAR(10) DEFAULT 'en'",
        })
        conn.commit()
        logger.info("geo_probes.language column verified")


def _translate_prompt(keyword, brand_name, language):
    """Translate the probe prompt to the target language using LLM."""
    if language == "en":
        return (
            f"I'm researching '{keyword}'. What are the best options available? "
            f"Please provide specific brand and product recommendations."
        )
    from ai_provider import generate
    lang_name = LANGUAGE_NAMES.get(language, language)
    translate_prompt = (
        f"Translate the following search query into {lang_name}. "
        f"Return ONLY the translated text, nothing else:\n\n"
        f"\"I'm researching '{keyword}'. What are the best options available? "
        f"Please provide specific brand and product recommendations.\""
    )
    try:
        translated = generate(translate_prompt, provider="nova")
        return translated.strip().strip('"').strip("'")
    except Exception as e:
        logger.warning("Translation to %s failed: %s", language, e)
        # Fallback to English
        return f"I'm researching '{keyword}'. What are the best options? Recommend specific brands."


def _probe_single_language(brand_name, keyword, language, provider):
    """Run a single GEO probe in a specific language."""
    from geo_probe_service import _detect_citation
    from ai_provider import generate

    prompt = _translate_prompt(keyword, brand_name, language)
    try:
        response = generate(prompt, provider=provider)
        cited, context, confidence = _detect_citation(response, brand_name)
        # Determine sentiment from context
        sentiment = "neutral"
        if context:
            pos_words = ["best", "top", "great", "excellent", "leading", "popular", "recommended"]
            neg_words = ["worst", "avoid", "poor", "bad", "disappointing"]
            ctx_lower = context.lower()
            if any(w in ctx_lower for w in pos_words):
                sentiment = "positive"
            elif any(w in ctx_lower for w in neg_words):
                sentiment = "negative"
        logger.info("Multilang probe [%s]: cited=%s conf=%.2f snippet=%s", language, cited, confidence, response[:100])
        return {
            "language": language,
            "language_name": LANGUAGE_NAMES.get(language, language),
            "cited": cited,
            "confidence": confidence,
            "citation_context": context or "",
            "sentiment": sentiment,
            "response_snippet": response[:500],
            "status": "ok",
        }
    except Exception as e:
        logger.warning("Multilang probe [%s] failed: %s", language, e)
        return {
            "language": language,
            "language_name": LANGUAGE_NAMES.get(language, language),
            "cited": False, "confidence": 0, "citation_context": "",
            "sentiment": "unknown", "response_snippet": "",
            "status": "error", "error": str(e)[:200],
        }


def probe_multilang(brand_name, keyword, languages=None, provider="nova", project_id=None):
    """Run GEO probes across multiple languages and return per-language visibility."""
    if not languages:
        languages = ["en"]
    pid = project_id or DEFAULT_PROJECT_ID
    t0 = time.time()

    # Probe all languages concurrently
    results = []
    with ThreadPoolExecutor(max_workers=min(len(languages), 4)) as pool:
        futures = {
            pool.submit(_probe_single_language, brand_name, keyword, lang, provider): lang
            for lang in languages
        }
        for future in as_completed(futures):
            results.append(future.result())

    # Sort by language order
    lang_order = {l: i for i, l in enumerate(languages)}
    results.sort(key=lambda r: lang_order.get(r["language"], 99))

    # Compute per-language visibility scores
    for r in results:
        if r["status"] == "ok":
            # Score: 0-100 based on citation + confidence + sentiment
            base = 50 if r["cited"] else 0
            conf_bonus = int(r["confidence"] * 30)
            sent_bonus = 20 if r["sentiment"] == "positive" else 10 if r["sentiment"] == "neutral" else 0
            r["visibility_score"] = min(100, base + conf_bonus + sent_bonus)
        else:
            r["visibility_score"] = 0

    # Save each result to geo_probes with language column
    try:
        from db import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            for r in results:
                if r["status"] == "ok":
                    try:
                        cur.execute("""
                            INSERT INTO geo_probes
                                (project_id, brand_name, keyword, ai_model, cited,
                                 citation_context, response_snippet, confidence, sentiment, language)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (pid, brand_name, keyword, provider, r["cited"],
                              r["citation_context"][:1000], r["response_snippet"][:2000],
                              r["confidence"], r["sentiment"], r["language"]))
                    except Exception as e:
                        logger.warning("Failed to save multilang probe for %s: %s", r["language"], e)
            conn.commit()
    except Exception as e:
        logger.warning("Failed to persist multilang probes to RDS: %s", e)

    elapsed = round(time.time() - t0, 2)
    cited_count = sum(1 for r in results if r.get("cited"))
    avg_score = round(sum(r["visibility_score"] for r in results) / max(len(results), 1))

    return {
        "brand_name": brand_name,
        "keyword": keyword,
        "languages_probed": len(results),
        "languages_cited": cited_count,
        "average_visibility_score": avg_score,
        "results": results,
        "elapsed_seconds": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
