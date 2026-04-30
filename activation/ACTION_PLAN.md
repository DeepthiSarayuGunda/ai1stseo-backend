# Growth Activation Action Plan

Backend engine: ~90% complete. Growth execution: ~15% complete.
Goal: Move from backend-ready → live growth system.

## Execution Order

### PHASE 1 — Activate Social Publishing (Day 1)

**What:** Connect real social accounts so the orchestrator can publish.

**Steps:**
1. Sign up at https://buffer.com (free plan, 3 channels)
2. Connect LinkedIn + X accounts in Buffer dashboard
3. Copy API key from Buffer Settings > API
4. Copy channel IDs from Buffer Settings > Channels
5. Set environment variables:
```powershell
$env:BUFFER_API_KEY="your-buffer-api-key"
$env:BUFFER_CHANNEL_LI="your-linkedin-channel-id"
$env:BUFFER_CHANNEL_X="your-x-channel-id"
```
6. Validate: `python activation/setup_social_env.py`
7. Test: `python activation/test_publish.py linkedin`

**Visible after:** Real posts appearing on LinkedIn/X from the backend.

---

### PHASE 2 — Activate Content Pipeline (Day 2-3)

**What:** Load existing content into the scheduler and start publishing.

**Steps:**
1. Preview: `python activation/import_posts_to_scheduler.py --dry-run`
2. Import: `python activation/import_posts_to_scheduler.py`
3. Verify: Check DynamoDB table for scheduled posts
4. Dry run: Call `POST /api/growth/social/run-scheduled` with `{"dry_run": true}`
5. Publish: Call `POST /api/growth/social/run-scheduled` with `{"dry_run": false}`

**Visible after:** 10+ posts scheduled across 5 days, auto-publishing via runner.

---

### PHASE 3 — Activate Email Nurture (Week 2)

**What:** Extend welcome email to a 3-email sequence.

**Files to create:**
- `growth/email_sequence.py` — sequence definitions + runner
- Modify `growth/growth_api.py` — add trigger endpoint

**Sequence:**
- Day 0: Welcome email (already works)
- Day 3: Value email (SEO tips + tool link)
- Day 7: Case study email (success story + CTA)

**Visible after:** Subscribers receive 3 emails over 7 days automatically.

---

### PHASE 4 — Add Dashboard UI (Week 2-3)

**What:** Simple HTML page that displays KPI metrics.

**Files to create:**
- `growth/dashboard.html` — single-page dashboard

**Displays:**
- Total subscribers
- New subscribers (7d)
- Lead magnet downloads
- Welcome emails sent/failed
- Posts published
- Top UTM sources

**Visible after:** Team can view growth metrics in a browser.

---

## Scripts Created

| File | Purpose | Command |
|------|---------|---------|
| `activation/setup_social_env.py` | Validate social credentials | `python activation/setup_social_env.py` |
| `activation/test_publish.py` | Send 1 test post | `python activation/test_publish.py linkedin` |
| `activation/import_posts_to_scheduler.py` | Load content into scheduler | `python activation/import_posts_to_scheduler.py` |

## What Changes After Each Phase

| Phase | What Becomes Live |
|-------|-------------------|
| Phase 1 | Real social posts published from backend |
| Phase 2 | 10+ posts auto-scheduled and publishing over 5 days |
| Phase 3 | 3-email nurture sequence for every new subscriber |
| Phase 4 | Visual dashboard showing all growth metrics |

## Bottom Line

System moves from backend-complete → growth-active after Phase 1 + 2.
Phase 1 requires ~1 hour of account setup (zero code changes).
Phase 2 requires running one script (zero code changes).
