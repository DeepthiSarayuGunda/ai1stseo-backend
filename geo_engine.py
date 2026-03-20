#!/usr/bin/env python3
"""
geo_engine.py — EC2 AI Engine for GEO Probe (Multi-Provider)

Standalone Flask service on EC2 with Bedrock access (IAM role).
Supports: Claude (Bedrock), OpenAI, Gemini, Perplexity.

Run:   USE_BEDROCK=1 python3 geo_engine.py
Port:  5005
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/geo_engine.log"),
    ],
)
logger = logging.getLogger("geo_engine")

USE_BEDROCK = os.environ.get("USE_BEDROCK", "0") == "1"


# ── Provider clients ──────────────────────────────────────────────────────────

_bedrock_client = None


def _get_bedrock():
    global _bedrock_client
    if _bedrock_client is None:
        import boto3
        region = os.environ.get("AWS_REGION", "us-east-1")
        _bedrock_client = boto3.client("bedrock-runtime", region_name=region)
        logger.info("Bedrock client initialized (region=%s)", region)
    return _bedrock_client


def _invoke_claude(prompt):
    client = _get_bedrock()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    })
    resp = client.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(resp["body"].read())
    return result["content"][0]["text"]


def _invoke_openai(prompt):
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not set on EC2")
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return resp.choices[0].message.content


def _invoke_gemini(prompt):
    import google.generativeai as genai
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY not set on EC2")
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(prompt)
    return resp.text


def _invoke_perplexity(prompt):
    from openai import OpenAI
    key = os.environ.get("PERPLEXITY_API_KEY")
    if not key:
        raise ValueError("PERPLEXITY_API_KEY not set on EC2")
    client = OpenAI(api_key=key, base_url="https://api.perplexity.ai")
    resp = client.chat.completions.create(
        model="llama-3.1-sonar-small-128k-online",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return resp.choices[0].message.content


# Provider registry: name → (invoke_fn, requires_env, requires_bedrock)
PROVIDER_REGISTRY = {
    "claude":     {"fn": _invoke_claude,     "env": None,              "needs_bedrock": True},
    "openai":     {"fn": _invoke_openai,     "env": "OPENAI_API_KEY",  "needs_bedrock": False},
    "gemini":     {"fn": _invoke_gemini,     "env": "GEMINI_API_KEY",  "needs_bedrock": False},
    "perplexity": {"fn": _invoke_perplexity, "env": "PERPLEXITY_API_KEY", "needs_bedrock": False},
}


def _get_available_providers():
    """Return list of providers that are currently usable."""
    available = []
    for name, cfg in PROVIDER_REGISTRY.items():
        if cfg["needs_bedrock"] and not USE_BEDROCK:
            continue
        if cfg["env"] and not os.environ.get(cfg["env"]):
            continue
        available.append(name)
    return available


def _invoke_provider(provider, prompt):
    """Invoke the specified provider. Raises ValueError/RuntimeError on failure."""
    cfg = PROVIDER_REGISTRY.get(provider)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDER_REGISTRY.keys())}")
    if cfg["needs_bedrock"] and not USE_BEDROCK:
        raise RuntimeError(f"Provider '{provider}' requires USE_BEDROCK=1")
    if cfg["env"] and not os.environ.get(cfg["env"]):
        raise RuntimeError(f"Provider '{provider}' requires {cfg['env']} env var")
    return cfg["fn"](prompt)


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(keyword, brand_name):
    return (
        f"You are a knowledgeable product reviewer. A user wants to know:\n\n"
        f"\"What are the best {keyword}?\"\n\n"
        f"List the top brands and products for this category. "
        f"If {brand_name} is a genuinely well-known brand in this category, "
        f"include it and explain why it stands out. "
        f"If {brand_name} is NOT a real, established brand in this space, "
        f"do not mention it at all — do not invent or fabricate information about it. "
        f"For each brand, briefly explain why it stands out."
    )


# ── Citation detection ────────────────────────────────────────────────────────

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


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _detect_citation(response_text, brand_name, provider):
    """Shared citation detection logic for all providers."""
    brand_sentences = _find_brand_sentences(response_text, brand_name)
    cited = len(brand_sentences) > 0
    context = brand_sentences[0] if brand_sentences else None
    confidence = _score_confidence(brand_sentences)

    if cited and _is_conditional_mention(brand_sentences):
        logger.info("REJECTED: conditional mention for brand=%s provider=%s", brand_name, provider)
        cited = False
        confidence = 0.0
        context = None

    if cited and context and brand_name.lower() not in context.lower():
        logger.info("REJECTED: brand not in context for brand=%s provider=%s", brand_name, provider)
        cited = False
        confidence = 0.0
        context = None

    return cited, context, confidence


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/geo-probe", methods=["POST"])
def geo_probe():
    data = request.get_json(silent=True) or {}
    brand_name = (data.get("brand_name") or "").strip()
    keyword = (data.get("keyword") or "").strip()
    provider = (data.get("provider") or data.get("ai_model") or "claude").strip().lower()

    if not brand_name or not keyword:
        return jsonify({"error": "brand_name and keyword are required"}), 400

    if provider not in PROVIDER_REGISTRY:
        return jsonify({"error": f"Unknown provider: {provider}. Available: {list(PROVIDER_REGISTRY.keys())}"}), 400

    logger.info("GEO probe START: brand=%s keyword=%s provider=%s", brand_name, keyword, provider)

    prompt = _build_prompt(keyword, brand_name)
    try:
        response_text = _invoke_provider(provider, prompt)
    except Exception as e:
        logger.error("Provider %s failed: %s", provider, e)
        return jsonify({"error": f"{provider} invocation failed: {e}"}), 503

    logger.info("RAW %s RESPONSE (%d chars):\n%s", provider.upper(), len(response_text), response_text[:1500])

    if not response_text or not response_text.strip():
        return jsonify({"error": f"Empty response from {provider}"}), 503

    cited, context, confidence = _detect_citation(response_text, brand_name, provider)

    logger.info(
        "DETECTION: brand=%s provider=%s cited=%s confidence=%.1f context=%s",
        brand_name, provider, cited, confidence,
        context[:100] if context else "null",
    )

    return jsonify({
        "keyword": keyword,
        "brand_name": brand_name,
        "ai_model": provider,
        "cited": cited,
        "citation_context": context,
        "timestamp": _now(),
        "confidence": confidence,
        "source": provider,
    })


@app.route("/geo-probe/providers", methods=["GET"])
def geo_probe_providers():
    """List available providers on this EC2 engine."""
    providers = []
    for name, cfg in PROVIDER_REGISTRY.items():
        available = True
        reason = "ready"
        if cfg["needs_bedrock"] and not USE_BEDROCK:
            available = False
            reason = "USE_BEDROCK=1 not set"
        elif cfg["env"] and not os.environ.get(cfg["env"]):
            available = False
            reason = f"{cfg['env']} not set"
        providers.append({"name": name, "available": available, "reason": reason})
    return jsonify({"providers": providers})


@app.route("/generate", methods=["POST"])
def generate():
    """General-purpose text generation via any provider."""
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    provider = (data.get("provider") or "claude").strip().lower()

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    try:
        text = _invoke_provider(provider, prompt)
        return jsonify({"text": text, "source": provider})
    except Exception as e:
        logger.error("Generate failed (%s): %s", provider, e)
        return jsonify({"error": f"Generation failed ({provider}): {e}"}), 503


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "geo-engine",
        "bedrock": USE_BEDROCK,
        "available_providers": _get_available_providers(),
    })


if __name__ == "__main__":
    logger.info("Starting geo_engine on port 5005 (bedrock=%s, providers=%s)",
                USE_BEDROCK, _get_available_providers())
    app.run(host="0.0.0.0", port=5005, debug=False)
