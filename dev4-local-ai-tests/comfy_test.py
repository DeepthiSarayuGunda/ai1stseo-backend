"""
comfy_test.py — ComfyUI (FLUX Schnell / SDXL) image generation test.
Fully isolated — does NOT import anything from the main project.

PREREQUISITES:
  1. ComfyUI server credentials (HTTP Basic Auth)
  2. Set environment variables before running:
       set COMFY_USER=your_username
       set COMFY_PASS=your_password
  3. Run: python dev4-local-ai-tests/comfy_test.py

Server: https://comfy.aisomad.ai (behind openresty reverse proxy, Basic Auth)
"""
import json
import os
import sys
import time
import base64
import urllib.request
import urllib.error
import uuid

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

SERVER = "https://comfy.aisomad.ai"
COMFY_USER = os.environ.get("COMFY_USER", "")
COMFY_PASS = os.environ.get("COMFY_PASS", "")


def _auth_header():
    """Build Basic Auth header from env vars."""
    if not COMFY_USER or not COMFY_PASS:
        return None
    token = base64.b64encode(f"{COMFY_USER}:{COMFY_PASS}".encode()).decode()
    return f"Basic {token}"


def _request(endpoint, method="GET", data=None):
    """Make authenticated request to ComfyUI server."""
    url = f"{SERVER}{endpoint}"
    req = urllib.request.Request(url, method=method)
    auth = _auth_header()
    if auth:
        req.add_header("Authorization", auth)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())


# ============================================================
# STEP 1: Access Check
# ============================================================

def check_access():
    """Verify connection and get system info."""
    print("=" * 60)
    print("STEP 1: ACCESS CHECK")
    print("=" * 60)

    if not COMFY_USER or not COMFY_PASS:
        print("  ERROR: COMFY_USER and COMFY_PASS env vars not set.")
        print("  Set them before running:")
        print('    set COMFY_USER=your_username')
        print('    set COMFY_PASS=your_password')
        return False

    try:
        stats = _request("/system_stats")
        print(f"  Server: {SERVER}")
        print(f"  Connection: OK")
        devices = stats.get("devices", [])
        for d in devices:
            print(f"  GPU: {d.get('name', '?')}")
            vram = d.get("vram_total", 0)
            if vram:
                print(f"  VRAM: {vram / (1024**3):.1f} GB")
        return True
    except urllib.error.HTTPError as e:
        print(f"  HTTP Error: {e.code}")
        if e.code == 401:
            print("  Authentication failed — check COMFY_USER / COMFY_PASS")
        return False
    except Exception as e:
        print(f"  Connection failed: {e}")
        return False


# ============================================================
# STEP 2: Discover Available Models
# ============================================================

def discover_models():
    """Query ComfyUI for available checkpoints and models."""
    print("\n" + "=" * 60)
    print("STEP 2: AVAILABLE MODELS")
    print("=" * 60)

    try:
        obj_info = _request("/object_info")

        # Extract checkpoint loader info
        ckpt_info = obj_info.get("CheckpointLoaderSimple", {})
        ckpt_input = ckpt_info.get("input", {}).get("required", {})
        checkpoints = ckpt_input.get("ckpt_name", [[]])[0]

        # Extract UNET/diffusion model loader info (for FLUX)
        unet_info = obj_info.get("UNETLoader", {})
        unet_input = unet_info.get("input", {}).get("required", {})
        unet_models = unet_input.get("unet_name", [[]])[0]

        # Extract VAE models
        vae_info = obj_info.get("VAELoader", {})
        vae_input = vae_info.get("input", {}).get("required", {})
        vae_models = vae_input.get("vae_name", [[]])[0]

        print(f"\n  Checkpoints ({len(checkpoints)}):")
        for c in checkpoints:
            print(f"    - {c}")

        if unet_models:
            print(f"\n  UNET/Diffusion models ({len(unet_models)}):")
            for u in unet_models:
                print(f"    - {u}")

        if vae_models:
            print(f"\n  VAE models ({len(vae_models)}):")
            for v in vae_models:
                print(f"    - {v}")

        # Detect known models
        all_models = [m.lower() for m in checkpoints + unet_models]
        has_flux = any("flux" in m for m in all_models)
        has_sdxl = any("sdxl" in m or "sd_xl" in m for m in all_models)
        has_svd = any("svd" in m for m in all_models)
        has_sd15 = any("v1-5" in m or "sd15" in m or "v1.5" in m for m in all_models)

        print(f"\n  Detected:")
        print(f"    FLUX Schnell: {'YES' if has_flux else 'NO'}")
        print(f"    SDXL:         {'YES' if has_sdxl else 'NO'}")
        print(f"    SD 1.5:       {'YES' if has_sd15 else 'NO'}")
        print(f"    SVD (video):  {'YES' if has_svd else 'NO'}")

        return {
            "checkpoints": checkpoints,
            "unet_models": unet_models,
            "vae_models": vae_models,
            "has_flux": has_flux,
            "has_sdxl": has_sdxl,
            "has_svd": has_svd,
        }
    except Exception as e:
        print(f"  Failed to query models: {e}")
        return None


# ============================================================
# STEP 3: Image Generation — FLUX Schnell workflow
# ============================================================

def build_flux_schnell_workflow(prompt, width=1024, height=1024, steps=4, seed=None):
    """
    Build a ComfyUI API workflow for FLUX Schnell text-to-image.
    FLUX Schnell uses UNETLoader + DualCLIPLoader + VAEDecode pipeline.
    Schnell is optimized for speed — typically 4 steps is enough.
    """
    if seed is None:
        seed = int.from_bytes(os.urandom(4), "big")

    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "4": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux1-schnell-fp8.safetensors",
                "weight_dtype": "fp8_e4m3fn",
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["11", 0]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["11", 0]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["10", 0]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "comfy_test"},
        },
        "10": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        "11": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux",
            },
        },
    }


def build_sdxl_workflow(prompt, negative="", width=1024, height=1024, steps=20, seed=None, ckpt_name=None):
    """
    Build a ComfyUI API workflow for SDXL text-to-image.
    Uses CheckpointLoaderSimple pipeline.
    """
    if seed is None:
        seed = int.from_bytes(os.urandom(4), "big")
    if ckpt_name is None:
        ckpt_name = "sd_xl_base_1.0.safetensors"

    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt_name},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative or "blurry, low quality, distorted", "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "comfy_test"},
        },
    }


def queue_prompt(workflow):
    """Submit a workflow to ComfyUI and return the prompt_id."""
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    result = _request("/prompt", method="POST", data=payload)
    prompt_id = result.get("prompt_id")
    print(f"  Queued prompt: {prompt_id}")
    return prompt_id, client_id


def wait_for_completion(prompt_id, timeout=300):
    """Poll /history until the prompt completes."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            history = _request("/history")
            if prompt_id in history:
                return history[prompt_id]
        except Exception:
            pass
        time.sleep(2)
    return None


def download_image(history_entry, output_name):
    """Download generated image from ComfyUI output."""
    outputs = history_entry.get("outputs", {})
    for node_id, node_out in outputs.items():
        images = node_out.get("images", [])
        for img_info in images:
            filename = img_info.get("filename")
            subfolder = img_info.get("subfolder", "")
            img_type = img_info.get("type", "output")

            url = f"{SERVER}/view?filename={filename}&subfolder={subfolder}&type={img_type}"
            req = urllib.request.Request(url)
            auth = _auth_header()
            if auth:
                req.add_header("Authorization", auth)
            resp = urllib.request.urlopen(req, timeout=30)
            img_data = resp.read()

            out_path = os.path.join(OUTPUTS_DIR, output_name)
            with open(out_path, "wb") as f:
                f.write(img_data)
            print(f"  Saved: {out_path} ({len(img_data) / 1024:.0f} KB)")
            return out_path
    return None


# ============================================================
# STEP 4: Generate Sample Images
# ============================================================

DEMO_PROMPTS = [
    {
        "name": "seo_banner",
        "prompt": "A modern, clean digital marketing banner for an AI-powered SEO analytics "
                  "platform. Blue and white color scheme, professional minimalist design, "
                  "abstract technology elements, data visualization in background. High quality, "
                  "sharp details, 4k render.",
    },
    {
        "name": "social_post",
        "prompt": "A vibrant social media post design showing upward trending analytics charts. "
                  "Modern gradient from deep blue to teal, clean white text area, professional "
                  "business aesthetic suitable for LinkedIn or Instagram. High quality graphic design.",
    },
    {
        "name": "dashboard_ui",
        "prompt": "A clean SEO dashboard UI graphic showing analytics widgets, charts, and "
                  "metrics. Modern flat design, dark mode with blue accent colors, professional "
                  "data visualization. Screenshot-style, high resolution, crisp typography.",
    },
]


def generate_images(models_info):
    """Generate sample images using the best available model."""
    print("\n" + "=" * 60)
    print("STEP 3-4: IMAGE GENERATION")
    print("=" * 60)

    results = []
    use_flux = models_info and models_info.get("has_flux", False)
    model_name = "FLUX Schnell" if use_flux else "SDXL"
    # NOTE: As of April 2026, this server has SDXL but NOT FLUX Schnell.
    print(f"  Using model: {model_name}")

    for item in DEMO_PROMPTS:
        print(f"\n  --- {item['name']} ---")
        try:
            if use_flux:
                workflow = build_flux_schnell_workflow(item["prompt"])
            else:
                # Try to find an SDXL checkpoint
                ckpt = None
                if models_info and models_info.get("checkpoints"):
                    for c in models_info["checkpoints"]:
                        if "sdxl" in c.lower() or "sd_xl" in c.lower():
                            ckpt = c
                            break
                    if not ckpt:
                        ckpt = models_info["checkpoints"][0]
                workflow = build_sdxl_workflow(item["prompt"], ckpt_name=ckpt)

            t0 = time.time()
            prompt_id, _ = queue_prompt(workflow)
            history = wait_for_completion(prompt_id)
            elapsed = time.time() - t0

            if history:
                out_file = f"{item['name']}_{model_name.lower().replace(' ', '_')}.png"
                path = download_image(history, out_file)
                if path:
                    results.append({
                        "name": item["name"],
                        "model": model_name,
                        "file": out_file,
                        "time_sec": round(elapsed, 1),
                        "status": "OK",
                    })
                    print(f"  Generated in {elapsed:.1f}s")
                else:
                    results.append({
                        "name": item["name"],
                        "model": model_name,
                        "file": None,
                        "time_sec": round(elapsed, 1),
                        "status": "FAIL: could not download image",
                    })
            else:
                results.append({
                    "name": item["name"],
                    "model": model_name,
                    "file": None,
                    "time_sec": round(time.time() - t0, 1),
                    "status": "FAIL: generation timed out",
                })
        except Exception as e:
            results.append({
                "name": item["name"],
                "model": model_name,
                "file": None,
                "time_sec": 0,
                "status": f"ERROR: {e}",
            })
            print(f"  ERROR: {e}")

    return results


# ============================================================
# STEP 5: Video Check (SVD)
# ============================================================

def check_video_capability(models_info):
    """Check if Stable Video Diffusion is available."""
    print("\n" + "=" * 60)
    print("STEP 5: VIDEO CAPABILITY CHECK")
    print("=" * 60)

    if models_info and models_info.get("has_svd"):
        print("  Stable Video Diffusion: AVAILABLE")
        print("  Video generation from image is possible.")
        return True
    else:
        print("  Stable Video Diffusion: NOT AVAILABLE")
        print("  No video generation models detected on this server.")
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("COMFYUI LOCAL AI — IMAGE/VIDEO GENERATION TEST")
    print(f"Server: {SERVER}")
    print("=" * 60)

    # Step 1: Access check
    if not check_access():
        print("\n" + "=" * 60)
        print("CANNOT PROCEED — server access failed.")
        print("Set COMFY_USER and COMFY_PASS env vars and retry.")
        print("=" * 60)
        sys.exit(1)

    # Step 2: Discover models
    models_info = discover_models()

    # Step 3-4: Generate images
    if models_info:
        results = generate_images(models_info)
    else:
        print("\nSkipping generation — could not discover models.")
        results = []

    # Step 5: Video check
    has_video = check_video_capability(models_info)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    ok_count = sum(1 for r in results if r["status"] == "OK")
    print(f"  Images generated: {ok_count}/{len(results)}")
    for r in results:
        status = "OK" if r["status"] == "OK" else "FAIL"
        print(f"    [{r['model']}] {r['name']}: {status} ({r['time_sec']}s)")
        if r.get("file"):
            print(f"      -> {r['file']}")
    print(f"  Video capable: {'YES' if has_video else 'NO'}")
    print(f"  Outputs: {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
