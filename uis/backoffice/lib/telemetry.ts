import { getToken } from "@/lib/auth";

export const TELEMETRY_SCHEMA_VERSION = "1.0.0";

const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_AT_QUEUE_SIZE = 20;
const MAX_QUEUE_SIZE = 200; // telemetry is non-critical: drop oldest, never grow unbounded
const MAX_RETRIES = 3;
const BASE_BACKOFF_MS = 1_000;
const SESSION_STORAGE_KEY = "nexova_telemetry_session";

// Closed property allowlist per event_type, mirrored from
// docs/telemetry/event-schemas.json. Anything not listed is dropped.
const ALLOWED_PROPERTIES: Record<string, readonly string[]> = {
  inbound_order_created: ["office", "product_id", "product_category", "programme_id", "quantity", "currency", "supplier_id", "unit_cost", "order_id"],
  outbound_order_created: ["office", "product_id", "product_category", "programme_id", "quantity", "currency", "recipient_role", "order_id"],
  stock_threshold_triggered: ["office", "product_id", "product_category", "programme_id", "currency", "current_stock", "minimum_threshold"],
  direct_stock_edit_rejected: ["office", "product_id", "product_category", "programme_id", "currency", "attempted_quantity", "rejection_reason"],
  kit_cost_variance_detected: ["office", "product_id", "product_category", "programme_id", "currency", "supplier_id", "unit_cost", "historical_unit_cost", "variance_pct", "threshold_pct"],
  login_failed: ["office", "attempted_username_hash", "failure_reason", "attempt_count"],
  login_succeeded: ["office", "role"],
  session_expired: ["office", "session_duration_seconds", "last_section"],
  api_latency_recorded: ["endpoint", "method", "status_code", "duration_ms", "sampled"],
  validation_error_raised: ["office", "form_name", "field_name", "error_code"],
  api_request_failed: ["endpoint", "method", "status_code", "error_class", "occurrence_count"],
  backoffice_section_viewed: ["section", "office", "referrer_section"],
  report_exported: ["report_name", "office", "format"],
  incident_created: ["severity", "area", "office"],
  product_created: ["product_id", "product_category", "programme_id"],
  // PROPOSED plan amendment (uncaught frontend errors have no event in plan 1.0.0)
  frontend_error_raised: ["error_class", "source", "section"],
};

interface TelemetryEnvelope {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string | null;
  event_type: string;
  schemaVersion: string;
  requestId: string;
  properties: Record<string, unknown>;
}

const queue: TelemetryEnvelope[] = [];
let started = false;
let warnedNoEndpoint = false;
let cachedSession: { key: string; id: string } | null = null;

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function decodeTokenPayload(token: string | null): Record<string, unknown> | null {
  if (!token) return null;
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

// One telemetry session per login: keyed on the JWT's issued-at, so a new
// login (new token) starts a new session and a page reload keeps it.
function currentSessionId(): string {
  const key = String(decodeTokenPayload(getToken())?.iat ?? "anonymous");
  if (cachedSession?.key === key) return cachedSession.id;
  try {
    const stored = JSON.parse(sessionStorage.getItem(SESSION_STORAGE_KEY) ?? "null");
    if (stored?.key === key && typeof stored.id === "string") {
      cachedSession = stored;
      return stored.id;
    }
  } catch {
    // storage unavailable: fall through to an in-memory session
  }
  cachedSession = { key, id: uuid() };
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(cachedSession));
  } catch {
    // ignore
  }
  return cachedSession.id;
}

function currentUserId(): string | null {
  const sub = decodeTokenPayload(getToken())?.sub;
  // Guard: if the token subject is an email address, never ship it as userId.
  return typeof sub === "string" && !sub.includes("@") ? sub : null;
}

function endpoint(): string | undefined {
  return process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
}

async function flush(): Promise<void> {
  const url = endpoint();
  if (!url || queue.length === 0) return;
  const batch = queue.splice(0);
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
        keepalive: true,
      });
      if (res.ok) return;
      if (res.status >= 400 && res.status < 500) return; // bad payload: retrying won't help
    } catch {
      // network failure: retry with backoff
    }
    if (attempt < MAX_RETRIES) await sleep(BASE_BACKOFF_MS * 2 ** attempt);
  }
  // all attempts failed: discard the batch, telemetry must never block the app
}

function flushWithBeacon(): void {
  const url = endpoint();
  if (!url || queue.length === 0) return;
  const batch = queue.splice(0);
  try {
    const body = new Blob([JSON.stringify({ events: batch })], { type: "application/json" });
    navigator.sendBeacon(url, body);
  } catch {
    // ignore
  }
}

function ensureStarted(): void {
  if (started || typeof window === "undefined") return;
  started = true;
  setInterval(() => void flush(), FLUSH_INTERVAL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushWithBeacon();
  });
  window.addEventListener("pagehide", flushWithBeacon); // Safari / bfcache
}

/**
 * The ONLY entry point for backoffice telemetry. Callers pass just the
 * event_type and its allowlisted properties; the envelope (eventId,
 * timestamp, sessionId, userId, schemaVersion, requestId) is added here.
 */
export function track(eventType: string, properties: Record<string, unknown>): void {
  try {
    if (typeof window === "undefined") return;
    const allowed = ALLOWED_PROPERTIES[eventType];
    if (!allowed) {
      if (process.env.NODE_ENV !== "production") console.warn(`[telemetry] unknown event_type "${eventType}" dropped`);
      return;
    }
    const clean: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(properties)) {
      if (value === undefined || value === null) continue;
      if (allowed.includes(key)) clean[key] = value;
      else if (process.env.NODE_ENV !== "production") console.warn(`[telemetry] "${key}" is not allowlisted for ${eventType}; dropped`);
    }
    if (!endpoint() && !warnedNoEndpoint) {
      warnedNoEndpoint = true;
      console.warn("[telemetry] NEXT_PUBLIC_TELEMETRY_ENDPOINT is not set; events stay queued and are dropped.");
    }
    queue.push({
      eventId: uuid(),
      timestamp: new Date().toISOString(),
      sessionId: currentSessionId(),
      userId: currentUserId(),
      event_type: eventType,
      schemaVersion: TELEMETRY_SCHEMA_VERSION,
      requestId: uuid(),
      properties: clean,
    });
    if (queue.length > MAX_QUEUE_SIZE) queue.shift();
    ensureStarted();
    if (queue.length >= FLUSH_AT_QUEUE_SIZE) void flush();
  } catch {
    // telemetry must never break the app
  }
}
