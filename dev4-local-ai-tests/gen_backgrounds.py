"""Generate text-free background images optimized for text overlay."""
import urllib.request
import base64
import json
import os
import time
import uuid

SERVER = "https://comfy.aisomad.ai"
user = os.environ.get("COMFY_USER", "")
pw = os.environ.get("COMFY_PASS", "")
if not user or not pw:
    print("ERROR: Set COMFY_USER and COMFY_PASS env vars")
    exit(1)

auth_token = base64.b64encode(f"{user}:{pw}".encode()).decode()
OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def req(endpoint, method="GET", data=None):
    url = f"{SERVER}{endpoint}"
    r = urllib.request.Request(url, method=method)
    r.add_header("Authorization", f"Basic {auth_token}")
    if data:
        r.add_header("Content-Type", "application/json")
        r.data = json.dumps(data).encode()
    resp = urllib.request.urlopen(r, timeout=60)
    return json.loads(resp.read().decode())


def sdxl_workflow(prompt, neg, seed=None, w=1024, h=1024, steps=30):
    if seed is None:
        seed = int.from_bytes(os.urandom(4), "big")
    return {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "SDXL/sd_xl_base_1.0.safetensors"},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": w, "height": h, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": neg, "clip": ["4", 1]},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 7.5,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "dev4_bg"},
        },
    }


BACKGROUNDS = [
    {
        "name": "bg_seo_banner",
        "prompt": (
            "modern digital marketing banner background, clean minimal layout, "
            "large empty space in center for text, professional blue and white gradient, "
            "subtle abstract geometric shapes on edges, soft bokeh light effects, "
            "corporate tech aesthetic, smooth clean surface, no text, no letters, "
            "no words, no writing, no typography, no watermark, 4k, sharp"
        ),
        "negative": (
            "text, letters, words, writing, typography, watermark, logo, signature, "
            "blurry, low quality, distorted, ugly, noisy, cluttered, busy, "
            "people, faces, hands, fingers"
        ),
    },
    {
        "name": "bg_social_post",
        "prompt": (
            "social media post background design, vibrant modern gradient from deep blue "
            "to teal to cyan, large clean empty area in upper half for text overlay, "
            "subtle abstract data visualization elements at bottom, glowing particles, "
            "professional business aesthetic, minimal, no text, no letters, no words, "
            "no writing, no typography, 4k, crisp, high quality"
        ),
        "negative": (
            "text, letters, words, writing, typography, watermark, logo, signature, "
            "blurry, low quality, distorted, ugly, noisy, cluttered, people, faces"
        ),
    },
]


def generate_and_download(item):
    wf = sdxl_workflow(item["prompt"], item["negative"])
    client_id = str(uuid.uuid4())
    print(f"\n  Generating: {item['name']}...")
    t0 = time.time()
    result = req("/prompt", "POST", {"prompt": wf, "client_id": client_id})
    pid = result.get("prompt_id", "")
    if not pid:
        print(f"    Queue failed: {result}")
        return None

    for _ in range(120):
        time.sleep(3)
        try:
            h = req("/history")
            if pid in h:
                elapsed = time.time() - t0
                entry = h[pid]
                status_str = entry.get("status", {}).get("status_str", "?")
                if status_str == "error":
                    print(f"    FAILED: {entry.get('status', {}).get('messages', [])}")
                    return None
                outputs = entry.get("outputs", {})
                for nid, nout in outputs.items():
                    for img in nout.get("images", []):
                        fn = img["filename"]
                        dl_url = f"{SERVER}/view?filename={fn}&subfolder=&type=output"
                        dr = urllib.request.Request(dl_url)
                        dr.add_header("Authorization", f"Basic {auth_token}")
                        resp = urllib.request.urlopen(dr, timeout=30)
                        data = resp.read()
                        out = os.path.join(OUTPUTS_DIR, f"{item['name']}.png")
                        with open(out, "wb") as f:
                            f.write(data)
                        print(f"    OK — {elapsed:.1f}s, {len(data)/1024:.0f} KB -> {out}")
                        return out
                return None
        except Exception:
            pass
    print("    Timed out")
    return None


def main():
    print("=" * 60)
    print("GENERATING TEXT-FREE BACKGROUNDS (SDXL)")
    print("=" * 60)
    for item in BACKGROUNDS:
        generate_and_download(item)
    print("\nDone.")


if __name__ == "__main__":
    main()
