"""
AI Inference Module for Site Monitor — Dual-path: Nova Lite (primary) + Ollama (fallback)
Mirrors backend/ai_inference.py for independent Lambda deployment.
"""
import json
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://ollama.sageaios.com")
NOVA_MODEL = os.environ.get("NOVA_MODEL", "amazon.nova-lite-v1:0")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:30b-a3b")


def generate(prompt, max_tokens=4096, temperature=0.7):
    """
    Primary: Nova Lite via Bedrock.
    Fallback: Gurbachan's homelab Ollama (ollama.sageaios.com).
    Returns the generated text string.
    """
    text = _try_nova_lite(prompt, max_tokens, temperature)
    if text:
        return text

    text = _try_ollama(prompt, max_tokens, temperature)
    if text:
        return text

    return "AI inference unavailable. Both Nova Lite and Ollama endpoints failed."


def _try_nova_lite(prompt, max_tokens, temperature):
    """Invoke Amazon Nova Lite via Bedrock using the Messages API."""
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
        return result["output"]["message"]["content"][0]["text"]
    except Exception as e:
        print("Nova Lite failed: {}".format(e))
        return None


def _try_ollama(prompt, max_tokens, temperature):
    """Call Gurbachan's homelab Ollama server."""
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
            return resp.json().get("response", "")
    except Exception as e:
        print("Ollama failed: {}".format(e))
    return None
