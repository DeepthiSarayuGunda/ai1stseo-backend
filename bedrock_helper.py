"""
bedrock_helper.py
Thin wrapper around AWS Bedrock Runtime for Claude invocations.
Uses IAM role credentials (no API keys required).

On EC2, credentials come from the instance profile / IAM role automatically.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
DEFAULT_REGION = "us-east-1"

_client = None


def get_client():
    """Return a cached Bedrock Runtime client using IAM credentials."""
    global _client
    if _client is None:
        region = os.environ.get("AWS_REGION", DEFAULT_REGION)
        _client = boto3.client("bedrock-runtime", region_name=region)
        logger.info("Bedrock runtime client created (region=%s)", region)
    return _client


def invoke_claude(
    prompt: str,
    max_tokens: int = 1024,
    model_id: str = DEFAULT_MODEL,
) -> str:
    """
    Send a prompt to Claude via AWS Bedrock and return the raw text response.

    Uses the Messages API format required by Bedrock's Anthropic models.

    Raises:
        RuntimeError: if the Bedrock call fails.
    """
    client = get_client()

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    })

    logger.info("Invoking Bedrock model=%s max_tokens=%d", model_id, max_tokens)

    try:
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        text = result["content"][0]["text"]
        logger.info("Bedrock response received (%d chars)", len(text))
        return text
    except client.exceptions.AccessDeniedException as e:
        raise RuntimeError(
            f"Bedrock access denied — check IAM role permissions for {model_id}: {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Bedrock invocation failed: {e}") from e
