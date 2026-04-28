#!/usr/bin/env python3
"""PostgreSQL database layer for the generic Directory module.

Supports categories like Sports, Tools, Brands, etc. with items that have
structured fields: name, category, description, source_url, status, tags,
trending score, ranking, and last_updated.

Uses the same RDS connection pool from db.py — no new database required.
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# ── Connection ────────────────────────────────────────────────────────────────

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
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


# ── Schema init ───────────────────────────────────────────────────────────────

def init_directory_tables():
    """Create directory_categories and directory_items tables if they don't exist."""
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS directory_categories (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(255) NOT NULL,
                slug        VARCHAR(255) UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                icon        VARCHAR(100) DEFAULT '',
                sort_order  INTEGER DEFAULT 0,
                is_active   BOOLEAN DEFAULT TRUE,
                item_count  INTEGER DEFAULT 0,
                meta_json   JSONB DEFAULT '{}',
                created_at  TIMESTAMP DEFAULT NOW(),
                updated_at  TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS directory_items (
                id              SERIAL PRIMARY KEY,
                category_id     INTEGER NOT NULL REFERENCES directory_categories(id) ON DELETE CASCADE,
                name            VARCHAR(500) NOT NULL,
                slug            VARCHAR(500) NOT NULL,
                description     TEXT DEFAULT '',
                source_url      VARCHAR(2048) DEFAULT '',
                image_url       VARCHAR(2048) DEFAULT '',
                status          VARCHAR(50) DEFAULT 'active',
                tags            TEXT[] DEFAULT '{}',
                trending_score  INTEGER DEFAULT 0,
                ranking         INTEGER DEFAULT 0,
                rating          NUMERIC(3,1) DEFAULT 0.0,
                review_count    INTEGER DEFAULT 0,
                meta_json       JSONB DEFAULT '{}',
                last_updated    TIMESTAMP DEFAULT NOW(),
                created_at      TIMESTAMP DEFAULT NOW(),
                UNIQUE(category_id, slug)
            )
        """)

        # Indexes for fast queries
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_dir_items_category ON directory_items(category_id)",
            "CREATE INDEX IF NOT EXISTS idx_dir_items_status ON directory_items(status)",
            "CREATE INDEX IF NOT EXISTS idx_dir_items_trending ON directory_items(trending_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_dir_items_ranking ON directory_items(ranking ASC)",
            "CREATE INDEX IF NOT EXISTS idx_dir_items_tags ON directory_items USING GIN(tags)",
            "CREATE INDEX IF NOT EXISTS idx_dir_cats_slug ON directory_categories(slug)",
        ]:
            try:
                cur.execute(idx_sql)
            except Exception:
                pass

        conn.commit()
        logger.info("directory_categories + directory_items tables verified")


# ── Category CRUD ─────────────────────────────────────────────────────────────

def create_category(name: str, slug: str, description: str = '',
                    icon: str = '', sort_order: int = 0,
                    meta_json: dict = None) -> Dict:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO directory_categories (name, slug, description, icon, sort_order, meta_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                name=EXCLUDED.name, description=EXCLUDED.description,
                icon=EXCLUDED.icon, sort_order=EXCLUDED.sort_order,
                meta_json=EXCLUDED.meta_json, updated_at=NOW()
            RETURNING *
        """, (name, slug, description, icon, sort_order,
              json.dumps(meta_json or {})))
        return dict(cur.fetchone())


def get_categories(active_only: bool = True) -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = "SELECT * FROM directory_categories"
        if active_only:
            sql += " WHERE is_active = TRUE"
        sql += " ORDER BY sort_order, name"
        cur.execute(sql)
        rows = cur.fetchall()
        return [_fmt_cat(r) for r in rows]


def get_category_by_slug(slug: str) -> Optional[Dict]:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM directory_categories WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return _fmt_cat(row) if row else None


def update_category(slug: str, updates: Dict) -> Optional[Dict]:
    allowed = {'name', 'description', 'icon', 'sort_order', 'is_active', 'meta_json'}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_category_by_slug(slug)
    if 'meta_json' in fields:
        fields['meta_json'] = json.dumps(fields['meta_json'])
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    set_clause += ", updated_at = NOW()"
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            f"UPDATE directory_categories SET {set_clause} WHERE slug = %s RETURNING *",
            list(fields.values()) + [slug]
        )
        row = cur.fetchone()
        return _fmt_cat(row) if row else None


def delete_category(slug: str) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM directory_categories WHERE slug = %s", (slug,))
        return cur.rowcount > 0


# ── Item CRUD ─────────────────────────────────────────────────────────────────

def create_item(category_slug: str, data: Dict) -> Optional[Dict]:
    cat = get_category_by_slug(category_slug)
    if not cat:
        return None
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO directory_items
                (category_id, name, slug, description, source_url, image_url,
                 status, tags, trending_score, ranking, rating, review_count, meta_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (category_id, slug) DO UPDATE SET
                name=EXCLUDED.name, description=EXCLUDED.description,
                source_url=EXCLUDED.source_url, image_url=EXCLUDED.image_url,
                status=EXCLUDED.status, tags=EXCLUDED.tags,
                trending_score=EXCLUDED.trending_score, ranking=EXCLUDED.ranking,
                rating=EXCLUDED.rating, review_count=EXCLUDED.review_count,
                meta_json=EXCLUDED.meta_json, last_updated=NOW()
            RETURNING *
        """, (
            cat['id'], data['name'], data.get('slug', _slugify(data['name'])),
            data.get('description', ''), data.get('source_url', ''),
            data.get('image_url', ''), data.get('status', 'active'),
            data.get('tags', []), data.get('trending_score', 0),
            data.get('ranking', 0), data.get('rating', 0),
            data.get('review_count', 0),
            json.dumps(data.get('meta_json', {}))
        ))
        row = cur.fetchone()
        # Update category item count
        cur.execute("""
            UPDATE directory_categories SET item_count = (
                SELECT COUNT(*) FROM directory_items WHERE category_id = %s AND status = 'active'
            ), updated_at = NOW() WHERE id = %s
        """, (cat['id'], cat['id']))
        return _fmt_item(row) if row else None


def get_items(category_slug: str, status: str = None, tag: str = None,
              sort_by: str = 'ranking', order: str = 'asc',
              limit: int = 50, offset: int = 0) -> Dict:
    """Get items for a category with filtering, sorting, and pagination."""
    cat = get_category_by_slug(category_slug)
    if not cat:
        return {'items': [], 'total': 0, 'category': None}

    where = ["di.category_id = %s"]
    params: list = [cat['id']]

    if status:
        where.append("di.status = %s")
        params.append(status)
    if tag:
        where.append("%s = ANY(di.tags)")
        params.append(tag)

    where_sql = " AND ".join(where)

    sort_map = {
        'ranking': 'di.ranking', 'trending': 'di.trending_score',
        'rating': 'di.rating', 'name': 'di.name',
        'newest': 'di.created_at', 'updated': 'di.last_updated',
    }
    sort_col = sort_map.get(sort_by, 'di.ranking')
    order_sql = 'DESC' if order == 'desc' else 'ASC'
    # For trending and rating, default to DESC
    if sort_by in ('trending', 'rating', 'newest', 'updated') and order != 'asc':
        order_sql = 'DESC'

    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Total count
        cur.execute(f"SELECT COUNT(*) as cnt FROM directory_items di WHERE {where_sql}", params)
        total = cur.fetchone()['cnt']

        # Items
        cur.execute(f"""
            SELECT di.* FROM directory_items di
            WHERE {where_sql}
            ORDER BY {sort_col} {order_sql}
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        items = [_fmt_item(r) for r in cur.fetchall()]

    return {'items': items, 'total': total, 'category': cat}


def get_item_by_slug(category_slug: str, item_slug: str) -> Optional[Dict]:
    cat = get_category_by_slug(category_slug)
    if not cat:
        return None
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM directory_items WHERE category_id = %s AND slug = %s",
            (cat['id'], item_slug)
        )
        row = cur.fetchone()
        return _fmt_item(row) if row else None


def update_item(category_slug: str, item_slug: str, updates: Dict) -> Optional[Dict]:
    cat = get_category_by_slug(category_slug)
    if not cat:
        return None
    allowed = {'name', 'description', 'source_url', 'image_url', 'status',
               'tags', 'trending_score', 'ranking', 'rating', 'review_count', 'meta_json'}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_item_by_slug(category_slug, item_slug)
    if 'meta_json' in fields:
        fields['meta_json'] = json.dumps(fields['meta_json'])
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    set_clause += ", last_updated = NOW()"
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            f"UPDATE directory_items SET {set_clause} WHERE category_id = %s AND slug = %s RETURNING *",
            list(fields.values()) + [cat['id'], item_slug]
        )
        row = cur.fetchone()
        return _fmt_item(row) if row else None


def delete_item(category_slug: str, item_slug: str) -> bool:
    cat = get_category_by_slug(category_slug)
    if not cat:
        return False
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM directory_items WHERE category_id = %s AND slug = %s",
            (cat['id'], item_slug)
        )
        deleted = cur.rowcount > 0
        if deleted:
            cur.execute("""
                UPDATE directory_categories SET item_count = (
                    SELECT COUNT(*) FROM directory_items WHERE category_id = %s AND status = 'active'
                ), updated_at = NOW() WHERE id = %s
            """, (cat['id'], cat['id']))
        return deleted


# ── Trending & Search ─────────────────────────────────────────────────────────

def get_trending_items(limit: int = 20, category_slug: str = None) -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if category_slug:
            cat = get_category_by_slug(category_slug)
            if not cat:
                return []
            cur.execute("""
                SELECT di.*, dc.slug as category_slug, dc.name as category_name
                FROM directory_items di
                JOIN directory_categories dc ON dc.id = di.category_id
                WHERE di.category_id = %s AND di.status = 'active'
                ORDER BY di.trending_score DESC
                LIMIT %s
            """, (cat['id'], limit))
        else:
            cur.execute("""
                SELECT di.*, dc.slug as category_slug, dc.name as category_name
                FROM directory_items di
                JOIN directory_categories dc ON dc.id = di.category_id
                WHERE di.status = 'active'
                ORDER BY di.trending_score DESC
                LIMIT %s
            """, (limit,))
        return [_fmt_item(r) for r in cur.fetchall()]


def search_items(query: str, category_slug: str = None,
                 limit: int = 30) -> List[Dict]:
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        like = f"%{query}%"
        if category_slug:
            cat = get_category_by_slug(category_slug)
            if not cat:
                return []
            cur.execute("""
                SELECT di.*, dc.slug as category_slug, dc.name as category_name
                FROM directory_items di
                JOIN directory_categories dc ON dc.id = di.category_id
                WHERE di.category_id = %s AND di.status = 'active'
                  AND (di.name ILIKE %s OR di.description ILIKE %s OR %s = ANY(di.tags))
                ORDER BY di.trending_score DESC
                LIMIT %s
            """, (cat['id'], like, like, query.lower(), limit))
        else:
            cur.execute("""
                SELECT di.*, dc.slug as category_slug, dc.name as category_name
                FROM directory_items di
                JOIN directory_categories dc ON dc.id = di.category_id
                WHERE di.status = 'active'
                  AND (di.name ILIKE %s OR di.description ILIKE %s OR %s = ANY(di.tags))
                ORDER BY di.trending_score DESC
                LIMIT %s
            """, (like, like, query.lower(), limit))
        return [_fmt_item(r) for r in cur.fetchall()]


def get_all_tags(category_slug: str = None) -> List[str]:
    """Return distinct tags, optionally scoped to a category."""
    with get_conn() as conn:
        cur = conn.cursor()
        if category_slug:
            cat = get_category_by_slug(category_slug)
            if not cat:
                return []
            cur.execute("""
                SELECT DISTINCT unnest(tags) AS tag
                FROM directory_items
                WHERE category_id = %s AND status = 'active'
                ORDER BY tag
            """, (cat['id'],))
        else:
            cur.execute("""
                SELECT DISTINCT unnest(tags) AS tag
                FROM directory_items WHERE status = 'active'
                ORDER BY tag
            """)
        return [r[0] for r in cur.fetchall()]


# ── Bulk upsert (admin / API ingestion) ───────────────────────────────────────

def bulk_upsert_items(category_slug: str, items: List[Dict]) -> Dict:
    """Insert or update many items at once. Returns counts."""
    cat = get_category_by_slug(category_slug)
    if not cat:
        return {'error': f'Category {category_slug} not found', 'inserted': 0, 'updated': 0}
    inserted = 0
    updated = 0
    for item in items:
        existing = None
        slug = item.get('slug', _slugify(item['name']))
        with get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id FROM directory_items WHERE category_id = %s AND slug = %s",
                (cat['id'], slug)
            )
            existing = cur.fetchone()
        item['slug'] = slug
        create_item(category_slug, item)
        if existing:
            updated += 1
        else:
            inserted += 1
    return {'inserted': inserted, 'updated': updated, 'total': len(items)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _fmt_cat(row) -> Dict:
    if not row:
        return {}
    d = dict(row)
    if d.get('created_at'):
        d['created_at'] = d['created_at'].isoformat()
    if d.get('updated_at'):
        d['updated_at'] = d['updated_at'].isoformat()
    return d


def _fmt_item(row) -> Dict:
    if not row:
        return {}
    d = dict(row)
    for ts_key in ('created_at', 'last_updated'):
        if d.get(ts_key):
            d[ts_key] = d[ts_key].isoformat()
    if d.get('rating'):
        d['rating'] = float(d['rating'])
    if d.get('meta_json') and isinstance(d['meta_json'], str):
        try:
            d['meta_json'] = json.loads(d['meta_json'])
        except (json.JSONDecodeError, TypeError):
            pass
    return d
