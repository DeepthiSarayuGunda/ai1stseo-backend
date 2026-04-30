"""
AEO Visibility Engine — Real Search Data (No APIs, No Mocks)

Scrapes real search results (Startpage → Yahoo fallback) for
SEO-related queries, extracts titles/snippets/URLs, detects
brand + competitor mentions, and calculates a visibility score.

Usage:  python services/aeo_engine.py

Dependencies (already in requirements.txt):
  requests, beautifulsoup4, lxml
"""

import json
import os
import re
import sys
import time
import random
from datetime import datetime, timezone
from urllib.parse import urlparse, quote_plus, unquote

import requests
from bs4 import BeautifulSoup

# ── Paths ─────────────────────────────────────────────────────────────────── #

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "aeo_results.json")

# ── Queries ───────────────────────────────────────────────────────────────── #

QUERIES = [
    "best AI SEO tools",
    "what is AEO SEO",
    "top AI SEO platforms",
    "how to rank in ChatGPT search results",
]

# ── Detection targets ─────────────────────────────────────────────────────── #

BRAND_PATTERNS = [
    re.compile(r"ai1stseo", re.I),
    re.compile(r"ai1stseo\.com", re.I),
    re.compile(r"ai\s*1st\s*seo", re.I),
]

COMPETITORS = [
    ("Ahrefs",       re.compile(r"ahrefs", re.I)),
    ("SEMrush",      re.compile(r"semrush", re.I)),
    ("Surfer SEO",   re.compile(r"surfer\s?seo", re.I)),
    ("Moz",          re.compile(r"\bmoz\b", re.I)),
    ("Clearscope",   re.compile(r"clearscope", re.I)),
    ("MarketMuse",   re.compile(r"marketmuse", re.I)),
    ("Frase",        re.compile(r"\bfrase\b", re.I)),
    ("NeuronWriter", re.compile(r"neuronwriter", re.I)),
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


# ── Search scrapers ───────────────────────────────────────────────────────── #

def _make_session(ua=None):
    """Create a fresh requests session with browser-like headers."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": ua or random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return s


def search_startpage(query, max_results=5):
    """Scrape Startpage (Google proxy). Returns list of {title, snippet, url}."""
    session = _make_session()
    resp = session.post(
        "https://www.startpage.com/sp/search",
        data={"query": query, "cat": "web"},
        timeout=15,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for div in soup.select(".result"):
        if len(results) >= max_results:
            break

        # Title + URL from the result-link anchor
        a_tag = div.select_one("a.result-link")
        if not a_tag:
            continue
        href = a_tag.get("href", "")
        h2 = a_tag.select_one("h2")
        title = h2.get_text(strip=True) if h2 else a_tag.get_text(strip=True)

        # Snippet from p.description
        desc_el = div.select_one("p.description")
        snippet = desc_el.get_text(strip=True) if desc_el else ""

        if not title and not snippet:
            continue
        # Skip startpage internal links
        if "startpage.com" in href:
            continue

        results.append({"title": title, "snippet": snippet, "url": href})

    return results


def decode_yahoo_url(href):
    """Extract the real URL from Yahoo's redirect wrapper."""
    if "/RU=" in href:
        try:
            encoded = href.split("/RU=")[1].split("/RK=")[0]
            return unquote(encoded)
        except Exception:
            pass
    return href


def search_yahoo(query, max_results=5):
    """Scrape Yahoo search results. Returns list of {title, snippet, url}."""
    session = _make_session()
    url = f"https://search.yahoo.com/search?p={quote_plus(query)}&n=10"
    resp = session.get(url, timeout=15, allow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for div in soup.select("div.algo"):
        if len(results) >= max_results:
            break

        h3 = div.select_one("h3")
        title = h3.get_text(strip=True) if h3 else ""

        a_tag = div.select_one(".compTitle a")
        href = decode_yahoo_url(a_tag.get("href", "")) if a_tag else ""

        snippet_el = div.select_one(".compText")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

        if not title and not snippet:
            continue

        results.append({"title": title, "snippet": snippet, "url": href})

    return results


# Ordered list of search engines to try
_ENGINES = [
    ("startpage", search_startpage),
    ("yahoo", search_yahoo),
]


def fetch_search_results(query, max_results=5):
    """Try each search engine in order until one returns results."""
    for engine_name, engine_fn in _ENGINES:
        try:
            results = engine_fn(query, max_results)
            if results:
                return results, engine_name
        except Exception:
            pass
        # Brief pause before trying next engine
        time.sleep(random.uniform(0.5, 1.5))

    return [], None


# ── Detection ─────────────────────────────────────────────────────────────── #

def detect_brand(search_results):
    """Check if ai1stseo appears in any result title, snippet, or URL."""
    combined = " ".join(
        f"{r['title']} {r['snippet']} {r['url']}" for r in search_results
    )
    return any(p.search(combined) for p in BRAND_PATTERNS)


def detect_competitors(search_results):
    """Return list of competitor names found in results."""
    combined = " ".join(
        f"{r['title']} {r['snippet']} {r['url']}" for r in search_results
    )
    return [name for name, pat in COMPETITORS if pat.search(combined)]


def detect_content_patterns(search_results):
    """Detect content format patterns in top results."""
    combined = " ".join(f"{r['title']} {r['snippet']}" for r in search_results)
    patterns = []
    if re.search(r"\d+\s+(best|top|tools|platforms)", combined, re.I):
        patterns.append("list_content")
    if re.search(r"how to|step|guide|tutorial", combined, re.I):
        patterns.append("how_to_content")
    if re.search(r"vs\.?|versus|compar", combined, re.I):
        patterns.append("comparison_content")
    if re.search(r"\?|FAQ|question|answer", combined, re.I):
        patterns.append("qa_content")
    return patterns


def build_summary(query, search_results):
    """Build a readable summary from top results."""
    if not search_results:
        return f'No search results found for "{query}".'
    parts = []
    for i, r in enumerate(search_results[:3], 1):
        host = ""
        try:
            host = f" ({urlparse(r['url']).hostname})"
        except Exception:
            pass
        text = r["snippet"] or r["title"]
        parts.append(f"{i}. {text}{host}")
    return f'Top results for "{query}":\n' + "\n".join(parts)


# ── Insights & recommendations ────────────────────────────────────────────── #

def generate_insights(mentions_found, total_q, successful_q, score, comp_counts, patterns):
    insights = []

    if mentions_found == 0:
        insights.append(
            "ai1stseo.com does not appear in any top search results for target queries."
        )
        insights.append(
            "Competitors dominate search results — ai1stseo.com has no organic presence for these terms."
        )
    elif score < 50:
        insights.append(
            f"ai1stseo.com appeared in {mentions_found}/{successful_q} search queries — below 50% visibility."
        )
    else:
        insights.append(
            f"ai1stseo.com has strong search presence: found in {mentions_found}/{successful_q} queries."
        )

    top_comps = sorted(comp_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_comps:
        parts = ", ".join(f"{n} ({c}\u00d7)" for n, c in top_comps)
        insights.append(f"Top competitors in search results: {parts}")

    if "list_content" in patterns:
        insights.append(
            "Top-ranking pages use list-based content — this format is favored by AI retrieval systems."
        )
    if "comparison_content" in patterns:
        insights.append(
            "Comparison content (vs. pages) appears in results — a strong signal for AI citation."
        )
    if "qa_content" in patterns:
        insights.append(
            "FAQ and Q&A-style content is present in top results — AI engines prefer structured answers."
        )
    if "how_to_content" in patterns:
        insights.append(
            "How-to and tutorial content ranks well — step-by-step formats improve AI extractability."
        )

    failed = total_q - successful_q
    if failed > 0:
        insights.append(
            f"{failed} queries failed to return results — data may be incomplete."
        )

    return insights


def generate_recommendations(score, comp_counts, patterns):
    recs = [
        "Create content directly targeting these search queries with answer-style formatting.",
        "Add FAQ schema (FAQPage JSON-LD) to key landing pages to improve AI extraction.",
    ]

    if comp_counts:
        top = max(comp_counts, key=comp_counts.get)
        recs.append(
            f"Publish comparison pages (e.g., 'ai1stseo vs {top}') to build brand association in search."
        )

    recs.append("Increase entity mentions of 'ai1stseo' across authoritative third-party sites.")
    recs.append("Strengthen semantic coverage with topic clusters and internal linking.")

    if score < 50:
        recs.append("Improve SEO ranking for target queries to influence AI retrieval systems.")
        recs.append("Submit site to AI training data sources (Common Crawl, Wikipedia citations).")

    if "list_content" not in patterns:
        recs.append(
            "Create list-based content ('Best AI SEO tools 2026') to match top-ranking formats."
        )
    if "qa_content" not in patterns:
        recs.append(
            "Add Q&A sections to key pages — AI engines prioritize structured question-answer content."
        )

    return recs


# ── Main engine ───────────────────────────────────────────────────────────── #

def run_aeo_engine():
    print("\U0001f50d AEO Visibility Engine (Real Search) \u2014 starting\u2026\n")

    results = []
    mentions_found = 0
    competitor_counts = {}
    all_patterns = set()

    for i, query in enumerate(QUERIES):
        sys.stdout.write(f'  \u25b8 "{query}" \u2026 ')
        sys.stdout.flush()

        search_results, engine_used = fetch_search_results(query, 5)

        if not search_results:
            print("\u26a0 no results")
            results.append({
                "query": query,
                "mentioned": False,
                "competitors": [],
                "content_patterns": [],
                "sources": [],
                "summary": f'No search results found for "{query}".',
                "error": "No results returned",
            })
        else:
            mentioned = detect_brand(search_results)
            competitors = detect_competitors(search_results)
            patterns = detect_content_patterns(search_results)
            summary = build_summary(query, search_results)

            if mentioned:
                mentions_found += 1
            for c in competitors:
                competitor_counts[c] = competitor_counts.get(c, 0) + 1
            all_patterns.update(patterns)

            results.append({
                "query": query,
                "mentioned": mentioned,
                "competitors": competitors,
                "content_patterns": patterns,
                "sources": [
                    {"title": r["title"], "snippet": r["snippet"], "url": r["url"]}
                    for r in search_results
                ],
                "summary": summary,
                "search_engine": engine_used,
            })

            status = "\u2705 mentioned" if mentioned else "\u274c not mentioned"
            print(f"{status} ({len(search_results)} results, {len(competitors)} competitors) [{engine_used}]")

        # Polite delay between requests
        if i < len(QUERIES) - 1:
            delay = random.uniform(2.5, 4.5)
            time.sleep(delay)

    # ── Score ─────────────────────────────────────────────────────────────── #

    successful = sum(1 for r in results if "error" not in r)
    score = round((mentions_found / successful) * 100) if successful > 0 else 0

    insights = generate_insights(
        mentions_found, len(QUERIES), successful, score, competitor_counts, all_patterns
    )
    recommendations = generate_recommendations(score, competitor_counts, all_patterns)

    output = {
        "mode": "real_search",
        "visibility_score": score,
        "total_queries": len(QUERIES),
        "successful_queries": successful,
        "mentions_found": mentions_found,
        "competitor_frequency": competitor_counts,
        "content_patterns_detected": list(all_patterns),
        "insights": insights,
        "recommendations": recommendations,
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # ── Save ──────────────────────────────────────────────────────────────── #

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n\u2705 Done \u2014 visibility score: {score}% [real_search mode]")
    print(f"   Mentions: {mentions_found}/{successful} successful queries")
    print(f"   Competitors detected: {len(competitor_counts)}")
    print(f"   Saved to: {OUTPUT_FILE}\n")

    return output


if __name__ == "__main__":
    run_aeo_engine()
