"""
test_publishers.py
Test Buffer and Postiz publisher stubs — dry-run and configuration checks.
Run: python dev4-tests/test_publishers.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_buffer_unconfigured():
    print("[TEST 1] Buffer - Unconfigured state")
    from buffer_publisher import BufferPublisher
    pub = BufferPublisher()
    assert not pub.configured
    result = pub.publish("Test post", platform="Twitter/X")
    assert not result["success"]
    assert "BUFFER_API_KEY" in result["error"]
    print("  PASS: Buffer correctly reports unconfigured")


def test_buffer_dry_run():
    print("\n[TEST 2] Buffer - Dry-run with fake key")
    from buffer_publisher import BufferPublisher
    pub = BufferPublisher(api_key="fake-key-for-testing")
    assert pub.configured

    os.environ["BUFFER_CHANNEL_X"] = "fake-channel-id"
    try:
        result = pub.publish("Test post #AISEO", platform="Twitter/X", dry_run=True)
        assert result["success"], f"Dry-run should succeed: {result}"
        assert "query" in result["data"]
        assert "createPost" in result["data"]["query"]
        print(f"  PASS: Buffer dry-run generated valid GraphQL mutation")
    finally:
        os.environ.pop("BUFFER_CHANNEL_X", None)


def test_buffer_platform_mapping():
    print("\n[TEST 3] Buffer - Platform name mapping")
    from buffer_publisher import CHANNEL_ENV
    assert CHANNEL_ENV["twitter/x"] == "BUFFER_CHANNEL_X"
    assert CHANNEL_ENV["instagram"] == "BUFFER_CHANNEL_IG"
    assert CHANNEL_ENV["facebook"] == "BUFFER_CHANNEL_FB"
    assert CHANNEL_ENV["linkedin"] == "BUFFER_CHANNEL_LI"
    print("  PASS: All platform mappings correct")


def test_postiz_unconfigured():
    print("\n[TEST 4] Postiz - Unconfigured state")
    from postiz_publisher import PostizPublisher
    pub = PostizPublisher()
    assert not pub.configured
    result = pub.publish("Test", "Twitter/X")
    assert not result["success"]
    assert "POSTIZ_API_KEY" in result["error"]
    print("  PASS: Postiz correctly reports unconfigured")


def test_postiz_dry_run():
    print("\n[TEST 5] Postiz - Dry-run with fake key")
    from postiz_publisher import PostizPublisher
    pub = PostizPublisher(api_key="fake-key")

    os.environ["POSTIZ_INTEGRATION_X"] = "fake-integration-id"
    try:
        result = pub.publish("Test post", "Twitter/X", dry_run=True)
        assert result["success"], f"Dry-run should succeed: {result}"
        payload = result["data"]["payload"]
        assert payload["type"] == "now"
        assert len(payload["posts"]) == 1
        assert payload["posts"][0]["settings"]["__type"] == "x"
        print(f"  PASS: Postiz dry-run generated valid payload")
    finally:
        os.environ.pop("POSTIZ_INTEGRATION_X", None)


def test_postiz_platform_mapping():
    print("\n[TEST 6] Postiz - Platform name mapping")
    from postiz_publisher import PLATFORM_MAP
    assert PLATFORM_MAP["twitter/x"] == "x"
    assert PLATFORM_MAP["instagram"] == "instagram"
    assert PLATFORM_MAP["facebook"] == "facebook"
    assert PLATFORM_MAP["linkedin"] == "linkedin"
    print("  PASS: All platform mappings correct")


def test_postiz_schedule_mode():
    print("\n[TEST 7] Postiz - Schedule mode payload")
    from postiz_publisher import PostizPublisher
    pub = PostizPublisher(api_key="fake-key")
    os.environ["POSTIZ_INTEGRATION_LI"] = "fake-li-id"
    try:
        result = pub.publish(
            "Scheduled LinkedIn post",
            "LinkedIn",
            scheduled_at="2026-04-01T10:00:00Z",
            dry_run=True,
        )
        assert result["success"]
        payload = result["data"]["payload"]
        assert payload["type"] == "schedule"
        assert payload["date"] == "2026-04-01T10:00:00Z"
        print("  PASS: Schedule mode sets correct type and date")
    finally:
        os.environ.pop("POSTIZ_INTEGRATION_LI", None)


if __name__ == "__main__":
    print("=" * 60)
    print("Publishing Bridge Test Suite (Buffer + Postiz)")
    print("=" * 60)
    test_buffer_unconfigured()
    test_buffer_dry_run()
    test_buffer_platform_mapping()
    test_postiz_unconfigured()
    test_postiz_dry_run()
    test_postiz_platform_mapping()
    test_postiz_schedule_mode()
    print("\n" + "=" * 60)
    print("ALL 7 TESTS PASSED")
    print("=" * 60)
