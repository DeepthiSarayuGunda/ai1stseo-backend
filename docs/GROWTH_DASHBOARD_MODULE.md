# Growth KPI Dashboard Module

## Purpose

Provides a single authenticated API endpoint that aggregates growth metrics from the analytics tracker and email subscriber store into one KPI summary.

## Endpoint

### GET /api/growth/dashboard (Auth required)

Query params: `days` (integer, default 7, clamped to 1-90)

**Example:**
```
GET /api/growth/dashboard?days=30
Authorization: Bearer <cognito_token>
```

**Response (200):**
```json
{
  "success": true,
  "days": 30,
  "generated_at": "2026-04-07T23:00:00+00:00",
  "analytics_available": true,
  "subscribers_available": true,
  "total_subscribers": 247,
  "new_subscribers": 38,
  "lead_magnet_downloads": 15,
  "welcome_email_attempted": 42,
  "welcome_email_sent": 40,
  "welcome_email_failed": 2,
  "top_event_types": {"page_view": 580, "email_signup_completed": 42},
  "top_utm_sources": {"linkedin": 120, "twitter": 45},
  "top_utm_campaigns": {"launch_2026": 90, "starter_kit": 52}
}
```

## KPI Fields

| Field | Type | Source |
|-------|------|--------|
| total_subscribers | int | email_subscriber.list_subscribers() total |
| new_subscribers | int | subscribers with subscribed_at within days window |
| lead_magnet_downloads | int | analytics by_type["lead_magnet_downloaded"] |
| welcome_email_attempted | int | analytics by_type["welcome_email_attempted"] |
| welcome_email_sent | int | analytics by_type["welcome_email_sent"] |
| welcome_email_failed | int | analytics by_type["welcome_email_failed"] |
| top_event_types | dict | analytics by_type (all event types) |
| top_utm_sources | dict | analytics by_utm_source |
| top_utm_campaigns | dict | analytics by_utm_campaign |

## Graceful Degradation

If a data source is unavailable, the dashboard still returns `success: true` with:
- Failed source fields zeroed out
- `analytics_available: false` or `subscribers_available: false` flag set
- The other source's data remains unaffected

## Files

- `growth/growth_dashboard.py` — aggregation logic
- `growth/growth_api.py` — endpoint route
