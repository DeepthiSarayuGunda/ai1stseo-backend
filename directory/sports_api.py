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
