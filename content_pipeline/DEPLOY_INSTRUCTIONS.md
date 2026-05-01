# Content Pipeline — Lambda Deployment Instructions

## What's Built
The full pipeline code is in `content_pipeline/`:
- `handler.py` — main Lambda entry point
- `bedrock.py` — Nova (articles) + Haiku (summaries/social)
- `articles.py` — generates 2 articles per run
- `newsletter.py` — generates newsletter from articles
- `social.py` — generates social media posts
- `image_gen.py` — generates images via ComfyUI or Nova Canvas
- `storage.py` — saves everything to S3
- `publisher.py` — publishes to Postiz

## S3 Bucket
Already created: `ai-content-output` (us-east-1)

## What Needs Admin Access

### 1. Create IAM Role
An admin needs to create a role for the Lambda:

```bash
# Create role
aws iam create-role \
  --role-name content-pipeline-lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

# Attach policies
aws iam attach-role-policy --role-name content-pipeline-lambda-role --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam attach-role-policy --role-name content-pipeline-lambda-role --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam attach-role-policy --role-name content-pipeline-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### 2. Package and Deploy Lambda
```bash
# Package
cd content_pipeline
zip -r ../content_pipeline_lambda.zip .

# Create function
aws lambda create-function \
  --function-name content_pipeline_lambda \
  --runtime python3.11 \
  --handler handler.lambda_handler \
  --role arn:aws:iam::823766426087:role/content-pipeline-lambda-role \
  --timeout 600 \
  --memory-size 1024 \
  --environment "Variables={S3_BUCKET=ai-content-output,BEDROCK_REGION=us-east-1}" \
  --zip-file fileb://../content_pipeline_lambda.zip
```

### 3. Add CloudWatch Cron Trigger
```bash
# Create rule (daily at 8 AM UTC)
aws events put-rule \
  --name content-pipeline-daily \
  --schedule-expression "cron(0 8 * * ? *)"

# Add Lambda as target
aws events put-targets \
  --rule content-pipeline-daily \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:823766426087:function:content_pipeline_lambda"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name content_pipeline_lambda \
  --statement-id content-pipeline-cron \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:823766426087:rule/content-pipeline-daily
```

### 4. Optional: Add Postiz and ComfyUI env vars
```bash
aws lambda update-function-configuration \
  --function-name content_pipeline_lambda \
  --environment "Variables={S3_BUCKET=ai-content-output,BEDROCK_REGION=us-east-1,POSTIZ_API_KEY=your-key,COMFYUI_API_URL=https://comfy.aisomad.ai,COMFY_USER=user,COMFY_PASS=pass}"
```

## Testing Locally
```bash
python -m content_pipeline.handler
```
Note: Requires AWS credentials with Bedrock access (App Runner role has this, SSO PowerUser does not).

## Pipeline Flow
Trigger (CloudWatch cron, daily 8 AM UTC)
→ Generate 2 articles (Nova)
→ Format newsletter (Haiku)
→ Generate social posts (Haiku)
→ Generate images (ComfyUI → Nova Canvas fallback)
→ Upload all to S3 (ai-content-output bucket)
→ Send posts to Postiz
