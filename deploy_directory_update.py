#!/usr/bin/env python3
"""Add directory module to the ai1stseo-backend Lambda.

Downloads current code, adds directory/ module, re-uploads.
"""
import boto3, zipfile, io, os

FUNCTION = 'ai1stseo-backend'
REGION = 'us-east-1'
S3_BUCKET = 'ai1stseo-backend-deployments'
S3_KEY = 'ai1stseo-backend-with-directory.zip'

lam = boto3.client('lambda', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

# Step 1: Download current Lambda code
print("Downloading current Lambda code...")
resp = lam.get_function(FunctionName=FUNCTION)
code_url = resp['Code']['Location']

import requests
r = requests.get(code_url)
current_zip = io.BytesIO(r.content)
print(f"  Downloaded {len(r.content) / 1024 / 1024:.1f} MB")

# Step 2: Create new zip with directory module added
print("Adding directory module...")
new_zip = io.BytesIO()
with zipfile.ZipFile(current_zip, 'r') as zin:
    with zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
        # Copy all existing files
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        
        # Add directory/, dynamo/, and templates/ files
        for mod_dir in ['directory', 'dynamo']:
            mod_path = os.path.join(os.path.dirname(__file__), mod_dir)
            if not os.path.isdir(mod_path):
                continue
            existing = [i.filename for i in zin.infolist()]
            for fname in os.listdir(mod_path):
                if fname.endswith('.py'):
                    fpath = os.path.join(mod_path, fname)
                    arcname = f'{mod_dir}/{fname}'
                    zout.write(fpath, arcname)
                    status = '~' if arcname in existing else '+'
                    print(f"  {status} {arcname}")

        # Update app.py with latest version
        app_path = os.path.join(os.path.dirname(__file__), 'app.py')
        if os.path.exists(app_path):
            zout.write(app_path, 'app.py')
            print("  ~ app.py (updated)")

        # Add directory template
        tpl_path = os.path.join(os.path.dirname(__file__), 'templates', 'directory_category.html')
        if os.path.exists(tpl_path):
            zout.write(tpl_path, 'templates/directory_category.html')
            print("  + templates/directory_category.html")

new_zip.seek(0)
new_size = len(new_zip.getvalue())
print(f"  New zip: {new_size / 1024 / 1024:.1f} MB")

# Step 3: Upload to S3 and update Lambda
print(f"Uploading to s3://{S3_BUCKET}/{S3_KEY}...")
s3.put_object(Bucket=S3_BUCKET, Key=S3_KEY, Body=new_zip.getvalue())

print("Updating Lambda function code...")
lam.update_function_code(
    FunctionName=FUNCTION,
    S3Bucket=S3_BUCKET,
    S3Key=S3_KEY,
)
print(f"\nDone — {FUNCTION} updated with directory module")
