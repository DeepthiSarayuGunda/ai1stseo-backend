#!/usr/bin/env python3
"""Month 3 API Blueprint — all system endpoints under /api/m3/*"""

import json
from flask import Blueprint, request, jsonify

m3_bp = Blueprint('month3', __name__, url_prefix='/api/m3')


# ═══════════════════════════════════════════════════════════════════════════════
# 3.1 AEO ANSWER INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

@m3_bp.route('/aeo/questions', methods=['GET'])
def aeo_questions():
    from month3_systems.aeo_answer_intelligence import QuestionIntelligenceDB
    db = QuestionIntelligenceDB()
    limit = int(request.args.get('limit', 50))
    return jsonify({'questions': db.get_all(limit=limit)})

@m3_bp.route('/aeo/questions', methods=['POST'])
def aeo_question_upsert():
    from month3_systems.aeo_answer_intelligence import QuestionIntelligenceDB
    db = QuestionIntelligenceDB()
    data = request.get_json() or {}
    kw = data.get('keyword', '').strip()
    if not kw: return jsonify({'error': 'keyword required'}), 400
    db.upsert_query(kw, data)
    return jsonify({'status': 'saved', 'keyword': kw})

@m3_bp.route('/aeo/questions/bulk', methods=['POST'])
def aeo_questions_bulk():
    from month3_systems.aeo_answer_intelligence import QuestionIntelligenceDB
    db = QuestionIntelligenceDB()
    data = request.get_json() or {}
    items = data.get('queries', [])
    count = db.bulk_enrich(items)
    return jsonify({'enriched': count})

@m3_bp.route('/aeo/questions/gaps', methods=['GET'])
def aeo_priority_gaps():
    from month3_systems.aeo_answer_intelligence import QuestionIntelligenceDB
    db = QuestionIntelligenceDB()
    limit = int(request.args.get('limit', 10))
    return jsonify({'gaps': db.get_priority_gaps(limit=limit)})

@m3_bp.route('/aeo/templates', methods=['GET'])
def aeo_templates():
    from month3_systems.aeo_answer_intelligence import AnswerTemplateLibrary
    lib = AnswerTemplateLibrary()
    return jsonify({'templates': lib.get_all()})

@m3_bp.route('/aeo/templates/seed', methods=['POST'])
def aeo_templates_seed():
    from month3_systems.aeo_answer_intelligence import AnswerTemplateLibrary
    lib = AnswerTemplateLibrary()
    count = lib.seed_defaults()
    return jsonify({'seeded': count})

@m3_bp.route('/aeo/calendar', methods=['GET'])
def aeo_calendar():
    from month3_systems.aeo_answer_intelligence import AEOContentCalendar
    cal = AEOContentCalendar()
    status = request.args.get('status')
    return jsonify({'entries': cal.get_calendar(status=status)})

@m3_bp.route('/aeo/calendar', methods=['POST'])
def aeo_calendar_add():
    from month3_systems.aeo_answer_intelligence import AEOContentCalendar
    cal = AEOContentCalendar()
    data = request.get_json() or {}
    kw = data.get('keyword', '').strip()
    if not kw: return jsonify({'error': 'keyword required'}), 400
    eid = cal.add_entry(kw, data)
    return jsonify({'entry_id': eid}), 201

@m3_bp.route('/aeo/calendar/<entry_id>/status', methods=['PUT'])
def aeo_calendar_status(entry_id):
    from month3_systems.aeo_answer_intelligence import AEOContentCalendar
    cal = AEOContentCalendar()
    data = request.get_json() or {}
    cal.update_status(entry_id, data.get('status', 'brief'), **data)
    return jsonify({'status': 'updated'})

@m3_bp.route('/aeo/citations', methods=['GET'])
def aeo_citations():
    from month3_systems.aeo_answer_intelligence import CitationMonitoringRegister
    reg = CitationMonitoringRegister()
    return jsonify({'pages': reg.get_all()})

@m3_bp.route('/aeo/citations', methods=['POST'])
def aeo_citation_register():
    from month3_systems.aeo_answer_intelligence import CitationMonitoringRegister
    reg = CitationMonitoringRegister()
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url: return jsonify({'error': 'url required'}), 400
    pid = reg.register_page(url, data)
    return jsonify({'page_id': pid}), 201

@m3_bp.route('/aeo/citations/<page_id>/check', methods=['POST'])
def aeo_citation_check(page_id):
    from month3_systems.aeo_answer_intelligence import CitationMonitoringRegister
    reg = CitationMonitoringRegister()
    data = request.get_json() or {}
    reg.record_weekly_check(page_id, data)
    return jsonify({'status': 'recorded'})

@m3_bp.route('/aeo/learning-log', methods=['GET'])
def aeo_learning_log():
    from month3_systems.aeo_answer_intelligence import AEOLearningLog
    log = AEOLearningLog()
    return jsonify({'entries': log.get_log()})

@m3_bp.route('/aeo/learning-log', methods=['POST'])
def aeo_learning_log_add():
    from month3_systems.aeo_answer_intelligence import AEOLearningLog
    log = AEOLearningLog()
    data = request.get_json() or {}
    eid = log.add_entry(data)
    return jsonify({'entry_id': eid}), 201

@m3_bp.route('/aeo/weekly-cadence', methods=['POST'])
def aeo_weekly():
    from month3_systems.aeo_answer_intelligence import run_aeo_weekly_cadence
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    if not brand: return jsonify({'error': 'brand required'}), 400
    result = run_aeo_weekly_cadence(brand)
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════════
# 3.2 GEO BRAND INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

@m3_bp.route('/geo/score-tracker', methods=['GET'])
def geo_tracker():
    from month3_systems.geo_brand_intelligence import GEOScoreTracker
    t = GEOScoreTracker()
    brand = request.args.get('brand', '')
    if not brand: return jsonify({'error': 'brand required'}), 400
    return jsonify({'trend': t.get_trend(brand)})

@m3_bp.route('/geo/score-tracker', methods=['POST'])
def geo_tracker_record():
    from month3_systems.geo_brand_intelligence import GEOScoreTracker
    t = GEOScoreTracker()
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    if not brand: return jsonify({'error': 'brand required'}), 400
    week = t.record_week(brand, data)
    return jsonify({'week': week}), 201

@m3_bp.route('/geo/keywords', methods=['GET'])
def geo_keywords():
    from month3_systems.geo_brand_intelligence import KeywordPerformanceRegister
    r = KeywordPerformanceRegister()
    week = request.args.get('week')
    return jsonify({'keywords': r.get_all_latest(week)})

@m3_bp.route('/geo/keywords', methods=['POST'])
def geo_keywords_record():
    from month3_systems.geo_brand_intelligence import KeywordPerformanceRegister
    r = KeywordPerformanceRegister()
    data = request.get_json() or {}
    week = data.get('week', '')
    records = data.get('records', [])
    count = r.bulk_record(week, records)
    return jsonify({'recorded': count})

@m3_bp.route('/geo/keywords/<keyword>/history', methods=['GET'])
def geo_keyword_history(keyword):
    from month3_systems.geo_brand_intelligence import KeywordPerformanceRegister
    r = KeywordPerformanceRegister()
    return jsonify({'history': r.get_keyword_history(keyword)})

@m3_bp.route('/geo/competitors', methods=['GET'])
def geo_competitors():
    from month3_systems.geo_brand_intelligence import CompetitorVisibilityMatrix
    m = CompetitorVisibilityMatrix()
    week = request.args.get('week')
    return jsonify({'matrix': m.get_matrix(week)})

@m3_bp.route('/geo/competitors', methods=['POST'])
def geo_competitor_record():
    from month3_systems.geo_brand_intelligence import CompetitorVisibilityMatrix
    m = CompetitorVisibilityMatrix()
    data = request.get_json() or {}
    comp = data.get('competitor', '').strip()
    week = data.get('week', '')
    if not comp: return jsonify({'error': 'competitor required'}), 400
    m.record(comp, week, data)
    return jsonify({'status': 'recorded'})

@m3_bp.route('/geo/competitors/<competitor>/trend', methods=['GET'])
def geo_competitor_trend(competitor):
    from month3_systems.geo_brand_intelligence import CompetitorVisibilityMatrix
    m = CompetitorVisibilityMatrix()
    return jsonify({'trend': m.get_competitor_trend(competitor)})

@m3_bp.route('/geo/actions', methods=['GET'])
def geo_actions():
    from month3_systems.geo_brand_intelligence import GEOActionRegister
    r = GEOActionRegister()
    brand = request.args.get('brand')
    return jsonify({'actions': r.get_all(brand=brand)})

@m3_bp.route('/geo/actions', methods=['POST'])
def geo_action_log():
    from month3_systems.geo_brand_intelligence import GEOActionRegister
    r = GEOActionRegister()
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    if not brand: return jsonify({'error': 'brand required'}), 400
    aid = r.log_action(brand, data)
    return jsonify({'action_id': aid}), 201

@m3_bp.route('/geo/actions/<action_id>/impact', methods=['PUT'])
def geo_action_impact(action_id):
    from month3_systems.geo_brand_intelligence import GEOActionRegister
    r = GEOActionRegister()
    data = request.get_json() or {}
    r.update_impact(action_id, data.get('geo_score_after', 0))
    return jsonify({'status': 'updated'})

@m3_bp.route('/geo/providers', methods=['GET'])
def geo_providers():
    from month3_systems.geo_brand_intelligence import ProviderSensitivityMap
    m = ProviderSensitivityMap()
    return jsonify({'providers': m.get_map()})

@m3_bp.route('/geo/providers/seed', methods=['POST'])
def geo_providers_seed():
    from month3_systems.geo_brand_intelligence import ProviderSensitivityMap
    m = ProviderSensitivityMap()
    count = m.seed_defaults()
    return jsonify({'seeded': count})

@m3_bp.route('/geo/weekly-cadence', methods=['POST'])
def geo_weekly():
    from month3_systems.geo_brand_intelligence import run_geo_weekly_cadence
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    if not brand: return jsonify({'error': 'brand required'}), 400
    comps = data.get('competitors', [])
    result = run_geo_weekly_cadence(brand, comps)
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════════
# 3.3 SEO FOUNDATION
# ═══════════════════════════════════════════════════════════════════════════════

@m3_bp.route('/seo/tech-debt', methods=['GET'])
def seo_tech_debt():
    from month3_systems.seo_foundation import TechnicalDebtRegister
    r = TechnicalDebtRegister()
    status = request.args.get('status')
    return jsonify({'issues': r.get_all(status=status), 'stats': r.get_stats()})

@m3_bp.route('/seo/tech-debt', methods=['POST'])
def seo_tech_debt_add():
    from month3_systems.seo_foundation import TechnicalDebtRegister
    r = TechnicalDebtRegister()
    data = request.get_json() or {}
    iid = r.add_issue(data)
    return jsonify({'issue_id': iid}), 201

@m3_bp.route('/seo/tech-debt/<issue_id>/resolve', methods=['PUT'])
def seo_tech_debt_resolve(issue_id):
    from month3_systems.seo_foundation import TechnicalDebtRegister
    r = TechnicalDebtRegister()
    r.resolve_issue(issue_id)
    return jsonify({'status': 'resolved'})

@m3_bp.route('/seo/tech-debt/seed', methods=['POST'])
def seo_tech_debt_seed():
    from month3_systems.seo_foundation import TechnicalDebtRegister
    r = TechnicalDebtRegister()
    data = request.get_json() or {}
    count = r.seed_from_audit(data.get('audit_results', []))
    return jsonify({'seeded': count})

@m3_bp.route('/seo/eeat', methods=['GET'])
def seo_eeat():
    from month3_systems.seo_foundation import EEATPipeline
    p = EEATPipeline()
    status = request.args.get('status')
    return jsonify({'gaps': p.get_all(status=status)})

@m3_bp.route('/seo/eeat', methods=['POST'])
def seo_eeat_add():
    from month3_systems.seo_foundation import EEATPipeline
    p = EEATPipeline()
    data = request.get_json() or {}
    gid = p.add_gap(data)
    return jsonify({'gap_id': gid}), 201

@m3_bp.route('/seo/eeat/<gap_id>/status', methods=['PUT'])
def seo_eeat_status(gap_id):
    from month3_systems.seo_foundation import EEATPipeline
    p = EEATPipeline()
    data = request.get_json() or {}
    p.update_status(gap_id, data.get('status', 'identified'), data.get('verification', ''))
    return jsonify({'status': 'updated'})

@m3_bp.route('/seo/content-queue', methods=['GET'])
def seo_content_queue():
    from month3_systems.seo_foundation import ContentOptimisationQueue
    q = ContentOptimisationQueue()
    status = request.args.get('status')
    return jsonify({'queue': q.get_queue(status=status)})

@m3_bp.route('/seo/content-queue', methods=['POST'])
def seo_content_queue_add():
    from month3_systems.seo_foundation import ContentOptimisationQueue
    q = ContentOptimisationQueue()
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url: return jsonify({'error': 'url required'}), 400
    pid = q.add_page(url, data)
    return jsonify({'page_id': pid}), 201

@m3_bp.route('/seo/authority-map', methods=['GET'])
def seo_authority_map():
    from month3_systems.seo_foundation import TopicalAuthorityMap
    m = TopicalAuthorityMap()
    pillar = request.args.get('pillar')
    return jsonify({'topics': m.get_map(pillar=pillar)})

@m3_bp.route('/seo/authority-map', methods=['POST'])
def seo_authority_map_add():
    from month3_systems.seo_foundation import TopicalAuthorityMap
    m = TopicalAuthorityMap()
    data = request.get_json() or {}
    pillar = data.get('pillar', '').strip()
    if not pillar: return jsonify({'error': 'pillar required'}), 400
    tid = m.add_topic(pillar, data)
    return jsonify({'topic_id': tid}), 201

@m3_bp.route('/seo/authority-map/gaps', methods=['GET'])
def seo_authority_gaps():
    from month3_systems.seo_foundation import TopicalAuthorityMap
    m = TopicalAuthorityMap()
    return jsonify({'gaps': m.get_gaps()})

@m3_bp.route('/seo/weekly-cadence', methods=['POST'])
def seo_weekly():
    from month3_systems.seo_foundation import run_seo_weekly_cadence
    result = run_seo_weekly_cadence()
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════════
# KPI BASELINE
# ═══════════════════════════════════════════════════════════════════════════════

@m3_bp.route('/kpi-baseline', methods=['POST'])
def kpi_baseline():
    """Generate Month 3 KPI baseline across all 3 systems."""
    from month3_systems.aeo_answer_intelligence import (
        QuestionIntelligenceDB, AnswerTemplateLibrary, AEOContentCalendar,
        CitationMonitoringRegister, AEOLearningLog)
    from month3_systems.geo_brand_intelligence import (
        GEOScoreTracker, KeywordPerformanceRegister, CompetitorVisibilityMatrix,
        GEOActionRegister, ProviderSensitivityMap)
    from month3_systems.seo_foundation import (
        TechnicalDebtRegister, EEATPipeline, ContentOptimisationQueue, TopicalAuthorityMap)
    from datetime import datetime, timezone

    data = request.get_json() or {}
    brand = data.get('brand', '')

    baseline = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'brand': brand,
        'aeo_system': {
            'questions_in_db': len(QuestionIntelligenceDB().get_all()),
            'templates_available': len(AnswerTemplateLibrary().get_all()),
            'calendar_entries': len(AEOContentCalendar().get_calendar()),
            'pages_monitored': len(CitationMonitoringRegister().get_all()),
            'learning_log_entries': len(AEOLearningLog().get_log()),
        },
        'geo_system': {
            'latest_geo_score': (GEOScoreTracker().get_latest(brand) or {}).get('geo_score', 0) if brand else 0,
            'keywords_tracked': len(KeywordPerformanceRegister().get_all_latest()),
            'competitors_tracked': len(CompetitorVisibilityMatrix().get_matrix()),
            'actions_logged': len(GEOActionRegister().get_all(brand=brand)),
            'providers_mapped': len(ProviderSensitivityMap().get_map()),
        },
        'seo_system': {
            'tech_debt': TechnicalDebtRegister().get_stats(),
            'eeat_gaps_open': len(EEATPipeline().get_all(status='identified')),
            'content_queue_size': len(ContentOptimisationQueue().get_queue()),
            'authority_map_topics': len(TopicalAuthorityMap().get_map()),
            'authority_gaps': len(TopicalAuthorityMap().get_gaps()),
        },
    }
    return jsonify(baseline)
