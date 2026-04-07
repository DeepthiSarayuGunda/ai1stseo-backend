# Postiz Self-Hosted — Integration Notes

## How Postiz Fits Into Our Backend

Our current system uses `buffer_publisher.py` to send posts via Buffer's GraphQL API. Postiz provides a REST API that can serve as a drop-in replacement or run alongside Buffer.

### Current Architecture

```
┌──────────────────────┐
│  Social Scheduler    │  (social_posts table, data_api.py)
│  CRUD + scheduling   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  buffer_publisher.py │  → Buffer GraphQL API → Twitter/X, IG, FB, LinkedIn
└──────────────────────┘
```

### Proposed Architecture (Postiz Added)

```
┌──────────────────────┐
│  Social Scheduler    │
│  CRUD + scheduling   │
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────────┐
│  Buffer  │ │  Postiz      │
│  (legacy)│ │  Self-Hosted │
└──────────┘ └──────────────┘
     │              │
     ▼              ▼
  3 channels    32+ channels
```

---

## Postiz Public API Reference

Base URL (self-hosted): `http://<EC2_IP>:4007/api/public/v1`

### Authentication

All requests require the API key in the `Authorization` header:

```
Authorization: your-api-key
```

Generate the key in Postiz UI: Settings > Developers > Public API.

### Key Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/integrations` | List connected social accounts |
| POST | `/posts` | Create or schedule a post |
| POST | `/upload` | Upload media (images/video) |

### List Integrations

```bash
curl -H "Authorization: YOUR_API_KEY" \
  http://<EC2_IP>:4007/api/public/v1/integrations
```

Response:
```json
[
  {
    "id": "abc123",
    "name": "My LinkedIn Page",
    "providerIdentifier": "linkedin-page",
    "disabled": false
  },
  {
    "id": "def456",
    "name": "@myhandle",
    "providerIdentifier": "x",
    "disabled": false
  }
]
```

### Create / Schedule a Post

```bash
curl -X POST http://<EC2_IP>:4007/api/public/v1/posts \
  -H "Authorization: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "schedule",
    "date": "2026-04-01T10:00:00.000Z",
    "shortLink": false,
    "tags": [],
    "posts": [
      {
        "integration": { "id": "abc123" },
        "value": [
          {
            "content": "Hello from our scheduler!",
            "image": []
          }
        ],
        "settings": {
          "__type": "linkedin"
        }
      }
    ]
  }'
```

### Post Types

| `type` value | Behavior |
|-------------|----------|
| `"now"` | Publish immediately |
| `"schedule"` | Publish at the specified `date` |
| `"draft"` | Save as draft (no publishing) |

### Platform Settings (`__type` values)

| Platform | `__type` | Extra Settings |
|----------|----------|----------------|
| Twitter/X | `x` | `who_can_reply_post`: "everyone" / "following" / "mentioned" |
| LinkedIn | `linkedin` | None required |
| LinkedIn Page | `linkedin-page` | None required |
| Facebook | `facebook` | None required |
| Instagram | `instagram` | `post_type`: "post" / "reel" / "story" |
| Threads | `threads` | None required |
| Bluesky | `bluesky` | None required |
| Mastodon | `mastodon` | None required |
| TikTok | `tiktok` | `privacy_level`, `disable_comment`, `disable_duet`, `disable_stitch` |
| YouTube | `youtube` | `title`, `description`, `privacy`: "public"/"private"/"unlisted" |

---

## Integration with Our Scheduler

### Option 1: Use Existing `postiz_publisher.py` (Already Built)

We already have `postiz_publisher.py` in the project root. To point it at the self-hosted instance instead of Postiz Cloud:

```bash
# In your .env or environment variables:
POSTIZ_API_KEY=your-self-hosted-api-key
POSTIZ_API_URL=http://<EC2_IP>:4007/api/public/v1

# Integration IDs (get from GET /integrations after connecting accounts)
POSTIZ_INTEGRATION_X=integration-id-for-twitter
POSTIZ_INTEGRATION_LI=integration-id-for-linkedin
POSTIZ_INTEGRATION_FB=integration-id-for-facebook
POSTIZ_INTEGRATION_IG=integration-id-for-instagram
```

The existing `postiz_publisher.py` already supports:
- `publish()` — post now or schedule
- `list_integrations()` — fetch connected accounts
- `build_payload()` — construct API payloads
- Platform mapping (our names → Postiz `__type`)

No code changes needed — just update the env vars.

### Option 2: Dual Publishing (Buffer + Postiz)

Run both publishers in parallel during evaluation:

```python
# In data_api.py publish handler:
from buffer_publisher import publish_post as buffer_publish
from postiz_publisher import publish_post as postiz_publish

# Publish to Buffer (existing channels)
if buffer_is_configured():
    buffer_result = buffer_publish(content, platform)

# Also publish to Postiz (new channels or all)
if postiz_is_configured():
    postiz_result = postiz_publish(content, platform)
```

### Option 3: Full Migration to Postiz

Replace Buffer entirely. Update the scheduler to use only `postiz_publisher.py`:

```python
# In data_api.py:
from postiz_publisher import publish_post, is_configured

# Single publisher path
if is_configured():
    result = publish_post(content, platform, scheduled_at=scheduled_time)
```

---

## Webhook / Callback Status

As of the current Postiz version, there is **no built-in webhook system** for post delivery notifications. Options for tracking post status:

1. **Poll the API** — Periodically check post status (not ideal)
2. **Check Temporal UI** — Visual inspection at `http://<EC2_IP>:8080` for workflow status
3. **Database query** — Since we own the Postiz PostgreSQL database, we could query it directly (fragile, not recommended)
4. **Feature request** — The Postiz team is actively developing; webhook support may come in future versions

For our use case, the simplest approach is to treat the API call as fire-and-forget and log the response. If the API returns success, the post is queued in Temporal and will be delivered reliably.

---

## Multi-Platform Posting

Postiz supports posting to multiple platforms in a single API call:

```json
{
  "type": "schedule",
  "date": "2026-04-01T10:00:00.000Z",
  "shortLink": false,
  "tags": [],
  "posts": [
    {
      "integration": { "id": "linkedin-id" },
      "value": [{ "content": "Post text here", "image": [] }],
      "settings": { "__type": "linkedin" }
    },
    {
      "integration": { "id": "x-id" },
      "value": [{ "content": "Post text here", "image": [] }],
      "settings": { "__type": "x", "who_can_reply_post": "everyone" }
    },
    {
      "integration": { "id": "threads-id" },
      "value": [{ "content": "Post text here", "image": [] }],
      "settings": { "__type": "threads" }
    }
  ]
}
```

This is a significant advantage over Buffer, where you post to one channel at a time.

---

## Image/Media Upload Flow

```bash
# Step 1: Upload the file
curl -X POST http://<EC2_IP>:4007/api/public/v1/upload \
  -H "Authorization: YOUR_API_KEY" \
  -F "file=@image.jpg"

# Response: { "id": "img-abc", "path": "http://<EC2_IP>:4007/uploads/image.jpg" }

# Step 2: Reference in post payload
{
  "value": [{
    "content": "Check this out!",
    "image": [{ "id": "img-abc", "path": "http://<EC2_IP>:4007/uploads/image.jpg" }]
  }]
}
```

---

## CLI Tool

Postiz also provides a CLI (`@postiz/cli`) for terminal-based automation:

```bash
npx @postiz/cli posts:create \
  --integration linkedin-id \
  --content "Hello from CLI" \
  --type now \
  --api-key YOUR_KEY \
  --base-url http://<EC2_IP>:4007/api/public/v1
```

Useful for cron jobs or CI/CD pipelines.

---

## Security Considerations

| Concern | Recommendation |
|---------|----------------|
| API key exposure | Store in AWS Secrets Manager or SSM Parameter Store, not in code |
| Public access to Postiz UI | Restrict security group to your IP range, or put behind VPN |
| OAuth callback URLs | Use HTTPS in production (Nginx + Let's Encrypt) |
| Database access | PostgreSQL is not exposed externally (Docker internal network) |
| Temporal UI | Restrict port 8080 to your IP only |

---

## Cost Estimate (AWS)

| Resource | Monthly Cost |
|----------|-------------|
| t3.medium EC2 (on-demand) | ~$30 |
| 30GB gp3 EBS | ~$2.40 |
| Data transfer (minimal) | ~$1 |
| **Total** | **~$33/month** |

With Reserved Instances or Savings Plans, this drops to ~$20/month. Compared to Buffer's paid plans ($6-120/month per channel), self-hosted Postiz is significantly cheaper for multiple channels.

---

## Recommended Next Steps

1. Deploy Postiz on EC2 using `deploy_postiz.sh`
2. Connect LinkedIn and Twitter/X accounts for initial testing
3. Set `POSTIZ_API_URL` in our backend to point at the self-hosted instance
4. Run `postiz_publisher.py` dry-run tests against the self-hosted API
5. Run parallel publishing (Buffer + Postiz) for 2 weeks
6. Evaluate reliability, then decide on full migration
