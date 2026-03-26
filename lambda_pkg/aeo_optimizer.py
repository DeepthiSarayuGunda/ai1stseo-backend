"""
aeo_optimizer.py
AEO (Answer Engine Optimization) — analyzes a webpage and returns
actionable recommendations to improve AI engine visibility.

Uses the GEO probe results + page content analysis to generate suggestions.
"""

import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _fetch_page(url: str, timeout: int = 10) -> BeautifulSoup:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AEOBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "html.parser")


def _check_schema_markup(soup: BeautifulSoup) -> list[dict]:
    """Check for structured data that helps AI engines."""
    issues = []
    json_ld = soup.find_all("script", {"type": "application/ld+json"})
    if not json_ld:
        issues.append({
            "type": "missing_schema",
            "severity": "high",
            "message": "No JSON-LD structured data found",
            "fix": "Add Schema.org JSON-LD markup (FAQPage, HowTo, Article, Product, etc.)",
        })
    else:
        import json as _json
        has_faq = False
        has_howto = False
        for block in json_ld:
            try:
                data = _json.loads(block.string or "")
                t = data.get("@type", "")
                if t == "FAQPage" or (isinstance(t, list) and "FAQPage" in t):
                    has_faq = True
                if t == "HowTo" or (isinstance(t, list) and "HowTo" in t):
                    has_howto = True
            except Exception:
                pass
        if not has_faq:
            issues.append({
                "type": "missing_faq_schema",
                "severity": "medium",
                "message": "No FAQPage schema found — FAQ schema boosts AI snippet selection",
                "fix": "Add FAQPage JSON-LD with common questions about your topic",
            })
    return issues


def _check_content_structure(soup: BeautifulSoup) -> list[dict]:
    """Check if content is structured for AI consumption."""
    issues = []
    text = soup.get_text()
    words = text.split()

    # Question-answer patterns
    questions = re.findall(r'[^.]*\?', text)
    if len(questions) < 2:
        issues.append({
            "type": "low_qa_density",
            "severity": "medium",
            "message": f"Only {len(questions)} questions found — AI engines favor Q&A content",
            "fix": "Add FAQ section with 5-10 common questions and concise answers",
        })

    # Lists and structured content
    lists = soup.find_all(["ul", "ol"])
    if len(lists) < 2:
        issues.append({
            "type": "low_list_usage",
            "severity": "low",
            "message": "Few lists found — structured lists improve AI extraction",
            "fix": "Use bullet/numbered lists for features, steps, comparisons",
        })

    # Headings hierarchy
    h2s = soup.find_all("h2")
    if len(h2s) < 3:
        issues.append({
            "type": "weak_heading_structure",
            "severity": "medium",
            "message": f"Only {len(h2s)} H2 headings — AI engines use headings to understand topics",
            "fix": "Add descriptive H2 headings for each major section",
        })

    # Content length
    if len(words) < 800:
        issues.append({
            "type": "thin_content",
            "severity": "high",
            "message": f"Only {len(words)} words — comprehensive content ranks better in AI",
            "fix": "Expand content to 1500+ words with detailed, authoritative information",
        })

    # Tables
    tables = soup.find_all("table")
    if not tables:
        issues.append({
            "type": "no_comparison_tables",
            "severity": "low",
            "message": "No comparison tables — tables help AI extract structured data",
            "fix": "Add comparison tables for features, pricing, or specifications",
        })

    return issues


def _check_meta_optimization(soup: BeautifulSoup) -> list[dict]:
    """Check meta tags for AI discoverability."""
    issues = []

    title = soup.find("title")
    title_text = title.string.strip() if title and title.string else ""
    if not title_text:
        issues.append({"type": "missing_title", "severity": "high",
                        "message": "No title tag", "fix": "Add a descriptive title tag"})
    elif len(title_text) > 60:
        issues.append({"type": "long_title", "severity": "low",
                        "message": f"Title is {len(title_text)} chars (>60)",
                        "fix": "Shorten title to under 60 characters"})

    desc = soup.find("meta", {"name": "description"})
    desc_text = desc.get("content", "").strip() if desc else ""
    if not desc_text:
        issues.append({"type": "missing_description", "severity": "high",
                        "message": "No meta description",
                        "fix": "Add a concise meta description (150-160 chars)"})

    # Open Graph
    og = soup.find("meta", {"property": "og:title"})
    if not og:
        issues.append({"type": "missing_og", "severity": "low",
                        "message": "No Open Graph tags",
                        "fix": "Add og:title, og:description, og:image for social/AI sharing"})

    return issues


def _check_authority_signals(soup: BeautifulSoup, text: str) -> list[dict]:
    """Check for E-E-A-T and authority signals AI engines look for."""
    issues = []

    if not re.search(r'(?:author|written by|byline)', text, re.I):
        issues.append({"type": "no_author", "severity": "medium",
                        "message": "No author attribution found",
                        "fix": "Add author name, bio, and credentials for E-E-A-T"})

    if not re.search(r'(?:updated|published|modified)\s*:?\s*\d', text, re.I):
        issues.append({"type": "no_date", "severity": "medium",
                        "message": "No publish/update date found",
                        "fix": "Show publish and last-updated dates"})

    if not re.search(r'(?:source|according to|study|research|cited)', text, re.I):
        issues.append({"type": "no_citations", "severity": "medium",
                        "message": "No source citations found",
                        "fix": "Cite authoritative sources, studies, and data"})

    return issues


def analyze_aeo(url: str, brand_name: str = None) -> dict:
    """
    Full AEO analysis for a URL.
    Returns issues grouped by category with an overall AEO score.
    """
    try:
        soup = _fetch_page(url)
    except Exception as e:
        raise RuntimeError(f"Could not fetch {url}: {e}")

    text = soup.get_text()
    all_issues = []
    all_issues.extend(_check_schema_markup(soup))
    all_issues.extend(_check_content_structure(soup))
    all_issues.extend(_check_meta_optimization(soup))
    all_issues.extend(_check_authority_signals(soup, text))

    # Score: start at 100, deduct per issue
    deductions = {"high": 15, "medium": 8, "low": 3}
    score = 100
    for issue in all_issues:
        score -= deductions.get(issue["severity"], 5)
    score = max(0, score)

    high = sum(1 for i in all_issues if i["severity"] == "high")
    medium = sum(1 for i in all_issues if i["severity"] == "medium")
    low = sum(1 for i in all_issues if i["severity"] == "low")

    return {
        "url": url,
        "aeo_score": score,
        "total_issues": len(all_issues),
        "severity_breakdown": {"high": high, "medium": medium, "low": low},
        "issues": all_issues,
        "recommendations_summary": (
            f"Fix {high} high-priority issues first. "
            f"{medium} medium and {low} low-priority improvements available."
        ),
    }
