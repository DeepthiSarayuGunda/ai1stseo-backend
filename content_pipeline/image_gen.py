"""
Image generation via ComfyUI (FLUX Schnell / SDXL).
Falls back to Amazon Nova Canvas if ComfyUI is unavailable.
"""

import base64
import json
import logging
import os
import time
import urllib.request
import urllib.error
import uuid

logger = logging.getLogger(__name__)

COMFYUI_URL = os.environ.get("COMFYUI_API_URL", "https://comfy.aisomad.ai")
COMFY_USER = os.environ.get("COMFY_USER", "")
COMFY_PASS = os.environ.get("COMFY_PASS", "")


def _auth_header():
    if not COMFY_USER or not COMFY_PASS:
        return None
    token = base64.b64encode(f"{COMFY_USER}:{COMFY_PASS}".encode()).decode()
    return f"Basic {token}"


def _comfy_request(endpoint, method="GET", data=None):
    url = f"{COMFYUI_URL.rstrip('/')}{endpoint}"
    req = urllib.request.Request(url, method=method)
    auth = _auth_header()
    if auth:
        req.add_header("Authorization", auth)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())


def is_comfyui_available() -> bool:
    """Check if ComfyUI server is reachable."""
    if not COMFY_USER or not COMFY_PASS:
        return False
    try:
        _comfy_request("/system_stats")
        return True
    except Exception:
        return False


def generate_image_comfyui(prompt: str, filename: str) -> bytes:
    """Generate image via ComfyUI. Returns image bytes."""
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                "latent_image": ["5", 0], "seed": int.from_bytes(os.urandom(4), "big"),
                "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                "scheduler": "normal", "denoise": 1.0,
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, distorted", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "pipeline"}},
    }

    client_id = str(uuid.uuid4())
    result = _comfy_request("/prompt", method="POST", data={"prompt": workflow, "client_id": client_id})
    prompt_id = result.get("prompt_id")

    # Wait for completion
    for _ in range(150):  # 5 min timeout
        time.sleep(2)
        try:
            history = _comfy_request("/history")
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_out in outputs.values():
                    for img in node_out.get("images", []):
                        url = f"{COMFYUI_URL}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img.get('type','output')}"
                        req = urllib.request.Request(url)
                        auth = _auth_header()
                        if auth:
                            req.add_header("Authorization", auth)
                        return urllib.request.urlopen(req, timeout=30).read()
        except Exception:
            pass

    raise RuntimeError("ComfyUI image generation timed out")


def generate_image_nova_canvas(prompt: str) -> bytes:
    """Generate image using Amazon Nova Canvas via Bedrock."""
    import boto3
    region = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))
    client = boto3.client("bedrock-runtime", region_name=region)

    body = json.dumps({
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {"text": prompt},
        "imageGenerationConfig": {"numberOfImages": 1, "height": 1024, "width": 1024, "cfgScale": 8.0},
    })

    resp = client.invoke_model(modelId="amazon.nova-canvas-v1:0", contentType="application/json", accept="application/json", body=body)
    result = json.loads(resp["body"].read())
    img_b64 = result["images"][0]
    return base64.b64decode(img_b64)


def generate_image(title: str) -> bytes:
    """Generate an image for an article. Tries ComfyUI first, falls back to Nova Canvas."""
    prompt = (
        f"A modern, professional blog header image for an article titled '{title}'. "
        "Clean design, blue and white color scheme, abstract technology elements, "
        "suitable for a professional SEO/marketing blog. High quality, 4k."
    )

    if is_comfyui_available():
        try:
            logger.info("Generating image via ComfyUI: %s", title[:50])
            return generate_image_comfyui(prompt, title)
        except Exception as e:
            logger.warning("ComfyUI failed, falling back to Nova Canvas: %s", e)

    try:
        logger.info("Generating image via Nova Canvas: %s", title[:50])
        return generate_image_nova_canvas(prompt)
    except Exception as e:
        logger.error("Image generation failed: %s", e)
        return None
