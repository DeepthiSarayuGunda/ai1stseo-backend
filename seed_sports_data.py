#!/usr/bin/env python3
"""Seed the Sports module with real data — sports, teams, matches, rankings, news.

Run: python seed_sports_data.py

Seeds data matching the live ai1stseo.com/directory-sport.html page:
  - 15+ sport categories (Football, Cricket, Hockey, Basketball, etc.)
  - Teams for Premier League, Champions League
  - Recent/upcoming matches with real scores
  - Premier League standings
  - Trending news items
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from directory.sports_db import (
    init_sports_tables, create_sport, bulk_create_teams,
    bulk_create_matches, bulk_upsert_rankings, bulk_create_news
)

print("Initializing sports tables...")
init_sports_tables()

# ── Sport categories (matching the Explore More grid) ─────────────────────────

SPORTS = [
    ("Football", "football", "football", "The world's most popular sport with 4 billion fans. From the FIFA World Cup to the English Premier League, football unites the globe.", 1),
    ("Cricket", "cricket", "cricket", "Bat-and-ball sport popular in South Asia, UK, and Australia. Formats include Test, ODI, and T20.", 2),
    ("Basketball", "basketball", "basketball", "Fast-paced court sport. NBA is the premier league globally.", 3),
    ("Tennis", "tennis", "tennis", "Individual racquet sport with Grand Slam tournaments: Australian Open, French Open, Wimbledon, US Open.", 4),
    ("Baseball", "baseball", "baseball", "America's pastime. MLB features 30 teams with a 162-game regular season.", 5),
    ("Ice Hockey", "ice-hockey", "hockey", "Fast contact sport on ice. NHL is the top professional league.", 6),
    ("Golf", "golf", "golf", "Precision club-and-ball sport. Major championships: Masters, US Open, The Open, PGA.", 7),
    ("Rugby", "rugby", "rugby", "Contact team sport with Rugby Union and Rugby League variants.", 8),
    ("Boxing", "boxing", "boxing", "Combat sport with professional and amateur divisions across weight classes.", 9),
    ("Formula 1", "formula-1", "racing", "Pinnacle of motorsport. 10 teams, 20 drivers, races on circuits worldwide.", 10),
    ("Cycling", "cycling", "cycling", "Road and track cycling. Tour de France is the most prestigious race.", 11),
    ("Swimming", "swimming", "swimming", "Aquatic sport with freestyle, backstroke, breaststroke, and butterfly events.", 12),
    ("Athletics", "athletics", "athletics", "Track and field events including sprints, marathons, jumps, and throws.", 13),
    ("Volleyball", "volleyball", "volleyball", "Team sport played indoor and on beach. Popular worldwide.", 14),
    ("Esports", "esports", "esports", "Competitive video gaming across titles like League of Legends, CS2, Valorant, and Dota 2.", 15),
]

print("\nSeeding sports categories...")
for name, slug, icon, desc, order in SPORTS:
    create_sport(name, slug, icon, desc, order)
    print(f"  + {name}")

# ── Football teams ────────────────────────────────────────────────────────────

PL_TEAMS = [
    {"name": "Manchester City", "slug": "man-city", "short_name": "MCI", "league": "Premier League", "country": "England"},
    {"name": "Arsenal", "slug": "arsenal", "short_name": "ARS", "league": "Premier League", "country": "England"},
    {"name": "Liverpool", "slug": "liverpool", "short_name": "LIV", "league": "Premier League", "country": "England"},
    {"name": "Chelsea", "slug": "chelsea", "short_name": "CHE", "league": "Premier League", "country": "England"},
    {"name": "Manchester United", "slug": "man-united", "short_name": "MUN", "league": "Premier League", "country": "England"},
    {"name": "Tottenham Hotspur", "slug": "tottenham", "short_name": "TOT", "league": "Premier League", "country": "England"},
    {"name": "Newcastle United", "slug": "newcastle", "short_name": "NEW", "league": "Premier League", "country": "England"},
    {"name": "Aston Villa", "slug": "aston-villa", "short_name": "AVL", "league": "Premier League", "country": "England"},
    {"name": "Brighton", "slug": "brighton", "short_name": "BHA", "league": "Premier League", "country": "England"},
    {"name": "West Ham United", "slug": "west-ham", "short_name": "WHU", "league": "Premier League", "country": "England"},
    {"name": "Real Madrid", "slug": "real-madrid", "short_name": "RMA", "league": "Champions League", "country": "Spain"},
    {"name": "Bayern Munich", "slug": "bayern-munich", "short_name": "BAY", "league": "Champions League", "country": "Germany"},
    {"name": "Barcelona", "slug": "barcelona", "short_name": "BAR", "league": "Champions League", "country": "Spain"},
    {"name": "PSG", "slug": "psg", "short_name": "PSG", "league": "Champions League", "country": "France"},
    {"name": "Inter Milan", "slug": "inter-milan", "short_name": "INT", "league": "Serie A", "country": "Italy"},
    {"name": "Juventus", "slug": "juventus", "short_name": "JUV", "league": "Serie A", "country": "Italy"},
    {"name": "Brazil", "slug": "brazil", "short_name": "BRA", "league": "World Cup Qualifier", "country": "Brazil"},
    {"name": "Argentina", "slug": "argentina", "short_name": "ARG", "league": "World Cup Qualifier", "country": "Argentina"},
]

print("\nSeeding football teams...")
count = bulk_create_teams("football", PL_TEAMS)
print(f"  + {count} teams created")


# ── Matches (matching the screenshot) ─────────────────────────────────────────

MATCHES = [
    # Premier League
    {"home_team": "Manchester City", "away_team": "Arsenal", "home_score": "0", "away_score": "0",
     "status": "scheduled", "league": "Premier League", "match_date": "2026-04-18T15:00:00",
     "meta_json": {"round": 34, "broadcast": "Sky Sports"}},

    {"home_team": "Liverpool", "away_team": "Chelsea", "home_score": "2", "away_score": "0",
     "status": "final", "league": "Premier League", "match_date": "2026-04-12T17:30:00",
     "meta_json": {"round": 33, "broadcast": "TNT Sports"}},

    # Champions League
    {"home_team": "Real Madrid", "away_team": "Bayern Munich", "home_score": "2", "away_score": "1",
     "status": "live", "league": "Champions League", "match_date": "2026-04-27T20:00:00",
     "meta_json": {"stage": "Semi-final", "leg": "1st leg"}},

    {"home_team": "Barcelona", "away_team": "PSG", "home_score": "3", "away_score": "2",
     "status": "final", "league": "Champions League", "match_date": "2026-04-22T20:00:00",
     "meta_json": {"stage": "Quarter-final", "leg": "2nd leg"}},

    # Serie A
    {"home_team": "Inter Milan", "away_team": "Juventus", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "Serie A", "match_date": "2026-04-19T19:45:00",
     "meta_json": {"round": 33}},

    # World Cup Qualifier
    {"home_team": "Brazil", "away_team": "Argentina", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "World Cup Qualifier", "match_date": "2026-04-12T21:00:00",
     "meta_json": {"stage": "CONMEBOL Qualifier"}},

    # More Premier League
    {"home_team": "Newcastle United", "away_team": "Aston Villa", "home_score": "1", "away_score": "1",
     "status": "final", "league": "Premier League", "match_date": "2026-04-13T14:00:00",
     "meta_json": {"round": 33}},

    {"home_team": "Tottenham Hotspur", "away_team": "Brighton", "home_score": "3", "away_score": "1",
     "status": "final", "league": "Premier League", "match_date": "2026-04-13T16:30:00",
     "meta_json": {"round": 33}},

    {"home_team": "West Ham United", "away_team": "Manchester United", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "Premier League", "match_date": "2026-04-20T14:00:00",
     "meta_json": {"round": 34}},

    {"home_team": "Arsenal", "away_team": "Liverpool", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "Premier League", "match_date": "2026-04-26T17:30:00",
     "meta_json": {"round": 35}},
]

print("\nSeeding football matches...")
count = bulk_create_matches("football", MATCHES)
print(f"  + {count} matches created")

# ── Premier League standings ──────────────────────────────────────────────────

PL_RANKINGS = [
    {"league": "Premier League", "team_name": "Liverpool", "position": 1, "played": 33, "won": 24, "drawn": 6, "lost": 3, "gf": 72, "ga": 28, "gd": 44, "points": 78},
    {"league": "Premier League", "team_name": "Arsenal", "position": 2, "played": 33, "won": 23, "drawn": 5, "lost": 5, "gf": 68, "ga": 25, "gd": 43, "points": 74},
    {"league": "Premier League", "team_name": "Manchester City", "position": 3, "played": 33, "won": 21, "drawn": 6, "lost": 6, "gf": 65, "ga": 30, "gd": 35, "points": 69},
    {"league": "Premier League", "team_name": "Chelsea", "position": 4, "played": 33, "won": 19, "drawn": 7, "lost": 7, "gf": 58, "ga": 35, "gd": 23, "points": 64},
    {"league": "Premier League", "team_name": "Newcastle United", "position": 5, "played": 33, "won": 18, "drawn": 6, "lost": 9, "gf": 55, "ga": 38, "gd": 17, "points": 60},
    {"league": "Premier League", "team_name": "Aston Villa", "position": 6, "played": 33, "won": 17, "drawn": 7, "lost": 9, "gf": 52, "ga": 40, "gd": 12, "points": 58},
    {"league": "Premier League", "team_name": "Tottenham Hotspur", "position": 7, "played": 33, "won": 16, "drawn": 5, "lost": 12, "gf": 60, "ga": 50, "gd": 10, "points": 53},
    {"league": "Premier League", "team_name": "Brighton", "position": 8, "played": 33, "won": 14, "drawn": 9, "lost": 10, "gf": 50, "ga": 42, "gd": 8, "points": 51},
    {"league": "Premier League", "team_name": "Manchester United", "position": 9, "played": 33, "won": 13, "drawn": 6, "lost": 14, "gf": 42, "ga": 48, "gd": -6, "points": 45},
    {"league": "Premier League", "team_name": "West Ham United", "position": 10, "played": 33, "won": 12, "drawn": 7, "lost": 14, "gf": 45, "ga": 52, "gd": -7, "points": 43},
]

print("\nSeeding Premier League rankings...")
count = bulk_upsert_rankings("football", PL_RANKINGS)
print(f"  + {count} rankings upserted")


# ── News items ────────────────────────────────────────────────────────────────

NEWS = [
    # Football
    {"title": "Champions League semi-final draw: Real Madrid vs Bayern Munich confirmed",
     "summary": "The Champions League semi-final first leg kicks off April 27 with Real Madrid hosting Bayern Munich at the Bernabeu.",
     "source_url": "https://www.uefa.com/uefachampionsleague/", "is_trending": True,
     "published_at": "2026-04-25T10:00:00"},

    {"title": "Premier League title race: Liverpool lead Arsenal by 4 points with 5 games left",
     "summary": "Liverpool maintain their grip on the Premier League title after a 2-0 win over Chelsea at Anfield.",
     "source_url": "https://www.premierleague.com/", "is_trending": True,
     "published_at": "2026-04-24T14:00:00"},

    {"title": "FIFA World Cup 2026 qualifying: Brazil vs Argentina preview",
     "summary": "South American rivals meet in a crucial World Cup qualifier. Both teams need points to secure automatic qualification.",
     "source_url": "https://www.fifa.com/", "is_trending": True,
     "published_at": "2026-04-23T09:00:00"},

    {"title": "Transfer Window Tracker: Latest signings and rumours",
     "summary": "Summer transfer window approaches. Top targets include midfield reinforcements for Manchester City and a striker for Chelsea.",
     "source_url": "https://www.transfermarkt.com/", "is_trending": False,
     "published_at": "2026-04-22T16:00:00"},

    {"title": "Fantasy Premier League: GW34 tips and captain picks",
     "summary": "FPL managers face tough decisions with double gameweek players and differential picks for the run-in.",
     "source_url": "https://fantasy.premierleague.com/", "is_trending": False,
     "published_at": "2026-04-21T11:00:00"},
]

print("\nSeeding football news...")
count = bulk_create_news("football", NEWS)
print(f"  + {count} news items created")

# ── Cricket matches & news ────────────────────────────────────────────────────

CRICKET_TEAMS = [
    {"name": "India", "slug": "india", "short_name": "IND", "league": "ICC", "country": "India"},
    {"name": "Australia", "slug": "australia", "short_name": "AUS", "league": "ICC", "country": "Australia"},
    {"name": "England", "slug": "england-cricket", "short_name": "ENG", "league": "ICC", "country": "England"},
    {"name": "Mumbai Indians", "slug": "mumbai-indians", "short_name": "MI", "league": "IPL", "country": "India"},
    {"name": "Chennai Super Kings", "slug": "csk", "short_name": "CSK", "league": "IPL", "country": "India"},
    {"name": "Royal Challengers Bengaluru", "slug": "rcb", "short_name": "RCB", "league": "IPL", "country": "India"},
]

print("\nSeeding cricket teams...")
count = bulk_create_teams("cricket", CRICKET_TEAMS)
print(f"  + {count} cricket teams created")

CRICKET_MATCHES = [
    {"home_team": "Mumbai Indians", "away_team": "Chennai Super Kings", "home_score": "185/4", "away_score": "178/8",
     "status": "final", "league": "IPL 2026", "match_date": "2026-04-25T19:30:00",
     "meta_json": {"format": "T20", "venue": "Wankhede Stadium"}},
    {"home_team": "India", "away_team": "Australia", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "ICC Test Series", "match_date": "2026-05-10T10:00:00",
     "meta_json": {"format": "Test", "venue": "MCG"}},
    {"home_team": "Royal Challengers Bengaluru", "away_team": "Mumbai Indians", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "IPL 2026", "match_date": "2026-04-28T19:30:00",
     "meta_json": {"format": "T20", "venue": "M. Chinnaswamy Stadium"}},
]

count = bulk_create_matches("cricket", CRICKET_MATCHES)
print(f"  + {count} cricket matches created")

CRICKET_NEWS = [
    {"title": "IPL 2026: Mumbai Indians edge past CSK in thriller",
     "summary": "MI defended 185 to beat CSK by 7 runs at Wankhede. Rohit Sharma scored a crucial 67 off 42 balls.",
     "source_url": "https://www.iplt20.com/", "is_trending": True,
     "published_at": "2026-04-25T23:00:00"},
]
count = bulk_create_news("cricket", CRICKET_NEWS)
print(f"  + {count} cricket news created")

# ── Basketball ────────────────────────────────────────────────────────────────

BASKETBALL_TEAMS = [
    {"name": "Boston Celtics", "slug": "celtics", "short_name": "BOS", "league": "NBA", "country": "USA"},
    {"name": "Denver Nuggets", "slug": "nuggets", "short_name": "DEN", "league": "NBA", "country": "USA"},
    {"name": "Oklahoma City Thunder", "slug": "thunder", "short_name": "OKC", "league": "NBA", "country": "USA"},
    {"name": "Milwaukee Bucks", "slug": "bucks", "short_name": "MIL", "league": "NBA", "country": "USA"},
]

print("\nSeeding basketball teams...")
count = bulk_create_teams("basketball", BASKETBALL_TEAMS)
print(f"  + {count} basketball teams created")

NBA_MATCHES = [
    {"home_team": "Boston Celtics", "away_team": "Milwaukee Bucks", "home_score": "112", "away_score": "105",
     "status": "final", "league": "NBA Playoffs", "match_date": "2026-04-22T19:30:00",
     "meta_json": {"series": "Eastern Conference R1", "game": 2}},
    {"home_team": "Denver Nuggets", "away_team": "Oklahoma City Thunder", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "NBA Playoffs", "match_date": "2026-04-28T21:00:00",
     "meta_json": {"series": "Western Conference R1", "game": 3}},
]
count = bulk_create_matches("basketball", NBA_MATCHES)
print(f"  + {count} NBA matches created")

# ── Ice Hockey ────────────────────────────────────────────────────────────────

HOCKEY_TEAMS = [
    {"name": "Edmonton Oilers", "slug": "oilers", "short_name": "EDM", "league": "NHL", "country": "Canada"},
    {"name": "Florida Panthers", "slug": "panthers", "short_name": "FLA", "league": "NHL", "country": "USA"},
    {"name": "Toronto Maple Leafs", "slug": "maple-leafs", "short_name": "TOR", "league": "NHL", "country": "Canada"},
    {"name": "Dallas Stars", "slug": "stars", "short_name": "DAL", "league": "NHL", "country": "USA"},
]

print("\nSeeding ice hockey teams...")
count = bulk_create_teams("ice-hockey", HOCKEY_TEAMS)
print(f"  + {count} hockey teams created")

NHL_MATCHES = [
    {"home_team": "Edmonton Oilers", "away_team": "Dallas Stars", "home_score": "4", "away_score": "2",
     "status": "final", "league": "NHL Playoffs", "match_date": "2026-04-24T20:00:00",
     "meta_json": {"series": "Western Conference R1", "game": 1}},
    {"home_team": "Florida Panthers", "away_team": "Toronto Maple Leafs", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "NHL Playoffs", "match_date": "2026-04-29T19:00:00",
     "meta_json": {"series": "Eastern Conference R1", "game": 2}},
]
count = bulk_create_matches("ice-hockey", NHL_MATCHES)
print(f"  + {count} NHL matches created")

# ── Formula 1 ─────────────────────────────────────────────────────────────────

F1_MATCHES = [
    {"home_team": "Max Verstappen", "away_team": "Field", "home_score": "P1", "away_score": "",
     "status": "final", "league": "F1 2026", "match_date": "2026-04-20T14:00:00",
     "meta_json": {"race": "Emilia Romagna GP", "circuit": "Imola", "laps": 63}},
    {"home_team": "Grid", "away_team": "Field", "home_score": "", "away_score": "",
     "status": "scheduled", "league": "F1 2026", "match_date": "2026-05-04T15:00:00",
     "meta_json": {"race": "Miami GP", "circuit": "Miami International Autodrome"}},
]
count = bulk_create_matches("formula-1", F1_MATCHES)
print(f"\n  + {count} F1 races created")

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\n[OK] Done seeding sports data:")
print(f"  - {len(SPORTS)} sport categories")
print(f"  - {len(PL_TEAMS) + len(CRICKET_TEAMS) + len(BASKETBALL_TEAMS) + len(HOCKEY_TEAMS)} teams")
print(f"  - {len(MATCHES) + len(CRICKET_MATCHES) + len(NBA_MATCHES) + len(NHL_MATCHES) + len(F1_MATCHES)} matches")
print(f"  - {len(PL_RANKINGS)} Premier League rankings")
print(f"  - {len(NEWS) + len(CRICKET_NEWS)} news items")
