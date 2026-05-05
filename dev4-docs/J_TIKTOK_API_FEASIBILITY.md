# J — TikTok API Feasibility Report

**Date:** April 1, 2026
**Status:** Research complete — DELAY recommended

---

## Summary

- TikTok's official **Content Posting API** supports programmatic video posting (upload from file or URL).
- Real integration requires: TikTok developer account, registered app, OAuth 2.0 authorization, and a formal app audit/review by TikTok (1–4 weeks).
- TikTok enforces strict UX compliance — mandatory creator info display, privacy dropdown with no defaults, and user consent declaration.
- Without audit approval, posting is **private-only** (SELF_ONLY), limited to 5 users per day. Not demo-worthy.
- TikTok explicitly rejects internal/team-only posting tools during audit — our current use case is at risk of rejection.
- Complexity is **HIGH** (industry estimate: 40–50 hours for full integration).
- **Recommendation: DELAY.** Not suitable for current demo. Revisit if project scope expands to public-facing social media management.

## Isolated Test Files

- `dev4-tiktok-tests/tiktok_api_research.md` — Full research report with API details, requirements, and limitations
- `dev4-tiktok-tests/tiktok_flow_simulation.py` — Simulation of the complete API flow (no real calls, no credentials)

## Alternatives

- Postiz or Buffer (already explored) may support TikTok posting as part of their platforms, avoiding direct API work.
