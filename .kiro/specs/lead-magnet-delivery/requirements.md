# Requirements Document

## Introduction

The Lead Magnet Delivery System enables the ai1stseo.com growth platform to serve downloadable resources (e.g. PDF guides, checklists) to users who subscribe via the existing email capture flow. Phase 1 keeps storage simple (static Python config), integrates with the existing analytics tracker for event logging, and adds two new endpoints to the existing growth Blueprint. No email sending, no file uploads, no frontend UI.

## Glossary

- **Lead_Magnet_Module**: The `growth/lead_magnet.py` Python module responsible for managing lead magnet metadata and download logic.
- **Growth_API**: The existing Flask Blueprint (`growth_bp`) in `growth/growth_api.py` that exposes all growth-related HTTP endpoints under `/api/growth`.
- **Analytics_Tracker**: The existing `growth/analytics_tracker.py` module that logs events to DynamoDB with UTM attribution.
- **Lead_Magnet**: A downloadable digital resource (PDF, checklist, guide) offered in exchange for an email subscription. Each lead magnet has a unique immutable `id` (internal primary key) and a human-readable `slug` (public identifier).
- **Lead_Magnet_Registry**: A static Python data structure (list of dicts) inside `growth/lead_magnet.py` that holds all available lead magnet metadata for Phase 1.
- **Download_URL**: An HTTPS URL pointing to the hosted lead magnet file (e.g. an S3 public URL or CDN link).
- **Subscriber**: A user who has provided an email address via the `/api/growth/subscribe` endpoint.

## Requirements

### Requirement 1: Retrieve Available Lead Magnets

**User Story:** As a site visitor, I want to see what lead magnets are available, so that I can decide whether to subscribe.

#### Acceptance Criteria

1. WHEN a GET request is sent to `/api/growth/lead-magnet`, THE Growth_API SHALL return a JSON response containing a list of all lead magnets from the Lead_Magnet_Registry.
2. THE Growth_API SHALL include the fields `id`, `slug`, `title`, `description`, and `download_url` for each lead magnet in the response.
3. THE Growth_API SHALL return HTTP status 200 for a successful retrieval.
4. WHEN the Lead_Magnet_Registry contains zero entries, THE Growth_API SHALL return an empty list with HTTP status 200.

### Requirement 2: Log Lead Magnet Download

**User Story:** As a subscriber, I want to download a lead magnet and have that interaction recorded, so that the site can track engagement.

#### Acceptance Criteria

1. WHEN a POST request with a valid `slug` is sent to `/api/growth/lead-magnet/download`, THE Growth_API SHALL return a JSON response containing the matching `download_url`, `title`, and `slug`.
2. WHEN a POST request with a valid `slug` is sent to `/api/growth/lead-magnet/download`, THE Lead_Magnet_Module SHALL call the Analytics_Tracker to log a `lead_magnet_downloaded` event with the lead magnet `slug` and `id` in the event data.
3. WHEN a POST request with an unknown `slug` is sent to `/api/growth/lead-magnet/download`, THE Growth_API SHALL return HTTP status 404 with an error message indicating the lead magnet was not found.
4. WHEN a POST request without a `slug` field is sent to `/api/growth/lead-magnet/download`, THE Growth_API SHALL return HTTP status 400 with an error message indicating the slug is required.
5. THE Growth_API SHALL return HTTP status 200 for a successful download request.

### Requirement 3: Download Endpoint Rate Limiting

**User Story:** As a developer, I want the download endpoint to have lightweight spam protection consistent with the analytics tracker, so that accidental abuse is prevented during development.

#### Acceptance Criteria

1. THE Growth_API download endpoint SHALL accept an optional `session_id` field in the request JSON.
2. WHEN `session_id` is provided, THE Lead_Magnet_Module SHALL reuse the existing `_check_rate_limit()` function from `growth/analytics_tracker.py` to enforce the same rate limit (max 20 requests per 60-second sliding window per session_id).
3. WHEN `session_id` is provided and the rate limit is exceeded, THE Growth_API SHALL return HTTP status 429 with `{"success": false, "error": "Rate limit exceeded"}` without returning the download URL.
4. WHEN `session_id` is not provided (None or absent), THE Lead_Magnet_Module SHALL allow the request through and emit a `logger.warning` indicating the download was called without a session_id.
5. THE download endpoint SHALL NOT require authentication in Phase 1.
6. THE `session_id` SHALL be passed through to the Analytics_Tracker `track_event` call when logging the download event.

### Requirement 4: Track Lead Magnet Click Events

**User Story:** As a growth team member, I want lead magnet click events tracked, so that I can measure funnel performance.

#### Acceptance Criteria

1. THE Analytics_Tracker SHALL accept `lead_magnet_clicked` as a valid event type in the ALLOWED_EVENT_TYPES set.
2. THE Analytics_Tracker SHALL accept `lead_magnet_downloaded` as a valid event type in the ALLOWED_EVENT_TYPES set.
3. WHEN a `lead_magnet_downloaded` event is tracked, THE Analytics_Tracker SHALL store the lead magnet `slug` and `id` in the `event_data` field.

### Requirement 5: Return Lead Magnet Link After Subscription

**User Story:** As a new subscriber, I want to receive a lead magnet link immediately after subscribing, so that I get instant value.

#### Acceptance Criteria

1. WHEN a POST request to `/api/growth/subscribe` includes a `lead_magnet_slug` field matching a valid lead magnet, THE Growth_API SHALL include a `lead_magnet` object in the success response containing the `id`, `title`, `slug`, and `download_url`.
2. WHEN a POST request to `/api/growth/subscribe` includes a `lead_magnet_slug` field that does not match any lead magnet, THE Growth_API SHALL complete the subscription without a `lead_magnet` object in the response.
3. WHEN a POST request to `/api/growth/subscribe` omits the `lead_magnet_slug` field, THE Growth_API SHALL complete the subscription without a `lead_magnet` object in the response.
4. WHEN a lead magnet is returned after subscription, THE Lead_Magnet_Module SHALL call the Analytics_Tracker to log a `lead_magnet_clicked` event with the lead magnet `slug` and `id` in the event data.

### Requirement 6: Lead Magnet Data Validation

**User Story:** As a developer, I want lead magnet data to be validated, so that no broken or unsafe URLs are served to users.

#### Acceptance Criteria

1. THE Lead_Magnet_Module SHALL validate that every `download_url` in the Lead_Magnet_Registry starts with `https://`.
2. THE Lead_Magnet_Module SHALL validate that every lead magnet entry contains non-empty `id`, `slug`, `title`, `description`, and `download_url` fields.
3. IF a lead magnet entry fails validation, THEN THE Lead_Magnet_Module SHALL exclude the invalid entry from API responses and log a warning.
4. THE Lead_Magnet_Module SHALL validate that every `id` in the Lead_Magnet_Registry is unique across all entries.
5. THE Lead_Magnet_Module SHALL treat `id` values as immutable — once assigned, an `id` SHALL NOT change even if the `slug` is updated.

### Requirement 7: Lead Magnet Registry Management

**User Story:** As a developer, I want a simple way to define available lead magnets in code, so that Phase 1 stays lightweight without needing a database.

#### Acceptance Criteria

1. THE Lead_Magnet_Module SHALL store lead magnet definitions as a static Python list of dictionaries inside `growth/lead_magnet.py`, where each entry includes `id`, `slug`, `title`, `description`, and `download_url`.
2. THE Lead_Magnet_Module SHALL provide a `get_lead_magnets()` function that returns all valid lead magnet entries.
3. THE Lead_Magnet_Module SHALL provide a `get_lead_magnet_by_slug(slug)` function that returns a single lead magnet matching the given slug, or `None` if not found.
4. THE Lead_Magnet_Module SHALL treat `slug` values as case-insensitive by normalizing to lowercase before comparison.

### Requirement 8: Module Documentation

**User Story:** As a developer, I want clear documentation for the lead magnet module, so that teammates can understand and extend the feature.

#### Acceptance Criteria

1. THE Lead_Magnet_Module SHALL include a module-level docstring describing its purpose, environment variables (if any), and integration points.
2. THE Lead_Magnet_Module SHALL create a `docs/LEAD_MAGNET_MODULE.md` file documenting the endpoints, data format, and usage examples.
