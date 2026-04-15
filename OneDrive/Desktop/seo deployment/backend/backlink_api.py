"""
Backlink Analysis Module — Dev 3 (Troy)
Domain authority scoring, toxic link detection, link gap analysis.
DynamoDB-backed, registered as Flask blueprint.

Tables: ai1stseo-backlinks, ai1stseo-backlink-opportunities
"""
from flask import Blueprint, jsonify, request
from auth import require_auth
from dynamodb_helper import put_item, get_item, scan_table, query_index, update_item, delete_item
import json
import uuid
import requests as http_requests
from datetime import datetime, timezone
from urllib.parse import urlparse

backlink_bp = Blueprint('backlinks', __name__)
DEFAULT_PROJECT_ID = '24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2'

BACKLINKS_TABLE = 'ai1stseo-backlinks'
OPPORTUNITIES_TABLE = 'ai1stseo-backlink-opportunities'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get_user_id():
    if hasattr(request, 'cognito_user') and request.cognito_user:
        return request.cognito_user.get('user_id')
    return None


# ===================== DOMAIN AUTHORITY SCORING =====================

def _estimate_domain_authority(domain):
    """
    Estimate domain authority using publicly available signals.
    Returns a score 0-100 based on: HTTPS, response time, headers, structured data hints.
    For production, integrate Ahrefs/Majestic API for real DA scores.
    """
    score = 0
    signals = {}
    url = 'https://' + domain if not domain.startswith('http') else domain
    parsed = urlparse(url)
    domain_clean = parsed.netloc or parsed.path

    try:
        resp = http_requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO/1.0)'
        }, allow_redirects=True)

        # HTTPS
        if resp.url.startswith('https'):
            score += 15
            signals['https'] = True
        else:
            signals['https'] = False

        # Response time
        elapsed_ms = int(resp.elapsed.total_seconds() * 1000)
        signals['response_time_ms'] = elapsed_ms
        if elapsed_ms < 500:
            score += 10
        elif elapsed_ms < 1500:
            score += 5

        # Security headers
        has_hsts = bool(resp.headers.get('Strict-Transport-Security'))
        has_csp = bool(resp.headers.get('Content-Security-Policy'))
        if has_hsts: score += 5
        if has_csp: score += 5
        signals['hsts'] = has_hsts
        signals['csp'] = has_csp

        # Content analysis
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.content, 'html.parser')

        # Schema markup
        json_ld = soup.find_all('script', {'type': 'application/ld+json'})
        if json_ld:
            score += 10
            signals['schema_markup'] = len(json_ld)
        else:
            signals['schema_markup'] = 0

        # Meta tags quality
        title = soup.find('title')
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if title and title.string and len(title.string.strip()) > 10: score += 5
        if meta_desc and meta_desc.get('content', '') and len(meta_desc['content']) > 50: score += 5
        signals['has_title'] = bool(title and title.string)
        signals['has_meta_desc'] = bool(meta_desc)

        # Internal link count (proxy for site depth)
        internal_links = len([a for a in soup.find_all('a', href=True)
                              if domain_clean in a.get('href', '')])
        if internal_links > 20: score += 10
        elif internal_links > 5: score += 5
        signals['internal_links'] = internal_links

        # External link count
        external_links = len([a for a in soup.find_all('a', href=True)
                              if a.get('href', '').startswith('http') and domain_clean not in a.get('href', '')])
        signals['external_links'] = external_links

        # Content depth
        text = soup.get_text()
        word_count = len(text.split())
        if word_count > 1000: score += 10
        elif word_count > 300: score += 5
        signals['word_count'] = word_count

        # Robots.txt
        try:
            robots = http_requests.get(url.rstrip('/') + '/robots.txt', timeout=5)
            if robots.status_code == 200: score += 5
            signals['robots_txt'] = robots.status_code == 200
        except Exception:
            signals['robots_txt'] = False

        # Sitemap
        try:
            sitemap = http_requests.get(url.rstrip('/') + '/sitemap.xml', timeout=5)
            if sitemap.status_code == 200: score += 5
            signals['sitemap'] = True
        except Exception:
            signals['sitemap'] = False

        # Cap at 100
        score = min(score, 100)

    except Exception as e:
        signals['error'] = str(e)[:200]
        score = 0

    return {
        'domain': domain_clean,
        'da_score': score,
        'signals': signals,
        'scored_at': _now(),
    }


# ===================== TOXIC LINK DETECTION =====================

def _classify_toxic(backlink):
    """
    Classify a backlink as potentially toxic based on heuristic signals.
    Returns toxic_score 0-100 and reasons.
    """
    toxic_score = 0
    reasons = []
    source_url = backlink.get('source_url', '')
    anchor = backlink.get('anchor_text', '').lower()
    parsed = urlparse(source_url)
    domain = parsed.netloc

    # Spammy TLD patterns
    spam_tlds = ['.xyz', '.top', '.club', '.work', '.click', '.link', '.info', '.biz']
    if any(domain.endswith(tld) for tld in spam_tlds):
        toxic_score += 20
        reasons.append('Spammy TLD')

    # Exact match anchor text (over-optimization signal)
    if anchor and len(anchor.split()) == 1 and anchor.isalpha():
        toxic_score += 10
        reasons.append('Exact match anchor')

    # Gambling/pharma/adult keywords in anchor
    toxic_keywords = ['casino', 'poker', 'viagra', 'cialis', 'payday', 'loan', 'xxx', 'porn', 'betting']
    if any(kw in anchor for kw in toxic_keywords):
        toxic_score += 40
        reasons.append('Toxic keyword in anchor')

    # Very long domain (often auto-generated spam)
    if len(domain) > 40:
        toxic_score += 15
        reasons.append('Unusually long domain')

    # Subdomain depth (spam sites often use deep subdomains)
    subdomain_count = domain.count('.') - 1
    if subdomain_count > 2:
        toxic_score += 15
        reasons.append('Deep subdomain structure')

    # No-follow check
    if backlink.get('nofollow'):
        toxic_score = max(toxic_score - 10, 0)  # nofollow links are less harmful

    return {
        'toxic_score': min(toxic_score, 100),
        'is_toxic': toxic_score >= 50,
        'reasons': reasons,
    }


# ===================== API ENDPOINTS =====================

@backlink_bp.route('/api/backlinks/score', methods=['POST'])
@require_auth
def score_domain():
    """Score a domain's authority. Returns DA score + signal breakdown."""
    data = request.get_json() or {}
    domain = data.get('domain', '').strip()
    if not domain:
        return jsonify({'status': 'error', 'message': 'domain required'}), 400
    try:
        result = _estimate_domain_authority(domain)
        # Store the score
        put_item(BACKLINKS_TABLE, {
            'id': str(uuid.uuid4()),
            'type': 'domain_score',
            'domain': result['domain'],
            'da_score': result['da_score'],
            'signals': result['signals'],
            'scored_at': result['scored_at'],
            'project_id': DEFAULT_PROJECT_ID,
            'scored_by': _get_user_id(),
        })
        return jsonify({'status': 'success', **result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/analyze-toxic', methods=['POST'])
@require_auth
def analyze_toxic():
    """Analyze a list of backlinks for toxic signals."""
    data = request.get_json() or {}
    backlinks = data.get('backlinks', [])
    if not backlinks:
        return jsonify({'status': 'error', 'message': 'backlinks array required'}), 400
    results = []
    toxic_count = 0
    for bl in backlinks[:100]:  # Cap at 100
        classification = _classify_toxic(bl)
        results.append({**bl, **classification})
        if classification['is_toxic']:
            toxic_count += 1
    return jsonify({
        'status': 'success',
        'total': len(results),
        'toxic_count': toxic_count,
        'toxic_percentage': round(toxic_count / len(results) * 100, 1) if results else 0,
        'backlinks': results,
    })


@backlink_bp.route('/api/backlinks/link-gap', methods=['POST'])
@require_auth
def link_gap_analysis():
    """
    Find backlink opportunities: domains that link to competitors but not to you.
    Accepts your domain + competitor domains, compares their backlink profiles.
    """
    data = request.get_json() or {}
    your_domain = data.get('domain', '').strip()
    competitors = data.get('competitors', [])
    if not your_domain or not competitors:
        return jsonify({'status': 'error', 'message': 'domain and competitors[] required'}), 400

    try:
        # Score all domains
        your_score = _estimate_domain_authority(your_domain)
        comp_scores = []
        for comp in competitors[:5]:  # Cap at 5 competitors
            comp_score = _estimate_domain_authority(comp)
            comp_scores.append(comp_score)

        # Identify gaps (where competitors score higher)
        gaps = []
        for comp in comp_scores:
            if comp['da_score'] > your_score['da_score']:
                advantage = comp['da_score'] - your_score['da_score']
                # Find specific signal gaps
                signal_gaps = []
                for signal, value in comp['signals'].items():
                    your_val = your_score['signals'].get(signal)
                    if isinstance(value, bool) and value and not your_val:
                        signal_gaps.append(signal)
                    elif isinstance(value, (int, float)) and isinstance(your_val, (int, float)) and value > your_val:
                        signal_gaps.append('{} ({} vs {})'.format(signal, value, your_val))

                gaps.append({
                    'competitor': comp['domain'],
                    'competitor_da': comp['da_score'],
                    'your_da': your_score['da_score'],
                    'advantage': advantage,
                    'signal_gaps': signal_gaps[:10],
                })

        # Store the analysis
        analysis_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': analysis_id,
            'type': 'link_gap',
            'domain': your_domain,
            'competitors': competitors,
            'your_da': your_score['da_score'],
            'gaps': gaps,
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({
            'status': 'success',
            'id': analysis_id,
            'your_domain': your_score,
            'competitors': comp_scores,
            'gaps': gaps,
            'total_gaps': len(gaps),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/history', methods=['GET'])
@require_auth
def backlink_history():
    """Get backlink analysis history. Filter by type: domain_score, link_gap, toxic_scan."""
    analysis_type = request.args.get('type', '')
    domain = request.args.get('domain', '')
    limit = request.args.get('limit', 50, type=int)
    try:
        items = scan_table(BACKLINKS_TABLE, 200)
        if analysis_type:
            items = [i for i in items if i.get('type') == analysis_type]
        if domain:
            items = [i for i in items if domain.lower() in (i.get('domain', '') or '').lower()]
        items.sort(key=lambda x: x.get('created_at', x.get('scored_at', '')), reverse=True)
        return jsonify({'status': 'success', 'analyses': items[:limit], 'total': len(items)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/opportunities', methods=['GET'])
@require_auth
def list_opportunities():
    """List backlink opportunities from all sources (link gap, broken links, etc.)."""
    try:
        items = scan_table(OPPORTUNITIES_TABLE, 100)
        items.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        return jsonify({'status': 'success', 'opportunities': items, 'total': len(items)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/opportunities', methods=['POST'])
@require_auth
def add_opportunity():
    """Manually add a backlink opportunity."""
    data = request.get_json() or {}
    source_url = data.get('source_url', '').strip()
    if not source_url:
        return jsonify({'status': 'error', 'message': 'source_url required'}), 400
    try:
        opp_id = put_item(OPPORTUNITIES_TABLE, {
            'source_url': source_url,
            'source_da': data.get('source_da', 0),
            'opportunity_type': data.get('type', 'manual'),
            'target_url': data.get('target_url', ''),
            'anchor_suggestion': data.get('anchor_suggestion', ''),
            'priority_score': data.get('priority_score', 50),
            'status': 'new',
            'notes': data.get('notes', ''),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })
        return jsonify({'status': 'success', 'id': opp_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
