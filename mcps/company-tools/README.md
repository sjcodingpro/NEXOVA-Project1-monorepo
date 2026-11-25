# company-tools MCP server

One MCP server that gives AI clients (the LangGraph support agent, MCP Playground, any MCP client)
controlled access to two Nexova systems:

| System | Access | Backend call |
|---|---|---|
| Incidents Manager | read + write (create, change status) | `services/api` `/api/incidents` |
| Inventory | **read only** | `services/api` `/inventory/products` (GET only) |

Built with the official MCP Python SDK (`FastMCP`) and **mcpauth** for OAuth.

## Transport: Streamable HTTP

The server speaks **Streamable HTTP** at `POST /mcp` (stateless, JSON responses). Why:

- **Remote clients.** MCP Playground and the agent connect over the network to a public URL
  (Codespaces forwarded port). stdio only works for a client that launches the server as a
  local subprocess, so it can't serve a hosted Playground or a separately deployed agent.
- **OAuth needs HTTP.** The MCP authorization spec is defined for HTTP transports: bearer tokens
  in the `Authorization` header, `401` + `WWW-Authenticate`, and Protected Resource Metadata.
  stdio has no place for any of that.
- **Not SSE.** The older HTTP+SSE transport is deprecated in the MCP spec; Streamable HTTP
  replaces it with one endpoint.
- **Stateless.** Every request carries its own token and nothing is kept between calls, so the
  server can restart or scale out without breaking clients.

## OAuth (mcpauth)

The server is an OAuth **resource server**. It does not issue tokens; an authorization server
(Auth0) does. mcpauth:

- serves **Protected Resource Metadata** at `/.well-known/oauth-protected-resource/mcp`
  (which authorization server to use, which scopes exist), so clients can discover how to log in;
- checks every `/mcp` request's JWT: signature (JWKS), issuer, audience, expiry;
- exposes the token's scopes and client id (`azp`) to the tools.

### Scopes (least privilege)

| Scope | Allows | Granted to |
|---|---|---|
| `incidents:read` | `get_incident`, `list_incidents` | agent, Playground |
| `incidents:write` | `create_incident`, `update_incident_status` | Playground (testing) |
| `inventory:read` | `query_inventory` | Playground |

There is **no inventory write scope**: no token can ever write to inventory through this server.
The support agent only gets `incidents:read`.

## Tools

| Tool | Scope | What it does |
|---|---|---|
| `get_incident(ticket_id)` | incidents:read | One ticket by id |
| `list_incidents(status?, limit=10)` | incidents:read | Newest first, with total count |
| `create_incident(title, description, category, origin, branch)` | incidents:write | Creates a ticket (status `open`) |
| `update_incident_status(ticket_id, status)` | incidents:write | `PATCH /api/incidents/{id}/status`, follows the lifecycle open → in_progress/discarded, in_progress → resolved/discarded |
| `query_inventory(operation="list"\|"get", product_id?, office?, search?)` | inventory:read | Read-only product/stock lookup. Any write verb (`create`, `update`, `delete`, `adjust_stock`, `inbound`…) or extra write field is rejected with `INVENTORY_WRITE_FORBIDDEN` **before** any HTTP call |

Every tool has a JSON input schema, a structured output schema, MCP annotations
(`readOnlyHint`, `destructiveHint`, `idempotentHint`) and a description naming its scope and errors,
so clients discover all of this through `tools/list`.

## Error codes

Errors return `{"error_code", "message", "tool", "details"}`; codes are distinct so a client can
react without parsing text.

| Code | Where | Meaning |
|---|---|---|
| `AUTH_MISSING_TOKEN` | HTTP 401 | No bearer token |
| `AUTH_INVALID_TOKEN` | HTTP 401 | Bad signature, expired, wrong issuer or audience |
| `AUTH_INSUFFICIENT_SCOPE` | tool error | Token is valid but lacks the tool's scope (`details.required`, `details.granted`) |
| `INVENTORY_WRITE_FORBIDDEN` | tool error | A write was attempted on read-only inventory |
| `VALIDATION_ERROR` | tool error | Bad arguments (`details.fields`) |
| `NOT_FOUND` | tool error | Ticket or product does not exist |
| `INVALID_STATUS_TRANSITION` | tool error | Status change not allowed by the lifecycle |
| `UPSTREAM_TIMEOUT` | tool error | Company API did not answer in `COMPANY_API_TIMEOUT_S` |
| `UPSTREAM_ERROR` | tool error | Company API unreachable or returned an unexpected error |

## Invocation log

Every tool call (success or failure) is appended to `logs/invocations.jsonl` (gitignored):
timestamp, client id, tool, an input summary (free text like titles is logged as `"<N chars>"`,
never the content), result, error code and duration.

## Run locally

```bash
cd mcps/company-tools
cp .env.example .env        # fill in the values
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 8010
curl localhost:8010/health
curl localhost:8010/.well-known/oauth-protected-resource/mcp
```

The Incidents API (`services/api`, port 8000) must be running.

## Test in MCP Playground (Codespaces)

1. Start the API (port 8000) and this server (port 8010) in the Codespace.
2. Ports tab → port 8010 → right-click → Port Visibility → **Public**. Copy the forwarded URL.
3. Set `MCP_RESOURCE_URL=https://<codespace>-8010.app.github.dev/mcp` in `.env` and restart.
4. Get a token for the Playground client (all three scopes) from the authorization server.
5. In MCP Playground: transport Streamable HTTP, URL `…/mcp`, header
   `Authorization: Bearer <token>`. Run `tools/list`, then create → update status → get, a
   `query_inventory` list, and a rejected inventory write.

## Agent integration

The LangGraph support agent (`services/agent`) reaches incidents **only** through this server,
via `langchain-mcp-adapters` with its own client-credentials token (`incidents:read`). The old
direct call into the Incidents Manager's service layer was removed.

## Tests

```bash
uv run --project mcps/company-tools --with pytest --with cryptography pytest tests/mcps -q
```

28 tests: auth failures, discovery, every tool, scope checks, write rejection, timeouts, error
codes, the invocation log and signing-key caching, against a fake company API and locally
signed tokens.
