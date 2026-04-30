"""
final_features/image_generator.py
Image generation with AI (OpenAI DALL-E), Pexels, and placeholder fallback.

Priority chain:
  1. OPENAI_API_KEY set -> generate via DALL-E
  2. PEXELS_API_KEY set -> fetch from Pexels
  3. Neither -> return curated placeholders

All paths return the same shape so callers never break.

Usage:
    from final_features.image_generator import generate_image
    result = generate_image("SEO strategies")
"""

import hashlib
import logging
import os

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

PLACEHOLDERS = [
    {"url": "https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg",
     "description": "Team collaboration at desk"},
    {"url": "https://images.pexels.com/photos/590016/pexels-photo-590016.jpeg",
     "description": "Analytics dashboard on screen"},
    {"url": "https://images.pexels.com/photos/265087/pexels-photo-265087.jpeg",
     "description": "SEO and digital marketing concept"},
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def generate_image(topic: str) -> dict:
    """Generate or fetch images for a topic.

    Returns:
        {
            "success": bool,
            "image_url": str,
            "images": list[dict],
            "source": str,          # "ai", "pexels", "placeholder"
            "topic": str,
        }
    """
    if not topic or not topic.strip():
        return {"success": False, "error": "Topic is required"}

    topic = topic.strip()

    # Priority 1: OpenAI DALL-E
    if OPENAI_API_KEY:
        result = _generate_openai(topic)
        if result.get("success"):
            return result
        logger.warning("OpenAI image gen failed, falling back to Pexels")

    # Priority 2: Pexels API
    if PEXELS_API_KEY:
        result = _fetch_pexels(topic)
        if result.get("success"):
            return result
        logger.warning("Pexels failed, falling back to placeholders")

    # Priority 3: Placeholders
    logger.info("Using placeholders for: %s", topic[:40])
    return {
        "success": True,
        "image_url": PLACEHOLDERS[0]["url"],
        "images": PLACEHOLDERS,
        "source": "placeholder",
        "topic": topic,
    }


# ---------------------------------------------------------------------------
# OpenAI DALL-E
# ---------------------------------------------------------------------------

def _generate_openai(topic: str) -> dict:
    """Generate image via OpenAI DALL-E API."""
    try:
        import openai
    except ImportError:
        logger.info("openai package not installed — skipping AI image gen")
        return {"success": False, "error": "openai not installed"}

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            "Professional, clean social media graphic for the topic: "
            + topic
            + ". Modern design, suitable for LinkedIn and Instagram."
        )

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        url = response.data[0].url
        revised_prompt = getattr(response.data[0], "revised_prompt", "")

        # Try to download and save locally
        local_path = _download_image(url, topic)

        images = [{
            "url": url,
            "local_path": local_path,
            "description": revised_prompt[:200] if revised_prompt else "AI-generated image for " + topic,
        }]

        return {
            "success": True,
            "image_url": url,
            "local_path": local_path,
            "images": images,
            "source": "ai",
            "topic": topic,
        }

    except Exception as e:
        logger.warning("OpenAI image generation failed: %s", e)
        return {"success": False, "error": str(e)}


def _download_image(url: str, topic: str) -> str:
    """Download image to output/ directory. Returns local path or empty string."""
    try:
        import requests
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        topic_hash = hashlib.md5(topic.lower().encode()).hexdigest()[:10]
        filename = "img_" + topic_hash + ".png"
        filepath = os.path.join(OUTPUT_DIR, filename)

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        logger.info("Image saved to %s", filepath)
        return filepath
    except Exception as e:
        logger.debug("Image download failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Pexels API
# ---------------------------------------------------------------------------

def _fetch_pexels(topic: str) -> dict:
    """Fetch top 3 images from Pexels API."""
    try:
        import requests
        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": topic, "per_page": 3, "orientation": "landscape"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            photos = data.get("photos", [])
            if photos:
                images = []
                for p in photos:
                    src = p.get("src", {})
                    url = src.get("large2x") or src.get("original", "")
                    images.append({
                        "url": url,
                        "description": p.get("alt", ""),
                        "photographer": p.get("photographer", ""),
                    })
                return {
                    "success": True,
                    "image_url": images[0]["url"],
                    "images": images,
                    "source": "pexels",
                    "topic": topic,
                }
        logger.warning("Pexels returned %d", resp.status_code)
    except Exception as e:
        logger.warning("Pexels fetch failed: %s", e)

    return {"success": False, "error": "Pexels fetch failed"}
