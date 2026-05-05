"""
generate_samples.py — Generate sample images once Bedrock InvokeModel access is granted.
Isolated test — does NOT import anything from the main project.

Usage:
  1. Ensure SSO is logged in:  aws sso login --profile poweruser
  2. Run:  python dev4-amazon-tests/generate_samples.py

Generates 2-3 sample images using Nova Canvas and Titan Image Generator.
Attempts Nova Reel video only if S3 bucket is available.
"""
import json
import os
import sys
import base64
import time

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

PROFILE = "poweruser"
REGION = "us-east-1"

# --- Sample prompts for SEO/marketing demo ---
NOVA_CANVAS_PROMPTS = [
    {
        "name": "nova_canvas_seo_banner",
        "prompt": "A modern digital marketing banner for an AI-powered SEO analytics platform. "
                  "Clean blue and white color scheme, professional minimalist design, abstract "
                  "technology elements, data visualization graphics in the background.",
    },
    {
        "name": "nova_canvas_social_post",
        "prompt": "A vibrant social media post graphic showing upward trending analytics charts "
                  "and graphs. Modern gradient from deep blue to teal, clean white text area, "
                  "professional business aesthetic suitable for LinkedIn or Instagram.",
    },
]

TITAN_PROMPTS = [
    {
        "name": "titan_brand_visual",
        "prompt": "Professional brand visual for AI content optimization tool. Abstract neural "
                  "network pattern, modern tech aesthetic, purple and blue gradient, clean and "
                  "corporate design suitable for website hero section.",
    },
]


def get_session():
    import boto3
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print(f"Authenticated as: {identity['Arn']}")
    return session


def generate_nova_canvas(session, prompt_text, output_name):
    """Generate image with Nova Canvas."""
    bedrock_rt = session.client("bedrock-runtime")
    body = json.dumps({
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {"text": prompt_text},
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "height": 1024,
            "width": 1024,
            "quality": "standard",
        },
    })

    print(f"  Generating: {output_name}")
    print(f"  Prompt: {prompt_text[:70]}...")
    t0 = time.time()
    response = bedrock_rt.invoke_model(
        modelId="amazon.nova-canvas-v1:0",
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    elapsed = time.time() - t0
    result = json.loads(response["body"].read())
    images = result.get("images", [])

    if not images:
        print(f"  FAILED: No images returned")
        return None

    img_bytes = base64.b64decode(images[0])
    out_path = os.path.join(OUTPUTS_DIR, f"{output_name}.png")
    with open(out_path, "wb") as f:
        f.write(img_bytes)
    size_kb = len(img_bytes) / 1024
    print(f"  OK — {elapsed:.1f}s, {size_kb:.0f} KB → {out_path}")
    return out_path


def generate_titan_image(session, prompt_text, output_name):
    """Generate image with Titan Image Generator v2."""
    bedrock_rt = session.client("bedrock-runtime")
    body = json.dumps({
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {"text": prompt_text},
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "height": 1024,
            "width": 1024,
            "quality": "standard",
        },
    })

    print(f"  Generating: {output_name}")
    print(f"  Prompt: {prompt_text[:70]}...")
    t0 = time.time()
    response = bedrock_rt.invoke_model(
        modelId="amazon.titan-image-generator-v2:0",
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    elapsed = time.time() - t0
    result = json.loads(response["body"].read())
    images = result.get("images", [])

    if not images:
        print(f"  FAILED: No images returned")
        return None

    img_bytes = base64.b64decode(images[0])
    out_path = os.path.join(OUTPUTS_DIR, f"{output_name}.png")
    with open(out_path, "wb") as f:
        f.write(img_bytes)
    size_kb = len(img_bytes) / 1024
    print(f"  OK — {elapsed:.1f}s, {size_kb:.0f} KB → {out_path}")
    return out_path


def test_nova_reel_access(session):
    """Check if Nova Reel can be invoked (needs S3 bucket)."""
    print("\n--- Nova Reel (Video) ---")
    print("  Nova Reel requires start_async_invoke() + S3 output bucket.")

    # Check if any S3 buckets exist that we could use
    try:
        s3 = session.client("s3")
        buckets = s3.list_buckets().get("Buckets", [])
        if buckets:
            print(f"  Found {len(buckets)} S3 bucket(s):")
            for b in buckets[:5]:
                print(f"    - {b['Name']}")
            print("  Video generation possible if a bucket is designated for output.")
        else:
            print("  No S3 buckets found. Video generation requires an output bucket.")
        return len(buckets) > 0
    except Exception as e:
        print(f"  Could not list S3 buckets: {e}")
        return False


def main():
    print("=" * 60)
    print("AMAZON BEDROCK — SAMPLE IMAGE GENERATION")
    print("=" * 60)

    try:
        session = get_session()
    except Exception as e:
        print(f"\nAWS AUTH FAILED: {e}")
        print("Run: aws sso login --profile poweruser")
        sys.exit(1)

    results = []

    # Nova Canvas images
    print("\n--- Nova Canvas (amazon.nova-canvas-v1:0) ---")
    for item in NOVA_CANVAS_PROMPTS:
        try:
            path = generate_nova_canvas(session, item["prompt"], item["name"])
            results.append(("Nova Canvas", item["name"], "OK" if path else "FAIL", path))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(("Nova Canvas", item["name"], f"ERROR: {e}", None))

    # Titan images
    print("\n--- Titan Image Generator v2 (amazon.titan-image-generator-v2:0) ---")
    for item in TITAN_PROMPTS:
        try:
            path = generate_titan_image(session, item["prompt"], item["name"])
            results.append(("Titan v2", item["name"], "OK" if path else "FAIL", path))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(("Titan v2", item["name"], f"ERROR: {e}", None))

    # Nova Reel check
    has_s3 = test_nova_reel_access(session)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for model, name, status, path in results:
        print(f"  [{model}] {name}: {status}")
    if has_s3:
        print("  [Nova Reel] Video generation: POSSIBLE (S3 available)")
    else:
        print("  [Nova Reel] Video generation: BLOCKED (no S3 bucket)")

    ok_count = sum(1 for _, _, s, _ in results if s == "OK")
    print(f"\n  Total generated: {ok_count}/{len(results)} images")
    print(f"  Output dir: {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
