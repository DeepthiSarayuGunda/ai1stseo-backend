# AI SEO Starter Kit — Email Subscriber Capture System

**Status:** LIVE on ai1stseo.com
**Date:** April 7, 2026
**Owner:** Tabasum (Dev 4)
**Branch:** dev4-tabasum-integrations (merged to main)

---

## What Was Built

A complete email subscriber capture system for the ai1stseo.com 5-month growth plan. This is the first growth feature — captures email subscribers from the homepage and stores them in DynamoDB for future email marketing campaigns.

## Live Demo

1. Go to https://www.ai1stseo.com
2. Scroll past the stats bar (236 / 10 / PDF / 24/7)
3. See the "Get the AI SEO Starter Kit" section
4. Enter an email and click Subscribe
5. Green success message appears
6. Try the same email again — shows "already subscribed"

## What Was Delivered

### 1. Growth Plan Audit
- Audited the entire codebase against the 5-month growth plan
- Produced a detailed gap report: `docs/AI1STSEO_5_MONTH_IMPLEMENTATION_GAP_REPORT.md`
- Identified email subscriber capture as the #1 priority gap
- Mapped existing systems, missing systems, risk areas, and recommended build order

### 2. Email Subscriber Capture Module
- New isolated `growth/` directory — no existing code was modified
- Backend API with 3 endpoints:
  - POST /api/growth/subscribe (public — captures subscribers)
  - GET /api/growth/subscribers (admin — paginated list with filters)
  - GET /api/growth/subscribers/export (admin — CSV or JSON export)
- Email validation, input sanitization, duplicate prevention
- Source/platform/campaign tracking on every subscriber
- UTM parameter attribution (utm_source, utm_medium, utm_campaign, utm_content)

### 3. Homepage Integration
- Email capture section added to the live ai1stseo.com homepage
- Placed after the stats bar, styled to match the homepage design
- Dark theme, cyan accent, centered layout — looks native
- Standalone fallback script (`assets/growth-email-capture.js`) prevents removal
- Works on both local development and production

### 4. DynamoDB Migration
- Migrated subscriber storage from PostgreSQL to DynamoDB
- Works on App Runner without RDS dependency
- Table: `ai1stseo-email-subscribers`
- Partition key: email (enforces uniqueness)
- GSI: source-subscribed_at-index (for filtering)
- PAY_PER_REQUEST billing (no provisioned capacity)

### 5. Email Platform Sync Hook
- `growth/email_platform_sync.py` — placeholder for future Brevo/MailerLite integration
- Called after every successful subscribe (non-blocking)
- Passes email, name, source, platform, campaign, subscriber_id, timestamp
- Ready to wire up when email provider credentials are available

### 6. Local Development Setup
- app.py serves index.html on localhost instead of redirecting to ai1stseo.com
- Local PostgreSQL support for development (DynamoDB for production)
- Test script: `test_growth_subscribe.py`

## Files Created

| File | Purpose |
|------|---------|
| `growth/__init__.py` | Package init, exports growth_bp |
| `growth/email_subscriber.py` | Core module: validation, CRUD, export, DynamoDB |
| `growth/growth_api.py` | Flask Blueprint with 3 API endpoints + admin UI |
| `growth/email_platform_sync.py` | Email provider integration hook (placeholder) |
| `growth/subscribers.html` | Admin subscriber management UI |
| `assets/growth-email-capture.js` | Standalone homepage email capture script |
| `docs/AI1STSEO_5_MONTH_IMPLEMENTATION_GAP_REPORT.md` | Full audit report |
| `docs/EMAIL_SUBSCRIBER_MODULE.md` | Technical documentation |
| `docs/PRODUCTION_EMAIL_CAPTURE_SNIPPET.html` | Production-ready HTML snippet |
| `s3-index-patched.html` | Patched production homepage with email capture |
| `deploy-homepage.ps1` | S3 + CloudFront deploy script |
| `deploy-now.ps1` | Quick deploy with inline credentials |
| `iam-dynamodb-policy.json` | IAM policy for AppRunnerRole |
| `test_growth_subscribe.py` | Endpoint test script |

## Files Modified

| File | Change |
|------|--------|
| `app.py` | Added growth Blueprint registration (~6 lines) + localhost serve fix |
| `index.html` | Added email capture injection script + standalone script tag |

## Architecture

```
Homepage (S3/CloudFront)
  |
  | POST /api/growth/subscribe
  v
App Runner (Flask)
  |
  | growth/growth_api.py -> growth/email_subscriber.py
  v
DynamoDB (ai1stseo-email-subscribers)
  |
  | (future) growth/email_platform_sync.py
  v
Brevo / MailerLite (not connected yet)
```

## DynamoDB Table Schema

Table: `ai1stseo-email-subscribers`

| Field | Type | Notes |
|-------|------|-------|
| email | String (PK) | Partition key, enforces uniqueness |
| id | String | UUID |
| name | String | Optional |
| source | String | e.g. "website_main", "landing_page" |
| platform | String | e.g. "landing_page", "homepage_footer" |
| campaign | String | Optional campaign tag |
| utm_source | String | From URL params |
| utm_medium | String | From URL params |
| utm_campaign | String | From URL params |
| utm_content | String | From URL params |
| opted_in | Boolean | Default true |
| status | String | "active" |
| subscribed_at | String | ISO timestamp |
| updated_at | String | ISO timestamp |

## Environment Variables

| Variable | Default | Required |
|----------|---------|----------|
| GROWTH_SUBSCRIBERS_TABLE | ai1stseo-email-subscribers | No |
| AWS_REGION | us-east-1 | No |
| EMAIL_PLATFORM | (empty) | No — for future Brevo/MailerLite |
| EMAIL_PLATFORM_API_KEY | (empty) | No — for future integration |

## IAM Permissions (AppRunnerRole)

Policy name: `DynamoDBGrowthSubscribers`
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:Scan",
      "dynamodb:Query",
      "dynamodb:CreateTable",
      "dynamodb:DescribeTable"
    ],
    "Resource": "arn:aws:dynamodb:us-east-1:823766426087:table/ai1stseo-email-subscribers*"
  }]
}
```

## Git Commits

| Commit | Description |
|--------|-------------|
| 10e0401 | Initial growth module + Blueprint registration + subscribe endpoint |
| 0d814d8 | Homepage email capture, UTM attribution, email platform sync, local dev serve, deploy script |
| d96265c | Migrate subscriber module from PostgreSQL to DynamoDB |
| 977febf | Add safe DynamoDB logging, fix duplicate exception handler |
| cb9a1d0 | Add standalone growth-email-capture.js for stable homepage section |

## What's Next

1. Welcome email automation — wire SES to send a welcome email after subscribe
2. Drip campaign integration — connect Brevo or MailerLite via the sync hook
3. Social scheduler DynamoDB migration — move from SQLite to DynamoDB
4. Content repurposing engine integration — Dev 2 building this, will feed into scheduler
5. Analytics event tracking — log subscribe events for conversion tracking
6. A/B testing on the homepage CTA copy

## Team Coordination Notes

- SES email system is live (set up by teammate) — marketing@ai1stseo.com sends/receives
- Dev 2 is building content repurposing engine — needs social scheduler JSON format
- Social scheduler is still on SQLite — DynamoDB migration planned next
- No social platforms are connected for actual posting yet (Postiz, Buffer, Reddit all need credentials)


---

## AI Photo & Video Generation Research

As part of the growth plan, I evaluated three approaches for generating marketing images and videos for social media content.

### 1. Local AI (ComfyUI Server) — SUCCESS

Tested image and video generation on a remote ComfyUI server (Tesla P40 GPU, 24GB VRAM).

**What worked:**
- SDXL image generation for marketing banners and social media graphics
- SVD video generation (14-frame animated banners)
- Two-step workflow: SDXL generates text-free backgrounds, then Pillow adds crisp text overlays
- Final banners are demo-ready with proper fonts, drop shadows, and CTA buttons

**Key finding:** AI models can't render readable text in images. The solution is to generate backgrounds with AI, then overlay text programmatically. This produces sharp, professional results.

**Output files:** `dev4-local-ai-tests/outputs/` — includes final banners, backgrounds, raw SDXL images, and SVD video

**Scripts built:**
- `comfy_test.py` — main ComfyUI test
- `gen_backgrounds.py` — batch background generation
- `add_text_overlay.py` — text overlay with Pillow
- `svd_test.py` — video generation
- `batch_generate_v2.py` — batch image generation
- `gen_demo_video.py` — demo video generation

**Full report:** `dev4-local-ai-tests/local_ai_results.md`

### 2. Amazon Bedrock (Nova Canvas, Titan Image, Nova Reel) — BLOCKED

Tested AWS Bedrock image/video models. All 4 models are authorized in Bedrock console but blocked by an explicit IAM deny on `bedrock:InvokeModel` in the SSO permission set.

**Models tested:**
- Amazon Nova Canvas (image, ~$0.04-0.08/image)
- Amazon Titan Image Gen v2 (image, ~$0.01/image — cheapest)
- Amazon Nova Reel v1:0 and v1:1 (video, ~$0.80/6s clip)

**Status:** Scripts are ready to run (`amazon_test.py`, `generate_samples.py`) but waiting for admin to remove the explicit deny on `bedrock:InvokeModel` from the PowerUserAccess SSO permission set.

**Full report:** `dev4-amazon-tests/amazon_results.md`

### 3. TikTok Video Posting API — DELAYED (Not Recommended Now)

Researched TikTok's Content Posting API for automated video publishing.

**Key findings:**
- API exists and supports programmatic video upload
- Requires developer account, app registration, OAuth 2.0, and app audit (1-4 weeks)
- TikTok explicitly rejects internal/team-only posting tools — our use case may not pass audit
- Sandbox mode only allows private videos to 5 users — not demo-worthy
- Estimated 40-50 hours of developer time for full integration
- Recommendation: DELAY — use Postiz or Buffer for TikTok posting instead

**Full report:** `dev4-tiktok-tests/tiktok_api_research.md`

### Summary

| Approach | Status | Best For |
|----------|--------|----------|
| Local AI (ComfyUI) | Working | Background images, banners, short video clips |
| Amazon Bedrock | Blocked (IAM) | Production-quality images at scale (once unblocked) |
| TikTok API | Delayed | Not recommended now — use Postiz/Buffer instead |

**Recommended production workflow:** Generate backgrounds with AI (ComfyUI or Bedrock), overlay text with Pillow, use the content repurposing engine to create platform-specific versions, schedule via the social scheduler.
