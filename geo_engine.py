#!/usr/bin/env python3
"""
geo_engine.py — EC2 AI Engine for GEO Probe

Standalone Flask service on EC2 with Bedrock access (IAM role).
Set USE_BEDROCK=1 to call Claude, otherwise returns stub response.

Run:   python3 geo_engine.py
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


# ── Bedrock ───────────────────────────────────────────────────────────────────

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


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(keyword, brand_name):
    """
    Prompt that encourages natural brand mentions without forcing them.
    Asks Claude to list top brands and include the target brand if applicable.
    """
    return (
        f"You are a knowledgeable product reviewer. A user wants to know:\n\n"
        f"\"What are the best {keyword}?\"\n\n"
        f"List the top brands and products for this category. "
        f"Include {brand_name} in your answer if it is a relevant and reputable option. "
        f"For each brand, briefly explain why it stands out. "
        f"Be honest — only mention brands that genuinely fit."
    )


# ── Citation detection ────────────────────────────────────────────────────────

# Recommendation signals (brand is clearly endorsed)
_RECOMMEND_PATTERNS = [
    r"(?:top|best|leading|excellent|outstanding|highly\s+rated|popular|go-to|premier)",
    r"(?:recommend|stands?\s+out|known\s+for|excels?|dominates?|renowned)",
    r"(?:#\d|number\s+\d|first\s+choice|top\s+pick|editor.?s?\s+choice)",
]

# Comparison signals (brand mentioned alongside others)
_COMPARE_PATTERNS = [
    r"(?:compared?\s+to|alternative|competitor|similar\s+to|versus|vs\.?|alongside)",
    r"(?:however|although|while|on\s+the\s+other\s+hand|but)",
    r"(?:also\s+worth|another\s+option|consider)",
]


def _split_sentences(text):
    """Split text into sentences, handling lists and line breaks."""
    # Normalize bullet/numbered list items into separate sentences
    text = re.sub(r'\n\s*[-*•]\s*', '\n', text)
    text = re.sub(r'\n\s*\d+[.)]\s*', '\n', text)
    parts = re.split(r'(?<=[.!?])\s+|\n{1,}', text)
    return [s.strip() for s in parts if s.strip()]


def _find_brand_sentences(text, brand):
    """Return all sentences that mention the brand (case-insensitive, partial match)."""
    sentences = _split_sentences(text)
    # Match brand as a word boundary: "Nike" matches "Nike shoes", "Nike running"
    pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
    return [s for s in sentences if pattern.search(s)]


def _score_confidence(brand_sentences):
    """
    Score confidence based on how the brand is mentioned.
    1.0 = clearly recommended / top pick
    0.5 = mentioned in comparison or neutral context
    0.0 = not found
    """
    if not brand_sentences:
        return 0.0

    combined = " ".join(brand_sentences).lower()

    # Check for strong recommendation signals
    for pat in _RECOMMEND_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            return 1.0

    # Check for comparison/neutral signals
    for pat in _COMPARE_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            return 0.5

    # Brand is mentioned but no strong signal either way
    return 0.5


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/geo-probe", methods=["POST"])
def geo_probe():
    data = request.get_json(silent=True) or {}
    brand_name = (data.get("brand_name") or "").strip()
    keyword = (data.get("keyword") or "").strip()

    if not brand_name or not keyword:
        return jsonify({"error": "brand_name and keyword are required"}), 400

    logger.info("GEO probe START: brand=%s keyword=%s bedrock=%s", brand_name, keyword, USE_BEDROCK)

    if USE_BEDROCK:
        prompt = _build_prompt(keyword, brand_name)
        try:
            response_text = _invoke_claude(prompt)
        except Exception as e:
            logger.error("Bedrock failed: %s", e)
            return jsonify({"error": f"Bedrock invocation failed: {e}"}), 503

        logger.info("RAW CLAUDE RESPONSE (%d chars):\n%s", len(response_text), response_text[:1500])

        if not response_text or not response_text.strip():
            return jsonify({"error": "Empty response from Claude"}), 503

        # Find all sentences mentioning the brand
        brand_sentences = _find_brand_sentences(response_text, brand_name)
        cited = len(brand_sentences) > 0
        context = brand_sentences[0] if brand_sentences else None
        confidence = _score_confidence(brand_sentences)
        source = "bedrock"

        logger.info(
            "DETECTION: brand=%s cited=%s confidence=%.1f mentions=%d context=%s",
            brand_name, cited, confidence, len(brand_sentences),
            context[:100] if context else "null",
        )
    else:
        cited = False
        context = None
        confidence = 0.0
        source = "stub"
        logger.info("STUB MODE — returning mock response")

    return jsonify({
        "keyword": keyword,
        "brand_name": brand_name,
        "ai_model": "claude",
        "cited": cited,
        "citation_context": context,
        "timestamp": _now(),
        "confidence": confidence,
        "source": source,
    })


@app.route("/generate", methods=["POST"])
def generate():
    """General-purpose text generation via Bedrock Claude."""
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    if not USE_BEDROCK:
        return jsonify({"text": "[stub] Bedrock not enabled", "source": "stub"})

    try:
        text = _invoke_claude(prompt)
        return jsonify({"text": text, "source": "bedrock"})
    except Exception as e:
        logger.error("Generate failed: %s", e)
        return jsonify({"error": f"Generation failed: {e}"}), 503


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "geo-engine", "bedrock": USE_BEDROCK})


if __name__ == "__main__":
    logger.info("Starting geo_engine on port 5005 (bedrock=%s)", USE_BEDROCK)
    app.run(host="0.0.0.0", port=5005, debug=False)
