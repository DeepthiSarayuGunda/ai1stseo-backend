# Social Publish Orchestrator Module

## Purpose

Routes social media publish requests to the correct publisher (Buffer or Postiz) based on available credentials. Normalizes platform names, tracks analytics events, and updates post status in DynamoDB.

## Endpoint

### POST /api/growth/social/publish (Auth required)

**Request:**
```json
{
  "content": "Check out our new AI SEO tool!",
  "platform": "linkedin",
  "post_id": "abc123",
  "scheduled_at": "2026-04-15T14:00:00Z"
}
```
`content` and `platform` are required. `post_id` and `scheduled_at` are optional.

**Responses:**
- `200` — Published successfully
- `400` — Missing content or platform
- `401` — Missing/invalid auth token
- `502` — Publisher API error
- `503` — No publisher configured

## Platform Normalization

| Input | Canonical Output |
|-------|-----------------|
| linkedin | linkedin |
| x | x |
| twitter | x |
| twitter/x | x |
| instagram | instagram |
| facebook | facebook |

Input is case-insensitive and whitespace-trimmed.

## Publisher Selection

1. Check if Buffer is configured (`BUFFER_API_KEY` set)
2. Check if Postiz is configured (`POSTIZ_API_KEY` set)
3. If both: prefer Buffer (override with `SOCIAL_PUBLISHER_PREFERENCE=postiz`)
4. If neither: return 503 with "No publisher configured"

## Analytics Events

- `publish_attempted` — tracked before publish call. event_data: `{platform, provider}`
- `publish_succeeded` — tracked after success. event_data: `{platform, provider, post_id}`
- `publish_failed` — tracked after failure. event_data: `{platform, provider, post_id, error}`

All analytics tracking is non-blocking.

## Post Status Updates

When `post_id` is provided, the orchestrator updates the DynamoDB post status:
- Success → `"published"`
- Failure → `"failed"`

Status updates are non-blocking (fire-and-forget).

## Environment Variables

- `SOCIAL_PUBLISHER_PREFERENCE` — `"buffer"` (default) or `"postiz"`
- `BUFFER_API_KEY` — Buffer API key
- `POSTIZ_API_KEY` — Postiz API key
- Platform-specific channel/integration IDs (see buffer_publisher.py and postiz_publisher.py)

## Files

- `growth/social_orchestrator.py` — orchestration logic
- `growth/growth_api.py` — endpoint route
