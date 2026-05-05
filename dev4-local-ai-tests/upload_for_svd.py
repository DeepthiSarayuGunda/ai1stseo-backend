"""Upload an image to ComfyUI input folder for SVD video generation."""
import urllib.request
import base64
import json
import os
import uuid
import io

SERVER = "https://comfy.aisomad.ai"
user = os.environ.get("COMFY_USER", "")
pw = os.environ.get("COMFY_PASS", "")

if not user or not pw:
    print("ERROR: Set COMFY_USER and COMFY_PASS env vars")
    exit(1)

auth_token = base64.b64encode(f"{user}:{pw}".encode()).decode()

img_path = os.path.join(os.path.dirname(__file__), "outputs", "seo_banner_sdxl.png")
with open(img_path, "rb") as f:
    img_data = f.read()

boundary = "----WebKitFormBoundary" + uuid.uuid4().hex[:16]
body = io.BytesIO()

# Image file part
body.write(f"--{boundary}\r\n".encode())
body.write(
    b'Content-Disposition: form-data; name="image"; filename="dev4_seo_banner.png"\r\n'
)
body.write(b"Content-Type: image/png\r\n\r\n")
body.write(img_data)
body.write(b"\r\n")

# Overwrite flag
body.write(f"--{boundary}\r\n".encode())
body.write(b'Content-Disposition: form-data; name="overwrite"\r\n\r\n')
body.write(b"true\r\n")

body.write(f"--{boundary}--\r\n".encode())

data = body.getvalue()
url = f"{SERVER}/upload/image"
req = urllib.request.Request(url, data=data, method="POST")
req.add_header("Authorization", f"Basic {auth_token}")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read().decode())
print(f"Upload result: {result}")
