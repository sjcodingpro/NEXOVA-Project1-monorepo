"""OAuth for the company-tools MCP server, with MCP Auth (`mcpauth`), resource-server mode.

- Protected Resource Metadata is served at /.well-known/oauth-protected-resource, so any MCP
  client can discover which authorization server issues tokens for this server and which
  scopes exist, before it calls anything.
- Every request to /mcp (tool discovery included) must carry a valid bearer JWT: signature
  checked against the issuer's JWKS, issuer and audience checked.
- Each tool then checks the scope it needs (least privilege):
      incidents:read   get_incident, list_incidents
      incidents:write  create_incident, update_incident_status
      inventory:read   query_inventory
  No inventory write scope exists, so no token can ever be granted inventory writes.

FastMCP's built-in auth is deliberately not used.
"""
from __future__ import annotations

import json
import logging
import os
from mcpauth import MCPAuth
from mcpauth.config import AuthServerConfig, AuthServerType
from mcpauth.types import ResourceServerConfig, ResourceServerMetadata
from mcpauth.utils import fetch_server_config

from errors import MESSAGES, ToolFailure


# --- JWKS caching -------------------------------------------------------------------------------
# mcpauth 0.2.0b1 builds a new PyJWKClient for every request (token_verifier.create_verify_jwt_function
# calls create_verify_jwt(jwks_uri) inside verify_jwt), so every HTTP request re-downloads the
# authorization server's signing keys. One MCP tool call is 3-4 HTTP requests, so against a real
# Auth0 tenant that added seconds per call. We memoise the verifier per JWKS URI; PyJWKClient then
# keeps the keys cached (and refetches on an unknown `kid`, so key rotation still works).
import functools as _functools

from mcpauth.auth import token_verifier as _token_verifier
from mcpauth.utils import create_verify_jwt as _create_verify_jwt


@_functools.lru_cache(maxsize=8)
def _cached_verify_jwt(jwks_uri: str, leeway: float = 60):
    return _create_verify_jwt(jwks_uri, leeway=leeway)


_token_verifier.create_verify_jwt = _cached_verify_jwt

log = logging.getLogger("company_tools.auth")

SCOPES = {
    "incidents:read": "Read incident tickets (get one, list by status).",
    "incidents:write": "Create incident tickets and move them through the status lifecycle.",
    "inventory:read": "Read inventory products and current stock. There is no inventory write scope.",
}

# mcpauth's bearer error codes -> this server's documented codes (errors.py).
_AUTH_CODE_MAP = {
    "missing_auth_header": "AUTH_MISSING_TOKEN",
    "invalid_auth_header_format": "AUTH_MISSING_TOKEN",
    "missing_bearer_token": "AUTH_MISSING_TOKEN",
    "invalid_token": "AUTH_INVALID_TOKEN",
    "invalid_issuer": "AUTH_INVALID_TOKEN",
    "invalid_audience": "AUTH_INVALID_TOKEN",
    "missing_required_scopes": "AUTH_INSUFFICIENT_SCOPE",
}


def resource_url() -> str:
    """This server's public identifier (its /mcp URL). In Codespaces, the forwarded URL."""
    return os.environ.get("MCP_RESOURCE_URL", "http://localhost:8010/mcp")


def build_mcp_auth(server_config: AuthServerConfig | None = None) -> MCPAuth:
    """MCPAuth in resource-server mode. `server_config` is fetched from the issuer's OIDC
    discovery document unless given (tests pass a local one)."""
    if server_config is None:
        issuer = os.environ["MCP_AUTH_ISSUER"]  # e.g. https://<tenant>.us.auth0.com/
        server_config = fetch_server_config(issuer, AuthServerType.OIDC)
    return MCPAuth(protected_resources=[ResourceServerConfig(metadata=ResourceServerMetadata(
        resource=resource_url(),
        authorization_servers=[server_config],
        scopes_supported=list(SCOPES),
        resource_name="Nexova company tools (Incidents Manager + inventory)",
        resource_documentation="https://github.com/sjcodingpro/NEXOVA-Project1-monorepo/tree/main/mcps/company-tools",
    ))])


def bearer_middleware(mcp_auth: MCPAuth):
    """Validates the bearer JWT on every /mcp request with MCP Auth's 'jwt' mode: signature
    against the issuer's JWKS, expiry, issuer (must be the configured authorization server) and
    audience. No global required_scopes: listing tools needs only a valid token; each tool
    enforces its own scope."""
    return mcp_auth.bearer_auth_middleware(
        "jwt",
        resource=resource_url(),
        audience=os.environ.get("MCP_AUTH_AUDIENCE") or None,
    )


def current_client(mcp_auth: MCPAuth) -> str:
    info = mcp_auth.auth_info
    if info is None:
        return "anonymous"
    return info.client_id or info.subject or "unknown"


def require_scope(mcp_auth: MCPAuth, tool: str, scope: str) -> None:
    info = mcp_auth.auth_info
    granted = list(info.scopes) if info else []
    if scope not in granted:
        raise ToolFailure("AUTH_INSUFFICIENT_SCOPE", tool,
                          details={"required_scope": scope, "granted_scopes": granted})


class ErrorCodeMiddleware:
    """Outermost ASGI middleware. Rewrites mcpauth's 401/403 JSON bodies to carry this server's
    documented `error_code` + `message` (keeping its WWW-Authenticate header), and logs every
    rejected request. All other responses pass through untouched (streams included)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        state = {"start": None, "body": b""}

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                if message["status"] in (401, 403):
                    state["start"] = message          # hold it until the body is rewritten
                    return
                return await send(message)
            if message["type"] == "http.response.body" and state["start"] is not None:
                state["body"] += message.get("body", b"")
                if message.get("more_body"):
                    return
                start, body = state["start"], state["body"]
                try:
                    payload = json.loads(body or b"{}")
                except ValueError:
                    payload = {}
                code = _AUTH_CODE_MAP.get(payload.get("error"), "AUTH_INVALID_TOKEN")
                new_body = json.dumps({"error_code": code, "message": MESSAGES[code],
                                       "oauth_error": payload.get("error")}).encode()
                headers = [(k, v) for k, v in start["headers"] if k.lower() != b"content-length"]
                headers.append((b"content-length", str(len(new_body)).encode()))
                log.warning(json.dumps({"event": "auth_rejected", "status": start["status"],
                                        "error_code": code, "path": scope.get("path")}))
                await send({**start, "headers": headers})
                return await send({"type": "http.response.body", "body": new_body})
            return await send(message)

        return await self.app(scope, receive, wrapped_send)
