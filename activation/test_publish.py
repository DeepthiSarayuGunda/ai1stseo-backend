"""
activation/test_publish.py
Sends 1 test post to 1 platform via the social orchestrator.

Run: python activation/test_publish.py [platform]
Default platform: linkedin

Does NOT modify the orchestrator. Just calls publish_post().
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

platform = sys.argv[1] if len(sys.argv) > 1 else "linkedin"

print("=" * 60)
print(f"  TEST PUBLISH — {platform.upper()}")
print("=" * 60)

from growth.social_orchestrator import publish_post

result = publish_post({
    "content": f"Test post from AI1stSEO growth automation. Verifying {platform} publishing pipeline. #AISEO #TestPost",
    "platform": platform,
    "post_id": None,
    "scheduled_at": None,
})

print(f"\n  Success: {result.get('success')}")
print(f"  Provider: {result.get('provider')}")
if result.get("success"):
    print(f"  Result: {json.dumps(result.get('result', {}), indent=4, default=str)}")
else:
    print(f"  Error: {result.get('error')}")
    if result.get("status") == "provider_unavailable":
        print("\n  No publisher configured. Run setup_social_env.py first.")

print(f"\n{'='*60}")
