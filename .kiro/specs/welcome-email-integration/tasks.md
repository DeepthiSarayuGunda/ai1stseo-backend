# Implementation Plan: Welcome Email Integration

## Overview

Wire welcome email sending into the existing `subscribe()` endpoint so every new subscriber receives a welcome email via AWS SES. Add optional lead magnet download link support to the email template, track email lifecycle analytics events, and create module documentation. All changes isolated to `growth/` and `docs/`.

## Tasks

- [x] 1. Register welcome email analytics event types
  - [x] 1.1 Add `welcome_email_attempted`, `welcome_email_sent`, and `welcome_email_failed` to `ALLOWED_EVENT_TYPES` in `growth/analytics_tracker.py`
    - Append the three new strings to the existing `frozenset` definition
    - No other changes to analytics_tracker logic
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 1.2 Write property test: new event types are accepted by `track_event()`
    - **Property 6: Analytics lifecycle — attempted event precedes outcome event**
    - **Validates: Requirements 4.1, 4.2, 4.3, 8.1, 8.2, 8.3**
    - Verify `track_event()` returns `success: True` for each of the three new event types (mock DynamoDB)

- [x] 2. Enhance `_send_welcome_email()` with lead magnet support
  - [x] 2.1 Add optional `lead_magnet` parameter to `_send_welcome_email()` in `growth/email_platform_sync.py`
    - Add `lead_magnet: dict = None` parameter with default None
    - When `lead_magnet` is provided with a `download_url`, build a styled HTML download section and insert it after the bullet list in the HTML template
    - When `lead_magnet` is provided with a `download_url`, append the download URL to the plain text body
    - When `lead_magnet` is None or missing `download_url`, render the template identically to current behavior
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 6.1, 6.2_

  - [ ]* 2.2 Write property test: lead magnet download URL appears in email when provided
    - **Property 3: Lead magnet download URL appears in email when provided**
    - **Validates: Requirements 3.1, 3.2, 3.3**
    - For any lead_magnet dict with non-empty `download_url` and `title`, verify the HTML body and text body both contain the `download_url`

  - [ ]* 2.3 Write property test: backward compatibility without lead_magnet
    - **Property 4: Backward compatibility — no lead_magnet produces identical output**
    - **Validates: Requirements 3.4, 6.1, 6.2, 6.3**
    - Verify calling `_send_welcome_email(email, name)` without `lead_magnet` produces the same result as calling with `lead_magnet=None`

- [x] 3. Enhance `sync_subscriber_to_email_platform()` to pass lead_magnet through
  - [x] 3.1 Update `sync_subscriber_to_email_platform()` in `growth/email_platform_sync.py` to extract `lead_magnet` from `subscriber_data` and pass it to `_send_welcome_email()`
    - Extract `lead_magnet = subscriber_data.get("lead_magnet")` 
    - Pass it as third argument to `_send_welcome_email(email, name, lead_magnet)`
    - Existing callers without `lead_magnet` key must continue to work (`.get()` returns None)
    - _Requirements: 3.1, 6.3_

- [x] 4. Checkpoint — Verify email_platform_sync and analytics_tracker changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Wire welcome email into `subscribe()` in `growth/growth_api.py`
  - [x] 5.1 Add welcome email sending and analytics tracking to `subscribe()` after successful `add_subscriber()`
    - After `add_subscriber()` succeeds and lead_magnet is resolved, call `sync_subscriber_to_email_platform()` with `{"email": email, "name": name, "lead_magnet": lead_magnet}`
    - Before the sync call, track `welcome_email_attempted` event with `event_data={"lead_magnet_slug": lead_magnet_slug}` (no raw email)
    - After sync returns, track `welcome_email_sent` (if `sent` is True) or `welcome_email_failed` (if `sent` is False, include `error` in event_data)
    - Wrap all email/analytics logic in try/except — never let exceptions change the 201 response
    - Wrap each `track_event()` call in its own try/except so analytics failure doesn't block email sending
    - Do not modify the existing lead_magnet_clicked tracking or the response format
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 4.1, 4.2, 4.3, 5.1, 5.2, 7.1, 7.2, 7.3, 9.1, 9.4_

  - [ ]* 5.2 Write property test: subscription always returns 201 regardless of email/analytics outcome
    - **Property 1: Subscription always returns 201 regardless of email/analytics outcome**
    - **Validates: Requirements 2.1, 2.2, 2.3, 7.2, 7.3**
    - Mock `sync_subscriber_to_email_platform` to return success, return failure, or raise exception — verify 201 in all cases

  - [ ]* 5.3 Write property test: sync only called on successful add_subscriber
    - **Property 2: Sync only called on successful add_subscriber**
    - **Validates: Requirements 1.1, 1.2, 1.3**
    - Mock `add_subscriber` to return success, duplicate, or failure — verify `sync_subscriber_to_email_platform` is called only on success

  - [ ]* 5.4 Write property test: analytics events never contain raw email addresses
    - **Property 5: Analytics events never contain raw email addresses**
    - **Validates: Requirements 5.1, 5.2**
    - For any subscriber email, capture all `track_event()` calls and verify the email string does not appear in any `event_data` dict

  - [ ]* 5.5 Write property test: analytics failure does not prevent email sending
    - **Property 7: Analytics failure does not prevent email sending**
    - **Validates: Requirements 7.1**
    - Mock `track_event` to raise an exception on `welcome_email_attempted` — verify `sync_subscriber_to_email_platform` is still called

- [x] 6. Checkpoint — Verify full integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Create module documentation
  - [x] 7.1 Create `docs/WELCOME_EMAIL_MODULE.md`
    - Document the welcome email flow (subscribe → attempted → sync → sent/failed)
    - Document configuration (SES_SENDER_EMAIL, EMAIL_PLATFORM env vars)
    - Document the three analytics event types and their event_data schemas
    - Document lead magnet template behavior (with and without download link)
    - Document error handling and failure-safe guarantees
    - _Requirements: 10.1_

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- All changes are isolated to `growth/growth_api.py`, `growth/email_platform_sync.py`, `growth/analytics_tracker.py`, and `docs/WELCOME_EMAIL_MODULE.md` per Requirement 9
- No modifications to `app.py`, no new DynamoDB tables, no new environment variables
