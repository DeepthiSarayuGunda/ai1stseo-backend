#!/usr/bin/env python3
"""Build Lambda deployment package for AEO Platform."""
import os, sys, zipfile, shutil, subprocess, tempfile

OUT_ZIP = "aeo-platform-lambda.zip"
VENV_DIR = os.path.join(tempfile.gettempdir(), "aeo-lambda-deps")

# Python files to include at root of zip
ROOT_FILES = [
    ("web_app.py", "app.py"),  # Rename to app.py for handler=app.handler
    ("database.py", "database.py"),
    ("scheduler.py", "scheduler.py"),
    ("bedrock_helper.py", "bedrock_helper.py"),
    ("openclaw_real_routes.py", "openclaw_real_routes.py"),
    ("openclaw_real.py", "openclaw_real.py"),
]

# Directories to include
SRC_DIRS = ["src", "production", "dynamo", "directory"]
TEMPLATE_DIRS = ["templates"]

# Pip packages needed
PIP_PACKAGES = ["flask", "flask-cors", "mangum", "boto3", "requests", "beautifulsoup4", "lxml"]

def install_deps():
    """Install pip packages into a temp directory for Lambda."""
    if os.path.exists(VENV_DIR):
        shutil.rmtree(VENV_DIR)
    os.makedirs(VENV_DIR)
    print("Installing dependencies...")
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "--target", VENV_DIR,
        "--platform", "manylinux2014_x86_64",
        "--implementation", "cp",
        "--python-version", "3.11",
        "--only-binary=:all:",
        "--no-deps",
    ] + PIP_PACKAGES, check=False)
    # Also install with deps for the ones that need it
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "--target", VENV_DIR,
        "--upgrade",
        "flask", "flask-cors", "mangum", "requests", "beautifulsoup4", "lxml",
    ], check=True)
    print(f"Dependencies installed to {VENV_DIR}")

def build_zip():
    """Create the Lambda deployment zip."""
    print(f"\nBuilding {OUT_ZIP}...")
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add root Python files
        for src, dst in ROOT_FILES:
            if os.path.exists(src):
                zf.write(src, dst)
                print(f"  + {src} -> {dst}")
            else:
                print(f"  SKIP: {src}")

        # Add src/ and production/ directories
        for d in SRC_DIRS:
            if not os.path.isdir(d):
                print(f"  SKIP dir: {d}")
                continue
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.endswith(".py"):
                        fp = os.path.join(root, f)
                        zf.write(fp, fp)
                        print(f"  + {fp}")

        # Add templates directory
        for d in TEMPLATE_DIRS:
            if not os.path.isdir(d):
                print(f"  SKIP dir: {d}")
                continue
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.endswith(".html"):
                        fp = os.path.join(root, f)
                        zf.write(fp, fp)
                        print(f"  + {fp}")

        # Add pip dependencies
        dep_count = 0
        for root, dirs, files in os.walk(VENV_DIR):
            # Skip dist-info, __pycache__, tests
            dirs[:] = [d for d in dirs if not d.endswith(('.dist-info', '__pycache__'))]
            for f in files:
                if f.endswith(('.pyc', '.pyo')):
                    continue
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, VENV_DIR)
                zf.write(fp, arcname)
                dep_count += 1

        print(f"\n  {dep_count} dependency files added")

    size_mb = os.path.getsize(OUT_ZIP) / (1024 * 1024)
    print(f"\n✅ {OUT_ZIP} created ({size_mb:.1f} MB)")

if __name__ == "__main__":
    install_deps()
    build_zip()
