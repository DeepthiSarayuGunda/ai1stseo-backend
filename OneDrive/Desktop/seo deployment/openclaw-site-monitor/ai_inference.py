"""
AI Inference Module for Site Monitor — Tiered model support via local Ollama accelerator.
Primary: Nova Lite via Bedrock (Lambda). Fallback: Local Ollama accelerator (LAN).
Supports 3 model tiers: fast (8B), standard (30B), heavy (235B) + embeddings.
Logs usage to ai_usage_log table for cost tracking.
"""
import json
import os
import time
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.2.200:11434")
NOVA_MODEL = os.environ.get("NOVA_MODEL", "amazon.nova-lite-v1:0")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:30b-a3b")
OLLAMA_FAST_MODEL = os.environ.get("OLLAMA_FAST_MODEL", "llama3.1:8b")
OLLAMA_HEAVY_MODEL = os.environ.get("OLLAMA_HEAVY_MODEL", "qwen3:235b-a22b")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")

# Nova Lite pricing (us-east-1, per token)
NOVA_INPUT_COST = 0.00000006   # $0.06 per 1M input tokens
NOVA_OUTPUT_COST = 0.00000024  # $0.24 per 1M output tokens

# Model tier mapping
MODEL_TIERS = {
    'fast': OLLAMA_FAST_MODEL,       # llama3.1:8b — quick checks, summaries
    'standard': OLLAMA_MODEL,         # qwen3:30b — default analysis
    'heavy': OLLAMA_HEAVY_MODEL,      # qwen3:235b — deep analysis, competitor intel
}


def generate(prompt, max_tokens=4096, temperature=0.7, triggered_by='monitor', tier='standard'):
    """
    Primary: Nova Lite via Bedrock.
    Fallback: Local Ollama accelerator with tiered model selection.
    Tiers: 'fast' (8B, <2s), 'standard' (30B, ~5s), 'heavy' (235B, ~30s).
    Returns the generated text string.
    """
    # For heavy tier, skip Nova and go straight to the 235B model
    if tier != 'heavy':
        text = _try_nova_lite(prompt, max_tokens, temperature, triggered_by)
        if text:
            return text

    model = MODEL_TIERS.get(tier, OLLAMA_MODEL)
    text = _try_ollama(prompt, max_tokens, temperature, triggered_by, model=model)
    if text:
        return text

    # If heavy failed, try standard as fallback
    if tier == 'heavy':
        text = _try_ollama(prompt, max_tokens, temperature, triggered_by, model=OLLAMA_MODEL)
        if text:
            return text

    return "AI inference unavailable. Both Nova Lite and Ollama endpoints failed."


def generate_fast(prompt, max_tokens=1024, triggered_by='monitor'):
    """Quick inference using the 8B model. Good for summaries, classifications."""
    return generate(prompt, max_tokens=max_tokens, triggered_by=triggered_by, tier='fast')


def generate_deep(prompt, max_tokens=8192, triggered_by='monitor'):
    """Deep inference using the 235B model. Good for competitor analysis, detailed reports."""
    return generate(prompt, max_tokens=max_tokens, temperature=0.5, triggered_by=triggered_by, tier='heavy')


def get_embeddings(text, triggered_by='monitor'):
    """Generate text embeddings using nomic-embed-text for semantic similarity."""
    start = time.time()
    try:
        resp = requests.post(
            "{}/api/embeddings".format(OLLAMA_URL),
            json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=30,
        )
        if resp.status_code == 200:
            embedding = resp.json().get("embedding", [])
            latency = int((time.time() - start) * 1000)
            _log_ai_usage('ollama_local', OLLAMA_EMBED_MODEL, len(text) // 4, 0, 0, True, latency, triggered_by)
            return embedding
    except Exception as e:
        print("Embedding failed: {}".format(e))
    return None


def _try_nova_lite(prompt, max_tokens, temperature, triggered_by='monitor'):
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


def _try_ollama(prompt, max_tokens, temperature, triggered_by='monitor', model=None):
    """Call local Ollama accelerator on LAN (192.168.2.200)."""
    if model is None:
        model = OLLAMA_MODEL
    start = time.time()
    try:
        resp = requests.post(
            "{}/api/generate".format(OLLAMA_URL),
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
            timeout=300,  # 235B model can take a while
        )
        if resp.status_code == 200:
            text = resp.json().get("response", "")
            latency = int((time.time() - start) * 1000)
            _log_ai_usage('ollama_local', model, len(prompt) // 4, len(text) // 4, 0, True, latency, triggered_by)
            return text
    except Exception as e:
        print("Ollama failed ({}): {}".format(model, e))
    latency = int((time.time() - start) * 1000)
    _log_ai_usage('ollama_local', model, len(prompt) // 4, 0, 0, False, latency, triggered_by)
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
