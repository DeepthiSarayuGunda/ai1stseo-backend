# Lead Magnet Module

## Purpose

Delivers downloadable resources (PDFs, checklists) to users after email subscription. Phase 1 uses a static Python registry — no database, no email sending, no file uploads.

All code lives in `growth/lead_magnet.py` with API routes in `growth/growth_api.py`.

## Lead Magnet Data Format

Each entry in the registry:
```python
{
    "id": "lm-001",                    # unique immutable identifier
    "slug": "seo-starter-checklist",   # human-readable URL identifier
    "title": "SEO Starter Checklist",
    "description": "A 20-point checklist to launch your first SEO campaign.",
    "download_url": "https://assets.ai1stseo.com/lead-magnets/seo-starter-checklist.pdf"
}
```

## Adding New Lead Magnets

Edit `_LEAD_MAGNETS` in `growth/lead_magnet.py`:
```python
_LEAD_MAGNETS.append({
    "id": "lm-002",
    "slug": "aeo-guide",
    "title": "AEO Quick-Start Guide",
    "description": "How to optimize for AI search engines.",
    "download_url": "https://assets.ai1stseo.com/lead-magnets/aeo-guide.pdf",
})
```

Rules: `id` must be unique, `download_url` must start with `https://`.

## Endpoints

### GET /api/growth/lead-magnet (Public)

Returns all valid lead magnets.

**Response (200):**
```json
{
  "success": true,
  "lead_magnets": [
    {"id": "lm-001", "slug": "seo-starter-checklist", "title": "SEO Starter Checklist", "description": "...", "download_url": "https://..."}
  ],
  "count": 1
}
```

### POST /api/growth/lead-magnet/download (Public)

Logs a download event and returns the resource URL.

**Request:**
```json
{"slug": "seo-starter-checklist", "session_id": "sess_abc123"}
```
`slug` is required. `session_id` is optional (used for rate limiting).

**Responses:**
- `200` — Success with download_url, title, slug
- `400` — Missing slug
- `404` — Unknown slug
- `429` — Rate limit exceeded (20/min per session_id)

### POST /api/growth/subscribe (Modified)

Now accepts optional `lead_magnet_slug`. If valid, the response includes a `lead_magnet` object:
```json
{
  "success": true,
  "lead_magnet": {
    "id": "lm-001",
    "title": "SEO Starter Checklist",
    "slug": "seo-starter-checklist",
    "download_url": "https://..."
  }
}
```
If `lead_magnet_slug` is missing or invalid, subscription proceeds normally without the lead_magnet field.

## Analytics Events

- `lead_magnet_downloaded` — tracked on POST /api/growth/lead-magnet/download
- `lead_magnet_clicked` — tracked when lead magnet is returned after subscription

Both include `{"slug": "...", "id": "..."}` in event_data.

## Rate Limiting

The download endpoint reuses the analytics tracker's in-memory rate limiter:
- If `session_id` provided: max 20 requests per 60s per session
- If no `session_id`: allowed through with a warning log
- No auth required in Phase 1
