# Welcome Email Module

## Purpose

Sends a welcome email via AWS SES after a successful growth subscription. Optionally includes a lead magnet download link when the subscriber signed up with a valid `lead_magnet_slug`.

## Flow

1. Subscriber calls `POST /api/growth/subscribe`
2. `add_subscriber()` succeeds → subscription saved
3. Lead magnet resolved (if `lead_magnet_slug` provided)
4. `welcome_email_attempted` analytics event tracked
5. `sync_subscriber_to_email_platform()` called with email, name, and optional lead_magnet
6. SES sends the welcome email
7. `welcome_email_sent` or `welcome_email_failed` analytics event tracked
8. Subscription returns 201 regardless of email/analytics outcome

## Configuration

- `EMAIL_PLATFORM` — `"ses"` (default), `"brevo"`, `"mailerlite"`, or `""` (disabled)
- `SES_SENDER_EMAIL` — sender address (default: `marketing@ai1stseo.com`)
- `AWS_REGION` — AWS region (default: `us-east-1`)

## Analytics Events

All events omit raw email from event_data (PII stays in subscriber system only).

- `welcome_email_attempted` — tracked before send attempt. event_data: `{lead_magnet_slug}`
- `welcome_email_sent` — tracked after successful SES send. event_data: `{lead_magnet_slug}`
- `welcome_email_failed` — tracked after SES failure. event_data: `{error, lead_magnet_slug}`

## Lead Magnet in Email

When a valid `lead_magnet_slug` is provided at subscribe time, the welcome email includes a styled download button with the lead magnet title and URL. When no lead magnet is provided, the email template is unchanged from the standard welcome.

## Error Handling

- Email sending failure → subscription still returns 201
- Analytics tracking failure → subscription still returns 201
- SES client unavailable → logged as warning, subscription unaffected
- All email/analytics logic wrapped in try/except

## Files

- `growth/email_platform_sync.py` — SES sending with optional lead magnet template
- `growth/growth_api.py` — subscribe() wiring
- `growth/analytics_tracker.py` — event type registration
