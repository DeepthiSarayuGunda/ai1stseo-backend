# Analytics Tracker Module

## Purpose

Lightweight internal analytics event tracker for growth-related events. Stores events in DynamoDB with UTM attribution fields. Provides a summary endpoint for grouped reporting.

All code lives in `growth/analytics_tracker.py` with API routes in `growth/growth_api.py`.

## Allowed Event Types

- `page_view`
- `email_signup_started`
- `email_signup_completed`
- `lead_magnet_clicked`
- `newsletter_cta_clicked`
- `subscriber_exported`
- `subscriber_list_viewed`

Any other event type is rejected with HTTP 400.

## Endpoints

### POST /api/growth/track (Public, no auth)

Track a growth analytics event.

**Request:**
```json
{
  "event_type": "page_view",
  "source": "website_main",
  "session_id": "sess_abc123",
  "page_url": "https://ai1stseo.com/blog/seo-tips",
  "utm_source": "linkedin",
  "utm_medium": "social",
  "utm_campaign": "launch_2026",
  "utm_content": "banner_v2",
  "utm_term": "seo tools",
  "event_data": {"key": "value"}
}
```

Only `event_type` is required. All other fields are optional.

`created_at` and `event_id` are always server-generated. Any client-provided values are silently ignored.

**Responses:**
- `201` — Event tracked successfully
- `400` — Invalid or missing event_type
- `429` — Rate limit exceeded (max 20 events/min per session_id)
- `503` — DynamoDB unavailable

**Example:**
```bash
curl -X POST https://ai1stseo.com/api/growth/track \
  -H "Content-Type: application/json" \
  -d '{"event_type":"page_view","source":"website_main","utm_source":"linkedin","utm_campaign":"launch_2026"}'
```

### GET /api/growth/analytics/summary (Auth required)

Get event counts grouped by type, date, source, utm_source, and utm_campaign.

**Query params:** `days` (default 7, max 90)

**Response:**
```json
{
  "success": true,
  "days": 7,
  "total_events": 142,
  "by_type": {"page_view": 80, "email_signup_completed": 27},
  "by_date": {"2026-04-07": 45, "2026-04-06": 38},
  "by_source": {"website_main": 100, "landing_page": 42},
  "by_utm_source": {"linkedin": 60, "twitter": 30},
  "by_utm_campaign": {"launch_2026": 90, "starter_kit": 52}
}
```

**Example:**
```bash
curl -X GET "https://ai1stseo.com/api/growth/analytics/summary?days=7" \
  -H "Authorization: Bearer <cognito_token>"
```

## Rate Limiting

- If `session_id` is present: max 20 events per 60-second sliding window per session
- If `session_id` is absent: event is allowed through with a warning log
- In-memory only (process-local, resets on restart)
- Not a production rate limiter — dev safety guard only

## Input Sanitization

- All string fields: leading/trailing whitespace stripped
- Lowercased: `event_type`, `source`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`
- Case preserved: `page_url`, `session_id`
- All strings truncated to 2048 characters
- `event_data` float values converted to Decimal for DynamoDB

## DynamoDB Table

- Table: `ai1stseo-growth-analytics` (env var: `GROWTH_ANALYTICS_TABLE`)
- Key: `event_type` (HASH) + `created_at` (RANGE)
- UTM fields stored as top-level attributes
- Billing: PAY_PER_REQUEST

## Error Handling

All DynamoDB failures return `{"success": false, "error": "Analytics unavailable"}` with HTTP 503. The app never crashes on analytics errors.

## Environment Variables

- `GROWTH_ANALYTICS_TABLE` — DynamoDB table name (default: `ai1stseo-growth-analytics`)
- `AWS_REGION` — AWS region (default: `us-east-1`)
