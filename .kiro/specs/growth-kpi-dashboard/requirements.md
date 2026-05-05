# Requirements Document

## Introduction

This document defines the requirements for a lightweight Growth KPI Dashboard endpoint that aggregates metrics from existing data sources (`growth/analytics_tracker.py` and `growth/email_subscriber.py`) into a single authenticated API response. The feature adds one new module (`growth/growth_dashboard.py`) for aggregation logic, one new endpoint (`GET /api/growth/dashboard`) in the existing `growth/growth_api.py` Blueprint, and one documentation file (`docs/GROWTH_DASHBOARD_MODULE.md`). No new DynamoDB tables, no `app.py` changes, and no frontend work are required. All code is isolated under `growth/`.

## Glossary

- **Dashboard_Aggregator**: The `growth/growth_dashboard.py` module responsible for collecting and combining metrics from Analytics_Tracker and Subscriber_Store into a single KPI summary.
- **Growth_API**: The `growth/growth_api.py` Flask Blueprint that exposes HTTP endpoints under `/api/growth`.
- **Analytics_Tracker**: The `growth/analytics_tracker.py` module that provides `get_summary(days)` returning event counts grouped by type, date, source, utm_source, and utm_campaign.
- **Subscriber_Store**: The `growth/email_subscriber.py` module that provides `list_subscribers(page, per_page)` returning paginated subscriber records with `subscribed_at` timestamps.
- **KPI_Response**: The JSON object returned by the dashboard endpoint containing all aggregated growth metrics.
- **require_auth**: The existing authentication decorator in `growth/growth_api.py` that validates Cognito Bearer tokens.

## Requirements

### Requirement 1: Dashboard Aggregation Module

**User Story:** As a developer, I want a dedicated aggregation module that collects KPI data from existing sources, so that the API layer stays thin and the aggregation logic is testable in isolation.

#### Acceptance Criteria

1. THE Dashboard_Aggregator SHALL be implemented in a new file `growth/growth_dashboard.py`.
2. THE Dashboard_Aggregator SHALL expose a `get_dashboard_kpis(days)` function that accepts an integer `days` parameter (default 7).
3. THE Dashboard_Aggregator SHALL clamp the `days` parameter to the range [1, 90].
4. THE Dashboard_Aggregator SHALL return a dictionary containing all fields defined in Requirement 3.
5. THE Dashboard_Aggregator SHALL import and call `get_summary` from `growth/analytics_tracker` and `list_subscribers` from `growth/email_subscriber` to obtain source data.

### Requirement 2: Subscriber Metrics

**User Story:** As a growth manager, I want to see total subscriber count and recent subscriber growth, so that I can track email list health at a glance.

#### Acceptance Criteria

1. THE Dashboard_Aggregator SHALL include a `total_subscribers` field containing the total count of all subscribers returned by `list_subscribers`.
2. THE Dashboard_Aggregator SHALL include a `new_subscribers` field containing the count of subscribers whose `subscribed_at` timestamp falls within the last N calendar days from the current UTC time, where N is the clamped `days` parameter.
3. WHEN the Subscriber_Store returns a response where `success` is false, THE Dashboard_Aggregator SHALL set `total_subscribers` to 0 and `new_subscribers` to 0.
4. THE Dashboard_Aggregator SHALL retrieve all subscribers by calling `list_subscribers` with `per_page` set to a value large enough to fetch all records (10000) and `page` set to 1.

### Requirement 3: KPI Response Schema

**User Story:** As a frontend developer, I want a well-defined JSON schema for the dashboard response, so that I can reliably consume the data.

#### Acceptance Criteria

1. THE KPI_Response SHALL contain the following top-level fields: `success` (boolean), `days` (integer), `generated_at` (ISO 8601 UTC timestamp string), `total_subscribers` (integer), `new_subscribers` (integer), `lead_magnet_downloads` (integer), `welcome_email_attempted` (integer), `welcome_email_sent` (integer), `welcome_email_failed` (integer), `top_event_types` (dictionary mapping event type strings to integer counts), `top_utm_sources` (dictionary mapping utm_source strings to integer counts), `top_utm_campaigns` (dictionary mapping utm_campaign strings to integer counts).
2. THE Dashboard_Aggregator SHALL populate `lead_magnet_downloads` from the `by_type` dictionary value for key `lead_magnet_downloaded`, defaulting to 0 when the key is absent.
3. THE Dashboard_Aggregator SHALL populate `welcome_email_attempted` from the `by_type` dictionary value for key `welcome_email_attempted`, defaulting to 0 when the key is absent.
4. THE Dashboard_Aggregator SHALL populate `welcome_email_sent` from the `by_type` dictionary value for key `welcome_email_sent`, defaulting to 0 when the key is absent.
5. THE Dashboard_Aggregator SHALL populate `welcome_email_failed` from the `by_type` dictionary value for key `welcome_email_failed`, defaulting to 0 when the key is absent.
6. THE Dashboard_Aggregator SHALL populate `top_event_types` with the complete `by_type` dictionary from the Analytics_Tracker summary.
7. THE Dashboard_Aggregator SHALL populate `top_utm_sources` with the complete `by_utm_source` dictionary from the Analytics_Tracker summary.
8. THE Dashboard_Aggregator SHALL populate `top_utm_campaigns` with the complete `by_utm_campaign` dictionary from the Analytics_Tracker summary.
9. THE Dashboard_Aggregator SHALL set `generated_at` to the current UTC time in ISO 8601 format at the moment the response is assembled.

### Requirement 4: Dashboard API Endpoint

**User Story:** As an admin, I want a single authenticated endpoint that returns all growth KPIs, so that I can view the dashboard without making multiple API calls.

#### Acceptance Criteria

1. THE Growth_API SHALL expose a `GET /api/growth/dashboard` endpoint.
2. THE Growth_API dashboard endpoint SHALL require authentication using the existing `require_auth` decorator.
3. THE Growth_API dashboard endpoint SHALL accept an optional `days` query parameter (integer, default 7).
4. WHEN the `days` query parameter is not a valid integer, THE Growth_API SHALL default to 7.
5. WHEN the Dashboard_Aggregator returns a response where `success` is true, THE Growth_API SHALL respond with HTTP status code 200 and the KPI_Response as JSON.
6. WHEN the Dashboard_Aggregator returns a response where `success` is false, THE Growth_API SHALL respond with HTTP status code 500 and the error response as JSON.

### Requirement 5: Graceful Failure Handling

**User Story:** As a system operator, I want the dashboard to degrade gracefully when individual data sources are unavailable, so that partial data is still returned rather than a complete failure.

#### Acceptance Criteria

1. WHEN the Analytics_Tracker `get_summary` call raises an exception or returns a response where `success` is false, THE Dashboard_Aggregator SHALL set all analytics-derived fields (`lead_magnet_downloads`, `welcome_email_attempted`, `welcome_email_sent`, `welcome_email_failed`, `top_event_types`, `top_utm_sources`, `top_utm_campaigns`) to their zero/empty defaults and SHALL set `analytics_available` to false in the response.
2. WHEN the Subscriber_Store `list_subscribers` call raises an exception or returns a response where `success` is false, THE Dashboard_Aggregator SHALL set `total_subscribers` to 0 and `new_subscribers` to 0 and SHALL set `subscribers_available` to false in the response.
3. WHEN both data sources fail, THE Dashboard_Aggregator SHALL still return `success` as true with all fields set to zero/empty defaults, `analytics_available` as false, and `subscribers_available` as false.
4. THE Dashboard_Aggregator SHALL log each data source failure at WARNING level with the exception message.
5. IF an unexpected exception occurs in the Dashboard_Aggregator outside of individual data source calls, THEN THE Dashboard_Aggregator SHALL log the exception at ERROR level and return `{"success": false, "error": "Dashboard aggregation failed"}`.

### Requirement 6: Isolation Constraints

**User Story:** As a team lead, I want all dashboard changes isolated to the growth module, so that existing application code is not affected.

#### Acceptance Criteria

1. THE Growth KPI Dashboard feature SHALL not modify `app.py` or any file outside of `growth/growth_dashboard.py`, `growth/growth_api.py`, and `docs/GROWTH_DASHBOARD_MODULE.md`.
2. THE Growth KPI Dashboard feature SHALL not create any new DynamoDB tables.
3. THE Growth KPI Dashboard feature SHALL not introduce any new environment variables.
4. THE Growth KPI Dashboard feature SHALL reuse the existing `require_auth` decorator from `growth/growth_api.py` without modification.
5. THE Growth KPI Dashboard feature SHALL not include any frontend UI components (API-only for Phase 1).
6. THE Growth KPI Dashboard feature SHALL not install any new Python dependencies.

### Requirement 7: Documentation

**User Story:** As a developer, I want clear documentation for the dashboard module, so that I can understand the endpoint, its response format, and how to extend it.

#### Acceptance Criteria

1. THE Growth KPI Dashboard feature SHALL include a `docs/GROWTH_DASHBOARD_MODULE.md` file.
2. THE documentation SHALL describe the `GET /api/growth/dashboard` endpoint including URL, method, authentication requirement, query parameters, and a complete example JSON response.
3. THE documentation SHALL list all KPI fields with their data types and source descriptions.
4. THE documentation SHALL describe the graceful degradation behavior when data sources are unavailable.
