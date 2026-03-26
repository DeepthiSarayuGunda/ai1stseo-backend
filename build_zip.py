import zipfile, os

src = 'ai1stseo-backend-main/lambda_pkg'
out = 'ai1stseo-backend-main/lambda_deploy_new.zip'

with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(src):
        if '__pycache__' in root:
            continue
        for f in files:
            full = os.path.join(root, f)
            arc = os.path.relpath(full, src)
            z.write(full, arc)

size = os.path.getsize(out) / 1024 / 1024
print(f'Done: {size:.1f} MB')
