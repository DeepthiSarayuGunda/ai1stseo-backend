"""
Outreach Generator — Converts unlinked brand mentions into outreach drafts.

Reads mention data from AEO results, Troy's mentions API, or direct input,
filters for unlinked mentions, and generates personalized outreach emails
requesting backlinks.

Usage:
    from services.outreach_generator import generate_outreach, get_outreach_queue,
                                            fetch_mentions_from_api

No external paid services. Generation only — does not send emails.
"""

import json
import os
import re
import requests as http_requests
from datetime import datetime, timezone
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
AEO_FILE = os.path.join(DATA_DIR, "aeo_results.json")
OUTREACH_FILE = os.path.join(DATA_DIR, "outreach_queue.json")

BRAND = "ai1stseo"
BRAND_DOMAIN = "ai1stseo.com"

# Troy's mentions API (Lambda)
MENTIONS_API_URL = "https://api.ai1stseo.com/api/mentions/scan"
MENTIONS_HISTORY_URL = "https://api.ai1stseo.com/api/mentions/history"
BRAND_URL = "https://www.ai1stseo.com"
BRAND_PATTERNS = [
    re.compile(r"ai1stseo", re.I),
    re.compile(r"ai\s*1st\s*seo", re.I),
]


# ── Mention extraction ────────────────────────────────────────────────────── #

def _has_brand_mention(text):
    """Check if text mentions the brand."""
    return any(p.search(text) for p in BRAND_PATTERNS)


def _has_backlink(text):
    """Check if text already contains a link to ai1stseo.com."""
    return bool(re.search(r"ai1stseo\.com", text, re.I))


def _extract_domain(url):
    """Extract clean domain from URL."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return host.replace("www.", "")
    except Exception:
        return ""


def _normalize_mention(raw):
    """Normalize a mention dict from any source into a consistent format.

    Handles input from:
      - AEO search results: {url, title, snippet, source, date}
      - Backlink API /api/mentions/scan: {url, title, source, published, has_backlink, publication}
      - Direct input: any dict with at least {url}

    Returns:
        Dict with {url, title, snippet, domain, source, date} or None if invalid.
    """
    url = (raw.get("url") or "").strip()
    if not url:
        return None

    domain = raw.get("domain") or _extract_domain(url)

    title = (raw.get("title") or "").strip()
    snippet = (raw.get("snippet") or raw.get("description") or raw.get("selftext") or "").strip()

    # Detect source type
    source = raw.get("source", "")
    if not source:
        if raw.get("has_backlink") is not None:
            source = "backlink"
        elif raw.get("search_engine"):
            source = "aeo"
        else:
            source = "manual"

    # Normalize date from various formats
    date = (
        raw.get("date")
        or raw.get("published")
        or raw.get("generated_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    if isinstance(date, str) and len(date) > 10:
        date = date[:10]

    return {
        "url": url,
        "domain": domain,
        "title": title,
        "snippet": snippet,
        "source": source,
        "date": date,
    }


def extract_unlinked_mentions(mentions=None):
    """Extract mentions that reference the brand but don't link to ai1stseo.com.

    Args:
        mentions: List of mention dicts from any source (AEO, backlink API, manual).
                  If None, reads from AEO results file.

    Returns:
        List of normalized unlinked mention dicts.
    """
    if mentions is None:
        mentions = _load_mentions_from_aeo()

    unlinked = []
    for raw in mentions:
        m = _normalize_mention(raw)
        if not m:
            continue

        # Skip our own domain
        if BRAND_DOMAIN in m["domain"]:
            continue

        # Backlink API items already have has_backlink flag
        if raw.get("has_backlink") is True:
            continue

        combined = f"{m['title']} {m['snippet']} {m['url']}"

        # Include if brand is mentioned but no backlink present
        if _has_brand_mention(combined) and not _has_backlink(combined):
            unlinked.append(m)

    return unlinked


def fetch_mentions_from_api(auth_token=None):
    """Fetch unlinked brand mentions from Troy's mentions API.

    Args:
        auth_token: Cognito JWT token for authentication.

    Returns:
        List of mention dicts from Google News + Reddit, or empty list on failure.
    """
    if not auth_token:
        auth_token = os.environ.get("AI1STSEO_AUTH_TOKEN", "")

    if not auth_token:
        return []

    try:
        resp = http_requests.post(
            MENTIONS_API_URL,
            json={"brand": "AI 1st SEO", "domain": "ai1stseo.com"},
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        if data.get("status") != "success":
            return []

        return data.get("mentions", [])

    except Exception:
        return []


def _load_mentions_from_aeo():
    """Load search result sources from AEO data as potential mentions."""
    if not os.path.exists(AEO_FILE):
        return []

    with open(AEO_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    mentions = []
    for result in data.get("results", []):
        for src in result.get("sources", []):
            mentions.append({
                "url": src.get("url", ""),
                "title": src.get("title", ""),
                "snippet": src.get("snippet", ""),
                "source": "aeo_search",
                "date": data.get("generated_at", "")[:10],
            })

    return mentions


# ── Outreach message generation ───────────────────────────────────────────── #

def _generate_subject(title):
    """Generate email subject line."""
    short_title = title[:60] + "..." if len(title) > 60 else title
    return f"Quick note about your article: {short_title}"


def _generate_email_body(domain, title, snippet):
    """Generate a professional outreach email body."""
    # Extract a relevant snippet line for personalization
    snippet_line = snippet[:120].strip()
    if snippet_line and not snippet_line.endswith("."):
        snippet_line = snippet_line.rsplit(" ", 1)[0] + "..."

    body = (
        f"Hi {domain} team,\n\n"
        f"I came across your article \"{title}\" and wanted to say thanks for "
        f"covering this topic so thoroughly.\n\n"
    )

    if snippet_line:
        body += (
            f"I noticed you mentioned AI SEO tools in your piece — specifically "
            f"where you wrote: \"{snippet_line}\"\n\n"
        )

    body += (
        f"We've built AI 1st SEO (ai1stseo.com), a platform focused on AI-powered "
        f"search optimization and answer engine visibility. Given the context of your "
        f"article, I think our tool would be a valuable addition for your readers.\n\n"
        f"Would you consider adding a link to ai1stseo.com in your article? "
        f"Here's a suggested anchor text that fits naturally:\n\n"
        f"  \"AI 1st SEO\" → https://www.ai1stseo.com\n\n"
        f"Happy to return the favor with a mention on our end as well.\n\n"
        f"Thanks for your time,\n"
        f"The AI 1st SEO Team\n"
        f"https://www.ai1stseo.com"
    )

    return body


def _count_sources(queue):
    """Count outreach items by source type."""
    counts = {}
    for item in queue:
        src = item.get("source", "unknown")
        counts[src] = counts.get(src, 0) + 1
    return counts


def generate_outreach(mentions=None):
    """Generate outreach messages for unlinked mentions.

    Args:
        mentions: Optional list of mention dicts. If None, uses AEO data.

    Returns:
        Dict with generated outreach messages and metadata.
    """
    unlinked = extract_unlinked_mentions(mentions)

    # Also generate outreach for pages that mention competitors but not us
    if not unlinked and mentions is None:
        all_mentions = _load_mentions_from_aeo()
        for raw in all_mentions:
            m = _normalize_mention(raw)
            if not m or BRAND_DOMAIN in m["domain"]:
                continue
            m["source"] = "competitor_page"
            unlinked.append(m)

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for m in unlinked:
        if m["url"] not in seen_urls:
            seen_urls.add(m["url"])
            unique.append(m)

    # Generate outreach for each
    queue = []
    for m in unique:
        subject = _generate_subject(m["title"])
        email_body = _generate_email_body(m["domain"], m["title"], m["snippet"])

        queue.append({
            "url": m["url"],
            "domain": m["domain"],
            "title": m["title"],
            "snippet_context": m["snippet"][:150],
            "source": m["source"],
            "subject": subject,
            "email_body": email_body,
            "status": "pending",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    output = {
        "total_mentions_scanned": len(unlinked),
        "outreach_generated": len(queue),
        "source_breakdown": _count_sources(queue),
        "queue": queue,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save to file
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTREACH_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output


def get_outreach_queue():
    """Read the current outreach queue from disk."""
    if not os.path.exists(OUTREACH_FILE):
        return {"total_mentions_scanned": 0, "outreach_generated": 0, "queue": []}

    with open(OUTREACH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def update_outreach_status(url, new_status):
    """Update the status of an outreach item by URL."""
    data = get_outreach_queue()
    updated = False
    for item in data.get("queue", []):
        if item["url"] == url:
            item["status"] = new_status
            updated = True
            break

    if updated:
        with open(OUTREACH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return updated


# ── CLI ───────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":
    print("Generating outreach from AEO data...\n")
    result = generate_outreach()
    print(f"Scanned: {result['total_mentions_scanned']} mentions")
    print(f"Generated: {result['outreach_generated']} outreach drafts")
    print(f"Saved to: {OUTREACH_FILE}\n")
    for item in result["queue"][:3]:
        print(f"  → {item['domain']}: {item['subject']}")
