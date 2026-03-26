# Social Media Scheduler — Tabasum's PR Summary

## What Was Done

### 1. Encoding Fix
All three core files were corrupted with UTF-16 LE encoding (BOM + NULL bytes between every character):
- `app.py` — decoded from UTF-16 to clean UTF-8, normalized `\r\r\n` line endings to `\n`
- `social.html` — regenerated as clean UTF-8 (original was unreadable)
- `requirements.txt` — decoded from UTF-16 to clean UTF-8

### 2. Social Scheduler Feature
Added a full social media post scheduler with CRUD functionality.

**Backend (app.py):**
- `GET /api/social/posts` — returns all scheduled posts ordered by datetime
- `POST /api/social/posts` — creates a post (supports multipart/form-data with image upload)
- `DELETE /api/social/posts/<int:post_id>` — deletes a post and removes uploaded image from disk
- SQLite database (`social_scheduler.db`) with `scheduled_posts` table
- Image uploads stored in `static/uploads/`

**Frontend (social.html):**
- Served at `/social`
- Post content textarea
- Platform checkboxes: LinkedIn, Facebook, Instagram, X (Twitter)
- Date and time inputs (defaults to 30 min from now)
- Optional image upload with preview
- Upcoming posts table with delete buttons
- Flash messages for success/error feedback

**DB Schema:**
```sql
CREATE TABLE scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    platforms TEXT NOT NULL,          -- comma-separated
    scheduled_datetime TEXT NOT NULL, -- "YYYY-MM-DD HH:MM"
    created_at TEXT NOT NULL,
    image_path TEXT                   -- nullable, e.g. "/static/uploads/filename.jpg"
);
```

### 3. Conflict Resolution
- Merged `origin/main` into PR branch, keeping all teammates' code (JSON error handlers, RDS init, call_llm, content brief generator, content scoring engine)
- Social scheduler code added without overwriting any shared backend logic

### 4. .gitignore Updates
Added entries to exclude runtime files:
- `social_scheduler.db`
- `static/uploads/`

## Manual Test Flow
1. Start server: `python app.py`
2. Navigate to `http://127.0.0.1:5001/social`
3. Create post → fill form, select platforms, submit
4. List posts → table auto-refreshes after create
5. Delete post → click Delete, confirm

## Files in This PR
- `app.py` — encoding fix + social scheduler endpoints
- `social.html` — scheduler frontend (new file)
- `requirements.txt` — encoding fix only
- `.gitignore` — added runtime exclusions
- `SOCIAL_SCHEDULER_TABASUM.md` — this file
