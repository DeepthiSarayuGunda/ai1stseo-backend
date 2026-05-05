# Implementation Plan: Scheduled Publishing Runner

## Overview

Implement a batch-publish runner module (`growth/publish_runner.py`) that scans the existing DynamoDB social posts table for overdue scheduled posts, splits multi-platform posts into individual calls, and routes each through `social_orchestrator.publish_post()`. Add a manual trigger endpoint (`POST /api/growth/social/run-scheduled`) to `growth_api.py`, register two new analytics event types, and create developer documentation. All code is Python (Flask). No new dependencies, no changes to `app.py`, no new DynamoDB tables.

## Tasks

- [x] 1. Register runner analytics event types
  - [x] 1.1 Add `runner_batch_started` and `runner_batch_completed` to `ALLOWED_EVENT_TYPES` in `growth/analytics_tracker.py`
    - Append the two new strings to the existing `frozenset`
    - Do not modify any other logic in the module
    - _Requirements: 7.3_

- [x] 2. Create the publish runner module
  - [x] 2.1 Create `growth/publish_runner.py` with `_get_due_posts()` helper
    - Import `get_posts` from `growth.social_scheduler_dynamo`
    - Implement `_get_due_posts()` that calls `get_posts()`, filters to posts where `status == "scheduled"` and `scheduled_datetime` (parsed as `"YYYY-MM-DD HH:MM"` UTC) is less than or equal to `datetime.now(timezone.utc)`
    - Posts with unparseable `scheduled_datetime` should be collected as skipped entries with a parse-error result (`success=False`, descriptive error message)
    - Posts with empty or missing `platforms` field should be collected as skipped entries with a missing-platform result (`success=False`)
    - Return `(due_posts, skipped_entries)` tuple
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.3_

  - [x] 2.2 Add `_split_platforms()` and `_build_payload()` helpers to `growth/publish_runner.py`
    - `_split_platforms(post)` splits the `platforms` comma-separated string, trims whitespace, lowercases each entry, returns `list[str]`
    - `_build_payload(post, platform)` constructs `{"post_id": post["post_id"], "content": post["content"], "platform": platform, "scheduled_at": post["scheduled_datetime"]}`
    - _Requirements: 2.1, 2.2, 3.1_

  - [x] 2.3 Implement `run_scheduled_posts(dry_run=False)` in `growth/publish_runner.py`
    - Call `_get_due_posts()` to get due posts and skipped entries
    - Track `runner_batch_started` event via `analytics_tracker.track_event()` with `event_data` containing `dry_run` and `total_due` (wrap in try/except, non-blocking)
    - For each due post, call `_split_platforms()` then for each platform:
      - If `dry_run=False`: call `social_orchestrator.publish_post(_build_payload(post, platform))`, catch exceptions per-platform-entry, record result
      - If `dry_run=True`: record result with `success=None` and `error=None` without calling the Orchestrator
    - Track `runner_batch_completed` event with `event_data` containing `dry_run`, `total_due`, `succeeded`, `failed`, `skipped` (wrap in try/except, non-blocking)
    - Return BatchSummary dict: `{"success": True, "dry_run": bool, "total_due": int, "total_publish_attempts": int, "succeeded": int, "failed": int, "skipped": int, "results": [...]}`
    - Each result entry: `{"post_id": str, "platform": str, "success": bool|None, "error": str|None}`
    - `succeeded + failed` must equal `total_publish_attempts`; top-level `success` is always `True` when the function completes
    - If no due posts found, return summary with all counts at zero
    - _Requirements: 1.2, 1.5, 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 7.1, 7.2_

  - [ ]* 2.4 Write property test for due post filtering
    - **Property 1: Due post filtering**
    - **Validates: Requirements 1.2, 1.3, 1.4**

  - [ ]* 2.5 Write property test for platform splitting
    - **Property 2: Platform splitting produces correct count**
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 2.6 Write property test for publish payload construction
    - **Property 3: Publish payload construction**
    - **Validates: Requirements 3.1**

  - [ ]* 2.7 Write property test for result completeness
    - **Property 4: All platform entries produce results**
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 2.8 Write property test for batch summary consistency
    - **Property 5: Batch summary counts are consistent**
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 2.9 Write property test for top-level success invariant
    - **Property 6: Top-level success is always true on completion**
    - **Validates: Requirements 4.3**

  - [ ]* 2.10 Write property test for dry-run no side effects
    - **Property 7: Dry-run produces no side effects**
    - **Validates: Requirements 5.1, 5.3**

  - [ ]* 2.11 Write property test for dry-run result entries
    - **Property 8: Dry-run result entries have null success and error**
    - **Validates: Requirements 5.2**

  - [ ]* 2.12 Write property test for analytics event correctness
    - **Property 9: Analytics events contain correct data**
    - **Validates: Requirements 7.1, 7.2**

- [x] 3. Checkpoint - Ensure runner module is complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add the run-scheduled endpoint to growth API
  - [x] 4.1 Add `POST /api/growth/social/run-scheduled` endpoint in `growth/growth_api.py`
    - Add a new route function `social_run_scheduled()` decorated with `@growth_bp.route("/social/run-scheduled", methods=["POST"])` and `@require_auth`
    - Read `dry_run` from JSON body (default `False`)
    - Import and call `run_scheduled_posts(dry_run=dry_run)` from `growth.publish_runner`
    - Return HTTP 200 with BatchSummary JSON on success
    - Wrap in try/except: return HTTP 500 with `{"success": false, "error": "..."}` on unhandled exception
    - Do not remove or alter any existing endpoints
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.2_

- [x] 5. Create developer documentation
  - [x] 5.1 Create `docs/PUBLISH_RUNNER_MODULE.md`
    - Document module purpose and architecture overview
    - Document the `POST /api/growth/social/run-scheduled` endpoint (auth, request body, response codes)
    - Document dry-run mode usage
    - Document BatchSummary response format with field descriptions
    - Document analytics event types (`runner_batch_started`, `runner_batch_completed`) and their `event_data` schemas
    - Include manual testing examples with `curl` or PowerShell commands
    - _Requirements: 1.1, 4.1, 5.1, 6.1, 7.1_

- [x] 6. Final checkpoint - Ensure all code is wired and complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All code is Python targeting the existing Flask application
- No changes to `app.py` — the endpoint is registered via the existing `growth_bp` Blueprint
- No new dependencies — uses only existing imports (`boto3`, `flask`, `datetime`)
- No new DynamoDB tables — reuses `ai1stseo-social-posts` via `social_scheduler_dynamo`
- Manual testing only for Phase 1 (curl/PowerShell against running app)
- Property tests can be added in a future phase if `hypothesis` is introduced
