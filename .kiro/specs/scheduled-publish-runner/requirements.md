# Requirements Document

## Introduction

The Scheduled Publishing Runner is a lightweight module that identifies due social media posts and publishes them in batch. It scans the existing DynamoDB social posts table for posts with status "scheduled" whose `scheduled_datetime` has passed, splits multi-platform posts into individual publish calls, and routes each through the existing `social_orchestrator.publish_post()`. Phase 1 exposes a manual HTTP trigger endpoint only — no background worker or cron infrastructure. An optional dry-run mode allows previewing what would be published without side effects.

## Glossary

- **Runner**: The `publish_runner.py` module responsible for fetching due posts and orchestrating batch publishing.
- **Due_Post**: A post in the social posts DynamoDB table with `status` equal to `"scheduled"` and `scheduled_datetime` less than or equal to the current UTC time.
- **Batch_Summary**: A structured response object containing counts of attempted, succeeded, and failed publishes, plus per-post result details.
- **Orchestrator**: The existing `social_orchestrator.publish_post()` function that routes a single publish call to Buffer or Postiz and handles status updates and analytics internally.
- **Scheduler_Table**: The existing DynamoDB table `ai1stseo-social-posts` accessed via `social_scheduler_dynamo.py`.
- **Trigger_Endpoint**: The `POST /api/growth/social/run-scheduled` Flask route that invokes the Runner.
- **Dry_Run**: An optional mode where the Runner identifies due posts and returns what would be published without calling the Orchestrator or changing any state.
- **Platform_String**: A comma-separated string stored in the `platforms` field of a post (e.g. `"LinkedIn, X"`).

## Requirements

### Requirement 1: Fetch Due Posts

**User Story:** As an admin, I want the Runner to identify all posts that are due for publishing, so that overdue scheduled posts are processed in batch.

#### Acceptance Criteria

1. WHEN the Runner is invoked, THE Runner SHALL call `social_scheduler_dynamo.get_posts()` to retrieve all posts from the Scheduler_Table.
2. WHEN the Runner retrieves posts, THE Runner SHALL filter to only posts where `status` equals `"scheduled"` and `scheduled_datetime` is less than or equal to the current UTC time.
3. WHEN parsing `scheduled_datetime`, THE Runner SHALL parse the `"YYYY-MM-DD HH:MM"` format and treat the value as UTC.
4. IF `scheduled_datetime` cannot be parsed, THEN THE Runner SHALL skip that post and include a parse-error entry in the Batch_Summary.
5. WHEN no Due_Posts are found, THE Runner SHALL return a Batch_Summary with zero attempted, zero succeeded, and zero failed.

### Requirement 2: Multi-Platform Splitting

**User Story:** As an admin, I want multi-platform posts to be published to each platform individually, so that a single scheduled post reaches all intended platforms.

#### Acceptance Criteria

1. WHEN a Due_Post has a Platform_String containing multiple platforms, THE Runner SHALL split the Platform_String by comma, trim whitespace from each entry, and produce one publish call per platform.
2. WHEN a Due_Post has a Platform_String containing a single platform, THE Runner SHALL produce exactly one publish call for that platform.
3. IF a Due_Post has an empty or missing Platform_String, THEN THE Runner SHALL skip that post and include a missing-platform entry in the Batch_Summary.

### Requirement 3: Publish Routing

**User Story:** As an admin, I want each publish call routed through the existing Orchestrator, so that provider selection, status updates, and analytics tracking are handled consistently.

#### Acceptance Criteria

1. WHEN the Runner publishes a platform entry, THE Runner SHALL call `social_orchestrator.publish_post()` with a payload containing `post_id`, `content`, `platform` (lowercased, trimmed), and `scheduled_at` from the Due_Post.
2. THE Runner SHALL record the Orchestrator result (success or failure with error message) for each platform entry in the Batch_Summary.
3. THE Runner SHALL continue processing remaining platform entries and remaining Due_Posts even when an individual publish call fails.

### Requirement 4: Batch Summary Response

**User Story:** As an admin, I want a structured summary of all publish attempts, so that I can see what happened in a single response.

#### Acceptance Criteria

1. THE Runner SHALL return a Batch_Summary containing `success` (boolean, always `true` for a completed run), `dry_run` (boolean), `total_due` (number of Due_Posts found), `total_publish_attempts`, `succeeded`, `failed`, and `skipped` counts.
2. THE Runner SHALL include a `results` list in the Batch_Summary where each entry contains `post_id`, `platform`, `success` (boolean), and `error` (string or null).
3. THE `success` field in the Batch_Summary SHALL be `true` when the Runner completes processing (even if individual publishes fail), consistent with other growth endpoint response shapes.

### Requirement 5: Dry-Run Mode

**User Story:** As an admin, I want to preview which posts would be published without actually publishing them, so that I can verify the runner logic before committing.

#### Acceptance Criteria

1. WHEN the Runner is invoked with `dry_run` set to `true`, THE Runner SHALL identify Due_Posts and build the results list without calling the Orchestrator.
2. WHEN dry-run mode is active, THE Runner SHALL set each result entry's `success` to `null` and `error` to `null`.
3. WHEN dry-run mode is active, THE Runner SHALL leave all post statuses unchanged in the Scheduler_Table.

### Requirement 6: Manual Trigger Endpoint

**User Story:** As an admin, I want an authenticated HTTP endpoint to trigger the Runner on demand, so that I can manually initiate batch publishing.

#### Acceptance Criteria

1. THE Trigger_Endpoint SHALL be registered as `POST /api/growth/social/run-scheduled` on the existing `growth_bp` Blueprint.
2. THE Trigger_Endpoint SHALL require authentication using the same auth mechanism as other admin endpoints in `growth_api.py`.
3. WHEN the Trigger_Endpoint receives a request with JSON body containing `"dry_run": true`, THE Trigger_Endpoint SHALL invoke the Runner in dry-run mode.
4. WHEN the Trigger_Endpoint receives a request without `dry_run` or with `dry_run` set to `false`, THE Trigger_Endpoint SHALL invoke the Runner in normal publish mode.
5. WHEN the Runner completes, THE Trigger_Endpoint SHALL return HTTP 200 with the Batch_Summary as JSON.
6. IF the Runner raises an unhandled exception, THEN THE Trigger_Endpoint SHALL return HTTP 500 with a JSON error message.

### Requirement 7: Runner Analytics Events

**User Story:** As an admin, I want batch-level analytics events tracked, so that I can monitor runner invocations over time.

#### Acceptance Criteria

1. WHEN the Runner begins processing, THE Runner SHALL track a `runner_batch_started` analytics event via `analytics_tracker.track_event()` with `event_data` containing `dry_run` (boolean) and `total_due` (integer).
2. WHEN the Runner finishes processing, THE Runner SHALL track a `runner_batch_completed` analytics event via `analytics_tracker.track_event()` with `event_data` containing `dry_run`, `total_due`, `succeeded`, `failed`, and `skipped` counts.
3. THE `runner_batch_started` and `runner_batch_completed` event types SHALL be registered in the `ALLOWED_EVENT_TYPES` set in `analytics_tracker.py`.

### Requirement 8: No Infrastructure Side Effects

**User Story:** As a developer, I want the Runner to integrate without modifying app.py, creating new DynamoDB tables, or adding background worker infrastructure, so that the deployment footprint stays minimal.

#### Acceptance Criteria

1. THE Runner SHALL reuse the existing Scheduler_Table and Orchestrator without creating new DynamoDB tables.
2. THE Runner SHALL be importable and callable without modifications to `app.py`.
3. THE Runner SHALL operate as a synchronous request-response function with no background threads, cron jobs, or worker processes.
