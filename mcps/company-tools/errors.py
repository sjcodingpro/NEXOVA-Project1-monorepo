"""Error codes this MCP server returns. Each one is distinct, documented in README.md, and
never a generic "error".

Transport-level (HTTP, before any tool runs; set by auth.ErrorCodeMiddleware):
    AUTH_MISSING_TOKEN        401  no / malformed `Authorization: Bearer <token>` header
    AUTH_INVALID_TOKEN        401  bad signature, expired, wrong issuer or wrong audience

Tool-level (inside a tool result with isError=true, as JSON in the text content):
    AUTH_INSUFFICIENT_SCOPE   403-equivalent  valid token, but missing the scope this tool needs
    INVENTORY_WRITE_FORBIDDEN 403-equivalent  any write attempt on the read-only inventory tool
    VALIDATION_ERROR          422-equivalent  input fails the tool's schema or rules (field-level detail)
    NOT_FOUND                 404-equivalent  the ticket or product id does not exist
    INVALID_STATUS_TRANSITION 409-equivalent  lifecycle rule refused the status change (e.g. resolved -> open)
    UPSTREAM_TIMEOUT          504-equivalent  the Incidents Manager / inventory API didn't answer in time
    UPSTREAM_ERROR            502-equivalent  the Incidents Manager / inventory API failed
"""
from __future__ import annotations

import json

from mcp.server.fastmcp.exceptions import ToolError

MESSAGES = {
    "AUTH_MISSING_TOKEN": "Missing bearer token. Send 'Authorization: Bearer <access token>' from the OAuth server.",
    "AUTH_INVALID_TOKEN": "The access token is invalid, expired, or was issued for a different issuer or audience.",
    "AUTH_INSUFFICIENT_SCOPE": "The access token is valid but lacks the scope this tool requires.",
    "INVENTORY_WRITE_FORBIDDEN": "Inventory tool is read-only. Write operations are not permitted on this MCP server.",
    "VALIDATION_ERROR": "The tool input is invalid.",
    "NOT_FOUND": "The requested resource does not exist.",
    "INVALID_STATUS_TRANSITION": "The Incidents Manager lifecycle does not allow this status change.",
    "UPSTREAM_TIMEOUT": "The company service did not respond in time.",
    "UPSTREAM_ERROR": "The company service returned an error.",
}


class ToolFailure(ToolError):
    """Raised inside a tool. FastMCP turns it into a result with isError=true whose text is a
    JSON object: {"error_code", "message", "tool", "details"?}."""

    def __init__(self, code: str, tool: str, message: str | None = None, details: dict | None = None):
        self.code, self.tool, self.details = code, tool, details
        self.message = message or MESSAGES[code]
        body = {"error_code": code, "message": self.message, "tool": tool}
        if details:
            body["details"] = details
        super().__init__(json.dumps(body))
