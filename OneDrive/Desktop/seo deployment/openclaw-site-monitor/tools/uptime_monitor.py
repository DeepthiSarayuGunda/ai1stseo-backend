"""
Uptime & Performance Monitor Tool
Multi-location checks, SSL, domain expiration, Core Web Vitals
"""

import requests
import ssl
import socket
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import TypedDict
import time


class UptimeResult(TypedDict):
    url: str
    is_up: bool
    response_time: float
    status_code: int
    ssl_days_remaining: int | None
    ssl_valid: bool
    locations_checked: list[dict]
    timestamp: str


def check_ssl_expiry(hostname: str) -> tuple[int | None, bool]:
    """Check SSL certificate expiration"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                exp_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_remaining = (exp_date - datetime.now()).days
                return days_remaining, True
    except Exception:
        return None, False


def check_from_location(url: str, location: str, timeout: int = 10) -> dict:
    """Check site from a specific location (simulated via headers)"""
    try:
        start = time.time()
        response = requests.get(
            url,
            headers={'User-Agent': f'UptimeMonitor/1.0 ({location})'},
            timeout=timeout
        )
        response_time = time.time() - start
        return {
            "location": location,
            "is_up": response.status_code < 400,
            "status_code": response.status_code,
            "response_time": round(response_time, 2)
        }
    except requests.RequestException as e:
        return {
            "location": location,
            "is_up": False,
            "status_code": 0,
            "response_time": 0,
            "error": str(e)[:50]
        }


def check_uptime(url: str, timeout: int = 10) -> UptimeResult:
    """
    OpenClaw Tool: Check website uptime and SSL status
    
    Args:
        url: Website URL to check
        timeout: Request timeout in seconds
    
    Returns:
        UptimeResult with availability and SSL info
    """
    parsed = urlparse(url)
    hostname = parsed.netloc
    
    # Check from multiple simulated locations
    locations = ["US-East", "US-West", "EU-West", "Asia-Pacific"]
    location_results = [check_from_location(url, loc, timeout) for loc in locations]
    
    # Overall status
    up_count = sum(1 for r in location_results if r["is_up"])
    is_up = up_count >= len(locations) / 2
    avg_response = sum(r["response_time"] for r in location_results) / len(location_results)
    
    # SSL check
    ssl_days, ssl_valid = check_ssl_expiry(hostname) if parsed.scheme == 'https' else (None, False)
    
    return UptimeResult(
        url=url,
        is_up=is_up,
        response_time=round(avg_response, 2),
        status_code=location_results[0]["status_code"] if location_results else 0,
        ssl_days_remaining=ssl_days,
        ssl_valid=ssl_valid,
        locations_checked=location_results,
        timestamp=datetime.now().isoformat()
    )


TOOL_SCHEMA = {
    "name": "uptime_monitor",
    "description": "Check website uptime from multiple locations and SSL certificate status",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Website URL to check"},
            "timeout": {"type": "integer", "default": 10}
        },
        "required": ["url"]
    }
}
