# Email Subscriber Capture Module

**Created:** April 4, 2026
**Module:** `growth/`
**Status:** Implemented — subscriber capture, storage, and export only

---

## What Was Built

An isolated email subscriber capture system for ai1stseo.com that:
- Accepts newsletter/lead capture subscriptions via a public API endpoint
- Stores subscribers in a new `email_subscribers` PostgreSQL table
- Validates email format and sanitises all inputs
- Prevents duplicate subscriptions gracefully
- Supports paginated listing with filters (auth required)
- Supports CSV and JSON export (auth required)

This is the first module in the 5-month growth plan. It does NOT include
email provider integration, lead magnets, analytics, or UTM tracking.

---

## Files Created

| File | Purpose |
|------|---------|
| `growth/__init__.py` | Package init, exports `growth_bp` |
| `growth/email_subscriber.py` | Core module: validation, CRUD, export, table init |
| `growth/growth_api.py` | Flask Blueprint with 3 endpoints, lazy table init, auth |
| `docs/EMAIL_SUBSCRIBER_MODULE.md` | This documentation |

## Files Modified

| File | Change | Lines |
|------|--------|-------|
| `app.py` | Added Blueprint registration block before catch_all route | ~5 lines |

No other files were modified. `db.py`, `requirements.txt`, `index.html`, and
all teammate directories are untouched.

---

## New Table Schema

```sql
CREATE TABLE IF NOT EXISTS email_subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    source VARCHAR(100) DEFAULT 'unknown',
    platform VARCHAR(100),
    campaign VARCHAR(255),
    opted_in BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) DEFAULT 'active',
    subscribed_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

Indexes: `email`, `source`, `platform`, `campaign`, `subscribed_at DESC`.

Table is created automatically via lazy-init on first request. No manual
migration needed.

---

## Endpoints

### POST /api/growth/subscribe (Public)

Subscribe a new email address.

**Request:**
```json
{
    "email": "user@example.com",
    "name": "Jane Doe",
    "source": "website",
    "platform": "homepage_footer",
    "campaign": "launch_2026",
    "opted_in": true
}
```

Only `email` is required. Defaults: `source="unknown"`, `opted_in=true`.

**Success (201):**
```json
{
    "success": true,
    "subscriber": {
        "id": "a1b2c3d4-...",
        "email": "user@example.com",
        "subscribed_at": "2026-04-04T12:00:00"
    }
}
```

**Duplicate (409):**
```json
{"success": false, "error": "Email already subscribed", "duplicate": true}
```

**Invalid email (400):**
```json
{"success": false, "error": "Invalid email format"}
```

### GET /api/growth/subscribers (Auth Required)

Paginated subscriber list. Requires `Authorization: Bearer <token>`.

**Query params:** `page` (default 1), `per_page` (default 25, max 100),
`source`, `platform`, `campaign`.

**Response (200):**
```json
{
    "success": true,
    "subscribers": [
        {
            "id": "...",
            "email": "user@example.com",
            "name": "Jane Doe",
            "source": "website",
            "platform": "homepage_footer",
            "campaign": "launch_2026",
            "opted_in": true,
            "status": "active",
            "subscribed_at": "2026-04-04T12:00:00",
            "updated_at": "2026-04-04T12:00:00"
        }
    ],
    "total": 42,
    "page": 1,
    "per_page": 25,
    "pages": 2
}
```

### GET /api/growth/subscribers/export (Auth Required)

Export all matching subscribers. Requires `Authorization: Bearer <token>`.

**Query params:** `format` (`json` default, or `csv`), `source`, `platform`, `campaign`.

No pagination — returns ALL filtered rows.

**JSON response (200):** Array of subscriber objects.

**CSV response (200):**
- Content-Type: `text/csv; charset=utf-8`
- Content-Disposition: `attachment; filename="subscribers_export_20260404.csv"`
- Always includes header row, even with 0 results.

**Invalid format (400):**
```json
{"success": false, "error": "Invalid format. Use csv or json"}
```

---

## How to Test Locally

```bash
# 1. Subscribe (public — no auth needed)
curl -X POST http://localhost:5000/api/growth/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User", "source": "website"}'
# Expect: 201

# 2. Duplicate subscribe
curl -X POST http://localhost:5000/api/growth/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
# Expect: 409

# 3. Invalid email
curl -X POST http://localhost:5000/api/growth/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "not-an-email"}'
# Expect: 400

# 4. List subscribers (auth required)
curl http://localhost:5000/api/growth/subscribers \
  -H "Authorization: Bearer YOUR_COGNITO_TOKEN"
# Expect: 200

# 5. Export JSON (default format)
curl http://localhost:5000/api/growth/subscribers/export \
  -H "Authorization: Bearer YOUR_COGNITO_TOKEN"
# Expect: 200 JSON array

# 6. Export CSV
curl http://localhost:5000/api/growth/subscribers/export?format=csv \
  -H "Authorization: Bearer YOUR_COGNITO_TOKEN"
# Expect: 200 text/csv

# 7. Invalid export format
curl "http://localhost:5000/api/growth/subscribers/export?format=xml" \
  -H "Authorization: Bearer YOUR_COGNITO_TOKEN"
# Expect: 400

# 8. List without auth
curl http://localhost:5000/api/growth/subscribers
# Expect: 401
```

---

## Environment Variables

No new environment variables are required. The module uses:
- `db.get_conn()` for PostgreSQL (existing connection pool)
- Cognito auth via existing `require_auth` decorator

---

## Future Extension Points

These are NOT built yet — documented for future reference:

1. **Email provider integration** — Connect to Mailchimp, ConvertKit, or
   SES for automated welcome sequences and drip campaigns.
2. **Lead magnet delivery** — Trigger a download or email delivery when a
   subscriber signs up with a specific campaign tag.
3. **Analytics tracking** — Log subscribe events to an analytics_events
   table for conversion tracking.
4. **UTM capture** — Accept and store UTM parameters alongside the
   subscription to track campaign attribution.
5. **Unsubscribe endpoint** — Add `POST /api/growth/unsubscribe` that
   sets `status='unsubscribed'` and updates `updated_at`.
6. **Rate limiting** — Add rate limiting on the public subscribe endpoint.
7. **Role-based access** — Replace Cognito token check with admin role
   verification for list/export endpoints.
