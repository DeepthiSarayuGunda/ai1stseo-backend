"""
demo_full_system.py
Full system demo — exercises the complete publishing pipeline via HTTP API.

Demonstrates: generation -> queue -> duplicate detection -> dashboard -> control

Prerequisites:
    1. Start the server:  python app.py
    2. Set auth token:    set DEMO_AUTH_TOKEN=<your-cognito-access-token>
       (or pass as CLI arg: python demo_full_system.py <token>)
    3. Run this script:   python demo_full_system.py

If no auth token is provided, the script runs anyway and shows the
expected 401 responses — useful for verifying endpoint availability.
"""

import json
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = "http://127.0.0.1:5001"
PUBLISH_API = f"{BASE_URL}/api/publish"
GROWTH_API = f"{BASE_URL}/api/growth"

# Auth token from env var or CLI arg
TOKEN = ""
if len(sys.argv) > 1:
    TOKEN = sys.argv[1]
else:
    import os
    TOKEN = os.environ.get("DEMO_AUTH_TOKEN", "")

HEADERS = {}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"
HEADERS["Content-Type"] = "application/json"

# Fixed content for duplicate testing
SAMPLE_CONTENT = {
    "caption": "5 SEO strategies every small business needs in 2026",
    "image_url": "https://cdn.ai1stseo.com/blog/seo-strategies-2026.png",
    "platforms": ["twitter", "linkedin"],
    "source": "demo_script",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def separator(title):
    print()
    print("=" * 64)
    print(f"  {title}")
    print("=" * 64)


def step(n, desc):
    print(f"\n  STEP {n}: {desc}")
    print(f"  {'-' * 56}")


def api_post(url, data=None):
    """POST with error handling. Returns (status_code, json_body)."""
    try:
        resp = requests.post(url, json=data or {}, headers=HEADERS, timeout=30)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:200]}
        return resp.status_code, body
    except requests.ConnectionError:
        return 0, {"error": "Connection refused — is the server running?"}
    except Exception as e:
        return 0, {"error": str(e)}


def api_get(url):
    """GET with error handling. Returns (status_code, json_body)."""
    try:
        # Send empty JSON body so require_auth's get_json() doesn't fail
        resp = requests.get(url, json={}, headers=HEADERS, timeout=30)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:200]}
        return resp.status_code, body
    except requests.ConnectionError:
        return 0, {"error": "Connection refused — is the server running?"}
    except Exception as e:
        return 0, {"error": str(e)}


def print_result(status_code, body):
    """Print API response cleanly."""
    status_label = "OK" if 200 <= status_code < 300 else f"HTTP {status_code}"
    print(f"    Status: {status_label}")
    print(f"    Response:")
    for line in json.dumps(body, indent=4).split("\n"):
        print(f"      {line}")


# ---------------------------------------------------------------------------
# Main demo flow
# ---------------------------------------------------------------------------
def main():
    separator("SOCIAL PUBLISHING SYSTEM — FULL DEMO")

    if TOKEN:
        print(f"\n  Auth token: {TOKEN[:12]}...{TOKEN[-6:]}")
    else:
        print("\n  No auth token set. Endpoints requiring auth will return 401.")
        print("  Set DEMO_AUTH_TOKEN env var or pass as CLI arg to authenticate.")

    # Quick connectivity check
    print("\n  Checking server connectivity...")
    code, body = api_get(f"{BASE_URL}/")
    if code == 0:
        print(f"  ERROR: {body.get('error')}")
        print("  Start the server first: python app.py")
        return 1
    print(f"  Server is up (HTTP {code})")

    # ------------------------------------------------------------------
    # STEP 1: Generate & Publish (First Run)
    # ------------------------------------------------------------------
    step(1, "Generate & Publish (First Run)")
    print(f"    Endpoint: POST {PUBLISH_API}/content/submit")
    print(f"    Content:  {SAMPLE_CONTENT['caption'][:50]}...")

    code, body = api_post(f"{PUBLISH_API}/content/submit", SAMPLE_CONTENT)
    print_result(code, body)

    if code in (200, 201):
        print("    -> First publish completed")
    elif code == 401:
        print("    -> Auth required (expected without token)")
    else:
        print(f"    -> Unexpected response")

    print("    Waiting 3s for worker to process...")
    time.sleep(3)

    # ------------------------------------------------------------------
    # STEP 2: Duplicate Test (Same Content Again)
    # ------------------------------------------------------------------
    step(2, "Duplicate Test (Same Content Again)")
    print(f"    Endpoint: POST {PUBLISH_API}/content/submit")
    print(f"    Content:  (identical to Step 1)")

    code, body = api_post(f"{PUBLISH_API}/content/submit", SAMPLE_CONTENT)
    print_result(code, body)

    if code in (200, 201):
        print("    -> Second submit completed (duplicate check runs in queue worker)")
    elif code == 401:
        print("    -> Auth required (expected without token)")

    print("    Waiting 3s for worker to process duplicate check...")
    time.sleep(3)

    # ------------------------------------------------------------------
    # STEP 3: Fetch Dashboard Summary
    # ------------------------------------------------------------------
    step(3, "Fetch Dashboard Summary")
    print(f"    Endpoint: GET {PUBLISH_API}/dashboard/summary")

    code, body = api_get(f"{PUBLISH_API}/dashboard/summary")
    print_result(code, body)

    time.sleep(1)

    # ------------------------------------------------------------------
    # STEP 4: Fetch Recent Activity
    # ------------------------------------------------------------------
    step(4, "Fetch Recent Activity")
    print(f"    Endpoint: GET {PUBLISH_API}/dashboard/recent")

    code, body = api_get(f"{PUBLISH_API}/dashboard/recent")
    print_result(code, body)

    time.sleep(1)

    # ------------------------------------------------------------------
    # STEP 5: Pause System
    # ------------------------------------------------------------------
    step(5, "Pause System")
    print(f"    Endpoint: POST {PUBLISH_API}/control/pause")

    code, body = api_post(f"{PUBLISH_API}/control/pause")
    print_result(code, body)

    if code == 200 and body.get("status") == "paused":
        print("    -> System paused")

    time.sleep(1)

    # ------------------------------------------------------------------
    # STEP 6: Generate Content While Paused
    # ------------------------------------------------------------------
    step(6, "Generate Content While Paused")
    print(f"    Endpoint: POST {PUBLISH_API}/content/submit")

    paused_content = {
        "caption": "Why AI-powered SEO is the future of digital marketing",
        "platforms": ["linkedin"],
        "source": "demo_paused",
    }
    code, body = api_post(f"{PUBLISH_API}/content/submit", paused_content)
    print_result(code, body)

    if code in (200, 201):
        print("    -> Content added to queue while paused")

    time.sleep(1)

    # ------------------------------------------------------------------
    # STEP 7: Resume System
    # ------------------------------------------------------------------
    step(7, "Resume System")
    print(f"    Endpoint: POST {PUBLISH_API}/control/resume")

    code, body = api_post(f"{PUBLISH_API}/control/resume")
    print_result(code, body)

    if code == 200 and body.get("status") == "running":
        print("    -> System resumed")

    print("    Waiting 4s for worker to process queued items...")
    time.sleep(4)

    # ------------------------------------------------------------------
    # STEP 8: Final Dashboard Check
    # ------------------------------------------------------------------
    step(8, "Final Dashboard Check")
    print(f"    Endpoint: GET {PUBLISH_API}/dashboard/summary")

    code, body = api_get(f"{PUBLISH_API}/dashboard/summary")
    print_result(code, body)

    # Also check system status
    print(f"\n    Endpoint: GET {PUBLISH_API}/dashboard/system-status")
    code2, body2 = api_get(f"{PUBLISH_API}/dashboard/system-status")
    print_result(code2, body2)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    separator("DEMO COMPLETE")
    print("  Steps executed:")
    print("    1. Content submitted for publishing")
    print("    2. Duplicate content submitted (caught by queue worker)")
    print("    3. Dashboard summary retrieved")
    print("    4. Recent activity retrieved")
    print("    5. System paused")
    print("    6. Content queued while paused")
    print("    7. System resumed")
    print("    8. Final dashboard check")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
