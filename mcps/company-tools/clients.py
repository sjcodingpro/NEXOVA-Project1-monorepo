"""HTTP clients for the company services this MCP server fronts. Live endpoints only: no
mocked or copied data lives here.

IncidentsApiClient  -> the Incidents Manager (services/api, /api/incidents). Its routes require
                       a user JWT, so this server logs in as a dedicated service account
                       (INCIDENTS_API_EMAIL / INCIDENTS_API_PASSWORD) and caches the token,
                       logging in again once if the API answers 401.
InventoryReadClient -> the inventory API (/inventory/products). GET only: the class has no
                       method that can send a write, by design.

Every request carries an explicit timeout (COMPANY_API_TIMEOUT_S, default 5 seconds).
"""
from __future__ import annotations

import os
import threading

import httpx

TIMEOUT_S = float(os.environ.get("COMPANY_API_TIMEOUT_S", "5"))


class UpstreamError(Exception):
    def __init__(self, kind: str, status: int | None = None, detail: str | None = None):
        super().__init__(f"{kind} {status} {detail}")
        self.kind, self.status, self.detail = kind, status, detail   # kind: timeout | http | network


def _request(client: httpx.Client, method: str, url: str, **kw) -> httpx.Response:
    try:
        return client.request(method, url, timeout=TIMEOUT_S, **kw)
    except httpx.TimeoutException as exc:
        raise UpstreamError("timeout") from exc
    except httpx.HTTPError as exc:
        raise UpstreamError("network", detail=type(exc).__name__) from exc


class IncidentsApiClient:
    def __init__(self, base_url: str | None = None, email: str | None = None,
                 password: str | None = None, http: httpx.Client | None = None):
        self.base_url = (base_url or os.environ.get("INCIDENTS_API_URL", "http://localhost:8000")).rstrip("/")
        self._email = email or os.environ.get("INCIDENTS_API_EMAIL")
        self._password = password or os.environ.get("INCIDENTS_API_PASSWORD")
        self._http = http or httpx.Client()
        self._token: str | None = None
        self._lock = threading.Lock()

    def _login(self) -> str:
        if not (self._email and self._password):
            raise UpstreamError("http", 401, "INCIDENTS_API_EMAIL / INCIDENTS_API_PASSWORD not set")
        r = _request(self._http, "POST", f"{self.base_url}/auth/login",
                     json={"email": self._email, "password": self._password})
        if r.status_code != 200:
            raise UpstreamError("http", r.status_code, "service account login failed")
        return r.json()["access_token"]

    def _call(self, method: str, path: str, **kw) -> httpx.Response:
        for attempt in (1, 2):
            with self._lock:
                if self._token is None:
                    self._token = self._login()
                token = self._token
            r = _request(self._http, method, f"{self.base_url}{path}",
                         headers={"Authorization": f"Bearer {token}"}, **kw)
            if r.status_code == 401 and attempt == 1:   # token expired: log in again, once
                with self._lock:
                    self._token = None
                continue
            return r
        return r

    # Each method maps to exactly one Incidents Manager endpoint.
    def create(self, payload: dict) -> httpx.Response:
        return self._call("POST", "/api/incidents", json=payload)

    def update_status(self, incident_id: int, status: str) -> httpx.Response:
        # Lifecycle endpoint: the Incidents Manager validates the transition itself.
        return self._call("PATCH", f"/api/incidents/{incident_id}/status", json={"status": status})

    def get(self, incident_id: int) -> httpx.Response:
        return self._call("GET", f"/api/incidents/{incident_id}")

    def list(self, status: str | None = None) -> httpx.Response:
        return self._call("GET", "/api/incidents", params={"status": status} if status else None)


class InventoryReadClient:
    """Read-only by construction: GET is the only verb this class can send."""

    def __init__(self, base_url: str | None = None, http: httpx.Client | None = None):
        self.base_url = (base_url or os.environ.get("INVENTORY_API_URL", "http://localhost:8000")).rstrip("/")
        self._http = http or httpx.Client()

    def list_products(self) -> httpx.Response:
        return _request(self._http, "GET", f"{self.base_url}/inventory/products")

    def get_product(self, product_id: int) -> httpx.Response:
        return _request(self._http, "GET", f"{self.base_url}/inventory/products/{product_id}")
