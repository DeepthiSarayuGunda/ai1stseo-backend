"""Check Bedrock model access permissions in detail."""
import boto3
import json

session = boto3.Session(profile_name="poweruser", region_name="us-east-1")

# Check if models need to be explicitly enabled
bedrock = session.client("bedrock")

print("=" * 60)
print("BEDROCK MODEL ACCESS STATUS")
print("=" * 60)

# Check model access for our target models
targets = [
    "amazon.nova-canvas-v1:0",
    "amazon.titan-image-generator-v2:0",
    "amazon.nova-reel-v1:0",
    "amazon.nova-lite-v1:0",  # text model that already works
]

for model_id in targets:
    try:
        info = bedrock.get_foundation_model(modelIdentifier=model_id)
        m = info["modelDetails"]
        status = m.get("modelLifecycle", {}).get("status", "?")
        print(f"\n{model_id}:")
        print(f"  Name: {m.get('modelName', '?')}")
        print(f"  Status: {status}")
        print(f"  Input: {m.get('inputModalities', [])}")
        print(f"  Output: {m.get('outputModalities', [])}")
        print(f"  Streaming: {m.get('responseStreamingSupported', '?')}")
    except Exception as e:
        print(f"\n{model_id}: ERROR - {str(e)[:150]}")

# Try invoking Nova Lite (text) to see if text models work
print("\n" + "=" * 60)
print("QUICK TEXT MODEL TEST (Nova Lite)")
print("=" * 60)
try:
    bedrock_rt = session.client("bedrock-runtime")
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": "Say hello in one word."}]}],
        "inferenceConfig": {"maxTokens": 10, "temperature": 0.1},
    })
    resp = bedrock_rt.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(resp["body"].read())
    text = result["output"]["message"]["content"][0]["text"]
    print(f"  Nova Lite response: {text}")
    print(f"  STATUS: WORKING")
except Exception as e:
    print(f"  STATUS: FAILED - {str(e)[:200]}")

# Try with cross-region inference ID
print("\n" + "=" * 60)
print("CROSS-REGION MODEL ID TEST")
print("=" * 60)
cross_region_ids = [
    "us.amazon.nova-canvas-v1:0",
    "us.amazon.titan-image-generator-v2:0",
]
for model_id in cross_region_ids:
    try:
        body = json.dumps({
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": "A blue circle on white background"},
            "imageGenerationConfig": {"numberOfImages": 1, "height": 512, "width": 512, "quality": "standard"},
        })
        resp = bedrock_rt.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        print(f"  {model_id}: ACCESSIBLE")
    except Exception as e:
        err = str(e)[:200]
        print(f"  {model_id}: {err}")
