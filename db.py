"""
db.py
RDS PostgreSQL connection pool for the AEO platform.

Uses psycopg2 with a simple connection pool. All GEO probe results,
AI visibility history, and batch results are persisted here.

Environment variables:
  RDS_HOST     - RDS endpoint (required)
  RDS_PORT     - default 5432
  RDS_DB       - database name (default: aeo_platform)
  RDS_USER     - database user
  RDS_PASSWORD - database password
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from psycopg2 import pool

logger = logging.getLogger(__name__)

# ── Connection pool ───────────────────────────────────────────────────────────

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.environ.get("RDS_HOST", "localhost"),
            port=int(os.environ.get("RDS_PORT", "5432")),
            dbname=os.environ.get("RDS_DB", "aeo_platform"),
            user=os.environ.get("RDS_USER", "postgres"),
            password=os.environ.get("RDS_PASSWORD", ""),
        )
        logger.info("RDS connection pool created: %s:%s/%s",
                     os.environ.get("RDS_HOST"), os.environ.get("RDS_PORT", "5432"),
                     os.environ.get("RDS_DB", "aeo_platform"))
    return _pool


@contextmanager
def get_conn():
    """Context manager that checks out a connection and returns it to the pool."""
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


# ── Schema initialization ─────────────────────────────────────────────────────

def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS geo_probes (
                id          SERIAL PRIMARY KEY,
                keyword     TEXT NOT NULL,
                brand       TEXT NOT NULL,
                ai_model    TEXT NOT NULL,
                cited       BOOLEAN NOT NULL DEFAULT FALSE,
                citation_context TEXT,
                confidence  REAL DEFAULT 0.0,
                site_url    TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_visibility_history (
                id          SERIAL PRIMARY KEY,
                brand       TEXT NOT NULL,
                ai_model    TEXT NOT NULL,
                keyword     TEXT NOT NULL,
                geo_score   REAL DEFAULT 0.0,
                cited_count INTEGER DEFAULT 0,
                total_prompts INTEGER DEFAULT 0,
                batch_results JSONB,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Indexes for common queries
        cur.execute("CREATE INDEX IF NOT EXISTS idx_geo_probes_brand ON geo_probes (brand)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_geo_probes_model ON geo_probes (ai_model)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_geo_probes_created ON geo_probes (created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vis_history_brand ON ai_visibility_history (brand)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vis_history_created ON ai_visibility_history (created_at)")

        conn.commit()
        logger.info("RDS tables initialized (geo_probes, ai_visibility_history)")


# ── geo_probes CRUD ───────────────────────────────────────────────────────────

def insert_probe(keyword: str, brand: str, ai_model: str, cited: bool,
                 citation_context: str = None, confidence: float = 0.0,
                 site_url: str = None) -> int:
    """Insert a single probe result. Returns the new row id."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO geo_probes (keyword, brand, ai_model, cited, citation_context, confidence, site_url)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (keyword, brand, ai_model, cited, citation_context, confidence, site_url),
        )
        return cur.fetchone()[0]


def get_probes(limit: int = 50, brand: str = None, ai_model: str = None) -> list[dict]:
    """Fetch probe results with optional filters."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        clauses, params = [], []
        if brand:
            clauses.append("brand = %s")
            params.append(brand)
        if ai_model:
            clauses.append("ai_model = %s")
            params.append(ai_model)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        cur.execute(f"SELECT * FROM geo_probes {where} ORDER BY id DESC LIMIT %s", params)
        rows = cur.fetchall()
        # Convert datetime to ISO string for JSON serialization
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
        return rows


def get_probe_trend(brand: str, limit: int = 30) -> list[dict]:
    """Daily aggregated visibility trend for a brand."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT DATE(created_at) AS date,
                   COUNT(*) AS total,
                   SUM(CASE WHEN cited THEN 1 ELSE 0 END) AS cited,
                   ROUND(SUM(CASE WHEN cited THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100) AS visibility_score,
                   ARRAY_AGG(DISTINCT ai_model) AS providers
            FROM geo_probes
            WHERE brand = %s
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) DESC
            LIMIT %s
        """, (brand, limit))
        rows = cur.fetchall()
        for r in rows:
            r["date"] = r["date"].isoformat() if r.get("date") else None
            r["providers"] = list(r["providers"]) if r.get("providers") else []
        return rows


# ── ai_visibility_history CRUD ────────────────────────────────────────────────

def insert_visibility_batch(brand: str, ai_model: str, keyword: str,
                            geo_score: float, cited_count: int,
                            total_prompts: int, batch_results: dict = None) -> int:
    """Insert a batch visibility result. Returns the new row id."""
    import json
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ai_visibility_history
               (brand, ai_model, keyword, geo_score, cited_count, total_prompts, batch_results)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (brand, ai_model, keyword, geo_score, cited_count, total_prompts,
             json.dumps(batch_results) if batch_results else None),
        )
        return cur.fetchone()[0]


def get_visibility_history(limit: int = 20, brand: str = None) -> list[dict]:
    """Fetch batch visibility history."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if brand:
            cur.execute(
                "SELECT * FROM ai_visibility_history WHERE brand = %s ORDER BY id DESC LIMIT %s",
                (brand, limit))
        else:
            cur.execute(
                "SELECT * FROM ai_visibility_history ORDER BY id DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
