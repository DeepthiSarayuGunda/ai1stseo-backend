"""
Daily Admin Metrics Aggregation — DynamoDB version.
Populates ai1stseo-admin-metrics table with rolled-up stats.
Triggered by EventBridge at 02:00 UTC.
"""
from dynamodb_helper import put_item, scan_table
from datetime import date, timedelta


def aggregate_daily_metrics(event=None, context=None):
    """Lambda handler for daily aggregation."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    try:
        users = scan_table('ai1stseo-users', 500)
        audits = scan_table('ai1stseo-audits', 500)
        logs = scan_table('ai1stseo-api-logs', 500)

        scores = [a.get('overall_score', 0) for a in audits if a.get('overall_score')]

        put_item('ai1stseo-admin-metrics', {
            'metric_date': yesterday,
            'total_users': len(users),
            'total_scans': len(audits),
            'avg_score': round(sum(scores) / len(scores), 1) if scores else 0,
            'api_requests': len(logs),
            'database': 'DynamoDB',
        })
        print("Aggregated metrics for {}".format(yesterday))
        return {'status': 'success', 'date': yesterday}
    except Exception as e:
        print("Aggregation failed: {}".format(e))
        return {'status': 'error', 'message': str(e)}


# Lambda handler
def handler(event, context):
    return aggregate_daily_metrics(event, context)
