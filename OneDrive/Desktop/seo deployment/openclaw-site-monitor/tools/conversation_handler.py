"""
Conversational Handler for WhatsApp/Chat Interactions
Allows users to ask questions about their site and get AI-powered responses
"""

import json
from typing import Optional
from tools.ai_analyzer import get_analyzer
from tools.seo_scanner import scan_site


# In-memory context cache (persists across warm Lambda invocations)
_context_cache = {}


def _load_context_from_db(user_id: str) -> dict:
    """Load conversation context from RDS, fall back to in-memory cache."""
    try:
        from db import query_one
        row = query_one(
            "SELECT data FROM reports WHERE report_type = 'chat_context' "
            "AND data->>'user_id' = %s ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        if row and row.get("data"):
            return row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
    except Exception:
        pass
    return _context_cache.get(user_id, {})


def _save_context_to_db(user_id: str, context: dict):
    """Save conversation context to RDS, also cache in memory."""
    _context_cache[user_id] = context
    try:
        from db import execute, insert_returning
        context_data = json.dumps({"user_id": user_id, **context}, default=str)
        # Upsert: delete old, insert new
        execute(
            "DELETE FROM reports WHERE report_type = 'chat_context' "
            "AND data->>'user_id' = %s",
            (user_id,)
        )
        insert_returning(
            "INSERT INTO reports (project_id, report_type, title, data) "
            "VALUES (%s, 'chat_context', %s, %s) RETURNING id",
            ("24766ac2-1b1b-4c3a-bb4f-97f20ca78bf2",
             "Chat context for {}".format(user_id), context_data)
        )
    except Exception:
        pass  # Graceful degradation — in-memory cache still works


def get_user_context(user_id: str) -> dict:
    """Get or create context for a user"""
    ctx = _load_context_from_db(user_id)
    if not ctx or "last_scan" not in ctx:
        ctx = {"last_scan": None, "site_url": None, "history": []}
        _context_cache[user_id] = ctx
    return ctx


def update_user_context(user_id: str, scan_data: dict, site_url: str):
    """Update user's context with new scan data"""
    ctx = _load_context_from_db(user_id)
    ctx = {
        "last_scan": scan_data,
        "site_url": site_url,
        "history": ctx.get("history", [])[-10:]
    }
    _save_context_to_db(user_id, ctx)


def handle_message(user_id: str, message: str) -> str:
    """
    Handle an incoming message from a user.
    Returns the AI-generated response.
    
    Supports commands:
    - "scan [url]" - Run a new scan
    - "why" - Explain issues
    - "fix [issue]" - Get fix code
    - "compare" - Compare to competitors
    - Any question - AI answers based on last scan
    """
    message_lower = message.lower().strip()
    context = get_user_context(user_id)
    analyzer = get_analyzer()
    
    # Command: Scan a site
    if message_lower.startswith("scan "):
        url = message[5:].strip()
        if not url.startswith("http"):
            url = "https://" + url
        
        try:
            scan_data = scan_site(url)
            update_user_context(user_id, scan_data, url)
            
            # Generate AI summary
            summary = analyzer.analyze_scan_results(scan_data)
            score = scan_data["score"]
            
            return f"*Scan Complete: {url}*\n\nScore: {score}/100\n\n{summary}"
            
        except Exception as e:
            return f"Could not scan {url}: {str(e)}"
    
    # Command: Why (explain issues)
    if message_lower in ["why", "why?", "explain", "what's wrong"]:
        if not context.get("last_scan"):
            return "I don't have a recent scan. Send 'scan yoursite.com' first."
        
        scan_data = context["last_scan"]
        issues = scan_data.get("critical_issues", []) + scan_data.get("warnings", [])[:3]
        
        if not issues:
            return "Good news - no major issues found in your last scan!"
        
        explanation = analyzer.answer_question(
            "Why is my score low? What are the main problems?",
            scan_data
        )
        return explanation
    
    # Command: Fix
    if message_lower.startswith("fix"):
        if not context.get("last_scan"):
            return "I don't have a recent scan. Send 'scan yoursite.com' first."
        
        scan_data = context["last_scan"]
        
        # If they specified an issue
        if len(message) > 4:
            issue = message[4:].strip()
        else:
            # Use top critical issue
            issues = scan_data.get("critical_issues", [])
            if not issues:
                return "No critical issues to fix. Your site is in good shape!"
            issue = issues[0]
        
        fix = analyzer.generate_fix_code(issue, {"url": context.get("site_url", "")})
        
        return f"*Fix for: {issue}*\n\nAdd this {fix.get('location', 'to your site')}:\n\n```\n{fix.get('code', 'N/A')}\n```\n\n{fix.get('explanation', '')}"
    
    # Command: Compare to competitors
    if message_lower in ["compare", "competitors", "vs"]:
        if not context.get("last_scan"):
            return "I don't have a recent scan. Send 'scan yoursite.com' first."
        
        return "Competitor comparison coming soon! For now, run the full demo on the server to see competitor analysis."
    
    # Command: Help
    if message_lower in ["help", "?", "commands"]:
        return """*Site Monitor Commands*

scan [url] - Scan a website
why - Explain current issues  
fix - Get code to fix top issue
fix [issue] - Get code for specific issue
compare - Compare to competitors

Or just ask any question about your site!"""
    
    # Default: Answer question using AI
    if context.get("last_scan"):
        return analyzer.answer_question(message, context["last_scan"])
    else:
        return "Hi! Send 'scan yoursite.com' to get started, or 'help' for commands."


def format_for_whatsapp(response: str) -> str:
    """Format response for WhatsApp (markdown adjustments)"""
    # WhatsApp uses *bold* and _italic_ like markdown
    # But code blocks need to be single backticks
    response = response.replace("```\n", "`").replace("\n```", "`")
    response = response.replace("```", "`")
    return response


# Example webhook handler (for integration with WhatsApp Business API)
def webhook_handler(payload: dict) -> str:
    """
    Handle incoming webhook from WhatsApp Business API.
    Returns the response message.
    """
    # Extract message details (structure depends on provider)
    user_id = payload.get("from", payload.get("sender", "unknown"))
    message = payload.get("text", payload.get("body", payload.get("message", "")))
    
    if not message:
        return "I didn't catch that. Send 'help' for commands."
    
    response = handle_message(user_id, message)
    return format_for_whatsapp(response)


# OpenClaw tool registration
TOOL_SCHEMA = {
    "name": "conversation_handler",
    "description": "Handle conversational interactions about SEO scans",
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User identifier"},
            "message": {"type": "string", "description": "User's message"}
        },
        "required": ["user_id", "message"]
    }
}
