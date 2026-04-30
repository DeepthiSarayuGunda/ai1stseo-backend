# Performance Optimizer Module

## Purpose

Closes the feedback loop: Generation → Publishing → Tracking → Analysis → Optimization → Generation. Analyzes content performance, scores posts, identifies winning patterns, and feeds optimization signals back into the content pipeline.

## Feedback Loop

```
Content Pipeline → Repurposer → Scheduler → Publisher → Analytics
       ↑                                                    ↓
       └──── Optimization Signals ←── Performance Analyzer ←┘
```

## API Endpoints (All Auth Required)

### Scoring

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/growth/performance/score` | Score a post's performance metrics |
| GET | `/api/growth/performance/top-posts` | Top performing posts by score |

### Analysis

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/growth/performance/platforms` | Platform performance rankings |
| GET | `/api/growth/performance/patterns` | Content type pattern analysis |
| GET | `/api/growth/performance/signals` | Optimization signals for the pipeline |
| GET | `/api/growth/performance/dashboard` | Full performance dashboard |

## Scoring Formula

```
base = engagements × 3 + clicks × 2 + conversions × 5
ctr_bonus = (clicks / impressions × 10) if impressions > 0
score = base + ctr_bonus
```

### Score a post

```bash
curl -X POST https://ai1stseo.com/api/growth/performance/score \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"post_id": "abc123", "clicks": 45, "impressions": 1200, "engagements": 30, "conversions": 3, "platform": "linkedin", "content_type": "thread"}'
```

## Optimization Signals

The `GET /performance/signals` endpoint returns:

```json
{
  "preferred_platforms": ["linkedin", "x"],
  "preferred_formats": ["thread", "short_post"],
  "platform_weights": {"linkedin": 0.6, "x": 0.4},
  "generation_hints": [
    "Prioritize linkedin — highest avg engagement score.",
    "Best performing format: thread. Generate more of this type."
  ],
  "has_data": true
}
```

When no performance data exists yet, default signals are returned:
- Prioritize X threads and LinkedIn posts
- Use hooks: questions, stats, contrarian takes
- Include clear CTAs with UTM-tagged links

## Pipeline Integration

The content pipeline (`run_content_pipeline`) automatically:
1. Fetches optimization signals before processing
2. Reorders platforms by performance ranking
3. Includes `optimization_applied` and `optimization_hints` in the response

This means the system improves automatically as performance data accumulates.

## Files

- `growth/performance_optimizer.py` — scoring, analysis, signals
- `growth/content_pipeline.py` — consumes signals (existing, extended)
- `growth/growth_api.py` — 6 new endpoints (existing, extended)
