# deploy-sports-live.ps1
# Deploys the live-data sports page to S3 and invalidates CloudFront.
# This replaces the static directory-sport.html with the API-powered version.
#
# Prerequisites:
#   1. aws sso login (or valid AWS credentials)
#   2. Backend deployed with /api/sports/* endpoints
#   3. Run: POST /api/sports/sync/all  (to populate real data from TheSportsDB)
#
# Run: .\deploy-sports-live.ps1

Write-Host "Checking AWS credentials..." -ForegroundColor Cyan
$id = aws sts get-caller-identity 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "AWS credentials expired or missing. Run 'aws sso login' first." -ForegroundColor Red
    exit 1
}
Write-Host "Credentials OK" -ForegroundColor Green

# Verify file exists
if (-not (Test-Path "s3-pages/directory-sport-live.html")) {
    Write-Host "s3-pages/directory-sport-live.html not found." -ForegroundColor Red
    exit 1
}

# Step 1: Backup current static version
Write-Host "Backing up current directory-sport.html from S3..." -ForegroundColor Cyan
aws s3 cp s3://ai1stseo-website/directory-sport.html s3://ai1stseo-website/directory-sport-static-backup.html --region us-east-1 2>$null
Write-Host "Backup done (directory-sport-static-backup.html)" -ForegroundColor Green

# Step 2: Upload the live version as directory-sport.html
Write-Host "Uploading live sports page to S3..." -ForegroundColor Cyan
aws s3 cp s3-pages/directory-sport-live.html s3://ai1stseo-website/directory-sport.html --content-type "text/html" --cache-control "no-cache, no-store, must-revalidate" --region us-east-1
if ($LASTEXITCODE -ne 0) {
    Write-Host "S3 upload FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "S3 upload OK" -ForegroundColor Green

# Step 3: Invalidate CloudFront cache
Write-Host "Invalidating CloudFront cache..." -ForegroundColor Cyan
aws cloudfront create-invalidation --distribution-id E16GYTIVXY9IOU --paths "/directory-sport.html" --region us-east-1
if ($LASTEXITCODE -ne 0) {
    Write-Host "CloudFront invalidation FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "CloudFront invalidation started" -ForegroundColor Green

Write-Host ""
Write-Host "DONE. Steps to complete:" -ForegroundColor Green
Write-Host "  1. Deploy backend (git push to trigger App Runner)" -ForegroundColor White
Write-Host "  2. Sync real data: curl -X POST https://cwb0hb27bf.execute-api.us-east-1.amazonaws.com/api/sports/sync/all" -ForegroundColor White
Write-Host "  3. Verify: https://www.ai1stseo.com/directory-sport.html?sport=football" -ForegroundColor White
Write-Host ""
Write-Host "To rollback: aws s3 cp s3://ai1stseo-website/directory-sport-static-backup.html s3://ai1stseo-website/directory-sport.html --content-type 'text/html' --region us-east-1" -ForegroundColor Yellow
