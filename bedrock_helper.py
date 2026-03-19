"""
bedrock_helper.py
Thin wrapper around AWS Bedrock Runtime for Claude invocations.
Used by the GEO monitoring engine and any future AI probe endpoints.
"""

import json
import boto3
from botocore.exceptions import ClientError

AWS_REGION = 'us-east-1'
DEFAULT_MODEL = 'anthropic.claude-3-haiku-20240307-v1:0'

_client = None


def get_client():
    """Return a cached Bedrock Runtime client."""
    global _client
    if _client is None:
        _client = boto3.client('bedrock-runtime', region_name=AWS_REGION)
    return _client


def invoke_claude(prompt: str, max_tokens: int = 1024, model_id: str = DEFAULT_MODEL) -> str:
    """
    Send a prompt to Claude via Bedrock and return the raw text response.

    Raises:
        RuntimeError: if the Bedrock call fails.
    """
    client = get_client()
    body = {
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    try:
        response = client.invoke_model(
            modelId=model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(body)
        )
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
    except ClientError as e:
        raise RuntimeError(f'Bedrock ClientError: {e.response["Error"]["Message"]}') from e
    except Exception as e:
        raise RuntimeError(f'Bedrock invocation failed: {str(e)}') from e
