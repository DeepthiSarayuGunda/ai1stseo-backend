# Postiz Integration — Evaluation & Status Report

## What Is Postiz?

Postiz is an open-source social media scheduling platform that supports 28+ channels. It can be self-hosted via Docker or used as a cloud service. It includes AI content generation, a public REST API, a CLI tool, and OAuth2 support for third-party integrations.

Source: [postiz.com](https://postiz.com) | [GitHub](https://github.com/gitroomhq/postiz-app) | [Docs](https://docs.postiz.com)

## Platform Support

| Platform | Postiz Support | Current Scheduler |
|----------|---------------|-------------------|
| Instagram | Yes (via Meta Business or standalone) | No (stores only, no publishing) |
| Twitter/X | Yes (OAuth1 for media, v2 API) | No (stores only, no publishing) |
| Facebook | Yes (Pages only) | No (stores only, no publishing) |
| LinkedIn | Yes (profiles and pages) | No (stores only, no publishing) |
| Threads | Yes | No |
| TikTok | Yes | No |
| YouTube | Yes | No |
| Reddit | Yes | No |
| Bluesky | Yes | No |
| Pinterest | Yes | No |
| Discord/Slack/Telegram | Yes | No |

Postiz supports all four target platforms (Instagram, Twitter/X, Facebook, LinkedIn) plus 20+ more.

## Setup Requirements

### Option A: Self-Hosted (Docker Compose)

Requirements:
- Docker + Docker Compose
- 2GB RAM minimum, 2 vCPUs
- PostgreSQL (included in compose)
- Redis (included in compose)
- Temporal workflow engine (included in compose)
- HTTPS required (secure cookies) — needs reverse proxy (Nginx/Caddy) with SSL
- Platform API keys for each social network

Environment variables needed:
- `JWT_SECRET` — random string
- `DATABASE_URL` — PostgreSQL connection
- `REDIS_URL` — Redis connection
- `X_API_KEY` / `X_API_SECRET` — from Twitter Developer Portal
- `FACEBOOK_APP_ID` / `FACEBOOK_APP_SECRET` — from Meta Developer Portal (covers Instagram + Facebook)
- `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` — from LinkedIn Developer Portal

### Option B: Postiz Cloud (Hosted)

- Free 7-day trial
- Standard: $29/month (5 channels, 100 posts/month)
- Team: $39/month (15 channels, 500 posts/month)
- Pro: $49/month (unlimited channels, unlimited posts)
- No Docker/server setup needed
- API key from Settings > Developers > Public API

### Option C: Public API Integration (Recommended for AI1stSEO)

Instead of self-hosting Postiz or replacing the current scheduler, integrate via the Postiz Public API. This lets the existing scheduler remain as the content management layer while Postiz handles the actual publishing.

API base: `https://api.postiz.com/public/v1`
Auth: API key in `Authorization` header

Key endpoints:
- `GET /integrations` — list connected social accounts
- `POST /posts` — create/schedule a post
- `POST /upload` — upload images
- `GET /posts` — list scheduled posts

## Instagram Setup (via Postiz)

1. Create a Meta for Developers account at developers.facebook.com
2. Create a new app with "Business" type
3. Add "Instagram Graph API" and "Facebook Login for Business" products
4. Configure OAuth redirect URL to Postiz callback
5. Set `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` in Postiz config
6. Connect Instagram account through Postiz UI (Facebook Business link or standalone)

Note: Instagram requires a Business or Creator account, not a personal account.

## Twitter/X Setup (via Postiz)

1. Apply for a Twitter Developer account at developer.twitter.com
2. Create a project and app
3. Set app permissions to "Read and Write"
4. Generate Consumer Keys (API Key + Secret)
5. Set `X_API_KEY` and `X_API_SECRET` in Postiz config
6. Connect X account through Postiz UI (OAuth1 flow)

Note: X uses OAuth1 (not OAuth2) because media upload requires the v1 API.

## Comparison: Current Scheduler vs Postiz

| Feature | Current Scheduler | Postiz |
|---------|------------------|--------|
| Store draft posts | Yes | Yes |
| Schedule posts | Yes (stores datetime) | Yes (actually publishes at scheduled time) |
| Publish to platforms | No — no API integration | Yes — publishes via platform APIs |
| Image upload | Yes (local storage) | Yes (local or Cloudflare R2) |
| Multi-platform posting | No | Yes (28+ platforms in one post) |
| AI content generation | Separate (content_generator.py) | Built-in AI features |
| Analytics | No | Basic engagement metrics |
| CRUD API | Yes (/api/data/social-posts) | Yes (Public API) |
| Auth | Cognito (existing) | Separate auth (JWT) |
| Cost | Free (self-built) | Free (self-hosted) or $29-49/month (cloud) |
| Setup complexity | Already done | Docker + API keys + HTTPS |

## What Was Tested

1. Researched Postiz documentation, setup requirements, and API
2. Verified platform support for all four target platforms
3. Reviewed Docker Compose configuration requirements
4. Reviewed Public API endpoints and payload format
5. Compared feature set with current scheduler

## What Was Not Tested (Blockers)

- Docker is not installed on the current Windows development machine — cannot run self-hosted Postiz locally
- No Twitter/X Developer API keys available yet — cannot test X publishing
- No Meta Developer app configured yet — cannot test Instagram/Facebook publishing
- Postiz cloud trial not activated — cannot test cloud API

## Recommendation

### Short-term: Use Postiz Cloud API as a publishing bridge

1. Sign up for Postiz cloud (7-day free trial, then $29/month Standard)
2. Connect Instagram and Twitter/X accounts through the Postiz web UI
3. Get an API key from Settings > Developers
4. Add a small publishing function to the existing scheduler that calls the Postiz API when a post's status changes from "scheduled" to "publishing"
5. Keep the current scheduler as the content management and drafting layer

This approach:
- Requires zero infrastructure changes
- Keeps the existing CRUD system intact
- Adds real publishing capability to Instagram and Twitter/X immediately
- Can be extended to LinkedIn and Facebook later
- Costs $29/month vs building and maintaining platform API integrations from scratch

### Medium-term: Self-host Postiz on AWS

If the cloud cost becomes a concern or you need more control:
- Deploy Postiz via Docker on an EC2 instance or ECS
- Use the existing RDS PostgreSQL (or a separate one)
- Set up HTTPS via ALB or Nginx
- Connect all platform API keys
- Integrate via the same Public API

### What NOT to do

- Don't replace the current scheduler — it works well for content management and CRUD
- Don't build custom platform API integrations from scratch — Postiz already handles the OAuth flows, token refresh, rate limits, and media upload for 28+ platforms
- Don't self-host Postiz on the local dev machine — it needs Docker, HTTPS, and persistent services

## Files Changed

None. This was an evaluation only — no code was modified.

## Next Steps

1. Sign up at [platform.postiz.com](https://platform.postiz.com)
2. Connect Instagram and Twitter/X accounts
3. Get API key
4. Test posting via the API with one of the draft posts from `social_media_posts.json`
5. If successful, add a `publish_to_postiz()` function to the scheduler backend
