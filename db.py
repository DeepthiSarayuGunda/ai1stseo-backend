"""
db.py
RDS PostgreSQL connection pool for the AEO platform.

Matches Troy's DATABASE_SCHEMA.md — uses UUID PKs, project_id for
multi-tenancy, and the exact column names from the shared schema.

Environment variables (matching Lambda config):
  DB_HOST     - RDS endpoint
  DB_PORT     - default 5432
  DB_NAME     - database name (default: ai1stseo)
  DB_USER     - database user
  DB_PASSWORD - database password
"""

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from psycopg2 import pool

logger = logging.getLogger(__name__)

_pool = None

# Default project_id — used until multi-tenancy auth is wired up
DEFAULT_PROJECT_ID = os.environ.get("DEFAULT_PROJECT_ID", "00000000-0000-0000-0000-000000000001")


def _get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.environ.get("DB_HOST", "localhost"),
                port=int(os.environ.get("DB_PORT", "5432")),
                dbname=os.environ.get("DB_NAME", "ai1stseo"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", ""),
            )
            logger.info("RDS pool created: %s/%s", os.environ.get("DB_HOST"), os.environ.get("DB_NAME"))
        except Exception as e:
            logger.error("Failed to create RDS pool: %s", e)
            raise RuntimeError(f"Database connection failed: {e}")
    return _pool


@contextmanager
def get_conn():
    """Check out a connection from the pool, auto-commit/rollback."""
    p = _get_pool()
    conn = p.getconn()
    try:
        # Test if connection is still alive
        try:
            conn.cursor().execute("SELECT 1")
        except Exception:
            # Connection is stale — close and get a fresh one
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


# ── Schema init (idempotent) ──────────────────────────────────────────────────

def init_db():
    """Ensure Troy's tables exist. Uses CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS."""
    with get_conn() as conn:
        cur = conn.cursor()

        # Ensure default project exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                owner_email VARCHAR(255) NOT NULL,
                plan VARCHAR(50) DEFAULT 'free',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            INSERT INTO projects (id, name, owner_email)
            VALUES (%s, 'Default Project', 'admin@ai1stseo.com')
            ON CONFLICT (id) DO NOTHING
        """, (DEFAULT_PROJECT_ID,))

        # geo_probes — matches DATABASE_SCHEMA.md exactly
        cur.execute("""
            CREATE TABLE IF NOT EXISTS geo_probes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL DEFAULT %s,
                url VARCHAR(2048),
                brand_name VARCHAR(255),
                keyword VARCHAR(500) NOT NULL,
                ai_model VARCHAR(100) NOT NULL,
                cited BOOLEAN DEFAULT FALSE,
                citation_context TEXT,
                response_snippet TEXT,
                citation_rank INTEGER,
                sentiment VARCHAR(20),
                ai_platform VARCHAR(50),
                query_text TEXT,
                confidence REAL DEFAULT 0.0,
                probe_timestamp TIMESTAMP DEFAULT NOW()
            )
        """, (DEFAULT_PROJECT_ID,))

        # ai_visibility_history — matches DATABASE_SCHEMA.md
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_visibility_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL DEFAULT %s,
                url VARCHAR(2048),
                visibility_score INTEGER,
                citation_count INTEGER DEFAULT 0,
                extractable_answers INTEGER DEFAULT 0,
                factual_density_score NUMERIC(5,2),
                schema_coverage_score NUMERIC(5,2),
                share_of_voice NUMERIC(5,2),
                competitor_citations INTEGER DEFAULT 0,
                ai_referral_sessions INTEGER DEFAULT 0,
                citation_sentiment_positive INTEGER DEFAULT 0,
                citation_sentiment_neutral INTEGER DEFAULT 0,
                citation_sentiment_negative INTEGER DEFAULT 0,
                brand_name VARCHAR(255),
                ai_model VARCHAR(100),
                keyword TEXT,
                geo_score REAL DEFAULT 0.0,
                cited_count INTEGER DEFAULT 0,
                total_prompts INTEGER DEFAULT 0,
                batch_results JSONB,
                measured_at TIMESTAMP DEFAULT NOW()
            )
        """, (DEFAULT_PROJECT_ID,))

        # Add columns that may be missing on existing tables (safe migration)
        _safe_add_columns(cur, "geo_probes", {
            "confidence": "REAL DEFAULT 0.0",
            "response_snippet": "TEXT",
            "citation_rank": "INTEGER",
            "sentiment": "VARCHAR(20)",
            "ai_platform": "VARCHAR(50)",
            "query_text": "TEXT",
        })
        _safe_add_columns(cur, "ai_visibility_history", {
            "brand_name": "VARCHAR(255)",
            "ai_model": "VARCHAR(100)",
            "keyword": "TEXT",
            "geo_score": "REAL DEFAULT 0.0",
            "cited_count": "INTEGER DEFAULT 0",
            "total_prompts": "INTEGER DEFAULT 0",
            "batch_results": "JSONB",
        })

        # Indexes
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_geo_project ON geo_probes(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_geo_keyword ON geo_probes(keyword)",
            "CREATE INDEX IF NOT EXISTS idx_geo_timestamp ON geo_probes(probe_timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_aiviz_project ON ai_visibility_history(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_aiviz_measured ON ai_visibility_history(measured_at DESC)",
        ]:
            try:
                cur.execute(idx)
            except Exception:
                pass

        conn.commit()
        logger.info("RDS tables verified (geo_probes, ai_visibility_history)")


def _safe_add_columns(cur, table, columns):
    """Add columns if they don't exist, using savepoints to avoid transaction abort."""
    for col, coldef in columns.items():
        try:
            cur.execute(f"SAVEPOINT sp_{col}")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coldef}")
            cur.execute(f"RELEASE SAVEPOINT sp_{col}")
        except Exception:
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_{col}")


# ── geo_probes CRUD ───────────────────────────────────────────────────────────

def insert_probe(keyword: str, brand: str, ai_model: str, cited: bool,
                 citation_context: str = None, confidence: float = 0.0,
                 site_url: str = None, response_snippet: str = None,
                 sentiment: str = None, query_text: str = None,
                 project_id: str = None) -> str:
    """Insert a probe result. Returns the new row UUID."""
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor()
        row_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO geo_probes
                (id, project_id, keyword, brand_name, ai_model, cited,
                 citation_context, confidence, url, response_snippet,
                 sentiment, ai_platform, query_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (row_id, pid, keyword, brand, ai_model, cited,
              citation_context, confidence, site_url, response_snippet,
              sentiment, ai_model, query_text))
        return row_id


def get_probes(limit: int = 50, brand: str = None, ai_model: str = None,
               project_id: str = None) -> list[dict]:
    """Fetch probe results with optional filters."""
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        clauses = ["project_id = %s"]
        params = [pid]
        if brand:
            clauses.append("brand_name = %s")
            params.append(brand)
        if ai_model:
            clauses.append("ai_model = %s")
            params.append(ai_model)
        where = "WHERE " + " AND ".join(clauses)
        params.append(limit)
        cur.execute(f"SELECT * FROM geo_probes {where} ORDER BY probe_timestamp DESC LIMIT %s", params)
        rows = cur.fetchall()
        for r in rows:
            # Serialize for JSON
            for k in ("id", "project_id"):
                if r.get(k):
                    r[k] = str(r[k])
            if r.get("probe_timestamp"):
                r["probe_timestamp"] = r["probe_timestamp"].isoformat()
            # Normalize for frontend compat
            r["brand"] = r.get("brand_name", "")
            r["created_at"] = r.get("probe_timestamp", "")
        return rows


def get_probe_trend(brand: str, limit: int = 30, project_id: str = None) -> list[dict]:
    """Daily aggregated visibility trend for a brand."""
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT DATE(probe_timestamp) AS date,
                   COUNT(*) AS total,
                   SUM(CASE WHEN cited THEN 1 ELSE 0 END) AS cited,
                   ROUND(SUM(CASE WHEN cited THEN 1 ELSE 0 END)::numeric
                         / NULLIF(COUNT(*), 0), 2) AS geo_score,
                   ARRAY_AGG(DISTINCT ai_model) AS providers
            FROM geo_probes
            WHERE project_id = %s AND brand_name = %s
            GROUP BY DATE(probe_timestamp)
            ORDER BY DATE(probe_timestamp) DESC
            LIMIT %s
        """, (pid, brand, limit))
        rows = cur.fetchall()
        for r in rows:
            r["date"] = r["date"].isoformat() if r.get("date") else None
            r["providers"] = list(r["providers"]) if r.get("providers") else []
            # Ensure geo_score is a float for JSON serialization
            if r.get("geo_score") is not None:
                r["geo_score"] = float(r["geo_score"])
        return rows


# ── ai_visibility_history CRUD ────────────────────────────────────────────────

def insert_visibility_batch(brand: str, ai_model: str, keyword: str,
                            geo_score: float, cited_count: int,
                            total_prompts: int, batch_results: dict = None,
                            project_id: str = None) -> str:
    """Insert a batch visibility result. Returns the new row UUID."""
    pid = project_id or DEFAULT_PROJECT_ID
    vis_score = round(geo_score * 100) if geo_score else 0
    with get_conn() as conn:
        cur = conn.cursor()
        row_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO ai_visibility_history
                (id, project_id, brand_name, ai_model, keyword,
                 visibility_score, citation_count, geo_score,
                 cited_count, total_prompts, batch_results)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (row_id, pid, brand, ai_model, keyword,
              vis_score, cited_count, geo_score,
              cited_count, total_prompts,
              json.dumps(batch_results) if batch_results else None))
        return row_id


def get_visibility_history(limit: int = 20, brand: str = None,
                           project_id: str = None) -> list[dict]:
    """Fetch batch visibility history."""
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if brand:
            cur.execute("""
                SELECT * FROM ai_visibility_history
                WHERE project_id = %s AND brand_name = %s
                ORDER BY measured_at DESC LIMIT %s
            """, (pid, brand, limit))
        else:
            cur.execute("""
                SELECT * FROM ai_visibility_history
                WHERE project_id = %s
                ORDER BY measured_at DESC LIMIT %s
            """, (pid, limit))
        rows = cur.fetchall()
        for r in rows:
            for k in ("id", "project_id"):
                if r.get(k):
                    r[k] = str(r[k])
            if r.get("measured_at"):
                r["measured_at"] = r["measured_at"].isoformat()
            r["created_at"] = r.get("measured_at", "")
            r["brand"] = r.get("brand_name", "")
        return rows


# ── content_briefs CRUD ───────────────────────────────────────────────────────

def save_content_brief(keyword: str, content_type: str, brief_json: dict,
                       serp_competitors: list = None, keywords: list = None,
                       target_word_count: int = None, ai_generated: bool = True,
                       project_id: str = None) -> str:
    """Save a content brief and its related competitors/keywords. Returns brief ID."""
    pid = project_id or DEFAULT_PROJECT_ID
    brief_id = str(uuid.uuid4())

    with get_conn() as conn:
        cur = conn.cursor()

        # Insert main brief
        cur.execute("""
            INSERT INTO content_briefs (id, project_id, keyword, content_type,
                target_word_count, brief_json, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            brief_id, pid, keyword, content_type,
            target_word_count or brief_json.get('target_word_count'),
            json.dumps(brief_json),
            'generated' if ai_generated else 'draft'
        ))

        # Insert competitors
        if serp_competitors:
            for comp in serp_competitors:
                cur.execute("""
                    INSERT INTO brief_competitors (id, brief_id, url, domain, title,
                        word_count, heading_structure)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()), brief_id,
                    comp.get('url', ''),
                    comp.get('url', '').split('/')[2] if '/' in comp.get('url', '') else '',
                    comp.get('title', ''),
                    comp.get('word_count', 0),
                    json.dumps({'headings_count': comp.get('headings_count', 0)})
                ))

        # Insert keywords
        if keywords:
            for kw in keywords:
                cur.execute("""
                    INSERT INTO brief_keywords (id, brief_id, keyword, placement)
                    VALUES (%s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()), brief_id,
                    kw.get('term', ''),
                    kw.get('placement', '')
                ))

    logger.info("Saved content brief %s for keyword '%s'", brief_id, keyword)
    return brief_id


def get_content_briefs(limit: int = 20, project_id: str = None, keyword_filter: str = '') -> list:
    """Retrieve past content briefs, optionally filtered by keyword."""
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if keyword_filter:
            cur.execute("""
                SELECT id, keyword, content_type, target_word_count, brief_json,
                       status, created_at
                FROM content_briefs
                WHERE project_id = %s AND keyword ILIKE %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (pid, f'%{keyword_filter}%', limit))
        else:
            cur.execute("""
                SELECT id, keyword, content_type, target_word_count, brief_json,
                       status, created_at
                FROM content_briefs
                WHERE project_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (pid, limit))
        rows = cur.fetchall()
        for r in rows:
            r['id'] = str(r['id'])
            if r.get('created_at'):
                r['created_at'] = r['created_at'].isoformat()
            if r.get('brief_json') and isinstance(r['brief_json'], str):
                r['brief_json'] = json.loads(r['brief_json'])
        return rows


def get_content_brief_by_id(brief_id: str, project_id: str = None) -> dict:
    """Retrieve a single brief with its competitors and keywords."""
    pid = project_id or DEFAULT_PROJECT_ID
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM content_briefs WHERE id = %s AND project_id = %s
        """, (brief_id, pid))
        brief = cur.fetchone()
        if not brief:
            return None

        brief['id'] = str(brief['id'])
        brief['project_id'] = str(brief['project_id'])
        if brief.get('created_at'):
            brief['created_at'] = brief['created_at'].isoformat()
        if brief.get('updated_at'):
            brief['updated_at'] = brief['updated_at'].isoformat()

        # Get competitors
        cur.execute("SELECT * FROM brief_competitors WHERE brief_id = %s", (brief_id,))
        brief['competitors'] = [
            {**r, 'id': str(r['id']), 'brief_id': str(r['brief_id'])}
            for r in cur.fetchall()
        ]

        # Get keywords
        cur.execute("SELECT * FROM brief_keywords WHERE brief_id = %s", (brief_id,))
        brief['keywords'] = [
            {**r, 'id': str(r['id']), 'brief_id': str(r['brief_id'])}
            for r in cur.fetchall()
        ]

        return brief
