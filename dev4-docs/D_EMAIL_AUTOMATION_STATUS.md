# Task D: Marketing Email Automation — Status & Recommendations

## Current Email Setup

| Component | Status | Details |
|-----------|--------|---------|
| SES Domain | ✅ Verified | `ai1stseo.com` — DKIM, SPF, DMARC all configured |
| SES Production | ✅ Active | 50,000 emails/day limit |
| Sender Address | ✅ Working | `no-reply@ai1stseo.com` |
| Outbound Sending | ✅ Working | Welcome emails, password resets, verification codes |
| Inbound Receiving | ❌ Not configured | No `marketing@` inbox exists |
| Reply Handling | ❌ Not configured | No mechanism to receive replies |

## What Currently Works

1. SES sends transactional emails from `no-reply@ai1stseo.com`
2. Cognito uses SES for verification codes and password resets
3. Welcome email sent via `/api/send-welcome` endpoint after signup
4. Site Monitor (`notifier.py`) can send alert emails via SES SMTP

## What Is Missing for `marketing@` Automation

To use `marketing@ai1stseo.com` for both sending AND receiving replies:

### Sending (Outbound)
- Already possible via SES — just use `marketing@ai1stseo.com` as the `Source`
- The domain is verified, so any `@ai1stseo.com` address can send
- No additional SES configuration needed for outbound

### Receiving (Inbound) — NOT SET UP
- SES alone cannot receive emails into a mailbox
- SES Inbound can trigger Lambda/S3 on receipt, but does NOT provide a mailbox
- Need a real mailbox solution for `marketing@` to receive replies

## Recommendation Options

### Option 1: Google Workspace (Easiest)
- **Cost:** $7/user/month (Business Starter)
- **Setup:** Add MX records for `ai1stseo.com` → Google, create `marketing@` mailbox
- **Pros:** Full inbox, calendar, IMAP/SMTP, familiar UI, mobile apps
- **Cons:** Monthly cost, MX record change affects all email routing
- **Automation:** Use Gmail API or IMAP to read replies programmatically
- **Best for:** If the team wants a real email workflow with a UI

### Option 2: AWS WorkMail (Cheapest AWS-native)
- **Cost:** $4/user/month
- **Setup:** Create WorkMail organization, add `marketing@` mailbox
- **Pros:** Stays in AWS ecosystem, IMAP/SMTP, web UI included
- **Cons:** Less polished UI than Gmail, limited integrations
- **Automation:** IMAP polling or WorkMail API
- **Best for:** Keeping everything in AWS

### Option 3: SES Inbound + S3 + Lambda (Cheapest, No Mailbox)
- **Cost:** ~$0 (within free tier for low volume)
- **Setup:** Configure SES inbound rule → store emails in S3 → Lambda processes them
- **Pros:** Cheapest, fully automated, no manual inbox needed
- **Cons:** No human-readable inbox, complex setup, no reply UI
- **Automation:** Lambda triggers on each incoming email, parses content, routes to app
- **Best for:** Fully automated reply processing (no human reads the inbox)

### Option 4: Zoho Mail Free (Free, External)
- **Cost:** Free (up to 5 users, 5GB)
- **Setup:** Add MX records → Zoho, create `marketing@` mailbox
- **Pros:** Free, full inbox, IMAP/SMTP
- **Cons:** MX record change, external dependency, limited free tier
- **Automation:** IMAP polling
- **Best for:** Budget-conscious with need for a real inbox

## Recommendation Summary

| Option | Cost | Ease | Best For |
|--------|------|------|----------|
| Google Workspace | $7/mo | ⭐⭐⭐⭐⭐ | Easiest overall |
| AWS WorkMail | $4/mo | ⭐⭐⭐⭐ | Cheapest with real inbox |
| SES Inbound + Lambda | ~$0 | ⭐⭐ | Pure automation, no inbox |
| Zoho Mail Free | $0 | ⭐⭐⭐ | Free with real inbox |

**My recommendation:** Start with AWS WorkMail ($4/mo) for `marketing@ai1stseo.com`. It stays in the AWS ecosystem, provides a real inbox for the team to monitor, and supports IMAP for programmatic access. If budget is zero, use Zoho Mail Free.

## What Is Already Configured

- SES domain verification (DKIM, SPF, DMARC) ✅
- SES production access (50k/day) ✅
- `no-reply@ai1stseo.com` sending ✅
- SES SMTP credentials exist (used by site monitor) ✅

## What Is Still Missing

1. MX records for inbound email (currently not set for any mailbox provider)
2. Mailbox provider selection and setup
3. `marketing@ai1stseo.com` mailbox creation
4. IMAP/API integration code for reading replies
5. Reply routing logic (which replies go where in the app)

## Blocked On

- **Decision:** Team/client needs to choose a mailbox provider
- **Cost:** WorkMail ($4/mo) or Google Workspace ($7/mo) requires payment
- **DNS:** MX record changes need to be made in Route 53
- **No purchases made** — this is documentation only
