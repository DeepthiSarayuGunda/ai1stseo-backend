"""
ai_chatbot.py
AI SEO Chatbot — conversational interface for SEO insights.

Maintains per-session conversation history and routes queries
through EC2 Bedrock (Claude) with SEO-specific system prompts.
"""

import collections
import logging
import os
import uuid
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

EC2_GEO_ENGINE_URL = os.environ.get("GEO_ENGINE_URL", "http://54.226.251.216:5005")
EC2_TIMEOUT = int(os.environ.get("GEO_ENGINE_TIMEOUT", "45"))

# In-memory session store (session_id → message history)
_sessions: dict[str, list[dict]] = {}
MAX_HISTORY = 20  # messages per session
MAX_SESSIONS = 100

SYSTEM_PROMPT = (
    "You are an expert AI SEO consultant specializing in AEO (Answer Engine Optimization) "
    "and GEO (Generative Engine Optimization). You help brands improve their visibility "
    "in AI-powered search engines like ChatGPT, Perplexity, Gemini, and Claude.\n\n"
    "Your expertise includes:\n"
    "- How AI models select and cite sources\n"
    "- Schema markup and structured data for AI\n"
    "- Content optimization for AI snippet extraction\n"
    "- E-E-A-T signals that AI engines look for\n"
    "- GEO monitoring and brand mention tracking\n"
    "- Technical SEO for AI crawlers\n\n"
    "Be concise, actionable, and specific. When giving advice, include concrete examples. "
    "If asked about a specific URL or brand, provide tailored recommendations."
)


def _call_ec2_generate(prompt: str) -> str:
    """Call EC2 /generate endpoint for chat responses via Bedrock."""
    url = f"{EC2_GEO_ENGINE_URL}/generate"
    try:
        resp = requests.post(url, json={"prompt": prompt}, timeout=EC2_TIMEOUT)
        if resp.status_code == 200:
            return resp.json().get("text", "")
    except Exception as e:
        logger.warning("EC2 generate failed: %s", e)
    raise RuntimeError("AI engine unavailable — could not reach EC2 Bedrock service")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_chat_prompt(history: list[dict], user_message: str) -> str:
    """Build a prompt with conversation context."""
    parts = [f"System: {SYSTEM_PROMPT}\n"]
    # Include last 6 messages for context
    for msg in history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        parts.append(f"{role}: {msg['content']}")
    parts.append(f"User: {user_message}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


def create_session() -> dict:
    """Create a new chat session."""
    # Evict oldest sessions if at capacity
    if len(_sessions) >= MAX_SESSIONS:
        oldest = list(_sessions.keys())[0]
        del _sessions[oldest]

    session_id = str(uuid.uuid4())[:12]
    _sessions[session_id] = []
    return {"session_id": session_id, "created_at": _now()}


def chat(session_id: str, message: str) -> dict:
    """
    Send a message in a chat session and get AI response.

    Auto-creates session if session_id is new.
    """
    if session_id not in _sessions:
        _sessions[session_id] = []

    history = _sessions[session_id]

    # Build prompt with history context
    prompt = _build_chat_prompt(history, message)

    # Get AI response
    response_text = _call_ec2_generate(prompt)

    # Store in history
    history.append({"role": "user", "content": message, "timestamp": _now()})
    history.append({"role": "assistant", "content": response_text, "timestamp": _now()})

    # Trim history
    if len(history) > MAX_HISTORY:
        _sessions[session_id] = history[-MAX_HISTORY:]

    return {
        "session_id": session_id,
        "message": message,
        "response": response_text,
        "timestamp": _now(),
        "history_length": len(_sessions[session_id]),
    }


def get_session_history(session_id: str) -> dict:
    """Get conversation history for a session."""
    if session_id not in _sessions:
        return {"session_id": session_id, "messages": [], "exists": False}
    return {
        "session_id": session_id,
        "messages": _sessions[session_id],
        "exists": True,
    }


def list_sessions() -> list[dict]:
    """List active chat sessions."""
    result = []
    for sid, msgs in _sessions.items():
        last_msg = msgs[-1]["timestamp"] if msgs else None
        result.append({
            "session_id": sid,
            "message_count": len(msgs),
            "last_activity": last_msg,
        })
    return result
