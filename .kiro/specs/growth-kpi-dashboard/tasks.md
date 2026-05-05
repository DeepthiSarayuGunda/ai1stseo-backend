# Implementation Plan: Growth KPI Dashboard

## Overview

Create a lightweight dashboard aggregator module, wire it into the existing growth Blueprint as an authenticated endpoint, and add module documentation. Three files touched: one new (`growth/growth_dashboard.py`), one modified (`growth/growth_api.py`), one new (`docs/GROWTH_DASHBOARD_MODULE.md`). No new dependencies, no app.py changes, no frontend work.

## Tasks

- [x] 1. Create the dashboard aggregator module
  - [x] 1.1 Create `growth/growth_dashboard.py` with `get_dashboard_kpis(days)` function
    - Import `get_summary` from `growth.analytics_tracker` and `list_subscribers` from `growth.email_subscriber`
    - Clamp `days` parameter to [1, 90] range
    - Call `get_summary(days)` inside try/except; on failure set `analytics_available=False` and zero all analytics fields
    - Call `list_subscribers(page=1, per_page=10000)` inside try/except; on failure set `subscribers_available=False` and zero subscriber fields
    - Compute `new_subscribers` by filtering subscribers whose `subscribed_at` falls within the `days` window from current UTC time
    - Extract `lead_magnet_downloads`, `welcome_email_attempted`, `welcome_email_sent`, `welcome_email_failed` from `by_type` dict with `.get()` defaulting to 0
    - Pass through `by_type`, `by_utm_source`, `by_utm_campaign` as `top_event_types`, `top_utm_sources`, `top_utm_campaigns`
    - Set `generated_at` to current UTC time in ISO 8601 format
    - Wrap entire function body in outer try/except that returns `{"success": false, "error": "Dashboard aggregation failed"}` and logs at ERROR level
    - Log individual data source failures at WARNING level
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 2. Checkpoint — Verify aggregator module
  - Ensure `growth/growth_dashboard.py` is syntactically valid and imports resolve correctly, ask the user if questions arise.

- [x] 3. Add the dashboard endpoint to growth_api.py
  - [x] 3.1 Add `GET /api/growth/dashboard` route to `growth/growth_api.py`
    - Add a new `dashboard()` view function decorated with `@growth_bp.route("/dashboard", methods=["GET"])` and `@require_auth`
    - Parse `days` query parameter with `int()`, defaulting to 7 on `ValueError`/`TypeError`
    - Late-import `get_dashboard_kpis` from `growth.growth_dashboard` (consistent with existing late-import pattern in the file)
    - Return 200 with JSON on `success: true`, 500 on `success: false`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.4_

- [x] 4. Checkpoint — Verify endpoint wiring
  - Ensure `growth/growth_api.py` has no syntax errors and the new route is properly registered, ask the user if questions arise.

- [x] 5. Create module documentation
  - [x] 5.1 Create `docs/GROWTH_DASHBOARD_MODULE.md`
    - Document the `GET /api/growth/dashboard` endpoint: URL, method, auth requirement, `days` query parameter
    - Include a complete example JSON response matching the KPI response schema from the design
    - List all KPI fields with data types and source descriptions
    - Describe graceful degradation behavior when analytics or subscriber data sources are unavailable
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 6. Final checkpoint — Ensure all files are complete
  - Verify `growth/growth_dashboard.py`, `growth/growth_api.py`, and `docs/GROWTH_DASHBOARD_MODULE.md` are all syntactically valid and consistent with each other. Ensure no changes were made to `app.py`. Ask the user if questions arise.

## Notes

- Phase 1 is manual testing only — no hypothesis or automated test tasks
- No new dependencies are introduced
- No `app.py` modifications
- All code is isolated to `growth/` and `docs/`
- Checkpoints ensure incremental validation
- Each task references specific requirements for traceability
