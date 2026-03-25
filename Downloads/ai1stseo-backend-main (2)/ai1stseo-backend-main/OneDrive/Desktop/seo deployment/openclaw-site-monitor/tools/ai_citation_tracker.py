"""
AI Citation Tracker Tool
Analyzes real citation-readiness signals across prompt archetypes.
Scores content against the patterns AI systems actually extract.
Based on AEO market research: Scrunch, Peec AI, Semrush, Ahrefs, Conductor.
"""

import re
import requests
from datetime import datetime
from typing import TypedDict, List
from urllib.parse import urlparse
from bs4 import BeautifulSoup


class CitationResult(TypedDict):
    prompt_type: str
    query: str
    readiness_score: float
    signals_found: List[str]
    signals_missing: List[str]
    recommendation: str


class AIVisibilityReport(TypedDict):
    brand: str
    domain: str
    queries_tested: int
    citations_found: int
    citation_rate: float
    prompt_scores: dict
    content_signals: dict
    competitor_comparison: dict
    recommendations: List[str]
    timestamp: str


def _fetch_page(url, timeout=10):
    """Fetch and parse a page."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
        return resp, soup
    except Exception:
        return None, None


def _analyze_content_signals(soup, text, html, parsed):
    """Analyze real content signals that determine AI citation likelihood."""
    signals = {}
    word_count = len(text.split())

    # 1. Structured Data Signals
    json_ld = soup.find_all('script', {'type': 'application/ld+json'})
    faq_schema = 'FAQPage' in html or '"Question"' in html
    howto_schema = 'HowTo' in html
    article_schema = 'Article' in html or 'BlogPosting' in html
    org_schema = 'Organization' in html

    signals['structured_data'] = {
        'json_ld_blocks': len(json_ld),
        'has_faq_schema': faq_schema,
        'has_howto_schema': howto_schema,
        'has_article_schema': article_schema,
        'has_org_schema': org_schema,
        'score': min(100, sum([
            30 if json_ld else 0,
            25 if faq_schema else 0,
            15 if howto_schema else 0,
            15 if article_schema else 0,
            15 if org_schema else 0
        ]))
    }

    # 2. Content Extractability
    paragraphs = soup.find_all('p')
    first_para = paragraphs[0].get_text() if paragraphs else ''
    first_para_words = len(first_para.split())
    has_answer_first = any(w in first_para.lower() for w in ['is', 'are', 'means', 'provides', 'helps', 'allows'])
    tables = soup.find_all('table')
    lists = soup.find_all(['ul', 'ol'])
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    question_headings = [h for h in headings if '?' in h.get_text()]
    questions = re.findall(r'(what|how|why|when|where|who|which)\s+[^.?]*\?', text.lower())
    definitions = re.findall(r'\b\w+\s+(?:is|are|means|refers to|defined as)\s+[^.]+\.', text)

    signals['extractability'] = {
        'intro_words': first_para_words,
        'intro_optimal': 20 <= first_para_words <= 60,
        'answer_first': has_answer_first,
        'tables': len(tables),
        'lists': len(lists),
        'question_headings': len(question_headings),
        'qa_patterns': len(questions),
        'definitions': len(definitions),
        'score': min(100, sum([
            20 if 20 <= first_para_words <= 60 and has_answer_first else 5,
            15 if tables else 0,
            15 if len(lists) >= 2 else (5 if lists else 0),
            20 if question_headings else 0,
            15 if len(questions) >= 2 else (5 if questions else 0),
            15 if definitions else 0
        ]))
    }

    # 3. Trust & Evidence
    stat_patterns = re.findall(r'\d+(?:\.\d+)?%|\d+(?:,\d{3})+|\d+x\b', text)
    evidence_words = ['methodology', 'benchmark', 'measured', 'tested', 'analyzed', 'results show', 'findings', 'data shows', 'evidence']
    evidence_count = sum(1 for w in evidence_words if w in text.lower())
    external_links = [a for a in soup.find_all('a', href=True) if a['href'].startswith('http') and parsed.netloc not in a['href']]
    author_patterns = soup.find_all(class_=re.compile(r'author|bio|byline|written-by', re.I))
    has_citations = any(c in text.lower() for c in ['according to', 'source:', 'study shows', 'research', 'data from'])

    signals['trust_evidence'] = {
        'data_points': len(stat_patterns),
        'evidence_language': evidence_count,
        'external_links': len(external_links),
        'has_author': bool(author_patterns),
        'has_citations': has_citations,
        'score': min(100, sum([
            25 if len(stat_patterns) >= 3 else (10 if stat_patterns else 0),
            20 if evidence_count >= 3 else (8 if evidence_count else 0),
            20 if len(external_links) >= 2 else (8 if external_links else 0),
            20 if author_patterns else 0,
            15 if has_citations else 0
        ]))
    }

    # 4. Freshness
    time_elements = soup.find_all('time')
    date_meta = soup.find('meta', property='article:modified_time') or soup.find('meta', property='article:published_time')
    freshness_words = ['updated', 'latest', 'current', '2026', '2025', 'new', 'recently']
    freshness_count = sum(1 for w in freshness_words if w in text.lower())

    signals['freshness'] = {
        'time_elements': len(time_elements),
        'has_date_meta': bool(date_meta),
        'freshness_language': freshness_count,
        'score': min(100, sum([
            35 if time_elements else 0,
            30 if date_meta else 0,
            35 if freshness_count >= 2 else (15 if freshness_count else 0)
        ]))
    }

    # 5. Brand & Differentiation
    brand_name = parsed.netloc.replace('www.', '').split('.')[0]
    brand_mentions = text.lower().count(brand_name)
    has_summary = bool(re.search(r'(?:summary|key takeaway|tl;?dr|in brief|at a glance)', text.lower()))
    main_content = soup.find('main') or soup.find('article')
    value_words = ['unique', 'only', 'first', 'exclusive', 'proprietary', 'unlike', 'our approach']
    value_count = sum(1 for w in value_words if w in text.lower())

    signals['brand'] = {
        'brand_mentions': brand_mentions,
        'has_summary': has_summary,
        'has_main_wrapper': bool(main_content),
        'differentiation': value_count,
        'score': min(100, sum([
            25 if brand_mentions >= 3 else (10 if brand_mentions else 0),
            25 if has_summary else 0,
            25 if main_content else 0,
            25 if value_count >= 2 else (10 if value_count else 0)
        ]))
    }

    # Overall citation readiness score (weighted)
    weights = {
        'structured_data': 0.20,
        'extractability': 0.30,
        'trust_evidence': 0.20,
        'freshness': 0.15,
        'brand': 0.15
    }
    overall = sum(signals[k]['score'] * weights[k] for k in weights)
    signals['overall_score'] = round(overall, 1)

    return signals


# Default prompt archetypes that AI systems commonly serve
PROMPT_ARCHETYPES = {
    'best_x': {
        'label': 'Best X (Listicle)',
        'patterns': ['best', 'top', 'leading', 'recommended', 'most popular'],
        'template': 'best {industry} tools',
        'signals': ['ranked lists', 'comparison tables', 'pros/cons', 'pricing'],
    },
    'x_vs_y': {
        'label': 'X vs Y (Comparison)',
        'patterns': ['vs', 'versus', 'compared to', 'difference between', 'or'],
        'template': '{brand} vs competitors',
        'signals': ['comparison tables', 'feature grids', 'side-by-side'],
    },
    'how_to': {
        'label': 'How To (Tutorial)',
        'patterns': ['how to', 'step by step', 'guide', 'tutorial', 'instructions'],
        'template': 'how to use {brand}',
        'signals': ['numbered steps', 'ordered lists', 'code blocks', 'screenshots'],
    },
    'pricing': {
        'label': 'Pricing & Specs',
        'patterns': ['price', 'pricing', 'cost', 'free', 'plan', 'tier', '$'],
        'template': '{brand} pricing',
        'signals': ['pricing tables', 'plan comparisons', 'dollar amounts'],
    },
    'trusted_source': {
        'label': 'Trusted Source (Authority)',
        'patterns': ['according to', 'source', 'study', 'research', 'data shows'],
        'template': '{industry} statistics',
        'signals': ['citations', 'data points', 'methodology', 'author bio'],
    },
}


def _score_prompt_readiness(soup, text, html, prompt_type, query):
    """Score content readiness for a specific AI prompt archetype."""
    archetype = PROMPT_ARCHETYPES.get(prompt_type, {})
    patterns = archetype.get('patterns', [])
    expected_signals = archetype.get('signals', [])

    signals_found = []
    signals_missing = []
    score = 0

    # Check pattern presence in content
    pattern_hits = sum(1 for p in patterns if p in text.lower())
    if pattern_hits >= 2:
        signals_found.append('Strong pattern match ({}/{})'.format(pattern_hits, len(patterns)))
        score += 25
    elif pattern_hits >= 1:
        signals_found.append('Partial pattern match ({}/{})'.format(pattern_hits, len(patterns)))
        score += 10
    else:
        signals_missing.append('No {} patterns found'.format(archetype.get('label', prompt_type)))

    # Archetype-specific scoring
    if prompt_type == 'best_x':
        lists = soup.find_all(['ul', 'ol'])
        tables = soup.find_all('table')
        if len(lists) >= 2:
            signals_found.append('Ranked lists present ({})'.format(len(lists)))
            score += 20
        else:
            signals_missing.append('Add ranked/numbered lists')
        if tables:
            signals_found.append('Comparison tables ({})'.format(len(tables)))
            score += 20
        else:
            signals_missing.append('Add comparison tables')
        pros_cons = bool(re.search(r'pros?\b|cons?\b|advantage|disadvantage', text.lower()))
        if pros_cons:
            signals_found.append('Pros/cons language')
            score += 15
        else:
            signals_missing.append('Add pros/cons sections')
        pricing = bool(re.search(r'\$\d+|pric|cost|free', text.lower()))
        if pricing:
            signals_found.append('Pricing mentioned')
            score += 10
        else:
            signals_missing.append('Include pricing info')

    elif prompt_type == 'x_vs_y':
        tables = soup.find_all('table')
        vs_patterns = re.findall(r'\b\w+\s+(?:vs\.?|versus|compared to)\s+\w+', text.lower())
        if tables:
            signals_found.append('Comparison table(s) ({})'.format(len(tables)))
            score += 30
        else:
            signals_missing.append('Add side-by-side comparison table')
        if vs_patterns:
            signals_found.append('Direct comparison phrases ({})'.format(len(vs_patterns)))
            score += 20
        else:
            signals_missing.append('Add explicit X vs Y phrasing')
        headings = soup.find_all(['h2', 'h3'])
        comp_headings = [h for h in headings if any(w in h.get_text().lower() for w in ['vs', 'comparison', 'difference'])]
        if comp_headings:
            signals_found.append('Comparison headings')
            score += 15
        else:
            signals_missing.append('Use comparison-focused headings')

    elif prompt_type == 'how_to':
        ordered_lists = soup.find_all('ol')
        step_patterns = re.findall(r'step\s*\d|first,|second,|third,|finally,|next,', text.lower())
        if ordered_lists:
            signals_found.append('Ordered lists ({})'.format(len(ordered_lists)))
            score += 25
        else:
            signals_missing.append('Add numbered/ordered lists')
        if step_patterns:
            signals_found.append('Step indicators ({})'.format(len(step_patterns)))
            score += 20
        else:
            signals_missing.append('Add step-by-step language')
        code_blocks = soup.find_all(['code', 'pre'])
        if code_blocks:
            signals_found.append('Code/example blocks ({})'.format(len(code_blocks)))
            score += 15
        else:
            signals_missing.append('Add code examples or screenshots')
        howto_schema = 'HowTo' in html
        if howto_schema:
            signals_found.append('HowTo schema present')
            score += 10
        else:
            signals_missing.append('Add HowTo structured data')

    elif prompt_type == 'pricing':
        tables = soup.find_all('table')
        pricing_table = any(t for t in tables if any(p in t.get_text().lower() for p in ['price', 'cost', 'plan', '$', 'month']))
        dollar_amounts = re.findall(r'\$\d+', text)
        if pricing_table:
            signals_found.append('Pricing table found')
            score += 30
        else:
            signals_missing.append('Add pricing comparison table')
        if len(dollar_amounts) >= 2:
            signals_found.append('Dollar amounts ({})'.format(len(dollar_amounts)))
            score += 20
        elif dollar_amounts:
            signals_found.append('Some pricing data')
            score += 10
        else:
            signals_missing.append('Add explicit dollar amounts')
        plan_words = re.findall(r'\b(?:free|basic|pro|premium|enterprise|starter|business)\b', text.lower())
        if plan_words:
            signals_found.append('Plan tier names ({})'.format(len(set(plan_words))))
            score += 15
        else:
            signals_missing.append('Name your pricing tiers explicitly')

    elif prompt_type == 'trusted_source':
        stat_patterns = re.findall(r'\d+(?:\.\d+)?%|\d+(?:,\d{3})+|\d+x\b', text)
        if len(stat_patterns) >= 3:
            signals_found.append('Rich data points ({})'.format(len(stat_patterns)))
            score += 25
        elif stat_patterns:
            signals_found.append('Some data ({})'.format(len(stat_patterns)))
            score += 10
        else:
            signals_missing.append('Add statistics and data points')
        evidence_words = ['methodology', 'benchmark', 'measured', 'tested', 'analyzed', 'results show', 'findings']
        ev_count = sum(1 for w in evidence_words if w in text.lower())
        if ev_count >= 2:
            signals_found.append('Evidence language ({})'.format(ev_count))
            score += 20
        else:
            signals_missing.append('Use methodology/evidence language')
        author_el = soup.find_all(class_=re.compile(r'author|bio|byline', re.I))
        if author_el:
            signals_found.append('Author attribution')
            score += 15
        else:
            signals_missing.append('Add visible author bio')
        parsed = urlparse('')
        ext_links = [a for a in soup.find_all('a', href=True) if a['href'].startswith('http')]
        if len(ext_links) >= 2:
            signals_found.append('External citations ({})'.format(len(ext_links)))
            score += 10
        else:
            signals_missing.append('Cite authoritative external sources')

    # Cap at 100
    score = min(100, max(0, score))

    # Generate recommendation
    if score >= 70:
        rec = 'Good readiness for {} queries'.format(archetype.get('label', prompt_type))
    elif score >= 40:
        top_missing = signals_missing[0] if signals_missing else 'Improve content signals'
        rec = 'Moderate readiness — priority: {}'.format(top_missing)
    else:
        top_missing = signals_missing[0] if signals_missing else 'Add archetype-specific content'
        rec = 'Low readiness — {}'.format(top_missing)

    return CitationResult(
        prompt_type=archetype.get('label', prompt_type),
        query=query,
        readiness_score=score,
        signals_found=signals_found,
        signals_missing=signals_missing,
        recommendation=rec,
    )


def check_ai_visibility(domain, brand_name, industry_queries=None):
    """
    Analyze a domain's AI citation readiness using real content signals.
    Returns AIVisibilityReport compatible with existing callers.
    """
    # Normalize domain to URL
    url = domain if domain.startswith('http') else 'https://{}'.format(domain)
    parsed = urlparse(url)

    # Fetch the page
    resp, soup = _fetch_page(url)

    if not soup:
        # Return a safe fallback if page can't be fetched
        return AIVisibilityReport(
            brand=brand_name,
            domain=domain,
            queries_tested=0,
            citations_found=0,
            citation_rate=0.0,
            prompt_scores={},
            content_signals={},
            competitor_comparison={},
            recommendations=['Could not fetch page — check URL and connectivity'],
            timestamp=datetime.now().isoformat(),
        )

    text = soup.get_text()
    html = str(soup)

    # Analyze content signals
    content_signals = _analyze_content_signals(soup, text, html, parsed)

    # Build query list from industry or defaults
    if not industry_queries:
        brand_lower = brand_name.lower().replace(' ', '-')
        industry_queries = [
            ('best_x', 'best {} tools'.format(brand_name.split()[0] if brand_name.split() else 'SEO')),
            ('x_vs_y', '{} vs competitors'.format(brand_name)),
            ('how_to', 'how to use {}'.format(brand_name)),
            ('pricing', '{} pricing'.format(brand_name)),
            ('trusted_source', '{} reviews'.format(brand_name)),
        ]

    # Score each prompt archetype
    prompt_scores = {}
    total_score = 0
    citations_found = 0

    for prompt_type, query in industry_queries:
        result = _score_prompt_readiness(soup, text, html, prompt_type, query)
        prompt_scores[prompt_type] = {
            'label': result['prompt_type'],
            'query': result['query'],
            'score': result['readiness_score'],
            'signals_found': result['signals_found'],
            'signals_missing': result['signals_missing'],
            'recommendation': result['recommendation'],
        }
        total_score += result['readiness_score']
        if result['readiness_score'] >= 50:
            citations_found += 1

    queries_tested = len(industry_queries)
    avg_score = total_score / queries_tested if queries_tested else 0
    citation_rate = round((citations_found / queries_tested) * 100, 1) if queries_tested else 0.0

    # Generate recommendations from weakest areas
    recommendations = []

    # Content signal recommendations
    signal_scores = {k: v['score'] for k, v in content_signals.items() if isinstance(v, dict) and 'score' in v}
    for signal_name, signal_score in sorted(signal_scores.items(), key=lambda x: x[1]):
        if signal_score < 50:
            rec_map = {
                'structured_data': 'Add JSON-LD schema (FAQ, HowTo, Article) for AI parsing',
                'extractability': 'Improve content structure — add Q&A patterns, tables, and concise intro',
                'trust_evidence': 'Add data points, author attribution, and cite authoritative sources',
                'freshness': 'Add visible timestamps and "Updated [date]" signals',
                'brand': 'Strengthen brand signals — add summary section and differentiation language',
            }
            if signal_name in rec_map:
                recommendations.append(rec_map[signal_name])

    # Prompt archetype recommendations
    for ptype, pdata in sorted(prompt_scores.items(), key=lambda x: x[1]['score']):
        if pdata['score'] < 50 and pdata.get('signals_missing'):
            recommendations.append('{}: {}'.format(pdata['label'], pdata['signals_missing'][0]))

    # Always cap at 5 recommendations
    recommendations = recommendations[:5]

    if not recommendations:
        recommendations = ['Content shows strong AI citation readiness across all archetypes']

    return AIVisibilityReport(
        brand=brand_name,
        domain=domain,
        queries_tested=queries_tested,
        citations_found=citations_found,
        citation_rate=citation_rate,
        prompt_scores=prompt_scores,
        content_signals=content_signals,
        competitor_comparison={},
        recommendations=recommendations,
        timestamp=datetime.now().isoformat(),
    )


def compare_with_competitors(domain, brand_name, competitors):
    """
    Compare AI citation readiness between domain and competitors.
    competitors: list of dicts with 'url' and 'name' keys.
    """
    # Analyze our domain
    our_report = check_ai_visibility(domain, brand_name)

    competitor_reports = []
    for comp in competitors:
        comp_url = comp.get('url', comp) if isinstance(comp, dict) else comp
        comp_name = comp.get('name', comp_url) if isinstance(comp, dict) else comp_url
        comp_report = check_ai_visibility(comp_url, comp_name)
        competitor_reports.append(comp_report)

    # Build comparison
    all_reports = [our_report] + competitor_reports
    all_reports_sorted = sorted(all_reports, key=lambda r: r['citation_rate'], reverse=True)

    our_rank = 1
    for i, r in enumerate(all_reports_sorted):
        if r['domain'] == domain or r['domain'] == our_report['domain']:
            our_rank = i + 1
            break

    # Find strengths and weaknesses vs competitors
    our_overall = our_report['content_signals'].get('overall_score', 0)
    comp_avg = 0
    if competitor_reports:
        comp_avg = sum(r['content_signals'].get('overall_score', 0) for r in competitor_reports) / len(competitor_reports)

    insights = []
    if our_overall > comp_avg:
        insights.append('Your content signals score ({:.0f}) beats competitor average ({:.0f})'.format(our_overall, comp_avg))
    else:
        insights.append('Competitors average {:.0f} content signal score vs your {:.0f}'.format(comp_avg, our_overall))

    # Compare by signal category
    signal_categories = ['structured_data', 'extractability', 'trust_evidence', 'freshness', 'brand']
    for cat in signal_categories:
        our_cat = our_report['content_signals'].get(cat, {}).get('score', 0)
        comp_cat_avg = 0
        if competitor_reports:
            comp_cat_avg = sum(r['content_signals'].get(cat, {}).get('score', 0) for r in competitor_reports) / len(competitor_reports)
        if our_cat < comp_cat_avg - 10:
            insights.append('Weak in {}: you score {:.0f} vs competitor avg {:.0f}'.format(cat.replace('_', ' '), our_cat, comp_cat_avg))

    return {
        'your_domain': domain,
        'your_citation_rate': our_report['citation_rate'],
        'your_overall_score': our_overall,
        'your_rank': our_rank,
        'total_compared': len(all_reports),
        'competitor_results': [
            {
                'domain': r['domain'],
                'brand': r['brand'],
                'citation_rate': r['citation_rate'],
                'overall_score': r['content_signals'].get('overall_score', 0),
            }
            for r in competitor_reports
        ],
        'rankings': [
            {'rank': i + 1, 'domain': r['domain'], 'citation_rate': r['citation_rate']}
            for i, r in enumerate(all_reports_sorted)
        ],
        'insights': insights,
        'timestamp': datetime.now().isoformat(),
    }


# OpenClaw tool schema
TOOL_SCHEMA = {
    'name': 'ai_citation_tracker',
    'description': 'Analyzes real AI citation readiness by scoring content against prompt archetypes (best X, X vs Y, how-to, pricing, authority). Uses actual page content analysis instead of simulated data.',
    'parameters': {
        'domain': {
            'type': 'string',
            'description': 'Domain or URL to analyze',
            'required': True,
        },
        'brand_name': {
            'type': 'string',
            'description': 'Brand name for the domain',
            'required': True,
        },
        'industry_queries': {
            'type': 'array',
            'description': 'Optional list of (prompt_type, query) tuples to test',
            'required': False,
        },
        'competitors': {
            'type': 'array',
            'description': 'Optional list of competitor dicts with url and name keys',
            'required': False,
        },
    },
    'functions': {
        'check_ai_visibility': 'Analyze AI citation readiness for a single domain',
        'compare_with_competitors': 'Compare citation readiness across multiple domains',
    },
}
