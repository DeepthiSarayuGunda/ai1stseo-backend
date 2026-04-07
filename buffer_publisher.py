"""
buffer_publisher.py
Buffer GraphQL API publishing bridge for the AI1stSEO social scheduler.

Buffer free plan: 3 channels, 10 posts per channel queue.
API access is available on ALL plans including free.
API uses GraphQL at https://api.buffer.com

Usage:
    from buffer_publisher import BufferPublisher

    pub = BufferPublisher()
    result = pub.publish(text, channel_id)
    result = pub.schedule(text, channel_id, due_at="2026-04-01T10:00:00Z")

Environment variables:
    BUFFER_API_KEY          — API key from https://publish.buffer.com/settings/api
    BUFFER_ORG_ID           — Organization ID (fetched automatically if not set)
    BUFFER_CHANNEL_X        — Channel ID for Twitter/X
    BUFFER_CHANNEL_IG       — Channel ID for Instagram
    BUFFER_CHANNEL_FB       — Channel ID for Facebook
    BUFFER_CHANNEL_LI       — Channel ID for LinkedIn
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

API_URL = "https://api.buffer.com"

# Map our platform names to Buffer channel env vars
CHANNEL_ENV = {
    "twitter/x": "BUFFER_CHANNEL_X",
    "twitter": "BUFFER_CHANNEL_X",
    "x": "BUFFER_CHANNEL_X",
    "instagram": "BUFFER_CHANNEL_IG",
    "facebook": "BUFFER_CHANNEL_FB",
    "linkedin": "BUFFER_CHANNEL_LI",
}


class BufferPublisher:
    """Thin wrapper around the Buffer GraphQL API."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("BUFFER_API_KEY", "")
        self.org_id = os.environ.get("BUFFER_ORG_ID", "")

    @property
    def configured(self):
        return bool(self.api_key)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _graphql(self, query, dry_run=False):
        """Execute a GraphQL request against Buffer API."""
        payload = {"query": query}
        if dry_run:
            return {"success": True, "data": {"dry_run": True, "query": query}}
        try:
            import requests
            resp = requests.post(API_URL, headers=self._headers(),
                                json=payload, timeout=30)
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and "errors" not in data:
                return {"success": True, "data": data.get("data", data)}
            errors = data.get("errors", [{"message": f"HTTP {resp.status_code}"}])
            msg = errors[0].get("message", str(errors)) if errors else "Unknown error"
            return {"success": False, "error": msg, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    def _resolve_channel(self, platform, channel_id=None):
        """Get the Buffer channel ID for a platform."""
        if channel_id:
            return channel_id
        key = platform.strip().lower()
        env_var = CHANNEL_ENV.get(key, "")
        return os.environ.get(env_var, "") if env_var else ""

    # ── Queries ───────────────────────────────────────────────────────────

    def get_organizations(self, dry_run=False):
        """Fetch organizations (needed to get org ID)."""
        if not self.configured:
            return {"success": False, "error": "BUFFER_API_KEY not set", "data": None}
        query = """
        query GetOrganizations {
          account {
            organizations {
              id
              name
            }
          }
        }
        """
        return self._graphql(query, dry_run)

    def get_channels(self, org_id=None, dry_run=False):
        """Fetch connected social channels."""
        if not self.configured:
            return {"success": False, "error": "BUFFER_API_KEY not set", "data": None}
        oid = org_id or self.org_id
        if not oid:
            # Auto-fetch org ID
            org_result = self.get_organizations(dry_run)
            if not org_result["success"]:
                return org_result
            orgs = (org_result.get("data", {}).get("account", {})
                    .get("organizations", []))
            if orgs:
                oid = orgs[0]["id"]
                self.org_id = oid
            else:
                return {"success": False, "error": "No organizations found", "data": None}

        query = f"""
        query GetChannels {{
          organization(input: {{ organizationId: "{oid}" }}) {{
            channels {{
              id
              name
              service
              avatar
            }}
          }}
        }}
        """
        return self._graphql(query, dry_run)

    # ── Mutations ─────────────────────────────────────────────────────────

    def build_create_post_query(self, text, channel_id, mode="shareNow",
                                due_at=None, image_url=None):
        """
        Build a GraphQL createPost mutation.

        Args:
            text: Post content
            channel_id: Buffer channel ID
            mode: "shareNow" | "addToQueue" | "customSchedule"
            due_at: ISO datetime for customSchedule mode
            image_url: Optional image URL
        """
        # Escape text for GraphQL string
        escaped = (text.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("\n", "\\n"))

        scheduling = "automatic"
        schedule_line = ""
        if due_at:
            mode = "customSchedule"
            schedule_line = f'    dueAt: "{due_at}"'

        assets_block = ""
        if image_url:
            img_escaped = image_url.replace('"', '\\"')
            assets_block = f"""
    assets: {{
      images: [{{ url: "{img_escaped}" }}]
    }}"""

        query = f"""mutation CreatePost {{
  createPost(input: {{
    text: "{escaped}",
    channelId: "{channel_id}",
    schedulingType: {scheduling},
    mode: {mode}{',' if schedule_line or assets_block else ''}
{schedule_line}{',' if schedule_line and assets_block else ''}{assets_block}
  }}) {{
    ... on PostActionSuccess {{
      post {{
        id
        text
      }}
    }}
    ... on MutationError {{
      message
    }}
  }}
}}"""
        return query

    def publish(self, text, platform=None, channel_id=None,
                due_at=None, image_url=None, dry_run=False):
        """
        Publish or schedule a post via Buffer.

        Args:
            text: Post content (caption + hashtags)
            platform: Platform name (e.g. "Twitter/X", "Instagram")
            channel_id: Buffer channel ID (or resolved from env)
            due_at: ISO datetime for scheduling (None = post now)
            image_url: Optional image URL
            dry_run: If True, return the query without executing

        Returns:
            dict with success, error, data keys
        """
        if not self.configured:
            return {"success": False, "error": "BUFFER_API_KEY not set", "data": None}

        cid = self._resolve_channel(platform, channel_id) if platform else channel_id
        if not cid:
            env_hint = CHANNEL_ENV.get(platform.strip().lower(), "BUFFER_CHANNEL_??") if platform else "?"
            return {"success": False,
                    "error": f"No channel ID for '{platform}'. Set {env_hint} env var or pass channel_id.",
                    "data": None}

        mode = "customSchedule" if due_at else "shareNow"
        query = self.build_create_post_query(text, cid, mode, due_at, image_url)

        result = self._graphql(query, dry_run)

        if result["success"] and not dry_run:
            data = result.get("data", {})
            create = data.get("createPost", {})
            if "post" in create:
                logger.info("Buffer publish OK: platform=%s post_id=%s",
                            platform, create["post"].get("id"))
            elif "message" in create:
                return {"success": False, "error": create["message"], "data": data}

        return result

    def schedule(self, text, platform=None, channel_id=None,
                 due_at=None, image_url=None, dry_run=False):
        """Alias for publish with scheduling."""
        if not due_at:
            due_at = datetime.now(timezone.utc).isoformat()
        return self.publish(text, platform, channel_id, due_at, image_url, dry_run)


# ── Convenience functions ─────────────────────────────────────────────────────

_publisher = None

def get_publisher():
    global _publisher
    if _publisher is None:
        _publisher = BufferPublisher()
    return _publisher

def publish_post(text, platform=None, channel_id=None,
                 due_at=None, image_url=None, dry_run=False):
    return get_publisher().publish(text, platform, channel_id,
                                  due_at, image_url, dry_run)

def is_configured():
    return get_publisher().configured


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pub = BufferPublisher()
    print(f"Buffer API: {API_URL}")
    print(f"API key set: {pub.configured}")

    if not pub.configured:
        print("\nSet BUFFER_API_KEY to test:")
        print("  set BUFFER_API_KEY=your-key")
        print("  python buffer_publisher.py")
        print("\nGet your key at: https://publish.buffer.com/settings/api")
        exit(0)

    # Fetch orgs
    print("\nFetching organizations...")
    result = pub.get_organizations()
    if result["success"]:
        orgs = result["data"].get("account", {}).get("organizations", [])
        for o in orgs:
            print(f"  org: {o.get('name', '?')} id={o['id']}")
    else:
        print(f"  Error: {result['error']}")

    # Fetch channels
    print("\nFetching channels...")
    result = pub.get_channels()
    if result["success"]:
        org_data = result["data"].get("organization", {})
        channels = org_data.get("channels", [])
        for c in channels:
            print(f"  {c.get('service', '?'):12s} | {c.get('name', '?'):20s} | id={c['id']}")
        if not channels:
            print("  No channels connected. Add them at https://publish.buffer.com/channels")
    else:
        print(f"  Error: {result['error']}")

    # Dry-run test
    print("\nDry-run: schedule a test post...")
    result = pub.publish(
        text="Test post from AI1stSEO scheduler #AISEO",
        platform="Twitter/X",
        dry_run=True,
    )
    if result["success"]:
        print(f"  Query:\n{result['data']['query']}")
    else:
        print(f"  Error: {result['error']}")
