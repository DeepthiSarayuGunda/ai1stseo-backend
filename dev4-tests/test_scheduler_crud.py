"""
test_scheduler_crud.py
Isolated CRUD test for the social scheduler SQLite database.
Tests all 4 operations: Create, Read, Update, Delete.
Run: python dev4-tests/test_scheduler_crud.py
"""
import sqlite3
import os
import sys
import json
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "social_scheduler.db")

def run_tests():
    print("=" * 60)
    print("Social Scheduler CRUD Test Suite")
    print(f"Database: {DB}")
    print("=" * 60)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    passed = 0
    failed = 0

    # --- Test 1: READ all posts ---
    print("\n[TEST 1] READ - Get all posts")
    try:
        rows = conn.execute("SELECT * FROM scheduled_posts ORDER BY id ASC").fetchall()
        assert len(rows) > 0, "No posts found in database"
        print(f"  PASS: {len(rows)} posts found")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # --- Test 2: READ - Verify schema columns ---
    print("\n[TEST 2] READ - Verify schema columns")
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(scheduled_posts)").fetchall()]
        expected = ["id", "content", "platforms", "scheduled_datetime", "created_at",
                    "image_path", "title", "hashtags", "category", "status", "created_by"]
        missing = [c for c in expected if c not in cols]
        assert not missing, f"Missing columns: {missing}"
        print(f"  PASS: All {len(expected)} expected columns present")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # --- Test 3: CREATE a new post ---
    print("\n[TEST 3] CREATE - Insert a test post")
    test_id = None
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """INSERT INTO scheduled_posts
               (content, platforms, scheduled_datetime, created_at, title,
                hashtags, category, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("CRUD test: automated test post", "Twitter/X", "2026-04-01 10:00:00",
             now, "CRUD Test Post", json.dumps(["#test", "#dev4"]),
             "Test", "draft", "Tabasum-AutoTest"),
        )
        conn.commit()
        test_id = cur.lastrowid
        assert test_id is not None and test_id > 0, "Insert returned no ID"
        print(f"  PASS: Created post id={test_id}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # --- Test 4: READ the created post ---
    print("\n[TEST 4] READ - Fetch the created post by ID")
    try:
        row = conn.execute("SELECT * FROM scheduled_posts WHERE id = ?", (test_id,)).fetchone()
        assert row is not None, f"Post id={test_id} not found"
        d = dict(row)
        assert d["content"] == "CRUD test: automated test post"
        assert d["platforms"] == "Twitter/X"
        assert d["status"] == "draft"
        assert d["created_by"] == "Tabasum-AutoTest"
        print(f"  PASS: Post id={test_id} retrieved with correct data")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # --- Test 5: UPDATE the post ---
    print("\n[TEST 5] UPDATE - Change status to 'scheduled'")
    try:
        conn.execute(
            "UPDATE scheduled_posts SET status = ?, content = ? WHERE id = ?",
            ("scheduled", "CRUD test: updated content", test_id),
        )
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM scheduled_posts WHERE id = ?", (test_id,)).fetchone())
        assert updated["status"] == "scheduled", f"Status is '{updated['status']}', expected 'scheduled'"
        assert updated["content"] == "CRUD test: updated content"
        print(f"  PASS: Post id={test_id} updated (status=scheduled, content changed)")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # --- Test 6: UPDATE - Change platforms ---
    print("\n[TEST 6] UPDATE - Change platforms")
    try:
        conn.execute(
            "UPDATE scheduled_posts SET platforms = ? WHERE id = ?",
            ("LinkedIn, Facebook", test_id),
        )
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM scheduled_posts WHERE id = ?", (test_id,)).fetchone())
        assert updated["platforms"] == "LinkedIn, Facebook"
        print(f"  PASS: Post id={test_id} platforms changed to 'LinkedIn, Facebook'")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # --- Test 7: DELETE the test post ---
    print("\n[TEST 7] DELETE - Remove the test post")
    try:
        conn.execute("DELETE FROM scheduled_posts WHERE id = ?", (test_id,))
        conn.commit()
        gone = conn.execute("SELECT * FROM scheduled_posts WHERE id = ?", (test_id,)).fetchone()
        assert gone is None, f"Post id={test_id} still exists after DELETE"
        print(f"  PASS: Post id={test_id} deleted and confirmed gone")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # --- Test 8: Verify original data intact ---
    print("\n[TEST 8] INTEGRITY - Verify original 20 posts still intact")
    try:
        count = conn.execute("SELECT COUNT(*) FROM scheduled_posts").fetchone()[0]
        assert count == 20, f"Expected 20 posts, found {count}"
        platforms = conn.execute(
            "SELECT platforms, COUNT(*) as cnt FROM scheduled_posts GROUP BY platforms ORDER BY platforms"
        ).fetchall()
        platform_counts = {r["platforms"]: r["cnt"] for r in platforms}
        assert platform_counts.get("Facebook", 0) == 5, f"Facebook count: {platform_counts.get('Facebook', 0)}"
        assert platform_counts.get("Instagram", 0) == 5, f"Instagram count: {platform_counts.get('Instagram', 0)}"
        assert platform_counts.get("LinkedIn", 0) == 5, f"LinkedIn count: {platform_counts.get('LinkedIn', 0)}"
        assert platform_counts.get("Twitter/X", 0) == 5, f"Twitter/X count: {platform_counts.get('Twitter/X', 0)}"
        print(f"  PASS: 20 posts intact (5 per platform)")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    conn.close()

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
