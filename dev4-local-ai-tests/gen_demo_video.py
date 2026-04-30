"""gen_demo_video.py - Generate a demo video from an existing image using SVD XT."""
import urllib.request
import base64
import json
import os
import io
import time
import uuid

SERVER = "https://comfy.aisomad.ai"
user = os.environ.get("COMFY_USER", "")
pw = os.environ.get("COMFY_PASS", "")
if not user or not pw:
    print("ERROR: Set COMFY_USER and COMFY_PASS env vars")
    exit(1)

auth_token = base64.b64encode((user + ":" + pw).encode()).decode()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(SCRIPT_DIR, "outputs")
SOURCE_IMG = os.path.join(OUTPUTS_DIR, "final_v2_05.png")
UPLOAD_NAME = "dev4_demo_src.png"


def req(endpoint, method="GET", data=None):
    url = SERVER + endpoint
    r = urllib.request.Request(url, method=method)
    r.add_header("Authorization", "Basic " + auth_token)
    if data is not None:
        r.add_header("Content-Type", "application/json")
        r.data = json.dumps(data).encode()
    resp = urllib.request.urlopen(r, timeout=120)
    return json.loads(resp.read().decode())


def upload_image():
    print("Uploading source image...")
    with open(SOURCE_IMG, "rb") as f:
        img_data = f.read()
    boundary = "----Boundary" + uuid.uuid4().hex[:12]
    body = io.BytesIO()
    body.write(("--" + boundary + "\r\n").encode())
    body.write(b'Content-Disposition: form-data; name="image"; filename="' + UPLOAD_NAME.encode() + b'"\r\n')
    body.write(b"Content-Type: image/png\r\n\r\n")
    body.write(img_data)
    body.write(b"\r\n")
    body.write(("--" + boundary + "\r\n").encode())
    body.write(b'Content-Disposition: form-data; name="overwrite"\r\n\r\n')
    body.write(b"true\r\n")
    body.write(("--" + boundary + "--\r\n").encode())
    payload = body.getvalue()
    url = SERVER + "/upload/image"
    r = urllib.request.Request(url, data=payload, method="POST")
    r.add_header("Authorization", "Basic " + auth_token)
    r.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    resp = urllib.request.urlopen(r, timeout=30)
    result = json.loads(resp.read().decode())
    print("  Uploaded: " + str(result))
    return result


def run_svd():
    workflow = {
        "1": {
            "class_type": "ImageOnlyCheckpointLoader",
            "inputs": {"ckpt_name": "SVD/svd_xt.safetensors"},
        },
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": UPLOAD_NAME},
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
                "seed": 12345,
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
                "filename_prefix": "dev4_demo_vid",
                "fps": 6.0,
                "lossless": False,
                "quality": 85,
                "method": "default",
            },
        },
    }
    client_id = str(uuid.uuid4())
    print("Queueing SVD generation (14 frames, 1024x576)...")
    print("This takes ~8 minutes on P40. Please wait.")
    t0 = time.time()
    result = req("/prompt", "POST", {"prompt": workflow, "client_id": client_id})
    pid = result.get("prompt_id", "")
    if not pid:
        print("Queue failed: " + str(result))
        return None, 0
    print("  prompt_id: " + pid)
    for i in range(250):
        time.sleep(5)
        elapsed = time.time() - t0
        try:
            h = req("/history")
            if pid in h:
                entry = h[pid]
                status = entry.get("status", {}).get("status_str", "?")
                print("  Status: %s in %.1fs" % (status, elapsed))
                if status == "error":
                    msgs = entry.get("status", {}).get("messages", [])
                    for m in msgs:
                        print("    " + str(m))
                    return None, elapsed
                outputs = entry.get("outputs", {})
                for nid, nout in outputs.items():
                    for img in nout.get("images", []):
                        return img, elapsed
                return None, elapsed
        except Exception:
            if i % 12 == 0:
                print("  Waiting... (%.0fs)" % elapsed)
    print("  Timed out")
    return None, time.time() - t0


def download(img_info):
    fn = img_info["filename"]
    sf = img_info.get("subfolder", "")
    tp = img_info.get("type", "output")
    url = "%s/view?filename=%s&subfolder=%s&type=%s" % (SERVER, fn, sf, tp)
    r = urllib.request.Request(url)
    r.add_header("Authorization", "Basic " + auth_token)
    resp = urllib.request.urlopen(r, timeout=60)
    data = resp.read()
    out_path = os.path.join(OUTPUTS_DIR, "demo_video.webp")
    with open(out_path, "wb") as f:
        f.write(data)
    kb = len(data) / 1024
    print("  Saved: %s (%.0f KB)" % (out_path, kb))
    return out_path


def main():
    print("=" * 60)
    print("DEMO VIDEO GENERATION (SVD XT)")
    print("=" * 60)
    print("Source: " + SOURCE_IMG)
    if not os.path.exists(SOURCE_IMG):
        print("ERROR: Source image not found")
        return
    upload_image()
    img_info, elapsed = run_svd()
    if img_info:
        path = download(img_info)
        print("")
        print("=" * 60)
        print("DONE")
        print("  File: demo_video.webp")
        print("  Source: final_v2_05.png (3X More Organic Traffic)")
        print("  Model: SVD XT")
        print("  Frames: 14 @ 6fps")
        print("  Resolution: 1024x576")
        print("  Generation time: %.1fs" % elapsed)
        print("=" * 60)
    else:
        print("FAILED - no output generated")


if __name__ == "__main__":
    main()
