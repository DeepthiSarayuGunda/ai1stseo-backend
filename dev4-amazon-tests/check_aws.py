"""
check_aws.py — Standalone AWS access check.
Does NOT import anything from the main project.
"""
import os
import json

print("=" * 60)
print("AWS ACCESS CHECK")
print("=" * 60)

# 1. Check env vars
key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION_NAME", "")))
profile = os.environ.get("AWS_PROFILE", "")
print(f"AWS_ACCESS_KEY_ID set: {bool(key_id)}")
print(f"AWS_REGION: {region if region else 'not set'}")
print(f"AWS_PROFILE: {profile if profile else 'not set'}")

# 2. Check credentials via STS
try:
    import boto3
    session = boto3.Session(profile_name="poweruser", region_name=region or "us-east-1")
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print(f"Account: {identity['Account']}")
    print(f"ARN: {identity['Arn']}")
    print("AWS credentials: VALID")
    creds_ok = True
except Exception as e:
    print(f"AWS credentials: FAILED - {e}")
    creds_ok = False

if not creds_ok:
    print("\nSTOPPING: No valid AWS credentials. Cannot test Bedrock models.")
    exit(1)

# 3. Check Bedrock access
print("\n" + "=" * 60)
print("BEDROCK ACCESS CHECK")
print("=" * 60)

try:
    bedrock = session.client("bedrock", region_name=region or "us-east-1")
    # List foundation models — filter for image/video
    models = bedrock.list_foundation_models()
    all_models = models.get("modelSummaries", [])
    print(f"Total Bedrock models available: {len(all_models)}")

    # Find image generation models
    print("\nImage generation models:")
    image_models = [m for m in all_models if "IMAGE" in str(m.get("outputModalities", []))]
    if image_models:
        for m in image_models:
            print(f"  {m['modelId']} - {m.get('modelName', '?')} [{m.get('providerName', '?')}]")
    else:
        print("  NONE FOUND")

    # Find video generation models
    print("\nVideo generation models:")
    video_models = [m for m in all_models if "VIDEO" in str(m.get("outputModalities", []))]
    if video_models:
        for m in video_models:
            print(f"  {m['modelId']} - {m.get('modelName', '?')} [{m.get('providerName', '?')}]")
    else:
        print("  NONE FOUND")

    # Check specific models we care about
    print("\nSpecific model check:")
    target_models = [
        "amazon.nova-canvas-v1:0",
        "amazon.titan-image-generator-v1",
        "amazon.titan-image-generator-v2:0",
        "amazon.nova-reel-v1:0",
        "stability.stable-diffusion-xl-v1",
    ]
    for mid in target_models:
        found = any(m["modelId"] == mid for m in all_models)
        status = "AVAILABLE" if found else "NOT FOUND"
        print(f"  {mid}: {status}")

except Exception as e:
    print(f"Bedrock access: FAILED - {e}")
    print("\nSTOPPING: Cannot access Bedrock. Check IAM permissions.")
    exit(1)

print("\n" + "=" * 60)
print("ACCESS CHECK COMPLETE")
print("=" * 60)
