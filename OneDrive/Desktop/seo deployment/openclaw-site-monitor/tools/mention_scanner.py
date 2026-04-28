"""
Brand Mention Scanner Tool
Scans Google News and Reddit for brand mentions.
Identifies unlinked mentions as backlink opportunities.
"""

import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, urlparse
from datetime import datetime, timezone
from typing import TypedDict


class MentionResult(TypedDict):
    brand: str
    domain: str
    total_mentions: int
    unlinked_count: int
    linked_count: int
    mentions: list
    timestamp: str


def scan_mentions(brand: str, domain: str = '') -> MentionResult:
    """
    Scan Google News and Reddit for brand mentions.
    Identifies which mentions link back to the domain and which don't.

    Args:
        brand: Brand name to search for
        domain: Your domain (to check if mentions include a backlink)

    Returns:
        MentionResult with all mentions categorized as linked/unlinked
    """
    mentions = []

    # 1. Google News RSS
    try:
        news_url = 'https://news.google.com/rss/search?q={}&hl=en'.format(quote_plus(brand))
        resp = requests.get(news_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO-Monitor/1.0)'
        })
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item')[:15]:
                title = item.findtext('title', '')
                link = item.findtext('link', '')
                pub_date = item.findtext('pubDate', '')
                source = item.findtext('source', '')
                has_link = domain.lower() in link.lower() if domain else False
                mentions.append({
                    'source': 'google_news',
                    'title': title,
                    'url': link,
                    'published': pub_date,
                    'publication': source,
                    'has_backlink': has_link,
                })
    except Exception as e:
        print('Google News scan error: {}'.format(e))

    # 2. Reddit search
    try:
        reddit_url = 'https://www.reddit.com/search.json?q={}&sort=new&limit=15'.format(
            quote_plus(brand))
        resp = requests.get(reddit_url, timeout=10, headers={
            'User-Agent': 'AI1stSEO-MentionScanner/1.0'
        })
        if resp.status_code == 200:
            data = resp.json()
            for post in data.get('data', {}).get('children', []):
                p = post.get('data', {})
                selftext = p.get('selftext', '')
                has_link = domain.lower() in selftext.lower() if domain else False
                mentions.append({
                    'source': 'reddit',
                    'title': p.get('title', ''),
                    'url': 'https://reddit.com{}'.format(p.get('permalink', '')),
                    'subreddit': p.get('subreddit', ''),
                    'score': p.get('score', 0),
                    'num_comments': p.get('num_comments', 0),
                    'published': datetime.fromtimestamp(
                        p.get('created_utc', 0), tz=timezone.utc
                    ).isoformat() if p.get('created_utc') else '',
                    'has_backlink': has_link,
                })
    except Exception as e:
        print('Reddit scan error: {}'.format(e))

    unlinked = [m for m in mentions if not m.get('has_backlink')]
    linked = [m for m in mentions if m.get('has_backlink')]

    return MentionResult(
        brand=brand,
        domain=domain,
        total_mentions=len(mentions),
        unlinked_count=len(unlinked),
        linked_count=len(linked),
        mentions=mentions,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


TOOL_SCHEMA = {
    "name": "mention_scanner",
    "description": "Scan Google News and Reddit for brand mentions and unlinked backlink opportunities",
    "input_schema": {
        "type": "object",
        "properties": {
            "brand": {"type": "string", "description": "Brand name to search for"},
            "domain": {"type": "string", "description": "Your domain to check for backlinks"},
        },
        "required": ["brand"],
    },
}
