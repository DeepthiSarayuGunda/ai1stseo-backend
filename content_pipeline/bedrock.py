"""
Bedrock LLM clients for the content pipeline.
Uses Nova for all content generation (articles, summaries, social).
Claude/Haiku will be added in 3rd week of May for quality comparison.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))
NOVA_MODEL = os.environ.get("NOVA_MODEL", "us.amazon.nova-lite-v1:0")
NOVA_PRO_MODEL = os.environ.get("NOVA_PRO_MODEL", "amazon.nova-pro-v1:0")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
        logger.info("Bedrock client initialized (region=%s)", REGION)
    return _client


def generate_with_nova(prompt: str, max_tokens: int = 4096) -> str:
    """Generate long-form content using Amazon Nova Pro."""
    client = _get_client()
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.7},
    })
    resp = client.invoke_model(
        modelId=NOVA_PRO_MODEL,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(resp["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def generate_with_haiku(prompt: str, max_tokens: int = 1024) -> str:
    """Generate summaries and social content using Nova Lite (Haiku replacement until May week 3)."""
    client = _get_client()
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.7},
    })
    resp = client.invoke_model(
        modelId=NOVA_MODEL,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(resp["body"].read())
    return result["output"]["message"]["content"][0]["text"]
