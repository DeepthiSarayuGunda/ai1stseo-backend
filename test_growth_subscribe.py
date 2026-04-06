"""
test_growth_subscribe.py
Standalone test for POST /api/growth/subscribe
Does NOT modify any Flask or DB code.
"""

import requests

BASE = "http://localhost:5001"

tests = [
    ("Valid email", {"email": "test@example.com"}),
    ("Duplicate email (same again)", {"email": "test@example.com"}),
    ("Invalid email", {"email": "not-an-email"}),
    ("Missing email", {"name": "No Email"}),
    ("Full payload", {
        "email": "full@example.com",
        "name": "Jane Doe",
        "source": "website",
        "platform": "homepage_footer",
        "campaign": "launch_2026",
        "opted_in": True,
    }),
]

print(f"Testing POST {BASE}/api/growth/subscribe\n{'='*60}")

for label, payload in tests:
    print(f"\n--- {label} ---")
    print(f"Payload: {payload}")
    try:
        resp = requests.post(
            f"{BASE}/api/growth/subscribe",
            json=payload,
            timeout=10,
        )
        print(f"Status:  {resp.status_code}")
        try:
            print(f"JSON:    {resp.json()}")
        except Exception:
            print(f"Text:    {resp.text[:500]}")
    except requests.ConnectionError:
        print("ERROR:   Could not connect. Is the app running on port 5001?")
    except Exception as e:
        print(f"ERROR:   {e}")

print(f"\n{'='*60}\nDone.")
