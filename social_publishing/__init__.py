"""
social_publishing — Direct social media publishing system with automated pipeline.

Connects directly to Twitter/X, LinkedIn, Facebook, and Instagram APIs.
Provides a unified publish_content() function with:
  - Per-platform content formatting
  - Automatic retry on failure
  - DynamoDB post logging
  - Scheduling support (date/time input)
  - Queue-based processing for safe concurrent publishing
  - Content pipeline integration for fully automated posting

Usage (manual):
    from social_publishing import publish_content

    result = publish_content({
        "text": "Check out our new feature!",
        "image_url": "https://example.com/image.png",
        "platforms": ["twitter", "linkedin", "facebook", "instagram"],
    })

Usage (automated from content pipeline):
    from social_publishing.content_bridge import on_content_generated

    on_content_generated({
        "caption": "New blog post!",
        "image_url": "https://cdn.example.com/img.png",
    })

Usage (full pipeline with auto-publish):
    from social_publishing.pipeline_hook import run_pipeline_with_auto_publish

    result = run_pipeline_with_auto_publish(limit=5)
"""

from social_publishing.orchestrator import publish_content  # noqa: F401

__all__ = ["publish_content"]
