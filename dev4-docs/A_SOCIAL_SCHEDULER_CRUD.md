# Task A: Social Scheduler CRUD — Status & Documentation

**Last Updated:** March 31, 2026

## Scheduler Routes

| Method | Endpoint | Function | Status |
|--------|----------|----------|--------|
| GET | `/api/social/posts` | `social_get_posts()` | ✅ Working |
| POST | `/api/social/posts` | `social_create_post()` | ✅ Working |
| PUT | `/api/social/posts/<id>` | `social_update_post()` | ✅ Working |
| DELETE | `/api/social/posts/<id>` | `social_delete_post()` | ✅ Working |
| GET | `/social` | Serves `social.html` UI | ✅ Working |

## UI Status

| Feature | Status |
|---------|--------|
| Create form (POST) | ✅ Working — form with content, platforms, date/time, image upload |
| Posts table (GET) | ✅ Working — shows all posts with platform tags, schedule, status |
| Edit button (PUT) | ✅ Added — modal with content edit and status change |
| Delete button (DELETE) | ✅ Working — with confirmation dialog |
| Status column | ✅ Added — shows draft/scheduled/published with color coding |

## DB / API Flow

```
Client (social.html or API consumer)
  │
  ├── GET /api/social/posts
  │     → SQLite: SELECT * FROM scheduled_posts ORDER BY scheduled_datetime ASC
  │     → Returns: { posts: [...] }
  │
  ├── POST /api/social/posts
  │     → Accepts JSON or multipart/form-data (with image upload)
  │     → Required: content, platforms[], scheduled_date, scheduled_time
  │     → Optional: image (JPG/PNG)
  │     → SQLite: INSERT INTO scheduled_posts
  │     → Returns: { status: "success", id: <new_id> }
  │
  ├── PUT /api/social/posts/<id>
  │     → Accepts JSON: { content, platforms, scheduled_date, scheduled_time, status }
  │     → All fields optional (keeps existing values if omitted)
  │     → SQLite: UPDATE scheduled_posts SET ... WHERE id = ?
  │     → Returns: { status: "success", post: {...} }
  │
  └── DELETE /api/social/posts/<id>
        → Removes uploaded image file if present
        → SQLite: DELETE FROM scheduled_posts WHERE id = ?
        → Returns: { status: "success" }
```

## Database Schema (SQLite — `social_scheduler.db`)

```sql
CREATE TABLE scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    platforms TEXT NOT NULL,
    scheduled_datetime TEXT NOT NULL,
    created_at TEXT NOT NULL,
    image_path TEXT,
    title TEXT,
    hashtags TEXT,           -- JSON array string
    category TEXT,
    status TEXT DEFAULT 'draft',
    created_by TEXT
);
```

Columns `title`, `hashtags`, `category`, `status`, `created_by` were added via safe ALTER TABLE migrations in `import_social_posts.py`.

## Required Environment Variables

None for SQLite-based scheduler. The scheduler uses a local file `social_scheduler.db`.

For PostgreSQL (production RDS), these are needed:
- `DB_HOST` — RDS endpoint
- `DB_NAME` — database name
- `DB_USER` — database user
- `DB_PASSWORD` — database password

## Current Data

20 draft posts imported from `social_media_posts.json`:
- 5 LinkedIn, 5 Facebook, 5 Instagram, 5 Twitter/X
- All created by "Tabasum"
- All in "draft" status

## CRUD Test Results (March 31, 2026)

### Automated Test Suite: `dev4-tests/test_scheduler_crud.py`
- 8 tests, 8 passed, 0 failed
- Tests: READ all, schema verification, CREATE, READ by ID, UPDATE status, UPDATE platforms, DELETE, data integrity check

### Publisher Tests: `dev4-tests/test_publishers.py`
- 7 tests, 7 passed, 0 failed
- Tests: Buffer unconfigured, Buffer dry-run, Buffer mapping, Postiz unconfigured, Postiz dry-run, Postiz mapping, Postiz schedule mode

### Reddit Publisher Tests: `dev4-tests/test_reddit_publisher.py`
- 3 tests, 3 passed, 0 failed
- Tests: unconfigured state, dry-run with fake creds, is_configured() function

## Merge Readiness

- Branch: `dev4-tabasum-integrations`
- No teammate code modified
- PUT route added cleanly before existing DELETE route in `app.py`
- Edit UI added to `social.html` (additive only — no existing code changed)
- Safe to merge — additive changes only
- All 18 automated tests pass

## Files Changed

| File | Change |
|------|--------|
| `app.py` | Added `social_update_post()` PUT route |
| `social.html` | Added Edit button, status column, edit modal, JS functions |
