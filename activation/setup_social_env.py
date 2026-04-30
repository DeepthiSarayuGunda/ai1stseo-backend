"""
activation/setup_social_env.py
Validates social publishing credentials and prints connected platforms.

Run: python activation/setup_social_env.py
"""

import os
import sys

print("=" * 60)
print("  SOCIAL PUBLISHING — CREDENTIAL CHECK")
print("=" * 60)

checks = []

# Buffer
buffer_key = os.environ.get("BUFFER_API_KEY", "")
if buffer_key:
    print("\n  ✓ BUFFER_API_KEY is set")
    checks.append(("Buffer API Key", True))
    for name, env in [("LinkedIn", "BUFFER_CHANNEL_LI"), ("X/Twitter", "BUFFER_CHANNEL_X"),
                      ("Instagram", "BUFFER_CHANNEL_IG"), ("Facebook", "BUFFER_CHANNEL_FB")]:
        val = os.environ.get(env, "")
        status = "✓" if val else "✗"
        checks.append((f"Buffer {name}", bool(val)))
        print(f"    {status} {env}: {'set' if val else 'NOT SET'}")
else:
    print("\n  ✗ BUFFER_API_KEY: NOT SET")
    checks.append(("Buffer API Key", False))

# Postiz
postiz_key = os.environ.get("POSTIZ_API_KEY", "")
if postiz_key:
    print("\n  ✓ POSTIZ_API_KEY is set")
    checks.append(("Postiz API Key", True))
    for name, env in [("LinkedIn", "POSTIZ_INTEGRATION_LI"), ("X/Twitter", "POSTIZ_INTEGRATION_X"),
                      ("Instagram", "POSTIZ_INTEGRATION_IG"), ("Facebook", "POSTIZ_INTEGRATION_FB")]:
        val = os.environ.get(env, "")
        status = "✓" if val else "✗"
        checks.append((f"Postiz {name}", bool(val)))
        print(f"    {status} {env}: {'set' if val else 'NOT SET'}")
else:
    print("\n  ✗ POSTIZ_API_KEY: NOT SET")
    checks.append(("Postiz API Key", False))

# Preference
pref = os.environ.get("SOCIAL_PUBLISHER_PREFERENCE", "buffer")
print(f"\n  Publisher preference: {pref}")

# Orchestrator check
print("\n  Orchestrator discovery test:")
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from growth.social_orchestrator import discover_publisher
    pub, name = discover_publisher()
    if pub:
        print(f"    ✓ Active publisher: {name}")
    else:
        print("    ✗ No publisher configured — set API keys above")
except Exception as e:
    print(f"    ✗ Error: {e}")

passed = sum(1 for _, ok in checks if ok)
print(f"\n{'='*60}")
print(f"  {passed}/{len(checks)} checks passed")
if not buffer_key and not postiz_key:
    print("\n  ACTION REQUIRED:")
    print("  1. Sign up at https://buffer.com (free, 3 channels)")
    print("  2. Get API key from Settings > API")
    print("  3. Connect LinkedIn/X accounts")
    print("  4. Set environment variables:")
    print('     $env:BUFFER_API_KEY="your-key"')
    print('     $env:BUFFER_CHANNEL_LI="channel-id"')
print(f"{'='*60}")
