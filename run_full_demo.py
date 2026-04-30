"""
run_full_demo.py
Final demo orchestrator — runs the full system and verifies all features.

Executes three stages:
  1. System health check (in-process, no server needed)
  2. Publishing pipeline demo (requires running server)
  3. Growth features demo (in-process, no server needed)

Usage:
    python run_full_demo.py

For the publishing pipeline demo (Step 2), start the server first:
    python app.py
If the server is not running, Step 2 is skipped gracefully.
"""

import subprocess
import sys
import time


def _banner(title):
    print()
    print("#" * 64)
    print("#" + title.center(62) + "#")
    print("#" * 64)


def _step_header(n, title):
    print()
    print("=" * 64)
    print("  STEP " + str(n) + ": " + title)
    print("=" * 64)


def main():
    _banner("FULL SYSTEM DEMO")
    print()
    print("  This script runs all system components end-to-end.")
    print("  Stages: health check -> pipeline demo -> growth features")

    results = {}

    # ------------------------------------------------------------------
    # STEP 1: System Health Check
    # ------------------------------------------------------------------
    _step_header(1, "System Health Check (in-process)")
    print("  Running system health check...")
    try:
        from system_check import run_system_check
        passed, failed = run_system_check(base_url=None)
        results["health_check"] = failed == 0
        if failed == 0:
            print("  -> Health check: ALL PASSED (" + str(passed) + " checks)")
        else:
            print("  -> Health check: " + str(failed) + " FAILED out of " + str(passed + failed))
    except Exception as e:
        print("  -> Health check ERROR: " + str(e))
        results["health_check"] = False

    time.sleep(1)

    # ------------------------------------------------------------------
    # STEP 2: Publishing Pipeline Demo
    # ------------------------------------------------------------------
    _step_header(2, "Publishing Pipeline Demo (requires server)")
    print("  Running publishing pipeline demo via subprocess...")
    print("  (If server is not running, this step will show connection errors)")
    print()
    try:
        proc = subprocess.run(
            [sys.executable, "demo_full_system.py"],
            timeout=120,
            capture_output=False,
        )
        results["pipeline"] = proc.returncode == 0
        if proc.returncode == 0:
            print("  -> Pipeline demo: COMPLETED")
        else:
            print("  -> Pipeline demo: finished with code " + str(proc.returncode))
    except subprocess.TimeoutExpired:
        print("  -> Pipeline demo: TIMED OUT (120s)")
        results["pipeline"] = False
    except FileNotFoundError:
        print("  -> Pipeline demo: demo_full_system.py not found")
        results["pipeline"] = False
    except Exception as e:
        print("  -> Pipeline demo ERROR: " + str(e))
        results["pipeline"] = False

    time.sleep(1)

    # ------------------------------------------------------------------
    # STEP 3: Growth Features Demo
    # ------------------------------------------------------------------
    _step_header(3, "Growth Features Demo (in-process)")
    print("  Running growth features demo...")
    print()
    try:
        from final_features.demo_final_features import run_final_features_demo
        run_final_features_demo("AI SEO Tips")
        results["growth_features"] = True
        print("  -> Growth features: COMPLETED")
    except Exception as e:
        print("  -> Growth features ERROR: " + str(e))
        results["growth_features"] = False

    # ------------------------------------------------------------------
    # FINAL SUMMARY
    # ------------------------------------------------------------------
    _banner("DEMO COMPLETE")

    components = [
        ("Pipeline", results.get("pipeline", False)),
        ("Tracking", results.get("health_check", False)),
        ("Duplicate detection", results.get("health_check", False)),
        ("Dashboard", results.get("pipeline", False)),
        ("Control system", results.get("pipeline", False)),
        ("Growth features", results.get("growth_features", False)),
    ]

    print()
    for name, ok in components:
        status = "OK" if ok else "NEEDS SERVER" if name in ("Pipeline", "Dashboard", "Control system") and not ok else "FAIL"
        print("  " + name + ": " + status)

    total_ok = sum(1 for _, ok in components if ok)
    print()
    print("  " + str(total_ok) + "/" + str(len(components)) + " components verified")

    # Note about server-dependent steps
    if not results.get("pipeline", False):
        print()
        print("  Note: Pipeline/Dashboard/Control require a running server.")
        print("  Start with: python app.py")
        print("  Then re-run: python run_full_demo.py")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
