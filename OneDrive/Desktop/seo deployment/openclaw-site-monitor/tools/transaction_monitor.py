"""
Transaction & API Health Monitor Tool
Tests critical paths, forms, and API endpoints
"""

import requests
from datetime import datetime
from typing import TypedDict
from urllib.parse import urljoin
from bs4 import BeautifulSoup


class TransactionResult(TypedDict):
    name: str
    status: str
    response_time: float
    error: str | None


class TransactionReport(TypedDict):
    url: str
    transactions_tested: int
    passed: int
    failed: int
    results: list[TransactionResult]
    api_health: list[dict]
    timestamp: str


def test_form_exists(soup: BeautifulSoup, form_type: str) -> TransactionResult:
    """Check if a specific form type exists and is functional"""
    import time
    start = time.time()
    
    # Look for common form patterns
    form_patterns = {
        "contact": ["contact", "message", "inquiry", "get-in-touch"],
        "newsletter": ["newsletter", "subscribe", "email-signup", "mailing"],
        "search": ["search", "query", "find"],
        "login": ["login", "signin", "sign-in", "auth"]
    }
    
    patterns = form_patterns.get(form_type, [form_type])
    
    forms = soup.find_all('form')
    for form in forms:
        form_str = str(form).lower()
        if any(p in form_str for p in patterns):
            # Check form has required elements
            has_input = form.find('input')
            has_submit = form.find('button') or form.find('input', {'type': 'submit'})
            
            if has_input and has_submit:
                return TransactionResult(
                    name=f"{form_type}_form",
                    status="pass",
                    response_time=round(time.time() - start, 2),
                    error=None
                )
    
    return TransactionResult(
        name=f"{form_type}_form",
        status="not_found",
        response_time=round(time.time() - start, 2),
        error=f"No {form_type} form found"
    )


def test_api_endpoint(url: str, endpoint: str, timeout: int = 10) -> dict:
    """Test an API endpoint"""
    import time
    full_url = urljoin(url, endpoint)
    start = time.time()
    
    try:
        response = requests.get(
            full_url,
            headers={'User-Agent': 'TransactionMonitor/1.0'},
            timeout=timeout
        )
        return {
            "endpoint": endpoint,
            "status": "healthy" if response.status_code < 400 else "unhealthy",
            "status_code": response.status_code,
            "response_time": round(time.time() - start, 2)
        }
    except requests.RequestException as e:
        return {
            "endpoint": endpoint,
            "status": "error",
            "status_code": 0,
            "response_time": round(time.time() - start, 2),
            "error": str(e)[:50]
        }


def test_critical_paths(url: str, timeout: int = 15) -> TransactionReport:
    """
    OpenClaw Tool: Test critical transaction paths and API health
    
    Args:
        url: Website URL to test
        timeout: Request timeout in seconds
    
    Returns:
        TransactionReport with test results
    """
    results = []
    api_health = []
    
    try:
        response = requests.get(
            url,
            headers={'User-Agent': 'TransactionMonitor/1.0'},
            timeout=timeout
        )
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Test common forms
        form_types = ["contact", "newsletter", "search"]
        for form_type in form_types:
            result = test_form_exists(soup, form_type)
            results.append(result)
        
        # Test common API/resource endpoints
        common_endpoints = [
            "/robots.txt",
            "/sitemap.xml",
            "/favicon.ico",
            "/.well-known/security.txt"
        ]
        
        for endpoint in common_endpoints:
            api_result = test_api_endpoint(url, endpoint, timeout=5)
            api_health.append(api_result)
        
        # Check for broken internal links (sample)
        links = soup.find_all('a', href=True)[:10]  # Check first 10 links
        for link in links:
            href = link.get('href', '')
            if href.startswith('/') and not href.startswith('//'):
                link_result = test_api_endpoint(url, href, timeout=5)
                if link_result["status"] == "unhealthy":
                    results.append(TransactionResult(
                        name=f"internal_link:{href[:30]}",
                        status="fail",
                        response_time=link_result["response_time"],
                        error=f"Broken link: {link_result['status_code']}"
                    ))
        
    except requests.RequestException as e:
        results.append(TransactionResult(
            name="page_load",
            status="fail",
            response_time=0,
            error=str(e)[:50]
        ))
    
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    
    return TransactionReport(
        url=url,
        transactions_tested=len(results),
        passed=passed,
        failed=failed,
        results=results,
        api_health=api_health,
        timestamp=datetime.now().isoformat()
    )


TOOL_SCHEMA = {
    "name": "transaction_monitor",
    "description": "Test critical transaction paths, forms, and API endpoints",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Website URL to test"},
            "timeout": {"type": "integer", "default": 15}
        },
        "required": ["url"]
    }
}
