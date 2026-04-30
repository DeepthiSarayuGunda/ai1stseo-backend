# Content Pipeline Module

## Purpose

Automated content production system that feeds the repurposing pipeline continuously. Content goes in, platform-specific scheduled posts come out.

## Full Pipeline Flow

```
Content Source (DynamoDB) → Pipeline Runner → Repurposer → UTM Tagger → Scheduler → Runner → Publisher → Analytics
```

## Modules

- `growth/content_source_manager.py` — content queue (DynamoDB CRUD)
- `growth/content_pipeline.py` — pipeline runner + seed importer
- `growth/content_repurposer.py` — AI-powered content transformation (existing)
- `growth/utm_manager.py` — auto UTM tagging (existing)
- `growth/social_scheduler_dynamo.py` — post scheduling (existing)

## API Endpoints (All Auth Required)

### Content Sources

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/growth/content/sources` | Add content to pipeline queue |
| GET | `/api/growth/content/sources` | List content items (?status=new) |
| GET | `/api/growth/content/sources/<id>` | Get single content item |

### Pipeline Operations

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/growth/content/pipeline/run` | Run the pipeline (fetch → repurpose → schedule) |
| POST | `/api/growth/content/pipeline/import-seeds` | Import social_media_posts.json as seed content |

## Usage

### 1. Add content to the queue

```bash
curl -X POST https://ai1stseo.com/api/growth/content/sources \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Your blog post text...", "title": "My Blog Post", "source_type": "blog"}'
```

### 2. Run the pipeline

```bash
curl -X POST https://ai1stseo.com/api/growth/content/pipeline/run \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "dry_run": false}'
```

### 3. Import seed content (one-time)

```bash
curl -X POST https://ai1stseo.com/api/growth/content/pipeline/import-seeds \
  -H "Authorization: Bearer TOKEN"
```

## Scheduling Strategy

- X/Twitter: up to 5 posts/day (09:00, 12:00, 15:00, 18:00, 21:00 UTC)
- LinkedIn: 1 post/day (10:00 UTC)
- TikTok scripts and email snippets: generated but not auto-scheduled

Posts are scheduled starting tomorrow to avoid immediate publishing. The scheduler avoids time slot conflicts with existing posts.

## Content Statuses

| Status | Meaning |
|--------|---------|
| new | Queued, not yet processed |
| processing | Currently being repurposed |
| processed | Repurposed and scheduled |
| failed | Repurposing failed |

## Dashboard Integration

The KPI dashboard (`GET /api/growth/dashboard`) now includes:
- `content_repurposed` — count of repurpose events
- `publish_attempted` / `publish_succeeded` / `publish_failed` — publish metrics
- `pipeline` — content queue stats (total, new, processed, failed)
