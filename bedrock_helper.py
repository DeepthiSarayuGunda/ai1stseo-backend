"""
bedrock_helper.py
Thin wrapper around AWS Bedrock Runtime.

Supports multiple model families via two paths:
  - invoke_llm(): legacy per-family body formats (Nova, Anthropic)
  - invoke_model(): uses the Converse API (uniform across ALL Bedrock models:
                    Nova, Anthropic, Meta Llama, Mistral, Cohere, etc.)

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

# Per-agent model registry — used by the council and any multi-model feature.
# Inference profile IDs (us.* prefix) route via geo inference for better availability.
MODEL_REGISTRY = {
    # Nova family — Amazon, cheap & fast
    "nova-lite": "amazon.nova-lite-v1:0",
    "nova-pro": "amazon.nova-pro-v1:0",
    "nova-premier": "us.amazon.nova-premier-v1:0",
    # Anthropic — reasoning & attribution
    "claude-haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "claude-sonnet-4": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    # Meta Llama — content quality, large context
    "llama-3-70b": "us.meta.llama3-3-70b-instruct-v1:0",
    "llama-4-maverick": "us.meta.llama4-maverick-17b-instruct-v1:0",
    # Mistral — structured analysis, competitor intel
    "mistral-large": "mistral.mistral-large-2407-v1:0",
    "mistral-large-3": "mistral.mistral-large-3-675b-instruct",
    # DeepSeek — budget reasoning alternative
    "deepseek-v3": "us.deepseek.v3-v1:0",
}

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


def resolve_model(name_or_id: str) -> str:
    """Accept a short alias (e.g. 'claude-haiku') or a full Bedrock model ID."""
    return MODEL_REGISTRY.get(name_or_id, name_or_id)


def invoke_converse(
    prompt: str,
    model: str = "nova-lite",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    system: str = None,
) -> str:
    """
    Invoke any Bedrock model via the unified Converse API.

    Works across Nova, Anthropic, Meta Llama, Mistral, Cohere, DeepSeek —
    single call signature, single response shape.

    Args:
        prompt: the user prompt text
        model: alias from MODEL_REGISTRY or full Bedrock model ID
        max_tokens: max output tokens
        temperature: sampling temperature
        system: optional system prompt (not supported by every model; skipped if so)

    Returns:
        response text

    Raises:
        RuntimeError on Bedrock failure.
    """
    client = get_client()
    model_id = resolve_model(model)

    messages = [{"role": "user", "content": [{"text": prompt}]}]
    kwargs = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        kwargs["system"] = [{"text": system}]

    logger.info("Bedrock converse: model=%s max_tokens=%d", model_id, max_tokens)

    try:
        response = client.converse(**kwargs)
        text = response["output"]["message"]["content"][0]["text"]
        logger.info("Bedrock response (%d chars)", len(text))
        return text
    except client.exceptions.AccessDeniedException as e:
        raise RuntimeError(
            f"Bedrock access denied for {model_id} — enable model access in Bedrock console: {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Bedrock converse failed for {model_id}: {e}") from e


def invoke_llm(
    prompt: str,
    max_tokens: int = 2048,
    model_id: str = DEFAULT_MODEL,
) -> str:
    """
    Legacy invoke_model path — kept for backward compatibility.

    Supports Nova and Anthropic via per-family body formats.
    New code should prefer invoke_converse() for uniform multi-model support.
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
