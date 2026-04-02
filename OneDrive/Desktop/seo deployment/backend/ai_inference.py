"""
AI Inference Module — Dual-path: Nova Lite (primary) + Ollama (fallback)
Used by all services that need LLM inference.
Logs usage to ai_usage_log table for cost tracking.
"""
import json
import os
import time
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://ollama.sageaios.com")
NOVA_MODEL = os.environ.get("NOVA_MODEL", "amazon.nova-lite-v1:0")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:30b-a3b")

# Nova Lite pricing (us-east-1, per token)
NOVA_INPUT_COST = 0.00000006   # $0.06 per 1M input tokens
NOVA_OUTPUT_COST = 0.00000024  # $0.24 per 1M output tokens


def generate(prompt, max_tokens=4096, temperature=0.7, triggered_by='scan'):
    """
    Primary: Nova Lite via Bedrock.
    Fallback: Gurbachan's homelab Ollama (ollama.sageaios.com).
    Returns the generated text string.
    """
    # Try Nova Lite first
    text = _try_nova_lite(prompt, max_tokens, temperature, triggered_by)
    if text:
        return text

    # Fallback: Ollama
    text = _try_ollama(prompt, max_tokens, temperature, triggered_by)
    if text:
        return text

    return "AI inference unavailable. Both Nova Lite and Ollama endpoints failed."


def _try_nova_lite(prompt, max_tokens, temperature, triggered_by='scan'):
    """Invoke Amazon Nova Lite via Bedrock using the Messages API."""
    start = time.time()
    try:
        import boto3
        bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxNewTokens": max_tokens, "temperature": temperature},
        })
        response = bedrock.invoke_model(modelId=NOVA_MODEL, body=body)
        result = json.loads(response["body"].read())
        text = result["output"]["message"]["content"][0]["text"]
        latency = int((time.time() - start) * 1000)
        # Estimate tokens (~4 chars per token)
        input_tokens = len(prompt) // 4
        output_tokens = len(text) // 4
        cost = (input_tokens * NOVA_INPUT_COST) + (output_tokens * NOVA_OUTPUT_COST)
        _log_ai_usage('nova_lite', NOVA_MODEL, input_tokens, output_tokens, cost, True, latency, triggered_by)
        return text
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        _log_ai_usage('nova_lite', NOVA_MODEL, len(prompt) // 4, 0, 0, False, latency, triggered_by)
        print("Nova Lite failed: {}".format(e))
        return None


def _try_ollama(prompt, max_tokens, temperature, triggered_by='scan'):
    """Call Gurbachan's homelab Ollama server."""
    start = time.time()
    try:
        resp = requests.post(
            "{}/api/generate".format(OLLAMA_URL),
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
            timeout=180,
        )
        if resp.status_code == 200:
            text = resp.json().get("response", "")
            latency = int((time.time() - start) * 1000)
            _log_ai_usage('ollama_sageaios', OLLAMA_MODEL, len(prompt) // 4, len(text) // 4, 0, True, latency, triggered_by)
            return text
    except Exception as e:
        print("Ollama failed: {}".format(e))
    latency = int((time.time() - start) * 1000)
    _log_ai_usage('ollama_sageaios', OLLAMA_MODEL, len(prompt) // 4, 0, 0, False, latency, triggered_by)
    return None


def _log_ai_usage(provider, model, input_tokens, output_tokens, cost, success, latency_ms, triggered_by):
    """Log AI call to ai_usage_log table. Fails silently to not break inference."""
    try:
        from database import execute
        execute(
            "INSERT INTO ai_usage_log (provider, model, input_tokens_est, output_tokens_est, "
            "estimated_cost_usd, success, latency_ms, triggered_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (provider, model, input_tokens, output_tokens, cost, success, latency_ms, triggered_by),
        )
    except Exception as e:
        print("AI usage log failed (non-fatal): {}".format(e))
