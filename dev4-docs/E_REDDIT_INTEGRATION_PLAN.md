# Task E: Reddit Integration — Feasibility & Plan

## Current Status

Reddit integration does NOT exist in the codebase. The only reference is in `postiz_integration_status.md` which notes that Postiz supports Reddit as one of its 32+ platforms, and `deploy_postiz.sh` has placeholder env vars `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.

## Feasibility: HIGH

Reddit has a well-documented API and a mature Python library (`praw`). Integration is straightforward for posting.

## API / Library Options

### Option A: PRAW (Python Reddit API Wrapper) — Recommended
- **Library:** `praw` (pip install praw)
- **Auth:** OAuth2 (script type for server-side)
- **Docs:** [praw.readthedocs.io](https://praw.readthedocs.io)
- **Posting:** `subreddit.submit(title, selftext=...)` for text posts
- **Rate limits:** 60 requests/minute (OAuth), 10 requests/minute (no auth)
- **Pros:** Mature, well-maintained, handles OAuth automatically
- **Cons:** Another dependency

### Option B: Via Postiz
- Postiz already supports Reddit natively
- If Postiz is deployed, Reddit posting works through the same API
- No additional code needed — just connect Reddit account in Postiz UI
- **Pros:** Zero code, unified publishing
- **Cons:** Requires Postiz deployment

### Option C: Direct Reddit API (requests)
- **Endpoint:** `https://oauth.reddit.com/api/submit`
- **Auth:** OAuth2 bearer token
- **Pros:** No extra dependency
- **Cons:** Must handle token refresh manually

## Posting Flow (PRAW)

```
1. User creates post in scheduler (status: "draft")
2. User approves post (status: "scheduled")
3. At scheduled time, system calls reddit_publisher.publish()
4. reddit_publisher:
   a. Authenticates via OAuth2 (PRAW handles this)
   b. Selects target subreddit
   c. Submits post (text or link)
   d. Returns post URL and ID
5. Scheduler updates status to "published" or "failed"
```

## Auth Approach

Reddit uses OAuth2 for API access. For a server-side "script" app:

1. Create a Reddit account (or use existing)
2. Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
3. Create a new app (type: "script")
4. Get `client_id` (under app name) and `client_secret`
5. Set env vars:
   ```
   REDDIT_CLIENT_ID=your-client-id
   REDDIT_CLIENT_SECRET=your-client-secret
   REDDIT_USERNAME=your-reddit-username
   REDDIT_PASSWORD=your-reddit-password
   REDDIT_USER_AGENT=ai1stseo-scheduler/1.0
   ```

## API Limits

| Limit | Value |
|-------|-------|
| Requests/minute (OAuth) | 60 |
| Requests/minute (no auth) | 10 |
| Post rate limit | ~1 post per 10 minutes for new accounts |
| Subreddit-specific rules | Varies (some require karma, account age) |
| Self-promotion rules | Reddit's site-wide rule: max 10% self-promotional content |

## Risks

1. **Self-promotion policy:** Reddit actively penalizes accounts that only post promotional content. The AI1stSEO posts are marketing-focused, which could trigger spam filters or bans.
2. **Subreddit rules:** Each subreddit has its own posting rules. Automated posting to the wrong subreddit will get the account banned.
3. **Account age/karma:** New accounts have severe rate limits and may not be able to post in many subreddits.
4. **Content format:** Reddit posts need to feel organic, not like ads. The current social media posts are too promotional for most subreddits.

## What Can Be Done Now

Since no Reddit credentials exist, I've created a stub integration module:

## Recommended Next Steps

1. Create a Reddit account specifically for AI1stSEO
2. Build karma organically (comment, engage) for 2-4 weeks
3. Identify target subreddits (r/SEO, r/digital_marketing, r/smallbusiness, r/startups)
4. Create Reddit Developer App at reddit.com/prefs/apps
5. Set environment variables
6. Test with `reddit_publisher.py` dry-run
7. Start with 1-2 posts per week, monitor reception

## Recommendation

**Short-term:** Use Postiz for Reddit posting (if deployed) — zero additional code.
**Medium-term:** Build `reddit_publisher.py` with PRAW for direct integration.
**Important:** Reddit requires a different content strategy than LinkedIn/Twitter. Posts should be educational/helpful, not promotional. Consider adapting the content calendar specifically for Reddit.
