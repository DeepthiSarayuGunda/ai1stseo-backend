#!/usr/bin/env python3
"""PostgreSQL database layer for the Sports module.

Tables:
  - sports              (sport definitions: football, cricket, hockey, etc.)
  - sports_matches      (match/game data with scores, status, dates)
  - sports_teams        (team info)
  - sports_rankings     (league standings / rankings)
  - sports_news         (news/trending items per sport)

Uses the same RDS pool pattern as the rest of the app.
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
from psycopg2 import pool

logger = logging.getLogger(__name__)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            minconn=1, maxconn=5,
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            dbname=os.environ.get("DB_NAME", "ai1stseo"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", ""),
        )
    return _pool


@contextmanager
def get_conn():
    p = _get_pool()
    conn = p.getconn()
    try:
        try:
            conn.cursor().execute("SELECT 1")
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            p.putconn(conn, close=True)
            conn = p.getconn()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


# ── Schema ────────────────────────────────────────────────────────────────────

def init_sports_tables():
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sports (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100) NOT NULL,
                slug        VARCHAR(100) UNIQUE NOT NULL,
                icon        VARCHAR(50) DEFAULT '',
                description TEXT DEFAULT '',
                is_active   BOOLEAN DEFAULT TRUE,
                sort_order  INTEGER DEFAULT 0,
                meta_json   JSONB DEFAULT '{}',
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sports_teams (
                id          SERIAL PRIMARY KEY,
                sport_id    INTEGER NOT NULL REFERENCES sports(id) ON DELETE CASCADE,
                name        VARCHAR(255) NOT NULL,
                slug        VARCHAR(255) NOT NULL,
                short_name  VARCHAR(50) DEFAULT '',
                logo_url    VARCHAR(2048) DEFAULT '',
                league      VARCHAR(255) DEFAULT '',
                country     VARCHAR(100) DEFAULT '',
                meta_json   JSONB DEFAULT '{}',
                created_at  TIMESTAMP DEFAULT NOW(),
                UNIQUE(sport_id, slug)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sports_matches (
                id              SERIAL PRIMARY KEY,
                sport_id        INTEGER NOT NULL REFERENCES sports(id) ON DELETE CASCADE,
                home_team_id    INTEGER REFERENCES sports_teams(id),
                away_team_id    INTEGER REFERENCES sports_teams(id),
                home_team_name  VARCHAR(255) NOT NULL,
                away_team_name  VARCHAR(255) NOT NULL,
                home_score      VARCHAR(20) DEFAULT '',
                away_score      VARCHAR(20) DEFAULT '',
                status          VARCHAR(50) DEFAULT 'scheduled',
                league          VARCHAR(255) DEFAULT '',
                venue           VARCHAR(500) DEFAULT '',
                match_date      TIMESTAMP NOT NULL,
                match_url       VARCHAR(2048) DEFAULT '',
                meta_json       JSONB DEFAULT '{}',
                created_at      TIMESTAMP DEFAULT NOW(),
                updated_at      TIMESTAMP DEFAULT NOW()
            )
        """)

        # Add unique constraint for deduplication on repeated syncs
        try:
            cur.execute("""
                ALTER TABLE sports_matches
                ADD CONSTRAINT uq_match_identity
                UNIQUE (sport_id, home_team_name, away_team_name, match_date)
            """)
        except Exception:
            pass  # already exists

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sports_rankings (
                id          SERIAL PRIMARY KEY,
                sport_id    INTEGER NOT NULL REFERENCES sports(id) ON DELETE CASCADE,
                league      VARCHAR(255) NOT NULL,
                team_name   VARCHAR(255) NOT NULL,
                position    INTEGER NOT NULL,
                played      INTEGER DEFAULT 0,
                won         INTEGER DEFAULT 0,
                drawn       INTEGER DEFAULT 0,
                lost        INTEGER DEFAULT 0,
                gf          INTEGER DEFAULT 0,
                ga          INTEGER DEFAULT 0,
                gd          INTEGER DEFAULT 0,
                points      INTEGER DEFAULT 0,
                meta_json   JSONB DEFAULT '{}',
                season      VARCHAR(50) DEFAULT '2025-26',
                updated_at  TIMESTAMP DEFAULT NOW(),
                UNIQUE(sport_id, league, team_name, season)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sports_news (
                id          SERIAL PRIMARY KEY,
                sport_id    INTEGER NOT NULL REFERENCES sports(id) ON DELETE CASCADE,
                title       VARCHAR(500) NOT NULL,
                summary     TEXT DEFAULT '',
                source_url  VARCHAR(2048) DEFAULT '',
                image_url   VARCHAR(2048) DEFAULT '',
                is_trending BOOLEAN DEFAULT FALSE,
                published_at TIMESTAMP DEFAULT NOW(),
                meta_json   JSONB DEFAULT '{}',
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)

        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_sp_matches_sport ON sports_matches(sport_id)",
            "CREATE INDEX IF NOT EXISTS idx_sp_matches_date ON sports_matches(match_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sp_matches_status ON sports_matches(status)",
            "CREATE INDEX IF NOT EXISTS idx_sp_rankings_sport ON sports_rankings(sport_id, league)",
            "CREATE INDEX IF NOT EXISTS idx_sp_news_sport ON sports_news(sport_id)",
            "CREATE INDEX IF NOT EXISTS idx_sp_news_trending ON sports_news(is_trending)",
            "CREATE INDEX IF NOT EXISTS idx_sp_teams_sport ON sports_teams(sport_id)",
        ]:
            try:
                cur.execute(idx)
            except Exception:
                pass

        conn.commit()
        logger.info("Sports tables initialized")


# ── Sports CRUD ───────────────────────────────────────────────────────────────

def create_sport(name, slug, icon='', description='', sort_order=0, meta_json=None):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO sports (name, slug, icon, description, sort_order, meta_json)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (slug) DO UPDATE SET
                name=EXCLUDED.name, icon=EXCLUDED.icon, description=EXCLUDED.description,
                sort_order=EXCLUDED.sort_order, meta_json=EXCLUDED.meta_json
            RETURNING *
        """, (name, slug, icon, description, sort_order, json.dumps(meta_json or {})))
        return _fmt(cur.fetchone())


def get_sports(active_only=True):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = "SELECT * FROM sports"
        if active_only:
            sql += " WHERE is_active = TRUE"
        sql += " ORDER BY sort_order, name"
        cur.execute(sql)
        return [_fmt(r) for r in cur.fetchall()]


def get_sport_by_slug(slug):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM sports WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return _fmt(row) if row else None


# ── Teams ─────────────────────────────────────────────────────────────────────

def create_team(sport_slug, data):
    sport = get_sport_by_slug(sport_slug)
    if not sport:
        return None
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO sports_teams (sport_id, name, slug, short_name, logo_url, league, country, meta_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sport_id, slug) DO UPDATE SET
                name=EXCLUDED.name, short_name=EXCLUDED.short_name, logo_url=EXCLUDED.logo_url,
                league=EXCLUDED.league, country=EXCLUDED.country, meta_json=EXCLUDED.meta_json
            RETURNING *
        """, (sport['id'], data['name'], data.get('slug', _slugify(data['name'])),
              data.get('short_name', ''), data.get('logo_url', ''),
              data.get('league', ''), data.get('country', ''),
              json.dumps(data.get('meta_json', {}))))
        return _fmt(cur.fetchone())


def get_teams(sport_slug, league=None, limit=50):
    sport = get_sport_by_slug(sport_slug)
    if not sport:
        return []
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if league:
            cur.execute(
                "SELECT * FROM sports_teams WHERE sport_id=%s AND league=%s ORDER BY name LIMIT %s",
                (sport['id'], league, limit))
        else:
            cur.execute(
                "SELECT * FROM sports_teams WHERE sport_id=%s ORDER BY name LIMIT %s",
                (sport['id'], limit))
        return [_fmt(r) for r in cur.fetchall()]


def bulk_create_teams(sport_slug, teams_list):
    count = 0
    for t in teams_list:
        if create_team(sport_slug, t):
            count += 1
    return count


# ── Matches ───────────────────────────────────────────────────────────────────

def create_match(sport_slug, data):
    sport = get_sport_by_slug(sport_slug)
    if not sport:
        return None
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO sports_matches
                (sport_id, home_team_name, away_team_name, home_score, away_score,
                 status, league, venue, match_date, match_url, meta_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sport_id, home_team_name, away_team_name, match_date)
            DO UPDATE SET
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                status     = EXCLUDED.status,
                venue      = COALESCE(NULLIF(EXCLUDED.venue, ''), sports_matches.venue),
                meta_json  = EXCLUDED.meta_json,
                updated_at = NOW()
            RETURNING *
        """, (
            sport['id'], data['home_team'], data['away_team'],
            data.get('home_score', ''), data.get('away_score', ''),
            data.get('status', 'scheduled'), data.get('league', ''),
            data.get('venue', ''), data['match_date'],
            data.get('match_url', ''), json.dumps(data.get('meta_json', {}))
        ))
        return _fmt(cur.fetchone())


def get_matches(sport_slug, status=None, league=None, limit=20, offset=0):
    """Get matches for a sport. status: live, final, scheduled, all."""
    sport = get_sport_by_slug(sport_slug)
    if not sport:
        return {'matches': [], 'total': 0}

    where = ["m.sport_id = %s"]
    params = [sport['id']]

    if status and status != 'all':
        where.append("m.status = %s")
        params.append(status)
    if league:
        where.append("m.league = %s")
        params.append(league)

    where_sql = " AND ".join(where)

    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT COUNT(*) as cnt FROM sports_matches m WHERE {where_sql}", params)
        total = cur.fetchone()['cnt']

        # Live matches first, then by date descending
        cur.execute(f"""
            SELECT m.* FROM sports_matches m
            WHERE {where_sql}
            ORDER BY
                CASE m.status WHEN 'live' THEN 0 WHEN 'scheduled' THEN 1 ELSE 2 END,
                m.match_date DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        matches = [_fmt_match(r) for r in cur.fetchall()]

    return {'matches': matches, 'total': total}


def update_match(match_id, updates):
    allowed = {'home_score', 'away_score', 'status', 'venue', 'match_url', 'meta_json'}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return None
    if 'meta_json' in fields:
        fields['meta_json'] = json.dumps(fields['meta_json'])
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    set_clause += ", updated_at = NOW()"
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            f"UPDATE sports_matches SET {set_clause} WHERE id = %s RETURNING *",
            list(fields.values()) + [match_id]
        )
        row = cur.fetchone()
        return _fmt_match(row) if row else None


def bulk_create_matches(sport_slug, matches_list):
    created = 0
    for m in matches_list:
        if create_match(sport_slug, m):
            created += 1
    return created


# ── Rankings ──────────────────────────────────────────────────────────────────

def upsert_ranking(sport_slug, data):
    sport = get_sport_by_slug(sport_slug)
    if not sport:
        return None
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO sports_rankings
                (sport_id, league, team_name, position, played, won, drawn, lost,
                 gf, ga, gd, points, season, meta_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sport_id, league, team_name, season) DO UPDATE SET
                position=EXCLUDED.position, played=EXCLUDED.played, won=EXCLUDED.won,
                drawn=EXCLUDED.drawn, lost=EXCLUDED.lost, gf=EXCLUDED.gf, ga=EXCLUDED.ga,
                gd=EXCLUDED.gd, points=EXCLUDED.points, meta_json=EXCLUDED.meta_json,
                updated_at=NOW()
            RETURNING *
        """, (
            sport['id'], data['league'], data['team_name'], data['position'],
            data.get('played', 0), data.get('won', 0), data.get('drawn', 0),
            data.get('lost', 0), data.get('gf', 0), data.get('ga', 0),
            data.get('gd', 0), data.get('points', 0),
            data.get('season', '2025-26'), json.dumps(data.get('meta_json', {}))
        ))
        return _fmt(cur.fetchone())


def get_rankings(sport_slug, league, season='2025-26', limit=30):
    sport = get_sport_by_slug(sport_slug)
    if not sport:
        return []
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM sports_rankings
            WHERE sport_id = %s AND league = %s AND season = %s
            ORDER BY position ASC
            LIMIT %s
        """, (sport['id'], league, season, limit))
        return [_fmt(r) for r in cur.fetchall()]


def bulk_upsert_rankings(sport_slug, rankings_list):
    count = 0
    for r in rankings_list:
        if upsert_ranking(sport_slug, r):
            count += 1
    return count


# ── News ──────────────────────────────────────────────────────────────────────

def create_news(sport_slug, data):
    sport = get_sport_by_slug(sport_slug)
    if not sport:
        return None
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO sports_news
                (sport_id, title, summary, source_url, image_url, is_trending, published_at, meta_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *
        """, (
            sport['id'], data['title'], data.get('summary', ''),
            data.get('source_url', ''), data.get('image_url', ''),
            data.get('is_trending', False),
            data.get('published_at', datetime.utcnow().isoformat()),
            json.dumps(data.get('meta_json', {}))
        ))
        return _fmt(cur.fetchone())


def get_news(sport_slug=None, trending_only=False, limit=20):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where = []
        params = []
        if sport_slug:
            sport = get_sport_by_slug(sport_slug)
            if not sport:
                return []
            where.append("n.sport_id = %s")
            params.append(sport['id'])
        if trending_only:
            where.append("n.is_trending = TRUE")

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        cur.execute(f"""
            SELECT n.*, s.slug as sport_slug, s.name as sport_name
            FROM sports_news n
            JOIN sports s ON s.id = n.sport_id
            {where_sql}
            ORDER BY n.published_at DESC
            LIMIT %s
        """, params + [limit])
        return [_fmt(r) for r in cur.fetchall()]


def bulk_create_news(sport_slug, news_list):
    count = 0
    for n in news_list:
        if create_news(sport_slug, n):
            count += 1
    return count


# ── Explore categories (sub-sports) ──────────────────────────────────────────

def get_explore_categories():
    """Return all sports as explore cards for the 'Explore More' section."""
    return get_sports(active_only=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text):
    import re
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _fmt(row):
    if not row:
        return {}
    d = dict(row)
    for k in ('created_at', 'updated_at', 'published_at'):
        if d.get(k):
            d[k] = d[k].isoformat()
    if d.get('meta_json') and isinstance(d['meta_json'], str):
        try:
            d['meta_json'] = json.loads(d['meta_json'])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


def _fmt_match(row):
    if not row:
        return {}
    d = _fmt(row)
    if d.get('match_date'):
        d['match_date'] = d['match_date'] if isinstance(d['match_date'], str) else d['match_date'].isoformat()
    return d
