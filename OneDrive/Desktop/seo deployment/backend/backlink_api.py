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


# ===================== MONTH 2: LLM CITATION AUTHORITY =====================

@backlink_bp.route('/api/backlinks/citation-authority', methods=['POST'])
@require_auth
def citation_authority_probe():
    """
    Probe AI models to discover which domains they cite for a given topic.
    This is the novel differentiator — no competitor tracks LLM citation patterns.
    """
    data = request.get_json() or {}
    queries = data.get('queries', [])
    niche = data.get('niche', 'SEO')
    if not queries:
        return jsonify({'status': 'error', 'message': 'queries[] required (list of prompts to send to AI models)'}), 400

    try:
        import re
        from collections import Counter

        cited_domains = Counter()
        probe_results = []

        # Use our AI inference to probe — this calls the Ollama accelerator or Bedrock
        try:
            from ai_inference import generate
        except ImportError:
            generate = None

        for query in queries[:20]:  # Cap at 20 queries
            if not generate:
                break
            prompt = (
                'Answer this question and cite specific websites as sources. '
                'Include URLs where possible: {}'
            ).format(query)

            response = generate(prompt, max_tokens=1024, temperature=0.3, triggered_by='citation_probe')

            # Extract URLs from the response
            urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', response)
            domains_found = []
            for url in urls:
                domain = urlparse(url).netloc
                if domain and len(domain) > 3:
                    cited_domains[domain] += 1
                    domains_found.append(domain)

            probe_results.append({
                'query': query,
                'domains_cited': list(set(domains_found)),
                'citation_count': len(domains_found),
            })

        # Build citation authority scores
        authority_scores = []
        for domain, count in cited_domains.most_common(50):
            authority_scores.append({
                'domain': domain,
                'citation_count': count,
                'citation_frequency': round(count / len(queries) * 100, 1) if queries else 0,
                'niche': niche,
            })

        # Store the probe
        probe_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': probe_id,
            'type': 'citation_authority',
            'niche': niche,
            'queries_count': len(queries),
            'top_cited_domains': authority_scores[:20],
            'probe_results': probe_results,
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({
            'status': 'success',
            'id': probe_id,
            'total_domains_cited': len(cited_domains),
            'top_cited': authority_scores[:20],
            'probes': probe_results,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/citation-scores', methods=['GET'])
@require_auth
def get_citation_scores():
    """Get stored citation authority scores by niche."""
    niche = request.args.get('niche', '')
    try:
        items = scan_table(BACKLINKS_TABLE, 100)
        probes = [i for i in items if i.get('type') == 'citation_authority']
        if niche:
            probes = [p for p in probes if niche.lower() in (p.get('niche', '') or '').lower()]
        probes.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'status': 'success', 'probes': probes[:20]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/velocity', methods=['POST'])
@require_auth
def link_velocity_check():
    """
    Detect link velocity anomalies — domains acquiring links unusually fast.
    These are either running a campaign (competitive threat) or publishing viral content (opportunity).
    """
    data = request.get_json() or {}
    domain = data.get('domain', '').strip()
    if not domain:
        return jsonify({'status': 'error', 'message': 'domain required'}), 400
    try:
        # Check historical scores for this domain
        items = scan_table(BACKLINKS_TABLE, 200)
        domain_scores = [i for i in items if i.get('domain') == domain and i.get('type') == 'domain_score']
        domain_scores.sort(key=lambda x: x.get('scored_at', ''))

        velocity = {
            'domain': domain,
            'data_points': len(domain_scores),
            'trend': 'insufficient_data',
            'anomaly': False,
        }

        if len(domain_scores) >= 2:
            scores = [s.get('da_score', 0) for s in domain_scores]
            latest = scores[-1]
            avg = sum(scores) / len(scores)
            change = latest - scores[0]

            velocity['latest_score'] = latest
            velocity['average_score'] = round(avg, 1)
            velocity['total_change'] = change
            velocity['trend'] = 'improving' if change > 5 else ('declining' if change < -5 else 'stable')
            velocity['anomaly'] = abs(change) > 15  # Flag if DA changed by more than 15 points

        return jsonify({'status': 'success', **velocity})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== MONTH 3: BROKEN LINK RECLAIM + WIKIPEDIA GAP =====================

@backlink_bp.route('/api/backlinks/broken-links', methods=['POST'])
@require_auth
def find_broken_links():
    """
    Scan a page for broken outbound links — reclaim opportunities.
    If a broken link pointed to content similar to the client's, it's a reclaim candidate.
    """
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400
    try:
        from bs4 import BeautifulSoup
        resp = http_requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO/1.0)'})
        soup = BeautifulSoup(resp.content, 'html.parser')

        broken = []
        checked = 0
        links = soup.find_all('a', href=True)

        for link in links[:50]:  # Cap at 50 links per page
            href = link.get('href', '')
            if not href.startswith('http'):
                continue
            checked += 1
            try:
                r = http_requests.head(href, timeout=5, allow_redirects=True,
                                       headers={'User-Agent': 'Mozilla/5.0'})
                if r.status_code >= 400:
                    broken.append({
                        'broken_url': href,
                        'status_code': r.status_code,
                        'anchor_text': link.get_text().strip()[:100],
                        'linking_page': url,
                        'context': link.parent.get_text().strip()[:200] if link.parent else '',
                    })
            except Exception:
                broken.append({
                    'broken_url': href,
                    'status_code': 0,
                    'anchor_text': link.get_text().strip()[:100],
                    'linking_page': url,
                    'context': 'Connection failed',
                })

        # Store as opportunities
        for bl in broken:
            put_item(OPPORTUNITIES_TABLE, {
                'source_url': bl['linking_page'],
                'broken_url': bl['broken_url'],
                'anchor_text': bl['anchor_text'],
                'opportunity_type': 'broken_link_reclaim',
                'priority_score': 70,
                'status': 'new',
                'project_id': DEFAULT_PROJECT_ID,
                'created_by': _get_user_id(),
            })

        return jsonify({
            'status': 'success',
            'url': url,
            'links_checked': checked,
            'broken_count': len(broken),
            'broken_links': broken,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/wikipedia-gaps', methods=['POST'])
@require_auth
def wikipedia_citation_gaps():
    """
    Find Wikipedia articles in a topic that cite weak/dead sources.
    These are replacement opportunities — if your content is better, you can suggest an edit.
    """
    data = request.get_json() or {}
    topic = data.get('topic', '').strip()
    if not topic:
        return jsonify({'status': 'error', 'message': 'topic required'}), 400
    try:
        # Search Wikipedia for articles on this topic
        wiki_search = http_requests.get(
            'https://en.wikipedia.org/w/api.php',
            params={'action': 'query', 'list': 'search', 'srsearch': topic,
                    'srlimit': 10, 'format': 'json'},
            timeout=10,
        ).json()

        articles = wiki_search.get('query', {}).get('search', [])
        gaps = []

        for article in articles[:5]:  # Check top 5 articles
            title = article.get('title', '')
            # Get external links from this article
            links_resp = http_requests.get(
                'https://en.wikipedia.org/w/api.php',
                params={'action': 'query', 'titles': title, 'prop': 'extlinks',
                        'ellimit': 50, 'format': 'json'},
                timeout=10,
            ).json()

            pages = links_resp.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                ext_links = page_data.get('extlinks', [])
                for link in ext_links:
                    ext_url = link.get('*', '')
                    if not ext_url:
                        continue
                    # Check if the external link is still alive
                    try:
                        r = http_requests.head(ext_url, timeout=5, allow_redirects=True)
                        if r.status_code >= 400:
                            gaps.append({
                                'wikipedia_article': title,
                                'wikipedia_url': 'https://en.wikipedia.org/wiki/' + title.replace(' ', '_'),
                                'dead_citation': ext_url,
                                'status_code': r.status_code,
                                'opportunity': 'Replace dead citation with your content',
                            })
                    except Exception:
                        gaps.append({
                            'wikipedia_article': title,
                            'wikipedia_url': 'https://en.wikipedia.org/wiki/' + title.replace(' ', '_'),
                            'dead_citation': ext_url,
                            'status_code': 0,
                            'opportunity': 'Citation unreachable — replacement opportunity',
                        })

        # Store gaps as opportunities
        for gap in gaps:
            put_item(OPPORTUNITIES_TABLE, {
                'source_url': gap['wikipedia_url'],
                'broken_url': gap['dead_citation'],
                'opportunity_type': 'wikipedia_citation_gap',
                'priority_score': 90,  # Wikipedia links are very high value
                'status': 'new',
                'notes': gap['opportunity'],
                'project_id': DEFAULT_PROJECT_ID,
                'created_by': _get_user_id(),
            })

        return jsonify({
            'status': 'success',
            'topic': topic,
            'articles_checked': len(articles[:5]),
            'gaps_found': len(gaps),
            'gaps': gaps,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== MONTH 4: AUTOMATION =====================

@backlink_bp.route('/api/backlinks/competitor-alerts', methods=['POST'])
@require_auth
def check_competitor_new_links():
    """
    Compare a competitor's current backlink profile against stored history.
    Detect new links they acquired that you don't have.
    """
    data = request.get_json() or {}
    competitor = data.get('competitor', '').strip()
    your_domain = data.get('your_domain', '').strip()
    if not competitor:
        return jsonify({'status': 'error', 'message': 'competitor domain required'}), 400
    try:
        # Get stored scores for this competitor
        items = scan_table(BACKLINKS_TABLE, 200)
        comp_history = [i for i in items if i.get('domain') == competitor and i.get('type') == 'domain_score']
        comp_history.sort(key=lambda x: x.get('scored_at', ''))

        # Run a fresh score
        current = _estimate_domain_authority(competitor)

        alert = {
            'competitor': competitor,
            'current_da': current['da_score'],
            'historical_scores': len(comp_history),
            'alert_type': 'none',
        }

        if comp_history:
            prev_score = comp_history[-1].get('da_score', 0)
            change = current['da_score'] - prev_score
            alert['previous_da'] = prev_score
            alert['da_change'] = change
            if change > 5:
                alert['alert_type'] = 'competitor_improving'
                alert['message'] = '{} gained {} DA points — they may have acquired new high-value links'.format(competitor, change)
            elif change < -5:
                alert['alert_type'] = 'competitor_declining'
                alert['message'] = '{} lost {} DA points — potential toxic link issue or content removal'.format(competitor, abs(change))

        # Store the check
        put_item(BACKLINKS_TABLE, {
            'id': str(uuid.uuid4()),
            'type': 'competitor_alert',
            'competitor': competitor,
            'your_domain': your_domain,
            'da_score': current['da_score'],
            'alert_type': alert['alert_type'],
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
        })

        return jsonify({'status': 'success', **alert})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/priority-queue', methods=['GET'])
@require_auth
def priority_queue():
    """
    Get the unified backlink opportunity queue, auto-scored by composite priority.
    Combines: broken links, Wikipedia gaps, citation authority, competitor alerts.
    """
    try:
        items = scan_table(OPPORTUNITIES_TABLE, 200)

        # Enrich with composite scoring
        for item in items:
            base = item.get('priority_score', 50)
            # Boost Wikipedia opportunities
            if item.get('opportunity_type') == 'wikipedia_citation_gap':
                base = max(base, 90)
            # Boost broken link reclaims on high-DA pages
            if item.get('opportunity_type') == 'broken_link_reclaim':
                base = max(base, 70)
            item['composite_score'] = base

        items.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

        # Group by type
        by_type = {}
        for item in items:
            t = item.get('opportunity_type', 'unknown')
            by_type[t] = by_type.get(t, 0) + 1

        return jsonify({
            'status': 'success',
            'opportunities': items[:100],
            'total': len(items),
            'by_type': by_type,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/decay-predict', methods=['POST'])
@require_auth
def predict_link_decay():
    """
    Predict which existing backlinks are at risk of disappearing.
    Based on: link age, source domain health, and historical patterns.
    """
    data = request.get_json() or {}
    domain = data.get('domain', '').strip()
    if not domain:
        return jsonify({'status': 'error', 'message': 'domain required'}), 400
    try:
        # Get all stored data for this domain
        items = scan_table(BACKLINKS_TABLE, 200)
        domain_data = [i for i in items if (i.get('domain', '') or '').lower() == domain.lower()]

        at_risk = []
        for item in domain_data:
            risk_score = 0
            reasons = []

            # Old scores with declining trend
            if item.get('type') == 'domain_score':
                da = item.get('da_score', 0)
                if da < 20:
                    risk_score += 30
                    reasons.append('Low DA ({})'.format(da))

            # Broken link opportunities (already dead)
            if item.get('type') == 'link_gap':
                gaps = item.get('gaps', [])
                if len(gaps) > 3:
                    risk_score += 20
                    reasons.append('{} competitive gaps'.format(len(gaps)))

            if risk_score > 0:
                at_risk.append({
                    'id': item.get('id'),
                    'type': item.get('type'),
                    'risk_score': risk_score,
                    'reasons': reasons,
                    'created_at': item.get('created_at', item.get('scored_at', '')),
                })

        at_risk.sort(key=lambda x: x.get('risk_score', 0), reverse=True)

        return jsonify({
            'status': 'success',
            'domain': domain,
            'at_risk_count': len(at_risk),
            'at_risk': at_risk[:20],
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/report', methods=['POST'])
@require_auth
def generate_backlink_report():
    """
    Generate a comprehensive backlink report for a domain.
    Combines: DA score, toxic analysis, link gaps, citation authority, opportunities.
    """
    data = request.get_json() or {}
    domain = data.get('domain', '').strip()
    competitors = data.get('competitors', [])
    if not domain:
        return jsonify({'status': 'error', 'message': 'domain required'}), 400
    try:
        # Score the domain
        da_result = _estimate_domain_authority(domain)

        # Get stored history
        items = scan_table(BACKLINKS_TABLE, 200)
        domain_history = [i for i in items if (i.get('domain', '') or '').lower() == domain.lower()]

        # Get opportunities
        opps = scan_table(OPPORTUNITIES_TABLE, 100)

        # Competitor comparison
        comp_scores = []
        for comp in competitors[:3]:
            comp_scores.append(_estimate_domain_authority(comp))

        report = {
            'domain': domain,
            'da_score': da_result['da_score'],
            'signals': da_result['signals'],
            'history_count': len(domain_history),
            'opportunities_count': len(opps),
            'competitors': comp_scores,
            'generated_at': _now(),
        }

        # Store the report
        report_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': report_id,
            'type': 'backlink_report',
            'domain': domain,
            'report': report,
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({'status': 'success', 'id': report_id, 'report': report})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== WHITE-LABEL HTML REPORT (S3 download) =====================

import boto3 as _report_boto3

_report_s3 = _report_boto3.client('s3', region_name='us-east-1')
_REPORT_BUCKET = 'ai1stseo-documents'


def _generate_report_html(domain, da_result, competitors, opportunities, config):
    """Generate a branded HTML backlink report."""
    brand = config.get('brand_name', 'AI 1st SEO')
    primary = config.get('primary_color', '#00d4ff')
    accent = config.get('accent_color', '#7b2cbf')
    logo = config.get('logo_url', '')
    footer = config.get('footer_text', 'AI 1st SEO — AI-Powered Search Engine Optimization')

    # Build competitor rows
    comp_rows = ''
    for c in competitors:
        comp_rows += '<tr><td>{}</td><td>{}</td><td>{}</td></tr>\n'.format(
            c.get('domain', ''), c.get('da_score', 0),
            'Yes' if c.get('signals', {}).get('https') else 'No')

    # Build opportunity rows
    opp_rows = ''
    for o in opportunities[:10]:
        opp_rows += '<tr><td>{}</td><td>{}</td><td>{}</td></tr>\n'.format(
            o.get('source_url', '')[:60], o.get('opportunity_type', ''),
            o.get('priority_score', 0))

    # Signal breakdown
    signals = da_result.get('signals', {})
    signal_items = ''
    for k, v in signals.items():
        if k == 'error':
            continue
        signal_items += '<tr><td>{}</td><td>{}</td></tr>\n'.format(k, v)

    logo_html = '<img src="{}" style="max-height:50px;" />'.format(logo) if logo else ''

    html = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Backlink Report — {domain}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
  h1 {{ color: {primary}; border-bottom: 3px solid {accent}; padding-bottom: 10px; }}
  h2 {{ color: {accent}; margin-top: 30px; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
  .brand {{ font-size: 24px; font-weight: bold; color: {primary}; }}
  .score-box {{ background: linear-gradient(135deg, {primary}, {accent}); color: white; padding: 30px;
    border-radius: 12px; text-align: center; margin: 20px 0; }}
  .score-box .score {{ font-size: 64px; font-weight: bold; }}
  .score-box .label {{ font-size: 18px; opacity: 0.9; }}
  table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
  th {{ background: #f5f5f5; font-weight: 600; color: {accent}; }}
  tr:hover {{ background: #fafafa; }}
  .footer {{ margin-top: 40px; padding-top: 20px; border-top: 2px solid #eee; color: #888; font-size: 13px; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
  .badge-green {{ background: #e6f9e6; color: #2d7d2d; }}
  .badge-red {{ background: #fde8e8; color: #c0392b; }}
  .badge-yellow {{ background: #fff8e1; color: #f39c12; }}
  @media print {{ body {{ margin: 20px; }} .score-box {{ -webkit-print-color-adjust: exact; }} }}
</style>
</head>
<body>
<div class="header">
  <div>{logo_html}<span class="brand">{brand}</span></div>
  <div style="color:#888;">Generated: {date}</div>
</div>

<h1>Backlink Analysis Report</h1>
<p><strong>Domain:</strong> {domain}</p>

<div class="score-box">
  <div class="score">{da_score}</div>
  <div class="label">Domain Authority Score (0-100)</div>
</div>

<h2>Signal Breakdown</h2>
<table>
  <tr><th>Signal</th><th>Value</th></tr>
  {signal_items}
</table>

<h2>Competitor Comparison</h2>
{comp_section}

<h2>Top Backlink Opportunities</h2>
{opp_section}

<div class="footer">
  <p>{footer}</p>
  <p>Report ID: {report_id} | This report was generated automatically by {brand}.</p>
</div>
</body>
</html>'''

    comp_section = '<p>No competitors analyzed.</p>'
    if comp_rows:
        comp_section = '<table><tr><th>Domain</th><th>DA Score</th><th>HTTPS</th></tr>\n{}</table>'.format(comp_rows)

    opp_section = '<p>No opportunities found yet. Run backlink scans to populate.</p>'
    if opp_rows:
        opp_section = '<table><tr><th>Source URL</th><th>Type</th><th>Priority</th></tr>\n{}</table>'.format(opp_rows)

    return html.format(
        domain=domain,
        primary=primary,
        accent=accent,
        brand=brand,
        logo_html=logo_html,
        date=_now()[:10],
        da_score=da_result.get('da_score', 0),
        signal_items=signal_items,
        comp_section=comp_section,
        opp_section=opp_section,
        footer=footer,
        report_id=str(uuid.uuid4())[:8],
    )


@backlink_bp.route('/api/backlinks/report/download', methods=['POST'])
@require_auth
def generate_downloadable_report():
    """
    Generate a white-label HTML backlink report, upload to S3, return presigned URL.
    Uses the white-label config from admin settings for branding.
    """
    data = request.get_json() or {}
    domain = data.get('domain', '').strip()
    competitors = data.get('competitors', [])
    if not domain:
        return jsonify({'status': 'error', 'message': 'domain required'}), 400

    try:
        # Score the domain
        da_result = _estimate_domain_authority(domain)

        # Score competitors
        comp_scores = []
        for comp in competitors[:3]:
            comp_scores.append(_estimate_domain_authority(comp))

        # Get opportunities
        opps = scan_table(OPPORTUNITIES_TABLE, 50)
        opps.sort(key=lambda x: x.get('priority_score', 0), reverse=True)

        # Get white-label config
        config = {}
        try:
            config = get_item('ai1stseo-admin-metrics', {'metric_date': 'white_label_config'}) or {}
        except Exception:
            pass

        # Generate HTML
        html = _generate_report_html(domain, da_result, comp_scores, opps, config)

        # Upload to S3
        report_id = str(uuid.uuid4())
        s3_key = 'reports/backlink-{}-{}.html'.format(
            domain.replace('.', '-'), report_id[:8])

        _report_s3.put_object(
            Bucket=_REPORT_BUCKET,
            Key=s3_key,
            Body=html.encode('utf-8'),
            ContentType='text/html',
        )

        # Generate presigned URL (valid 24 hours)
        url = _report_s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': _REPORT_BUCKET,
                'Key': s3_key,
                'ResponseContentDisposition': 'inline; filename="backlink-report-{}.html"'.format(domain),
            },
            ExpiresIn=86400,
        )

        # Store report metadata
        put_item(BACKLINKS_TABLE, {
            'id': report_id,
            'type': 'backlink_report_download',
            'domain': domain,
            's3_key': s3_key,
            'da_score': da_result['da_score'],
            'competitors': [c.get('domain') for c in comp_scores],
            'opportunities_count': len(opps),
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({
            'status': 'success',
            'id': report_id,
            'download_url': url,
            'expires_in': 86400,
            'domain': domain,
            'da_score': da_result['da_score'],
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
