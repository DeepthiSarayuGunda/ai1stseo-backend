# Implementation Plan: Growth Analytics Tracker (DynamoDB Enhancement)

## Overview

Enhance the existing `growth/analytics_tracker.py` module with UTM-enriched event tracking, event type validation, input sanitization, in-memory rate limiting, multi-dimensional summary grouping, and graceful DynamoDB failure handling. Update `growth/growth_api.py` to pass UTM fields and map HTTP status codes. Create module documentation. All changes isolated to three files.

## Tasks

- [x] 1. Add constants, imports, and helper functions to analytics_tracker.py
  - [x] 1.1 Add `import time` and define new constants: `ALLOWED_EVENT_TYPES` frozenset (7 event types), `MAX_STRING_LENGTH = 2048`, `RATE_LIMIT_MAX_EVENTS = 20`, `RATE_LIMIT_WINDOW_SECONDS = 60`, and `_session_event_log: dict[str, list[float]] = {}`
    - _Requirements: 1.4, 5.6_

  - [x] 1.2 Implement `_sanitize(value: str, lowercase: bool = True) -> str` helper
    - Strip leading/trailing whitespace, optionally lowercase, truncate to `MAX_STRING_LENGTH`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 1.3 Implement `_check_rate_limit(session_id: str) -> bool` helper
    - Sliding window: prune timestamps older than `RATE_LIMIT_WINDOW_SECONDS`, check count against `RATE_LIMIT_MAX_EVENTS`, append current timestamp if allowed
    - Uses `time.time()` for timestamps and `_session_event_log` dict for state
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.6_

  - [ ]* 1.4 Write property test: sanitization idempotency (Property 2)
    - **Property 2: Sanitization is idempotent**
    - Using `hypothesis`, verify `_sanitize(_sanitize(s, lc), lc) == _sanitize(s, lc)` for arbitrary strings and both lowercase values
    - **Validates: Requirement 3.6**

  - [ ]* 1.5 Write property test: sanitization correctness (Property 3)
    - **Property 3: Sanitization correctness (strip, lowercase, truncate)**
    - Verify output has no leading/trailing whitespace, length ≤ MAX_STRING_LENGTH, and is lowercased when `lowercase=True`
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

- [x] 2. Enhance track_event() with validation, UTM fields, rate limiting, and graceful failure
  - [x] 2.1 Rewrite `track_event()` to add UTM parameters (`page_url`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`), validate `event_type` against `ALLOWED_EVENT_TYPES`, call `_check_rate_limit()` when `session_id` is present (log warning when absent), sanitize all string fields via `_sanitize()`, store UTM fields as top-level DynamoDB attributes, and return `"Analytics unavailable"` on DynamoDB exceptions
    - Server-generated `created_at` and `event_id` (existing behavior preserved)
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 5.1, 5.2, 5.3, 7.1_

  - [ ]* 2.2 Write property test: event type validation (Property 1)
    - **Property 1: Event type validation is complete**
    - Verify all `ALLOWED_EVENT_TYPES` members succeed and arbitrary strings not in the set are rejected
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [ ]* 2.3 Write property test: UTM fields stored as top-level attributes (Property 4)
    - **Property 4: UTM fields stored as top-level attributes**
    - Mock `_get_table().put_item` and verify UTM fields appear as top-level keys, not nested in `event_data`
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 2.4 Write property test: rate limit boundary (Property 7)
    - **Property 7: Rate limit boundary**
    - Verify that after exactly 20 calls with the same session_id within 60s, the 21st is rejected
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 2.5 Write property test: rate limit session independence (Property 8)
    - **Property 8: Rate limit session independence**
    - Exhaust rate limit for session A, verify session B can still track events
    - **Validates: Requirement 5.5**

  - [ ]* 2.6 Write property test: no session_id bypasses rate limit (Property 9)
    - **Property 9: No session_id bypasses rate limit**
    - Verify calls with `session_id=None` are never rate-limited
    - **Validates: Requirement 5.3**

  - [ ]* 2.7 Write property test: server-generated timestamps (Property 12)
    - **Property 12: Server-generated timestamps and IDs**
    - Verify `created_at` is valid ISO 8601 UTC and `event_id` is valid UUID4 on every successful call
    - **Validates: Requirements 4.1, 4.2**

- [x] 3. Enhance get_summary() with 5-dimension grouping and graceful failure
  - [x] 3.1 Rewrite `get_summary()` to group events by 5 dimensions: `by_type`, `by_date` (YYYY-MM-DD from `created_at`), `by_source`, `by_utm_source`, `by_utm_campaign`. Only include events with `created_at >= cutoff`. Return `"Analytics unavailable"` on DynamoDB exceptions.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.2_

  - [ ]* 3.2 Write property test: summary total invariant (Property 5)
    - **Property 5: Summary total invariant**
    - Verify `total_events == sum(by_type.values())` for any set of mock items
    - **Validates: Requirement 6.3**

  - [ ]* 3.3 Write property test: summary grouping correctness (Property 6)
    - **Property 6: Summary grouping correctness**
    - Verify all 5 grouping dicts are correct for a generated set of items, events without optional fields are omitted from corresponding dicts
    - **Validates: Requirements 6.1, 6.2, 6.4, 6.5**

- [x] 4. Checkpoint — Verify analytics_tracker.py changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update growth_api.py for UTM pass-through and status code mapping
  - [x] 5.1 Update the `track()` endpoint to extract `page_url`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` from request JSON and pass them to `track_event()`. Silently ignore any client-provided `created_at` or `event_id` fields. Map response errors: `"Invalid event_type"` or `"event_type is required"` → HTTP 400, `"Rate limit exceeded"` → HTTP 429, `"Analytics unavailable"` → HTTP 503, success → HTTP 201.
    - _Requirements: 4.3, 4.4, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 5.2 Update the `analytics_summary()` endpoint to return HTTP 503 when `get_summary()` returns `"Analytics unavailable"` error, and HTTP 200 on success with the full multi-dimensional response.
    - _Requirements: 8.6_

  - [ ]* 5.3 Write property test: HTTP status code mapping (Property 13)
    - **Property 13: HTTP status code mapping**
    - Using Flask test client, verify 201 on success, 400 on validation error, 429 on rate limit, 503 on DynamoDB failure for the track endpoint; 200 on success and 503 on failure for the summary endpoint
    - **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 8.6**

  - [ ]* 5.4 Write property test: graceful DynamoDB failure (Property 11)
    - **Property 11: Graceful DynamoDB failure**
    - Mock DynamoDB exceptions in both `track_event` and `get_summary`, verify `"Analytics unavailable"` error and HTTP 503
    - **Validates: Requirements 7.1, 7.2, 7.3**

- [x] 6. Checkpoint — Verify growth_api.py changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Create docs/ANALYTICS_TRACKER_MODULE.md
  - [x] 7.1 Create module documentation covering: module purpose, ALLOWED_EVENT_TYPES list, track_event() signature with all UTM parameters, get_summary() response shape with 5 grouping dimensions, rate limiting behavior (20 events/60s per session), sanitization rules, error responses, and example curl commands for both endpoints
    - _Requirements: 9.1_

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use the `hypothesis` library (Python)
- All changes are isolated to `growth/analytics_tracker.py`, `growth/growth_api.py`, and `docs/ANALYTICS_TRACKER_MODULE.md` per Requirement 9
