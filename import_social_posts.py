"""
import_social_posts.py
Import draft social media posts from social_media_posts.json into the
social_scheduler.db SQLite database used by /api/social/posts (app.py)
AND into the PostgreSQL social_posts table used by /api/data/social-posts
(data_api.py).

Usage:
    python import_social_posts.py [--target sqlite|postgres|both] [--dry-run]

Defaults to sqlite (local, no auth required).
"""

import json
import os
import sqlite3
import sys
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

JSON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "social_media_posts.json")
SOCIAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "social_scheduler.db")

DRY_RUN = "--dry-run" in sys.argv
TARGET = "sqlite"
for arg in sys.argv:
    if arg.startswith("--target="):
        TARGET = arg.split("=", 1)[1]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_posts():
    """Load and validate the JSON file."""
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        posts = json.load(f)
    if not isinstance(posts, list):
        raise ValueError("JSON root must be an array")
    print(f"Loaded {len(posts)} posts from {JSON_FILE}")
    return posts


def build_content_blob(post):
    """
    Pack title, caption, hashtags, and category into a single content string.
    Format:
        [Title] ...
        [Category] ...
        <caption text>
        [Hashtags] #a #b #c
    This preserves all fields in a human-readable way inside the content column.
    """
    parts = []
    if post.get("title"):
        parts.append(f"[Title] {post['title']}")
    if post.get("category"):
        parts.append(f"[Category] {post['category']}")
    parts.append("")  # blank line before caption
    parts.append(post.get("caption", ""))
    if post.get("hashtags"):
        parts.append("")
        parts.append("[Hashtags] " + " ".join(post["hashtags"]))
    return "\n".join(parts)


# ── SQLite import (social_scheduler.db) ───────────────────────────────────────

def ensure_sqlite_schema(conn):
    """Create table if missing and add extra columns for richer data."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            platforms TEXT NOT NULL,
            scheduled_datetime TEXT NOT NULL,
            created_at TEXT NOT NULL,
            image_path TEXT
        )
    """)
    # Add columns that the original schema lacks
    existing = [row[1] for row in conn.execute("PRAGMA table_info(scheduled_posts)").fetchall()]
    migrations = {
        "image_path": "TEXT",
        "title": "TEXT",
        "hashtags": "TEXT",
        "category": "TEXT",
        "status": "TEXT DEFAULT 'draft'",
        "created_by": "TEXT",
    }
    for col, coldef in migrations.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE scheduled_posts ADD COLUMN {col} {coldef}")
            print(f"  [migrate] added column '{col}' to scheduled_posts")
    conn.commit()


def import_to_sqlite(posts):
    """Insert posts into the local SQLite database."""
    print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Importing to SQLite → {SOCIAL_DB}")
    conn = sqlite3.connect(SOCIAL_DB)
    ensure_sqlite_schema(conn)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0

    for i, post in enumerate(posts, 1):
        platform = post.get("platform", "")
        caption = post.get("caption", "")
        title = post.get("title", "")
        hashtags_str = json.dumps(post.get("hashtags", []))
        category = post.get("category", "")
        status = post.get("status", "draft")
        scheduled_at = post.get("scheduled_at") or ""
        image_url = post.get("image_url") or ""
        created_by = post.get("created_by", "")

        if DRY_RUN:
            print(f"  [{i:02d}] {platform:12s} | {title[:50]}")
            inserted += 1
            continue

        conn.execute(
            """INSERT INTO scheduled_posts
               (content, platforms, scheduled_datetime, created_at, image_path,
                title, hashtags, category, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (caption, platform, scheduled_at, now, image_url,
             title, hashtags_str, category, status, created_by),
        )
        inserted += 1
        print(f"  [{i:02d}] ✓ {platform:12s} | {title[:50]}")

    if not DRY_RUN:
        conn.commit()
    conn.close()
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Inserted {inserted}/{len(posts)} posts into SQLite.\n")
    return inserted


# ── PostgreSQL import (via data_api helpers) ──────────────────────────────────

def import_to_postgres(posts):
    """Insert posts into the PostgreSQL social_posts table."""
    print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Importing to PostgreSQL → social_posts")
    try:
        from database import insert_returning
    except ImportError:
        # Try backend path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "OneDrive", "Desktop", "seo deployment", "backend"))
        try:
            from database import insert_returning
        except ImportError:
            print("  ✗ Could not import database module. Skipping PostgreSQL import.")
            print("    Set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD env vars and ensure psycopg2 is installed.")
            return 0

    DEFAULT_PROJECT_ID = os.environ.get("DEFAULT_PROJECT_ID", "24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2")
    inserted = 0

    for i, post in enumerate(posts, 1):
        content = build_content_blob(post)
        platform = post.get("platform", "")
        platforms_pg = "{" + platform + "}"
        scheduled_at = post.get("scheduled_at")
        status = post.get("status", "draft")

        if DRY_RUN:
            print(f"  [{i:02d}] {platform:12s} | {post.get('title', '')[:50]}")
            inserted += 1
            continue

        try:
            post_id = insert_returning(
                "INSERT INTO social_posts (project_id, content, platforms, scheduled_at, status, created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (DEFAULT_PROJECT_ID, content, platforms_pg, scheduled_at, status, None),
            )
            inserted += 1
            print(f"  [{i:02d}] ✓ {platform:12s} | id={post_id} | {post.get('title', '')[:40]}")
        except Exception as e:
            print(f"  [{i:02d}] ✗ {platform:12s} | {e}")

    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Inserted {inserted}/{len(posts)} posts into PostgreSQL.\n")
    return inserted


# ── CRUD verification ─────────────────────────────────────────────────────────

def verify_sqlite_crud():
    """Run basic CRUD checks against the SQLite database."""
    print("── SQLite CRUD Verification ──")
    conn = sqlite3.connect(SOCIAL_DB)
    conn.row_factory = sqlite3.Row

    # GET all
    rows = conn.execute("SELECT * FROM scheduled_posts ORDER BY id DESC").fetchall()
    print(f"  GET  all: {len(rows)} posts found")
    if not rows:
        conn.close()
        print("  ✗ No posts to verify. Skipping CRUD tests.\n")
        return

    # Check fields on latest row
    latest = dict(rows[0])
    expected_fields = ["content", "platforms", "title", "hashtags", "category", "status", "created_by"]
    missing = [f for f in expected_fields if f not in latest or latest[f] in (None, "")]
    if missing:
        print(f"  ⚠ Missing/empty fields on latest row: {missing}")
    else:
        print(f"  ✓ All expected fields present on latest row")

    # POST (insert a test post)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        """INSERT INTO scheduled_posts
           (content, platforms, scheduled_datetime, created_at, title, hashtags, category, status, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("CRUD test caption", "Twitter/X", "", now,
         "CRUD Test Post", '["#test"]', "Test", "draft", "Tabasum"),
    )
    conn.commit()
    test_id = cur.lastrowid
    print(f"  POST created test post id={test_id}")

    # UPDATE
    conn.execute("UPDATE scheduled_posts SET status = 'scheduled' WHERE id = ?", (test_id,))
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM scheduled_posts WHERE id = ?", (test_id,)).fetchone())
    assert updated["status"] == "scheduled", "UPDATE failed"
    print(f"  PUT  updated test post id={test_id} status → 'scheduled' ✓")

    # DELETE
    conn.execute("DELETE FROM scheduled_posts WHERE id = ?", (test_id,))
    conn.commit()
    gone = conn.execute("SELECT * FROM scheduled_posts WHERE id = ?", (test_id,)).fetchone()
    assert gone is None, "DELETE failed"
    print(f"  DEL  deleted test post id={test_id} ✓")

    # Final count
    final_count = conn.execute("SELECT COUNT(*) FROM scheduled_posts").fetchone()[0]
    print(f"  Final post count: {final_count}")

    conn.close()
    print("  ✓ All CRUD operations passed.\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    posts = load_posts()

    if TARGET in ("sqlite", "both"):
        import_to_sqlite(posts)
        if not DRY_RUN:
            verify_sqlite_crud()

    if TARGET in ("postgres", "both"):
        import_to_postgres(posts)

    print("Done.")


if __name__ == "__main__":
    main()
