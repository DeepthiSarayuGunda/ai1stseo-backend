# Requirements Document

## Introduction

The Social Publish Orchestrator is a lightweight orchestration layer that bridges the existing social post scheduler (`growth/social_scheduler_dynamo.py`) with the two configured publishers (`buffer_publisher.py` and `postiz_publisher.py`). Currently, posts are created and scheduled in DynamoDB but never auto-published. This feature adds a single publish endpoint that accepts a normalized payload, selects the correct publisher based on available credentials, routes the request, and returns structured results. All publish lifecycle events are tracked via the existing analytics tracker.

## Glossary

- **Orchestrator**: The new `growth/social_orchestrator.py` module responsible for publisher selection, routing, and result normalization.
- **Publisher**: An existing module (`BufferPublisher` or `PostizPublisher`) that sends content to social media platforms via third-party APIs.
- **Buffer_Publisher**: The `BufferPublisher` class in `buffer_publisher.py` that publishes via the Buffer GraphQL API.
- **Postiz_Publisher**: The `PostizPublisher` class in `postiz_publisher.py` that publishes via the Postiz Cloud REST API.
- **Social_Scheduler**: The `growth/social_scheduler_dynamo.py` module providing DynamoDB CRUD for scheduled posts in the `ai1stseo-social-posts` table.
- **Analytics_Tracker**: The `growth/analytics_tracker.py` module that logs events to the `ai1stseo-growth-analytics` DynamoDB table.
- **Growth_API**: The Flask Blueprint in `growth/growth_api.py` serving endpoints under `/api/growth/`.
- **Publish_Payload**: A normalized JSON object containing `post_id`, `content`, `platform`, and optional `scheduled_at` fields.
- **Platform**: One of the four supported social networks: LinkedIn, Twitter/X, Instagram, Facebook.
- **Provider**: The selected publisher backend, either "buffer" or "postiz".
- **Configured**: A publisher whose `.configured` property returns `True`, indicating valid API credentials are present.

## Requirements

### Requirement 1: Publisher Discovery

**User Story:** As a system operator, I want the Orchestrator to detect which publishers have valid credentials at runtime, so that publishing routes to an available provider without manual configuration.

#### Acceptance Criteria

1. WHEN a publish request is received, THE Orchestrator SHALL check the `configured` property of Buffer_Publisher and Postiz_Publisher to determine availability.
2. WHILE both Buffer_Publisher and Postiz_Publisher are configured, THE Orchestrator SHALL select Buffer_Publisher as the default provider.
3. WHERE the `SOCIAL_PUBLISHER_PREFERENCE` environment variable is set to "postiz", THE Orchestrator SHALL select Postiz_Publisher as the preferred provider when both publishers are configured.
4. IF neither Buffer_Publisher nor Postiz_Publisher is configured, THEN THE Orchestrator SHALL return a response with `success` set to `false`, `error` set to "No publisher configured", and `provider` set to `null`.
5. THE Orchestrator SHALL instantiate publishers using their existing constructors without modifying `buffer_publisher.py` or `postiz_publisher.py`.

### Requirement 2: Publish Routing

**User Story:** As a system operator, I want the Orchestrator to route publish requests to the selected provider, so that posts reach the correct social media platform.

#### Acceptance Criteria

1. WHEN a valid Publish_Payload is received and a provider is available, THE Orchestrator SHALL call the selected publisher's `publish()` method with the `content` and `platform` fields from the payload.
2. WHEN the Publish_Payload contains a non-null `scheduled_at` value, THE Orchestrator SHALL pass the `scheduled_at` value to the publisher as the scheduling parameter.
3. IF the selected publisher returns a failure result, THEN THE Orchestrator SHALL return a response with `success` set to `false`, the `provider` field set to the name of the attempted provider, and the `error` field set to the publisher's error message.
4. WHEN the selected publisher returns a success result, THE Orchestrator SHALL return a response with `success` set to `true`, the `provider` field set to the name of the provider used, and the `result` field containing the publisher's response data.
5. IF the specified platform is not supported by the selected publisher, THEN THE Orchestrator SHALL return a response with `success` set to `false` and `error` describing the unsupported platform.

### Requirement 3: Publish API Endpoint

**User Story:** As a system operator, I want a REST endpoint to trigger publishing, so that scheduled posts can be published via HTTP.

#### Acceptance Criteria

1. THE Growth_API SHALL expose a `POST /api/growth/social/publish` endpoint.
2. THE Growth_API publish endpoint SHALL require authentication using the existing `require_auth` decorator.
3. WHEN the endpoint receives a request without a valid Bearer token, THE Growth_API SHALL return HTTP 401 with an authentication error.
4. WHEN the endpoint receives a JSON body with `content` and `platform` fields, THE Growth_API SHALL pass the payload to the Orchestrator for publishing.
5. IF the `content` field is missing or empty, THEN THE Growth_API SHALL return HTTP 400 with `success` set to `false` and `error` set to "content is required".
6. IF the `platform` field is missing or empty, THEN THE Growth_API SHALL return HTTP 400 with `success` set to `false` and `error` set to "platform is required".
7. WHEN the Orchestrator returns a success result, THE Growth_API SHALL respond with HTTP 200 and the Orchestrator's result as the JSON body.
8. WHEN the Orchestrator returns a failure result due to no configured provider, THE Growth_API SHALL respond with HTTP 503 and the Orchestrator's error as the JSON body.
9. WHEN the Orchestrator returns a failure result due to a publisher error, THE Growth_API SHALL respond with HTTP 502 and the Orchestrator's error as the JSON body.

### Requirement 4: Platform Normalization

**User Story:** As a system operator, I want platform input normalized before routing, so that aliases like "x" and "twitter" resolve to the same canonical platform and unsupported values are rejected early.

#### Acceptance Criteria

1. THE Orchestrator SHALL define the following canonical platform values: `linkedin`, `x`, `instagram`, `facebook`.
2. THE Orchestrator SHALL normalize the `platform` input by stripping whitespace and lowercasing before comparison.
3. THE Orchestrator SHALL accept the following aliases and map them to canonical values: `"twitter"` → `"x"`, `"twitter/x"` → `"x"`.
4. IF the normalized platform value does not match any canonical value or alias, THEN THE Orchestrator SHALL return a response with `success` set to `false` and `error` set to "Unsupported platform: {value}. Supported: linkedin, x, instagram, facebook".
5. THE Orchestrator SHALL pass the canonical platform value (not the alias) to the selected publisher.

### Requirement 5: Post Status Update After Publish

**User Story:** As a system operator, I want the scheduler record to reflect publish outcomes, so that I can track which posts have been published.

#### Acceptance Criteria

1. WHEN a Publish_Payload includes a valid `post_id` and publishing succeeds, THE Orchestrator SHALL call `update_post` on the Social_Scheduler to set the post status to "published".
2. WHEN a Publish_Payload includes a valid `post_id` and publishing fails, THE Orchestrator SHALL call `update_post` on the Social_Scheduler to set the post status to "failed".
3. IF the `update_post` call fails, THEN THE Orchestrator SHALL log a warning and still return the publish result to the caller without raising an exception.
4. WHEN a Publish_Payload does not include a `post_id`, THE Orchestrator SHALL skip the status update step and return the publish result directly.

### Requirement 6: Analytics Event Tracking

**User Story:** As a system operator, I want publish lifecycle events tracked in analytics, so that I can monitor publishing success rates and diagnose failures.

#### Acceptance Criteria

1. THE Analytics_Tracker SHALL accept "publish_attempted", "publish_succeeded", and "publish_failed" as valid event types in `ALLOWED_EVENT_TYPES`.
2. WHEN a publish request is received, THE Orchestrator SHALL track a "publish_attempted" event with `event_data` containing `platform` and `provider` fields.
3. WHEN publishing succeeds, THE Orchestrator SHALL track a "publish_succeeded" event with `event_data` containing `platform`, `provider`, and `post_id` fields.
4. WHEN publishing fails, THE Orchestrator SHALL track a "publish_failed" event with `event_data` containing `platform`, `provider`, `post_id`, and `error` fields.
5. THE Orchestrator SHALL NOT include raw email addresses or personally identifiable information in analytics `event_data`.
6. IF the Analytics_Tracker raises an exception during event tracking, THEN THE Orchestrator SHALL log the exception and return the publish result without blocking the response.

### Requirement 7: Structured Error Responses

**User Story:** As a system operator, I want consistent, structured error responses from the publish flow, so that I can programmatically handle failures.

#### Acceptance Criteria

1. THE Orchestrator SHALL return all responses as JSON objects containing at minimum the fields `success` (boolean), `provider` (string or null), and `error` (string or null).
2. IF a publisher's credentials are missing, THEN THE Orchestrator SHALL return `success` set to `false` with a `status` field set to "provider_unavailable" and the application SHALL NOT raise an unhandled exception.
3. WHEN a publish request completes successfully, THE Orchestrator SHALL include a `result` field containing the publisher's response data.
4. IF an unexpected exception occurs during publishing, THEN THE Orchestrator SHALL catch the exception, log it, and return a response with `success` set to `false` and `error` describing the failure.

### Requirement 8: Module Isolation

**User Story:** As a developer, I want the orchestration logic isolated in a single module under `growth/`, so that it does not affect existing code paths.

#### Acceptance Criteria

1. THE Orchestrator SHALL reside in a single file at `growth/social_orchestrator.py`.
2. THE Orchestrator SHALL NOT modify `app.py`.
3. THE Orchestrator SHALL NOT create new DynamoDB tables.
4. THE Orchestrator SHALL import `BufferPublisher` from `buffer_publisher` and `PostizPublisher` from `postiz_publisher` without modifying those modules.
5. THE Growth_API SHALL register the new publish endpoint additively, without removing or altering existing endpoints.
6. THE Analytics_Tracker SHALL be modified only to add new event type strings to `ALLOWED_EVENT_TYPES`, with no changes to existing tracking logic.
