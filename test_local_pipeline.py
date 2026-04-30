"""
test_local_pipeline.py
Local test runner — demonstrates the full content → queue → publish → duplicate flow.

Runs entirely in-process. No HTTP requests, no server required.
Monkey-patches the duplicate detector to use an in-memory store
so the duplicate detection works without DynamoDB.

Usage:
    python test_local_pipeline.py
"""

import logging
import sys
from datetime import datetime, timezone
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Logging — show all relevant output on console
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("test_local_pipeline")

# ---------------------------------------------------------------------------
# In-memory hash store — replaces DynamoDB for local testing
# ---------------------------------------------------------------------------
_local_hash_store: dict[str, str] = {}  # hash -> ISO timestamp


def _mock_is_duplicate(content, time_window_hours=None):
    """In-memory duplicate check."""
    from social_publishing.duplicate_detector import generate_content_hash
    h = generate_content_hash(content)
    if h in _local_hash_store:
        logger.info("  [DETECTOR] Duplicate detected: hash=%s...%s stored_at=%s",
                     h[:8], h[-4:], _local_hash_store[h])
        return True
    return False


def _mock_store_hash(content):
    """In-memory hash store."""
    from social_publishing.duplicate_detector import generate_content_hash
    h = generate_content_hash(content)
    now = datetime.now(timezone.utc).isoformat()
    _local_hash_store[h] = now
    logger.info("  [DETECTOR] Hash stored: %s...%s", h[:8], h[-4:])
    return h


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def separator(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def step(n: int, desc: str):
    print(f"\n  Step {n}: {desc}")
    print(f"  {'-' * 50}")


# ---------------------------------------------------------------------------
# Main test flow
# ---------------------------------------------------------------------------
def main():
    separator("LOCAL PIPELINE TEST: content -> queue -> publish -> duplicate")

    # Imports (all from social_publishing — no external deps)
    from social_publishing.content_bridge import (
        on_content_generated,
        detect_content_type,
        select_platforms,
        normalize_content_input,
    )
    from social_publishing.queue import flush_queue, stop_worker
    from social_publishing.duplicate_detector import generate_content_hash

    # Stop any background worker so flush_queue processes items synchronously
    stop_worker()

    # Fixed sample content (same every run so duplicate can be tested)
    sample_content = {
        "caption": "5 SEO tips every small business should know in 2026",
        "image_url": "https://cdn.ai1stseo.com/blog/seo-tips-2026.png",
        "source": "test_pipeline",
    }

    normalised = normalize_content_input(sample_content)
    content_hash = generate_content_hash(normalised)
    print(f"\n  Content hash: {content_hash[:16]}...{content_hash[-8:]}")

    # ------------------------------------------------------------------
    # STEP 1: Generate / normalise content
    # ------------------------------------------------------------------
    step(1, "Generate sample content")
    content_type = detect_content_type(sample_content)
    platforms = select_platforms(sample_content)
    print(f"  Content type : {content_type}")
    print(f"  Platforms    : {platforms}")
    print(f"  Text         : {normalised['text'][:60]}...")
    print(f"  Image        : {normalised['image_url']}")
    print("  -> Content generated")

    # ------------------------------------------------------------------
    # Patch: duplicate detector uses in-memory store,
    #        worker auto-start disabled so flush_queue works
    # ------------------------------------------------------------------
    with patch("social_publishing.duplicate_detector.is_duplicate", _mock_is_duplicate), \
         patch("social_publishing.duplicate_detector.store_hash", _mock_store_hash), \
         patch("social_publishing.queue._ensure_worker_running", lambda: None):

        # ------------------------------------------------------------------
        # STEP 2: First run — enqueue via content_bridge
        # ------------------------------------------------------------------
        step(2, "First run -- enqueue content")
        bridge_result = on_content_generated(sample_content, auto_publish=True)
        print(f"  Queue ID     : {bridge_result.get('queue_id')}")
        print(f"  Queued       : {bridge_result.get('queued')}")
        print(f"  Platforms    : {bridge_result.get('platforms')}")
        print("  -> Item queued")

        # ------------------------------------------------------------------
        # STEP 3: Flush queue — triggers _process_item -> publish_content
        # ------------------------------------------------------------------
        step(3, "Process queue (first run)")
        flush_result = flush_queue()
        print(f"  Processed    : {flush_result.get('processed')}")
        print(f"  Succeeded    : {flush_result.get('succeeded')}")
        print(f"  Failed       : {flush_result.get('failed')}")

        first_item = (flush_result.get("results") or [{}])[0]
        first_result = first_item.get("result", {})

        was_duplicate = first_result.get("duplicate", False)
        if was_duplicate:
            print("  X Unexpected: first run was flagged as duplicate!")
        else:
            print("  -> First run: published (or attempted -- no API keys is expected)")
            hash_stored = content_hash[:8] in str(_local_hash_store)
            status = "stored" if hash_stored else "skipped (publish failed, no API keys)"
            print(f"    Hash store : {status}")

        # If publish failed (no API keys), store_hash wasn't called by the
        # worker because it only stores on success. Simulate a successful
        # first publish so we can demonstrate the duplicate detection path.
        if content_hash not in _local_hash_store:
            print("\n  (Simulating successful first publish by storing hash)")
            _mock_store_hash(normalised)

        # ------------------------------------------------------------------
        # STEP 4: Second run — same content again
        # ------------------------------------------------------------------
        step(4, "Second run -- enqueue SAME content")
        bridge_result_2 = on_content_generated(sample_content, auto_publish=True)
        print(f"  Queue ID     : {bridge_result_2.get('queue_id')}")
        print("  -> Item queued (same content)")

        # ------------------------------------------------------------------
        # STEP 5: Flush queue — should detect duplicate and skip
        # ------------------------------------------------------------------
        step(5, "Process queue (second run -- expect duplicate skip)")
        flush_result_2 = flush_queue()
        print(f"  Processed    : {flush_result_2.get('processed')}")
        print(f"  Succeeded    : {flush_result_2.get('succeeded')}")
        print(f"  Failed       : {flush_result_2.get('failed')}")

        second_item = (flush_result_2.get("results") or [{}])[0]
        second_result = second_item.get("result", {})
        was_duplicate_2 = second_result.get("duplicate", False)
        was_skipped = second_result.get("skipped", False)

        if was_duplicate_2 and was_skipped:
            print("  -> Second run: duplicate skipped")
        else:
            print(f"  X Expected duplicate skip, got: {second_result}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    separator("RESULTS")
    print(f"  Hash store entries : {len(_local_hash_store)}")
    for h, ts in _local_hash_store.items():
        print(f"    {h[:16]}...{h[-8:]}  stored at {ts}")
    print()
    first_label = "published" if not was_duplicate else "duplicate (unexpected)"
    second_label = "duplicate skipped" if was_duplicate_2 else "NOT detected"
    print(f"  First run  : {first_label}")
    print(f"  Second run : {second_label}")
    print()

    if was_duplicate_2 and was_skipped:
        print("  TEST PASSED -- duplicate detection works end-to-end")
    else:
        print("  TEST FAILED -- duplicate was not caught on second run")

    print()
    return 0 if (was_duplicate_2 and was_skipped) else 1


if __name__ == "__main__":
    sys.exit(main())
