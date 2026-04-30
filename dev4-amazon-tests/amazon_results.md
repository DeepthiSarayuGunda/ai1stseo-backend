# Amazon Image/Video Generation Test Results

**Date:** April 2, 2026 (updated)
**Tester:** Dev 4 (Tabasum)
**Status:** STILL BLOCKED — explicit deny on `bedrock:InvokeModel` persists

---

## Latest Update (April 2, 2026)

Admin confirmed:
- "No IAM changes needed"
- "PowerUserAccess already allows bedrock:* and bedrock-runtime:*"
- Models are enabled and authorized
- Profile to use: `kaurlections` / region: `us-east-1`

**What we found:**
- Profile `kaurlections` does NOT exist on this machine. Only `poweruser` and `default` are configured.
- Only one SSO role is available for this account: `PowerUserAccess`
- All 4 models return `AUTHORIZED` from `get-foundation-model-availability` ✅
- `bedrock:InvokeModel` still returns **explicit deny** ❌
- The IAM-level explicit deny has NOT been removed

**Conclusion:** The Bedrock console shows models as authorized, but the SSO permission set still contains an explicit deny policy on `bedrock:InvokeModel`. These are two different layers — Bedrock model access ≠ IAM invocation permission.

---

## Access Verification (April 2, 2026)

| Check | Result |
|-------|--------|
| SSO login (`poweruser` profile) | ✅ Successful |
| Account | `823766426087` |
| Role | `AWSReservedSSO_PowerUserAccess_1309d249628fcacb` |
| Profile `kaurlections` | ❌ Does not exist on this machine |
| `bedrock:ListFoundationModels` | ✅ Allowed |
| `bedrock:GetFoundationModelAvailability` | ✅ Allowed |
| Nova Canvas — authorization status | ✅ AUTHORIZED |
| Titan Image Gen v2 — authorization status | ✅ AUTHORIZED |
| Nova Reel v1:0 — authorization status | ✅ AUTHORIZED |
| Nova Reel v1:1 — authorization status | ✅ AUTHORIZED |
| `bedrock:InvokeModel` (Nova Canvas) | ❌ **Explicit deny** |
| `bedrock:InvokeModel` (Titan Image) | ❌ **Explicit deny** |
| S3 buckets available | ✅ 16 buckets found |

---

## The Exact Error (unchanged)

```
AccessDeniedException: User arn:aws:sts::823766426087:assumed-role/
AWSReservedSSO_PowerUserAccess_1309d249628fcacb/tabasum is not authorized
to perform: bedrock:InvokeModel on resource: arn:aws:bedrock:us-east-1::
foundation-model/amazon.nova-canvas-v1:0 with an explicit deny in an
identity-based policy
```

Key: **"explicit deny in an identity-based policy"** — this is NOT a missing permission. It is an active DENY rule in the SSO permission set that overrides any allow.

---

## What the Admin Needs to Do

The models being "authorized" in Bedrock console is a separate layer from IAM permissions. Both must be in place:

1. ✅ Bedrock model access — DONE (all 4 models authorized)
2. ❌ IAM permission to invoke — BLOCKED (explicit deny on `bedrock:InvokeModel`)

**Fix required:** Remove the explicit deny on `bedrock:InvokeModel` from the PowerUserAccess SSO permission set.

Location: **AWS IAM Identity Center → Permission Sets → PowerUserAccess → Inline policy**

Look for a statement like:
```json
{
  "Effect": "Deny",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": "*"
}
```
This deny statement must be removed or scoped to not include the target models.

**OR** create a `kaurlections` profile with a different SSO role that does not have this deny.

---

## Scripts Ready to Run (once IAM is fixed)

| Script | Purpose | Status |
|--------|---------|--------|
| `amazon_test.py` | Basic test — 1 Nova Canvas + 1 Titan image | Ready |
| `generate_samples.py` | Full demo — 2 Nova Canvas + 1 Titan + Nova Reel check | Ready |

Both scripts use `profile=poweruser`, `region=us-east-1`.

**To run after fix:**
```bash
aws sso login --profile poweruser
python dev4-amazon-tests/amazon_test.py
python dev4-amazon-tests/generate_samples.py
```

---

## Sample Images Planned (once access works)

| # | Model | Output File | Prompt Theme |
|---|-------|-------------|--------------|
| 1 | Nova Canvas | `nova_canvas_seo_banner.png` | AI SEO marketing banner, blue/white |
| 2 | Nova Canvas | `nova_canvas_social_post.png` | Analytics social media graphic, blue/teal |
| 3 | Titan Image v2 | `titan_brand_visual.png` | AI brand visual, neural network, purple/blue |

---

## Video Generation (Nova Reel)

- 16 S3 buckets available — output storage is not a blocker
- Nova Reel uses `start_async_invoke()` (async, ~90s per 6s clip)
- Will test once `bedrock:InvokeModel` / `bedrock:InvokeModelWithResponseStream` deny is removed
- Both v1:0 and v1:1 are authorized in Bedrock

---

## Cost Estimates (for when it works)

| Model | Est. Cost | Notes |
|-------|-----------|-------|
| Nova Canvas | ~$0.04–0.08/image | 1024×1024, standard quality |
| Titan Image Gen v2 | ~$0.01/image | 1024×1024, cheapest option |
| Nova Reel v1:0 | ~$0.80/6s clip | Async, needs S3 |
| Nova Reel v1:1 | ~$0.80/6s clip | Up to 2 min video |

**Best for demo:** Titan Image Gen v2 (cheapest) for bulk, Nova Canvas for quality.

---

## Quality Comparison (pending — cannot test yet)

Will be filled in once images are generated:
- Nova Canvas: (pending)
- Titan Image Gen v2: (pending)
- Side-by-side comparison: (pending)
- Best for demo recommendation: (pending)

---

## Files in dev4-amazon-tests/

| File | Purpose |
|------|---------|
| `amazon_test.py` | Basic image generation test (Nova Canvas + Titan) |
| `generate_samples.py` | Multi-sample generation with demo prompts |
| `check_aws.py` | AWS credentials + model listing |
| `check_sso.py` | SSO profile check |
| `check_model_access.py` | Detailed model access + IAM diagnosis |
| `check_iam_policies.py` | IAM policy introspection |
| `amazon_results.md` | This report |
| `outputs/` | Directory for generated images (empty until IAM fix) |

No existing project files were modified.
