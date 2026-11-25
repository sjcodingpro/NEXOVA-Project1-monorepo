"""Nexova company-tools MCP server.

Transport: Streamable HTTP at /mcp (stateless, JSON responses). Chosen over stdio because the
server is consumed remotely by several clients (the LangGraph support agent, MCP Playground,
future teams and partners), not spawned as a local subprocess. Over HTTP every request carries
an OAuth bearer token that MCP Auth validates; with stdio there is no HTTP layer for a bearer
token, so it would only suit a single trusted local process.

Routes
  GET  /.well-known/oauth-protected-resource   Protected Resource Metadata (public, by design)
  POST /mcp                                     MCP endpoint, bearer JWT required (discovery too)
  GET  /health                                  liveness (public, no company data)

Run (from this folder):  uv run uvicorn server:app --host 0.0.0.0 --port 8010
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

import auth  # noqa: E402
import invocation_log  # noqa: E402
import tools  # noqa: E402
from clients import IncidentsApiClient, InventoryReadClient  # noqa: E402
from errors import ToolFailure  # noqa: E402

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(message)s")

INSTRUCTIONS = """\
Nexova company tools. Lets an authorized agent manage tickets in Nexova's Incidents Manager and
read (never modify) inventory.

Tools: get_incident, list_incidents (scope incidents:read); create_incident,
update_incident_status (scope incidents:write); query_inventory (scope inventory:read,
read-only: any write is rejected with INVENTORY_WRITE_FORBIDDEN).

Every tool error is a JSON object with error_code, message and tool. Codes: AUTH_INSUFFICIENT_SCOPE,
INVENTORY_WRITE_FORBIDDEN, VALIDATION_ERROR, NOT_FOUND, INVALID_STATUS_TRANSITION,
UPSTREAM_TIMEOUT, UPSTREAM_ERROR. Requests without a valid OAuth token get HTTP 401 with
AUTH_MISSING_TOKEN or AUTH_INVALID_TOKEN before reaching any tool.
"""

INVENTORY_ARGS = {"operation", "product_id", "office", "search"}


class CompanyToolsMCP(FastMCP):
    """FastMCP whose call_tool is the single choke point for every invocation: it maps errors to
    the documented codes and writes one invocation-log entry per call."""

    mcp_auth = None  # set in create_app

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        started = time.perf_counter()
        client = auth.current_client(self.mcp_auth)
        error_code = None
        try:
            if name == "query_inventory":
                extra = sorted(set(arguments or {}) - INVENTORY_ARGS)
                if extra:  # e.g. {"current_stock": 0} -- a write disguised as a field
                    raise ToolFailure("INVENTORY_WRITE_FORBIDDEN", name,
                                      details={"unexpected_fields": extra,
                                               "allowed_fields": sorted(INVENTORY_ARGS)})
            return await super().call_tool(name, arguments)
        except ToolFailure as exc:
            error_code = exc.code
            raise
        except ToolError as exc:
            cause = exc.__cause__
            if isinstance(cause, ToolFailure):
                error_code = cause.code
                raise cause from None
            if isinstance(cause, ValidationError):
                error_code = "VALIDATION_ERROR"
                fields = [{"field": ".".join(str(p) for p in e["loc"]), "error": e["msg"]}
                          for e in cause.errors()]
                raise ToolFailure("VALIDATION_ERROR", name, details={"fields": fields}) from None
            if "Unknown tool" in str(exc):
                error_code = "VALIDATION_ERROR"
                raise ToolFailure("VALIDATION_ERROR", name, message=f"Unknown tool: {name}") from None
            error_code = "UPSTREAM_ERROR"
            raise ToolFailure("UPSTREAM_ERROR", name, details={"error": type(cause).__name__}) from None
        finally:
            invocation_log.record(client_id=client, tool=name, arguments=arguments,
                                  result="error" if error_code else "success",
                                  error_code=error_code,
                                  duration_ms=(time.perf_counter() - started) * 1000)


def _transport_security() -> TransportSecuritySettings:
    """DNS-rebinding protection: only accept Host headers we serve (localhost, the Codespaces
    forwarded host, anything in MCP_ALLOWED_HOSTS)."""
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    hosts += [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if os.environ.get("CODESPACE_NAME"):
        hosts.append(f"{os.environ['CODESPACE_NAME']}-*.{os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'app.github.dev')}")
    origins = ["https://www.mcpplayground.tech", "https://mcpplayground.tech", "http://localhost:*"]
    origins += [f"https://{h}" for h in hosts if "." in h and "localhost" not in h]
    return TransportSecuritySettings(enable_dns_rebinding_protection=os.environ.get("MCP_DNS_REBINDING_PROTECTION", "false") == "true",
                                     allowed_hosts=hosts, allowed_origins=origins)


def create_app(*, server_config=None, incidents: IncidentsApiClient | None = None,
               inventory: InventoryReadClient | None = None) -> Starlette:
    """Build the ASGI app. Tests pass a local `server_config` (a test issuer) and HTTP-stubbed clients;
    token verification is always MCP Auth's own 'jwt' mode."""
    mcp_auth = auth.build_mcp_auth(server_config)
    mcp = CompanyToolsMCP(name="nexova-company-tools", instructions=INSTRUCTIONS,
                          stateless_http=True, json_response=True, streamable_http_path="/mcp",
                          transport_security=_transport_security())
    mcp.mcp_auth = mcp_auth
    tools.register(mcp, mcp_auth, incidents or IncidentsApiClient(), inventory or InventoryReadClient())

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    async def health(_request):
        return JSONResponse({"status": "ok", "server": "nexova-company-tools"})

    bearer = Middleware(auth.bearer_middleware(mcp_auth))
    app = Starlette(
        routes=[
            Route("/health", health),
            *mcp_auth.resource_metadata_router().routes,
            # Everything under / except the routes above requires a valid bearer token.
            Mount("/", app=mcp.streamable_http_app(), middleware=[bearer]),
        ],
        lifespan=lifespan,
    )
    app.state.mcp = mcp
    app.state.mcp_auth = mcp_auth
    return _cors(auth.ErrorCodeMiddleware(app))


def _cors(app):
    """Browser MCP clients (MCP Playground) call /mcp cross-origin. Only the origins listed in
    MCP_CORS_ORIGINS (comma-separated) may do so; CORS answers the preflight before auth runs, and
    every real request still needs a valid bearer token."""
    origins = [o.strip() for o in os.environ.get("MCP_CORS_ORIGINS", "https://mcpplaygroundonline.com").split(",")
               if o.strip()]
    return CORSMiddleware(app, allow_origins=origins, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                          allow_headers=["authorization", "content-type", "accept", "mcp-protocol-version",
                                         "mcp-session-id", "last-event-id"],
                          expose_headers=["mcp-session-id", "mcp-protocol-version", "www-authenticate"])


if os.environ.get("MCP_AUTH_ISSUER"):
    app = create_app()
