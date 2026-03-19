"""
bedrock_helper.py
Thin wrapper around the Anthropic API for Claude invocations.
Used by the GEO monitoring engine and any future AI probe endpoints.

Requires env var: ANTHROPIC_API_KEY
"""

import os
import anthropic

DEFAULT_MODEL = 'claude-3-haiku-20240307'

_client = None


def get_client() -> anthropic.Anthropic:
    """Return a cached Anthropic client."""
    global _client
    if _client is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError('ANTHROPIC_API_KEY environment variable is not set')
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def invoke_claude(prompt: str, max_tokens: int = 1024, model_id: str = DEFAULT_MODEL) -> str:
    """
    Send a prompt to Claude via Anthropic API and return the raw text response.

    Raises:
        RuntimeError: if the API call fails.
    """
    try:
        client = get_client()
        message = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return message.content[0].text
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f'Anthropic API call failed: {str(e)}') from e
