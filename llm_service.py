"""
llm_service.py
Modular LLM service for the GEO monitoring engine.

Supports: Claude (Anthropic) — extensible to OpenAI, Gemini, Perplexity.
All providers expose the same interface: query(prompt, model) -> str
"""

import os
import re
import json


# ---------------------------------------------------------------------------
# Provider registry — add new providers here without touching call sites
# ---------------------------------------------------------------------------

def _claude(prompt: str, model: str) -> str:
    """Call Claude via Anthropic API."""
    import anthropic
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY environment variable is not set')
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return msg.content[0].text


# Map provider name -> (callable, default model id)
_PROVIDERS = {
    'claude':     (_claude,  'claude-3-haiku-20240307'),
    # 'openai':   (_openai,  'gpt-4o-mini'),      # plug in later
    # 'gemini':   (_gemini,  'gemini-1.5-flash'),  # plug in later
    # 'perplexity': (_perplexity, 'llama-3.1-sonar-small-128k-online'),
}

DEFAULT_PROVIDER = 'claude'


def query(prompt: str, provider: str = DEFAULT_PROVIDER, model: str = None) -> str:
    """
    Send a prompt to the specified LLM provider and return raw text.

    Args:
        prompt:   The full prompt string.
        provider: One of the keys in _PROVIDERS ('claude', 'openai', …).
        model:    Override the default model for the provider.

    Returns:
        Raw text response from the model.

    Raises:
        ValueError:   Unknown provider.
        RuntimeError: API call failed.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Available: {list(_PROVIDERS)}")
    fn, default_model = _PROVIDERS[provider]
    try:
        return fn(prompt, model or default_model)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f'LLM query failed ({provider}): {str(e)}') from e


# ---------------------------------------------------------------------------
# Citation probe analysis helpers
# ---------------------------------------------------------------------------

_CITATION_PROMPT = """\
You are an AI search engine answering a user query. Respond naturally and helpfully.

Query: "{keyword}"

After your full answer, output ONLY a JSON object (no markdown fences, no extra text) \
on a new line in this exact format:
{{
  "mentioned_brands": ["brand or tool names explicitly mentioned in your answer"],
  "citations": ["any URLs, study names, or source references you cited"],
  "answer_structure": "one of: list, paragraph, table, faq, mixed",
  "key_facts": ["up to 5 notable statistics or factual claims from your answer"],
  "ai_summary": "one sentence summarising your answer"
}}"""


def citation_probe(keyword: str, provider: str = DEFAULT_PROVIDER, model: str = None) -> dict:
    """
    Query an AI model for a keyword and extract citation intelligence.

    Returns a dict matching the citation-probe response schema:
        keyword, citations, mentioned_brands, answer_structure,
        key_facts, ai_summary, ai_model, provider, timestamp
    """
    from datetime import datetime

    prompt = _CITATION_PROMPT.format(keyword=keyword)
    raw = query(prompt, provider=provider, model=model)

    # Extract the trailing JSON block Claude appended
    json_match = re.search(r'\{[\s\S]*"mentioned_brands"[\s\S]*\}', raw)
    if not json_match:
        # Fallback: return minimal structure so the endpoint never 500s on parse
        return {
            'keyword': keyword,
            'citations': [],
            'mentioned_brands': [],
            'answer_structure': 'unknown',
            'key_facts': [],
            'ai_summary': raw.strip()[:300],
            'ai_model': model or _PROVIDERS.get(provider, (None, 'unknown'))[1],
            'provider': provider,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            '_parse_warning': 'Could not extract structured JSON from model response'
        }

    structured = json.loads(json_match.group())
    _, default_model = _PROVIDERS[provider]

    return {
        'keyword': keyword,
        'citations':        _as_list(structured.get('citations')),
        'mentioned_brands': _as_list(structured.get('mentioned_brands')),
        'answer_structure': structured.get('answer_structure', 'unknown'),
        'key_facts':        _as_list(structured.get('key_facts')),
        'ai_summary':       structured.get('ai_summary', ''),
        'ai_model':         model or default_model,
        'provider':         provider,
        'timestamp':        datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    }


def _as_list(val) -> list:
    """Coerce a value to a list safely."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val] if val else []
    return []
