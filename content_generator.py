"""
content_generator.py
AI-Optimized Content Generation Pipeline

Generates content snippets optimized for AI engine citation:
- FAQ sections with schema markup
- Comparison content
- Feature descriptions
- Meta descriptions

Routes through EC2 Bedrock (Claude) for generation.
"""

import json
import logging
import os
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

EC2_GEO_ENGINE_URL = os.environ.get("GEO_ENGINE_URL", "http://54.226.251.216:5005")
EC2_TIMEOUT = int(os.environ.get("GEO_ENGINE_TIMEOUT", "45"))


def _call_ec2_generate(prompt: str) -> str:
    """Call EC2 /generate endpoint for content generation via Bedrock."""
    url = f"{EC2_GEO_ENGINE_URL}/generate"
    try:
        resp = requests.post(url, json={"prompt": prompt}, timeout=EC2_TIMEOUT)
        if resp.status_code == 200:
            return resp.json().get("text", "")
    except Exception as e:
        logger.warning("EC2 generate failed, using fallback: %s", e)
    return ""


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Content type generators ───────────────────────────────────────────────────

def generate_faq(brand_name: str, topic: str, count: int = 5) -> dict:
    """Generate FAQ content optimized for AI engines."""
    prompt = (
        f"Generate {count} frequently asked questions and answers about {brand_name} "
        f"related to '{topic}'. Format each as:\n"
        f"Q: [question]\nA: [concise 2-3 sentence answer]\n\n"
        f"Make answers factual, specific, and authoritative. "
        f"Include concrete details like features, pricing tiers, or use cases."
    )
    raw = _call_ec2_generate(prompt)

    # Also generate the JSON-LD schema
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [],
    }

    # Parse Q&A pairs from Claude's response
    import re
    pairs = re.findall(r'Q:\s*(.+?)\nA:\s*(.+?)(?=\nQ:|\Z)', raw, re.DOTALL)
    faqs = []
    for q, a in pairs:
        q, a = q.strip(), a.strip()
        faqs.append({"question": q, "answer": a})
        schema["mainEntity"].append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {"@type": "Answer", "text": a},
        })

    return {
        "type": "faq",
        "brand_name": brand_name,
        "topic": topic,
        "faqs": faqs,
        "schema_json_ld": json.dumps(schema, indent=2),
        "raw_content": raw,
        "timestamp": _now(),
    }


def generate_comparison(brand_name: str, competitors: list[str], category: str) -> dict:
    """Generate comparison content for brand vs competitors."""
    comp_list = ", ".join(competitors[:5])
    prompt = (
        f"Write a brief, objective comparison of {brand_name} vs {comp_list} "
        f"for the '{category}' category. For each, list 2-3 key strengths. "
        f"End with a summary of which is best for different use cases. "
        f"Be factual and balanced."
    )
    raw = _call_ec2_generate(prompt)
    return {
        "type": "comparison",
        "brand_name": brand_name,
        "competitors": competitors,
        "category": category,
        "content": raw,
        "timestamp": _now(),
    }


def generate_meta_description(brand_name: str, page_topic: str) -> dict:
    """Generate AI-optimized meta description."""
    prompt = (
        f"Write 3 meta description options (max 155 chars each) for a page about "
        f"'{page_topic}' by {brand_name}. Each should be compelling, include the brand, "
        f"and be optimized for AI engine extraction. Return only the 3 options, numbered."
    )
    raw = _call_ec2_generate(prompt)
    import re
    options = re.findall(r'\d+[.)]\s*(.+)', raw)
    return {
        "type": "meta_description",
        "brand_name": brand_name,
        "topic": page_topic,
        "options": [o.strip()[:160] for o in options[:3]],
        "timestamp": _now(),
    }


def generate_feature_snippet(brand_name: str, feature: str) -> dict:
    """Generate a concise feature description optimized for AI citation."""
    prompt = (
        f"Write a concise, factual 3-4 sentence description of {brand_name}'s "
        f"'{feature}' feature. Include specific capabilities and what makes it "
        f"stand out. Write in third person, suitable for an AI to cite as a source."
    )
    raw = _call_ec2_generate(prompt)
    return {
        "type": "feature_snippet",
        "brand_name": brand_name,
        "feature": feature,
        "content": raw,
        "timestamp": _now(),
    }


def generate_content(
    brand_name: str,
    content_type: str,
    topic: str = "",
    competitors: list[str] = None,
    count: int = 5,
) -> dict:
    """
    Unified content generation entry point.

    content_type: faq | comparison | meta_description | feature_snippet
    """
    if content_type == "faq":
        return generate_faq(brand_name, topic, count=count)
    elif content_type == "comparison":
        return generate_comparison(brand_name, competitors or [], topic)
    elif content_type == "meta_description":
        return generate_meta_description(brand_name, topic)
    elif content_type == "feature_snippet":
        return generate_feature_snippet(brand_name, topic)
    else:
        raise ValueError(f"Unknown content_type: {content_type}. Use: faq, comparison, meta_description, feature_snippet")
