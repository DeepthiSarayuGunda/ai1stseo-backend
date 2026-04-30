"""
AI Inference Module — Dual-path: Nova Lite (primary) + Ollama (fallback)
Used by all services that need LLM inference.
Logs usage to ai_usage_log table for cost tracking.
Includes DynamoDB response cache with 24h TTL to reduce duplicate calls.
"""
import json
import os
import time
import hashlib
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://ollama.sageaios.com")
NOVA_MODEL = os.environ.get("NOVA_MODEL", "amazon.nova-lite-v1:0")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:30b-a3b")

# Nova Lite pricing (us-east-1, per token)
NOVA_INPUT_COST = 0.00000006   # $0.06 per 1M input tokens
NOVA_OUTPUT_COST = 0.00000024  # $0.24 per 1M output tokens

# Response cache TTL (seconds)
_CACHE_TTL = 86400  # 24 hours


def _cache_key(prompt, max_tokens, temperature):
    """Generate a deterministic cache key from prompt parameters."""
    raw = '{}|{}|{}'.format(prompt.strip()[:500], max_tokens, temperature)
    return 'cache_' + hashlib.md5(raw.encode()).hexdigest()[:20]


def _get_cached(key):
    """Check DynamoDB for a cached response. Returns text or None."""
    try:
        from dynamodb_helper import get_item
        item = get_item('ai1stseo-api-logs', {'id': key})
        if item and item.get('log_type') == 'inference_cache':
            # Check TTL
            cached_at = item.get('created_at', '')
            if cached_at:
                from datetime import datetime, timezone
                cached_time = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
                age = (datetime.now(timezone.utc) - cached_time).total_seconds()
                if age < _CACHE_TTL:
                    return item.get('cached_response')
    except Exception:
        pass
    return None


def _set_cached(key, prompt_hash, response_text):
    """Store a response in the DynamoDB cache."""
    try:
        from dynamodb_helper import put_item
        from datetime import datetime, timezone
        put_item('ai1stseo-api-logs', {
            'id': key,
            'log_type': 'inference_cache',
            'prompt_hash': prompt_hash,
            'cached_response': response_text[:10000],  # Cap at 10KB
            'created_at': datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


def generate(prompt, max_tokens=4096, temperature=0.7, triggered_by='scan'):
    """
    Primary: Nova Lite via Bedrock.
    Fallback: Gurbachan's homelab Ollama (ollama.sageaios.com).
    Includes DynamoDB response cache (24h TTL) to avoid duplicate calls.
    Returns the generated text string.
    """
    # Check cache first (only for low-temperature deterministic calls)
    if temperature <= 0.3:
        key = _cache_key(prompt, max_tokens, temperature)
        cached = _get_cached(key)
        if cached:
            _log_ai_usage('cache_hit', 'cached', 0, 0, 0, True, 0, triggered_by)
            return cached

    # Try Nova Lite first
    text = _try_nova_lite(prompt, max_tokens, temperature, triggered_by)
    if text:
        if temperature <= 0.3:
            _set_cached(key, hashlib.md5(prompt.encode()).hexdigest()[:16], text)
        return text

    # Fallback: Ollama
    text = _try_ollama(prompt, max_tokens, temperature, triggered_by)
    if text:
        if temperature <= 0.3:
            _set_cached(key, hashlib.md5(prompt.encode()).hexdigest()[:16], text)
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
    """Log AI call to DynamoDB. Fails silently."""
    try:
        from dynamodb_helper import put_item
        put_item('ai1stseo-api-logs', {
            'provider': provider, 'model': model,
            'input_tokens_est': input_tokens, 'output_tokens_est': output_tokens,
            'estimated_cost_usd': cost, 'success': success,
            'latency_ms': latency_ms, 'triggered_by': triggered_by,
            'log_type': 'ai_usage',
        })
    except Exception as e:
        print("AI usage log failed (non-fatal): {}".format(e))
