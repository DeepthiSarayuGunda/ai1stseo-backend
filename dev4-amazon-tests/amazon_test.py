"""
amazon_test.py — Standalone Amazon image/video generation test.
Does NOT import anything from the main project.

PREREQUISITES:
  1. Refresh SSO login:  aws sso login --profile poweruser
  2. Then run:           python dev4-amazon-tests/amazon_test.py

This script tests:
  - Nova Canvas (image generation)
  - Titan Image Generator (image generation)
  - Nova Reel (video generation)
"""
import json
import os
import sys
import base64
import time

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# Admin confirmed: PowerUserAccess allows bedrock:* and bedrock-runtime:*
# Profile "kaurlections" not configured on this machine — using "poweruser" SSO profile
# which maps to the same account (823766426087) with PowerUserAccess role.
PROFILE = "poweruser"
REGION = "us-east-1"


def get_session():
    import boto3
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    # Verify credentials
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print(f"Authenticated as: {identity['Arn']}")
    return session


def list_image_video_models(session):
    """List available image and video generation models."""
    print("\n" + "=" * 60)
    print("AVAILABLE IMAGE/VIDEO MODELS")
    print("=" * 60)
    bedrock = session.client("bedrock")
    models = bedrock.list_foundation_models()["modelSummaries"]

    image_models = []
    video_models = []
    for m in models:
        out = m.get("outputModalities", [])
        if "IMAGE" in out:
            image_models.append(m)
        if "VIDEO" in out:
            video_models.append(m)

    print(f"\nImage generation models ({len(image_models)}):")
    for m in image_models:
        print(f"  {m['modelId']} - {m.get('modelName', '?')} [{m.get('providerName', '?')}]")

    print(f"\nVideo generation models ({len(video_models)}):")
    for m in video_models:
        print(f"  {m['modelId']} - {m.get('modelName', '?')} [{m.get('providerName', '?')}]")

    return image_models, video_models


def test_nova_canvas(session):
    """Test image generation with Amazon Nova Canvas."""
    print("\n" + "=" * 60)
    print("TEST: Amazon Nova Canvas (Image Generation)")
    print("=" * 60)

    model_id = "amazon.nova-canvas-v1:0"
    prompt = "A modern, clean digital marketing banner for an AI-powered SEO tool. Blue and white color scheme, professional, minimalist design with abstract tech elements."

    body = json.dumps({
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": prompt,
        },
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "height": 1024,
            "width": 1024,
            "quality": "standard",
        },
    })

    print(f"  Model: {model_id}")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"  Size: 1024x1024")
    print(f"  Generating...")

    try:
        bedrock_rt = session.client("bedrock-runtime")
        t0 = time.time()
        response = bedrock_rt.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        elapsed = time.time() - t0
        result = json.loads(response["body"].read())
        images = result.get("images", [])

        if images:
            img_bytes = base64.b64decode(images[0])
            out_path = os.path.join(OUTPUTS_DIR, "nova_canvas_test.png")
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            print(f"  SUCCESS in {elapsed:.1f}s")
            print(f"  Image size: {len(img_bytes)} bytes")
            print(f"  Saved to: {out_path}")
            return True
        else:
            print(f"  FAILED: No images in response")
            print(f"  Response: {json.dumps(result)[:300]}")
            return False
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def test_titan_image(session):
    """Test image generation with Amazon Titan Image Generator."""
    print("\n" + "=" * 60)
    print("TEST: Amazon Titan Image Generator (Image Generation)")
    print("=" * 60)

    model_id = "amazon.titan-image-generator-v2:0"
    prompt = "Professional social media post graphic for AI SEO platform, modern gradient background, clean typography space, tech-inspired design"

    body = json.dumps({
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": prompt,
        },
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "height": 1024,
            "width": 1024,
            "quality": "standard",
        },
    })

    print(f"  Model: {model_id}")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"  Generating...")

    try:
        bedrock_rt = session.client("bedrock-runtime")
        t0 = time.time()
        response = bedrock_rt.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        elapsed = time.time() - t0
        result = json.loads(response["body"].read())
        images = result.get("images", [])

        if images:
            img_bytes = base64.b64decode(images[0])
            out_path = os.path.join(OUTPUTS_DIR, "titan_image_test.png")
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            print(f"  SUCCESS in {elapsed:.1f}s")
            print(f"  Image size: {len(img_bytes)} bytes")
            print(f"  Saved to: {out_path}")
            return True
        else:
            print(f"  FAILED: No images in response")
            return False
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def test_nova_reel(session):
    """Test video generation with Amazon Nova Reel."""
    print("\n" + "=" * 60)
    print("TEST: Amazon Nova Reel (Video Generation)")
    print("=" * 60)

    model_id = "amazon.nova-reel-v1:0"
    prompt = "A smooth animated logo reveal for an AI SEO platform, blue gradient background, modern tech aesthetic"

    print(f"  Model: {model_id}")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"  NOTE: Nova Reel requires S3 output bucket and is async (takes ~90s for 6s video)")

    # Nova Reel uses StartAsyncInvoke, not InvokeModel
    # It requires an S3 bucket for output — check if we have one
    try:
        bedrock_rt = session.client("bedrock-runtime")

        # Nova Reel uses start_async_invoke which needs S3 destination
        # We cannot test without an S3 bucket configured
        print(f"  SKIPPED: Nova Reel requires S3 output bucket (async generation)")
        print(f"  To test manually:")
        print(f"    1. Create S3 bucket for video output")
        print(f"    2. Use bedrock-runtime.start_async_invoke()")
        print(f"    3. Poll for completion (~90s for 6s video)")
        return None  # Not tested, not failed
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def main():
    print("=" * 60)
    print("AMAZON IMAGE/VIDEO GENERATION TEST")
    print("Isolated test — no main project imports")
    print("=" * 60)

    # Step 1: Authenticate
    try:
        session = get_session()
    except Exception as e:
        print(f"\nAWS AUTHENTICATION FAILED: {e}")
        print("\nTo fix, run in your terminal:")
        print("  aws sso login --profile poweruser")
        print("Then re-run this script.")
        sys.exit(1)

    # Step 2: List available models
    image_models, video_models = list_image_video_models(session)

    # Step 3: Test image generation
    nova_canvas_ok = test_nova_canvas(session)
    titan_ok = test_titan_image(session)

    # Step 4: Test video generation
    nova_reel_ok = test_nova_reel(session)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Nova Canvas (image):  {'PASS' if nova_canvas_ok else 'FAIL' if nova_canvas_ok is False else 'NOT TESTED'}")
    print(f"  Titan Image (image):  {'PASS' if titan_ok else 'FAIL' if titan_ok is False else 'NOT TESTED'}")
    print(f"  Nova Reel (video):    {'PASS' if nova_reel_ok else 'FAIL' if nova_reel_ok is False else 'SKIPPED (needs S3)'}")
    print(f"  Image models found:   {len(image_models)}")
    print(f"  Video models found:   {len(video_models)}")
    print(f"  Outputs saved to:     {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
