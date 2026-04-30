# Requirements Document

## Introduction

This document defines the requirements for enhancing the existing `growth/analytics_tracker.py` module with UTM-enriched event tracking, event type validation, input sanitization, multi-dimensional summary grouping, in-memory rate limiting, and graceful DynamoDB failure handling. The corresponding Flask API layer in `growth/growth_api.py` is updated to pass UTM fields and map HTTP status codes. All changes are isolated to `growth/analytics_tracker.py`, `growth/growth_api.py`, and `docs/ANALYTICS_TRACKER_MODULE.md`. No new DynamoDB tables, environment variables, or `app.py` changes are introduced.

## Glossary

- **Analytics_Tracker**: The `growth/analytics_tracker.py` module responsible for validating, storing, and querying growth analytics events in DynamoDB.
- **Growth_API**: The `growth/growth_api.py` Flask Blueprint that exposes HTTP endpoints for event tracking and analytics summary retrieval.
- **DynamoDB_Table**: The existing `ai1stseo-growth-analytics` DynamoDB table with composite key `event_type` (HASH) + `created_at` (RANGE).
- **ALLOWED_EVENT_TYPES**: A frozen set of 7 valid event type strings: `page_view`, `email_signup_started`, `email_signup_completed`, `lead_magnet_clicked`, `newsletter_cta_clicked`, `subscriber_exported`, `subscriber_list_viewed`.
- **UTM_Fields**: The set of marketing attribution fields: `page_url`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`.
- **Rate_Limiter**: An in-memory sliding-window mechanism that limits event submissions to a maximum of 20 events per 60-second window per `session_id`.
- **Sanitize**: The process of stripping leading/trailing whitespace, lowercasing (where applicable), and truncating strings to 2048 characters.
- **MAX_STRING_LENGTH**: The maximum allowed length for any string field stored in DynamoDB, set to 2048 characters.

## Requirements

### Requirement 1: Event Type Validation

**User Story:** As a developer, I want the analytics tracker to validate event types against an allowlist, so that only recognized event types are stored in DynamoDB.

#### Acceptance Criteria

1. WHEN a `track_event` call is made with an `event_type` value that, after stripping whitespace and lowercasing, is contained in ALLOWED_EVENT_TYPES, THE Analytics_Tracker SHALL accept the event and proceed with storage.
2. WHEN a `track_event` call is made with an `event_type` value that, after stripping whitespace and lowercasing, is not contained in ALLOWED_EVENT_TYPES, THE Analytics_Tracker SHALL reject the event and return `{"success": false, "error": "Invalid event_type: {value}. Allowed: [...]"}` without writing to DynamoDB.
3. WHEN a `track_event` call is made with an empty or missing `event_type`, THE Analytics_Tracker SHALL return `{"success": false, "error": "event_type is required"}` without writing to DynamoDB.
4. THE Analytics_Tracker SHALL define ALLOWED_EVENT_TYPES as a frozen set containing exactly: `page_view`, `email_signup_started`, `email_signup_completed`, `lead_magnet_clicked`, `newsletter_cta_clicked`, `subscriber_exported`, `subscriber_list_viewed`.

### Requirement 2: UTM Field Support

**User Story:** As a marketer, I want analytics events to capture UTM attribution fields, so that I can track which campaigns and sources drive user engagement.

#### Acceptance Criteria

1. THE Analytics_Tracker `track_event` function SHALL accept the following optional parameters: `page_url`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`.
2. WHEN any UTM_Fields parameter is provided with a non-empty value, THE Analytics_Tracker SHALL store the field as a top-level attribute on the DynamoDB item, not nested inside `event_data`.
3. WHEN a UTM_Fields parameter is not provided or is empty, THE Analytics_Tracker SHALL omit the corresponding attribute from the DynamoDB item.

### Requirement 3: Input Sanitization

**User Story:** As a developer, I want all string inputs sanitized before storage, so that data is consistent and no oversized values are written to DynamoDB.

#### Acceptance Criteria

1. THE Analytics_Tracker SHALL strip leading and trailing whitespace from all string input fields before storage.
2. THE Analytics_Tracker SHALL lowercase the following fields before storage: `event_type`, `source`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`.
3. THE Analytics_Tracker SHALL preserve the original case of `page_url` and `session_id` (strip whitespace only, no lowercasing).
4. THE Analytics_Tracker SHALL truncate all string fields to MAX_STRING_LENGTH (2048 characters) after stripping and lowercasing.
5. WHEN a string field exceeds MAX_STRING_LENGTH, THE Analytics_Tracker SHALL silently truncate the value without returning an error.
6. THE Sanitize operation SHALL be idempotent: applying sanitization to an already-sanitized value SHALL produce the same result.

### Requirement 4: Server-Generated Timestamps

**User Story:** As a system operator, I want `created_at` and `event_id` to always be server-generated, so that clients cannot spoof timestamps or identifiers.

#### Acceptance Criteria

1. THE Analytics_Tracker SHALL generate `created_at` using `datetime.now(timezone.utc).isoformat()` on every `track_event` call.
2. THE Analytics_Tracker SHALL generate `event_id` as a UUID4 string on every `track_event` call.
3. THE Growth_API SHALL not pass any client-provided `created_at` or `event_id` values to the `track_event` function.
4. WHEN a client includes `created_at` or `event_id` in the request JSON, THE Growth_API SHALL silently ignore those fields.

### Requirement 5: In-Memory Rate Limiting

**User Story:** As a developer, I want a lightweight rate limiter on event tracking, so that accidental spam from a single session does not flood the analytics table.

#### Acceptance Criteria

1. WHEN a `track_event` call includes a `session_id` and the session has submitted 20 or more events within the last 60 seconds, THE Analytics_Tracker SHALL reject the event and return `{"success": false, "error": "Rate limit exceeded"}` without writing to DynamoDB.
2. WHEN a `track_event` call includes a `session_id` and the session has submitted fewer than 20 events within the last 60 seconds, THE Analytics_Tracker SHALL allow the event and record the timestamp in the in-memory log.
3. WHEN a `track_event` call does not include a `session_id` (None or empty), THE Analytics_Tracker SHALL allow the event through without performing a rate check and SHALL emit a `logger.warning` message.
4. THE Rate_Limiter SHALL use a sliding window: timestamps older than 60 seconds SHALL be pruned on each rate check call.
5. THE Rate_Limiter SHALL maintain independent state per `session_id`: rate limiting one session SHALL not affect any other session.
6. THE Rate_Limiter SHALL store state in a process-local dictionary that resets on process restart.

### Requirement 6: Enhanced Summary Grouping

**User Story:** As an admin, I want the analytics summary to group events by multiple dimensions, so that I can understand traffic patterns across event types, dates, sources, and campaigns.

#### Acceptance Criteria

1. THE Analytics_Tracker `get_summary` function SHALL return event counts grouped by 5 dimensions: `by_type` (event_type), `by_date` (YYYY-MM-DD extracted from `created_at`), `by_source` (source field), `by_utm_source` (utm_source field), `by_utm_campaign` (utm_campaign field).
2. THE Analytics_Tracker SHALL only include events where `created_at` is greater than or equal to the date cutoff (current UTC time minus the requested number of days).
3. THE Analytics_Tracker `get_summary` response SHALL include a `total_events` field whose value equals the sum of all values in the `by_type` dictionary.
4. THE Analytics_Tracker SHALL clamp the `days` parameter to the range [1, 90].
5. WHEN an event lacks a `source`, `utm_source`, or `utm_campaign` attribute, THE Analytics_Tracker SHALL omit that event from the corresponding grouping dictionary without error.

### Requirement 7: Graceful DynamoDB Failure Handling

**User Story:** As a system operator, I want analytics operations to fail gracefully when DynamoDB is unavailable, so that the application remains responsive and does not crash.

#### Acceptance Criteria

1. WHEN `_get_table().put_item()` raises an exception during `track_event`, THE Analytics_Tracker SHALL log the exception at ERROR level and return `{"success": false, "error": "Analytics unavailable"}`.
2. WHEN `_get_table().scan()` raises an exception during `get_summary`, THE Analytics_Tracker SHALL log the exception at ERROR level and return `{"success": false, "error": "Analytics unavailable"}`.
3. WHEN the Analytics_Tracker returns an error containing "Analytics unavailable", THE Growth_API SHALL respond with HTTP status code 503.

### Requirement 8: Growth API UTM Pass-Through and Status Code Mapping

**User Story:** As a developer, I want the Growth API to forward UTM fields to the tracker and return correct HTTP status codes, so that clients receive meaningful responses.

#### Acceptance Criteria

1. THE Growth_API `track` endpoint SHALL extract `page_url`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, and `utm_term` from the request JSON and pass them to `track_event`.
2. WHEN the Analytics_Tracker returns a validation error (invalid or missing event_type), THE Growth_API SHALL respond with HTTP status code 400.
3. WHEN the Analytics_Tracker returns a rate limit error, THE Growth_API SHALL respond with HTTP status code 429.
4. WHEN the Analytics_Tracker returns a DynamoDB failure error ("Analytics unavailable"), THE Growth_API SHALL respond with HTTP status code 503.
5. WHEN the Analytics_Tracker returns a successful result, THE Growth_API SHALL respond with HTTP status code 201.
6. THE Growth_API `analytics_summary` endpoint SHALL return the multi-dimensional summary response from `get_summary` with HTTP status code 200 on success and 503 on DynamoDB failure.

### Requirement 9: Isolation Constraints

**User Story:** As a team lead, I want all analytics tracker changes isolated to the growth module, so that existing application code is not affected.

#### Acceptance Criteria

1. THE Analytics_Tracker enhancement SHALL not modify `app.py` or any file outside of `growth/analytics_tracker.py`, `growth/growth_api.py`, and `docs/ANALYTICS_TRACKER_MODULE.md`.
2. THE Analytics_Tracker enhancement SHALL not create any new DynamoDB tables.
3. THE Analytics_Tracker enhancement SHALL not introduce any new environment variables.
4. THE Analytics_Tracker enhancement SHALL reuse the existing `ai1stseo-growth-analytics` DynamoDB table without schema changes to the key structure.
5. THE Analytics_Tracker enhancement SHALL not integrate with external analytics services (GA4 or similar).
6. THE Analytics_Tracker enhancement SHALL not include any dashboard UI components.
