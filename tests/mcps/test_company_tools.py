"""Tests for the company-tools MCP server (mcps/company-tools).

Auth runs for real: tokens are RS256 JWTs signed with a local key and verified by MCP Auth's own
'jwt' mode (signature, expiry, issuer, audience), exactly as in production. Only the JWKS
download is served locally instead of from the OAuth provider.
The Incidents Manager and inventory APIs are replaced at the HTTP layer (httpx.MockTransport)
with responses in their exact shapes, so the tool code and the requests it sends are real.

Run: uv run --project mcps/company-tools --with pytest pytest tests/mcps -q
"""
import json
import sys
import time
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

SERVER_DIR = Path(__file__).resolve().parents[2] / "mcps" / "company-tools"
sys.path.insert(0, str(SERVER_DIR))

ISSUER = "https://nexova-test.example.com/"
AUDIENCE = "https://nexova-company-tools"
RESOURCE = "http://testserver/mcp"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

INCIDENT = {"id": 96, "title": "Mobile app crashes on iOS 17 after update", "description": "Crash on launch.",
            "category": "technical_failure", "status": "open", "origin": "customer", "branch": "central",
            "created_at": "2024-01-28T00:00:00Z", "updated_at": "2024-01-28T00:00:00Z"}
PRODUCT = {"id": 1, "name": "Laptop Dell Latitude", "sku": "LAP-001", "category": "IT", "office": "Valencia",
           "current_stock": 7}


def token(scopes=("incidents:read", "incidents:write", "inventory:read"), *, key=KEY, iss=ISSUER,
          aud=AUDIENCE, exp_in=300, client="agent-support"):
    now = int(time.time())
    return jwt.encode({"iss": iss, "aud": aud, "sub": f"{client}@clients", "azp": client,
                       "scope": " ".join(scopes), "iat": now, "exp": now + exp_in}, key, algorithm="RS256",
                      headers={"kid": "test-key"})


def jwks():
    from jwt.algorithms import RSAAlgorithm
    jwk = RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
    return {"keys": [{**jwk, "kid": "test-key", "use": "sig", "alg": "RS256"}]}


class FakeCompanyApi:
    """Answers like services/api: /auth/login, /api/incidents..., /inventory/products..."""

    def __init__(self):
        self.requests, self.incidents, self.delay = [], {96: dict(INCIDENT)}, 0.0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path))
        if self.delay:
            raise httpx.ReadTimeout("slow", request=request)
        p, m = request.url.path, request.method
        if p == "/auth/login":
            return httpx.Response(200, json={"access_token": "svc-token", "token_type": "bearer"})
        if request.headers.get("authorization") != "Bearer svc-token" and p.startswith("/api/"):
            return httpx.Response(401, json={"detail": "Not authenticated"})
        if p == "/api/incidents" and m == "POST":
            body = json.loads(request.content)
            new = {**INCIDENT, **body, "id": 97, "status": "open"}
            self.incidents[97] = new
            return httpx.Response(201, json=new)
        if p == "/api/incidents" and m == "GET":
            st = request.url.params.get("status")
            return httpx.Response(200, json=[i for i in self.incidents.values() if not st or i["status"] == st])
        if p.startswith("/api/incidents/") and p.endswith("/status") and m == "PATCH":
            iid = int(p.split("/")[3]); target = json.loads(request.content)["status"]
            if iid not in self.incidents:
                return httpx.Response(404, json={"detail": "Incident not found."})
            cur = self.incidents[iid]["status"]
            allowed = {"open": {"in_progress", "discarded"}, "in_progress": {"resolved", "discarded"}}
            if target not in allowed.get(cur, set()):
                return httpx.Response(400, json={"detail": f"Cannot move an incident from '{cur}' to '{target}'."})
            self.incidents[iid]["status"] = target
            return httpx.Response(200, json=self.incidents[iid])
        if p.startswith("/api/incidents/") and m == "GET":
            iid = int(p.rsplit("/", 1)[1])
            return (httpx.Response(200, json=self.incidents[iid]) if iid in self.incidents
                    else httpx.Response(404, json={"detail": "Incident not found."}))
        if p == "/inventory/products" and m == "GET":
            return httpx.Response(200, json=[PRODUCT])
        if p.startswith("/inventory/products/") and m == "GET":
            return (httpx.Response(200, json=PRODUCT) if p.endswith("/1")
                    else httpx.Response(404, json={"detail": "Asset not found."}))
        return httpx.Response(405, json={"detail": "unexpected call"})


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("MCP_INVOCATION_LOG", str(tmp_path / "invocations.jsonl"))
    monkeypatch.delenv("MCP_AUTH_ISSUER", raising=False)
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: jwks())   # JWKS served locally
    import server  # noqa: F401  (imported after env is set)
    from clients import IncidentsApiClient, InventoryReadClient
    from mcpauth.config import AuthorizationServerMetadata, AuthServerConfig, AuthServerType
    from starlette.testclient import TestClient

    api = FakeCompanyApi()
    http = httpx.Client(transport=httpx.MockTransport(api.handler))
    config = AuthServerConfig(type=AuthServerType.OIDC, metadata=AuthorizationServerMetadata(
        issuer=ISSUER, authorization_endpoint=ISSUER + "authorize", token_endpoint=ISSUER + "oauth/token",
        jwks_uri=ISSUER + ".well-known/jwks.json", response_types_supported=["code"]))
    app = server.create_app(server_config=config,
                            incidents=IncidentsApiClient("http://api", "svc@nexova.test", "pw", http),
                            inventory=InventoryReadClient("http://api", http))
    with TestClient(app) as client:
        yield client, api, tmp_path / "invocations.jsonl"


HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(client, method, params=None, *, tok=None, raw_auth=None):
    headers = dict(HEADERS)
    if raw_auth is not None:
        headers["Authorization"] = raw_auth
    elif tok is not False:
        headers["Authorization"] = f"Bearer {tok or token()}"
    return client.post("/mcp", headers=headers,
                       json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})


def call(client, name, args, **kw):
    r = rpc(client, "tools/call", {"name": name, "arguments": args}, **kw)
    assert r.status_code == 200, r.text
    return r.json()["result"]


def error_of(result):
    assert result["isError"] is True
    return json.loads(result["content"][0]["text"])


# -------------------------------------------------------------------------- authentication
def test_no_token_cannot_list_tools(env):
    client, api, _ = env
    r = rpc(client, "tools/list", tok=False)
    assert r.status_code == 401
    assert r.json()["error_code"] == "AUTH_MISSING_TOKEN"
    assert "resource_metadata" in r.headers["www-authenticate"]     # points clients to the PRM
    assert api.requests == []


def test_no_token_cannot_call_tools(env):
    client, api, _ = env
    r = rpc(client, "tools/call", {"name": "get_incident", "arguments": {"ticket_id": 96}}, tok=False)
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_MISSING_TOKEN"
    assert api.requests == []


@pytest.mark.parametrize("bad", [
    token(key=OTHER_KEY),                 # forged signature
    token(exp_in=-3600),                  # expired
    token(iss="https://evil.example/"),   # wrong issuer
    token(aud="https://another-api"),     # wrong audience
    "not-a-jwt",
])
def test_invalid_tokens_are_rejected_with_a_distinct_code(env, bad):
    client, _, _ = env
    r = rpc(client, "tools/list", tok=bad)
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_INVALID_TOKEN"


def test_malformed_header_counts_as_missing_token(env):
    client, _, _ = env
    r = rpc(client, "tools/list", raw_auth="Token abc")
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_MISSING_TOKEN"


def test_protected_resource_metadata_is_discoverable(env):
    client, _, _ = env
    r = client.get("/.well-known/oauth-protected-resource/mcp")
    if r.status_code == 404:
        r = client.get("/.well-known/oauth-protected-resource")
    meta = r.json()
    assert meta["resource"] == RESOURCE
    assert meta["authorization_servers"] == [ISSUER]
    assert set(meta["scopes_supported"]) == {"incidents:read", "incidents:write", "inventory:read"}


# ------------------------------------------------------------------------------- discovery
def test_discovery_lists_documented_tools_with_schemas(env):
    client, _, _ = env
    tools = {t["name"]: t for t in rpc(client, "tools/list").json()["result"]["tools"]}
    assert set(tools) == {"get_incident", "list_incidents", "create_incident", "update_incident_status",
                          "query_inventory"}
    for t in tools.values():
        assert len(t["description"]) > 80 and "scope" in t["description"]
        assert t["inputSchema"]["type"] == "object" and t["outputSchema"]["type"] == "object"
    assert tools["create_incident"]["inputSchema"]["properties"]["category"]["enum"][0] == "technical_failure"
    assert tools["query_inventory"]["annotations"]["readOnlyHint"] is True
    assert "INVENTORY_WRITE_FORBIDDEN" in tools["query_inventory"]["description"]


# ---------------------------------------------------------------------------- ticket tool
def test_full_ticket_flow_create_update_get(env):
    client, api, _ = env
    created = call(client, "create_incident", {"title": "VPN down in Valencia", "description": "No VPN since 9am.",
                                               "category": "technical_failure", "origin": "branch",
                                               "branch": "valencia_operations"})["structuredContent"]
    assert created["id"] == 97 and created["status"] == "open"
    moved = call(client, "update_incident_status", {"ticket_id": 97, "status": "in_progress"})["structuredContent"]
    assert moved["status"] == "in_progress"
    got = call(client, "get_incident", {"ticket_id": 97})["structuredContent"]
    assert got["status"] == "in_progress"
    assert ("PATCH", "/api/incidents/97/status") in api.requests    # lifecycle endpoint, not a generic PATCH
    assert ("POST", "/api/incidents") in api.requests


def test_invalid_lifecycle_move_is_its_own_error(env):
    client, _, _ = env
    call(client, "update_incident_status", {"ticket_id": 96, "status": "in_progress"})
    call(client, "update_incident_status", {"ticket_id": 96, "status": "resolved"})
    err = error_of(call(client, "update_incident_status", {"ticket_id": 96, "status": "open"}))
    assert err["error_code"] == "INVALID_STATUS_TRANSITION" and "resolved" in err["message"]


def test_missing_ticket_is_not_found(env):
    client, _, _ = env
    err = error_of(call(client, "get_incident", {"ticket_id": 482}))
    assert err["error_code"] == "NOT_FOUND"


def test_list_by_status(env):
    client, _, _ = env
    out = call(client, "list_incidents", {"status": "open"})["structuredContent"]
    assert out["total"] == 1 and out["incidents"][0]["id"] == 96


def test_service_login_is_reused_and_refreshed_after_401(env):
    client, api, _ = env
    call(client, "get_incident", {"ticket_id": 96})
    call(client, "get_incident", {"ticket_id": 96})
    assert [r for r in api.requests if r[1] == "/auth/login"] == [("POST", "/auth/login")]


def test_upstream_timeout_has_its_own_code(env):
    client, api, _ = env
    api.delay = 1
    err = error_of(call(client, "get_incident", {"ticket_id": 96}))
    assert err["error_code"] == "UPSTREAM_TIMEOUT"


# -------------------------------------------------------------------- least privilege
def test_read_only_token_cannot_create_tickets(env):
    client, api, _ = env
    err = error_of(call(client, "create_incident", {"title": "x", "description": "y", "category": "other",
                                                    "origin": "internal", "branch": "remote"},
                        tok=token(scopes=("incidents:read",))))
    assert err["error_code"] == "AUTH_INSUFFICIENT_SCOPE"
    assert err["details"]["required_scope"] == "incidents:write"
    assert ("POST", "/api/incidents") not in api.requests


def test_incidents_token_cannot_read_inventory(env):
    client, _, _ = env
    err = error_of(call(client, "query_inventory", {"operation": "list"},
                        tok=token(scopes=("incidents:read", "incidents:write"))))
    assert err["error_code"] == "AUTH_INSUFFICIENT_SCOPE"


# ---------------------------------------------------------------------- inventory tool
def test_inventory_list_and_get(env):
    client, _, _ = env
    out = call(client, "query_inventory", {"operation": "list", "search": "lap"})["structuredContent"]
    assert out["total"] == 1 and out["products"][0]["current_stock"] == 7
    one = call(client, "query_inventory", {"operation": "get", "product_id": 1})["structuredContent"]
    assert one["products"][0]["sku"] == "LAP-001"


@pytest.mark.parametrize("args", [
    {"operation": "update", "product_id": 1},
    {"operation": "delete", "product_id": 1},
    {"operation": "adjust_stock", "product_id": 1},
    {"operation": "list", "current_stock": 0},          # write disguised as an extra field
])
def test_inventory_writes_are_explicitly_rejected(env, args):
    client, api, _ = env
    before = list(api.requests)
    err = error_of(call(client, "query_inventory", args))
    assert err["error_code"] == "INVENTORY_WRITE_FORBIDDEN"
    assert err["message"].startswith("Inventory tool is read-only")
    assert api.requests == before                         # nothing reached the inventory API


def test_inventory_write_rejected_even_with_no_inventory_scope(env):
    client, _, _ = env
    err = error_of(call(client, "query_inventory", {"operation": "update"}, tok=token(scopes=())))
    assert err["error_code"] == "INVENTORY_WRITE_FORBIDDEN"


# ------------------------------------------------------------------------- validation
def test_validation_errors_are_distinct_with_field_detail(env):
    client, _, _ = env
    err = error_of(call(client, "create_incident", {"title": "x", "description": "y", "category": "flood",
                                                    "origin": "internal", "branch": "remote"}))
    assert err["error_code"] == "VALIDATION_ERROR"
    assert err["details"]["fields"][0]["field"] == "category"
    err = error_of(call(client, "query_inventory", {"operation": "get"}))
    assert err["error_code"] == "VALIDATION_ERROR" and err["details"]["field"] == "product_id"
    err = error_of(call(client, "query_inventory", {"operation": "summarize"}))
    assert err["error_code"] == "VALIDATION_ERROR"


def test_error_codes_are_all_distinct(env):
    from errors import MESSAGES
    assert len(set(MESSAGES)) == len(MESSAGES) == len(set(MESSAGES.values()))


# ---------------------------------------------------------------------------- logging
def test_every_invocation_is_logged_with_client_tool_and_result(env):
    client, _, log = env
    call(client, "get_incident", {"ticket_id": 96})
    call(client, "query_inventory", {"operation": "update"})
    call(client, "create_incident", {"title": "t", "description": "secret details", "category": "other",
                                     "origin": "internal", "branch": "remote"},
         tok=token(scopes=("incidents:read",), client="partner-readonly"))
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(e["tool"], e["result"], e["error_code"]) for e in entries] == [
        ("get_incident", "success", None),
        ("query_inventory", "error", "INVENTORY_WRITE_FORBIDDEN"),
        ("create_incident", "error", "AUTH_INSUFFICIENT_SCOPE"),
    ]
    assert entries[0]["client_id"] == "agent-support" and entries[2]["client_id"] == "partner-readonly"
    assert entries[2]["input_summary"]["description"] == "<14 chars>"     # free text not logged
    assert all("timestamp" in e and "duration_ms" in e for e in entries)
