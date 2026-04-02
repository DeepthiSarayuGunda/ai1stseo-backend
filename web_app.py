#!/usr/bin/env python3
"""AEO-First AI SEO Platform v6.0 — Lambda-Ready + OpenClaw Connected"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env for local dev
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from database import SEODatabase
from src.aeo_engine import run_full_platform_analysis
from src.ai_visibility_tool import run_ai_visibility
from scheduler import SEOScheduler
from src.content_scorer import score_content
from bedrock_helper import bedrock
from src.geo_engine import run_geo_analysis

# --- Environment-driven config ---
IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
DB_DIR = '/tmp' if IS_LAMBDA else os.path.dirname(os.path.abspath(__file__))

# --- DynamoDB feature flags (GEO Scanner + AEO Month 1 only) ---
USE_DYNAMO_AEO = os.environ.get('USE_DYNAMO_AEO', 'false').lower() == 'true'
USE_DYNAMO_GEO = os.environ.get('USE_DYNAMO_GEO', 'false').lower() == 'true'

aeo_repo = None
geo_repo = None
if USE_DYNAMO_AEO:
    from dynamo.aeo_repository import AEORepository
    aeo_repo = AEORepository()
if USE_DYNAMO_GEO:
    from dynamo.geo_repository import GEORepository
    geo_repo = GEORepository()

app = Flask(__name__)
CORS(app)
db = SEODatabase(db_path=os.path.join(DB_DIR, 'seo_reports.db'))
scheduler = SEOScheduler(db_path=os.path.join(DB_DIR, 'seo_schedules.db'))

try:
    import openclaw_real_routes
    openclaw_real_routes.register_routes(app)
except Exception:
    pass

# --- AI Business Directory routes ---
try:
    from directory.routes import register_directory_routes
    register_directory_routes(app)
except Exception:
    pass


# ===================== PAGE ROUTES =====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ai-visibility')
def ai_visibility_page():
    return render_template('ai_visibility.html')


@app.route('/history')
def history():
    keyword = request.args.get('keyword', '')
    reports = db.get_reports(limit=100, keyword=keyword if keyword else None)
    return render_template('history.html', reports=reports, search_keyword=keyword)


@app.route('/benchmarks')
def benchmarks():
    keyword = request.args.get('keyword', '')
    bm = db.get_benchmarks(keyword=keyword if keyword else None)
    return render_template('benchmarks.html', benchmarks=bm, search_keyword=keyword)


@app.route('/openclaw')
def openclaw_integration():
    return render_template('openclaw.html')


@app.route('/automation-hub')
def automation_hub_page():
    return render_template('automation_hub.html')


@app.route('/scheduler')
def scheduler_page():
    return render_template('scheduler.html')


@app.route('/compare')
def compare_page():
    return render_template('compare.html')


@app.route('/trends')
def trends_page():
    return render_template('trends.html')


@app.route('/geo')
def geo_page():
    return render_template('geo.html')


@app.route('/editor')
def editor_page():
    return render_template('editor.html')


# ===================== ANALYSIS ROUTES =====================

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    topic = data.get('topic', '')
    source = request.headers.get('X-Source', 'web')
    if not topic:
        return jsonify({'error': 'Topic required'}), 400
    try:
        result = run_full_platform_analysis(topic)
        analysis_result = {'success': True, 'query': topic, 'aeo': result}
        if source != 'openclaw':
            try:
                if USE_DYNAMO_AEO and aeo_repo:
                    report_id = aeo_repo.save_report(topic, analysis_result)
                else:
                    report_id = db.save_report(topic, analysis_result)
                analysis_result['report_id'] = report_id
            except Exception:
                analysis_result['report_id'] = None
        db.log_api_access('/analyze', 'POST', source, topic, 200)
        return jsonify(analysis_result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai-visibility', methods=['POST'])
def api_ai_visibility():
    data = request.get_json()
    topic = data.get('topic', '')
    if not topic:
        return jsonify({'error': 'Topic required'}), 400
    try:
        result = run_ai_visibility(topic)
        return jsonify({'success': True, 'query': topic, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '').lower().strip()
    # Greetings
    if message in ('hi', 'hello', 'hey', 'yo', 'sup', 'hola', 'greetings'):
        r = "Hey! \U0001f44b I'm your AEO assistant. Try asking me things like:\n\n\u2022 How do I improve my AEO score?\n\u2022 What is a citation gap?\n\u2022 How does AI visibility work?\n\u2022 What's the difference between SEO and AEO?"
    elif 'help' in message or 'what can you' in message or 'what do you' in message:
        r = "I can help with:\n\n\U0001f4ca SEO & AEO scores \u2014 how they work and how to improve\n\U0001f50d Citation gaps \u2014 why AI skips your content\n\U0001f916 AI visibility \u2014 getting cited by ChatGPT/Gemini\n\U0001f4dd Content tips \u2014 structure, FAQ, trust signals\n\U0001f30d GEO readiness \u2014 generative engine optimization\n\nJust ask a question!"
    elif 'seo' in message and 'aeo' in message:
        r = "SEO = ranking on Google. AEO = getting cited by AI engines (ChatGPT, Gemini, Perplexity). SEO focuses on keywords & backlinks. AEO focuses on answer readiness, structured content, and citation signals. Both matter \u2014 AEO is the future."
    elif 'aeo' in message or 'answer engine' in message:
        r = "AEO (Answer Engine Optimization) is about making your content citable by AI. Key factors:\n\n1\ufe0f\u20e3 Answer Readiness \u2014 direct, clear answers\n2\ufe0f\u20e3 Content Structure \u2014 headings, lists, FAQ\n3\ufe0f\u20e3 Trust Signals \u2014 stats, sources, expert quotes\n4\ufe0f\u20e3 AI Extractability \u2014 short paragraphs, schema markup"
    elif 'seo' in message or 'score' in message:
        r = "Your SEO/AEO score is based on multiple factors:\n\n\u2022 Content structure (headings, lists, FAQ)\n\u2022 Answer readiness (direct answers to questions)\n\u2022 Trust signals (stats, citations, expert language)\n\u2022 AI extractability (short chunks, clear format)\n\nRun an analysis on the main page to see your breakdown!"
    elif 'improve' in message or 'better' in message or 'boost' in message or 'increase' in message or 'fix' in message:
        r = "Top 5 quick wins to boost your score:\n\n1. Add a TL;DR summary at the top\n2. Use question-format headings (What is X? How does X work?)\n3. Add an FAQ section with 5+ questions\n4. Include 3+ statistics with sources\n5. Use short paragraphs (under 3 sentences each)\n\nTry the \u2018Boost to 90+\u2019 feature after running an analysis!"
    elif 'gap' in message or 'citation' in message:
        r = "Citation gap = the difference between your Google ranking and AI citation rate. You might rank #3 on Google but never get cited by ChatGPT.\n\nFix it by:\n\u2022 Adding FAQ schema markup\n\u2022 Writing direct, quotable answers\n\u2022 Including recent statistics (2024/2025)\n\u2022 Using structured data"
    elif 'visibility' in message or 'ai visibility' in message:
        r = "AI Visibility measures how likely AI engines are to cite your content. It checks:\n\n\u2022 Clarity \u2014 can AI extract a clean answer?\n\u2022 Authority \u2014 do you cite sources and data?\n\u2022 Structure \u2014 headings, lists, FAQ format?\n\u2022 Freshness \u2014 recent dates and updated info?\n\nCheck yours with the \U0001f52e AI Visibility Tool in the nav!"
    elif 'geo' in message or 'generative' in message:
        r = "GEO (Generative Engine Optimization) focuses on 4 pillars:\n\n1. Citation Support \u2014 stats, percentages, year references\n2. Entity Coverage \u2014 keyword presence and related terms\n3. Answer Chunking \u2014 short paragraphs, headings, questions\n4. Trust Signals \u2014 authority words, balanced language\n\nTry the \U0001f30d GEO Readiness tool in the nav!"
    elif 'faq' in message or 'question' in message:
        r = "FAQ sections are gold for AEO! Tips:\n\n\u2022 Include 5-10 real questions people ask\n\u2022 Keep answers 2-3 sentences (AI-extractable)\n\u2022 Use FAQ schema markup for rich results\n\u2022 Start with \u2018What\u2019, \u2018How\u2019, \u2018Why\u2019 questions\n\nRun an analysis \u2014 we generate FAQ suggestions automatically!"
    elif 'keyword' in message or 'compare' in message:
        r = "Use the \u2696\ufe0f Compare tool to analyze 2-3 keywords side by side. It shows AEO scores, AI visibility, and which keyword has the best chance of getting cited by AI engines. Great for content planning!"
    elif 'schedule' in message or 'monitor' in message:
        r = "The \u23f0 Scheduler lets you set up automated AEO monitoring. It tracks score changes over time and can alert you when scores drop. Set it up from the Scheduler page in the nav!"
    elif 'openclaw' in message or 'bedrock' in message or 'claude' in message:
        r = "OpenClaw is connected via AWS Bedrock using Nova Lite. It powers AI-enhanced summarization and insights. Check the green banner at the top of the page for live connection status!"
    elif 'thank' in message:
        r = "You're welcome! \U0001f60a Let me know if you need anything else. Happy optimizing!"
    elif 'bye' in message or 'goodbye' in message:
        r = "See you! \U0001f44b Keep optimizing that content. Come back anytime!"
    else:
        r = "I'm not sure about that one. Try asking about:\n\n\u2022 AEO scores and how to improve them\n\u2022 Citation gaps and AI visibility\n\u2022 GEO readiness\n\u2022 Content optimization tips\n\u2022 FAQ best practices\n\nOr just type a keyword and hit Analyze on the main page!"
    return jsonify({'response': r})


# ===================== API ROUTES =====================

@app.route('/api/analyze', methods=['POST'])
@app.route('/api/aeo/analyze', methods=['POST'])
def api_analyze():
    return analyze()


@app.route('/api/reports', methods=['GET'])
@app.route('/api/aeo/reports', methods=['GET'])
def api_reports():
    limit = request.args.get('limit', 50, type=int)
    keyword = request.args.get('keyword', None)
    if USE_DYNAMO_AEO and aeo_repo:
        reports = aeo_repo.get_reports(limit=limit, keyword=keyword)
    else:
        reports = db.get_reports(limit=limit, keyword=keyword)
    return jsonify({'success': True, 'count': len(reports), 'reports': reports})


@app.route('/api/report/<report_id>', methods=['GET'])
@app.route('/api/aeo/report/<report_id>', methods=['GET'])
def api_report(report_id):
    if USE_DYNAMO_AEO and aeo_repo:
        report = aeo_repo.get_report_by_id(str(report_id))
    else:
        report = db.get_report_by_id(int(report_id))
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    return jsonify({'success': True, 'report': report})


@app.route('/api/history/<keyword>', methods=['GET'])
@app.route('/api/aeo/history/<keyword>', methods=['GET'])
def api_history(keyword):
    if USE_DYNAMO_AEO and aeo_repo:
        history_data = aeo_repo.get_keyword_history(keyword)
    else:
        history_data = db.get_keyword_history(keyword)
    return jsonify({'success': True, 'keyword': keyword, 'history': history_data})


@app.route('/api/benchmarks', methods=['GET'])
def api_benchmarks():
    keyword = request.args.get('keyword', None)
    bm = db.get_benchmarks(keyword=keyword)
    return jsonify({'success': True, 'benchmarks': bm})


@app.route('/api/stats', methods=['GET'])
@app.route('/api/aeo/stats', methods=['GET'])
def api_stats():
    if USE_DYNAMO_AEO and aeo_repo:
        stats = aeo_repo.get_stats()
    else:
        stats = db.get_stats()
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/clear-history', methods=['POST'])
def api_clear_history():
    try:
        if USE_DYNAMO_AEO and aeo_repo:
            return jsonify({'success': aeo_repo.clear_all_reports()})
        return jsonify({'success': db.clear_all_reports()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/docs', methods=['GET'])
def api_docs():
    return jsonify({'name': 'AEO-First AI SEO Platform', 'version': '6.0'})


# === SCHEDULER ROUTES ===

@app.route('/api/schedule-audit', methods=['POST'])
@app.route('/api/schedule/create', methods=['POST'])
def api_schedule_audit():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON body'}), 400
        keyword = data.get('keyword', '').strip()
        freq = data.get('frequency_hours', 24)
        email = data.get('email', None)
        notify_on_drop = data.get('notify_on_drop', True)
        notify_on_improve = data.get('notify_on_improve', True)
        notify_on_issue = data.get('notify_on_issue', True)
        if not keyword:
            return jsonify({'success': False, 'error': 'Keyword required'}), 400
        job_id = scheduler.create_schedule(keyword, freq, email, notify_on_drop, notify_on_improve, notify_on_issue)
        return jsonify({'success': True, 'job_id': job_id, 'message': 'Schedule created successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scheduled-jobs', methods=['GET'])
@app.route('/api/schedule/list', methods=['GET'])
def api_scheduled_jobs():
    try:
        jobs = scheduler.get_all_schedules()
        return jsonify({'success': True, 'jobs': jobs, 'schedules': jobs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'jobs': [], 'schedules': []}), 500


@app.route('/api/schedule/<int:job_id>', methods=['DELETE'])
def api_delete_schedule(job_id):
    try:
        return jsonify({'success': scheduler.delete_schedule(job_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/schedule/run-now/<int:job_id>', methods=['POST'])
def api_run_now(job_id):
    try:
        result = scheduler.run_now(job_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/schedule/restore/<int:job_id>', methods=['POST'])
def api_restore_schedule(job_id):
    try:
        return jsonify({'success': scheduler.restore_schedule(job_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/schedule/history/<int:job_id>', methods=['GET'])
def api_schedule_history(job_id):
    try:
        history_data = scheduler.get_job_history(job_id)
        return jsonify({'success': True, 'history': history_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'history': []}), 500


# === COMPARE, TRENDS, CONTENT SCORE, EXPORT ===

@app.route('/api/compare', methods=['POST'])
def api_compare():
    data = request.get_json()
    keywords = data.get('keywords', [])
    if len(keywords) < 2:
        return jsonify({'success': False, 'error': 'Need at least 2 keywords'}), 400
    try:
        results = []
        for kw in keywords[:3]:
            analysis = run_full_platform_analysis(kw)
            results.append({
                'keyword': kw,
                'aeo_score': analysis['aeo_score'],
                'ai_visibility': analysis['ai_visibility'],
                'will_ai_choose_you': analysis['will_ai_choose_you'],
                'competitor_snapshot': analysis['competitor_snapshot'],
            })
        winner = max(results, key=lambda r: r['aeo_score']['score'] + r['ai_visibility']['score'])
        return jsonify({'success': True, 'results': results, 'winner': winner['keyword']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trends', methods=['GET'])
def api_trends():
    try:
        if USE_DYNAMO_AEO and aeo_repo:
            trends = aeo_repo.get_trend_data(limit=20)
        else:
            trends = db.get_trend_data(limit=20)
        return jsonify({'success': True, 'trends': trends})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'trends': []}), 500


@app.route('/api/content-score', methods=['POST'])
def api_content_score():
    data = request.get_json()
    keyword = data.get('keyword', '')
    content_text = data.get('content', '')
    if not content_text:
        return jsonify({'success': False, 'error': 'Content required'}), 400
    try:
        result = score_content(keyword, content_text)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export-report', methods=['POST'])
def api_export_report():
    """Generate a text-based report (returned as JSON, no file writes)."""
    data = request.get_json()
    topic = data.get('topic', '')
    if not topic:
        return jsonify({'error': 'Topic required'}), 400
    try:
        result = run_full_platform_analysis(topic)
        aeo = result['aeo_score']
        vis = result['ai_visibility']
        choose = result['will_ai_choose_you']
        boost = result['boost_to_90']
        serp = result['ai_serp_simulation']

        report = []
        report.append("=" * 60)
        report.append("AEO PLATFORM — ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"Keyword: {topic}")
        report.append(f"Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("")
        report.append("--- SCORES ---")
        report.append(f"AEO Score: {aeo['score']}/100 (Grade: {aeo['grade']})")
        report.append(f"AI Visibility: {vis['score']}/100 (Grade: {vis['grade']})")
        report.append(f"AI Selection Likelihood: {choose['likelihood']}")
        report.append("")
        report.append("--- AEO BREAKDOWN ---")
        for c in aeo['components'].values():
            report.append(f"  {c['label']}: {c['score']}/{c['max']}")
        if aeo['missing']:
            report.append("")
            report.append("--- MISSING ELEMENTS ---")
            for m in aeo['missing']:
                report.append(f"  \u26a0 {m}")
        report.append("")
        report.append("--- AI SERP SIMULATION ---")
        report.append(f"Would be cited: {'Yes' if serp['would_be_cited'] else 'No'}")
        report.append(f"Your score: {serp['user_score']}")
        report.append(f"Verdict: {serp['verdict']}")
        report.append("")
        report.append("--- BOOST TO 90+ ---")
        report.append(f"Current: {boost['current_aeo']} \u2192 Projected: {boost['projected_aeo']}")
        for b in boost['boosts']:
            report.append(f"  +{b['gain']} pts: {b['area']} \u2014 {b['action']}")
        report.append("")
        report.append("--- FAQ SUGGESTIONS ---")
        for i, q in enumerate(result['faq'], 1):
            report.append(f"  {i}. {q}")
        report.append("")
        report.append("--- FIX PLAN ---")
        for i, f in enumerate(result['optimize_for_ai'], 1):
            report.append(f"  Step {i}: {f['step']} ({f['impact']} Impact)")
        report.append("")
        report.append("=" * 60)
        report.append("Generated by AEO Platform \u2014 AI Answer Engine Optimization")
        report.append("=" * 60)

        return jsonify({'success': True, 'report': '\n'.join(report), 'keyword': topic})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === GEO READINESS ===

@app.route('/api/geo', methods=['POST'])
@app.route('/api/aeo/geo', methods=['POST'])
def api_geo():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    content = data.get('content', '')
    if not keyword:
        return jsonify({'success': False, 'error': 'Keyword required'}), 400
    try:
        result = run_geo_analysis(keyword, content)
        if USE_DYNAMO_GEO and geo_repo:
            geo_repo.save_scan(keyword, result)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === OPENCLAW STATUS ===

@app.route('/api/openclaw/status', methods=['GET'])
def api_openclaw_status():
    """Check OpenClaw/Bedrock connection status"""
    try:
        status = bedrock.check_status()
        return jsonify({'success': True, **status})
    except Exception as e:
        return jsonify({'success': False, 'connected': False, 'error': str(e)})


# === AI LAB ===

@app.route('/api/ai-lab', methods=['POST'])
def api_ai_lab():
    data = request.get_json()
    topic = data.get('topic', '')
    tool = data.get('tool', '')
    mode = data.get('mode', 'gemini')
    if not topic:
        return jsonify({'error': 'Topic required'}), 400
    try:
        from src.ai_lab_tools import run_ai_lab_tool
        result = run_ai_lab_tool(topic, tool, mode)
        return jsonify({'success': True, 'query': topic, 'tool': tool, 'mode': mode, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===================== FEATURE: AEO SCORER =====================
from src.aeo_scorer import score_content_for_aeo

@app.route('/aeo-scorer')
def aeo_scorer_page():
    return render_template('aeo_scorer.html')

@app.route('/api/aeo-scorer', methods=['POST'])
def api_aeo_scorer():
    try:
        data = request.get_json()
        content = data.get('content', '')
        if not content or len(content.strip()) < 20:
            return jsonify({'success': False, 'error': 'Content too short. Provide at least a paragraph.'}), 400
        result = score_content_for_aeo(content)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===================== FEATURE: CITATION DIAGNOSIS =====================
from src.citation_diagnosis import diagnose_citation

@app.route('/diagnosis')
def diagnosis_page():
    return render_template('diagnosis.html')

@app.route('/api/diagnosis', methods=['POST'])
def api_diagnosis():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        keyword = data.get('keyword', '').strip()
        if not url or not keyword:
            return jsonify({'success': False, 'error': 'URL and keyword are required'}), 400
        result = diagnose_citation(url, keyword)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===================== FEATURE: ANSWER MONITORING =====================
from src.answer_monitor import AnswerMonitor
monitor = AnswerMonitor(db_path=os.path.join(DB_DIR, 'answer_monitors.db'))

@app.route('/monitoring')
def monitoring_page():
    return render_template('monitoring.html')

@app.route('/api/monitors', methods=['GET'])
def api_get_monitors():
    try:
        monitors = monitor.get_monitors()
        return jsonify({'success': True, 'monitors': monitors})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/monitors', methods=['POST'])
def api_add_monitor():
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()
        if not keyword:
            return jsonify({'success': False, 'error': 'Keyword required'}), 400
        result = monitor.add_monitor(keyword)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/monitors/<int:monitor_id>', methods=['DELETE'])
def api_delete_monitor(monitor_id):
    try:
        result = monitor.delete_monitor(monitor_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/monitors/<int:monitor_id>/check', methods=['POST'])
def api_check_monitor(monitor_id):
    try:
        monitors = monitor.get_monitors()
        target = next((m for m in monitors if m['id'] == monitor_id), None)
        if not target:
            return jsonify({'success': False, 'error': 'Monitor not found'}), 404
        answer = monitor.check_keyword(target['keyword'])
        result = monitor.update_answer(monitor_id, answer)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===================== FEATURE: REVERSE ENGINEER =====================
from src.reverse_engineer import reverse_engineer_competitor

@app.route('/reverse-engineer')
def reverse_engineer_page():
    return render_template('reverse_engineer.html')

@app.route('/api/reverse-engineer', methods=['POST'])
def api_reverse_engineer():
    try:
        data = request.get_json()
        competitor = data.get('competitor', '').strip()
        industry = data.get('industry', '').strip()
        if not competitor:
            return jsonify({'success': False, 'error': 'Competitor URL or brand name required'}), 400
        result = reverse_engineer_competitor(competitor, industry)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===================== LAMBDA HANDLER =====================

def handler(event, context):
    """AWS Lambda handler — converts API Gateway HTTP API v2 events to Flask WSGI."""
    import io
    from urllib.parse import urlencode

    http = event.get('requestContext', {}).get('http', {})
    method = http.get('method', 'GET')
    path = event.get('rawPath', '/')
    qs = event.get('rawQueryString', '')
    headers = event.get('headers', {})
    body = event.get('body', '') or ''
    is_base64 = event.get('isBase64Encoded', False)

    if is_base64 and body:
        import base64
        body = base64.b64decode(body)
    elif isinstance(body, str):
        body = body.encode('utf-8')

    environ = {
        'REQUEST_METHOD': method,
        'SCRIPT_NAME': '',
        'PATH_INFO': path,
        'QUERY_STRING': qs,
        'SERVER_NAME': headers.get('host', 'lambda'),
        'SERVER_PORT': headers.get('x-forwarded-port', '443'),
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': headers.get('x-forwarded-proto', 'https'),
        'wsgi.input': io.BytesIO(body),
        'wsgi.errors': io.StringIO(),
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
        'CONTENT_LENGTH': str(len(body)),
        'CONTENT_TYPE': headers.get('content-type', ''),
    }

    for key, value in headers.items():
        wsgi_key = 'HTTP_' + key.upper().replace('-', '_')
        if wsgi_key not in ('HTTP_CONTENT_TYPE', 'HTTP_CONTENT_LENGTH'):
            environ[wsgi_key] = value

    response_started = []
    response_body = []

    def start_response(status, response_headers, exc_info=None):
        response_started.append((status, response_headers))

    result = app(environ, start_response)
    try:
        for chunk in result:
            response_body.append(chunk)
    finally:
        if hasattr(result, 'close'):
            result.close()

    status_line = response_started[0][0]
    status_code = int(status_line.split(' ', 1)[0])
    resp_headers = {k: v for k, v in response_started[0][1]}

    body_bytes = b''.join(response_body)
    import base64
    is_binary = not resp_headers.get('Content-Type', '').startswith('text') and \
                not resp_headers.get('Content-Type', '').endswith('json')

    return {
        'statusCode': status_code,
        'headers': resp_headers,
        'body': base64.b64encode(body_bytes).decode() if is_binary else body_bytes.decode('utf-8', errors='replace'),
        'isBase64Encoded': is_binary,
    }

# Local development entry point
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print("\n" + "=" * 50)
    print("AEO-First AI SEO Platform v6.0 — Lambda-Ready")
    print("=" * 50)
    print(f"\nhttp://localhost:{port}")
    print("Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
