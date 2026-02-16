# AI1STSEO Backend Deployment Script for AWS Elastic Beanstalk
# Run this script after IAM roles are configured

param(
    [string]$Region = "us-east-1",
    [string]$AppName = "backend",
    [string]$EnvName = "ai1stseo-backend-prod",
    [string]$VersionLabel = "v1",
    [string]$InstanceType = "t3.micro"
)

Write-Host "🚀 Starting AI1STSEO Backend Deployment" -ForegroundColor Green
Write-Host "Region: $Region" -ForegroundColor Cyan
Write-Host "Application: $AppName" -ForegroundColor Cyan
Write-Host "Environment: $EnvName" -ForegroundColor Cyan

# Step 1: Create deployment package
Write-Host "`n📦 Creating deployment package..." -ForegroundColor Yellow
$files = @("app.py", "application.py", "requirements.txt", "Procfile", ".ebextensions")
Compress-Archive -Path $files -DestinationPath "seo-backend-$VersionLabel.zip" -Force
Write-Host "✓ Package created: seo-backend-$VersionLabel.zip" -ForegroundColor Green

# Step 2: Upload to S3
Write-Host "`n☁️  Uploading to S3..." -ForegroundColor Yellow
$bucketName = "ai1stseo-backend-deployments"
aws s3 cp "seo-backend-$VersionLabel.zip" "s3://$bucketName/seo-backend-$VersionLabel.zip" --region $Region

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Uploaded to S3" -ForegroundColor Green
} else {
    Write-Host "✗ S3 upload failed" -ForegroundColor Red
    exit 1
}

# Step 3: Create application version
Write-Host "`n📋 Creating application version..." -ForegroundColor Yellow
aws elasticbeanstalk create-application-version `
    --application-name $AppName `
    --version-label $VersionLabel `
    --source-bundle "S3Bucket=$bucketName,S3Key=seo-backend-$VersionLabel.zip" `
    --region $Region

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Application version created" -ForegroundColor Green
} else {
    Write-Host "✗ Application version creation failed" -ForegroundColor Red
    exit 1
}

# Step 4: Check if environment exists
Write-Host "`n🔍 Checking if environment exists..." -ForegroundColor Yellow
$envCheck = aws elasticbeanstalk describe-environments `
    --environment-names $EnvName `
    --region $Region `
    --query "Environments[0].Status" `
    --output text

if ($envCheck -eq "Ready" -or $envCheck -eq "Updating") {
    # Update existing environment
    Write-Host "✓ Environment exists, updating..." -ForegroundColor Yellow
    aws elasticbeanstalk update-environment `
        --environment-name $EnvName `
        --version-label $VersionLabel `
        --region $Region
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Environment update initiated" -ForegroundColor Green
    } else {
        Write-Host "✗ Environment update failed" -ForegroundColor Red
        exit 1
    }
} else {
    # Create new environment
    Write-Host "Creating new environment..." -ForegroundColor Yellow
    aws elasticbeanstalk create-environment `
        --application-name $AppName `
        --environment-name $EnvName `
        --solution-stack-name "64bit Amazon Linux 2023 v4.9.3 running Python 3.13" `
        --version-label $VersionLabel `
        --option-settings `
            "Namespace=aws:autoscaling:launchconfiguration,OptionName=InstanceType,Value=$InstanceType" `
            "Namespace=aws:autoscaling:launchconfiguration,OptionName=IamInstanceProfile,Value=aws-elasticbeanstalk-ec2-role" `
            "Namespace=aws:elasticbeanstalk:environment,OptionName=EnvironmentType,Value=SingleInstance" `
        --region $Region
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Environment creation initiated" -ForegroundColor Green
    } else {
        Write-Host "✗ Environment creation failed" -ForegroundColor Red
        Write-Host "⚠️  Make sure IAM instance profile 'aws-elasticbeanstalk-ec2-role' exists" -ForegroundColor Yellow
        exit 1
    }
}

# Step 5: Wait for environment to be ready
Write-Host "`n⏳ Waiting for environment to be ready (this may take 5-10 minutes)..." -ForegroundColor Yellow
Write-Host "You can monitor progress in the AWS Console or run:" -ForegroundColor Cyan
Write-Host "  aws elasticbeanstalk describe-environments --environment-names $EnvName --region $Region" -ForegroundColor Cyan

$maxAttempts = 60
$attempt = 0
$status = ""

while ($attempt -lt $maxAttempts) {
    Start-Sleep -Seconds 10
    $attempt++
    
    $status = aws elasticbeanstalk describe-environments `
        --environment-names $EnvName `
        --region $Region `
        --query "Environments[0].Status" `
        --output text
    
    $health = aws elasticbeanstalk describe-environments `
        --environment-names $EnvName `
        --region $Region `
        --query "Environments[0].Health" `
        --output text
    
    Write-Host "  Status: $status | Health: $health | Attempt: $attempt/$maxAttempts" -ForegroundColor Gray
    
    if ($status -eq "Ready" -and $health -eq "Green") {
        Write-Host "✓ Environment is ready!" -ForegroundColor Green
        break
    } elseif ($status -eq "Terminated" -or $status -eq "Terminating") {
        Write-Host "✗ Environment terminated. Check events for errors." -ForegroundColor Red
        aws elasticbeanstalk describe-events `
            --environment-name $EnvName `
            --region $Region `
            --max-records 10
        exit 1
    }
}

if ($attempt -ge $maxAttempts) {
    Write-Host "⚠️  Timeout waiting for environment. Check AWS Console for status." -ForegroundColor Yellow
}

# Step 6: Get the URL
Write-Host "`n🌐 Getting API URL..." -ForegroundColor Yellow
$apiUrl = aws elasticbeanstalk describe-environments `
    --environment-names $EnvName `
    --region $Region `
    --query "Environments[0].CNAME" `
    --output text

if ($apiUrl) {
    Write-Host "`n✅ DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
    Write-Host "`n📍 Your API Base URL:" -ForegroundColor Cyan
    Write-Host "   http://$apiUrl" -ForegroundColor White
    Write-Host "`n🧪 Test your API:" -ForegroundColor Cyan
    Write-Host "   curl http://$apiUrl/api/health" -ForegroundColor White
    Write-Host "`n📝 Next Steps:" -ForegroundColor Cyan
    Write-Host "   1. Update your frontend to use: http://$apiUrl" -ForegroundColor White
    Write-Host "   2. Test the /api/analyze endpoint" -ForegroundColor White
    Write-Host "   3. Set up custom domain (optional)" -ForegroundColor White
    Write-Host "   4. Enable HTTPS with AWS Certificate Manager" -ForegroundColor White
} else {
    Write-Host "⚠️  Could not retrieve API URL. Check environment status." -ForegroundColor Yellow
}

Write-Host "`n📊 View logs:" -ForegroundColor Cyan
Write-Host "   aws elasticbeanstalk describe-events --environment-name $EnvName --region $Region" -ForegroundColor White

Write-Host "`n🎉 Deployment script completed!" -ForegroundColor Green
