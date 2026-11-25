"""Agent tools that read live operational data (Support Agent Part 2, migrated to MCP).

lookup_ticket(TicketLookupInput) -> TicketLookupOutput
    Reads Nexova's Incidents Manager. One responsibility: tickets. Read-only.

Transport: the company-tools MCP server (mcps/company-tools), as an MCP client through
langchain-mcp-adapters. The agent loads the server's tools over Streamable HTTP and calls
`get_incident` / `list_incidents` with its own OAuth access token (client-credentials grant,
scope `incidents:read` only). This is the ONLY path from the agent to incidents: the old
in-process service-layer client was removed, and tests/pipelines/test_agent_tools.py fails if
anything under services/agent imports the Incidents Manager directly.

Read-only by construction: the agent's token carries no write scope, and McpIncidentClient only
knows the two read tools.

Every call runs under an explicit timeout (TICKET_TOOL_TIMEOUT_S, default 4 seconds) and
never raises: failures come back as found=False with outcome "timeout" / "not_found" /
"error", which the graph routes to its fallback node.
"""
from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import timedelta
from typing import Callable, Literal

from langchain_mcp_adapters.client import MultiServerMCPClient  # imported at load: ~3 s cold, kept out of the timed call

from services.agent.auth import AgentTokenProvider

from pydantic import BaseModel, Field

TICKET_TOOL_TIMEOUT_S = float(os.environ.get("TICKET_TOOL_TIMEOUT_S", "4"))
MAX_LISTED = 5

Outcome = Literal["success", "not_found", "timeout", "error"]
TicketStatus = Literal["open", "in_progress", "resolved", "discarded"]

# Same labels the incident manager UI shows (never raw enum values in an answer).
STATUS_LABELS = {"open": "Open", "in_progress": "In progress", "resolved": "Resolved", "discarded": "Discarded"}
CATEGORY_LABELS = {
    "technical_failure": "Technical failure", "process_error": "Process error",
    "client_complaint": "Client complaint", "candidate_issue": "Candidate issue",
    "staff_issue": "Staff issue", "sla_breach": "SLA breach", "data_quality": "Data quality",
    "other": "Other",
}
ORIGIN_LABELS = {"customer": "Customer", "branch": "Branch", "internal": "Internal"}
BRANCH_LABELS = {"central": "Central", "valencia_operations": "Valencia operations",
                 "miami_office": "Miami office", "remote": "Remote"}


class TicketLookupInput(BaseModel):
    """Exactly one of: a ticket id (detail lookup) or a status filter (list lookup)."""
    ticket_id: int | None = Field(None, ge=1)
    status: TicketStatus | None = None


class Ticket(BaseModel):
    ticket_id: int
    title: str
    status: TicketStatus
    category: str
    origin: str
    branch: str
    created_at: str
    updated_at: str


class TicketLookupOutput(BaseModel):
    found: bool
    outcome: Outcome
    query: TicketLookupInput
    tickets: list[Ticket] = []
    total_matching: int | None = None    # list lookups: how many tickets match the filter
    error: str | None = None             # short, safe description; never an exception dump
    duration_ms: float | None = None
    via: str | None = None               # which MCP tool answered, e.g. "mcp:company-tools/get_incident"


# ------------------------------------------------- incident manager access (via the MCP server)
MCP_SERVER_NAME = "company-tools"
READ_TOOLS = {"get": "get_incident", "list": "list_incidents"}


class McpToolError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code


class McpIncidentClient:
    """Reads tickets through the company-tools MCP server with langchain-mcp-adapters.
    Only the two read tools are ever invoked."""

    def __init__(self, url: str | None = None, token_provider: AgentTokenProvider | None = None):
        self.url = url or os.environ.get("AGENT_MCP_URL", "http://localhost:8010/mcp")
        self._tokens = token_provider or AgentTokenProvider()

    def prepare(self) -> None:
        """Fetch (or reuse the cached) OAuth token before the timed tool call, so a cold token
        request to the authorization server doesn't eat the ticket tool's time budget."""
        self._tokens.get()

    async def _tools(self) -> dict:
        """Tool objects from the MCP server, discovered once per access token. Each call then opens
        one MCP session (initialize + tools/call) instead of a second one for tools/list."""
        token = self._tokens.get()
        cached_token, cached_tools = getattr(self, "_tool_cache", (None, None))
        if cached_token == token:
            return cached_tools
        client = MultiServerMCPClient({MCP_SERVER_NAME: {
            "transport": "streamable_http",
            "url": self.url,
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": timedelta(seconds=TICKET_TOOL_TIMEOUT_S),
        }})
        tools = {t.name: t for t in await client.get_tools(server_name=MCP_SERVER_NAME)}
        self._tool_cache = (token, tools)
        return tools

    async def _invoke(self, action: str, args: dict) -> dict:
        tool_name = READ_TOOLS[action]
        tools = await self._tools()
        if tool_name not in tools:
            raise McpToolError("TOOL_NOT_FOUND", f"{tool_name} not offered by the MCP server")
        msg = await tools[tool_name].ainvoke({"type": "tool_call", "id": "lookup", "name": tool_name, "args": args})
        structured = (msg.artifact or {}).get("structured_content") if isinstance(msg.artifact, dict) else None
        if structured is not None and getattr(msg, "status", "success") != "error":
            return structured
        text = msg.content if isinstance(msg.content, str) else " ".join(
            b.get("text", "") for b in msg.content if isinstance(b, dict))
        try:
            err = json.loads(text)
        except ValueError:
            raise McpToolError("UPSTREAM_ERROR", text[:200])
        raise McpToolError(err.get("error_code", "UPSTREAM_ERROR"), err.get("message", ""))

    def get(self, ticket_id: int) -> dict | None:
        try:
            return asyncio.run(self._invoke("get", {"ticket_id": ticket_id}))
        except McpToolError as exc:
            if exc.code == "NOT_FOUND":
                return None
            raise

    def list(self, status: str) -> dict:
        """{"total": n, "incidents": [newest first, up to MAX_LISTED]}"""
        return asyncio.run(self._invoke("list", {"status": status, "limit": MAX_LISTED}))


_client = McpIncidentClient()
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ticket-tool")


def set_incident_client(client) -> None:
    """Swap the transport (tests use an in-memory stand-in with the same get/list methods)."""
    global _client
    _client = client


def _to_ticket(row: dict) -> Ticket:
    return Ticket(ticket_id=int(row["id"]), title=str(row["title"]), status=row["status"],
                  category=str(row["category"]), origin=str(row["origin"]), branch=str(row["branch"]),
                  created_at=str(row["created_at"]), updated_at=str(row["updated_at"]))


def _with_timeout(fn: Callable, *args):
    return _pool.submit(fn, *args).result(timeout=TICKET_TOOL_TIMEOUT_S)


def lookup_ticket(query: TicketLookupInput) -> TicketLookupOutput:
    """Look up one ticket by id, or the tickets with a given status. Never raises."""
    import time
    started = time.perf_counter()

    def done(**kw) -> TicketLookupOutput:
        return TicketLookupOutput(query=query, duration_ms=round((time.perf_counter() - started) * 1000, 1), **kw)

    try:
        if hasattr(_client, "prepare"):
            _client.prepare()          # token first; it has its own timeout (AGENT_OAUTH_TIMEOUT_S)
        if query.ticket_id is not None:
            row = _with_timeout(_client.get, query.ticket_id)
            if row is None:
                return done(found=False, outcome="not_found", error=f"ticket {query.ticket_id} does not exist",
                            via=f"mcp:{MCP_SERVER_NAME}/{READ_TOOLS['get']}")
            return done(found=True, outcome="success", tickets=[_to_ticket(row)],
                        via=f"mcp:{MCP_SERVER_NAME}/{READ_TOOLS['get']}")
        if query.status is not None:
            page = _with_timeout(_client.list, query.status)
            rows, total = page["incidents"], page["total"]
            if not total:
                return done(found=False, outcome="not_found", total_matching=0,
                            error=f"no tickets with status {query.status}",
                            via=f"mcp:{MCP_SERVER_NAME}/{READ_TOOLS['list']}")
            return done(found=True, outcome="success", total_matching=total,
                        tickets=[_to_ticket(r) for r in rows[:MAX_LISTED]],
                        via=f"mcp:{MCP_SERVER_NAME}/{READ_TOOLS['list']}")
        return done(found=False, outcome="error", error="no ticket id or status to look up")
    except FutureTimeout:
        return done(found=False, outcome="timeout",
                    error=f"MCP server / incident manager did not answer within {TICKET_TOOL_TIMEOUT_S:g}s")
    except McpToolError as exc:  # e.g. UPSTREAM_TIMEOUT, AUTH_INSUFFICIENT_SCOPE from the server
        return done(found=False, outcome="timeout" if exc.code == "UPSTREAM_TIMEOUT" else "error",
                    error=f"MCP server error {exc.code}")
    except Exception as exc:  # MCP server unreachable, token request refused...
        return done(found=False, outcome="error", error=f"MCP server unreachable ({type(exc).__name__})")
