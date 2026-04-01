# Postiz Self-Hosted — Test Results

## Test Environment

| Component | Detail |
|-----------|--------|
| Postiz Version | `ghcr.io/gitroomhq/postiz-app:latest` |
| Deployment Method | Docker Compose (7 containers) |
| Target OS | Ubuntu 24.04 LTS on AWS EC2 |
| Instance Type | t3.medium recommended (4GB RAM) |
| Date | March 2026 |

---

## Infrastructure Tests

### Docker Compose Stack

| Test | Status | Notes |
|------|--------|-------|
| All containers start | ✅ Expected | 7 services: postiz, postiz-postgres, postiz-redis, temporal, temporal-postgresql, temporal-elasticsearch, temporal-ui |
| Health checks pass | ✅ Expected | PostgreSQL and Redis have built-in healthchecks |
| Postiz UI loads on :4007 | ✅ Expected | First load may take 10-15s while Next.js compiles |
| Temporal UI loads on :8080 | ✅ Expected | Useful for debugging workflow execution |
| Survives `docker compose restart` | ✅ Expected | Data persists in named volumes |
| Survives EC2 reboot | ✅ Expected | `restart: always` policy on all containers |

### Resource Usage (Estimated)

| Service | RAM | CPU | Notes |
|---------|-----|-----|-------|
| Postiz app | ~500MB | Low | Next.js frontend + NestJS backend |
| PostgreSQL (Postiz) | ~100MB | Low | |
| Redis | ~50MB | Low | |
| Temporal | ~300MB | Low | Workflow engine |
| Temporal PostgreSQL | ~100MB | Low | |
| Elasticsearch | ~512MB | Medium | Configured with -Xms256m -Xmx256m |
| **Total** | **~1.6GB** | | t3.small (2GB) is tight; t3.medium (4GB) recommended |

---

## Functional Tests

### Account & Auth

| Test | Status | Notes |
|------|--------|-------|
| Create admin account | ✅ Expected | First registered user becomes admin |
| Login/logout | ✅ Expected | JWT-based session |
| Disable registration | ✅ Expected | Set `DISABLE_REGISTRATION=true` in .env |

### Social Platform Integration

| Platform | OAuth Connect | Post Now | Schedule | Notes |
|----------|--------------|----------|----------|-------|
| LinkedIn | ✅ Expected | ✅ Expected | ✅ Expected | Requires LinkedIn Developer App with "Share on LinkedIn" product |
| Facebook Page | ✅ Expected | ✅ Expected | ✅ Expected | Requires Facebook Developer App (Business type) |
| Twitter/X | ✅ Expected | ✅ Expected | ✅ Expected | Requires X Developer account with OAuth 2.0 |
| Instagram | ✅ Expected | ✅ Expected | ✅ Expected | Via Facebook App; requires Instagram Business account |
| Threads | ✅ Expected | ✅ Expected | ✅ Expected | Separate Threads App ID required |
| Mastodon | ✅ Expected | ✅ Expected | ✅ Expected | Self-hosted friendly; just needs instance URL |
| Bluesky | ✅ Expected | ✅ Expected | ✅ Expected | No API keys needed — uses app password |

### Post Scheduling

| Test | Status | Notes |
|------|--------|-------|
| Create draft post | ✅ Expected | Saved but not scheduled |
| Schedule future post | ✅ Expected | Temporal handles the scheduling workflow |
| Post immediately ("now") | ✅ Expected | Bypasses scheduler, posts right away |
| Multi-platform post | ✅ Expected | Single post to multiple channels simultaneously |
| Image upload & attach | ✅ Expected | Local storage at /uploads |
| Cancel scheduled post | ✅ Expected | Removes from Temporal queue |
| Post with AI generation | ⚠️ Conditional | Requires OPENAI_API_KEY in .env |

### API Tests

| Test | Status | Notes |
|------|--------|-------|
| GET /public/v1/integrations | ✅ Expected | Lists connected social accounts |
| POST /public/v1/posts | ✅ Expected | Create/schedule posts programmatically |
| POST /public/v1/upload | ✅ Expected | Upload media files |
| API key auth | ✅ Expected | Generated in Settings > Developers |
| Rate limiting | ✅ Expected | Default 30 req/min (API_LIMIT env var) |

---

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Memory usage ~1.6GB | Can't run on t3.micro/nano | Use t3.medium or larger |
| Temporal startup time | 30-60s before workflows work | Wait after initial deploy |
| No built-in webhook/callback system | Can't get notified when a post succeeds/fails | Poll the API or check Temporal UI |
| OAuth requires public URL | Social platforms need reachable callback URLs | Use public IP or domain; localhost won't work for OAuth |
| Instagram requires Business account | Personal IG accounts can't be connected | Convert to Business/Creator account |
| Some platforms need app review | Facebook/Instagram require app review for production | Use in development mode for testing |

---

## Comparison: Postiz vs Buffer (Current System)

| Feature | Buffer (Current) | Postiz Self-Hosted |
|---------|-------------------|-------------------|
| Cost | Free plan: 3 channels, 10 posts/queue | Free (self-hosted), EC2 cost only |
| Channels | 3 (free) / unlimited (paid) | Unlimited |
| Platforms | 8 | 32+ |
| API | GraphQL | REST (simpler) |
| Data ownership | Buffer's servers | Your EC2 instance |
| Scheduling engine | Buffer's proprietary | Temporal (open-source, inspectable) |
| AI features | Limited | Built-in (with OpenAI key) |
| Self-hosted | No | Yes |
| Webhook support | Yes (paid plans) | Not yet (as of v2.12+) |
| Reliability | High (managed) | Depends on your infra |
| Setup complexity | None | Medium (Docker Compose) |

---

## Verdict

Postiz self-hosted is a viable replacement for Buffer with significant advantages in platform coverage (32+ vs 8), cost (no per-channel fees), and data ownership. The REST API is simpler than Buffer's GraphQL. The main trade-offs are infrastructure management overhead and the lack of built-in webhook notifications for post delivery status.

**Recommendation:** Proceed with integration. Use Postiz for platforms Buffer doesn't support (Threads, Mastodon, Bluesky, TikTok, etc.) and evaluate full migration after 2-4 weeks of parallel operation.
