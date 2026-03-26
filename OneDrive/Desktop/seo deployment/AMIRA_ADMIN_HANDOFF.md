# Admin Dashboard — Handoff for Amira
## March 24, 2026

Everything is wired up and ready for you to customize. Here's what's been built:

## What's Ready

### 1. Admin Dashboard Page (`admin.html`)
- Accessible at `/admin` on the main site
- Uses the same dark theme, gradient, and design system as `audit.html`
- Auth-gated: checks `/api/admin/me` — only shows dashboard if `role === 'admin'`
- Non-admins see a "🔒 Admin Access Required" message
- 6 tabs: Overview, Users, Usage, AI Costs, Errors, Health
- All tabs are functional and wired to the backend API

### 2. Backend API Endpoints (all require admin role)
| Endpoint | What it returns |
|----------|----------------|
| `GET /api/admin/overview` | User count, scan volume, avg score, errors, monitored sites |
| `GET /api/admin/users?limit=25&offset=0` | Paginated user list with scan counts |
| `PUT /api/admin/users/<id>/role` | Change user role (admin/member) |
| `GET /api/admin/usage?days=30` | Daily scan volume + top scanned URLs |
| `GET /api/admin/ai-costs?days=30` | AI provider breakdown, daily trend, cost by trigger |
| `GET /api/admin/metrics?days=30` | Historical aggregated daily metrics |
| `GET /api/admin/errors?hours=48` | Recent scan errors with resolution status |
| `GET /api/admin/health` | Uptime %, avg response time, error count |
| `GET /api/admin/me` | Current user's role (used for auth gate) |

### 3. AI Usage Tracking
- Both `backend/ai_inference.py` and `openclaw-site-monitor/ai_inference.py` now log every AI call
- Tracks: provider, model, token estimates, cost, latency, success/failure, trigger type
- Data flows into `ai_usage_log` table → feeds the AI Costs tab

### 4. Daily Aggregation Job
- `backend/admin_aggregation.py` runs via EventBridge at 02:00 UTC
- Rolls up all metrics into `admin_metrics` table
- Feeds the Overview tab's "Daily Metrics" table

### 5. Navigation
- Admin Dashboard link added to Tools dropdown on both `index.html` and `audit.html`
- Shows in orange (#ff9800) to distinguish from regular tools

## What You Can Customize

- Tab layout, card styling, chart visualizations (currently tables — you could add Chart.js)
- Mobile responsiveness tweaks
- Additional filters (date range pickers, search)
- Export to CSV/PDF buttons
- Real-time refresh intervals

## Database Tables to Create (run once on RDS)
```bash
psql -h ai1stseo-db.ca5mm2skodf2.us-east-1.rds.amazonaws.com -U ai1stseo_admin -d ai1stseo -f backend/admin_tables.sql
```

## Files Changed
- `admin.html` — NEW: complete admin dashboard
- `backend/admin_api.py` — added `/api/admin/ai-costs` and `/api/admin/metrics`
- `backend/admin_aggregation.py` — NEW: EventBridge daily aggregation Lambda
- `backend/admin_tables.sql` — NEW: DDL for 3 new tables
- `backend/ai_inference.py` — added AI usage logging
- `openclaw-site-monitor/ai_inference.py` — added AI usage logging
- `backend/template.yaml` — added AdminAggregationFunction with cron schedule
- `backend/app.py` — added `/admin` route
- `index.html` — added admin link to Tools dropdown
- `audit.html` — added admin link to Tools dropdown
