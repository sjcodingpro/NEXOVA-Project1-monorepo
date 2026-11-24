"""The tools this server exposes. Names, descriptions, input schemas (from the type hints and
Field descriptions) and output schemas (from the return models) are what an MCP client sees in
tools/list: they are written so an agent with no human context knows what each tool does,
what it may not do, which scope it needs and what errors it returns.

Field names and values match the Incidents Manager and inventory APIs exactly
(services/api/app/incidents/models.py, services/api/app/inventory/schemas.py).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from clients import IncidentsApiClient, InventoryReadClient, UpstreamError
from errors import ToolFailure

Category = Literal["technical_failure", "process_error", "client_complaint", "candidate_issue",
                   "staff_issue", "sla_breach", "data_quality", "other"]
Status = Literal["open", "in_progress", "resolved", "discarded"]
Origin = Literal["customer", "branch", "internal"]
Branch = Literal["central", "valencia_operations", "miami_office", "remote"]

# Read verbs the inventory tool serves; anything else that looks like a write is rejected
# explicitly with INVENTORY_WRITE_FORBIDDEN (not just "unknown operation").
INVENTORY_READ_OPERATIONS = ("list", "get")
INVENTORY_WRITE_OPERATIONS = ("create", "add", "update", "edit", "patch", "set_stock", "adjust_stock",
                              "delete", "remove", "inbound", "outbound", "restock", "write")


class Incident(BaseModel):
    id: int = Field(description="Ticket id in the Incidents Manager.")
    title: str
    description: str
    category: Category
    status: Status = Field(description="Lifecycle: open -> in_progress -> resolved; open or in_progress -> discarded.")
    origin: Origin
    branch: Branch
    created_at: datetime
    updated_at: datetime


class IncidentList(BaseModel):
    total: int = Field(description="Number of tickets matching the filter.")
    incidents: list[Incident] = Field(description="Matching tickets, newest first (at most `limit`).")


class Product(BaseModel):
    id: int = Field(description="Inventory product (asset) id.")
    name: str
    sku: str
    category: str
    office: str
    current_stock: int = Field(description="Units in stock, computed from inbound and outbound records.")


class InventoryResult(BaseModel):
    operation: Literal["list", "get"]
    total: int
    products: list[Product]


def _upstream(tool: str, exc: UpstreamError) -> ToolFailure:
    if exc.kind == "timeout":
        return ToolFailure("UPSTREAM_TIMEOUT", tool)
    return ToolFailure("UPSTREAM_ERROR", tool, details={"status": exc.status, "detail": exc.detail})


def _check(tool: str, r, *, not_found: str | None = None):
    if r.status_code == 404 and not_found:
        raise ToolFailure("NOT_FOUND", tool, message=not_found)
    if r.status_code == 422:
        raise ToolFailure("VALIDATION_ERROR", tool, details={"upstream": r.json().get("detail")})
    if r.status_code >= 400:
        raise ToolFailure("UPSTREAM_ERROR", tool, details={"status": r.status_code})
    return r.json()


def register(mcp, mcp_auth, incidents: IncidentsApiClient, inventory: InventoryReadClient) -> None:
    from auth import require_scope

    # ------------------------------------------------------------------ incident tickets
    @mcp.tool(
        name="get_incident",
        title="Get incident ticket status",
        description=(
            "Look up ONE incident ticket in Nexova's Incidents Manager by its numeric id and return its "
            "current status, category, origin, branch and dates. Read-only. Requires scope "
            "`incidents:read`. Errors: NOT_FOUND (no such ticket), AUTH_INSUFFICIENT_SCOPE, "
            "UPSTREAM_TIMEOUT, UPSTREAM_ERROR."),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
    )
    def get_incident(
        ticket_id: Annotated[int, Field(ge=1, description="Ticket id, e.g. 96.")],
    ) -> Incident:
        require_scope(mcp_auth, "get_incident", "incidents:read")
        try:
            r = incidents.get(ticket_id)
        except UpstreamError as exc:
            raise _upstream("get_incident", exc)
        return Incident(**_check("get_incident", r, not_found=f"Ticket {ticket_id} does not exist."))

    @mcp.tool(
        name="list_incidents",
        title="List incident tickets",
        description=(
            "List incident tickets from the Incidents Manager, optionally filtered by status "
            "(open, in_progress, resolved, discarded). Returns the total count and the newest "
            "tickets up to `limit`. Read-only. Requires scope `incidents:read`."),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
    )
    def list_incidents(
        status: Annotated[Status | None, Field(description="Only tickets in this status. Omit for all.")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Max tickets returned (1-50).")] = 10,
    ) -> IncidentList:
        require_scope(mcp_auth, "list_incidents", "incidents:read")
        try:
            r = incidents.list(status)
        except UpstreamError as exc:
            raise _upstream("list_incidents", exc)
        rows = sorted(_check("list_incidents", r), key=lambda i: i["created_at"], reverse=True)
        return IncidentList(total=len(rows), incidents=[Incident(**i) for i in rows[:limit]])

    @mcp.tool(
        name="create_incident",
        title="Create incident ticket",
        description=(
            "Register a NEW incident ticket in the Incidents Manager (POST /api/incidents). Every new "
            "ticket starts with status `open`; change it afterwards with update_incident_status. "
            "Requires scope `incidents:write`. Errors: VALIDATION_ERROR (field-level detail), "
            "AUTH_INSUFFICIENT_SCOPE, UPSTREAM_TIMEOUT, UPSTREAM_ERROR."),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False,
                                    openWorldHint=False),
    )
    def create_incident(
        title: Annotated[str, Field(min_length=1, max_length=200, description="Short summary of the incident.")],
        description: Annotated[str, Field(min_length=1, description="What happened, in full.")],
        category: Annotated[Category, Field(description="Incident category.")],
        origin: Annotated[Origin, Field(description="Who reported it: customer, branch or internal.")],
        branch: Annotated[Branch, Field(description="Nexova branch the incident belongs to.")],
    ) -> Incident:
        require_scope(mcp_auth, "create_incident", "incidents:write")
        try:
            r = incidents.create({"title": title, "description": description, "category": category,
                                  "origin": origin, "branch": branch})
        except UpstreamError as exc:
            raise _upstream("create_incident", exc)
        return Incident(**_check("create_incident", r))

    @mcp.tool(
        name="update_incident_status",
        title="Move incident ticket through its lifecycle",
        description=(
            "Change the status of an existing ticket through the Incidents Manager lifecycle endpoint "
            "(PATCH /api/incidents/{id}/status). Allowed moves: open -> in_progress | discarded; "
            "in_progress -> resolved | discarded; resolved and discarded are final. Only the status "
            "can change; no other field is editable. Requires scope `incidents:write`. Errors: "
            "INVALID_STATUS_TRANSITION, NOT_FOUND, VALIDATION_ERROR, AUTH_INSUFFICIENT_SCOPE, "
            "UPSTREAM_TIMEOUT, UPSTREAM_ERROR."),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                                    openWorldHint=False),
    )
    def update_incident_status(
        ticket_id: Annotated[int, Field(ge=1, description="Ticket id to update.")],
        status: Annotated[Status, Field(description="Target status.")],
    ) -> Incident:
        require_scope(mcp_auth, "update_incident_status", "incidents:write")
        try:
            r = incidents.update_status(ticket_id, status)
        except UpstreamError as exc:
            raise _upstream("update_incident_status", exc)
        if r.status_code == 400:   # the Incidents Manager refused the lifecycle move
            raise ToolFailure("INVALID_STATUS_TRANSITION", "update_incident_status",
                              message=r.json().get("detail", "Transition not allowed."),
                              details={"ticket_id": ticket_id, "target_status": status})
        return Incident(**_check("update_incident_status", r, not_found=f"Ticket {ticket_id} does not exist."))

    # ------------------------------------------------------------------ inventory (read-only)
    @mcp.tool(
        name="query_inventory",
        title="Query inventory (read-only)",
        description=(
            "READ-ONLY lookup of Nexova inventory products and current stock. operation='list' "
            "returns all products (optionally filtered by office or name/sku text); operation='get' "
            "returns one product by product_id. Any write operation (create, update, delete, "
            "adjust stock, inbound/outbound orders...) is explicitly rejected with "
            "INVENTORY_WRITE_FORBIDDEN: this server never modifies inventory. Requires scope "
            "`inventory:read` (no inventory write scope exists). Errors: INVENTORY_WRITE_FORBIDDEN, "
            "VALIDATION_ERROR, NOT_FOUND, AUTH_INSUFFICIENT_SCOPE, UPSTREAM_TIMEOUT, UPSTREAM_ERROR."),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
    )
    def query_inventory(
        operation: Annotated[str, Field(description="'list' or 'get'. Write operations are rejected.")] = "list",
        product_id: Annotated[int | None, Field(ge=1, description="Required for operation='get'.")] = None,
        office: Annotated[str | None, Field(description="operation='list' only: exact office name filter.")] = None,
        search: Annotated[str | None, Field(description="operation='list' only: text matched against name or sku.")] = None,
    ) -> InventoryResult:
        op = (operation or "").strip().lower()
        # Rejected before anything else -- before the scope check and before any HTTP call, so a
        # write attempt can never reach the inventory service whatever the token holds.
        if op in INVENTORY_WRITE_OPERATIONS or op not in INVENTORY_READ_OPERATIONS and any(
                w in op for w in INVENTORY_WRITE_OPERATIONS):
            raise ToolFailure("INVENTORY_WRITE_FORBIDDEN", "query_inventory",
                              details={"attempted_operation": operation,
                                       "allowed_operations": list(INVENTORY_READ_OPERATIONS)})
        if op not in INVENTORY_READ_OPERATIONS:
            raise ToolFailure("VALIDATION_ERROR", "query_inventory",
                              details={"field": "operation", "value": operation,
                                       "allowed": list(INVENTORY_READ_OPERATIONS)})
        require_scope(mcp_auth, "query_inventory", "inventory:read")
        try:
            if op == "get":
                if product_id is None:
                    raise ToolFailure("VALIDATION_ERROR", "query_inventory",
                                      details={"field": "product_id", "error": "required when operation='get'"})
                r = inventory.get_product(product_id)
                row = _check("query_inventory", r, not_found=f"Product {product_id} does not exist.")
                return InventoryResult(operation="get", total=1, products=[Product(**row)])
            rows = _check("query_inventory", inventory.list_products())
        except UpstreamError as exc:
            raise _upstream("query_inventory", exc)
        if office:
            rows = [p for p in rows if p["office"] == office]
        if search:
            s = search.lower()
            rows = [p for p in rows if s in p["name"].lower() or s in p["sku"].lower()]
        return InventoryResult(operation="list", total=len(rows), products=[Product(**p) for p in rows])
