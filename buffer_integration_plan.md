# Buffer Publishing Bridge — Integration Plan

## Why Buffer Over Postiz

- Buffer free plan includes API access (GraphQL) — Postiz requires a paid plan for meaningful use
- Buffer free plan: 3 channels, 10 posts per channel queue — enough for testing and demo
- Buffer supports all four target platforms: Instagram, Twitter/X, Facebook, LinkedIn
- Buffer API is simple (single GraphQL endpoint) and well-documented

## Buffer Free Plan Details

| Feature | Free Plan |
|---------|-----------|
| Channels | 3 (each connected social account = 1 channel) |
| Queue per channel | 10 posts |
| API access | Yes (1 API key) |
| Scheduling | Yes |
| Image posts | Yes (via URL) |
| Analytics | Basic only |
| Team members | 1 |

For demo purposes: connect Instagram + Twitter/X = 2 channels (1 remaining for LinkedIn or Facebook later).

## Integration Approach: API-Based (Option A)

Buffer provides a full GraphQL API on the free plan. No manual workflow needed.

```
┌─────────────────────────┐
│  Social Scheduler CRUD  │  existing system
│  social_scheduler.db    │
│  social_posts (Postgres)│
└──────────┬──────────────┘
           │ status change → "publishing"
           ▼
┌─────────────────────────┐
│  buffer_publisher.py    │  new bridge module
│  GraphQL mutations      │
└──────────┬──────────────┘
           │ POST https://api.buffer.com
           ▼
┌─────────────────────────┐
│  Buffer Cloud           │
│  Handles OAuth, tokens, │
│  platform APIs          │
└──────────┬──────────────┘
           ▼
   Instagram / X / FB / LinkedIn
```

## Setup Steps

### 1. Create Buffer Account
- Sign up at [buffer.com](https://buffer.com) (free)
- Verify email

### 2. Connect Social Channels
- Go to [publish.buffer.com/channels](https://publish.buffer.com/channels)
- Click "Connect a Channel"
- Connect Instagram (requires Business/Creator account)
- Connect Twitter/X (authorize via OAuth)

### 3. Get API Key
- Go to [publish.buffer.com/settings/api](https://publish.buffer.com/settings/api)
- Click "Generate API Key"
- Copy the key

### 4. Get Organization and Channel IDs
Run the helper:
```bash
set BUFFER_API_KEY=your-key-here
python buffer_publisher.py
```
This will print your organization ID and all connected channels with their IDs.

### 5. Set Environment Variables
```bash
BUFFER_API_KEY=your-api-key
BUFFER_ORG_ID=your-org-id
BUFFER_CHANNEL_X=channel-id-for-twitter
BUFFER_CHANNEL_IG=channel-id-for-instagram
```

## Post Format Mapping

| Our Field | Buffer Field | Notes |
|-----------|-------------|-------|
| caption | text | Direct mapping |
| hashtags | (appended to text) | Buffer doesn't have a separate hashtags field |
| platform | channelId | Resolved via env var |
| scheduled_at | dueAt | ISO 8601 datetime |
| image_url | assets.images[].url | Must be a publicly accessible URL |
| status | (mapped to mode) | "shareNow" or "customSchedule" |

Example: converting a post from `social_media_posts.json` to a Buffer API call:

```python
from buffer_publisher import publish_post

# Post from our JSON
post = {
    "platform": "Twitter/X",
    "caption": "You rank #1 on Google but ChatGPT doesn't know you exist.\n\nThat's not a bug. That's a visibility gap.\n\nAI1stSEO measures it. ai1stseo.com",
    "hashtags": ["#AISEO", "#AEO"]
}

# Combine caption + hashtags
text = post["caption"] + "\n\n" + " ".join(post["hashtags"])

# Publish
result = publish_post(text=text, platform="Twitter/X")
```

## Buffer GraphQL API Reference

Endpoint: `POST https://api.buffer.com`
Auth: `Authorization: Bearer YOUR_API_KEY`

### Create/Schedule a Post
```graphql
mutation CreatePost {
  createPost(input: {
    text: "Your post content here",
    channelId: "your-channel-id",
    schedulingType: automatic,
    mode: customSchedule,
    dueAt: "2026-04-01T10:00:00.000Z"
  }) {
    ... on PostActionSuccess {
      post { id text }
    }
    ... on MutationError {
      message
    }
  }
}
```

### Mode Options
| Mode | Behavior |
|------|----------|
| `shareNow` | Publish immediately |
| `addToQueue` | Add to Buffer's scheduling queue |
| `customSchedule` | Publish at specific `dueAt` time |

## Status Flow

```
draft → scheduled → publishing → published
                               → failed
```

| Status | Trigger |
|--------|---------|
| `draft` | Post created |
| `scheduled` | User approves post for publishing |
| `publishing` | Buffer API call initiated |
| `published` | Buffer API returns success |
| `failed` | Buffer API returns error |

## How to Test Posting

### Dry-run (no API key needed)
```bash
python buffer_publisher.py
```

### Live test with API key
```bash
set BUFFER_API_KEY=your-key
python buffer_publisher.py
```

### Publish a real post
```python
from buffer_publisher import BufferPublisher

pub = BufferPublisher()

# Post immediately to Twitter/X
result = pub.publish(
    text="Test from AI1stSEO scheduler #AISEO",
    platform="Twitter/X"
)
print(result)

# Schedule for later
result = pub.schedule(
    text="Scheduled test #AISEO",
    platform="Instagram",
    due_at="2026-04-01T10:00:00.000Z"
)
print(result)
```

## Limitations of Free Plan

- 10 posts per channel queue — once 10 are queued, must wait for some to publish before adding more
- 3 channels max — enough for Instagram + Twitter/X + one more
- 1 API key — sufficient for our use case
- No advanced analytics via API
- Instagram requires Business/Creator account (not personal)
- Facebook requires a Page (not personal profile)

## Demo Workflow

For a live demo with the team:

1. Set `BUFFER_API_KEY` and channel IDs as env vars
2. Pick 2-3 posts from `social_media_posts.json` (one Twitter/X, one Instagram)
3. Run:
```python
import json
from buffer_publisher import BufferPublisher

pub = BufferPublisher()

with open('social_media_posts.json') as f:
    posts = json.load(f)

# Find a Twitter/X post
for p in posts:
    if p['platform'] == 'Twitter/X':
        text = p['caption'] + '\n\n' + ' '.join(p['hashtags'])
        result = pub.publish(text=text, platform='Twitter/X')
        print(f"Twitter/X: {result}")
        break
```
4. Check Buffer dashboard to see the post in the queue
5. Check Twitter/X to see it published

## Files Created

| File | Purpose |
|------|---------|
| `buffer_publisher.py` | Publishing bridge — GraphQL client for Buffer API |
| `buffer_integration_plan.md` | This plan document |

No existing files were modified.

## Next Steps

1. Sign up for Buffer free account
2. Connect Instagram and Twitter/X channels
3. Generate API key
4. Run `python buffer_publisher.py` to get channel IDs
5. Set env vars and test with a real post
6. If successful, add a `/api/social/publish` endpoint to the scheduler
7. Add a "Publish" button to the scheduler UI
