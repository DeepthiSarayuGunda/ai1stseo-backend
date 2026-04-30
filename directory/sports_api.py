#!/usr/bin/env python3
"""REST API for the Sports module — matches, scores, rankings, news, teams.

Blueprint: /api/sports/*
Powers the Sports tab on the Directory page with live data.

Endpoints:
  GET    /api/sports/                              — list all sports
  GET    /api/sports/<slug>                        — single sport detail
  POST   /api/sports/                              — create sport (admin)

  GET    /api/sports/<slug>/matches                — matches (filter: status, league)
  POST   /api/sports/<slug>/matches                — create match (admin)
  POST   /api/sports/<slug>/matches/bulk           — bulk create matches (admin)
  PUT    /api/sports/matches/<id>                  — update match score/status (admin)

  GET    /api/sports/<slug>/teams                  — teams for a sport
  POST   /api/sports/<slug>/teams                  — create team (admin)
  POST   /api/sports/<slug>/teams/bulk             — bulk create teams (admin)

  GET    /api/sports/<slug>/rankings               — league standings
  POST   /api/sports/<slug>/rankings               — upsert ranking (admin)
  POST   /api/sports/<slug>/rankings/bulk          — bulk upsert rankings (admin)

  GET    /api/sports/news                          — news across all sports
  GET    /api/sports/<slug>/news                   — news for a sport
  POST   /api/sports/<slug>/news                   — create news item (admin)
  POST   /api/sports/<slug>/news/bulk              — bulk create news (admin)

  GET    /api/sports/trending                      — trending news
  GET    /api/sports/explore                       — explore categories grid
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

sports_bp = Blueprint('sports_module', __name__, url_prefix='/api/sports')


def _err(msg, code=400):
    return jsonify({'error': msg}), code


def _ok(data, code=200):
    return jsonify(data), code


# ── Sports list ───────────────────────────────────────────────────────────────

@sports_bp.route('/', methods=['GET'])
@sports_bp.route('', methods=['GET'])
def list_sports():
    """List all sports categories."""
    try:
        from directory.sports_db import get_sports
        sports = get_sports(active_only=request.args.get('all') != 'true')
        return _ok({'sports': sports, 'count': len(sports)})
    except Exception as e:
        logger.exception("list_sports failed")
        return _err(f'Failed to load sports: {e}', 500)


@sports_bp.route('/<slug>', methods=['GET'])
def get_sport(slug):
    """Get a single sport with summary stats."""
    try:
        from directory.sports_db import get_sport_by_slug, get_matches, get_news
        sport = get_sport_by_slug(slug)
        if not sport:
            return _err('Sport not found', 404)
        # Include recent matches and news preview
        matches = get_matches(slug, limit=6)
        news = get_news(slug, limit=5)
        sport['recent_matches'] = matches['matches']
        sport['recent_news'] = news
        return _ok(sport)
    except Exception as e:
        logger.exception("get_sport failed")
        return _err(f'Failed to load sport: {e}', 500)


@sports_bp.route('/', methods=['POST'])
@sports_bp.route('', methods=['POST'])
def create_sport_endpoint():
    """Create a new sport category."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('slug'):
        return _err('name and slug are required')
    try:
        from directory.sports_db import create_sport
        sport = create_sport(
            name=data['name'], slug=data['slug'],
            icon=data.get('icon', ''), description=data.get('description', ''),
            sort_order=data.get('sort_order', 0), meta_json=data.get('meta_json')
        )
        return _ok({'sport': sport, 'message': 'Sport created'}, 201)
    except Exception as e:
        logger.exception("create_sport failed")
        return _err(f'Failed to create sport: {e}', 500)


# ── Matches ───────────────────────────────────────────────────────────────────

@sports_bp.route('/<slug>/matches', methods=['GET'])
def list_matches(slug):
    """Get matches for a sport.

    Query params:
      status  — live | final | scheduled | all (default: all)
      league  — filter by league name
      limit   — max results (default 20)
      offset  — pagination offset
    """
    try:
        from directory.sports_db import get_matches
        status = request.args.get('status')
        league = request.args.get('league')
        limit = min(int(request.args.get('limit', 20)), 100)
        offset = int(request.args.get('offset', 0))
        result = get_matches(slug, status=status, league=league, limit=limit, offset=offset)
        if not result['matches'] and not result['total']:
            # Check if sport exists
            from directory.sports_db import get_sport_by_slug
            if not get_sport_by_slug(slug):
                return _err('Sport not found', 404)
        return _ok({
            'matches': result['matches'],
            'total': result['total'],
            'limit': limit,
            'offset': offset,
        })
    except Exception as e:
        logger.exception("list_matches failed")
        return _err(f'Failed to load matches: {e}', 500)


@sports_bp.route('/<slug>/matches', methods=['POST'])
def create_match_endpoint(slug):
    """Create a new match."""
    data = request.get_json()
    if not data or not data.get('home_team') or not data.get('away_team') or not data.get('match_date'):
        return _err('home_team, away_team, and match_date are required')
    try:
        from directory.sports_db import create_match
        match = create_match(slug, data)
        if not match:
            return _err('Sport not found', 404)
        return _ok({'match': match, 'message': 'Match created'}, 201)
    except Exception as e:
        logger.exception("create_match failed")
        return _err(f'Failed to create match: {e}', 500)


@sports_bp.route('/<slug>/matches/bulk', methods=['POST'])
def bulk_create_matches_endpoint(slug):
    """Bulk create matches."""
    data = request.get_json()
    if not data or not data.get('matches'):
        return _err('matches array is required')
    try:
        from directory.sports_db import bulk_create_matches
        count = bulk_create_matches(slug, data['matches'])
        return _ok({'created': count}, 201)
    except Exception as e:
        logger.exception("bulk_create_matches failed")
        return _err(f'Bulk create failed: {e}', 500)


@sports_bp.route('/matches/<int:match_id>', methods=['PUT'])
def update_match_endpoint(match_id):
    """Update a match (score, status, etc.)."""
    data = request.get_json()
    if not data:
        return _err('Request body required')
    try:
        from directory.sports_db import update_match
        match = update_match(match_id, data)
        if not match:
            return _err('Match not found', 404)
        return _ok({'match': match, 'message': 'Match updated'})
    except Exception as e:
        logger.exception("update_match failed")
        return _err(f'Failed to update match: {e}', 500)


# ── Teams ─────────────────────────────────────────────────────────────────────

@sports_bp.route('/<slug>/teams', methods=['GET'])
def list_teams(slug):
    """Get teams for a sport, optionally filtered by league."""
    try:
        from directory.sports_db import get_teams
        league = request.args.get('league')
        limit = min(int(request.args.get('limit', 50)), 200)
        teams = get_teams(slug, league=league, limit=limit)
        return _ok({'teams': teams, 'count': len(teams)})
    except Exception as e:
        logger.exception("list_teams failed")
        return _err(f'Failed to load teams: {e}', 500)


@sports_bp.route('/<slug>/teams', methods=['POST'])
def create_team_endpoint(slug):
    """Create a new team."""
    data = request.get_json()
    if not data or not data.get('name'):
        return _err('name is required')
    try:
        from directory.sports_db import create_team
        team = create_team(slug, data)
        if not team:
            return _err('Sport not found', 404)
        return _ok({'team': team, 'message': 'Team created'}, 201)
    except Exception as e:
        logger.exception("create_team failed")
        return _err(f'Failed to create team: {e}', 500)


@sports_bp.route('/<slug>/teams/bulk', methods=['POST'])
def bulk_create_teams_endpoint(slug):
    """Bulk create teams."""
    data = request.get_json()
    if not data or not data.get('teams'):
        return _err('teams array is required')
    try:
        from directory.sports_db import bulk_create_teams
        count = bulk_create_teams(slug, data['teams'])
        return _ok({'created': count}, 201)
    except Exception as e:
        logger.exception("bulk_create_teams failed")
        return _err(f'Bulk create failed: {e}', 500)


# ── Rankings ──────────────────────────────────────────────────────────────────

@sports_bp.route('/<slug>/rankings', methods=['GET'])
def list_rankings(slug):
    """Get league standings/rankings.

    Query params: league (required), season (default: 2025-26)
    """
    league = request.args.get('league')
    if not league:
        return _err('league parameter is required')
    try:
        from directory.sports_db import get_rankings
        season = request.args.get('season', '2025-26')
        rankings = get_rankings(slug, league, season=season)
        return _ok({'rankings': rankings, 'league': league, 'season': season, 'count': len(rankings)})
    except Exception as e:
        logger.exception("list_rankings failed")
        return _err(f'Failed to load rankings: {e}', 500)


@sports_bp.route('/<slug>/rankings', methods=['POST'])
def upsert_ranking_endpoint(slug):
    """Upsert a single ranking entry."""
    data = request.get_json()
    if not data or not data.get('league') or not data.get('team_name') or data.get('position') is None:
        return _err('league, team_name, and position are required')
    try:
        from directory.sports_db import upsert_ranking
        ranking = upsert_ranking(slug, data)
        if not ranking:
            return _err('Sport not found', 404)
        return _ok({'ranking': ranking, 'message': 'Ranking upserted'}, 201)
    except Exception as e:
        logger.exception("upsert_ranking failed")
        return _err(f'Failed to upsert ranking: {e}', 500)


@sports_bp.route('/<slug>/rankings/bulk', methods=['POST'])
def bulk_upsert_rankings_endpoint(slug):
    """Bulk upsert rankings for a league."""
    data = request.get_json()
    if not data or not data.get('rankings'):
        return _err('rankings array is required')
    try:
        from directory.sports_db import bulk_upsert_rankings
        count = bulk_upsert_rankings(slug, data['rankings'])
        return _ok({'upserted': count}, 201)
    except Exception as e:
        logger.exception("bulk_upsert_rankings failed")
        return _err(f'Bulk upsert failed: {e}', 500)


# ── News ──────────────────────────────────────────────────────────────────────

@sports_bp.route('/news', methods=['GET'])
def global_news():
    """Get news across all sports."""
    try:
        from directory.sports_db import get_news
        limit = min(int(request.args.get('limit', 20)), 100)
        trending = request.args.get('trending') == 'true'
        news = get_news(trending_only=trending, limit=limit)
        return _ok({'news': news, 'count': len(news)})
    except Exception as e:
        logger.exception("global_news failed")
        return _err(f'Failed to load news: {e}', 500)


@sports_bp.route('/<slug>/news', methods=['GET'])
def sport_news(slug):
    """Get news for a specific sport."""
    try:
        from directory.sports_db import get_news
        limit = min(int(request.args.get('limit', 20)), 100)
        trending = request.args.get('trending') == 'true'
        news = get_news(slug, trending_only=trending, limit=limit)
        return _ok({'news': news, 'count': len(news)})
    except Exception as e:
        logger.exception("sport_news failed")
        return _err(f'Failed to load news: {e}', 500)


@sports_bp.route('/<slug>/news', methods=['POST'])
def create_news_endpoint(slug):
    """Create a news item."""
    data = request.get_json()
    if not data or not data.get('title'):
        return _err('title is required')
    try:
        from directory.sports_db import create_news
        news = create_news(slug, data)
        if not news:
            return _err('Sport not found', 404)
        return _ok({'news': news, 'message': 'News created'}, 201)
    except Exception as e:
        logger.exception("create_news failed")
        return _err(f'Failed to create news: {e}', 500)


@sports_bp.route('/<slug>/news/bulk', methods=['POST'])
def bulk_create_news_endpoint(slug):
    """Bulk create news items."""
    data = request.get_json()
    if not data or not data.get('news'):
        return _err('news array is required')
    try:
        from directory.sports_db import bulk_create_news
        count = bulk_create_news(slug, data['news'])
        return _ok({'created': count}, 201)
    except Exception as e:
        logger.exception("bulk_create_news failed")
        return _err(f'Bulk create failed: {e}', 500)


# ── Trending & Explore ────────────────────────────────────────────────────────

@sports_bp.route('/trending', methods=['GET'])
def trending():
    """Get trending news items across all sports."""
    try:
        from directory.sports_db import get_news
        limit = min(int(request.args.get('limit', 10)), 50)
        news = get_news(trending_only=True, limit=limit)
        return _ok({'trending': news, 'count': len(news)})
    except Exception as e:
        logger.exception("trending failed")
        return _err(f'Failed to load trending: {e}', 500)


@sports_bp.route('/explore', methods=['GET'])
def explore():
    """Get all sport categories for the 'Explore More' grid."""
    try:
        from directory.sports_db import get_explore_categories
        cats = get_explore_categories()
        return _ok({'categories': cats, 'count': len(cats)})
    except Exception as e:
        logger.exception("explore failed")
        return _err(f'Failed to load explore: {e}', 500)


# ── Live data sync (admin) ───────────────────────────────────────────────────

@sports_bp.route('/sync/today', methods=['POST'])
def sync_today():
    """Fetch today's real events from TheSportsDB and store them."""
    try:
        from directory.sports_fetcher import sync_todays_events
        sport = request.args.get('sport')
        count = sync_todays_events(sport_slug=sport)
        return _ok({'synced': count, 'message': f'Synced {count} events for today'})
    except Exception as e:
        logger.exception("sync_today failed")
        return _err(f'Sync failed: {e}', 500)


@sports_bp.route('/sync/league', methods=['POST'])
def sync_league():
    """Sync matches + standings for a specific league from TheSportsDB.

    Body: { "sport": "football", "league": "Premier League" }
    """
    data = request.get_json()
    if not data or not data.get('sport') or not data.get('league'):
        return _err('sport and league are required')
    try:
        from directory.sports_fetcher import sync_league_matches, sync_league_standings, sync_league_teams
        sport = data['sport']
        league = data['league']
        teams = sync_league_teams(sport, league)
        matches = sync_league_matches(sport, league)
        standings = sync_league_standings(sport, league)
        return _ok({
            'teams_synced': teams,
            'matches_synced': matches,
            'standings_synced': standings,
            'message': f'Synced {league} data from TheSportsDB'
        })
    except Exception as e:
        logger.exception("sync_league failed")
        return _err(f'Sync failed: {e}', 500)


@sports_bp.route('/sync/all', methods=['POST'])
def sync_all():
    """Sync all configured sports/leagues from TheSportsDB. Takes a few minutes."""
    try:
        from directory.sports_fetcher import sync_all_sports
        results = sync_all_sports()
        return _ok({'results': results, 'message': 'Full sync complete'})
    except Exception as e:
        logger.exception("sync_all failed")
        return _err(f'Full sync failed: {e}', 500)


# ── PDF Export ────────────────────────────────────────────────────────────────

@sports_bp.route('/<slug>/rankings/pdf', methods=['GET'])
def export_rankings_pdf(slug):
    """Download league rankings as a PDF.

    Query params: league (required), season (default: 2025-26)
    """
    league = request.args.get('league')
    if not league:
        return _err('league parameter is required')
    try:
        from directory.sports_db import get_rankings, get_sport_by_slug
        season = request.args.get('season', '2025-26')
        sport = get_sport_by_slug(slug)
        rankings = get_rankings(slug, league, season=season)
        if not rankings:
            return _err('No rankings found', 404)

        sport_name = sport['name'] if sport else slug.replace('-', ' ').title()
        pdf_bytes = _generate_rankings_pdf(sport_name, league, season, rankings)

        from flask import Response
        filename = f"{slug}-{league.replace(' ', '_')}-rankings-{season}.pdf"
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.exception("export_rankings_pdf failed")
        return _err(f'PDF generation failed: {e}', 500)


@sports_bp.route('/<slug>/matches/pdf', methods=['GET'])
def export_matches_pdf(slug):
    """Download recent matches as a PDF."""
    try:
        from directory.sports_db import get_matches, get_sport_by_slug
        sport = get_sport_by_slug(slug)
        league = request.args.get('league')
        status = request.args.get('status')
        matches = get_matches(slug, status=status, league=league, limit=50)
        if not matches:
            return _err('No matches found', 404)

        sport_name = sport['name'] if sport else slug.replace('-', ' ').title()
        pdf_bytes = _generate_matches_pdf(sport_name, league, matches)

        from flask import Response
        filename = f"{slug}-matches.pdf"
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.exception("export_matches_pdf failed")
        return _err(f'PDF generation failed: {e}', 500)


def _generate_rankings_pdf(sport_name, league, season, rankings):
    """Generate a PDF document for league rankings using reportlab or fallback."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        import io

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph(
            f"{sport_name} — {league} Rankings ({season})",
            styles['Title']
        ))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            "Generated by AI1stSEO Sports Directory",
            styles['Normal']
        ))
        elements.append(Spacer(1, 20))

        # Ranking parameters explanation
        elements.append(Paragraph(
            "<b>Ranking Parameters:</b> Position is determined by Points (Pts), "
            "then Goal Difference (GD = GF - GA), then Goals For (GF). "
            "Win = 3 pts, Draw = 1 pt, Loss = 0 pts.",
            styles['Normal']
        ))
        elements.append(Spacer(1, 16))

        # Table
        header = ['#', 'Team', 'P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts']
        data = [header]
        for r in rankings:
            meta = r.get('meta_json', {}) or {}
            data.append([
                r.get('position', ''),
                r.get('team_name', r.get('name', '')),
                meta.get('played', r.get('played', '')),
                meta.get('win', r.get('win', '')),
                meta.get('draw', r.get('draw', '')),
                meta.get('loss', r.get('loss', '')),
                meta.get('goals_for', r.get('goals_for', '')),
                meta.get('goals_against', r.get('goals_against', '')),
                meta.get('goal_diff', r.get('goal_diff', '')),
                r.get('points', ''),
            ])

        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(
            f"Source: AI1stSEO Sports Directory · ai1stseo.com · {season}",
            styles['Normal']
        ))

        doc.build(elements)
        return buf.getvalue()

    except ImportError:
        # Fallback: generate a simple text-based PDF without reportlab
        return _generate_simple_pdf_rankings(sport_name, league, season, rankings)


def _generate_simple_pdf_rankings(sport_name, league, season, rankings):
    """Minimal PDF generation without reportlab (pure Python)."""
    lines = [
        f"{sport_name} - {league} Rankings ({season})",
        "=" * 60,
        "Generated by AI1stSEO Sports Directory",
        "",
        "Ranking Parameters: Position determined by Points (Pts),",
        "then Goal Difference (GD), then Goals For (GF).",
        "Win = 3 pts, Draw = 1 pt, Loss = 0 pts.",
        "",
        f"{'#':<4}{'Team':<25}{'P':<5}{'W':<5}{'D':<5}{'L':<5}{'Pts':<5}",
        "-" * 60,
    ]
    for r in rankings:
        meta = r.get('meta_json', {}) or {}
        lines.append(
            f"{r.get('position', ''):<4}"
            f"{(r.get('team_name', r.get('name', '')))[:24]:<25}"
            f"{meta.get('played', ''):<5}"
            f"{meta.get('win', ''):<5}"
            f"{meta.get('draw', ''):<5}"
            f"{meta.get('loss', ''):<5}"
            f"{r.get('points', ''):<5}"
        )
    text = '\n'.join(lines)

    # Build minimal PDF manually
    import io
    buf = io.BytesIO()
    content_stream = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    # Split into lines for PDF text rendering
    pdf_lines = text.split('\n')
    stream_parts = []
    y = 750
    for line in pdf_lines:
        safe = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream_parts.append(f"BT /F1 10 Tf {50} {y} Td ({safe}) Tj ET")
        y -= 14
        if y < 50:
            break

    stream_content = '\n'.join(stream_parts)
    stream_bytes = stream_content.encode('latin-1', errors='replace')

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Courier>>endobj\n"
        b"4 0 obj<</Length " + str(len(stream_bytes)).encode() + b">>\n"
        b"stream\n" + stream_bytes + b"\nendstream\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000306 00000 n \n"
        b"0000000266 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\n"
        b"startxref\n0\n%%EOF"
    )
    buf.write(pdf)
    return buf.getvalue()


def _generate_matches_pdf(sport_name, league, matches):
    """Generate a PDF document for match results."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        import io

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        title = f"{sport_name} Matches"
        if league:
            title += f" — {league}"
        elements.append(Paragraph(title, styles['Title']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            "Generated by AI1stSEO Sports Directory",
            styles['Normal']
        ))
        elements.append(Spacer(1, 20))

        header = ['Date', 'Home', 'Score', 'Away', 'League', 'Status']
        data = [header]
        for m in matches:
            date_str = (m.get('match_date') or '')[:10]
            score = f"{m.get('home_score', '')} - {m.get('away_score', '')}"
            if not m.get('home_score') and not m.get('away_score'):
                score = 'TBD'
            data.append([
                date_str,
                m.get('home_team_name', ''),
                score,
                m.get('away_team_name', ''),
                m.get('league', ''),
                m.get('status', ''),
            ])

        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t)
        doc.build(elements)
        return buf.getvalue()

    except ImportError:
        # Fallback text PDF
        lines = [f"{sport_name} Matches", "=" * 60, ""]
        for m in matches:
            lines.append(
                f"{(m.get('match_date') or '')[:10]}  "
                f"{m.get('home_team_name', '')} {m.get('home_score', '')} - "
                f"{m.get('away_score', '')} {m.get('away_team_name', '')}  "
                f"({m.get('league', '')})"
            )
        return _generate_simple_pdf_rankings(sport_name, league or 'All', '', [])


# ── Ranking Parameters ────────────────────────────────────────────────────────

@sports_bp.route('/<slug>/ranking-parameters', methods=['GET'])
def ranking_parameters(slug):
    """Explain which parameters contribute to rankings for a sport."""
    from directory.sports_db import get_sport_by_slug
    sport = get_sport_by_slug(slug)
    if not sport:
        return _err('Sport not found', 404)

    # Sport-specific ranking parameter definitions
    RANKING_PARAMS = {
        'football': {
            'sport': 'Football',
            'parameters': [
                {'name': 'Points (Pts)', 'weight': 'Primary', 'description': 'Win = 3 pts, Draw = 1 pt, Loss = 0 pts. The main ranking factor.'},
                {'name': 'Goal Difference (GD)', 'weight': 'Tiebreaker #1', 'description': 'Goals For minus Goals Against. Used when teams are tied on points.'},
                {'name': 'Goals For (GF)', 'weight': 'Tiebreaker #2', 'description': 'Total goals scored. Rewards attacking play when GD is equal.'},
                {'name': 'Head-to-Head', 'weight': 'Tiebreaker #3', 'description': 'Direct match results between tied teams (used in some leagues like La Liga).'},
                {'name': 'Matches Played (P)', 'weight': 'Context', 'description': 'Total games played. Fewer games may mean a team has matches in hand.'},
            ],
            'methodology': 'Standard league table format used by FIFA and most football leagues worldwide.'
        },
        'cricket': {
            'sport': 'Cricket',
            'parameters': [
                {'name': 'Points (Pts)', 'weight': 'Primary', 'description': 'Win = 2 pts, Tie/No Result = 1 pt, Loss = 0 pts.'},
                {'name': 'Net Run Rate (NRR)', 'weight': 'Tiebreaker #1', 'description': 'Difference between run rate scored and run rate conceded. Higher is better.'},
                {'name': 'Matches Won', 'weight': 'Tiebreaker #2', 'description': 'Total wins when teams are tied on points and NRR.'},
                {'name': 'Head-to-Head', 'weight': 'Tiebreaker #3', 'description': 'Direct match results between tied teams.'},
            ],
            'methodology': 'ICC standard points system used in T20, ODI, and Test championships.'
        },
        'basketball': {
            'sport': 'Basketball',
            'parameters': [
                {'name': 'Win Percentage', 'weight': 'Primary', 'description': 'Wins divided by total games. The main ranking factor in NBA.'},
                {'name': 'Games Behind (GB)', 'weight': 'Context', 'description': 'How many games behind the division/conference leader.'},
                {'name': 'Head-to-Head', 'weight': 'Tiebreaker #1', 'description': 'Season series record between tied teams.'},
                {'name': 'Division Record', 'weight': 'Tiebreaker #2', 'description': 'Win percentage within the division.'},
                {'name': 'Conference Record', 'weight': 'Tiebreaker #3', 'description': 'Win percentage within the conference.'},
            ],
            'methodology': 'NBA standard standings format with conference/division structure.'
        },
    }

    # Default parameters for sports not explicitly defined
    default_params = {
        'sport': sport['name'],
        'parameters': [
            {'name': 'Points (Pts)', 'weight': 'Primary', 'description': 'Points accumulated from match results. The main ranking factor.'},
            {'name': 'Win/Loss Record', 'weight': 'Tiebreaker #1', 'description': 'Total wins vs losses when points are tied.'},
            {'name': 'Head-to-Head', 'weight': 'Tiebreaker #2', 'description': 'Direct match results between tied teams.'},
        ],
        'methodology': 'Standard points-based ranking system.'
    }

    params = RANKING_PARAMS.get(slug, default_params)
    return _ok(params)


# ── Registration ──────────────────────────────────────────────────────────────

def register_sports_module(app):
    """Register the sports module blueprint with the Flask app."""
    from directory.sports_db import init_sports_tables
    try:
        init_sports_tables()
        logger.info("Sports tables initialized")
    except Exception as e:
        logger.warning("Sports table init failed (non-fatal): %s", e)
    app.register_blueprint(sports_bp)
    logger.info("Sports module registered at /api/sports")
