# Task C: Samarveer (Dev 2) Integration Points

## What Samarveer Built (Branch: `dev2-samar-merge`)

1. Citation Gap Analysis — 10th SEO category (20 checks)
2. Content Scoring Engine — `/api/content-score` endpoint
3. Content Brief Generator — `/api/content-brief` endpoint with LLM fallback
4. Content Brief Persistence — RDS tables (`content_briefs`, `brief_competitors`, `brief_keywords`)
5. LLM Fallback Chain — Nova Lite → Ollama sageaios → Ollama databi → raw SERP

## Integration Points with Dev 4

### 1. Content Generator Pipeline (Shared Dependency)

Both Dev 2 and Dev 4 use `ai_provider.py` for AI content generation:
- Dev 2: `call_llm()` in app.py for content briefs
- Dev 4: `content_generator.py` imports `ai_provider.generate()` for FAQ/comparison/meta content

**No conflict.** Dev 4's `content_generator.py` is a standalone module that imports from `ai_provider.py`. It does not modify any of Samarveer's code.

### 2. Social Post Content → Content Scoring

Potential future integration: before publishing a social post, run it through Samarveer's content scoring engine to get an SEO/AEO quality score.

**Current status:** Not implemented. This would be a nice-to-have feature where the scheduler calls `/api/content-score` before publishing.

**No blocker.** This is additive work that can be done after both Dev 2 and Dev 4 branches are merged.

### 3. CORS Origins

Samarveer added `https://automationhub.ai1stseo.com` to CORS. Dev 4 has not modified CORS settings. No conflict.

## What Dev 4 Does NOT Touch

- `call_llm()` function
- Ollama URLs or model names
- Content brief endpoints or persistence
- Citation gap analysis
- `db.py` functions
- `audit.html` or `analyze.html`

## Dependencies / Blockers

**None.** Dev 4's work is fully isolated from Dev 2. The social scheduler, publishing bridges, and integration docs are all in separate files that don't overlap with Samarveer's content/NLP work.

## Note for Samarveer

> Hey Samarveer — Dev 4 (Tabasum) here. My social scheduler and publishing bridges are fully isolated from your content scoring and brief generator work. I use `ai_provider.py` via `content_generator.py` but don't modify it. No conflicts expected on merge. If you want, we could later add a content quality check step before social posts get published — your `/api/content-score` endpoint would be perfect for that. Let me know if you need anything from my side.
