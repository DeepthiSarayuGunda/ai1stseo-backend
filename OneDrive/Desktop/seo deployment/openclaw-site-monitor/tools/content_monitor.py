"""
Content Change Detection Tool
Detects SEO regressions, content changes, and accidental misconfigurations
"""

import requests
from bs4 import BeautifulSoup
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import TypedDict


class ContentChange(TypedDict):
    field: str
    old_value: str
    new_value: str
    severity: str


class ContentResult(TypedDict):
    url: str
    changes_detected: bool
    changes: list[ContentChange]
    alerts: list[str]
    content_hash: str
    timestamp: str


def get_content_snapshot(url: str, timeout: int = 15) -> dict:
    """Extract key SEO elements from a page"""
    try:
        response = requests.get(
            url,
            headers={'User-Agent': 'ContentMonitor/1.0'},
            timeout=timeout
        )
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract key elements
        title = soup.find('title')
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_robots = soup.find('meta', attrs={'name': 'robots'})
        canonical = soup.find('link', {'rel': 'canonical'})
        h1_tags = soup.find_all('h1')
        
        # Schema markup
        json_ld = soup.find_all('script', {'type': 'application/ld+json'})
        schema_types = []
        for script in json_ld:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and '@type' in data:
                    schema_types.append(data['@type'])
                elif isinstance(data, list):
                    schema_types.extend(d.get('@type', '') for d in data if isinstance(d, dict))
            except:
                pass
        
        # Content hash for change detection
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        content_text = main_content.get_text()[:5000] if main_content else ''
        content_hash = hashlib.md5(content_text.encode()).hexdigest()
        
        return {
            "title": title.string.strip() if title and title.string else "",
            "meta_description": meta_desc.get('content', '') if meta_desc else "",
            "meta_robots": meta_robots.get('content', '') if meta_robots else "",
            "canonical": canonical.get('href', '') if canonical else "",
            "h1_count": len(h1_tags),
            "h1_text": h1_tags[0].get_text().strip() if h1_tags else "",
            "schema_types": schema_types,
            "content_hash": content_hash,
            "word_count": len(content_text.split())
        }
    except Exception as e:
        return {"error": str(e)}


def compare_snapshots(old: dict, new: dict) -> list[ContentChange]:
    """Compare two snapshots and identify changes"""
    changes = []
    
    critical_fields = {
        "title": "Critical",
        "meta_description": "High",
        "meta_robots": "Critical",
        "canonical": "High",
        "h1_text": "High",
        "h1_count": "Medium"
    }
    
    for field, severity in critical_fields.items():
        old_val = str(old.get(field, ""))
        new_val = str(new.get(field, ""))
        if old_val != new_val:
            changes.append(ContentChange(
                field=field,
                old_value=old_val[:100],
                new_value=new_val[:100],
                severity=severity
            ))
    
    # Schema changes
    old_schemas = set(old.get("schema_types", []))
    new_schemas = set(new.get("schema_types", []))
    if old_schemas != new_schemas:
        removed = old_schemas - new_schemas
        if removed:
            changes.append(ContentChange(
                field="schema_removed",
                old_value=", ".join(removed),
                new_value="",
                severity="High"
            ))
    
    return changes


def _load_history_from_db(url):
    """Load previous content snapshot from RDS (if available), fall back to JSON file."""
    try:
        from db import query_one
        row = query_one(
            "SELECT old_value FROM content_changes "
            "WHERE change_type = 'snapshot' "
            "AND old_value LIKE %s "
            "ORDER BY detected_at DESC LIMIT 1",
            ('%' + url[:100] + '%',)
        )
        if row and row.get("old_value"):
            return json.loads(row["old_value"])
    except Exception:
        pass
    # Fallback to JSON file for backward compatibility on EC2
    history_file = Path("data/content_history.json")
    if history_file.exists():
        try:
            with open(history_file) as f:
                history = json.load(f)
            return history.get(url, {})
        except Exception:
            pass
    return {}


def _save_history_to_db(url, snapshot, site_id=None):
    """Save content snapshot to RDS, fall back to JSON file."""
    try:
        from db import execute
        execute(
            "INSERT INTO content_changes (site_id, change_type, old_value, new_value) "
            "VALUES (%s, 'snapshot', %s, %s)",
            (site_id, json.dumps(snapshot), url)
        )
    except Exception:
        pass
    # Also save to JSON file for backward compatibility
    try:
        history_file = Path("data/content_history.json")
        history = {}
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)
        history[url] = snapshot
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass  # Lambda has no writable filesystem outside /tmp


def check_content_changes(url: str, history_path: str = "data/content_history.json") -> ContentResult:
    """
    Detect content and SEO changes on a page.
    Uses RDS for history storage (Lambda-compatible), falls back to JSON file on EC2.
    """
    # Get current snapshot
    current = get_content_snapshot(url)
    if "error" in current:
        return ContentResult(
            url=url,
            changes_detected=False,
            changes=[],
            alerts=["Error scanning: {}".format(current['error'])],
            content_hash="",
            timestamp=datetime.now().isoformat()
        )

    # Compare with previous
    changes = []
    alerts = []
    previous = _load_history_from_db(url)

    if previous:
        changes = compare_snapshots(previous, current)

        for change in changes:
            if change["severity"] == "Critical":
                alerts.append("[CRITICAL] {} changed".format(change['field']))
            elif change["severity"] == "High":
                alerts.append("[WARNING] {} changed: '{}' -> '{}'".format(
                    change['field'], change['old_value'][:30], change['new_value'][:30]
                ))

        if 'noindex' in current.get('meta_robots', '').lower():
            alerts.append("[CRITICAL] Page has noindex - will be deindexed")
        if current.get('h1_count', 0) == 0 and previous.get('h1_count', 0) > 0:
            alerts.append("[WARNING] H1 tag was removed")
        if not current.get('canonical') and previous.get('canonical'):
            alerts.append("[WARNING] Canonical tag was removed")

    # Save current snapshot
    _save_history_to_db(url, current)

    return ContentResult(
        url=url,
        changes_detected=len(changes) > 0,
        changes=changes,
        alerts=alerts,
        content_hash=current.get('content_hash', ''),
        timestamp=datetime.now().isoformat()
    )


TOOL_SCHEMA = {
    "name": "content_monitor",
    "description": "Detect content changes and SEO regressions on a webpage",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Website URL to monitor"},
            "history_path": {"type": "string", "default": "data/content_history.json"}
        },
        "required": ["url"]
    }
}
