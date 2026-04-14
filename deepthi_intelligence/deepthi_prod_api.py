#!/usr/bin/env python3
"""
deepthi_prod_api.py
Production API endpoints under /api/m3/deepthi/ namespace.

Consolidates all Deepthi production-ready features:
  - EventBridge scheduler triggers
  - Multi-tenant management
  - Parallel probe execution
  - Global benchmark intelligence
  - Citation learning engine
  - Action register automation

Does NOT modify any existing API files.
"""

from flask import Blueprint, request, jsonify

deepthi_prod_bp = Blueprint('deepthi_prod', __name__, url_prefix='/api/m3/deepthi')


# =========================================================================
# 1. EVENTBRIDGE SCHEDULER
# =========================================================================

@deepthi_prod_bp.route('/scheduler/run/<task_type>', methods=['POST'])
def scheduler_run_task(task_type):
    """
    Trigger a scheduled task manually or via EventBridge.
    Valid task_types: directory_freshness, aeo_learning_update,
                     full_geo_scoring, competitor_matrix_update
    """
    from deepthi_intelligence.eventbridge_scheduler import (
        run_directory_freshness, run_aeo_learning_update,
        run_full_geo_scoring, run_competitor_matrix_update,
    )
    data = request.get_json() or {}
    project_id = data.get('project_id')

    task_map = {
        'directory_freshness': run_directory_freshness,
        'aeo_learning_update': run_aeo_learning_update,
        'full_geo_scoring': run_full_geo_scoring,
        'competitor_matrix_update': run_competitor_matrix_update,
    }
    handler = task_map.get(task_type)
    if not handler:
        return jsonify({'error': f'Unknown task: {task_type}',
                        'valid_tasks': list(task_map.keys())}), 400
    result = handler(project_id=project_id)
    return jsonify(result), 201


@deepthi_prod_bp.route('/scheduler/history', methods=['GET'])
def scheduler_history():
    """Get schedule execution history."""
    from deepthi_intelligence.eventbridge_scheduler import ScheduleLog
    task_type = request.args.get('task_type', '').strip() or None
    limit = int(request.args.get('limit', 50))
    return jsonify({'history': ScheduleLog().get_history(task_type, limit)})


@deepthi_prod_bp.route('/scheduler/eventbridge-config', methods=['GET'])
def scheduler_eventbridge_config():
    """Get EventBridge rule definitions for deployment."""
    from deepthi_intelligence.eventbridge_scheduler import generate_eventbridge_rules
    return jsonify(generate_eventbridge_rules())


# =========================================================================
# 2. MULTI-TENANT MANAGEMENT
# =========================================================================

@deepthi_prod_bp.route('/tenants', methods=['GET'])
def list_tenants():
    """List all active tenants."""
    from deepthi_intelligence.tenant_manager import TenantManager
    limit = int(request.args.get('limit', 100))
    return jsonify({'tenants': TenantManager().list_tenants(limit)})


@deepthi_prod_bp.route('/tenants', methods=['POST'])
def create_tenant():
    """
    Create a new tenant.
    Body: {"name": "Client Name", "owner_email": "[email]", "plan": "pro"}
    """
    from deepthi_intelligence.tenant_manager import TenantManager
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('owner_email', '').strip()
    if not name or not email:
        return jsonify({'error': 'name and owner_email required'}), 400
    plan = data.get('plan', 'free')
    tenant = TenantManager().create_tenant(name, email, plan)
    return jsonify(tenant), 201


@deepthi_prod_bp.route('/tenants/<project_id>', methods=['GET'])
def get_tenant(project_id):
    """Get tenant details."""
    from deepthi_intelligence.tenant_manager import TenantManager
    tenant = TenantManager().get_tenant(project_id)
    if not tenant:
        return jsonify({'error': 'tenant not found'}), 404
    return jsonify(tenant)


@deepthi_prod_bp.route('/tenants/<project_id>/brands', methods=['POST'])
def add_tenant_brand(project_id):
    """
    Add a brand to a tenant.
    Body: {"brand": "BrandName"}
    """
    from deepthi_intelligence.tenant_manager import TenantManager
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    if not brand:
        return jsonify({'error': 'brand required'}), 400
    result = TenantManager().add_brand_to_tenant(project_id, brand)
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result), 201


@deepthi_prod_bp.route('/tenants/<project_id>/brands/<brand>', methods=['DELETE'])
def remove_tenant_brand(project_id, brand):
    """Remove a brand from a tenant."""
    from deepthi_intelligence.tenant_manager import TenantManager
    result = TenantManager().remove_brand_from_tenant(project_id, brand)
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)


@deepthi_prod_bp.route('/tenants/<project_id>/geo-scores', methods=['GET'])
def tenant_geo_scores(project_id):
    """Get GEO scores filtered to tenant's brands."""
    from deepthi_intelligence.tenant_manager import TenantIsolatedQuery
    limit = int(request.args.get('limit', 12))
    query = TenantIsolatedQuery(project_id)
    return jsonify({'scores': query.get_geo_scores(limit_per_brand=limit)})


@deepthi_prod_bp.route('/tenants/<project_id>/keywords', methods=['GET'])
def tenant_keywords(project_id):
    """Get keyword performance filtered to tenant's brands."""
    from deepthi_intelligence.tenant_manager import TenantIsolatedQuery
    keyword = request.args.get('keyword', '').strip() or None
    query = TenantIsolatedQuery(project_id)
    return jsonify(query.get_keyword_performance(keyword))


# =========================================================================
# 3. PARALLEL PROBE EXECUTION
# =========================================================================

@deepthi_prod_bp.route('/probes/parallel', methods=['POST'])
def parallel_probe():
    """
    Dispatch a parallel probe job.
    Body: {
      "brand": "AI1stSEO",
      "keywords": ["best seo tool", ...],
      "provider": "nova",
      "project_id": "optional"
    }
    """
    from deepthi_intelligence.parallel_probe_executor import dispatch_parallel_probe
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    keywords = [k.strip() for k in data.get('keywords', []) if k.strip()]
    if not brand or not keywords:
        return jsonify({'error': 'brand and keywords required'}), 400
    provider = data.get('provider', 'nova')
    project_id = data.get('project_id')
    result = dispatch_parallel_probe(brand, keywords, provider, project_id)
    return jsonify(result), 201


@deepthi_prod_bp.route('/probes/jobs', methods=['GET'])
def list_probe_jobs():
    """List all probe jobs."""
    from deepthi_intelligence.parallel_probe_executor import ProbeJobManager
    limit = int(request.args.get('limit', 50))
    return jsonify({'jobs': ProbeJobManager().list_jobs(limit)})


@deepthi_prod_bp.route('/probes/jobs/<job_id>', methods=['GET'])
def get_probe_job(job_id):
    """Get probe job status and results."""
    from deepthi_intelligence.parallel_probe_executor import ProbeJobManager
    job = ProbeJobManager().get_job(job_id)
    if not job:
        return jsonify({'error': 'job not found'}), 404
    return jsonify(job)


# =========================================================================
# 4. GLOBAL BENCHMARK INTELLIGENCE
# =========================================================================

@deepthi_prod_bp.route('/global/industries', methods=['GET'])
def list_industries():
    """List available industry categories."""
    from deepthi_intelligence.global_benchmark_engine import IndustryBenchmarkTracker
    return jsonify({'categories': IndustryBenchmarkTracker().list_categories()})


@deepthi_prod_bp.route('/global/industry/<category_id>', methods=['GET'])
def industry_trend(category_id):
    """Get industry benchmark trend."""
    from deepthi_intelligence.global_benchmark_engine import IndustryBenchmarkTracker
    limit = int(request.args.get('limit', 12))
    trend = IndustryBenchmarkTracker().get_industry_trend(category_id, limit)
    return jsonify({'category': category_id, 'trend': trend})


@deepthi_prod_bp.route('/global/detect-competitors', methods=['GET'])
def detect_competitors():
    """Auto-detect new competitors from probe data."""
    from deepthi_intelligence.global_benchmark_engine import CompetitorDetector
    limit = int(request.args.get('limit', 200))
    return jsonify(CompetitorDetector().detect_new_competitors(limit=limit))


@deepthi_prod_bp.route('/global/weekly-report', methods=['POST'])
def generate_weekly_report():
    """Generate a weekly benchmark report."""
    from deepthi_intelligence.global_benchmark_engine import WeeklyReportGenerator
    data = request.get_json() or {}
    project_id = data.get('project_id')
    report = WeeklyReportGenerator().generate_report(project_id)
    return jsonify(report), 201


@deepthi_prod_bp.route('/global/weekly-report/<report_id>', methods=['GET'])
def get_weekly_report(report_id):
    """Get a specific weekly report."""
    from deepthi_intelligence.global_benchmark_engine import WeeklyReportGenerator
    report = WeeklyReportGenerator().get_report(report_id)
    if not report:
        return jsonify({'error': 'report not found'}), 404
    return jsonify(report)


@deepthi_prod_bp.route('/global/weekly-reports', methods=['GET'])
def list_weekly_reports():
    """List all weekly reports."""
    from deepthi_intelligence.global_benchmark_engine import WeeklyReportGenerator
    limit = int(request.args.get('limit', 20))
    return jsonify({'reports': WeeklyReportGenerator().list_reports(limit)})


# =========================================================================
# 5. CITATION LEARNING ENGINE
# =========================================================================

@deepthi_prod_bp.route('/citation-learning/learn', methods=['POST'])
def citation_learn():
    """Trigger learning from recent probes."""
    from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
    data = request.get_json() or {}
    limit = int(data.get('limit', 200))
    result = CitationLearningEngine().learn_from_recent_probes(limit)
    return jsonify(result), 201


@deepthi_prod_bp.route('/citation-learning/patterns', methods=['GET'])
def citation_patterns():
    """Get learned citation patterns."""
    from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
    limit = int(request.args.get('limit', 50))
    return jsonify({'patterns': CitationLearningEngine().get_learned_patterns(limit)})


@deepthi_prod_bp.route('/citation-learning/recommendations', methods=['GET'])
def citation_recommendations():
    """Get AEO template recommendations based on learned patterns."""
    from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
    limit = int(request.args.get('limit', 20))
    return jsonify({'recommendations': CitationLearningEngine().get_recommendations(limit)})


@deepthi_prod_bp.route('/citation-learning/keyword/<keyword>', methods=['GET'])
def citation_keyword_insights(keyword):
    """Get format insights for a specific keyword."""
    from deepthi_intelligence.citation_learning_engine import CitationLearningEngine
    return jsonify(CitationLearningEngine().get_keyword_insights(keyword))


# =========================================================================
# 6. ACTION REGISTER AUTOMATION
# =========================================================================

@deepthi_prod_bp.route('/actions/history', methods=['GET'])
def action_history():
    """Get automated action history."""
    from deepthi_intelligence.action_register_automation import AutoActionRegister
    brand = request.args.get('brand', '').strip() or None
    action_type = request.args.get('type', '').strip() or None
    limit = int(request.args.get('limit', 50))
    return jsonify({'actions': AutoActionRegister().get_action_history(brand, action_type, limit)})


@deepthi_prod_bp.route('/actions/impact/<brand>', methods=['GET'])
def action_impact_summary(brand):
    """Get impact summary for a brand."""
    from deepthi_intelligence.action_register_automation import AutoActionRegister
    return jsonify(AutoActionRegister().get_impact_summary(brand))


@deepthi_prod_bp.route('/actions/measure/<brand>', methods=['POST'])
def measure_pending_impacts(brand):
    """Measure pending content change impacts for a brand."""
    from deepthi_intelligence.action_register_automation import AutoActionRegister
    return jsonify(AutoActionRegister().measure_pending_impacts(brand))


@deepthi_prod_bp.route('/actions/log-change', methods=['POST'])
def log_content_change():
    """
    Log a content change for impact tracking.
    Body: {"brand": "...", "url": "...", "change_type": "faq_added|schema_updated|..."}
    """
    from deepthi_intelligence.action_register_automation import AutoActionRegister
    data = request.get_json() or {}
    brand = data.get('brand', '').strip()
    url = data.get('url', '').strip()
    change_type = data.get('change_type', 'content_update')
    if not brand or not url:
        return jsonify({'error': 'brand and url required'}), 400

    # Get current GEO score as before_score
    before_score = 0
    try:
        from deepthi_intelligence.data_hooks import get_m3_geo_score
        m3 = get_m3_geo_score(brand)
        if m3:
            before_score = float(m3.get('geo_score', 0))
    except Exception:
        pass

    action_id = AutoActionRegister().log_content_change(brand, url, change_type, before_score)
    return jsonify({'action_id': action_id, 'before_score': before_score}), 201
