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
    Supports country/persona/language segmentation for market-specific insights.
    """
    data = request.get_json() or {}
    queries = data.get('queries', [])
    niche = data.get('niche', 'SEO')
    country = data.get('country', '').strip()       # e.g. "Canada", "US", "UK"
    persona = data.get('persona', '').strip()        # e.g. "small business owner", "enterprise CMO"
    language = data.get('language', '').strip()       # e.g. "French", "Spanish"
    if not queries:
        return jsonify({'status': 'error', 'message': 'queries[] required (list of prompts to send to AI models)'}), 400

    try:
        import re
        from collections import Counter

        cited_domains = Counter()
        cited_pages = Counter()  # Page-level tracking
        probe_results = []

        # Use our AI inference to probe — this calls the Ollama accelerator or Bedrock
        try:
            from ai_inference import generate
        except ImportError:
            generate = None

        for query in queries[:20]:  # Cap at 20 queries
            if not generate:
                break

            # Build context-aware prompt with segmentation
            context_parts = []
            if country:
                context_parts.append('Answer from the perspective of someone in {}.'.format(country))
            if persona:
                context_parts.append('The user is a {}.'.format(persona))
            if language:
                context_parts.append('Respond in {}.'.format(language))
            context = ' '.join(context_parts)

            prompt = (
                '{context}'
                'Answer this question and cite specific websites as sources. '
                'Include full URLs where possible: {query}'
            ).format(context=context + ' ' if context else '', query=query)

            response = generate(prompt, max_tokens=1024, temperature=0.3, triggered_by='citation_probe')

            # Extract URLs from the response
            urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', response)
            domains_found = []
            pages_found = []
            for url in urls:
                parsed = urlparse(url)
                domain = parsed.netloc
                if domain and len(domain) > 3:
                    cited_domains[domain] += 1
                    domains_found.append(domain)
                    # Track full page URL (not just domain)
                    clean_url = '{}://{}{}'.format(parsed.scheme, parsed.netloc, parsed.path.rstrip('/'))
                    cited_pages[clean_url] += 1
                    pages_found.append(clean_url)

            probe_results.append({
                'query': query,
                'domains_cited': list(set(domains_found)),
                'pages_cited': list(set(pages_found)),
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

        # Build page-level citation scores
        page_scores = []
        for page_url, count in cited_pages.most_common(50):
            page_scores.append({
                'url': page_url,
                'domain': urlparse(page_url).netloc,
                'citation_count': count,
                'citation_frequency': round(count / len(queries) * 100, 1) if queries else 0,
            })

        # Store the probe with segmentation metadata
        probe_id = str(uuid.uuid4())
        probe_record = {
            'id': probe_id,
            'type': 'citation_authority',
            'niche': niche,
            'queries_count': len(queries),
            'top_cited_domains': authority_scores[:20],
            'top_cited_pages': page_scores[:20],
            'probe_results': probe_results,
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        }
        # Add segmentation fields if provided
        if country:
            probe_record['country'] = country
        if persona:
            probe_record['persona'] = persona
        if language:
            probe_record['language'] = language

        put_item(BACKLINKS_TABLE, probe_record)

        result = {
            'status': 'success',
            'id': probe_id,
            'total_domains_cited': len(cited_domains),
            'total_pages_cited': len(cited_pages),
            'top_cited': authority_scores[:20],
            'top_cited_pages': page_scores[:20],
            'probes': probe_results,
        }
        if country:
            result['country'] = country
        if persona:
            result['persona'] = persona
        if language:
            result['language'] = language

        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/citation-scores', methods=['GET'])
@require_auth
def get_citation_scores():
    """Get stored citation authority scores. Filter by niche, country, persona."""
    niche = request.args.get('niche', '')
    country = request.args.get('country', '')
    persona = request.args.get('persona', '')
    try:
        items = scan_table(BACKLINKS_TABLE, 100)
        probes = [i for i in items if i.get('type') == 'citation_authority']
        if niche:
            probes = [p for p in probes if niche.lower() in (p.get('niche', '') or '').lower()]
        if country:
            probes = [p for p in probes if country.lower() in (p.get('country', '') or '').lower()]
        if persona:
            probes = [p for p in probes if persona.lower() in (p.get('persona', '') or '').lower()]
        probes.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'status': 'success', 'probes': probes[:20]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== AI SENTIMENT & HALLUCINATION MONITORING =====================

@backlink_bp.route('/api/backlinks/brand-sentiment', methods=['POST'])
@require_auth
def brand_sentiment_probe():
    """
    Probe AI models for brand sentiment and factual accuracy.
    Sends brand-specific queries to AI, then analyzes the response for:
    - Sentiment (positive/neutral/negative)
    - Factual accuracy (hallucination detection)
    - Competitor mentions in the same response
    - Recommendation strength (does the AI recommend the brand?)
    """
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    domain = data.get('domain', '').strip()
    queries = data.get('queries', [])
    if not brand:
        return jsonify({'status': 'error', 'message': 'brand name required'}), 400

    # Default queries if none provided
    if not queries:
        queries = [
            'What is {} and is it any good?'.format(brand),
            'What are the pros and cons of {}?'.format(brand),
            'Would you recommend {} for SEO?'.format(brand),
            'Compare {} to its competitors.'.format(brand),
            'Is {} trustworthy and reliable?'.format(brand),
        ]

    try:
        import re
        try:
            from ai_inference import generate
        except ImportError:
            generate = None

        if not generate:
            return jsonify({'status': 'error', 'message': 'AI inference not available'}), 503

        results = []
        sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        total_recommendation_score = 0

        for query in queries[:10]:
            response = generate(query, max_tokens=1024, temperature=0.3, triggered_by='sentiment_probe')
            response_lower = response.lower()
            brand_lower = brand.lower()

            # Sentiment analysis (keyword-based heuristic)
            positive_signals = ['recommend', 'excellent', 'great', 'powerful', 'effective',
                                'impressive', 'reliable', 'trusted', 'innovative', 'leading',
                                'best', 'top', 'strong', 'valuable', 'worth']
            negative_signals = ['avoid', 'poor', 'weak', 'unreliable', 'expensive', 'limited',
                                'lacking', 'disappointing', 'outdated', 'concern', 'issue',
                                'problem', 'drawback', 'downside', 'risk']

            pos_count = sum(1 for w in positive_signals if w in response_lower)
            neg_count = sum(1 for w in negative_signals if w in response_lower)

            if pos_count > neg_count + 1:
                sentiment = 'positive'
            elif neg_count > pos_count + 1:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            sentiment_counts[sentiment] += 1

            # Recommendation strength (0-100)
            rec_score = 50  # neutral baseline
            if 'recommend' in response_lower and brand_lower in response_lower:
                rec_score = 80
            if 'highly recommend' in response_lower:
                rec_score = 95
            if 'not recommend' in response_lower or 'avoid' in response_lower:
                rec_score = 15
            total_recommendation_score += rec_score

            # Brand mention check
            brand_mentioned = brand_lower in response_lower
            brand_mention_count = response_lower.count(brand_lower)

            # Domain mention check
            domain_mentioned = domain.lower() in response_lower if domain else False

            # Competitor detection (other brands mentioned)
            competitor_mentions = []
            common_seo_brands = ['semrush', 'ahrefs', 'moz', 'surfer', 'clearscope',
                                 'brightedge', 'conductor', 'se ranking', 'seoclarity']
            for comp in common_seo_brands:
                if comp in response_lower and comp != brand_lower:
                    competitor_mentions.append(comp)

            # Hallucination flags (claims we can check)
            hallucination_flags = []
            # Check for made-up pricing
            price_matches = re.findall(r'\$[\d,]+(?:\.\d{2})?(?:/mo| per month| monthly)?', response)
            if price_matches:
                hallucination_flags.append({
                    'type': 'pricing_claim',
                    'claims': price_matches,
                    'note': 'Verify these prices are accurate',
                })
            # Check for specific year claims
            year_matches = re.findall(r'(?:founded|launched|started|since|established)\s+(?:in\s+)?(\d{4})', response_lower)
            if year_matches:
                hallucination_flags.append({
                    'type': 'founding_date_claim',
                    'claims': year_matches,
                    'note': 'Verify founding/launch dates',
                })

            results.append({
                'query': query,
                'sentiment': sentiment,
                'positive_signals': pos_count,
                'negative_signals': neg_count,
                'recommendation_score': rec_score,
                'brand_mentioned': brand_mentioned,
                'brand_mention_count': brand_mention_count,
                'domain_mentioned': domain_mentioned,
                'competitor_mentions': competitor_mentions,
                'hallucination_flags': hallucination_flags,
                'response_length': len(response),
            })

        # Aggregate
        avg_rec = round(total_recommendation_score / len(queries), 1) if queries else 0
        dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)

        # Store the probe
        probe_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': probe_id,
            'type': 'brand_sentiment',
            'brand': brand,
            'domain': domain,
            'queries_count': len(queries),
            'dominant_sentiment': dominant_sentiment,
            'sentiment_breakdown': sentiment_counts,
            'avg_recommendation_score': avg_rec,
            'results': results,
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({
            'status': 'success',
            'id': probe_id,
            'brand': brand,
            'dominant_sentiment': dominant_sentiment,
            'sentiment_breakdown': sentiment_counts,
            'avg_recommendation_score': avg_rec,
            'total_hallucination_flags': sum(len(r.get('hallucination_flags', [])) for r in results),
            'results': results,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/brand-sentiment/history', methods=['GET'])
@require_auth
def brand_sentiment_history():
    """Get brand sentiment probe history. Filter by brand name."""
    brand = request.args.get('brand', '')
    try:
        items = scan_table(BACKLINKS_TABLE, 100)
        probes = [i for i in items if i.get('type') == 'brand_sentiment']
        if brand:
            probes = [p for p in probes if brand.lower() in (p.get('brand', '') or '').lower()]
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


# ===================== WEB MENTION / PR MONITORING =====================

@backlink_bp.route('/api/mentions/scan', methods=['POST'])
@require_auth
def scan_web_mentions():
    """
    Scan the web for brand mentions. Checks Google News and Reddit
    for unlinked mentions — each is a potential backlink opportunity.
    """
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    domain = data.get('domain', '').strip()
    if not brand:
        return jsonify({'status': 'error', 'message': 'brand name required'}), 400

    try:
        mentions = []

        # 1. Google News search via RSS
        try:
            from urllib.parse import quote_plus
            news_url = 'https://news.google.com/rss/search?q={}&hl=en'.format(quote_plus(brand))
            news_resp = http_requests.get(news_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO/1.0)'
            })
            if news_resp.status_code == 200:
                # Parse RSS XML
                import xml.etree.ElementTree as ET
                root = ET.fromstring(news_resp.content)
                for item in root.findall('.//item')[:20]:
                    title = item.findtext('title', '')
                    link = item.findtext('link', '')
                    pub_date = item.findtext('pubDate', '')
                    source = item.findtext('source', '')

                    # Check if the mention links to our domain
                    has_link = domain.lower() in link.lower() if domain else False

                    mentions.append({
                        'source': 'google_news',
                        'title': title,
                        'url': link,
                        'published': pub_date,
                        'publication': source,
                        'has_backlink': has_link,
                        'opportunity_type': 'linked' if has_link else 'unlinked_mention',
                    })
        except Exception as e:
            mentions.append({'source': 'google_news', 'error': str(e)[:100]})

        # 2. Reddit search
        try:
            reddit_url = 'https://www.reddit.com/search.json?q={}&sort=new&limit=20'.format(
                quote_plus(brand))
            reddit_resp = http_requests.get(reddit_url, timeout=10, headers={
                'User-Agent': 'AI1stSEO-MentionScanner/1.0'
            })
            if reddit_resp.status_code == 200:
                reddit_data = reddit_resp.json()
                for post in reddit_data.get('data', {}).get('children', []):
                    p = post.get('data', {})
                    post_url = 'https://reddit.com{}'.format(p.get('permalink', ''))
                    selftext = p.get('selftext', '')

                    has_link = domain.lower() in selftext.lower() if domain else False

                    mentions.append({
                        'source': 'reddit',
                        'title': p.get('title', ''),
                        'url': post_url,
                        'subreddit': p.get('subreddit', ''),
                        'score': p.get('score', 0),
                        'num_comments': p.get('num_comments', 0),
                        'published': datetime.fromtimestamp(
                            p.get('created_utc', 0), tz=timezone.utc
                        ).isoformat() if p.get('created_utc') else '',
                        'has_backlink': has_link,
                        'opportunity_type': 'linked' if has_link else 'unlinked_mention',
                    })
        except Exception as e:
            mentions.append({'source': 'reddit', 'error': str(e)[:100]})

        # Separate linked vs unlinked
        unlinked = [m for m in mentions if m.get('opportunity_type') == 'unlinked_mention']
        linked = [m for m in mentions if m.get('opportunity_type') == 'linked']

        # Store unlinked mentions as backlink opportunities
        for m in unlinked[:10]:
            if m.get('url'):
                put_item(OPPORTUNITIES_TABLE, {
                    'source_url': m['url'],
                    'opportunity_type': 'unlinked_mention',
                    'brand': brand,
                    'title': m.get('title', ''),
                    'source_platform': m.get('source', ''),
                    'priority_score': 65,
                    'status': 'new',
                    'project_id': DEFAULT_PROJECT_ID,
                    'created_by': _get_user_id(),
                })

        # Store the scan
        scan_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': scan_id,
            'type': 'mention_scan',
            'brand': brand,
            'domain': domain,
            'total_mentions': len(mentions),
            'unlinked_count': len(unlinked),
            'linked_count': len(linked),
            'sources_checked': ['google_news', 'reddit'],
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({
            'status': 'success',
            'id': scan_id,
            'brand': brand,
            'total_mentions': len(mentions),
            'unlinked_count': len(unlinked),
            'linked_count': len(linked),
            'mentions': mentions,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/mentions/history', methods=['GET'])
@require_auth
def mention_scan_history():
    """Get brand mention scan history."""
    brand = request.args.get('brand', '')
    try:
        items = scan_table(BACKLINKS_TABLE, 100)
        scans = [i for i in items if i.get('type') == 'mention_scan']
        if brand:
            scans = [s for s in scans if brand.lower() in (s.get('brand', '') or '').lower()]
        scans.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'status': 'success', 'scans': scans[:20]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== INTERNAL LINK ANALYSIS =====================

@backlink_bp.route('/api/internal-links/analyze', methods=['POST'])
@require_auth
def analyze_internal_links():
    """
    Crawl a site's pages and analyze the internal link structure.
    Detects: orphan pages, over-linked pages, poor anchor text,
    and suggests new internal links between related pages.
    """
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    max_pages = data.get('max_pages', 20)
    if not url:
        return jsonify({'status': 'error', 'message': 'url required'}), 400

    try:
        from bs4 import BeautifulSoup
        from collections import defaultdict

        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc
        if not base_domain:
            return jsonify({'status': 'error', 'message': 'Invalid URL'}), 400

        # Crawl pages starting from the given URL
        visited = set()
        to_visit = [url]
        pages = {}  # url -> {title, internal_links, external_links, word_count}
        link_graph = defaultdict(set)  # source -> set of targets
        inbound_count = defaultdict(int)  # target -> count of pages linking to it

        while to_visit and len(visited) < min(max_pages, 30):
            current = to_visit.pop(0)
            if current in visited:
                continue
            visited.add(current)

            try:
                resp = http_requests.get(current, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; AI1stSEO/1.0)'
                }, allow_redirects=True)
                if resp.status_code != 200 or 'text/html' not in resp.headers.get('content-type', ''):
                    continue

                soup = BeautifulSoup(resp.content, 'html.parser')
                title = soup.find('title')
                title_text = title.get_text().strip() if title else current

                # Extract links
                all_links = soup.find_all('a', href=True)
                internal_links = []
                external_links = []

                for link in all_links:
                    href = link.get('href', '')
                    # Resolve relative URLs
                    from urllib.parse import urljoin
                    full_url = urljoin(current, href)
                    link_parsed = urlparse(full_url)

                    if link_parsed.netloc == base_domain:
                        # Internal link
                        clean = '{}://{}{}'.format(link_parsed.scheme, link_parsed.netloc,
                                                    link_parsed.path.rstrip('/'))
                        anchor = link.get_text().strip()[:100]
                        internal_links.append({'url': clean, 'anchor': anchor})
                        link_graph[current].add(clean)
                        inbound_count[clean] += 1

                        # Add to crawl queue
                        if clean not in visited and clean not in to_visit:
                            to_visit.append(clean)
                    elif link_parsed.scheme in ('http', 'https'):
                        external_links.append({
                            'url': full_url[:200],
                            'anchor': link.get_text().strip()[:100],
                        })

                word_count = len(soup.get_text().split())

                pages[current] = {
                    'url': current,
                    'title': title_text[:200],
                    'internal_link_count': len(internal_links),
                    'external_link_count': len(external_links),
                    'word_count': word_count,
                    'internal_links': internal_links[:20],
                }

            except Exception:
                continue

        # Analysis
        all_crawled_urls = set(pages.keys())

        # Orphan pages: pages that exist but no other page links to them
        orphan_pages = []
        for page_url in all_crawled_urls:
            if inbound_count.get(page_url, 0) == 0 and page_url != url:
                orphan_pages.append({
                    'url': page_url,
                    'title': pages[page_url]['title'],
                    'issue': 'No internal links point to this page',
                })

        # Over-linked pages: pages with too many outbound internal links
        over_linked = []
        under_linked = []
        for page_url, page_data in pages.items():
            count = page_data['internal_link_count']
            if count > 50:
                over_linked.append({
                    'url': page_url,
                    'title': page_data['title'],
                    'internal_links': count,
                    'issue': 'Too many internal links ({}) — dilutes link equity'.format(count),
                })
            elif count < 2 and page_data['word_count'] > 200:
                under_linked.append({
                    'url': page_url,
                    'title': page_data['title'],
                    'internal_links': count,
                    'word_count': page_data['word_count'],
                    'issue': 'Only {} internal link(s) on a {}-word page'.format(count, page_data['word_count']),
                })

        # Generic anchor text detection
        generic_anchors = []
        generic_terms = {'click here', 'read more', 'learn more', 'here', 'link', 'this', 'more'}
        for page_url, page_data in pages.items():
            for link in page_data.get('internal_links', []):
                if link['anchor'].lower().strip() in generic_terms:
                    generic_anchors.append({
                        'page': page_url,
                        'target': link['url'],
                        'anchor': link['anchor'],
                        'issue': 'Generic anchor text — use descriptive keywords instead',
                    })

        # Store the analysis
        analysis_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': analysis_id,
            'type': 'internal_link_analysis',
            'domain': base_domain,
            'pages_crawled': len(pages),
            'orphan_count': len(orphan_pages),
            'over_linked_count': len(over_linked),
            'under_linked_count': len(under_linked),
            'generic_anchor_count': len(generic_anchors),
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({
            'status': 'success',
            'id': analysis_id,
            'domain': base_domain,
            'pages_crawled': len(pages),
            'issues': {
                'orphan_pages': orphan_pages[:10],
                'over_linked': over_linked[:10],
                'under_linked': under_linked[:10],
                'generic_anchors': generic_anchors[:20],
            },
            'summary': {
                'total_pages': len(pages),
                'total_internal_links': sum(p['internal_link_count'] for p in pages.values()),
                'avg_internal_links': round(
                    sum(p['internal_link_count'] for p in pages.values()) / max(len(pages), 1), 1),
                'orphan_pages': len(orphan_pages),
                'over_linked_pages': len(over_linked),
                'under_linked_pages': len(under_linked),
                'generic_anchor_issues': len(generic_anchors),
            },
            'pages': list(pages.values())[:20],
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== ANSWER FINGERPRINT CHANGE DETECTION =====================

import hashlib as _hashlib

@backlink_bp.route('/api/backlinks/fingerprint-probe', methods=['POST'])
@require_auth
def fingerprint_probe():
    """
    Probe an AI model and fingerprint the response. Compares against previous
    fingerprint for the same query+model to detect answer changes.
    Returns: current response, hash, and diff against previous if one exists.
    """
    data = request.get_json() or {}
    query_text = data.get('query', '').strip()
    model = data.get('model', 'default')
    brand = data.get('brand', '').strip()
    if not query_text:
        return jsonify({'status': 'error', 'message': 'query required'}), 400

    try:
        import re

        try:
            from ai_inference import generate
        except ImportError:
            return jsonify({'status': 'error', 'message': 'AI inference not available'}), 503

        # Generate response
        response_text = generate(query_text, max_tokens=1024, temperature=0.3,
                                 triggered_by='fingerprint_probe')

        # Hash the response
        response_hash = _hashlib.sha256(response_text.encode('utf-8')).hexdigest()

        # Extract cited URLs
        urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', response_text)
        cited_domains = list(set(urlparse(u).netloc for u in urls if urlparse(u).netloc))

        # Check for brand mention
        brand_mentioned = brand.lower() in response_text.lower() if brand else False

        # Look up previous fingerprint for this query+model
        lookup_key = _hashlib.md5((query_text + '|' + model).encode()).hexdigest()[:16]
        items = scan_table(BACKLINKS_TABLE, 200)
        previous = None
        for item in items:
            if item.get('type') == 'answer_fingerprint' and item.get('lookup_key') == lookup_key:
                if previous is None or item.get('created_at', '') > previous.get('created_at', ''):
                    previous = item

        # Compute diff if previous exists
        diff = None
        changed = False
        if previous:
            prev_hash = previous.get('response_hash', '')
            if prev_hash != response_hash:
                changed = True
                prev_domains = set(previous.get('cited_domains', []))
                curr_domains = set(cited_domains)
                diff = {
                    'hash_changed': True,
                    'previous_hash': prev_hash[:12],
                    'current_hash': response_hash[:12],
                    'domains_added': sorted(curr_domains - prev_domains),
                    'domains_removed': sorted(prev_domains - curr_domains),
                    'domains_unchanged': sorted(curr_domains & prev_domains),
                    'brand_mentioned_before': previous.get('brand_mentioned', False),
                    'brand_mentioned_now': brand_mentioned,
                    'previous_date': previous.get('created_at', ''),
                }
            else:
                diff = {'hash_changed': False, 'message': 'Response identical to previous probe'}

        # Store the fingerprint
        fp_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': fp_id,
            'type': 'answer_fingerprint',
            'lookup_key': lookup_key,
            'query': query_text,
            'model': model,
            'brand': brand,
            'response_hash': response_hash,
            'cited_domains': cited_domains,
            'brand_mentioned': brand_mentioned,
            'response_length': len(response_text),
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        # If answer changed and we have webhooks, dispatch an event
        if changed:
            try:
                from webhook_api import dispatch_event
                dispatch_event('answer.changed', {
                    'query': query_text[:100],
                    'model': model,
                    'brand': brand,
                    'domains_added': diff.get('domains_added', [])[:5],
                    'domains_removed': diff.get('domains_removed', [])[:5],
                })
            except Exception:
                pass

        return jsonify({
            'status': 'success',
            'id': fp_id,
            'query': query_text,
            'model': model,
            'response_hash': response_hash[:12],
            'cited_domains': cited_domains,
            'brand_mentioned': brand_mentioned,
            'changed': changed,
            'diff': diff,
            'has_previous': previous is not None,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@backlink_bp.route('/api/backlinks/fingerprint-history', methods=['GET'])
@require_auth
def fingerprint_history():
    """Get answer fingerprint history. Filter by query or brand."""
    query_filter = request.args.get('query', '')
    brand_filter = request.args.get('brand', '')
    try:
        items = scan_table(BACKLINKS_TABLE, 200)
        fps = [i for i in items if i.get('type') == 'answer_fingerprint']
        if query_filter:
            fps = [f for f in fps if query_filter.lower() in (f.get('query', '') or '').lower()]
        if brand_filter:
            fps = [f for f in fps if brand_filter.lower() in (f.get('brand', '') or '').lower()]
        fps.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'status': 'success', 'fingerprints': fps[:50]})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== CITATION AUTHORITY DATA EXPORT =====================

@backlink_bp.route('/api/backlinks/citation-authority/export', methods=['GET'])
@require_auth
def export_citation_authority():
    """
    Bulk export all citation authority data as JSON.
    Includes: all citation probes, domain scores, page-level citations,
    and historical fingerprints. Designed for data licensing and analytics.
    Query params: ?format=json (default) or ?format=csv&type=citation_authority
    """
    export_format = request.args.get('format', 'json')
    data_type = request.args.get('type', '')  # filter by type
    try:
        items = scan_table(BACKLINKS_TABLE, 500)

        # Filter by type if specified
        if data_type:
            items = [i for i in items if i.get('type') == data_type]
        else:
            # Default: export citation-relevant data only
            citation_types = {'citation_authority', 'domain_score', 'answer_fingerprint',
                              'brand_sentiment', 'backlink_report', 'mention_scan'}
            items = [i for i in items if i.get('type') in citation_types]

        items.sort(key=lambda x: x.get('created_at', x.get('scored_at', '')), reverse=True)

        if export_format == 'csv':
            # Generate CSV
            import io, csv
            output = io.StringIO()
            if items:
                # Flatten top-level keys
                all_keys = set()
                for item in items:
                    all_keys.update(k for k, v in item.items() if not isinstance(v, (dict, list)))
                all_keys = sorted(all_keys)

                writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction='ignore')
                writer.writeheader()
                for item in items:
                    # Flatten: skip nested dicts/lists
                    flat = {k: v for k, v in item.items() if not isinstance(v, (dict, list))}
                    writer.writerow(flat)

            from flask import Response
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=citation-authority-export.csv'}
            )
        else:
            # JSON export
            return jsonify({
                'status': 'success',
                'export_type': 'citation_authority_data',
                'total_records': len(items),
                'data_types': list(set(i.get('type', '') for i in items)),
                'exported_at': _now(),
                'records': items,
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===================== CITATION PROBE BRIDGE (for Content Brief Generator) =====================

@backlink_bp.route('/api/backlinks/brief-citation-probe', methods=['POST'])
@require_auth
def brief_citation_probe():
    """
    Lightweight citation probe designed to be called by the content brief generator.
    Takes a keyword, probes AI models, returns:
    - Which sources AI models cite for this keyword
    - What content formats trigger citations (tables, FAQs, lists)
    - What data points appear in AI answers (prices, stats, comparisons)
    - Green/amber/red signals for the brief

    This bridges Troy's citation engine with Samar's brief pipeline.
    """
    data = request.get_json() or {}
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'status': 'error', 'message': 'keyword required'}), 400

    try:
        import re
        try:
            from ai_inference import generate
        except ImportError:
            return jsonify({'status': 'error', 'message': 'AI inference not available'}), 503

        # Probe with a citation-focused prompt
        prompt = (
            'Answer this question thoroughly and cite specific websites as sources with URLs. '
            'Include statistics, comparisons, and data points where relevant: '
            'What are the best resources and information about "{}"?'
        ).format(keyword)

        response = generate(prompt, max_tokens=1024, temperature=0.3,
                            triggered_by='brief_citation_probe')

        # Extract cited URLs
        urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', response)
        cited_domains = list(set(urlparse(u).netloc for u in urls if urlparse(u).netloc))
        cited_pages = list(set(
            '{}://{}{}'.format(urlparse(u).scheme, urlparse(u).netloc, urlparse(u).path.rstrip('/'))
            for u in urls if urlparse(u).netloc
        ))

        # Detect content formats mentioned
        response_lower = response.lower()
        format_signals = {
            'tables': bool(re.search(r'table|comparison|versus|vs\.', response_lower)),
            'faqs': bool(re.search(r'faq|frequently asked|question', response_lower)),
            'lists': bool(re.search(r'top \d|best \d|\d\.\s', response_lower)),
            'statistics': bool(re.search(r'\d+%|\$\d|million|billion|study|research', response_lower)),
            'how_to': bool(re.search(r'how to|step \d|guide|tutorial', response_lower)),
            'definitions': bool(re.search(r'is defined as|refers to|means that', response_lower)),
        }

        # Build green/amber/red signals for the brief
        green_signals = []  # Include these
        amber_signals = []  # Recommended additions
        red_signals = []    # Gaps/opportunities

        if format_signals['tables']:
            green_signals.append('Comparison tables trigger AI citations — include a comparison table')
        if format_signals['faqs']:
            green_signals.append('FAQ format detected in AI answers — add FAQ schema')
        if format_signals['statistics']:
            green_signals.append('AI cites specific statistics — include data points with sources')
        if format_signals['lists']:
            green_signals.append('Numbered/ranked lists appear in AI answers — use list format')

        if not format_signals['how_to']:
            amber_signals.append('Add step-by-step instructions — AI models prefer actionable content')
        if not format_signals['definitions']:
            amber_signals.append('Add clear definitions — AI models extract these for direct answers')
        if len(cited_domains) < 3:
            amber_signals.append('Few sources cited — opportunity to become a primary source')

        if not cited_domains:
            red_signals.append('No domains cited — AI models lack authoritative sources for this topic')
        if keyword.lower() not in response_lower:
            red_signals.append('Keyword not prominently featured in AI response — content gap')

        # Store the probe
        probe_id = str(uuid.uuid4())
        put_item(BACKLINKS_TABLE, {
            'id': probe_id,
            'type': 'brief_citation_probe',
            'keyword': keyword,
            'cited_domains': cited_domains,
            'cited_pages': cited_pages,
            'format_signals': format_signals,
            'green_signals': green_signals,
            'amber_signals': amber_signals,
            'red_signals': red_signals,
            'created_at': _now(),
            'project_id': DEFAULT_PROJECT_ID,
            'created_by': _get_user_id(),
        })

        return jsonify({
            'status': 'success',
            'id': probe_id,
            'keyword': keyword,
            'cited_domains': cited_domains,
            'cited_pages': cited_pages[:10],
            'format_signals': format_signals,
            'signals': {
                'green': green_signals,
                'amber': amber_signals,
                'red': red_signals,
            },
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
