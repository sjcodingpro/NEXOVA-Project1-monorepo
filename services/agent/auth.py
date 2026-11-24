"""OAuth access token for the agent (MCP client side).

Client-credentials grant against the authorization server the company-tools MCP server trusts.
The agent's client is granted `incidents:read` only, so even a bug in the agent cannot write
through the MCP server: the server would answer AUTH_INSUFFICIENT_SCOPE.

Env: AGENT_OAUTH_TOKEN_URL, AGENT_OAUTH_CLIENT_ID, AGENT_OAUTH_CLIENT_SECRET, AGENT_OAUTH_AUDIENCE.
"""
from __future__ import annotations

import os
import threading
import time as _time

TOKEN_TIMEOUT_S = float(os.getenv("AGENT_OAUTH_TIMEOUT_S", "4"))


class AgentTokenProvider:
    """OAuth 2.1 client-credentials grant against the same authorization server the MCP server
    trusts (AGENT_OAUTH_TOKEN_URL, AGENT_OAUTH_CLIENT_ID / _SECRET, AGENT_OAUTH_AUDIENCE). The
    token is cached until a minute before it expires."""

    def __init__(self):
        self._token, self._expires_at, self._lock = None, 0.0, threading.Lock()

    def get(self) -> str:
        import httpx
        with self._lock:
            if self._token and _time.time() < self._expires_at - 60:
                return self._token
            r = httpx.post(os.environ["AGENT_OAUTH_TOKEN_URL"], timeout=TOKEN_TIMEOUT_S, json={
                "grant_type": "client_credentials",
                "client_id": os.environ["AGENT_OAUTH_CLIENT_ID"],
                "client_secret": os.environ["AGENT_OAUTH_CLIENT_SECRET"],
                "audience": os.environ["AGENT_OAUTH_AUDIENCE"],
            })
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._expires_at = _time.time() + float(body.get("expires_in", 300))
            return self._token
