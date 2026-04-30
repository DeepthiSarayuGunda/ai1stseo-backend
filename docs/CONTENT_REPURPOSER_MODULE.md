# Content Repurposer Module

## Purpose

Transforms blog/article content into platform-specific social posts, email snippets, and short-form scripts. Integrates with the UTM manager (auto-tags all ai1stseo.com links), social orchestrator (direct publish), and DynamoDB scheduler (schedule for later).

## End-to-End Pipeline

```
Content Source → Repurposer → UTM Generator → Social Publisher → Scheduled Runner → Analytics Tracker
```

## Endpoints (Auth Required)

### POST /api/growth/content/repurpose

Generate a multi-platform content pack without publishing.

```json
{
  "content": "Your blog post or article text...",
  "platforms": ["x", "linkedin", "tiktok_script", "email_snippet"],
  "brand_name": "AI1stSEO",
  "source_url": "https://ai1stseo.com/blog/my-post",
  "campaign": "blog_launch"
}
```

`platforms` defaults to `["x", "linkedin", "tiktok_script", "email_snippet"]` if omitted.

Supported platforms: `x`, `linkedin`, `tiktok_script`, `email_snippet`, `x_thread`.

### POST /api/growth/content/repurpose-and-schedule

Repurpose + create scheduled posts in DynamoDB for social platforms (x, linkedin).

```json
{
  "content": "...",
  "platforms": ["x", "linkedin"],
  "schedule_datetime": "2026-05-01 10:00"
}
```

Omit `schedule_datetime` to create drafts.

### POST /api/growth/content/repurpose-and-publish

Repurpose + immediately publish via the social orchestrator (Buffer/Postiz).

```json
{
  "content": "...",
  "platforms": ["x", "linkedin"]
}
```

## UTM Auto-Tagging

All `ai1stseo.com` URLs in generated content are automatically tagged with:
- `utm_source` = platform name (e.g. `x`, `linkedin`)
- `utm_medium` = `social` or `email`
- `utm_campaign` = campaign parameter

## Analytics

Tracks `content_repurposed` event with platform list and success/failure counts. Publishing also triggers `publish_attempted`/`publish_succeeded`/`publish_failed` via the orchestrator.

## Files

- `growth/content_repurposer.py` — repurposing logic
- `growth/growth_api.py` — 3 new endpoints
- `growth/utm_manager.py` — UTM link tagging (existing)
- `growth/social_orchestrator.py` — publish routing (existing)
- `growth/social_scheduler_dynamo.py` — post scheduling (existing)
