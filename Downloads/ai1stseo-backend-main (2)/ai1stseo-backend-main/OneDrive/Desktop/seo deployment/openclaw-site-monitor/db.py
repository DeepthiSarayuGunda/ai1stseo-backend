"""
Database helper for Site Monitor — Lambda/Amplify compatible.
Mirrors backend/database.py but lives in the monitor package for independent deployment.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "ai1stseo-db.ca5mm2skodf2.us-east-1.rds.amazonaws.com"),
    "database": os.environ.get("DB_NAME", "ai1stseo"),
    "user": os.environ.get("DB_USER", "ai1stseo_admin"),
    "password": os.environ.get("DB_PASSWORD", "Ai1stSEO_db2026!"),
    "port": int(os.environ.get("DB_PORT", 5432)),
}

# Connection pooling for Lambda (reuse across warm invocations)
_conn = None


def get_conn():
    """Get a database connection, reusing across Lambda invocations when possible."""
    global _conn
    if _conn is not None:
        try:
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
    _conn = psycopg2.connect(**DB_CONFIG)
    _conn.autocommit = False
    return _conn


def query(sql, params=None):
    """Run a SELECT and return all rows as dicts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception:
        conn.rollback()
        raise


def query_one(sql, params=None):
    """Run a SELECT and return a single row as dict, or None."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    except Exception:
        conn.rollback()
        raise


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE and commit."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    except Exception:
        conn.rollback()
        raise


def insert_returning(sql, params=None):
    """Run an INSERT ... RETURNING and return the first column of the first row."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        conn.rollback()
        raise
