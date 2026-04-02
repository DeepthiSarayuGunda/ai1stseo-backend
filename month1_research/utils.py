"""
utils.py
Shared utilities for Month 1 research scripts.
"""

import json
import os
from datetime import datetime, timezone


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_json(filename: str, data: dict) -> str:
    """Save data as JSON to the output directory. Returns the file path."""
    ensure_output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"{filename}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  ✓ Saved: {path}")
    return path


def load_json(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_latest(prefix: str) -> dict | None:
    """Load the most recent output file matching a prefix."""
    ensure_output_dir()
    files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(prefix) and f.endswith(".json")]
    if not files:
        return None
    latest = sorted(files)[-1]
    return load_json(os.path.join(OUTPUT_DIR, latest))


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_section(title: str):
    print(f"\n--- {title} ---")
