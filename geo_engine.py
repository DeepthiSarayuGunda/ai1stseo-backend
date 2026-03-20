#!/usr/bin/env python3
"""
geo_engine.py — EC2 AI Engine for GEO Probe

Standalone Flask service that runs on EC2.
Phase 1: stub response to verify endpoint works.
Phase 2: Bedrock integration (already wired, set USE_BEDROCK=1 to enable).

Run:   python3 geo_engine.py
Port:  5005
Test:  curl -X POST http://localhost:5005/geo-probe \
         -H "Content-Type: application/json" \
         -d '{"brand_name":"nike","keyword":"running shoes"}'
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
)
logger = logging.getLogger("geo_engine")

USE_BEDROCK = os.environ.get("USE_BEDROCK", "0") == "1"


# ── Bedrock (only loaded when enabled) ───────────────────────────────────────

def _invoke_claude(prompt):
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_context(text, brand, window=150):
    match = re.search(re.escape(brand), text, re.IGNORECASE)
    if not match:
        return None
    s = max(0, match.start() - window)
    e = min(len(text), match.end() + window)
    snippet = text[s:e].strip()
    fd = snippet.find(". ")
    ld = snippet.rfind(".")
    if fd != -1 and s > 0:
        snippet = snippet[fd + 2:]
    if ld != -1 and ld > 0 and e < len(text):
        snippet = snippet[:ld + 1]
    return snippet or None


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

    logger.info("GEO probe: brand=%s keyword=%s bedrock=%s", brand_name, keyword, USE_BEDROCK)

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

        cited = bool(re.search(re.escape(brand_name), response_text, re.IGNORECASE))
        context = _extract_context(response_text, brand_name) if cited else None
        confidence = 1.0 if cited else 0.0
    else:
        # Stub mode — always returns a valid response for endpoint testing
        cited = False
        context = None
        confidence = 0.0
        logger.info("Stub mode — returning mock response")

    return jsonify({
        "keyword": keyword,
        "brand_name": brand_name,
        "ai_model": "claude",
        "cited": cited,
        "citation_context": context,
        "timestamp": _now(),
        "confidence": confidence,
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "geo-engine", "bedrock": USE_BEDROCK})


if __name__ == "__main__":
    logger.info("Starting geo_engine on port 5005 (bedrock=%s)", USE_BEDROCK)
    app.run(host="0.0.0.0", port=5005, debug=False)
