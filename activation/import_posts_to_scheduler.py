"""
activation/import_posts_to_scheduler.py
Imports posts from social_media_posts.json into the DynamoDB scheduler.
Auto-assigns schedule times spread across the next 5 days.

Run: python activation/import_posts_to_scheduler.py [--dry-run]
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DRY_RUN = "--dry-run" in sys.argv
JSON_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "social_media_posts.json")

print("=" * 60)
print(f"  IMPORT POSTS TO DYNAMO SCHEDULER {'(DRY RUN)' if DRY_RUN else ''}")
print("=" * 60)

# Load posts
with open(JSON_FILE, "r", encoding="utf-8") as f:
    posts = json.load(f)
print(f"\n  Loaded {len(posts)} posts from social_media_posts.json")

# Generate schedule times (spread across next 5 days, 2 per day at 10:00 and 15:00)
now = datetime.now(timezone.utc)
schedule_slots = []
for day_offset in range(1, 6):
    d = now + timedelta(days=day_offset)
    schedule_slots.append(d.replace(hour=10, minute=0, second=0, microsecond=0))
    schedule_slots.append(d.replace(hour=15, minute=0, second=0, microsecond=0))

imported = 0
skipped = 0

for i, post in enumerate(posts):
    content = post.get("caption", "")
    platform = post.get("platform", "LinkedIn")
    title = post.get("title", "")
    hashtags = post.get("hashtags", [])
    status = "scheduled"

    if not content:
        print(f"  ✗ Post {i+1}: empty caption — skipped")
        skipped += 1
        continue

    # Pick schedule slot (cycle through available slots)
    slot = schedule_slots[i % len(schedule_slots)]
    sched_str = slot.strftime("%Y-%m-%d %H:%M")

    # Build full content with hashtags
    full_content = content
    if hashtags:
        full_content += "\n\n" + " ".join(hashtags)

    post_id = str(uuid.uuid4())[:12]

    print(f"\n  Post {i+1}: {title[:50]}...")
    print(f"    Platform: {platform}")
    print(f"    Scheduled: {sched_str} UTC")
    print(f"    ID: {post_id}")

    if DRY_RUN:
        print(f"    [DRY RUN — not inserted]")
        imported += 1
        continue

    try:
        import boto3
        from growth.social_scheduler_dynamo import TABLE_NAME, AWS_REGION
        table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
        table.put_item(Item={
            "id": post_id,
            "post_id": post_id,
            "content": full_content.strip(),
            "platforms": platform,
            "scheduled_datetime": sched_str,
            "status": status,
            "created_at": now.isoformat(),
        })
        print(f"    ✓ Inserted")
        imported += 1
    except Exception as e:
        print(f"    ✗ Error: {e}")
        skipped += 1

print(f"\n{'='*60}")
print(f"  Imported: {imported}, Skipped: {skipped}")
if DRY_RUN:
    print("  (Dry run — no posts were actually inserted)")
    print("  Remove --dry-run to insert for real")
print(f"{'='*60}")
