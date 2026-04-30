# Requirements Document

## Introduction

This document defines the requirements for integrating welcome email sending into the growth subscription flow. When a new subscriber is added via `POST /api/growth/subscribe`, the system sends a welcome email via AWS SES. The email optionally includes a lead magnet download link when a valid `lead_magnet_slug` is provided. Three analytics events track the email lifecycle. Email sending and analytics tracking are failure-safe — subscription always succeeds with HTTP 201 regardless of email or analytics outcome. Changes are isolated to `growth/growth_api.py`, `growth/email_platform_sync.py`, `growth/analytics_tracker.py`, and a new `docs/WELCOME_EMAIL_MODULE.md`.

## Glossary

- **Subscribe_Endpoint**: The `POST /api/growth/subscribe` route in `growth/growth_api.py` that handles new email subscriber registration.
- **Email_Platform_Sync**: The `growth/email_platform_sync.py` module responsible for sending welcome emails via AWS SES and syncing subscribers to external email platforms.
- **Analytics_Tracker**: The `growth/analytics_tracker.py` module responsible for tracking growth analytics events in DynamoDB.
- **Welcome_Email**: The HTML/text email sent to a new subscriber after successful registration via AWS SES.
- **Lead_Magnet**: An optional downloadable resource (with `id`, `title`, `slug`, `download_url`) attached to a subscription when a valid `lead_magnet_slug` is provided.
- **ALLOWED_EVENT_TYPES**: The frozen set of valid analytics event type strings in `analytics_tracker.py`.
- **SES**: Amazon Simple Email Service, the email delivery provider used by Email_Platform_Sync.

## Requirements

### Requirement 1: Welcome Email Trigger on Subscription

**User Story:** As a growth team member, I want every new subscriber to automatically receive a welcome email, so that subscribers are engaged immediately after signing up.

#### Acceptance Criteria

1. WHEN `add_subscriber()` returns a successful result, THE Subscribe_Endpoint SHALL call `sync_subscriber_to_email_platform()` with the subscriber email and name.
2. WHEN `add_subscriber()` returns a duplicate result, THE Subscribe_Endpoint SHALL not call `sync_subscriber_to_email_platform()`.
3. WHEN `add_subscriber()` returns a failure result, THE Subscribe_Endpoint SHALL not call `sync_subscriber_to_email_platform()`.

### Requirement 2: Subscription Response Independence from Email Sending

**User Story:** As a developer, I want the subscription HTTP response to be independent of email sending outcome, so that email failures never degrade the subscriber signup experience.

#### Acceptance Criteria

1. WHEN `add_subscriber()` succeeds and `sync_subscriber_to_email_platform()` succeeds, THE Subscribe_Endpoint SHALL return HTTP status 201 with `{"success": true}`.
2. WHEN `add_subscriber()` succeeds and `sync_subscriber_to_email_platform()` raises an exception, THE Subscribe_Endpoint SHALL catch the exception, log a warning, and return HTTP status 201 with `{"success": true}`.
3. WHEN `add_subscriber()` succeeds and `sync_subscriber_to_email_platform()` returns `{"sent": false}`, THE Subscribe_Endpoint SHALL return HTTP status 201 with `{"success": true}`.

### Requirement 3: Lead Magnet Download Link in Welcome Email

**User Story:** As a marketer, I want the welcome email to include a lead magnet download link when the subscriber signed up with a lead magnet, so that subscribers receive their promised resource immediately.

#### Acceptance Criteria

1. WHEN a valid `lead_magnet_slug` is provided and resolves to a Lead_Magnet with a `download_url`, THE Subscribe_Endpoint SHALL pass the Lead_Magnet dict to `sync_subscriber_to_email_platform()` in the `subscriber_data`.
2. WHEN `lead_magnet` is present in `subscriber_data` and contains a `download_url`, THE Email_Platform_Sync `_send_welcome_email()` function SHALL include a download link section in the HTML email body containing the Lead_Magnet title and download URL.
3. WHEN `lead_magnet` is present in `subscriber_data` and contains a `download_url`, THE Email_Platform_Sync `_send_welcome_email()` function SHALL include the Lead_Magnet download URL in the plain text email body.
4. WHEN `lead_magnet_slug` is not provided or resolves to None, THE Email_Platform_Sync `_send_welcome_email()` function SHALL render the Welcome_Email without any download link section, identical to the current template output.
5. WHEN `lead_magnet_slug` is provided but `get_lead_magnet_by_slug()` returns None, THE Subscribe_Endpoint SHALL send the Welcome_Email without a download link section.

### Requirement 4: Welcome Email Analytics Tracking

**User Story:** As a growth team member, I want welcome email lifecycle events tracked in analytics, so that I can monitor email delivery success rates and diagnose failures.

#### Acceptance Criteria

1. WHEN `add_subscriber()` succeeds and before calling `sync_subscriber_to_email_platform()`, THE Subscribe_Endpoint SHALL track a `welcome_email_attempted` event via Analytics_Tracker with `event_data` containing `lead_magnet_slug` (or None).
2. WHEN `sync_subscriber_to_email_platform()` returns `{"sent": true}`, THE Subscribe_Endpoint SHALL track a `welcome_email_sent` event via Analytics_Tracker with `event_data` containing `lead_magnet_slug` (or None).
3. WHEN `sync_subscriber_to_email_platform()` returns `{"sent": false}`, THE Subscribe_Endpoint SHALL track a `welcome_email_failed` event via Analytics_Tracker with `event_data` containing `error` (the error message) and `lead_magnet_slug` (or None).

### Requirement 5: No Raw Email in Analytics Event Data

**User Story:** As a security-conscious developer, I want analytics events to never contain raw email addresses, so that subscriber PII is not stored in the analytics table.

#### Acceptance Criteria

1. THE Subscribe_Endpoint SHALL not include the subscriber email address in the `event_data` dict of any `welcome_email_attempted`, `welcome_email_sent`, or `welcome_email_failed` analytics event.
2. THE Subscribe_Endpoint SHALL only include metadata fields (`lead_magnet_slug`, `error`) in welcome email analytics `event_data`.

### Requirement 6: Backward Compatibility of Email Platform Sync

**User Story:** As a developer, I want the enhanced `email_platform_sync.py` functions to remain backward compatible, so that existing callers are not broken by the lead magnet enhancement.

#### Acceptance Criteria

1. THE Email_Platform_Sync `_send_welcome_email()` function SHALL accept `lead_magnet` as an optional parameter with a default value of None.
2. WHEN `_send_welcome_email()` is called without the `lead_magnet` parameter, THE Email_Platform_Sync SHALL produce output identical to the current implementation.
3. THE Email_Platform_Sync `sync_subscriber_to_email_platform()` function SHALL accept `subscriber_data` dicts that do not contain a `lead_magnet` key without raising an error.

### Requirement 7: Analytics Tracking Failure Independence

**User Story:** As a developer, I want analytics tracking failures to never affect the subscription response, so that DynamoDB outages do not degrade the signup experience.

#### Acceptance Criteria

1. WHEN tracking a `welcome_email_attempted` event raises an exception, THE Subscribe_Endpoint SHALL catch the exception silently and continue with the email sending step.
2. WHEN tracking a `welcome_email_sent` or `welcome_email_failed` event raises an exception, THE Subscribe_Endpoint SHALL catch the exception silently and return the subscription result unchanged.
3. WHEN both `sync_subscriber_to_email_platform()` and `track_event()` raise exceptions, THE Subscribe_Endpoint SHALL catch both exceptions and return HTTP status 201 with `{"success": true}`.

### Requirement 8: New Analytics Event Types Registration

**User Story:** As a developer, I want the three welcome email event types registered in the analytics tracker, so that they pass event type validation.

#### Acceptance Criteria

1. THE Analytics_Tracker ALLOWED_EVENT_TYPES set SHALL include `welcome_email_attempted`.
2. THE Analytics_Tracker ALLOWED_EVENT_TYPES set SHALL include `welcome_email_sent`.
3. THE Analytics_Tracker ALLOWED_EVENT_TYPES set SHALL include `welcome_email_failed`.

### Requirement 9: Isolation Constraints

**User Story:** As a team lead, I want all welcome email integration changes isolated to the growth module, so that existing application code and Cognito authentication flows are not affected.

#### Acceptance Criteria

1. THE welcome email integration SHALL not modify `app.py` or any file outside of `growth/growth_api.py`, `growth/email_platform_sync.py`, `growth/analytics_tracker.py`, and `docs/WELCOME_EMAIL_MODULE.md`.
2. THE welcome email integration SHALL not create any new DynamoDB tables.
3. THE welcome email integration SHALL not introduce any new environment variables.
4. THE welcome email integration SHALL not modify any existing endpoint signatures or response formats beyond the `subscribe()` function behavior.
5. THE welcome email integration SHALL not modify any Cognito authentication flows.

### Requirement 10: Module Documentation

**User Story:** As a developer, I want a documentation file for the welcome email module, so that the integration is discoverable and maintainable.

#### Acceptance Criteria

1. THE welcome email integration SHALL create a `docs/WELCOME_EMAIL_MODULE.md` file documenting the welcome email flow, configuration, analytics events, and lead magnet template behavior.
