"""
bedrock_helper.py
Thin wrapper around AWS Bedrock Runtime for Claude invocations.

Authentication priority:
  1. Explicit env vars: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (+ optional AWS_SESSION_TOKEN)
  2. Default boto3 credential chain (IAM role, instance profile, SSO, etc.)
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "amazon.nova-lite-v1:0"
DEFAULT_REGION = "us-east-1"

_client = None


def get_client():
    """Return a cached Bedrock Runtime client."""
    global _client
    if _client is None:
        region = os.environ.get("AWS_REGION", DEFAULT_REGION)
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

        if access_key and secret_key:
            session_token = os.environ.get("AWS_SESSION_TOKEN")
            _client = boto3.client(
                "bedrock-runtime",
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
            )
            logger.info("Bedrock client created with explicit credentials (region=%s)", region)
        else:
            _client = boto3.client("bedrock-runtime", region_name=region)
            logger.info("Bedrock client created with default credential chain (region=%s)", region)
    return _client


def invoke_llm(
    prompt: str,
    max_tokens: int = 2048,
    model_id: str = DEFAULT_MODEL,
) -> str:
    """
    Send a prompt to an LLM via AWS Bedrock and return the raw text response.

    Supports both Nova and Anthropic model families.

    Raises:
        RuntimeError: if the Bedrock call fails.
    """
    client = get_client()

    if model_id.startswith("amazon.nova"):
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"max_new_tokens": max_tokens}
        })
    else:
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

        if model_id.startswith("amazon.nova"):
            text = result["output"]["message"]["content"][0]["text"]
        else:
            text = result["content"][0]["text"]

        logger.info("Bedrock response received (%d chars)", len(text))
        return text
    except client.exceptions.AccessDeniedException as e:
        raise RuntimeError(
            f"Bedrock access denied — check IAM role permissions for {model_id}: {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Bedrock invocation failed: {e}") from e


# Keep backward compatibility
def invoke_claude(prompt: str, max_tokens: int = 1024, model_id: str = DEFAULT_MODEL) -> str:
    return invoke_llm(prompt, max_tokens, model_id)
