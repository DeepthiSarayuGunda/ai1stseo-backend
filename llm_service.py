"""
LLM Service - modular abstraction for multi-provider AI queries
Supports: Claude (Anthropic), OpenAI GPT, Perplexity
"""

import os
import re
import concurrent.futures
from datetime import datetime


def _anthropic_client():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=key)


def _openai_client():
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key)


def _perplexity_client():
    from openai import OpenAI
    key = os.environ.get("PERPLEXITY_API_KEY")
    if not key:
        raise ValueError("PERPLEXITY_API_KEY not set")
    return OpenAI(api_key=key, base_url="https://api.perplexity.ai")


def _extract_brands(text):
    tokens = re.findall(r'\b[A-Z][a-zA-Z0-9]*(?:\s[A-Z][a-zA-Z0-9]+)*\b', text)
    stopwords = {"The","A","An","In","On","At","For","To","Of","And","Or","But","Is","Are",
                 "Was","Were","Be","Been","Being","Have","Has","Had","Do","Does","Did",
                 "Will","Would","Could","Should","May","Might","Must","Shall","Can",
                 "I","You","He","She","It","We","They","This","That","These","Those",
                 "Here","There","When","Where","Why","How","What","Which","Who","Whom"}
    seen = set()
    brands = []
    for t in tokens:
        if t not in stopwords and t not in seen and len(t) > 2:
            seen.add(t)
            brands.append(t)
    return brands[:20]


def _extract_citations(text):
    urls = re.findall(r'https?://[^\s\)\"\']+', text)
    source_refs = re.findall(r'(?:Source|Reference|Cited|According to)[:\s]+([^\n\.]+)', text, re.I)
    return list(set(urls + source_refs))[:10]


def _detect_structure(text):
    if re.search(r'^\s*[-*\u2022]\s', text, re.M):
        return "bullet_list"
    if re.search(r'^\s*\d+\.\s', text, re.M):
        return "numbered_list"
    if re.search(r'\|.*\|', text):
        return "table"
    if re.search(r'^#{1,3}\s', text, re.M):
        return "sections"
    if text.count('?') >= 2:
        return "faq"
    return "paragraph"


def _extract_facts(text):
    return re.findall(r'[^.]*\b\d[\d,\.%]*\b[^.]*\.', text)[:5]


def _query_claude(keyword, model="claude-3-haiku-20240307"):
    client = _anthropic_client()
    prompt = (
        f"You are an AI assistant. Answer this query comprehensively: '{keyword}'\n\n"
        "Include relevant brands, tools, statistics, and cite sources where possible."
    )
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def _query_openai(keyword, model="gpt-4o-mini"):
    client = _openai_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Answer comprehensively. Include brands, tools, stats, and cite sources."},
            {"role": "user", "content": keyword}
        ],
        max_tokens=1024
    )
    return resp.choices[0].message.content


def _query_perplexity(keyword, model="llama-3.1-sonar-small-128k-online"):
    client = _perplexity_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Answer comprehensively. Include brands, tools, stats, and cite sources."},
            {"role": "user", "content": keyword}
        ],
        max_tokens=1024
    )
    return resp.choices[0].message.content


PROVIDERS = {
    "claude":     {"fn": _query_claude,     "env": "ANTHROPIC_API_KEY",  "default_model": "claude-3-haiku-20240307"},
    "openai":     {"fn": _query_openai,     "env": "OPENAI_API_KEY",     "default_model": "gpt-4o-mini"},
    "perplexity": {"fn": _query_perplexity, "env": "PERPLEXITY_API_KEY", "default_model": "llama-3.1-sonar-small-128k-online"},
}


def _available_providers():
    return [name for name, cfg in PROVIDERS.items() if os.environ.get(cfg["env"])]


def citation_probe(keyword, provider="claude", model=None):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider}")
    used_model = model or cfg["default_model"]
    text = cfg["fn"](keyword, used_model)
    return {
        "keyword": keyword,
        "provider": provider,
        "model": used_model,
        "citations": _extract_citations(text),
        "mentioned_brands": _extract_brands(text),
        "answer_structure": _detect_structure(text),
        "key_facts": _extract_facts(text),
        "ai_summary": text[:500]
    }


def geo_monitor(keyword, brand=None, providers=None):
    available = _available_providers()
    if providers:
        available = [p for p in providers if p in available]
    if not available:
        raise RuntimeError("No LLM providers configured - set at least one API key env var")

    results = {}

    def _run(provider):
        try:
            cfg = PROVIDERS[provider]
            text = cfg["fn"](keyword)
            return provider, {
                "status": "success",
                "model": cfg["default_model"],
                "citations": _extract_citations(text),
                "mentioned_brands": _extract_brands(text),
                "answer_structure": _detect_structure(text),
                "key_facts": _extract_facts(text),
                "ai_summary": text[:500]
            }
        except Exception as e:
            return provider, {"status": "error", "error": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(available)) as pool:
        futures = {pool.submit(_run, p): p for p in available}
        for future in concurrent.futures.as_completed(futures):
            provider, result = future.result()
            results[provider] = result

    geo_score = _compute_geo_score(results, brand)

    return {
        "keyword": keyword,
        "brand": brand,
        "models": results,
        "geo_score": geo_score,
        "providers_queried": available,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def _compute_geo_score(model_results, brand=None):
    successful = [r for r in model_results.values() if r.get("status") == "success"]
    if not successful:
        return 0

    total_models = len(successful)

    all_brands = []
    for r in successful:
        all_brands.extend(r.get("mentioned_brands", []))

    if brand:
        brand_hits = sum(1 for b in all_brands if brand.lower() in b.lower())
        brand_score = min(40, brand_hits * 10)
    else:
        brand_score = min(40, len(set(all_brands)) * 2)

    models_with_citations = sum(1 for r in successful if r.get("citations"))
    citation_score = round((models_with_citations / total_models) * 40)

    max_providers = len(PROVIDERS)
    coverage_score = round((total_models / max_providers) * 20)

    return min(100, brand_score + citation_score + coverage_score)
