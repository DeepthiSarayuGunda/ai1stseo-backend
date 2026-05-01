"""
AI Content Automation Pipeline — Lambda Handler

Main pipeline flow:
  Trigger (CloudWatch cron) →
  Generate 2 articles (Nova) →
  Format newsletter (Haiku) →
  Generate social posts (Haiku) →
  Generate images (ComfyUI / Nova Canvas) →
  Upload all to S3 →
  Send posts to Postiz

Can also be invoked directly: python -m content_pipeline.handler
"""

import json
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event=None, context=None):
    """Main pipeline entry point."""
    start = time.time()
    ts = datetime.now(timezone.utc).isoformat()
    logger.info("Content pipeline started at %s", ts)

    results = {
        "timestamp": ts,
        "articles": [],
        "newsletter": None,
        "social_posts": [],
        "images": [],
        "postiz_results": [],
        "errors": [],
    }

    # ── Step 1: Generate articles ─────────────────────────────────────── #
    try:
        from content_pipeline.articles import generate_articles
        logger.info("Step 1: Generating articles...")
        articles = generate_articles(count=2)
        results["articles"] = [{"title": a.get("title"), "words": a.get("word_count")} for a in articles]
        logger.info("Generated %d articles", len(articles))
    except Exception as e:
        logger.error("Article generation failed: %s", e)
        results["errors"].append(f"articles: {str(e)[:200]}")
        articles = []

    # ── Step 2: Generate newsletter ───────────────────────────────────── #
    try:
        from content_pipeline.newsletter import generate_newsletter
        logger.info("Step 2: Generating newsletter...")
        newsletter = generate_newsletter(articles)
        results["newsletter"] = newsletter.get("subject_line", "failed")
        logger.info("Newsletter: %s", newsletter.get("subject_line", "?"))
    except Exception as e:
        logger.error("Newsletter generation failed: %s", e)
        results["errors"].append(f"newsletter: {str(e)[:200]}")
        newsletter = {}

    # ── Step 3: Generate social posts ─────────────────────────────────── #
    try:
        from content_pipeline.social import generate_social_posts
        logger.info("Step 3: Generating social posts...")
        social_posts = generate_social_posts(articles)
        results["social_posts"] = [p.get("hook", "")[:60] for p in social_posts]
        logger.info("Generated %d social posts", len(social_posts))
    except Exception as e:
        logger.error("Social post generation failed: %s", e)
        results["errors"].append(f"social: {str(e)[:200]}")
        social_posts = []

    # ── Step 4: Generate images ───────────────────────────────────────── #
    image_keys = []
    try:
        from content_pipeline.image_gen import generate_image
        logger.info("Step 4: Generating images...")
        for i, article in enumerate(articles):
            img_bytes = generate_image(article.get("title", "AI SEO"))
            if img_bytes:
                image_keys.append({"index": i, "size_kb": len(img_bytes) // 1024, "bytes": img_bytes})
                logger.info("Image %d: %d KB", i, len(img_bytes) // 1024)
    except Exception as e:
        logger.error("Image generation failed: %s", e)
        results["errors"].append(f"images: {str(e)[:200]}")

    # ── Step 5: Store everything in S3 ────────────────────────────────── #
    s3_keys = {"articles": [], "newsletter": None, "social": [], "images": []}
    try:
        from content_pipeline.storage import save_articles, save_newsletter, save_social_posts, save_image, get_image_url
        logger.info("Step 5: Saving to S3...")

        s3_keys["articles"] = save_articles(articles)
        if newsletter and not newsletter.get("error"):
            s3_keys["newsletter"] = save_newsletter(newsletter)
        s3_keys["social"] = save_social_posts(social_posts)

        for img in image_keys:
            key = save_image(img["bytes"], img["index"])
            s3_keys["images"].append(key)

        results["images"] = s3_keys["images"]
        logger.info("S3 upload complete: %d articles, %d social, %d images",
                     len(s3_keys["articles"]), len(s3_keys["social"]), len(s3_keys["images"]))
    except Exception as e:
        logger.error("S3 storage failed: %s", e)
        results["errors"].append(f"s3: {str(e)[:200]}")

    # ── Step 6: Publish to Postiz ─────────────────────────────────────── #
    try:
        from content_pipeline.publisher import publish_to_postiz, schedule_posts_throughout_day, is_configured
        logger.info("Step 6: Publishing to Postiz...")

        if not is_configured():
            logger.warning("Postiz not configured — skipping publishing")
            results["postiz_results"].append({"success": False, "error": "POSTIZ_API_KEY not set"})
        else:
            # Collect image bytes for each post
            img_list = []
            for i in range(len(social_posts)):
                if i < len(image_keys) and image_keys[i].get("bytes"):
                    img_list.append(image_keys[i]["bytes"])
                else:
                    img_list.append(None)

            # Schedule posts spread across the day
            pub_results = schedule_posts_throughout_day(social_posts, img_list)
            results["postiz_results"] = pub_results
            logger.info("Published %d posts to Postiz", len(pub_results))
    except Exception as e:
        logger.error("Postiz publishing failed: %s", e)
        results["errors"].append(f"postiz: {str(e)[:200]}")

    # ── Summary ───────────────────────────────────────────────────────── #
    elapsed = round(time.time() - start, 1)
    results["elapsed_seconds"] = elapsed
    results["status"] = "complete" if not results["errors"] else "partial"

    logger.info("Pipeline complete in %ss — %d articles, %d social, %d images, %d errors",
                elapsed, len(articles), len(social_posts), len(image_keys), len(results["errors"]))

    return {
        "statusCode": 200,
        "body": json.dumps(results, indent=2, default=str),
    }


# Allow direct execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = lambda_handler()
    print(json.dumps(json.loads(result["body"]), indent=2))
