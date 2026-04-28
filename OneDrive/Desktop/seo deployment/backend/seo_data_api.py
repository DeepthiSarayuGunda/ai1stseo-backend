"""
SEO Data API Wrapper — Abstracts external SEO data sources.
Supports: Ahrefs API, DataForSEO, or built-in real-time scoring as fallback.
When an API key is configured, enriches domain data with crawl-based metrics.
When no key is available, falls back to our real-time signal-based scorer.

Env vars:
  AHREFS_API_KEY — Ahrefs API v3 bearer token
  DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD — DataForSEO credentials
"""
import os
import requests as http_requests
from urllib.parse import urlparse
from datetime import datetime, timezone

AHREFS_API_KEY = os.environ.get('AHREFS_API_KEY', '')
DATAFORSEO_LOGIN = os.environ.get('DATAFORSEO_LOGIN', '')
DATAFORSEO_PASSWORD = os.environ.get('DATAFORSEO_PASSWORD', '')


def get_domain_metrics(domain):
    """
    Get domain authority and backlink metrics from the best available source.
    Returns a standardized dict regardless of which source is used.
    """
    # Clean domain
    if domain.startswith('http'):
        domain = urlparse(domain).netloc
    domain = domain.replace('www.', '').strip()

    if AHREFS_API_KEY:
        result = _ahrefs_domain_metrics(domain)
        if result:
            return result

    if DATAFORSEO_LOGIN:
        result = _dataforseo_domain_metrics(domain)
        if result:
            return result

    # Fallback: our built-in real-time scorer
    return _builtin_domain_metrics(domain)


def get_backlink_profile(domain, limit=100):
    """
    Get backlink list for a domain from the best available source.
    """
    if domain.startswith('http'):
        domain = urlparse(domain).netloc
    domain = domain.replace('www.', '').strip()

    if AHREFS_API_KEY:
        result = _ahrefs_backlinks(domain, limit)
        if result:
            return result

    if DATAFORSEO_LOGIN:
        result = _dataforseo_backlinks(domain, limit)
        if result:
            return result

    return {'source': 'none', 'domain': domain, 'backlinks': [],
            'message': 'No external API configured. Set AHREFS_API_KEY or DATAFORSEO_LOGIN.'}


# ===================== AHREFS API v3 =====================

def _ahrefs_domain_metrics(domain):
    """Pull domain metrics from Ahrefs API v3."""
    try:
        resp = http_requests.get(
            'https://api.ahrefs.com/v3/site-explorer/domain-rating',
            params={'target': domain, 'output': 'json'},
            headers={'Authorization': 'Bearer {}'.format(AHREFS_API_KEY)},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                'source': 'ahrefs',
                'domain': domain,
                'domain_rating': data.get('domain_rating', 0),
                'ahrefs_rank': data.get('ahrefs_rank', 0),
                'backlinks': data.get('backlinks', 0),
                'referring_domains': data.get('refdomains', 0),
                'organic_keywords': data.get('organic_keywords', 0),
                'organic_traffic': data.get('organic_traffic', 0),
                'retrieved_at': datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        print('Ahrefs API error: {}'.format(e))
    return None


def _ahrefs_backlinks(domain, limit):
    """Pull backlink list from Ahrefs API v3."""
    try:
        resp = http_requests.get(
            'https://api.ahrefs.com/v3/site-explorer/all-backlinks',
            params={'target': domain, 'output': 'json', 'limit': min(limit, 1000),
                    'order_by': 'domain_rating_source:desc'},
            headers={'Authorization': 'Bearer {}'.format(AHREFS_API_KEY)},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            backlinks = []
            for bl in data.get('backlinks', []):
                backlinks.append({
                    'source_url': bl.get('url_from', ''),
                    'target_url': bl.get('url_to', ''),
                    'anchor_text': bl.get('anchor', ''),
                    'domain_rating': bl.get('domain_rating_source', 0),
                    'nofollow': bl.get('nofollow', False),
                    'first_seen': bl.get('first_seen', ''),
                    'last_seen': bl.get('last_seen', ''),
                })
            return {
                'source': 'ahrefs',
                'domain': domain,
                'total': data.get('stats', {}).get('total', len(backlinks)),
                'backlinks': backlinks,
            }
    except Exception as e:
        print('Ahrefs backlinks error: {}'.format(e))
    return None


# ===================== DATAFORSEO API =====================

def _dataforseo_domain_metrics(domain):
    """Pull domain metrics from DataForSEO."""
    try:
        resp = http_requests.post(
            'https://api.dataforseo.com/v3/backlinks/summary/live',
            json=[{'target': domain}],
            auth=(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD),
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('tasks', [{}])[0].get('result', [{}])
            if results:
                r = results[0]
                return {
                    'source': 'dataforseo',
                    'domain': domain,
                    'domain_rating': r.get('rank', 0),
                    'backlinks': r.get('backlinks', 0),
                    'referring_domains': r.get('referring_domains', 0),
                    'organic_keywords': 0,
                    'organic_traffic': 0,
                    'retrieved_at': datetime.now(timezone.utc).isoformat(),
                }
    except Exception as e:
        print('DataForSEO error: {}'.format(e))
    return None


def _dataforseo_backlinks(domain, limit):
    """Pull backlinks from DataForSEO."""
    try:
        resp = http_requests.post(
            'https://api.dataforseo.com/v3/backlinks/backlinks/live',
            json=[{'target': domain, 'limit': min(limit, 1000),
                   'order_by': ['rank,desc']}],
            auth=(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD),
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('tasks', [{}])[0].get('result', [{}])
            if results:
                items = results[0].get('items', [])
                backlinks = []
                for bl in items:
                    backlinks.append({
                        'source_url': bl.get('url_from', ''),
                        'target_url': bl.get('url_to', ''),
                        'anchor_text': bl.get('anchor', ''),
                        'domain_rating': bl.get('rank', 0),
                        'nofollow': bl.get('dofollow', True) is False,
                        'first_seen': bl.get('first_seen', ''),
                    })
                return {
                    'source': 'dataforseo',
                    'domain': domain,
                    'total': results[0].get('total_count', len(backlinks)),
                    'backlinks': backlinks,
                }
    except Exception as e:
        print('DataForSEO backlinks error: {}'.format(e))
    return None


# ===================== BUILT-IN FALLBACK =====================

def _builtin_domain_metrics(domain):
    """
    Real-time domain scoring using our built-in signals.
    No external API needed — works immediately.
    """
    url = 'https://' + domain
    score = 0
    signals = {}

    try:
        resp = http_requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO/1.0)'
        }, allow_redirects=True)

        if resp.url.startswith('https'):
            score += 15
            signals['https'] = True

        elapsed_ms = int(resp.elapsed.total_seconds() * 1000)
        signals['response_time_ms'] = elapsed_ms
        if elapsed_ms < 500:
            score += 10
        elif elapsed_ms < 1500:
            score += 5

        if resp.headers.get('Strict-Transport-Security'):
            score += 5
            signals['hsts'] = True
        if resp.headers.get('Content-Security-Policy'):
            score += 5
            signals['csp'] = True

        # Content analysis
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.content, 'html.parser')

        json_ld = soup.find_all('script', {'type': 'application/ld+json'})
        if json_ld:
            score += 10
            signals['schema_markup'] = len(json_ld)

        title = soup.find('title')
        if title and title.string and len(title.string.strip()) > 10:
            score += 5
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content', '') and len(meta['content']) > 50:
            score += 5

        internal_links = len([a for a in soup.find_all('a', href=True)
                              if domain in a.get('href', '')])
        if internal_links > 20:
            score += 10
        elif internal_links > 5:
            score += 5
        signals['internal_links'] = internal_links

        word_count = len(soup.get_text().split())
        if word_count > 1000:
            score += 10
        elif word_count > 300:
            score += 5
        signals['word_count'] = word_count

        try:
            robots = http_requests.get(url.rstrip('/') + '/robots.txt', timeout=5)
            if robots.status_code == 200:
                score += 5
                signals['robots_txt'] = True
        except Exception:
            pass

        try:
            sitemap = http_requests.get(url.rstrip('/') + '/sitemap.xml', timeout=5)
            if sitemap.status_code == 200:
                score += 5
                signals['sitemap'] = True
        except Exception:
            pass

        score = min(score, 100)

    except Exception as e:
        signals['error'] = str(e)[:200]

    return {
        'source': 'builtin',
        'domain': domain,
        'domain_rating': score,
        'backlinks': 0,
        'referring_domains': 0,
        'organic_keywords': 0,
        'organic_traffic': 0,
        'signals': signals,
        'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'note': 'Using real-time signal scoring. Set AHREFS_API_KEY for crawl-based metrics.',
    }
