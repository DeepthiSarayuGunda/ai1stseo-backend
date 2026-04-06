"""
geo_probe_service.py
GEO / AEO Monitoring Engine — Multi-Provider with DB Persistence

All AI calls go direct — no EC2:
  - nova   → Bedrock Nova Lite (boto3)
  - ollama → Ollama API (https://ollama.sageaios.com)

All results persisted to DynamoDB (default) or RDS (geo_probes + ai_visibility_history).
Respects USE_DYNAMODB / USE_RDS env flags set in app.py.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:30b-a3b")

# Match the same flag logic as app.py
_USE_DYNAMODB = not bool(os.environ.get("USE_RDS"))


def _get_insert_probe():
    if _USE_DYNAMODB:
        from db_dynamo import insert_probe
    else:
        from db import insert_probe
    return insert_probe


def _get_insert_visibility_batch():
    if _USE_DYNAMODB:
        from db_dynamo import insert_visibility_batch
    else:
        from db import insert_visibility_batch
    return insert_visibility_batch


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── prompt & citation detection ───────────────────────────────────────────────

def _build_prompt(keyword, brand_name):
    return (
        f"You are a knowledgeable product reviewer. A user wants to know:\n\n"
        f'"{keyword}"\n\n'
        f"List the top brands and products for this category. "
        f"If {brand_name} is a genuinely well-known brand in this category, "
        f"include it and explain why it stands out. "
        f"If {brand_name} is NOT a real, established brand in this space, "
        f"do not mention it at all — do not invent or fabricate information about it. "
        f"For each brand, briefly explain why it stands out."
    )

_RECOMMEND_PATTERNS = [
    r"(?:top|best|leading|excellent|outstanding|highly\s+rated|popular|go-to|premier)",
    r"(?:recommend|stands?\s+out|known\s+for|excels?|dominates?|renowned)",
    r"(?:#\d|number\s+\d|first\s+choice|top\s+pick|editor.?s?\s+choice)",
]
_COMPARE_PATTERNS = [
    r"(?:compared?\s+to|alternative|competitor|similar\s+to|versus|vs\.?|alongside)",
    r"(?:however|although|while|on\s+the\s+other\s+hand|but)",
    r"(?:also\s+worth|another\s+option|consider)",
]
_CONDITIONAL_PHRASES = [
    r"if it is relevant", r"if applicable", r"if it fits",
    r"if it is a relevant", r"if it is a reputable", r"if they are relevant",
    r"if you consider", r"worth mentioning if", r"could be considered if",
    r"not a well-known", r"not a recognized", r"not typically known",
    r"not a real", r"not an established", r"has not been included",
    r"not included in this", r"do not have.{0,20}information",
    r"i'?m not (?:familiar|aware)", r"doesn'?t appear to be",
    r"no information available", r"could not find",
    r"cannot confirm", r"i cannot (?:verify|confirm)",
]

def _split_sentences(text):
    text = re.sub(r'\n\s*[-*•]\s*', '\n', text)
    text = re.sub(r'\n\s*\d+[.)]\s*', '\n', text)
    parts = re.split(r'(?<=[.!?])\s+|\n{1,}', text)
    return [s.strip() for s in parts if s.strip()]

def _find_brand_sentences(text, brand):
    sentences = _split_sentences(text)
    pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
    return [s for s in sentences if pattern.search(s)]

def _score_confidence(brand_sentences):
    if not brand_sentences:
        return 0.0
    combined = " ".join(brand_sentences).lower()
    for pat in _RECOMMEND_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            return 1.0
    for pat in _COMPARE_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            return 0.5
    return 0.5

def _is_conditional_mention(brand_sentences):
    if not brand_sentences:
        return False
    combined = " ".join(brand_sentences).lower()
    for pat in _CONDITIONAL_PHRASES:
        if re.search(pat, combined, re.IGNORECASE):
            return True
    return False

def _detect_citation(response_text, brand_name):
    brand_sentences = _find_brand_sentences(response_text, brand_name)
    cited = len(brand_sentences) > 0
    context = brand_sentences[0] if brand_sentences else None
    confidence = _score_confidence(brand_sentences)
    if cited and _is_conditional_mention(brand_sentences):
        cited, confidence, context = False, 0.0, None
    if cited and context and brand_name.lower() not in context.lower():
        cited, confidence, context = False, 0.0, None
    return cited, context, confidence


# ── available models ──────────────────────────────────────────────────────────

def available_models() -> list[dict]:
    from ai_provider import get_available_providers
    return get_available_providers()


# ── single probe (direct AI call + RDS persist) ──────────────────────────────

def geo_probe(brand_name: str, keyword: str, ai_model: str = "nova") -> dict:
    """Probe a keyword for brand mentions. Calls AI directly, persists to DB."""
    from ai_provider import generate
    insert_probe = _get_insert_probe()

    prompt = _build_prompt(keyword, brand_name)
    logger.info("GEO probe: brand=%s keyword=%s provider=%s", brand_name, keyword, ai_model)

    response_text = generate(prompt, provider=ai_model)
    cited, context, confidence = _detect_citation(response_text, brand_name)
    model_label = f"ollama/{OLLAMA_MODEL}" if ai_model == "ollama" else ai_model

    try:
        insert_probe(
            keyword=keyword, brand=brand_name, ai_model=model_label,
            cited=cited, citation_context=context, confidence=confidence,
            response_snippet=response_text[:2000] if response_text else None,
            query_text=keyword,
        )
    except Exception as e:
        logger.error("Failed to persist probe to RDS: %s", e)

    # Auto-save fingerprint for answer change tracking
    try:
        from answer_fingerprint import save_fingerprint
        save_fingerprint(brand_name, keyword, model_label, response_text)
    except Exception as e:
        logger.warning("Failed to save fingerprint: %s", e)

    return {
        "keyword": keyword, "brand_name": brand_name, "ai_model": model_label,
        "brand_present": cited, "citation_context": context,
        "confidence": confidence, "cited_sources": [], "timestamp": _now_iso(),
    }


# ── batch probe ───────────────────────────────────────────────────────────────

def geo_probe_batch(brand_name: str, keywords: list[str], ai_model: str = "nova") -> dict:
    """Probe multiple keywords, compute geo_score, persist batch to DB."""
    insert_visibility_batch = _get_insert_visibility_batch()

    results = []
    for kw in keywords:
        try:
            results.append(geo_probe(brand_name, kw, ai_model=ai_model))
        except Exception as e:
            results.append({
                "keyword": kw, "ai_model": ai_model, "brand_present": None,
                "citation_context": None, "confidence": 0.0,
                "cited_sources": [], "error": str(e), "timestamp": _now_iso(),
            })

    total = len(results)
    cited_count = sum(1 for r in results if r.get("brand_present") is True)
    geo_score = round(cited_count / total, 2) if total else 0.0

    batch_result = {
        "brand_name": brand_name, "ai_model": ai_model, "results": results,
        "geo_score": geo_score, "total_prompts": total,
        "cited_count": cited_count, "timestamp": _now_iso(),
    }

    try:
        insert_visibility_batch(
            brand=brand_name, ai_model=ai_model,
            keyword=", ".join(keywords), geo_score=geo_score,
            cited_count=cited_count, total_prompts=total,
            batch_results=batch_result,
        )
    except Exception as e:
        logger.error("Failed to persist batch to RDS: %s", e)

    return batch_result


# ── history (from RDS) ────────────────────────────────────────────────────────

def get_history() -> list[dict]:
    if _USE_DYNAMODB:
        from db_dynamo import get_visibility_history
    else:
        from db import get_visibility_history
    return get_visibility_history(limit=20)

def get_stored_history(limit=50, brand=None, ai_model=None) -> list[dict]:
    if _USE_DYNAMODB:
        from db_dynamo import get_probes
    else:
        from db import get_probes
    return get_probes(limit=limit, brand=brand, ai_model=ai_model)


# ── scheduled monitoring placeholder ──────────────────────────────────────────

_scheduled_jobs = []

def schedule_probe(brand_name, keywords, ai_model="nova", interval_minutes=60):
    job = {
        "id": len(_scheduled_jobs) + 1, "brand_name": brand_name,
        "keywords": keywords, "ai_model": ai_model,
        "interval_minutes": interval_minutes, "status": "registered",
        "created": _now_iso(),
        "note": "Placeholder — use EventBridge for production scheduling.",
    }
    _scheduled_jobs.append(job)
    return job

def get_scheduled_jobs():
    return list(_scheduled_jobs)


# ── multi-model comparison ────────────────────────────────────────────────────

def geo_probe_compare(brand_name: str, keyword: str) -> dict:
    """Probe the SAME keyword across ALL available providers simultaneously."""
    import concurrent.futures
    from ai_provider import get_available_providers

    providers = [p["name"] for p in get_available_providers() if p.get("available")]
    if not providers:
        providers = ["nova", "ollama"]

    results = {}

    def _probe(provider):
        try:
            return provider, geo_probe(brand_name, keyword, ai_model=provider)
        except Exception as e:
            return provider, {
                "keyword": keyword, "ai_model": provider, "brand_present": None,
                "citation_context": None, "confidence": 0.0,
                "error": str(e), "timestamp": _now_iso(),
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {pool.submit(_probe, p): p for p in providers}
        for f in concurrent.futures.as_completed(futures):
            provider, result = f.result()
            results[provider] = result

    total = len(results)
    cited_count = sum(1 for r in results.values() if r.get("brand_present") is True)
    avg_confidence = round(
        sum(r.get("confidence", 0) for r in results.values()) / total, 2
    ) if total else 0.0

    return {
        "brand_name": brand_name, "keyword": keyword,
        "providers_queried": list(results.keys()), "results": results,
        "visibility_score": round((cited_count / total) * 100) if total else 0,
        "cited_count": cited_count, "total_providers": total,
        "avg_confidence": avg_confidence, "timestamp": _now_iso(),
    }


# ── site/URL detection ────────────────────────────────────────────────────────

def geo_probe_site(site_url: str, keyword: str, ai_model: str = "nova") -> dict:
    """Detect if a website URL is mentioned in AI output."""
    from urllib.parse import urlparse
    from ai_provider import generate
    insert_probe = _get_insert_probe()

    domain = urlparse(site_url).netloc or site_url
    domain_clean = domain.replace("www.", "")

    prompt = (
        f'A user asks: "{keyword}"\n\n'
        f"Provide a comprehensive answer with specific website recommendations, "
        f"tools, and resources. Include URLs where relevant."
    )

    try:
        text = generate(prompt, provider=ai_model)
    except Exception as e:
        return {
            "site_url": site_url, "keyword": keyword, "ai_model": ai_model,
            "site_mentioned": None, "error": str(e), "timestamp": _now_iso(),
        }

    pattern = re.compile(re.escape(domain_clean), re.IGNORECASE)
    mentioned = bool(pattern.search(text))
    context = None
    if mentioned:
        for s in re.split(r'(?<=[.!?])\s+|\n+', text):
            if pattern.search(s):
                context = s.strip()
                break

    model_label = f"ollama/{OLLAMA_MODEL}" if ai_model == "ollama" else ai_model
    try:
        insert_probe(
            keyword=keyword, brand=domain_clean, ai_model=model_label,
            cited=mentioned, citation_context=context,
            confidence=1.0 if mentioned else 0.0,
            site_url=site_url, response_snippet=text[:2000], query_text=prompt,
        )
    except Exception as e:
        logger.error("Failed to persist site probe: %s", e)

    return {
        "site_url": site_url, "domain": domain_clean, "keyword": keyword,
        "ai_model": model_label, "site_mentioned": mentioned,
        "mention_context": context, "timestamp": _now_iso(),
    }


# ── visibility trend ─────────────────────────────────────────────────────────

def get_visibility_trend(brand: str, limit: int = 30) -> dict:
    if _USE_DYNAMODB:
        from db_dynamo import get_probe_trend
    else:
        from db import get_probe_trend
    try:
        trend = get_probe_trend(brand, limit=limit)
        return {"brand": brand, "trend": trend,
                "total_probes": sum(t.get("total", 0) for t in trend)}
    except Exception as e:
        logger.error("Failed to get visibility trend: %s", e)
        return {"brand": brand, "trend": [], "error": str(e)}
