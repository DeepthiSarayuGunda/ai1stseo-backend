"""
ai_ranking_service.py
AI Ranking Recommendations — uses GEO probe results + page analysis
to suggest specific changes that improve AI citation likelihood.

Takes a URL + brand + keywords, runs probes, analyzes the page,
and returns prioritized recommendations.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _fetch_page(url: str, timeout: int = 10) -> BeautifulSoup:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AIRankBot/1.0)"}, timeout=timeout)
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "html.parser")


def _analyze_brand_presence(soup: BeautifulSoup, brand: str) -> dict:
    """How well is the brand represented on the page?"""
    text = soup.get_text().lower()
    brand_lower = brand.lower()
    mentions = len(re.findall(r'\b' + re.escape(brand_lower) + r'\b', text))
    in_title = brand_lower in (soup.title.string.lower() if soup.title and soup.title.string else "")
    in_h1 = any(brand_lower in h.get_text().lower() for h in soup.find_all("h1"))
    in_h2 = any(brand_lower in h.get_text().lower() for h in soup.find_all("h2"))
    in_meta = brand_lower in (
        (soup.find("meta", {"name": "description"}) or {}).get("content", "").lower()
    )
    return {
        "total_mentions": mentions,
        "in_title": in_title,
        "in_h1": in_h1,
        "in_h2": in_h2,
        "in_meta_description": in_meta,
    }


def _generate_recommendations(brand_presence: dict, brand: str, geo_results: list) -> list[dict]:
    """Generate prioritized recommendations based on analysis."""
    recs = []
    priority = 1

    # Based on GEO probe results
    cited_count = sum(1 for r in geo_results if r.get("brand_present") is True)
    total = len(geo_results)
    geo_score = cited_count / total if total else 0

    if geo_score < 0.3:
        recs.append({
            "priority": priority,
            "category": "ai_visibility",
            "title": "Critical: Low AI citation rate",
            "description": f"Brand cited in only {cited_count}/{total} AI queries ({geo_score:.0%})",
            "action": (
                f"Create comprehensive, authoritative content about {brand} "
                f"that directly answers common queries. AI models cite content "
                f"that is factual, well-structured, and widely referenced."
            ),
            "impact": "high",
        })
        priority += 1

    # Based on page brand presence
    bp = brand_presence
    if not bp["in_title"]:
        recs.append({
            "priority": priority,
            "category": "on_page",
            "title": f"Add '{brand}' to page title",
            "description": "Brand not found in title tag — title is a primary ranking signal",
            "action": f"Include '{brand}' naturally in your <title> tag",
            "impact": "high",
        })
        priority += 1

    if not bp["in_h1"]:
        recs.append({
            "priority": priority,
            "category": "on_page",
            "title": f"Add '{brand}' to H1 heading",
            "description": "Brand not in H1 — AI models weight headings heavily",
            "action": f"Include '{brand}' in your main H1 heading",
            "impact": "high",
        })
        priority += 1

    if not bp["in_meta_description"]:
        recs.append({
            "priority": priority,
            "category": "on_page",
            "title": "Add brand to meta description",
            "description": "Brand missing from meta description",
            "action": f"Mention '{brand}' in your meta description for AI snippet extraction",
            "impact": "medium",
        })
        priority += 1

    if bp["total_mentions"] < 5:
        recs.append({
            "priority": priority,
            "category": "content",
            "title": "Increase brand mention density",
            "description": f"Only {bp['total_mentions']} brand mentions on page",
            "action": f"Naturally mention '{brand}' 8-15 times across your content",
            "impact": "medium",
        })
        priority += 1

    # General AI optimization recommendations
    recs.append({
        "priority": priority,
        "category": "content_structure",
        "title": "Add FAQ section targeting AI queries",
        "description": "FAQ content is heavily favored by AI answer engines",
        "action": (
            "Add a FAQ section with 5-10 questions that users commonly ask about "
            f"'{brand}' and your product category. Use FAQPage schema markup."
        ),
        "impact": "high",
    })
    priority += 1

    recs.append({
        "priority": priority,
        "category": "authority",
        "title": "Add comparison content",
        "description": "AI models often cite comparison/review content",
        "action": (
            f"Create 'Best [category]' and '{brand} vs competitors' content. "
            "AI engines frequently pull from comparison articles."
        ),
        "impact": "medium",
    })
    priority += 1

    recs.append({
        "priority": priority,
        "category": "technical",
        "title": "Implement comprehensive Schema.org markup",
        "description": "Structured data helps AI engines understand your content",
        "action": "Add Organization, Product, FAQPage, and Review schema markup",
        "impact": "medium",
    })

    return recs


def get_ranking_recommendations(
    url: str,
    brand_name: str,
    geo_results: list = None,
) -> dict:
    """
    Analyze a page and return AI ranking recommendations.

    Args:
        url: Page URL to analyze
        brand_name: Brand to optimize for
        geo_results: Optional pre-computed GEO probe results
    """
    try:
        soup = _fetch_page(url)
    except Exception as e:
        raise RuntimeError(f"Could not fetch {url}: {e}")

    brand_presence = _analyze_brand_presence(soup, brand_name)
    recommendations = _generate_recommendations(
        brand_presence, brand_name, geo_results or []
    )

    high = sum(1 for r in recommendations if r["impact"] == "high")
    medium = sum(1 for r in recommendations if r["impact"] == "medium")

    return {
        "url": url,
        "brand_name": brand_name,
        "brand_presence": brand_presence,
        "recommendations": recommendations,
        "total_recommendations": len(recommendations),
        "high_impact": high,
        "medium_impact": medium,
        "summary": f"{high} high-impact and {medium} medium-impact recommendations for improving AI visibility.",
    }
