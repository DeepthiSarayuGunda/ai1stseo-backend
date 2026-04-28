#!/usr/bin/env python3
"""Fetch REAL live sports data from TheSportsDB free API.

Pulls real matches, scores, standings, and teams into the sports_db tables.
Free API key: 123 (30 requests/min limit).

Usage:
  python -m directory.sports_fetcher              # fetch all
  python -m directory.sports_fetcher --football   # football only
  python -m directory.sports_fetcher --cricket    # cricket only

TheSportsDB league IDs used:
  4328 = English Premier League
  4480 = Champions League
  4331 = Bundesliga
  4335 = La Liga
  4332 = Serie A
  4334 = Ligue 1
  4346 = MLS
  4337 = NHL
  4387 = NBA
  4424 = MLB
  4429 = Indian Premier League (Cricket)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://www.thesportsdb.com/api/v1/json"
API_KEY = os.environ.get("SPORTSDB_API_KEY", "123")  # free key

# League IDs on TheSportsDB
LEAGUE_MAP = {
    "football": {
        "Premier League": 4328,
        "Champions League": 4480,
        "La Liga": 4335,
        "Serie A": 4332,
        "Bundesliga": 4331,
        "Ligue 1": 4334,
        "MLS": 4346,
    },
    "ice-hockey": {
        "NHL": 4380,
    },
    "basketball": {
        "NBA": 4387,
    },
    "baseball": {
        "MLB": 4424,
    },
    "cricket": {
        "IPL": 4429,
    },
}

# Sport slug -> TheSportsDB sport name (for events by day)
SPORT_NAME_MAP = {
    "football": "Soccer",
    "ice-hockey": "Ice Hockey",
    "basketball": "Basketball",
    "baseball": "Baseball",
    "cricket": "Cricket",
    "tennis": "Tennis",
    "golf": "Golf",
    "rugby": "Rugby",
    "boxing": "Fighting",
    "formula-1": "Motorsport",
    "cycling": "Cycling",
}


def _api_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """Make a GET request to TheSportsDB API with rate-limit awareness."""
    url = f"{API_BASE}/{API_KEY}/{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 429:
            logger.warning("Rate limited — waiting 60s")
            time.sleep(60)
            resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("API request failed: %s — %s", url, e)
        return None


# ── Fetch events for a league ─────────────────────────────────────────────────

def fetch_league_next_events(league_id: int) -> List[Dict]:
    """Fetch next upcoming events for a league."""
    data = _api_get(f"eventsnextleague.php?id={league_id}")
    if not data or not data.get("events"):
        return []
    return [_parse_event(e) for e in data["events"]]


def fetch_league_past_events(league_id: int) -> List[Dict]:
    """Fetch recent past events for a league."""
    data = _api_get(f"eventspastleague.php?id={league_id}")
    if not data or not data.get("events"):
        return []
    return [_parse_event(e) for e in data["events"]]


def fetch_events_by_day(date_str: str, sport: str = None, league_id: int = None) -> List[Dict]:
    """Fetch all events on a specific day. date_str: YYYY-MM-DD."""
    params = {"d": date_str}
    if sport:
        params["s"] = sport
    if league_id:
        params["l"] = str(league_id)
    data = _api_get("eventsday.php", params)
    if not data or not data.get("events"):
        return []
    return [_parse_event(e) for e in data["events"]]


def fetch_league_table(league_id: int, season: str = None) -> List[Dict]:
    """Fetch league standings/table."""
    url = f"lookuptable.php?l={league_id}"
    if season:
        url += f"&s={season}"
    data = _api_get(url)
    if not data or not data.get("table"):
        return []
    return [_parse_standing(s) for s in data["table"]]


def fetch_league_teams(league_id: int) -> List[Dict]:
    """Fetch all teams in a league."""
    data = _api_get(f"lookup_all_teams.php?id={league_id}")
    if not data or not data.get("teams"):
        return []
    return [_parse_team(t) for t in data["teams"]]


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_event(e: dict) -> Dict:
    """Convert TheSportsDB event to our match format."""
    home_score = e.get("intHomeScore") or ""
    away_score = e.get("intAwayScore") or ""

    # Determine status
    status = "scheduled"
    if home_score and away_score:
        status = "final"
    # TheSportsDB doesn't have a live flag in free API, but we can infer
    date_str = e.get("dateEvent", "")
    time_str = e.get("strTime") or e.get("strTimestamp", "")

    match_date = date_str
    if time_str and "T" not in date_str:
        # Try to build ISO timestamp
        time_part = time_str.split("+")[0].replace("Z", "")
        if len(time_part) >= 5:
            match_date = f"{date_str}T{time_part}"

    return {
        "home_team": e.get("strHomeTeam", "TBD"),
        "away_team": e.get("strAwayTeam", "TBD"),
        "home_score": str(home_score) if home_score else "",
        "away_score": str(away_score) if away_score else "",
        "status": status,
        "league": e.get("strLeague", ""),
        "venue": e.get("strVenue", ""),
        "match_date": match_date,
        "match_url": "",
        "meta_json": {
            "thesportsdb_id": e.get("idEvent"),
            "round": e.get("intRound"),
            "season": e.get("strSeason"),
            "sport": e.get("strSport"),
            "thumb": e.get("strThumb", ""),
        }
    }


def _parse_standing(s: dict) -> Dict:
    """Convert TheSportsDB table entry to our ranking format."""
    return {
        "league": s.get("strLeague", ""),
        "team_name": s.get("strTeam", ""),
        "position": int(s.get("intRank", 0)),
        "played": int(s.get("intPlayed", 0)),
        "won": int(s.get("intWin", 0)),
        "drawn": int(s.get("intDraw", 0)),
        "lost": int(s.get("intLoss", 0)),
        "gf": int(s.get("intGoalsFor", 0)),
        "ga": int(s.get("intGoalsAgainst", 0)),
        "gd": int(s.get("intGoalDifference", 0)),
        "points": int(s.get("intPoints", 0)),
        "season": s.get("strSeason", ""),
        "meta_json": {
            "thesportsdb_team_id": s.get("idTeam"),
            "badge": s.get("strTeamBadge", ""),
            "form": s.get("strForm", ""),
        }
    }


def _parse_team(t: dict) -> Dict:
    """Convert TheSportsDB team to our team format."""
    return {
        "name": t.get("strTeam", ""),
        "slug": _slugify(t.get("strTeam", "")),
        "short_name": t.get("strTeamShort", "") or "",
        "logo_url": t.get("strBadge", "") or "",
        "league": t.get("strLeague", ""),
        "country": t.get("strCountry", ""),
        "meta_json": {
            "thesportsdb_id": t.get("idTeam"),
            "stadium": t.get("strStadium", ""),
            "description": (t.get("strDescriptionEN") or "")[:500],
        }
    }


def _slugify(text: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


# ── High-level fetch + store functions ────────────────────────────────────────

def sync_league_matches(sport_slug: str, league_name: str):
    """Fetch next + past events for a league and store in DB."""
    from directory.sports_db import bulk_create_matches

    league_id = LEAGUE_MAP.get(sport_slug, {}).get(league_name)
    if not league_id:
        logger.warning("No league ID for %s / %s", sport_slug, league_name)
        return 0

    events = []
    # Past events (recent results)
    past = fetch_league_past_events(league_id)
    events.extend(past)
    time.sleep(2)  # respect rate limit

    # Next events (upcoming fixtures)
    upcoming = fetch_league_next_events(league_id)
    events.extend(upcoming)
    time.sleep(2)

    if not events:
        logger.info("No events found for %s / %s", sport_slug, league_name)
        return 0

    count = bulk_create_matches(sport_slug, events)
    logger.info("Synced %d matches for %s / %s", count, sport_slug, league_name)
    return count


def sync_league_standings(sport_slug: str, league_name: str, season: str = None):
    """Fetch league table and store in DB."""
    from directory.sports_db import bulk_upsert_rankings

    league_id = LEAGUE_MAP.get(sport_slug, {}).get(league_name)
    if not league_id:
        return 0

    standings = fetch_league_table(league_id, season=season)
    time.sleep(2)

    if not standings:
        return 0

    count = bulk_upsert_rankings(sport_slug, standings)
    logger.info("Synced %d standings for %s / %s", count, sport_slug, league_name)
    return count


def sync_league_teams(sport_slug: str, league_name: str):
    """Fetch all teams in a league and store in DB."""
    from directory.sports_db import bulk_create_teams

    league_id = LEAGUE_MAP.get(sport_slug, {}).get(league_name)
    if not league_id:
        return 0

    teams = fetch_league_teams(league_id)
    time.sleep(2)

    if not teams:
        return 0

    count = bulk_create_teams(sport_slug, teams)
    logger.info("Synced %d teams for %s / %s", count, sport_slug, league_name)
    return count


def sync_todays_events(sport_slug: str = None):
    """Fetch all events happening today for a sport (or all sports)."""
    from directory.sports_db import bulk_create_matches, get_sports

    today = datetime.utcnow().strftime("%Y-%m-%d")
    total = 0

    if sport_slug:
        sport_name = SPORT_NAME_MAP.get(sport_slug)
        if sport_name:
            events = fetch_events_by_day(today, sport=sport_name)
            if events:
                total += bulk_create_matches(sport_slug, events)
            time.sleep(2)
    else:
        for slug, sport_name in SPORT_NAME_MAP.items():
            events = fetch_events_by_day(today, sport=sport_name)
            if events:
                total += bulk_create_matches(slug, events)
            time.sleep(2)  # respect rate limit between sports

    logger.info("Synced %d events for today (%s)", total, today)
    return total


def sync_all_football():
    """Full sync for football: teams, matches, standings for major leagues."""
    total_matches = 0
    total_standings = 0
    total_teams = 0

    for league_name in LEAGUE_MAP.get("football", {}):
        logger.info("Syncing football / %s ...", league_name)
        total_teams += sync_league_teams("football", league_name)
        time.sleep(2)
        total_matches += sync_league_matches("football", league_name)
        time.sleep(2)
        # Standings only for league-format competitions
        if league_name not in ("Champions League",):
            total_standings += sync_league_standings("football", league_name)
            time.sleep(2)

    return {
        "teams": total_teams,
        "matches": total_matches,
        "standings": total_standings,
    }


def sync_all_sports():
    """Sync matches and standings for all configured sports/leagues."""
    results = {}
    for sport_slug, leagues in LEAGUE_MAP.items():
        sport_results = {"matches": 0, "standings": 0, "teams": 0}
        for league_name in leagues:
            sport_results["teams"] += sync_league_teams(sport_slug, league_name)
            time.sleep(2)
            sport_results["matches"] += sync_league_matches(sport_slug, league_name)
            time.sleep(2)
            sport_results["standings"] += sync_league_standings(sport_slug, league_name)
            time.sleep(2)
        results[sport_slug] = sport_results
    return results


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Ensure we can import from project root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from directory.sports_db import init_sports_tables
    init_sports_tables()

    args = sys.argv[1:]

    if "--football" in args:
        print("Syncing football data from TheSportsDB...")
        result = sync_all_football()
        print(f"Done: {result}")
    elif "--today" in args:
        print("Syncing today's events...")
        count = sync_todays_events()
        print(f"Done: {count} events synced")
    elif "--cricket" in args:
        print("Syncing cricket data...")
        for league in LEAGUE_MAP.get("cricket", {}):
            sync_league_teams("cricket", league)
            sync_league_matches("cricket", league)
        print("Done")
    elif "--all" in args:
        print("Syncing ALL sports data (this will take a few minutes due to rate limits)...")
        results = sync_all_sports()
        for sport, r in results.items():
            print(f"  {sport}: {r}")
        print("Done")
    else:
        print("Usage:")
        print("  python -m directory.sports_fetcher --football   # sync football")
        print("  python -m directory.sports_fetcher --cricket    # sync cricket")
        print("  python -m directory.sports_fetcher --today      # sync today's events")
        print("  python -m directory.sports_fetcher --all        # sync everything")
        print("\nDefaulting to --today...")
        count = sync_todays_events()
        print(f"Synced {count} events for today")
