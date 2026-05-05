# Implementation Plan: Social Publish Orchestrator

## Overview

Implement a thin orchestration layer in `growth/social_orchestrator.py` that bridges the social post scheduler with Buffer and Postiz publishers. Add an authenticated REST endpoint in `growth/growth_api.py`, register new analytics event types, and create developer documentation. All code is Python (Flask). No new dependencies, no changes to `app.py`.

## Tasks

- [x] 1. Add publish event types to analytics tracker
  - [x] 1.1 Add "publish_attempted", "publish_succeeded", "publish_failed" to `ALLOWED_EVENT_TYPES` in `growth/analytics_tracker.py`
    - Append the three new strings to the existing `frozenset`
    - Do not modify any other logic in the module
    - _Requirements: 6.1, 8.6_

- [x] 2. Create the social orchestrator module
  - [x] 2.1 Create `growth/social_orchestrator.py` with constants and `normalize_platform()`
    - Define `CANONICAL_PLATFORMS = {"linkedin", "x", "instagram", "facebook"}`
    - Define `PLATFORM_ALIASES = {"twitter": "x", "twitter/x": "x"}`
    - Implement `normalize_platform(raw)` that strips whitespace, lowercases, resolves aliases, and returns `(canonical, None)` on success or `(None, error_msg)` on failure
    - Error message format: `"Unsupported platform: {value}. Supported: linkedin, x, instagram, facebook"`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.2 Write property tests for `normalize_platform()`
    - **Property 1: Platform normalization produces canonical values**
    - **Property 2: Invalid platforms are rejected**
    - **Validates: Requirements 4.2, 4.4, 4.5**

  - [x] 2.3 Implement `discover_publisher()` in `growth/social_orchestrator.py`
    - Import `BufferPublisher` from `buffer_publisher` and `PostizPublisher` from `postiz_publisher`
    - Instantiate both publishers fresh (no singletons)
    - Check `.configured` property on each
    - Default to Buffer when both configured; prefer Postiz when `SOCIAL_PUBLISHER_PREFERENCE` env var is `"postiz"`
    - Return `(publisher_instance, provider_name)` or `(None, None)` when neither is configured
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.4 Implement `publish_post(payload)` in `growth/social_orchestrator.py`
    - Orchestrate the full lifecycle: normalize platform → discover publisher → track `publish_attempted` → call publisher `publish()` → update post status → track success/failure → return structured response
    - Adapt call signature per publisher: Buffer uses `text` + `due_at`, Postiz uses `content` + `scheduled_at`
    - Wrap analytics tracking and `update_post` calls in try/except (fire-and-forget, log warnings)
    - Wrap publisher `publish()` call in try/except for unexpected exceptions
    - Return dict with keys: `success`, `provider`, `result`, `error`, `status`
    - When no provider available: `{"success": False, "provider": None, "error": "No publisher configured", "status": "provider_unavailable"}`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 2.5 Write property tests for `publish_post()`
    - **Property 3: Payload fields are forwarded to the publisher**
    - **Property 4: Orchestrator result mirrors publisher outcome**
    - **Property 5: Response shape invariant**
    - **Property 7: Post status update matches publish outcome**
    - **Property 8: No status update without post_id**
    - **Property 9: Analytics lifecycle events match publish flow**
    - **Property 10: Unexpected exceptions produce structured error responses**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 5.1, 5.2, 5.4, 6.2, 6.3, 6.4, 7.1, 7.3, 7.4**

- [x] 3. Checkpoint - Ensure orchestrator module is complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add the publish endpoint to growth API
  - [x] 4.1 Add `POST /api/growth/social/publish` endpoint in `growth/growth_api.py`
    - Add a new route function `social_publish()` decorated with `@growth_bp.route("/social/publish", methods=["POST"])` and `@require_auth`
    - Validate `content` (required, non-empty) → HTTP 400 with `{"success": false, "error": "content is required"}`
    - Validate `platform` (required, non-empty) → HTTP 400 with `{"success": false, "error": "platform is required"}`
    - Import and call `publish_post()` from `growth.social_orchestrator`
    - Map orchestrator results to HTTP status codes: success → 200, no provider → 503, publisher error → 502
    - Do not remove or alter any existing endpoints
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 8.5_

  - [ ]* 4.2 Write property tests for the publish endpoint
    - **Property 6: Missing required fields return validation error**
    - **Validates: Requirements 3.5, 3.6**

- [x] 5. Create developer documentation
  - [x] 5.1 Create `docs/SOCIAL_ORCHESTRATOR_MODULE.md`
    - Document module purpose, architecture overview, and sequence diagram
    - Document the `POST /api/growth/social/publish` endpoint (auth, request body, response codes)
    - Document platform normalization rules and alias table
    - Document publisher discovery logic and `SOCIAL_PUBLISHER_PREFERENCE` env var
    - Document analytics event types and event_data schemas
    - Include manual testing examples with `curl` commands
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 3.1, 4.1, 4.3, 6.1_

- [x] 6. Final checkpoint - Ensure all code is wired and complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All code is Python targeting the existing Flask application
- No changes to `app.py` — the endpoint is registered via the existing `growth_bp` Blueprint
- No new dependencies — uses only existing imports (`boto3`, `requests`, `flask`)
- Manual testing only for Phase 1 (curl against running app)
- Property tests use `hypothesis` if added in a future phase
