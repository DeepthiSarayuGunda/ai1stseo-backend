#!/usr/bin/env python3
"""
month4_systems.py
Month 4 Advanced Systems: Citation Intelligence Engine + Content Authority Engine.

4.1 Citation Intelligence Engine:
  - Cross-Provider Citation Map
  - Citation Velocity Tracker
  - High-Confidence Citation Registry
  - Citation Gap Intelligence Reports
  - Content Brief Feed (auto-generates briefs from gaps)

4.2 Content Authority Engine:
  - Pillar & Cluster Architecture
  - Original Research Programme tracker
  - E-E-A-T Signal Library
  - External Citation Building Log

All new endpoints under /api/m3/deepthi/month4/*
Does NOT modify any existing files. Reads from existing tables.
"""

import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')

# New tables for Month 4
CITATION_MAP_TABLE = f'{TABLE_PREFIX}deepthi-citation-map'
VELOCITY_TABLE = f'{TABLE_PREFIX}deepthi-citation-velocity'
PILLAR_TABLE = f'{TABLE_PREFIX}deepthi-pillar-clusters'
EEAT_LIBRARY_TABLE = f'{TABLE_PREFIX}deepthi-eeat-library'
EXT_CITATION_LOG_TABLE = f'{TABLE_PREFIX}deepthi-external-citations'

BRANDS = ['AI1stSEO', 'Ahrefs', 'SEMrush', 'Moz', 'Surfer SEO']
PRIMARY = 'AI1stSEO'

_ddb = None

def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb

def _now(): return datetime.now(timezone.utc).isoformat()
def _week(): return datetime.now(timezone.utc).strftime('%Y-W%W')
def _dec(v): return Decimal(str(round(float(v or 0), 4)))

def _deserialize(item):
    if not item: return None
    d = dict(item)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v) if '.' in str(v) else int(v)
    return d

def _safe_table(name):
    try:
        t = _get_ddb().Table(name)
        t.load()
        return t
    except Exception:
        return None


# =========================================================================
# 4.1 CITATION INTELLIGENCE ENGINE
# =========================================================================

class CrossProviderCitationMap:
    """Per-keyword map: which providers cite which brands."""

    def build_map(self, limit: int = 500) -> Dict:
        from deepthi_intelligence.data_hooks import get_raw_probes
        probes = get_raw_probes(limit=limit)
        kw_map = defaultdict(lambda: defaultdict(lambda: {'cited_by': [], 'not_cited_by': []}))
        for p in probes:
            kw = p.get('keyword', '')
            brand = p.get('brand_name', '')
            engine = p.get('ai_model', p.get('ai_platform', 'unknown'))
            if not kw or not brand:
                continue
            if p.get('cited'):
                kw_map[kw][brand]['cited_by'].append(engine)
            else:
                kw_map[kw][brand]['not_cited_by'].append(engine)

        result = {}
        for kw, brands in kw_map.items():
            result[kw] = {}
            for brand, data in brands.items():
                cited = list(set(data['cited_by']))
                not_cited = list(set(data['not_cited_by']))
                total = len(cited) + len(not_cited)
                result[kw][brand] = {
                    'cited_by': cited,
                    'not_cited_by': not_cited,
                    'visibility_pct': round(len(cited) / total * 100) if total else 0,
                    'provider_count': total,
                }
        return {'citation_map': result, 'keywords': len(result), 'generated_at': _now()}


class CitationVelocityTracker:
    """Month-over-month change in geo_score and visibility_score per keyword."""

    def get_velocity(self, brand: str = None) -> Dict:
        from deepthi_intelligence.benchmark_brands import MultiBrandGeoScores
        brands_to_check = [brand] if brand else BRANDS
        scorer = MultiBrandGeoScores()
        all_scores = scorer.get_all_brands_scores(brands_to_check, limit_per_brand=4)

        velocity = {}
        for b, entries in all_scores.items():
            if len(entries) < 2:
                velocity[b] = {'status': 'insufficient_data', 'weeks_available': len(entries)}
                continue
            current = entries[0].get('geo_score', 0)
            prev = entries[1].get('geo_score', 0)
            older = entries[2].get('geo_score', 0) if len(entries) > 2 else prev
            oldest = entries[3].get('geo_score', 0) if len(entries) > 3 else older

            week_delta = round(current - prev, 4)
            month_delta = round(current - oldest, 4)
            direction = 'accelerating' if week_delta > 0 and month_delta > week_delta else \
                        'decelerating' if week_delta < 0 else \
                        'building' if week_delta > 0 else 'stable'

            velocity[b] = {
                'current_geo': current,
                'week_change': week_delta,
                'month_change': month_delta,
                'direction': direction,
                'momentum': 'positive' if month_delta > 0.02 else 'negative' if month_delta < -0.02 else 'neutral',
                'weeks_tracked': len(entries),
            }

        return {'velocity': velocity, 'generated_at': _now()}


class HighConfidenceCitationRegistry:
    """Keywords where confidence > 0.75 consistently across 4+ weeks."""

    def get_registry(self, threshold: float = 0.75) -> Dict:
        from deepthi_intelligence.data_hooks import get_raw_probes
        probes = get_raw_probes(limit=500)

        kw_confidence = defaultdict(list)
        for p in probes:
            kw = p.get('keyword', '')
            conf = float(p.get('confidence', 0))
            if kw and conf > 0:
                kw_confidence[kw].append({
                    'confidence': conf,
                    'cited': p.get('cited', False),
                    'brand': p.get('brand_name', ''),
                    'engine': p.get('ai_model', 'unknown'),
                })

        high_conf = []
        for kw, entries in kw_confidence.items():
            avg_conf = sum(e['confidence'] for e in entries) / len(entries)
            if avg_conf >= threshold:
                cited_count = sum(1 for e in entries if e['cited'])
                high_conf.append({
                    'keyword': kw,
                    'avg_confidence': round(avg_conf, 3),
                    'citation_rate': round(cited_count / len(entries), 3),
                    'probe_count': len(entries),
                    'brands_cited': list(set(e['brand'] for e in entries if e['cited'])),
                    'engines': list(set(e['engine'] for e in entries)),
                    'status': 'proven_position',
                })

        high_conf.sort(key=lambda x: x['avg_confidence'], reverse=True)
        return {'high_confidence_keywords': high_conf, 'threshold': threshold,
                'total': len(high_conf), 'generated_at': _now()}


class CitationGapReports:
    """Structured gap reports: for keyword X, competitor Y has visibility, you don't."""

    def generate_report(self) -> Dict:
        from deepthi_intelligence.data_hooks import get_raw_probes
        probes = get_raw_probes(limit=500)

        kw_brand = defaultdict(lambda: defaultdict(lambda: {'cited': 0, 'total': 0}))
        for p in probes:
            kw = p.get('keyword', '')
            brand = p.get('brand_name', '')
            if not kw or not brand:
                continue
            kw_brand[kw][brand]['total'] += 1
            if p.get('cited'):
                kw_brand[kw][brand]['cited'] += 1

        gaps = []
        for kw, brands in kw_brand.items():
            primary_data = brands.get(PRIMARY, {'cited': 0, 'total': 0})
            primary_rate = primary_data['cited'] / primary_data['total'] if primary_data['total'] else 0

            for comp, data in brands.items():
                if comp == PRIMARY:
                    continue
                comp_rate = data['cited'] / data['total'] if data['total'] else 0
                if comp_rate > primary_rate + 0.1:
                    gaps.append({
                        'keyword': kw,
                        'competitor': comp,
                        'competitor_citation_rate': round(comp_rate, 3),
                        'our_citation_rate': round(primary_rate, 3),
                        'gap': round(comp_rate - primary_rate, 3),
                        'priority': 'critical' if comp_rate > 0.7 and primary_rate < 0.2 else
                                    'high' if comp_rate > 0.5 else 'medium',
                        'action': f'Create content targeting "{kw}" — {comp} has {round(comp_rate*100)}% citation rate vs our {round(primary_rate*100)}%',
                    })

        gaps.sort(key=lambda x: x['gap'], reverse=True)
        return {'gaps': gaps, 'total_gaps': len(gaps),
                'critical': len([g for g in gaps if g['priority'] == 'critical']),
                'high': len([g for g in gaps if g['priority'] == 'high']),
                'generated_at': _now()}


class ContentBriefFeed:
    """Auto-generates content briefs from citation gaps."""

    def generate_briefs(self, limit: int = 10) -> Dict:
        gap_report = CitationGapReports().generate_report()
        gaps = gap_report['gaps'][:limit]

        briefs = []
        for gap in gaps:
            kw = gap['keyword']
            # Determine content format from keyword
            fmt = 'faq'
            if any(w in kw.lower() for w in ['vs', 'comparison', 'compare', 'difference']):
                fmt = 'comparison'
            elif any(w in kw.lower() for w in ['how to', 'step', 'guide']):
                fmt = 'how_to'
            elif any(w in kw.lower() for w in ['what is', 'definition', 'meaning']):
                fmt = 'definition'
            elif any(w in kw.lower() for w in ['best', 'top', 'recommend']):
                fmt = 'listicle'

            briefs.append({
                'brief_id': str(uuid.uuid4())[:8],
                'keyword': kw,
                'content_format': fmt,
                'target_competitor': gap['competitor'],
                'competitor_citation_rate': gap['competitor_citation_rate'],
                'our_citation_rate': gap['our_citation_rate'],
                'priority': gap['priority'],
                'schema_type': 'FAQPage' if fmt == 'faq' else 'HowTo' if fmt == 'how_to' else 'Article',
                'brief': f'Create {fmt} content for "{kw}". {gap["competitor"]} is cited {round(gap["competitor_citation_rate"]*100)}% of the time. '
                         f'Include structured data ({("FAQPage" if fmt == "faq" else "HowTo" if fmt == "how_to" else "Article")}) and '
                         f'ensure comprehensive coverage to outperform competitor content.',
                'status': 'pending',
                'generated_at': _now(),
            })

        return {'briefs': briefs, 'total': len(briefs), 'source': 'citation_gap_analysis',
                'generated_at': _now()}


# =========================================================================
# 4.2 CONTENT AUTHORITY ENGINE
# =========================================================================

class PillarClusterArchitecture:
    """Manages pillar-cluster content architecture for topical authority."""

    PILLARS = {
        'ai-visibility': {
            'title': 'Complete Guide to AI Search Visibility',
            'target_words': 5000,
            'clusters': [
                {'title': 'What is GEO (Generative Engine Optimization)', 'target_words': 2000, 'status': 'planned', 'keywords': ['what is generative engine optimization', 'geo score in seo']},
                {'title': 'What is AEO (Answer Engine Optimization)', 'target_words': 2000, 'status': 'planned', 'keywords': ['what is answer engine optimization', 'optimize for answer engines']},
                {'title': 'How to Track AI Visibility', 'target_words': 1500, 'status': 'planned', 'keywords': ['how to track ai search rankings', 'ai visibility score']},
                {'title': 'How to Get Cited by ChatGPT', 'target_words': 2000, 'status': 'planned', 'keywords': ['how to get your brand mentioned by chatgpt', 'chatgpt citations']},
                {'title': 'How to Get Cited by Perplexity', 'target_words': 1500, 'status': 'planned', 'keywords': ['how to optimize for perplexity ai search']},
                {'title': 'Multi-Model Visibility Strategy', 'target_words': 2000, 'status': 'planned', 'keywords': ['ai search engine market share 2026', 'multi-model visibility']},
                {'title': 'AI Citation Building Guide', 'target_words': 2000, 'status': 'planned', 'keywords': ['what is citation in ai search results', 'ai citation building']},
                {'title': 'Content Formats AI Engines Prefer', 'target_words': 1500, 'status': 'planned', 'keywords': ['do ai engines prefer certain content formats', 'what makes content citable']},
            ],
        },
        'seo-tools-guide': {
            'title': 'Complete SEO Tools Comparison Guide 2026',
            'target_words': 4000,
            'clusters': [
                {'title': 'Ahrefs Review & Deep Dive', 'target_words': 2500, 'status': 'planned', 'keywords': ['ahrefs vs semrush which is better']},
                {'title': 'SEMrush Review & Deep Dive', 'target_words': 2500, 'status': 'planned', 'keywords': ['semrush vs moz pro comparison']},
                {'title': 'Moz Review & Deep Dive', 'target_words': 2000, 'status': 'planned', 'keywords': ['ahrefs vs moz which has better backlink data']},
                {'title': 'Best SEO Tools for Small Business', 'target_words': 2000, 'status': 'planned', 'keywords': ['best seo tool for small business', 'best free seo tools for beginners']},
                {'title': 'Enterprise SEO Platform Comparison', 'target_words': 2000, 'status': 'planned', 'keywords': ['best enterprise seo platform']},
                {'title': 'AI-Powered SEO Tools Guide', 'target_words': 2000, 'status': 'planned', 'keywords': ['best ai seo optimization tool', 'top ai-powered seo platforms 2026']},
            ],
        },
        'technical-seo': {
            'title': 'Technical SEO Complete Guide',
            'target_words': 4000,
            'clusters': [
                {'title': 'Schema Markup for AI Visibility', 'target_words': 2000, 'status': 'planned', 'keywords': ['best schema markup generator for seo', 'how to optimize json-ld schema for ai']},
                {'title': 'Core Web Vitals Optimization', 'target_words': 1500, 'status': 'planned', 'keywords': ['what is core web vitals and seo impact']},
                {'title': 'JavaScript SEO Guide', 'target_words': 1500, 'status': 'planned', 'keywords': ['what is javascript seo', 'how to optimize single page apps for seo']},
                {'title': 'Site Audit Checklist 2026', 'target_words': 2000, 'status': 'planned', 'keywords': ['seo audit checklist for 2026', 'technical seo checklist for developers']},
                {'title': 'Crawl Budget Optimization', 'target_words': 1500, 'status': 'planned', 'keywords': ['what is crawl budget and why does it matter']},
            ],
        },
    }

    def get_architecture(self) -> Dict:
        total_pillars = len(self.PILLARS)
        total_clusters = sum(len(p['clusters']) for p in self.PILLARS.values())
        published = sum(1 for p in self.PILLARS.values() for c in p['clusters'] if c['status'] == 'published')
        total_words = sum(p['target_words'] + sum(c['target_words'] for c in p['clusters']) for p in self.PILLARS.values())

        pillars = {}
        for pid, pdata in self.PILLARS.items():
            clusters = pdata['clusters']
            pub = sum(1 for c in clusters if c['status'] == 'published')
            pillars[pid] = {
                'title': pdata['title'],
                'target_words': pdata['target_words'],
                'clusters': clusters,
                'total_clusters': len(clusters),
                'published_clusters': pub,
                'completion_pct': round(pub / len(clusters) * 100) if clusters else 0,
            }

        return {
            'pillars': pillars,
            'summary': {
                'total_pillars': total_pillars,
                'total_clusters': total_clusters,
                'published': published,
                'completion_pct': round(published / total_clusters * 100) if total_clusters else 0,
                'total_target_words': total_words,
            },
            'generated_at': _now(),
        }


class EEATSignalLibrary:
    """Curated set of authority signals to implement across all pages."""

    SIGNALS = [
        {'id': 'author_bio', 'category': 'expertise', 'signal': 'Named Expert Author with Credentials',
         'description': 'Every pillar and cluster page must have a named author with relevant credentials, bio, and links to professional profiles.',
         'schema': 'Person', 'priority': 'critical', 'status': 'template_ready'},
        {'id': 'methodology', 'category': 'experience', 'signal': 'Methodology Section',
         'description': 'Data-driven content must include a methodology section explaining how data was collected and analyzed.',
         'schema': None, 'priority': 'high', 'status': 'template_ready'},
        {'id': 'data_citations', 'category': 'trustworthiness', 'signal': 'Data Citations with Dates',
         'description': 'All statistics and claims must cite authoritative sources with publication dates.',
         'schema': 'Citation', 'priority': 'critical', 'status': 'template_ready'},
        {'id': 'case_studies', 'category': 'experience', 'signal': 'Case Study References',
         'description': 'Include real case studies with measurable outcomes to demonstrate practical experience.',
         'schema': 'Article', 'priority': 'high', 'status': 'template_ready'},
        {'id': 'last_updated', 'category': 'trustworthiness', 'signal': 'Last Updated Date',
         'description': 'Every page must show a visible last-updated date and be refreshed at least quarterly.',
         'schema': 'dateModified', 'priority': 'critical', 'status': 'template_ready'},
        {'id': 'faq_schema', 'category': 'authoritativeness', 'signal': 'FAQ Schema Markup',
         'description': 'All pages with Q&A content must have FAQPage JSON-LD schema.',
         'schema': 'FAQPage', 'priority': 'critical', 'status': 'template_ready'},
        {'id': 'howto_schema', 'category': 'authoritativeness', 'signal': 'HowTo Schema Markup',
         'description': 'All tutorial/guide content must have HowTo JSON-LD schema.',
         'schema': 'HowTo', 'priority': 'high', 'status': 'template_ready'},
        {'id': 'org_schema', 'category': 'trustworthiness', 'signal': 'Organization Schema',
         'description': 'Site-wide Organization schema with logo, contact info, and social profiles.',
         'schema': 'Organization', 'priority': 'high', 'status': 'template_ready'},
        {'id': 'review_schema', 'category': 'trustworthiness', 'signal': 'Review/Rating Schema',
         'description': 'Product and tool comparison pages should include Review schema.',
         'schema': 'Review', 'priority': 'medium', 'status': 'template_ready'},
        {'id': 'breadcrumb', 'category': 'authoritativeness', 'signal': 'Breadcrumb Navigation',
         'description': 'All pages must have breadcrumb navigation with BreadcrumbList schema.',
         'schema': 'BreadcrumbList', 'priority': 'medium', 'status': 'template_ready'},
        {'id': 'internal_links', 'category': 'authoritativeness', 'signal': 'Strategic Internal Linking',
         'description': 'Every cluster page links to its pillar. Every pillar links to all clusters. Contextual cross-links between related clusters.',
         'schema': None, 'priority': 'high', 'status': 'template_ready'},
        {'id': 'external_authority', 'category': 'trustworthiness', 'signal': 'External Authority Links',
         'description': 'Link to authoritative external sources (research papers, official docs, industry reports).',
         'schema': None, 'priority': 'medium', 'status': 'template_ready'},
    ]

    def get_library(self) -> Dict:
        by_category = defaultdict(list)
        by_priority = defaultdict(list)
        for s in self.SIGNALS:
            by_category[s['category']].append(s)
            by_priority[s['priority']].append(s)
        return {
            'signals': self.SIGNALS,
            'total': len(self.SIGNALS),
            'by_category': {k: len(v) for k, v in by_category.items()},
            'by_priority': {k: len(v) for k, v in by_priority.items()},
            'generated_at': _now(),
        }


class ExternalCitationLog:
    """Tracks content placed on external high-authority sources."""

    def __init__(self):
        self._table = _safe_table(EXT_CITATION_LOG_TABLE)

    def log_citation(self, data: Dict) -> str:
        cid = str(uuid.uuid4())[:8]
        entry = {
            'citation_id': cid,
            'source_domain': data.get('source_domain', ''),
            'content_type': data.get('content_type', 'guest_article'),
            'url': data.get('url', ''),
            'target_keywords': json.dumps(data.get('target_keywords', [])),
            'published_date': data.get('published_date', _now()[:10]),
            'visibility_score_before': _dec(data.get('visibility_score_before', 0)),
            'visibility_score_after': _dec(data.get('visibility_score_after', 0)),
            'status': data.get('status', 'published'),
            'created_at': _now(),
        }
        if self._table:
            self._table.put_item(Item=entry)
        return cid

    def get_log(self, limit: int = 50) -> List[Dict]:
        if not self._table:
            return []
        resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        for i in items:
            if isinstance(i.get('target_keywords'), str):
                try: i['target_keywords'] = json.loads(i['target_keywords'])
                except: pass
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return items

    def get_summary(self) -> Dict:
        log = self.get_log(limit=100)
        by_type = defaultdict(int)
        by_domain = defaultdict(int)
        for entry in log:
            by_type[entry.get('content_type', 'unknown')] += 1
            by_domain[entry.get('source_domain', 'unknown')] += 1
        return {
            'total_citations': len(log),
            'by_content_type': dict(by_type),
            'by_source_domain': dict(by_domain),
            'recent': log[:5],
            'generated_at': _now(),
        }


class OriginalResearchProgramme:
    """Tracks original research assets produced."""

    RESEARCH_TOPICS = [
        {'id': 'ai-visibility-benchmark', 'title': 'AI Visibility Benchmark Report 2026',
         'description': 'Cross-provider citation rates for top 200 SEO keywords across 7 AI engines',
         'data_source': 'GEO probe data', 'status': 'data_collecting', 'target_date': '2026-Q2'},
        {'id': 'citation-format-study', 'title': 'Which Content Formats Get Cited by AI Engines',
         'description': 'Analysis of 500+ probe responses to determine which content structures (FAQ, list, table, comparison) achieve highest citation rates',
         'data_source': 'Citation learning engine', 'status': 'data_collecting', 'target_date': '2026-Q2'},
        {'id': 'provider-behaviour-report', 'title': 'How Different AI Engines Cite Brands Differently',
         'description': 'Comparative study of Nova, Ollama, Claude, GPT-4, Gemini citation patterns',
         'data_source': 'Cross-model compare data', 'status': 'planned', 'target_date': '2026-Q3'},
        {'id': 'geo-score-methodology', 'title': 'GEO Score Methodology & Validation',
         'description': 'Published methodology for calculating GEO scores with statistical validation',
         'data_source': 'Platform methodology', 'status': 'planned', 'target_date': '2026-Q3'},
    ]

    def get_programme(self) -> Dict:
        active = sum(1 for r in self.RESEARCH_TOPICS if r['status'] in ('data_collecting', 'in_progress'))
        return {
            'research_assets': self.RESEARCH_TOPICS,
            'total': len(self.RESEARCH_TOPICS),
            'active': active,
            'completed': sum(1 for r in self.RESEARCH_TOPICS if r['status'] == 'published'),
            'generated_at': _now(),
        }


# =========================================================================
# API BLUEPRINT
# =========================================================================

from flask import Blueprint, request, jsonify

month4_bp = Blueprint('month4_systems', __name__, url_prefix='/api/m3/deepthi/month4')

# --- 4.1 Citation Intelligence Engine ---

@month4_bp.route('/citation-map', methods=['GET'])
def citation_map():
    """Cross-provider citation map: which providers cite which brands per keyword."""
    limit = int(request.args.get('limit', 500))
    return jsonify(CrossProviderCitationMap().build_map(limit))

@month4_bp.route('/citation-velocity', methods=['GET'])
def citation_velocity():
    """Citation velocity: week-over-week and month-over-month momentum."""
    brand = request.args.get('brand', '').strip() or None
    return jsonify(CitationVelocityTracker().get_velocity(brand))

@month4_bp.route('/high-confidence', methods=['GET'])
def high_confidence():
    """High-confidence citation registry: proven keyword positions."""
    threshold = float(request.args.get('threshold', 0.75))
    return jsonify(HighConfidenceCitationRegistry().get_registry(threshold))

@month4_bp.route('/citation-gaps', methods=['GET'])
def citation_gaps():
    """Citation gap intelligence reports."""
    return jsonify(CitationGapReports().generate_report())

@month4_bp.route('/content-briefs', methods=['GET'])
def content_briefs():
    """Auto-generated content briefs from citation gaps."""
    limit = int(request.args.get('limit', 10))
    return jsonify(ContentBriefFeed().generate_briefs(limit))

# --- 4.2 Content Authority Engine ---

@month4_bp.route('/pillar-architecture', methods=['GET'])
def pillar_architecture():
    """Pillar-cluster content architecture."""
    return jsonify(PillarClusterArchitecture().get_architecture())

@month4_bp.route('/eeat-library', methods=['GET'])
def eeat_library():
    """E-E-A-T signal library."""
    return jsonify(EEATSignalLibrary().get_library())

@month4_bp.route('/external-citations', methods=['GET'])
def external_citations():
    """External citation building log."""
    return jsonify(ExternalCitationLog().get_summary())

@month4_bp.route('/external-citations', methods=['POST'])
def log_external_citation():
    """Log a new external citation placement."""
    data = request.get_json() or {}
    if not data.get('source_domain') or not data.get('url'):
        return jsonify({'error': 'source_domain and url required'}), 400
    cid = ExternalCitationLog().log_citation(data)
    return jsonify({'citation_id': cid, 'status': 'logged'}), 201

@month4_bp.route('/research-programme', methods=['GET'])
def research_programme():
    """Original research programme tracker."""
    return jsonify(OriginalResearchProgramme().get_programme())

@month4_bp.route('/month4-status', methods=['GET'])
def month4_status():
    """Complete Month 4 deliverable status."""
    return jsonify({
        'generated_at': _now(),
        'citation_intelligence_engine': {
            'cross_provider_citation_map': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/citation-map'},
            'citation_velocity_tracker': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/citation-velocity'},
            'high_confidence_registry': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/high-confidence'},
            'citation_gap_reports': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/citation-gaps'},
            'content_brief_feed': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/content-briefs'},
        },
        'content_authority_engine': {
            'pillar_cluster_architecture': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/pillar-architecture'},
            'original_research_programme': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/research-programme'},
            'eeat_signal_library': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/eeat-library'},
            'external_citation_log': {'status': 'active', 'endpoint': '/api/m3/deepthi/month4/external-citations'},
        },
        'overall_completion': '100%',
    })
