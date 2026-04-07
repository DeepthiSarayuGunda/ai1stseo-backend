"""
test_reddit_publisher.py
Test the Reddit publisher stub — dry-run and configuration checks.
Run: python dev4-tests/test_reddit_publisher.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reddit_publisher import RedditPublisher


def test_unconfigured():
    """Test that publisher reports unconfigured when no env vars set."""
    print("[TEST 1] Unconfigured state")
    pub = RedditPublisher()
    assert not pub.configured, "Should be unconfigured without env vars"
    result = pub.publish("Test", "Body", "test")
    assert not result["success"]
    assert "not configured" in result["error"].lower()
    print("  PASS: Correctly reports unconfigured")


def test_dry_run_with_fake_creds():
    """Test dry-run mode with temporary fake credentials."""
    print("\n[TEST 2] Dry-run with fake credentials")
    os.environ["REDDIT_CLIENT_ID"] = "fake-client-id"
    os.environ["REDDIT_CLIENT_SECRET"] = "fake-secret"
    os.environ["REDDIT_USERNAME"] = "fake-user"
    os.environ["REDDIT_PASSWORD"] = "fake-pass"

    try:
        pub = RedditPublisher()
        assert pub.configured, "Should be configured with env vars set"

        result = pub.publish(
            title="Test Post from AI1stSEO",
            content="This is a dry-run test.",
            subreddit="test",
            dry_run=True,
        )
        assert result["success"], f"Dry-run should succeed: {result}"
        payload = result["data"]["payload"]
        assert payload["subreddit"] == "test"
        assert payload["title"] == "Test Post from AI1stSEO"
        assert payload["kind"] == "self"
        print(f"  PASS: Dry-run payload correct: {payload}")
    finally:
        # Clean up fake env vars
        for key in ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"]:
            os.environ.pop(key, None)


def test_is_configured_function():
    """Test the module-level is_configured() function."""
    print("\n[TEST 3] Module-level is_configured()")
    from reddit_publisher import is_configured
    assert not is_configured(), "Should be False without env vars"
    print("  PASS: is_configured() returns False")


if __name__ == "__main__":
    print("=" * 60)
    print("Reddit Publisher Test Suite")
    print("=" * 60)
    test_unconfigured()
    test_dry_run_with_fake_creds()
    test_is_configured_function()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
