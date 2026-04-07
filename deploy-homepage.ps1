# deploy-homepage.ps1
# Uploads the patched homepage with email capture to S3 and invalidates CloudFront.
# Run this IMMEDIATELY after: aws sso login

Write-Host "Checking AWS credentials..." -ForegroundColor Cyan
$id = aws sts get-caller-identity 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "AWS credentials expired or missing. Run 'aws sso login' first." -ForegroundColor Red
    exit 1
}
Write-Host "Credentials OK" -ForegroundColor Green

# Verify patched file exists
if (-not (Test-Path "s3-index-patched.html")) {
    Write-Host "s3-index-patched.html not found in current directory." -ForegroundColor Red
    exit 1
}

Write-Host "Uploading s3-index-patched.html to S3..." -ForegroundColor Cyan
aws s3 cp s3-index-patched.html s3://ai1stseo-website/index.html --content-type "text/html" --cache-control "no-cache, no-store, must-revalidate" --region us-east-1
if ($LASTEXITCODE -ne 0) {
    Write-Host "S3 upload FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "S3 upload OK" -ForegroundColor Green

Write-Host "Invalidating CloudFront cache..." -ForegroundColor Cyan
aws cloudfront create-invalidation --distribution-id E16GYTIVXY9IOU --paths "/index.html" --region us-east-1
if ($LASTEXITCODE -ne 0) {
    Write-Host "CloudFront invalidation FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "CloudFront invalidation started" -ForegroundColor Green
Write-Host ""
Write-Host "DONE. Open https://www.ai1stseo.com in incognito to verify." -ForegroundColor Green
