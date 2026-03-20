#!/usr/bin/env python3
"""
validate_geo_probe.py
End-to-end validation of the GEO probe using AWS Bedrock (no API keys).

Run on EC2:  python3 validate_geo_probe.py
"""

import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from bedrock_helper import invoke_claude
from geo_probe_service import geo_probe

PAYLOADS = [
    {"brand_name": "Notion", "keyword": "best all-in-one workspace tools for team collaboration and documentation"},
    {"brand_name": "RandomBrandXYZ123", "keyword": "best project management tools"},
]


def divider(label: str):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")


def validate():
    # Step 1 — verify Bedrock connectivity
    divider("Step 1: Bedrock connectivity check")
    try:
        raw = invoke_claude("Say hello in one sentence.")
        print(f"  Bedrock OK — response: {raw[:120]}")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # Step 2 — run each payload
    for i, payload in enumerate(PAYLOADS, 1):
        divider(f"Step 2.{i}: GEO probe — brand={payload['brand_name']!r}")
        try:
            result = geo_probe(payload["brand_name"], payload["keyword"])
            print(json.dumps(result, indent=2))

            # assertions
            assert result["ai_model"] == "claude-bedrock", "ai_model mismatch"
            assert result["keyword"] == payload["keyword"], "keyword mismatch"
            assert isinstance(result["cited"], bool), "cited must be bool"
            assert "timestamp" in result, "missing timestamp"

            if result["cited"]:
                assert result["citation_context"] is not None, "cited=true but no context"
                print(f"  PASS — brand cited, context extracted")
            else:
                assert result["citation_context"] is None, "cited=false but context present"
                print(f"  PASS — brand not cited (expected for fake brand)")

        except AssertionError as e:
            print(f"  ASSERTION FAIL: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"  ERROR: {e}")
            sys.exit(1)

    divider("All validations passed")
    print("  GEO probe is working end-to-end via AWS Bedrock.")
    print("  No API keys used — IAM role credentials only.\n")


if __name__ == "__main__":
    validate()
