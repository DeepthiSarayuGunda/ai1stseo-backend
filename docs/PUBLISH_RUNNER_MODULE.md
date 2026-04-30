# Scheduled Publishing Runner Module

## Purpose

Batch-publishes overdue social media posts by scanning the DynamoDB scheduler table, filtering due posts, splitting multi-platform entries, and routing each through the social orchestrator.

## Endpoint

### POST /api/growth/social/run-scheduled (Auth required)

**Request:**
```json
{"dry_run": false}
```
`dry_run` defaults to `false`. Set to `true` to preview without publishing.

**Response (200):**
```json
{
  "success": true,
  "dry_run": false,
  "total_due": 3,
  "total_publish_attempts": 5,
  "succeeded": 4,
  "failed": 1,
  "skipped": 0,
  "results": [
    {"post_id": "abc123", "platform": "linkedin", "success": true, "error": null},
    {"post_id": "abc123", "platform": "x", "success": false, "error": "No publisher configured"},
    {"post_id": "def456", "platform": "instagram", "success": true, "error": null}
  ]
}
```

## How It Works

1. Calls `get_posts()` from the DynamoDB scheduler
2. Filters to posts with `status == "scheduled"` and `scheduled_datetime <= now`
3. Parses `scheduled_datetime` as `"YYYY-MM-DD HH:MM"` UTC
4. Splits comma-separated `platforms` field (e.g. "LinkedIn, X" → ["linkedin", "x"])
5. Calls `publish_post()` once per platform via the social orchestrator
6. Collects results into a batch summary

## Dry-Run Mode

When `dry_run: true`, the runner identifies due posts and builds the results list without calling the orchestrator. All result entries have `success: null` and `error: null`. No post statuses are changed.

## Analytics Events

- `runner_batch_started` — tracked before processing. event_data: `{dry_run, total_due}`
- `runner_batch_completed` — tracked after processing. event_data: `{dry_run, total_due, succeeded, failed, skipped}`

## Skipped Posts

Posts are skipped (not counted as failed) when:
- `scheduled_datetime` can't be parsed
- `platforms` field is empty or missing

## Files

- `growth/publish_runner.py` — runner logic
- `growth/growth_api.py` — endpoint route
