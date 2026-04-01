"""
reddit_publisher.py
Reddit publishing stub for the AI1stSEO social scheduler.

This is a starter integration — requires Reddit API credentials to function.
Uses PRAW (Python Reddit API Wrapper) when available, falls back to requests.

Environment variables:
    REDDIT_CLIENT_ID      — from reddit.com/prefs/apps
    REDDIT_CLIENT_SECRET  — from reddit.com/prefs/apps
    REDDIT_USERNAME       — Reddit account username
    REDDIT_PASSWORD       — Reddit account password
    REDDIT_USER_AGENT     — e.g. "ai1stseo-scheduler/1.0"
"""

import logging
import os

logger = logging.getLogger(__name__)


class RedditPublisher:
    """Stub publisher for Reddit integration."""

    def __init__(self):
        self.client_id = os.environ.get("REDDIT_CLIENT_ID", "")
        self.client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
        self.username = os.environ.get("REDDIT_USERNAME", "")
        self.password = os.environ.get("REDDIT_PASSWORD", "")
        self.user_agent = os.environ.get("REDDIT_USER_AGENT", "ai1stseo-scheduler/1.0")

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret and self.username)

    def publish(self, title, content, subreddit, dry_run=False):
        """
        Submit a text post to a subreddit.

        Args:
            title: Post title (required by Reddit)
            content: Post body (selftext)
            subreddit: Target subreddit name (without r/)
            dry_run: If True, return payload without posting
        """
        if not self.configured:
            return {
                "success": False,
                "error": "Reddit credentials not configured. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD.",
                "data": None,
            }

        payload = {
            "subreddit": subreddit,
            "title": title,
            "selftext": content,
            "kind": "self",
        }

        if dry_run:
            return {"success": True, "data": {"dry_run": True, "payload": payload}}

        try:
            import praw
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                username=self.username,
                password=self.password,
                user_agent=self.user_agent,
            )
            sub = reddit.subreddit(subreddit)
            submission = sub.submit(title=title, selftext=content)
            logger.info("Reddit post success: r/%s id=%s", subreddit, submission.id)
            return {
                "success": True,
                "data": {
                    "id": submission.id,
                    "url": f"https://reddit.com{submission.permalink}",
                    "subreddit": subreddit,
                },
            }
        except ImportError:
            return {
                "success": False,
                "error": "praw not installed. Run: pip install praw",
                "data": None,
            }
        except Exception as e:
            logger.error("Reddit post failed: %s", e)
            return {"success": False, "error": str(e), "data": None}


def is_configured():
    return RedditPublisher().configured


if __name__ == "__main__":
    pub = RedditPublisher()
    print(f"Reddit publisher configured: {pub.configured}")
    if not pub.configured:
        print("\nSet these env vars to use Reddit publishing:")
        print("  REDDIT_CLIENT_ID=...")
        print("  REDDIT_CLIENT_SECRET=...")
        print("  REDDIT_USERNAME=...")
        print("  REDDIT_PASSWORD=...")
        print("\nCreate an app at: https://www.reddit.com/prefs/apps")
    else:
        result = pub.publish(
            title="Test Post",
            content="This is a dry-run test from AI1stSEO scheduler.",
            subreddit="test",
            dry_run=True,
        )
        print(f"Dry-run result: {result}")
