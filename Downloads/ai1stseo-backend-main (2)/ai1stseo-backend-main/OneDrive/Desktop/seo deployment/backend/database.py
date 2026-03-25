"""
AI 1st SEO — PostgreSQL Database Helper
Shared module for all services to connect and query the RDS database.

Usage:
    from database import get_conn, query, execute, insert_returning

    # Simple query
    rows = query("SELECT * FROM projects WHERE owner_email = %s", (email,))

    # Insert and get the new ID back
    new_id = insert_returning("INSERT INTO projects (name, owner_email) VALUES (%s, %s) RETURNING id", ("My Site", email))

    # Execute (update/delete)
    execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user_id,))
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


def get_conn():
    """Get a new database connection."""
    return psycopg2.connect(**DB_CONFIG)


def query(sql, params=None):
    """Run a SELECT and return all rows as dicts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def query_one(sql, params=None):
    """Run a SELECT and return a single row as dict, or None."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE and commit."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()


def insert_returning(sql, params=None):
    """Run an INSERT ... RETURNING and return the first column of the first row."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()
