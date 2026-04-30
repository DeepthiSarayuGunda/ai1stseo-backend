# Implementation Plan: Lead Magnet Delivery System

## Overview

Implement a static lead magnet registry in `growth/lead_magnet.py`, add two new public endpoints and modify `subscribe()` in `growth/growth_api.py`, add `lead_magnet_downloaded` to the analytics tracker's allowed event types, and create developer documentation. All work is isolated to `growth/` and `docs/`.

## Tasks

- [x] 1. Create `growth/lead_magnet.py` with static registry and core functions
  - [x] 1.1 Create `growth/lead_magnet.py` with module docstring, `_LEAD_MAGNETS` static registry, and `validate_lead_magnet()` function
    - Define the `_LEAD_MAGNETS` list with the initial `seo-starter-checklist` entry
    - Implement `validate_lead_magnet(entry)` — checks all 5 required fields are non-empty strings and `download_url` starts with `https://`
    - _Requirements: 6.1, 6.2, 7.1, 8.1_

  - [x] 1.2 Implement `_check_unique_ids()`, `get_lead_magnets()`, and `get_lead_magnet_by_slug()`
    - `_check_unique_ids(magnets)` — filters duplicate IDs, keeps first occurrence, logs warnings
    - `get_lead_magnets()` — calls `_check_unique_ids()` then `validate_lead_magnet()` on each entry, excludes invalid entries with `logger.warning`
    - `get_lead_magnet_by_slug(slug)` — case-insensitive lookup (normalize to lowercase), returns `None` if not found
    - _Requirements: 6.3, 6.4, 6.5, 7.2, 7.3, 7.4_

  - [ ]* 1.3 Write property tests for lead magnet registry (Properties 1, 2, 3)
    - **Property 1: Validation filter excludes invalid entries**
    - **Validates: Requirements 1.1, 1.2, 6.1, 6.2, 6.3**
    - **Property 2: Unique ID deduplication**
    - **Validates: Requirements 6.4**
    - **Property 3: Slug lookup is case-insensitive and correct**
    - **Validates: Requirements 7.3, 7.4**

  - [ ]* 1.4 Write unit tests for lead magnet registry
    - Test `validate_lead_magnet()` with valid entry, missing fields, empty fields, non-https URL
    - Test `get_lead_magnets()` with empty registry
    - Test `_check_unique_ids()` with duplicate IDs
    - Test `get_lead_magnet_by_slug()` with exact match, case variation, and unknown slug
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.2, 7.3, 7.4_

- [x] 2. Checkpoint — Verify lead magnet registry module
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add `lead_magnet_downloaded` to analytics tracker and add new endpoints to `growth/growth_api.py`
  - [x] 3.1 Add `"lead_magnet_downloaded"` to `ALLOWED_EVENT_TYPES` in `growth/analytics_tracker.py`
    - Add the string to the existing `frozenset` — single-line change
    - Verify `"lead_magnet_clicked"` is already present
    - _Requirements: 4.1, 4.2_

  - [x] 3.2 Add `GET /api/growth/lead-magnet` endpoint to `growth/growth_api.py`
    - Implement `lead_magnet_list()` — calls `get_lead_magnets()`, returns `{success, lead_magnets, count}` with HTTP 200
    - Public endpoint, no auth required
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 3.3 Add `POST /api/growth/lead-magnet/download` endpoint to `growth/growth_api.py`
    - Validate `slug` present → 400 if missing
    - Lookup by slug → 404 if not found
    - Rate limit via `_check_rate_limit(session_id)` if session_id provided → 429 if exceeded; log warning if no session_id
    - Track `lead_magnet_downloaded` event via `track_event()` (non-blocking, catch exceptions)
    - Return `{success, download_url, title, slug}` with HTTP 200
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 3.4 Write property tests for download endpoint (Properties 4, 5, 6, 7)
    - **Property 4: Download returns correct data for valid slugs**
    - **Validates: Requirements 2.1, 2.5**
    - **Property 5: Download logs analytics event with correct data**
    - **Validates: Requirements 2.2, 3.6, 4.3**
    - **Property 6: Unknown slug returns 404**
    - **Validates: Requirements 2.3**
    - **Property 7: Rate limiting enforced after threshold**
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 3.5 Write unit tests for list and download endpoints
    - Test list endpoint returns all valid lead magnets with correct shape
    - Test list endpoint with empty registry returns `{success: true, lead_magnets: [], count: 0}`
    - Test download with missing slug → 400
    - Test download with unknown slug → 404
    - Test download without session_id succeeds with logger.warning
    - Test analytics failure during download still returns URL
    - Test `lead_magnet_downloaded` membership in `ALLOWED_EVENT_TYPES`
    - _Requirements: 1.1, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 3.4, 4.2_

- [x] 4. Checkpoint — Verify endpoints and analytics integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Modify `subscribe()` to optionally return lead magnet
  - [x] 5.1 Modify `subscribe()` in `growth/growth_api.py` to handle `lead_magnet_slug`
    - After successful `add_subscriber`, check for `lead_magnet_slug` in request data
    - If present and matches a valid lead magnet: attach `lead_magnet` object (`id`, `title`, `slug`, `download_url`) to response
    - Track `lead_magnet_clicked` event via `track_event()` (non-blocking, catch exceptions)
    - If slug not found or not provided: return normal subscribe response unchanged
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 5.2 Write property tests for subscribe + lead magnet (Properties 8, 9, 10)
    - **Property 8: Subscribe with valid slug returns lead magnet**
    - **Validates: Requirements 5.1**
    - **Property 9: Subscribe with invalid slug omits lead magnet**
    - **Validates: Requirements 5.2**
    - **Property 10: Subscribe with valid slug tracks clicked event**
    - **Validates: Requirements 5.4**

  - [ ]* 5.3 Write unit tests for subscribe + lead magnet integration
    - Test subscribe without `lead_magnet_slug` — normal response, no `lead_magnet` key
    - Test subscribe with valid `lead_magnet_slug` — response includes `lead_magnet` object
    - Test subscribe with invalid `lead_magnet_slug` — subscription succeeds, no `lead_magnet` key
    - Test analytics failure during subscribe still succeeds
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 6. Checkpoint — Verify subscribe integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Create developer documentation
  - [x] 7.1 Create `docs/LEAD_MAGNET_MODULE.md`
    - Document endpoints: `GET /api/growth/lead-magnet`, `POST /api/growth/lead-magnet/download`, modified `POST /api/growth/subscribe`
    - Document lead magnet data format (id, slug, title, description, download_url)
    - Include request/response examples for each endpoint
    - Document how to add new lead magnets to the static registry
    - Document analytics events (`lead_magnet_downloaded`, `lead_magnet_clicked`)
    - _Requirements: 8.2_

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- All code is isolated to `growth/` and `docs/` — no changes to `app.py`
- Python is the implementation language throughout
