"""SVD video generation test using uploaded image."""
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


def req(endpoint, method="GET", data=None):
    url = f"{SERVER}{endpoint}"
    r = urllib.request.Request(url, method=method)
    r.add_header("Authorization", f"Basic {auth_token}")
    if data:
        r.add_header("Content-Type", "application/json")
        r.data = json.dumps(data).encode()
    resp = urllib.request.urlopen(r, timeout=60)
    return json.loads(resp.read().decode())


# SVD img2vid workflow
workflow = {
    "1": {
        "class_type": "ImageOnlyCheckpointLoader",
        "inputs": {"ckpt_name": "SVD/svd_xt.safetensors"},
    },
    "2": {
        "class_type": "LoadImage",
        "inputs": {"image": "dev4_seo_banner.png"},
    },
    "3": {
        "class_type": "SVD_img2vid_Conditioning",
        "inputs": {
            "clip_vision": ["1", 1],
            "init_image": ["2", 0],
            "vae": ["1", 2],
            "width": 1024,
            "height": 576,
            "video_frames": 14,
            "motion_bucket_id": 127,
            "fps": 6,
            "augmentation_level": 0.0,
        },
    },
    "4": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["3", 0],
            "negative": ["3", 1],
            "latent_image": ["3", 2],
            "seed": 42,
            "steps": 20,
            "cfg": 2.5,
            "sampler_name": "euler",
            "scheduler": "karras",
            "denoise": 1.0,
        },
    },
    "5": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
    },
    "6": {
        "class_type": "SaveAnimatedWEBP",
        "inputs": {
            "images": ["5", 0],
            "filename_prefix": "dev4_video",
            "fps": 6.0,
            "lossless": False,
            "quality": 80,
            "method": "default",
        },
    },
}

client_id = str(uuid.uuid4())
print("Queueing SVD video generation (14 frames from seo_banner)...")
print("NOTE: SVD on P40 is slow — expect 5-10 minutes")
t0 = time.time()
result = req("/prompt", "POST", {"prompt": workflow, "client_id": client_id})
pid = result.get("prompt_id", "")
if not pid:
    print(f"Queue failed: {result}")
    exit(1)

print(f"  prompt_id: {pid}")

for i in range(200):
    time.sleep(5)
    elapsed = time.time() - t0
    try:
        h = req("/history")
        if pid in h:
            entry = h[pid]
            status = entry.get("status", {})
            status_str = status.get("status_str", "?")
            print(f"  Status: {status_str} in {elapsed:.1f}s")

            if status_str == "error":
                msgs = status.get("messages", [])
                for m in msgs:
                    print(f"    {m}")
                exit(1)

            outputs = entry.get("outputs", {})
            for nid, nout in outputs.items():
                for img in nout.get("images", []):
                    fn = img["filename"]
                    sf = img.get("subfolder", "")
                    tp = img.get("type", "output")
                    print(f"  Output: {fn}")
                    # Download
                    dl_url = f"{SERVER}/view?filename={fn}&subfolder={sf}&type={tp}"
                    dr = urllib.request.Request(dl_url)
                    dr.add_header("Authorization", f"Basic {auth_token}")
                    resp = urllib.request.urlopen(dr, timeout=60)
                    data = resp.read()
                    out = os.path.join(OUTPUTS_DIR, "svd_video_test.webp")
                    with open(out, "wb") as f:
                        f.write(data)
                    print(f"  Saved: {out} ({len(data)/1024:.0f} KB)")
            break
    except Exception as e:
        if i % 12 == 0:
            print(f"  Waiting... ({elapsed:.0f}s)")

else:
    print(f"  Timed out after {time.time()-t0:.0f}s")
