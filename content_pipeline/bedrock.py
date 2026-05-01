"""
Bedrock LLM clients for the content pipeline.
Uses Nova for long-form articles and Haiku for summaries/social content.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))
NOVA_MODEL = os.environ.get("NOVA_MODEL", "us.amazon.nova-lite-v1:0")
HAIKU_MODEL = os.environ.get("HAIKU_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
        logger.info("Bedrock client initialized (region=%s)", REGION)
    return _client


def generate_with_nova(prompt: str, max_tokens: int = 4096) -> str:
    """Generate long-form content using Amazon Nova."""
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


def generate_with_haiku(prompt: str, max_tokens: int = 1024) -> str:
    """Generate summaries and social content using Claude Haiku."""
    client = _get_client()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    })
    resp = client.invoke_model(
        modelId=HAIKU_MODEL,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(resp["body"].read())
    return result["content"][0]["text"]
