#!/usr/bin/env python3
"""Deploy the static frontend to AWS Amplify Hosting.

Uses the Amplify CreateDeployment + StartDeployment API to upload
a zip of the amplify-deploy/ folder as a manual deployment.
"""

import os
import sys
import zipfile
import json
import tempfile

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)

APP_ID = "d30a3tvkvr1a51"
BRANCH = "main"
REGION = "us-east-1"
BUILD_DIR = "amplify-deploy"

# Amplify rewrite rules for clean URLs
REWRITE_RULES = [
    {"source": "/ai-visibility", "target": "/ai-visibility.html", "status": "200"},
    {"source": "/history", "target": "/history.html", "status": "200"},
    {"source": "/benchmarks", "target": "/benchmarks.html", "status": "200"},
    {"source": "/openclaw", "target": "/openclaw.html", "status": "200"},
    {"source": "/automation-hub", "target": "/automation-hub.html", "status": "200"},
    {"source": "/scheduler", "target": "/scheduler.html", "status": "200"},
    {"source": "/compare", "target": "/compare.html", "status": "200"},
    {"source": "/trends", "target": "/trends.html", "status": "200"},
    {"source": "/geo", "target": "/geo.html", "status": "200"},
    {"source": "/editor", "target": "/editor.html", "status": "200"},
    {"source": "/directory-listing", "target": "/directory-listing.html", "status": "200"},
    {"source": "/directory-category", "target": "/directory-category.html", "status": "200"},
    {"source": "/directory-compare", "target": "/directory-compare.html", "status": "200"},
    {"source": "/<*>", "target": "/index.html", "status": "404-200"},
]


def create_zip():
    """Zip the build directory."""
    if not os.path.exists(BUILD_DIR):
        print(f"ERROR: {BUILD_DIR}/ not found. Run build_amplify.py first.")
        sys.exit(1)

    zip_path = os.path.join(tempfile.gettempdir(), "amplify-deploy.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, BUILD_DIR)
                zf.write(file_path, arcname)
                print(f"  + {arcname}")

    size_kb = os.path.getsize(zip_path) / 1024
    print(f"\n  Zip created: {zip_path} ({size_kb:.0f} KB)")
    return zip_path


def update_rewrite_rules(client):
    """Set Amplify custom rewrite rules for clean URLs."""
    print("\nUpdating Amplify rewrite rules...")
    try:
        client.update_app(
            appId=APP_ID,
            customRules=[
                {"source": r["source"], "target": r["target"], "status": r["status"]}
                for r in REWRITE_RULES
            ],
        )
        print("  ✓ Rewrite rules updated")
    except Exception as e:
        print(f"  ⚠ Could not update rewrite rules: {e}")


def deploy(zip_path):
    """Upload zip to Amplify and start deployment."""
    client = boto3.client("amplify", region_name=REGION)

    # Update rewrite rules first
    update_rewrite_rules(client)

    print("\nCreating deployment...")
    resp = client.create_deployment(appId=APP_ID, branchName=BRANCH)
    job_id = resp["jobId"]
    upload_url = resp["zipUploadUrl"]
    print(f"  Job ID: {job_id}")

    print("Uploading zip...")
    import urllib.request

    with open(zip_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(
        upload_url, data=data, method="PUT",
        headers={"Content-Type": "application/zip"}
    )
    urllib.request.urlopen(req)
    print("  ✓ Upload complete")

    print("Starting deployment...")
    client.start_deployment(appId=APP_ID, branchName=BRANCH, jobId=job_id)
    print("  ✓ Deployment started")

    print(f"\n{'='*50}")
    print(f"🚀 Deployment initiated!")
    print(f"   App: https://main.{APP_ID}.amplifyapp.com")
    print(f"   Console: https://{REGION}.console.aws.amazon.com/amplify/apps/{APP_ID}")
    print(f"{'='*50}")


def main():
    print(f"\n{'='*50}")
    print("Deploying to AWS Amplify Hosting")
    print(f"App: {APP_ID} | Branch: {BRANCH}")
    print(f"{'='*50}\n")

    print("Creating deployment zip:")
    zip_path = create_zip()
    deploy(zip_path)


if __name__ == "__main__":
    main()
