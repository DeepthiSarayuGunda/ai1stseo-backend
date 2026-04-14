#!/usr/bin/env python3
"""
parallel_probe_executor.py
Parallel Probe Execution via SQS for scalable global probing.

Instead of probing keywords one-by-one, this module:
  1. Splits 200+ keywords into batches
  2. Sends each batch to an SQS queue
  3. Lambda workers process batches in parallel
  4. Results are aggregated back into the intelligence tables

Cuts scan time from hours to minutes.

Does NOT modify geo_probe_service.py or any existing probe logic.
Calls existing geo_probe_batch() as the underlying probe mechanism.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_PREFIX = os.environ.get('DYNAMO_TABLE_PREFIX', '')
PROBE_QUEUE_URL = os.environ.get('DEEPTHI_PROBE_QUEUE_URL', '')
PROBE_JOBS_TABLE = f'{TABLE_PREFIX}deepthi-probe-jobs'
BATCH_SIZE = 20  # Keywords per SQS message (matches geo_probe_batch chunk size)

_ddb = None
_sqs = None


def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource('dynamodb', region_name=REGION)
    return _ddb


def _get_sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client('sqs', region_name=REGION)
    return _sqs


def _now():
    return datetime.now(timezone.utc).isoformat()


def _dec(v):
    if v is None:
        return Decimal('0')
    return Decimal(str(round(float(v), 4)))


def _deserialize(item):
    if not item:
        return None
    d = dict(item)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v) if '.' in str(v) else int(v)
    return d


class ProbeJobManager:
    """
    Manages parallel probe jobs. Each job tracks:
      - job_id: unique identifier
      - brand: target brand
      - total_keywords: how many keywords to probe
      - batches_sent: how many SQS messages dispatched
      - batches_complete: how many have returned results
      - status: pending / in_progress / complete / error
    """

    def __init__(self):
        try:
            self._table = _get_ddb().Table(PROBE_JOBS_TABLE)
            self._table.load()
            self._available = True
        except Exception:
            self._available = False

    def create_job(self, brand: str, keywords: List[str],
                   provider: str = 'nova', project_id: str = None) -> Dict:
        job_id = str(uuid.uuid4())[:12]
        batches = [keywords[i:i + BATCH_SIZE] for i in range(0, len(keywords), BATCH_SIZE)]
        job = {
            'job_id': job_id,
            'brand': brand,
            'provider': provider,
            'project_id': project_id or '',
            'total_keywords': len(keywords),
            'total_batches': len(batches),
            'batches_complete': 0,
            'status': 'pending',
            'created_at': _now(),
            'results_summary': '{}',
        }
        if self._available:
            self._table.put_item(Item=job)
        return {'job_id': job_id, 'batches': batches, 'job': job}

    def update_batch_complete(self, job_id: str, batch_result: Dict):
        """Called when a batch worker completes. Increments counter."""
        if not self._available:
            return
        self._table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET batches_complete = batches_complete + :one, '
                             '#s = :s',
            ExpressionAttributeValues={':one': 1, ':s': 'in_progress'},
            ExpressionAttributeNames={'#s': 'status'})

    def mark_complete(self, job_id: str, summary: Dict):
        if not self._available:
            return
        self._table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #s = :s, results_summary = :r, completed_at = :t',
            ExpressionAttributeValues={
                ':s': 'complete',
                ':r': json.dumps(summary, default=str),
                ':t': _now(),
            },
            ExpressionAttributeNames={'#s': 'status'})

    def mark_error(self, job_id: str, error: str):
        if not self._available:
            return
        self._table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #s = :s, error_message = :e',
            ExpressionAttributeValues={':s': 'error', ':e': error},
            ExpressionAttributeNames={'#s': 'status'})

    def get_job(self, job_id: str) -> Optional[Dict]:
        if not self._available:
            return None
        resp = self._table.get_item(Key={'job_id': job_id})
        item = _deserialize(resp.get('Item'))
        if item and isinstance(item.get('results_summary'), str):
            try:
                item['results_summary'] = json.loads(item['results_summary'])
            except Exception:
                pass
        return item

    def list_jobs(self, limit: int = 50) -> List[Dict]:
        if not self._available:
            return []
        resp = self._table.scan(Limit=limit)
        items = [_deserialize(i) for i in resp.get('Items', [])]
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return items[:limit]


def dispatch_parallel_probe(brand: str, keywords: List[str],
                            provider: str = 'nova',
                            project_id: str = None) -> Dict:
    """
    Dispatch a parallel probe job.

    If SQS queue is configured, sends batches to the queue for Lambda workers.
    If no queue, falls back to synchronous execution using existing geo_probe_batch.
    """
    mgr = ProbeJobManager()
    job_data = mgr.create_job(brand, keywords, provider, project_id)
    job_id = job_data['job_id']
    batches = job_data['batches']

    if PROBE_QUEUE_URL:
        # SQS mode: dispatch batches to queue
        return _dispatch_to_sqs(job_id, brand, batches, provider, project_id)
    else:
        # Fallback: synchronous execution with threading
        return _execute_sync_parallel(job_id, brand, batches, provider, mgr)


def _dispatch_to_sqs(job_id: str, brand: str, batches: List[List[str]],
                     provider: str, project_id: str = None) -> Dict:
    """Send keyword batches to SQS for parallel Lambda processing."""
    sqs = _get_sqs()
    sent = 0
    for i, batch in enumerate(batches):
        message = {
            'job_id': job_id,
            'brand': brand,
            'keywords': batch,
            'provider': provider,
            'batch_index': i,
            'project_id': project_id or '',
        }
        try:
            sqs.send_message(
                QueueUrl=PROBE_QUEUE_URL,
                MessageBody=json.dumps(message),
                MessageGroupId=job_id if '.fifo' in PROBE_QUEUE_URL else None,
            )
            sent += 1
        except Exception as e:
            logger.error("SQS send failed for batch %d: %s", i, e)

    return {
        'job_id': job_id,
        'mode': 'sqs_parallel',
        'batches_sent': sent,
        'total_batches': len(batches),
        'total_keywords': sum(len(b) for b in batches),
        'status': 'dispatched',
    }


def _execute_sync_parallel(job_id: str, brand: str,
                           batches: List[List[str]], provider: str,
                           mgr: ProbeJobManager) -> Dict:
    """Fallback: run batches using ThreadPoolExecutor for local parallelism."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from geo_probe_service import geo_probe_batch

    all_results = []
    errors = []

    def _run_batch(batch_keywords):
        return geo_probe_batch(brand, batch_keywords, ai_model=provider)

    max_workers = min(len(batches), 10)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_batch, b): i for i, b in enumerate(batches)}
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                result = future.result()
                all_results.append(result)
                mgr.update_batch_complete(job_id, result)
            except Exception as e:
                errors.append({'batch': batch_idx, 'error': str(e)})
                logger.error("Batch %d failed: %s", batch_idx, e)

    # Aggregate results
    total_cited = sum(r.get('cited_count', 0) for r in all_results)
    total_prompts = sum(r.get('total_prompts', 0) for r in all_results)
    overall_geo = round(total_cited / total_prompts, 4) if total_prompts else 0

    summary = {
        'geo_score': overall_geo,
        'cited_count': total_cited,
        'total_prompts': total_prompts,
        'batches_complete': len(all_results),
        'errors': errors,
    }
    mgr.mark_complete(job_id, summary)

    return {
        'job_id': job_id,
        'mode': 'sync_parallel',
        'brand': brand,
        'status': 'complete',
        'geo_score': overall_geo,
        'cited_count': total_cited,
        'total_prompts': total_prompts,
        'batches_complete': len(all_results),
        'total_batches': len(batches),
        'errors': errors,
    }


# -- SQS Lambda worker handler --

def sqs_worker_handler(event, context):
    """
    Lambda handler for SQS probe worker.
    Processes one batch of keywords and writes results back.
    """
    from geo_probe_service import geo_probe_batch

    mgr = ProbeJobManager()

    for record in event.get('Records', []):
        try:
            body = json.loads(record['body'])
            job_id = body['job_id']
            brand = body['brand']
            keywords = body['keywords']
            provider = body.get('provider', 'nova')

            result = geo_probe_batch(brand, keywords, ai_model=provider)
            mgr.update_batch_complete(job_id, result)

            logger.info("SQS worker: job=%s batch=%d keywords=%d geo=%.2f",
                        job_id, body.get('batch_index', 0),
                        len(keywords), result.get('geo_score', 0))
        except Exception as e:
            logger.error("SQS worker error: %s", e)
            job_id = json.loads(record.get('body', '{}')).get('job_id', '')
            if job_id:
                mgr.mark_error(job_id, str(e))
