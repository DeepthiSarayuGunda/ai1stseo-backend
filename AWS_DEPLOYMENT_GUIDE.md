# AI1STSEO Backend Deployment Guide

## Overview
This guide will help you deploy the SEO Analyzer backend API to AWS Elastic Beanstalk.

## Prerequisites
- AWS Account with appropriate permissions
- AWS CLI installed and configured
- EB CLI installed (optional but recommended)

## Deployment Files Created
The following files have been prepared for deployment:

1. **requirements.txt** - Updated with gunicorn for production
2. **Procfile** - Gunicorn configuration for Elastic Beanstalk
3. **.ebextensions/01_flask.config** - Elastic Beanstalk environment configuration
4. **app.py** - Updated with CORS for ai1stseo.com domains
5. **Dockerfile** - For containerized deployment (alternative)

## Option 1: Deploy with EB CLI (Recommended)

### Step 1: Install EB CLI
```bash
pip install awsebcli
```

### Step 2: Initialize Elastic Beanstalk
```bash
cd "seo deployment/backend"
eb init
```
- Select region: us-east-1
- Application name: backend (already exists)
- Platform: Python 3.13
- Use CodeCommit: No
- SSH: Yes (optional)

### Step 3: Create Environment
```bash
eb create ai1stseo-backend-prod --instance-type t3.micro --single
```

### Step 4: Deploy
```bash
eb deploy
```

### Step 5: Get URL
```bash
eb status
```
The CNAME will be your API base URL.

## Option 2: Deploy via AWS Console

### Step 1: Create Deployment Package
1. Navigate to `seo deployment/backend`
2. Create a ZIP file containing:
   - app.py
   - application.py
   - requirements.txt
   - Procfile
   - .ebextensions/ folder

### Step 2: Upload to Elastic Beanstalk
1. Go to AWS Console → Elastic Beanstalk
2. Select application "backend"
3. Click "Create environment"
4. Choose "Web server environment"
5. Platform: Python 3.13 on Amazon Linux 2023
6. Upload your ZIP file
7. Configure more options:
   - Instance type: t3.micro
   - Environment type: Single instance
   - Service role: Create new or use existing
   - EC2 instance profile: Create new with these policies:
     - AWSElasticBeanstalkWebTier
     - AWSElasticBeanstalkWorkerTier
     - AWSElasticBeanstalkMulticontainerDocker
8. Create environment

## Option 3: Deploy with AWS CLI (Current Approach)

### Issue Encountered
The deployment requires an IAM instance profile with proper permissions. Your current AWS user has PowerUser access but lacks IAM role creation permissions.

### Solution
Ask your AWS administrator to:

1. **Create IAM Role** named `aws-elasticbeanstalk-ec2-role` with trust policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ec2.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

2. **Attach Managed Policies** to the role:
   - `AWSElasticBeanstalkWebTier`
   - `AWSElasticBeanstalkWorkerTier`
   - `AWSElasticBeanstalkMulticontainerDocker`

3. **Create Instance Profile**:
```bash
aws iam create-instance-profile --instance-profile-name aws-elasticbeanstalk-ec2-role
aws iam add-role-to-instance-profile --instance-profile-name aws-elasticbeanstalk-ec2-role --role-name aws-elasticbeanstalk-ec2-role
```

4. **Then deploy** using:
```bash
cd "seo deployment/backend"

# Create deployment package
Compress-Archive -Path app.py,application.py,requirements.txt,Procfile,.ebextensions -DestinationPath seo-backend-v1.zip -Force

# Upload to S3
aws s3 cp seo-backend-v1.zip s3://ai1stseo-backend-deployments/seo-backend-v1.zip

# Create application version
aws elasticbeanstalk create-application-version \
  --application-name backend \
  --version-label v1 \
  --source-bundle S3Bucket=ai1stseo-backend-deployments,S3Key=seo-backend-v1.zip \
  --region us-east-1

# Create environment with instance profile
aws elasticbeanstalk create-environment \
  --application-name backend \
  --environment-name ai1stseo-backend-prod \
  --solution-stack-name "64bit Amazon Linux 2023 v4.9.3 running Python 3.13" \
  --version-label v1 \
  --option-settings \
    Namespace=aws:autoscaling:launchconfiguration,OptionName=InstanceType,Value=t3.micro \
    Namespace=aws:autoscaling:launchconfiguration,OptionName=IamInstanceProfile,Value=aws-elasticbeanstalk-ec2-role \
    Namespace=aws:elasticbeanstalk:environment,OptionName=EnvironmentType,Value=SingleInstance \
  --region us-east-1
```

## After Deployment

### 1. Get Your API URL
```bash
aws elasticbeanstalk describe-environments \
  --environment-names ai1stseo-backend-prod \
  --region us-east-1 \
  --query "Environments[0].CNAME" \
  --output text
```

Your API base URL will be: `http://<CNAME>.us-east-1.elasticbeanstalk.com`

### 2. Test the API
```bash
# Health check
curl http://<your-eb-url>/api/health

# Test analysis
curl -X POST http://<your-eb-url>/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","categories":["technical","onpage"]}'
```

### 3. Update Frontend
Update your frontend code to use the new API URL:
```javascript
const API_BASE_URL = 'http://<your-eb-url>';
```

### 4. Configure Custom Domain (Optional)
1. Go to Route 53
2. Create CNAME record: `api.ai1stseo.com` → `<your-eb-cname>`
3. Update CORS in app.py to include your custom domain

## CORS Configuration
The backend is already configured to accept requests from:
- https://ai1stseo.com
- https://www.ai1stseo.com
- http://localhost:5000 (for local testing)

## API Endpoints

### Health Check
```
GET /api/health
```

### Analyze URL
```
POST /api/analyze
Content-Type: application/json

{
  "url": "https://example.com",
  "categories": ["technical", "onpage", "content", "mobile", "performance", "security", "social", "local", "geo"]
}
```

### AI Recommendations (requires Ollama)
```
POST /api/ai-recommendations
Content-Type: application/json

{
  "url": "https://example.com",
  "auditResults": { ... }
}
```

## Monitoring

### View Logs
```bash
eb logs
# or
aws elasticbeanstalk retrieve-environment-info \
  --environment-name ai1stseo-backend-prod \
  --info-type tail \
  --region us-east-1
```

### Check Environment Health
```bash
eb health
# or
aws elasticbeanstalk describe-environment-health \
  --environment-name ai1stseo-backend-prod \
  --attribute-names All \
  --region us-east-1
```

## Troubleshooting

### 502 Bad Gateway
- Check application logs: `eb logs`
- Verify gunicorn is running
- Check if port 8000 is properly configured

### CORS Errors
- Verify your domain is in the CORS origins list in app.py
- Check browser console for specific CORS error messages

### Timeout Errors
- Increase timeout in Procfile (currently 120s)
- Check if the target website is responding slowly

## Cost Estimate
- t3.micro instance: ~$7.50/month
- S3 storage: ~$0.50/month
- Data transfer: Variable based on usage
- **Total: ~$8-10/month**

## Security Recommendations
1. Enable HTTPS using AWS Certificate Manager
2. Set up CloudWatch alarms for errors
3. Enable AWS WAF for DDoS protection
4. Restrict security group to only necessary ports
5. Enable CloudTrail for audit logging

## Next Steps
1. Complete the deployment using one of the options above
2. Get the API base URL
3. Update frontend to use the new API URL
4. Test all endpoints
5. Set up monitoring and alerts
