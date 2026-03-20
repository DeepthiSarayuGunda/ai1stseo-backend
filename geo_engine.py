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


# ── Citation detection ────────────────────────────────────────────────────────

def _extract_citation_context(text, brand):
    """
    Find the sentence(s) containing the brand name.
    Returns the first matching sentence, or None.
    """
    # Split into sentences (handles numbered lists, bullet points, etc.)
    sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
    pattern = re.compile(re.escape(brand), re.IGNORECASE)

    for sentence in sentences:
        if pattern.search(sentence):
            clean = sentence.strip().strip("-*• 0123456789.")
            if clean:
                return clean

    return None


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
        prompt = (
            f"You are a helpful assistant. A user is researching the following topic.\n\n"
            f"User query: What are the best tools for {keyword}?\n\n"
            f"Provide a thorough, natural answer. Mention specific brands, tools, "
            f"and products where relevant."
        )
        try:
            response_text = _invoke_claude(prompt)
        except Exception as e:
            logger.error("Bedrock failed: %s", e)
            return jsonify({"error": f"Bedrock invocation failed: {e}"}), 503

        # Log raw response so we can verify it's real model output
        logger.info("RAW CLAUDE RESPONSE (%d chars):\n%s", len(response_text), response_text[:1000])

        if not response_text or not response_text.strip():
            return jsonify({"error": "Empty response from Claude"}), 503

        cited = bool(re.search(re.escape(brand_name), response_text, re.IGNORECASE))
        context = _extract_citation_context(response_text, brand_name) if cited else None
        confidence = 1.0 if cited else 0.0
        source = "bedrock"

        logger.info("DETECTION: brand=%s cited=%s confidence=%.1f context=%s",
                     brand_name, cited, confidence, context[:80] if context else "null")
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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "geo-engine", "bedrock": USE_BEDROCK})


if __name__ == "__main__":
    logger.info("Starting geo_engine on port 5005 (bedrock=%s)", USE_BEDROCK)
    app.run(host="0.0.0.0", port=5005, debug=False)
