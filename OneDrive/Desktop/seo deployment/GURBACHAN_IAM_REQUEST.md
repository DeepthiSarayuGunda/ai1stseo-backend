# IAM Permissions Request — Amplify Migration

Hi Gurbachan,

We've made solid progress on the Amplify migration. The seo-backend and site-monitor are both deployed and tested on Lambda — SEO analysis, auth, monitoring scans all working. Here's what we need from you to finish up.

## What's Done

- **seo-backend** → Lambda function `ai1stseo-backend` (Python 3.11, 1024MB, 300s timeout)
  - API Gateway: `https://cwb0hb27bf.execute-api.us-east-1.amazonaws.com`
  - Custom domain ready: `api.ai1stseo.com`
  - Tested: 231-check SEO analysis ✅, Cognito auth ✅, health ✅

- **site-monitor** → Lambda function `seo-analyzer-api` (repurposed, Python 3.11, 1024MB, 300s timeout)
  - API Gateway: `https://w2duao5bg0.execute-api.us-east-1.amazonaws.com`
  - Custom domain ready: `monitor.ai1stseo.com`
  - Tested: scan ✅, uptime ✅, health ✅

- **Static frontend** → Amplify Hosting (Phase 1, already done)

- **Other microprojects** (seo-audit, automation-hub, doc-summarizer, seo-analysis) — staying on EC2 for now. Those are owned by other team members and we don't want to interfere with their work. EC2 stays running.

## What We Need (2 IAM role updates)

Both Lambda functions need 3 additional permissions. Without these, AI recommendations (Bedrock), email notifications (SES), and Cognito secret loading (Secrets Manager) won't work. Everything else already works.

### Role 1: `lambda-basic-execution`
Used by Lambda function: `ai1stseo-backend`

Add inline policy or attach permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:823766426087:secret:ai1stseo/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

### Role 2: `seo-analyzer-lambda-role`
Used by Lambda function: `seo-analyzer-api` (site-monitor)

Same 3 permissions as above (Bedrock, Secrets Manager, SES).

## Why We Can't Do This Ourselves

Troy's SSO role is PowerUserAccess — it can't modify IAM roles or policies. We also can't create new Lambda functions because `iam:PassRole` is blocked.

## What Happens After You Update the Roles

Once the permissions are in place, we'll:
1. Test AI recommendations (Nova Lite via Bedrock)
2. Test email notifications (SES)
3. Switch DNS for `api.ai1stseo.com` and `monitor.ai1stseo.com` from EC2 to API Gateway
4. EC2 keeps running for the other team members' services

No rush — everything that's deployed works fine without these permissions (just the AI and email features are blocked). But whenever you get a chance, this is the last piece to complete the migration for our two services.

Thanks,
Troy
