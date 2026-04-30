"""
social_publishing/queue.py
Thread-safe publish queue backed by DynamoDB for persistence.

Provides an in-memory queue for fast processing with DynamoDB fallback
so queued items survive restarts. Items flow:

    enqueue() → DynamoDB (status=queued) → worker picks up → publish_content() → status=completed/failed

The worker runs in a background thread, processing items one at a time
to avoid rate-limit issues with social APIs.

Environment variables:
    PUBLISH_QUEUE_TABLE     — DynamoDB table (default: social-publish-queue)
    PUBLISH_QUEUE_WORKERS   — Number of worker threads (default: 1)
    PUBLISH_QUEUE_ENABLED   — "1" to auto-start worker (default: "0")
    AWS_REGION              — AWS region (default: us-east-1)
"""

import logging
import os
import queue
import threading
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("PUBLISH_QUEUE_TABLE", "social-publish-queue")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
WORKER_COUNT = int(os.environ.get("PUBLISH_QUEUE_WORKERS", "1"))
QUEUE_ENABLED = os.environ.get("PUBLISH_QUEUE_ENABLED", "0") == "1"

# In-memory queue for fast processing
_mem_queue: queue.Queue = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()
_shutdown = threading.Event()

# DynamoDB table reference (lazy)
_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    return _table


def init_queue_table() -> None:
    """Create the DynamoDB queue table if it doesn't exist."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.load()
        logger.info("Queue table %s exists", TABLE_NAME)
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        logger.info("Creating queue table %s ...", TABLE_NAME)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "queue_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "queue_id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "status-index",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.meta.client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
        logger.info("Queue table %s created", TABLE_NAME)
    except Exception as e:
        logger.warning("Queue table init: %s", e)


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------

def enqueue(content: dict, priority: int = 5, source: str = "manual") -> dict:
    """Add a content item to the publish queue.

    Args:
        content: Same shape as publish_content() input:
            {"text": str, "image_url": str, "video_url": str,
             "platforms": list, "scheduled_at": str}
        priority: 1 (highest) to 10 (lowest). Default 5.
        source: Origin label ("pipeline", "api", "manual", "webhook").

    Returns:
        {"success": bool, "queue_id": str}
    """
    queue_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "queue_id": queue_id,
        "content": content,
        "priority": priority,
        "source": source,
        "status": "queued",
        "created_at": now,
        "started_at": "",
        "completed_at": "",
        "result": {},
        "attempts": 0,
        "error": "",
    }

    # Persist to DynamoDB
    try:
        db_item = {
            "queue_id": queue_id,
            "status": "queued",
            "created_at": now,
            "priority": priority,
            "source": source,
            "content_text": content.get("text", "")[:500],
            "content_platforms": ", ".join(content.get("platforms") or []),
            "has_image": bool(content.get("image_url")),
            "has_video": bool(content.get("video_url")),
            "attempts": 0,
            "error": "",
        }
        _get_table().put_item(Item=db_item)
    except Exception as e:
        logger.warning("Queue DynamoDB write failed (will process in-memory): %s", e)

    # Push to in-memory queue for immediate processing
    _mem_queue.put(item)

    # Auto-start worker if enabled
    _ensure_worker_running()

    logger.info("Enqueued %s from %s (priority=%d, platforms=%s)",
                queue_id, source, priority,
                content.get("platforms", "all"))

    return {"success": True, "queue_id": queue_id}


def enqueue_batch(items: list, source: str = "pipeline") -> dict:
    """Enqueue multiple content items at once.

    Args:
        items: List of content dicts (same shape as publish_content input).
        source: Origin label.

    Returns:
        {"success": bool, "queued": int, "queue_ids": list}
    """
    queue_ids = []
    for content in items:
        result = enqueue(content, source=source)
        if result.get("success"):
            queue_ids.append(result["queue_id"])

    return {"success": True, "queued": len(queue_ids), "queue_ids": queue_ids}


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _process_item(item: dict) -> dict:
    """Process a single queue item by calling publish_content()."""
    from social_publishing.orchestrator import publish_content

    queue_id = item.get("queue_id", "unknown")
    content = item.get("content", {})
    attempts = item.get("attempts", 0) + 1

    logger.info("Processing queue item %s (attempt %d)", queue_id, attempts)

    # Update status to processing
    _update_queue_status(queue_id, "processing", attempts=attempts)

    # --- Duplicate detection (fail-open: errors here never block publishing) ---
    try:
        from social_publishing.duplicate_detector import is_duplicate
        if is_duplicate(content):
            logger.info("Duplicate skipped: queue item %s", queue_id)
            _update_queue_status(queue_id, "completed",
                                 result={"duplicate": True},
                                 error="Duplicate content skipped")
            return {"success": True, "duplicate": True, "skipped": True}
    except Exception as e:
        logger.debug("Duplicate check unavailable for %s: %s — proceeding", queue_id, e)

    try:
        result = publish_content(content)

        if result.get("success") or result.get("scheduled"):
            _update_queue_status(queue_id, "completed", result=result)
            logger.info("Queue item %s completed: published=%s scheduled=%s",
                        queue_id, result.get("published", 0), result.get("scheduled", False))
            # Store hash after successful publish so future duplicates are caught
            try:
                from social_publishing.duplicate_detector import store_hash
                store_hash(content)
            except Exception as e:
                logger.debug("Hash store failed for %s: %s", queue_id, e)
        else:
            _update_queue_status(queue_id, "failed", result=result,
                                error=result.get("error", "publish_content returned failure"))
            logger.warning("Queue item %s failed: %s", queue_id, result.get("error"))

        return result

    except Exception as e:
        logger.error("Queue item %s exception: %s", queue_id, e)
        _update_queue_status(queue_id, "failed", error=str(e), attempts=attempts)
        return {"success": False, "error": str(e)}


def _worker_loop():
    """Background worker that processes queue items."""
    logger.info("Publish queue worker started")

    while not _shutdown.is_set():
        try:
            item = _mem_queue.get(timeout=2.0)
        except queue.Empty:
            continue

        try:
            _process_item(item)
        except Exception as e:
            logger.error("Worker unhandled error: %s", e)
        finally:
            _mem_queue.task_done()

        # Small delay between items to respect rate limits
        time.sleep(0.5)

    logger.info("Publish queue worker stopped")


def _ensure_worker_running():
    """Start the background worker thread if not already running."""
    global _worker_started
    if _worker_started:
        return

    with _worker_lock:
        if _worker_started:
            return
        _shutdown.clear()
        for i in range(WORKER_COUNT):
            t = threading.Thread(target=_worker_loop, name=f"publish-worker-{i}", daemon=True)
            t.start()
        _worker_started = True
        logger.info("Started %d publish queue worker(s)", WORKER_COUNT)


def start_worker():
    """Explicitly start the queue worker. Called during app init if PUBLISH_QUEUE_ENABLED=1."""
    _ensure_worker_running()


def stop_worker():
    """Signal workers to stop (for graceful shutdown)."""
    global _worker_started
    _shutdown.set()
    _worker_started = False
    logger.info("Publish queue worker stop requested")


# ---------------------------------------------------------------------------
# Queue status / management
# ---------------------------------------------------------------------------

def _update_queue_status(queue_id: str, status: str, result: dict = None,
                         error: str = "", attempts: int = None) -> None:
    """Update queue item status in DynamoDB (fire-and-forget)."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        update_expr = "SET #s = :s"
        attr_names = {"#s": "status"}
        attr_values = {":s": status}

        if status == "processing":
            update_expr += ", started_at = :t"
            attr_values[":t"] = now
        elif status in ("completed", "failed"):
            update_expr += ", completed_at = :t"
            attr_values[":t"] = now

        if error:
            update_expr += ", #e = :e"
            attr_names["#e"] = "error"
            attr_values[":e"] = error

        if attempts is not None:
            update_expr += ", attempts = :a"
            attr_values[":a"] = attempts

        _get_table().update_item(
            Key={"queue_id": queue_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
        )
    except Exception as e:
        logger.debug("Queue status update failed for %s: %s", queue_id, e)


def get_queue_status() -> dict:
    """Get current queue metrics."""
    pending = _mem_queue.qsize()

    # Count by status in DynamoDB
    counts = {"queued": 0, "processing": 0, "completed": 0, "failed": 0}
    try:
        from boto3.dynamodb.conditions import Key
        for status in counts:
            resp = _get_table().query(
                IndexName="status-index",
                KeyConditionExpression=Key("status").eq(status),
                Select="COUNT",
            )
            counts[status] = resp.get("Count", 0)
    except Exception as e:
        logger.debug("Queue status query failed: %s", e)

    return {
        "worker_running": _worker_started,
        "in_memory_pending": pending,
        "db_counts": counts,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_queue_items(status: str = None, limit: int = 20) -> list:
    """Retrieve queue items, optionally filtered by status."""
    try:
        if status:
            from boto3.dynamodb.conditions import Key
            resp = _get_table().query(
                IndexName="status-index",
                KeyConditionExpression=Key("status").eq(status),
                ScanIndexForward=False,
                Limit=limit,
            )
        else:
            resp = _get_table().scan(Limit=limit)
        return resp.get("Items", [])
    except Exception as e:
        logger.warning("Queue items query failed: %s", e)
        return []


def flush_queue() -> dict:
    """Process all pending in-memory queue items synchronously.

    Useful for testing or manual batch processing without the worker thread.
    Returns summary of processed items.
    """
    from social_publishing.orchestrator import publish_content

    processed = 0
    succeeded = 0
    failed = 0
    results = []

    while not _mem_queue.empty():
        try:
            item = _mem_queue.get_nowait()
        except queue.Empty:
            break

        result = _process_item(item)
        processed += 1
        if result.get("success") or result.get("scheduled"):
            succeeded += 1
        else:
            failed += 1
        results.append({"queue_id": item.get("queue_id"), "result": result})
        _mem_queue.task_done()

    return {
        "success": True,
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


def recover_stale_items(max_age_minutes: int = 30) -> dict:
    """Re-queue items stuck in 'processing' or 'queued' status in DynamoDB.

    Useful after a restart when in-memory queue was lost.
    """
    recovered = 0
    try:
        for status in ("queued", "processing"):
            items = get_queue_items(status=status, limit=50)
            for item in items:
                content = {
                    "text": item.get("content_text", ""),
                    "platforms": [p.strip() for p in item.get("content_platforms", "").split(",") if p.strip()],
                }
                if item.get("has_image"):
                    content["image_url"] = ""  # URL not stored in queue table
                _mem_queue.put({
                    "queue_id": item["queue_id"],
                    "content": content,
                    "attempts": int(item.get("attempts", 0)),
                })
                recovered += 1
    except Exception as e:
        logger.warning("Queue recovery failed: %s", e)
        return {"success": False, "error": str(e), "recovered": recovered}

    if recovered:
        _ensure_worker_running()

    return {"success": True, "recovered": recovered}
