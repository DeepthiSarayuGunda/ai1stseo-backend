# TikTok Video Posting — API Research & Feasibility Report

**Date:** April 1, 2026
**Author:** dev4 (automated research)
**Status:** Research complete — NO project files modified
**Decision:** DELAY — not suitable for current demo (see dev4-docs/J_TIKTOK_API_FEASIBILITY.md)

---

## 1. Can we post videos via API? — YES (with conditions)

TikTok provides an official **Content Posting API** as part of the TikTok for Developers platform.
It supports programmatic video upload and publishing to TikTok accounts.

Two publishing flows exist:
- **Direct Post** — publishes content immediately to a user's TikTok profile
- **Upload to Inbox (Creator Post)** — sends video to user's TikTok inbox for manual review before publishing

Two upload methods:
- `FILE_UPLOAD` — upload video file in chunks from local storage
- `PULL_FROM_URL` — provide a URL to a video hosted on a verified domain

Sources: [TikTok Content Posting API Get Started](https://developers.tiktok.com/doc/content-posting-api-get-started/), [TikTok Content Sharing Guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)

---

## 2. What is required to enable it

| Requirement | Details |
|---|---|
| TikTok Developer Account | Free registration at developers.tiktok.com |
| Registered App | Must create an app on TikTok for Developers portal |
| Content Posting API product | Must be added to the app |
| Direct Post configuration | Must be enabled in app settings |
| OAuth 2.0 | Required — user must authorize app with `video.publish` scope |
| App Audit/Review | Required to lift private-only restriction (1–4 weeks) |
| UX Requirements | TikTok mandates specific UI elements (creator info display, privacy dropdown, consent declaration) |

---

## 3. What is blocked right now

### Without app approval (sandbox/unverified mode):
- All uploaded content is **restricted to private viewing mode** (SELF_ONLY)
- Maximum **5 users** can post in a 24-hour window
- All user accounts must be set to **private** at time of posting
- Content cannot be made public until account owner manually changes settings

### After app approval (audited):
- 24-hour active creator cap (based on usage estimates in audit application)
- ~15 posts per day per creator account (shared across all API clients)
- Must comply with strict UX guidelines (creator info display, privacy selection, consent)
- No watermarks, branding, or promotional content allowed on videos
- App must be intended for wide audience — internal/private tools are explicitly **not acceptable**

### Key blocker for our project:
> TikTok explicitly states: *"A utility tool to help upload contents to the account(s) you or your team manages"* is **NOT acceptable** use of the API.

This means a tool built purely for our own team's posting needs would likely be rejected during audit.

---

## 4. Test performed

### Simulated API flow (no real API calls — no credentials available)

See `tiktok_flow_simulation.py` in this directory. The script demonstrates:
- The complete OAuth flow structure
- Creator info query request/response format
- Video upload initialization (FILE_UPLOAD and PULL_FROM_URL)
- Chunk upload process
- Post status polling
- All required request headers and payload structures

**No fake results were generated. No real API calls were made.**

---

## 5. Complexity level — HIGH

| Factor | Complexity |
|---|---|
| Developer account setup | Low |
| App registration | Low |
| OAuth 2.0 implementation | Medium |
| Chunk upload implementation | Medium |
| Async status polling | Medium |
| App audit/approval process | High (1–4 weeks, may be rejected) |
| UX compliance requirements | High (mandatory UI elements) |
| Ongoing maintenance | High (API changes, token refresh, rate limits) |
| **Overall** | **HIGH** |

Industry estimate: 40–50 hours of developer time for full integration.
Source: [bundle.social](https://bundle.social/blog/tiktok-api-integration-cost)

---

## 6. Recommendation: DELAY

### Reasoning:
1. **Approval risk** — TikTok explicitly rejects internal/team-only posting tools. Our use case may not pass audit.
2. **Time investment** — 40–50 hours for full integration is significant for uncertain ROI.
3. **Sandbox limitations** — Without audit approval, we can only post private videos to 5 users. Not demo-worthy.
4. **UX requirements** — TikTok mandates specific UI elements that would require frontend work beyond just API integration.
5. **Not suitable for demo** — Private-only videos in sandbox mode cannot demonstrate real value.

### When it would make sense:
- If the project pivots to a public-facing social media management tool with multiple users
- If a TikTok business account is available and the team is willing to go through the audit process
- If video content generation is already a core feature and TikTok is a priority distribution channel

### Alternative worth considering:
- **Postiz** or **Buffer** (already explored in this project) may support TikTok posting as part of their platform, avoiding the need to build direct API integration
- Third-party APIs like Zernio or Bundle Social abstract away TikTok's complexity into simpler REST calls

---

## Summary

| Question | Answer |
|---|---|
| Can we post videos via API? | YES — official Content Posting API exists |
| What is required? | Dev account, app registration, OAuth, app audit (1–4 weeks) |
| What is blocked? | App audit required for public posts; internal tools explicitly rejected |
| Test performed | Flow simulation only (no credentials) |
| Complexity | HIGH |
| Recommendation | **DELAY** — not worth the effort right now |
