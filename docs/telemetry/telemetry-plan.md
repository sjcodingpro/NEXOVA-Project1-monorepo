# Nexova Telemetry Plan

**Schema version:** `1.0.0` · **Status:** Design (no instrumentation yet) · **Owner:** sarahjean (AI Engineering bootcamp track)

## 0. Purpose

This document responds to the RFI from the technology team: can the Nexova system generate
actionable business information, across any part of the application a user or internal
process touches — not only inventory?

It catalogues every telemetry event worth capturing today, or plausibly worth capturing
tomorrow, before any instrumentation is written. It follows the golden rule from the brief:

> We capture `[event_type]` because we need to know `[hypothesis]`, which allows us to make
> the decision `[concrete decision]`.

Every event below completes that sentence. None exist "just in case."

**Totals:** 15 events designed — **5 mandatory** (from `CONTEXT-company.md`) and
**10 identified** by this design pass, across **5 categories**.

| Category | Events | Event types |
|---|---|---|
| Authentication / Security | 4 | `direct_stock_edit_rejected`, `login_failed`, `login_succeeded`, `session_expired` |
| Business | 6 | `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, `kit_cost_variance_detected`, `incident_created`, `product_created` |
| Errors | 2 | `validation_error_raised`, `api_request_failed` |
| Navigation | 2 | `backoffice_section_viewed`, `report_exported` |
| Performance | 1 | `api_latency_recorded` |

---

## Phase 1 — Exhaustive Catalogue of Data Opportunities

The mandatory metrics from `CONTEXT-company.md` are the floor of this catalogue, not the
ceiling. Around them, this plan also covers authentication/security, performance, error, and
navigation signals across the backoffice, plus two additional business-side opportunities
(incident volume, catalogue growth) that surfaced while reviewing what else the application
already tracks (the existing Incident Manager, and product-catalogue changes that are not
stock movements).

### Mandatory events (from CONTEXT)

### 1. `inbound_order_created`

**Category:** Business · **Status:** **MANDATORY (CONTEXT)** · **Actor:** Human user

- **Fires when:** A new batch of training or onboarding material arrives from a supplier and is recorded against the InboundOrder entity.
- **Business/operational hypothesis:** "We capture `inbound_order_created` because we need to know how much material is being produced/purchased, for which programme, and at what cost."
- **Decision it enables:** Plan material production based on expected enrolment demand (Elena).
- **Delivery:** **STREAM** — Inbound quantity feeds stock levels that stock_threshold_triggered evaluates immediately after; delaying this to a batch window would delay threshold detection and restocking alerts by up to a full batch cycle.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office the transaction belongs to. Independent from interface language. Allowed values: `valencia, miami`. |
| `product_id` | `string` | yes | Stable identifier of the material item (product). |
| `product_category` | `string` | yes | Category of the material item. Allowed values: `training_kit, certification, onboarding_equipment`. |
| `programme_id` | `string` | yes | Identifier of the training/certification programme the material belongs to. |
| `quantity` | `integer` | yes | Units affected by this transaction. |
| `currency` | `string` | yes | Local currency of the office. EUR for Valencia, USD for Miami. Never converted at the telemetry layer. Allowed values: `EUR, USD`. |
| `supplier_id` | `string` | yes | Identifier of the supplier the batch was received from. |
| `unit_cost` | `number` | yes | Cost per unit in the office's local currency, used for kit_cost_variance_detected. |
| `order_id` | `string` | yes | Identifier of the InboundOrder record, for correlation with the inventory database. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633704Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "inbound_order_created",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "product_id": "product-001",
    "product_category": "training_kit",
    "programme_id": "programme-001",
    "quantity": 5,
    "currency": "EUR",
    "supplier_id": "supplier-001",
    "unit_cost": 12.5,
    "order_id": "order-001"
  }
}
```

</details>

### 2. `outbound_order_created`

**Category:** Business · **Status:** **MANDATORY (CONTEXT)** · **Actor:** Human user

- **Fires when:** A kit or certificate is delivered to a client, candidate, consultant, or agent and recorded against the OutboundOrder entity.
- **Business/operational hypothesis:** "We capture `outbound_order_created` because we need to know which programmes consume the most material, and at what rate."
- **Decision it enables:** Anticipate restocking needs before a large enrolment wave (Elena).
- **Delivery:** **STREAM** — Outbound quantity depletes stock in real time and is the direct input to stock_threshold_triggered; a delivery delivered this morning must be reflected in stock levels before the next threshold check, not at the end of the day.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No — Recipient is identified only by role and programme (e.g. consultant, support_agent), never by candidate/client/consultant name, per CONTEXT constraint.

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office the transaction belongs to. Independent from interface language. Allowed values: `valencia, miami`. |
| `product_id` | `string` | yes | Stable identifier of the material item (product). |
| `product_category` | `string` | yes | Category of the material item. Allowed values: `training_kit, certification, onboarding_equipment`. |
| `programme_id` | `string` | yes | Identifier of the training/certification programme the material belongs to. |
| `quantity` | `integer` | yes | Units affected by this transaction. |
| `currency` | `string` | yes | Local currency of the office. EUR for Valencia, USD for Miami. Never converted at the telemetry layer. Allowed values: `EUR, USD`. |
| `recipient_role` | `string` | yes | Role of the recipient. Never a personal identifier or name. Allowed values: `client, candidate, consultant, support_agent`. |
| `order_id` | `string` | yes | Identifier of the OutboundOrder record. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633727Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "outbound_order_created",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "product_id": "product-001",
    "product_category": "training_kit",
    "programme_id": "programme-001",
    "quantity": 5,
    "currency": "EUR",
    "recipient_role": "client",
    "order_id": "order-001"
  }
}
```

</details>

### 3. `stock_threshold_triggered`

**Category:** Business · **Status:** **MANDATORY (CONTEXT)** · **Actor:** System/background process

- **Fires when:** The stock of a material item falls below its configured minimum threshold, evaluated after any order that changes stock.
- **Business/operational hypothesis:** "We capture `stock_threshold_triggered` because we need to know how often a programme runs out of available material."
- **Decision it enables:** Adjust the minimum threshold or speed up reprinting/reproduction of that material.
- **Delivery:** **STREAM** — This is an operational alert by definition (material is about to run out); any delay directly increases the risk of a stockout before Elena can react.
- **Throttle/debounce:** Debounced per product_id: once triggered, suppress duplicate events for the same product_id/office until stock rises back above threshold and falls below it again, so a single slow-moving shortage doesn't re-fire on every subsequent outbound order.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office the transaction belongs to. Independent from interface language. Allowed values: `valencia, miami`. |
| `product_id` | `string` | yes | Stable identifier of the material item (product). |
| `product_category` | `string` | yes | Category of the material item. Allowed values: `training_kit, certification, onboarding_equipment`. |
| `programme_id` | `string` | yes | Identifier of the training/certification programme the material belongs to. |
| `currency` | `string` | yes | Local currency of the office. EUR for Valencia, USD for Miami. Never converted at the telemetry layer. Allowed values: `EUR, USD`. |
| `current_stock` | `integer` | yes | Stock level at the moment the threshold was crossed. |
| `minimum_threshold` | `integer` | yes | Configured minimum stock threshold for this product/office. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633763Z",
  "sessionId": "sess-abc123",
  "userId": null,
  "event_type": "stock_threshold_triggered",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "product_id": "product-001",
    "product_category": "training_kit",
    "programme_id": "programme-001",
    "currency": "EUR",
    "current_stock": 5,
    "minimum_threshold": 5
  }
}
```

</details>

### 4. `direct_stock_edit_rejected`

**Category:** Authentication / Security · **Status:** **MANDATORY (CONTEXT)** · **Actor:** Human user

- **Fires when:** A user attempts to modify stock directly, outside an InboundOrder/OutboundOrder, and the system rejects it.
- **Business/operational hypothesis:** "We capture `direct_stock_edit_rejected` because we need to know if staff are attempting to bypass material traceability controls."
- **Decision it enables:** Reinforce training or permissions at the office where this happens most (Patricia).
- **Delivery:** **STREAM** — A rejected bypass attempt is a security-relevant event; repeated attempts in a short window should be visible immediately, not discovered a day later in a batch report.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office the transaction belongs to. Independent from interface language. Allowed values: `valencia, miami`. |
| `product_id` | `string` | yes | Stable identifier of the material item (product). |
| `product_category` | `string` | yes | Category of the material item. Allowed values: `training_kit, certification, onboarding_equipment`. |
| `programme_id` | `string` | yes | Identifier of the training/certification programme the material belongs to. |
| `currency` | `string` | yes | Local currency of the office. EUR for Valencia, USD for Miami. Never converted at the telemetry layer. Allowed values: `EUR, USD`. |
| `attempted_quantity` | `integer` | yes | Stock delta the user attempted to apply directly, before the system rejected it. |
| `rejection_reason` | `string` | yes | Why the system rejected the attempt. Allowed values: `direct_edit_not_allowed, insufficient_permissions`. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633789Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "direct_stock_edit_rejected",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "product_id": "product-001",
    "product_category": "training_kit",
    "programme_id": "programme-001",
    "currency": "EUR",
    "attempted_quantity": 5,
    "rejection_reason": "direct_edit_not_allowed"
  }
}
```

</details>

### 5. `kit_cost_variance_detected`

**Category:** Business · **Status:** **MANDATORY (CONTEXT)** · **Actor:** System/background process

- **Fires when:** An inbound order's unit cost deviates from the historical unit cost for that material/supplier by more than the configured threshold.
- **Business/operational hypothesis:** "We capture `kit_cost_variance_detected` because we need to know when a material supplier raises prices abnormally."
- **Decision it enables:** Alert Elena and Laura to renegotiate or find an alternate supplier.
- **Delivery:** **BATCH** — Cost variance is evaluated against a historical average and acted on through a renegotiation conversation with a supplier, which happens on a weekly/monthly cadence, not within seconds of the inbound order.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office the transaction belongs to. Independent from interface language. Allowed values: `valencia, miami`. |
| `product_id` | `string` | yes | Stable identifier of the material item (product). |
| `product_category` | `string` | yes | Category of the material item. Allowed values: `training_kit, certification, onboarding_equipment`. |
| `programme_id` | `string` | yes | Identifier of the training/certification programme the material belongs to. |
| `currency` | `string` | yes | Local currency of the office. EUR for Valencia, USD for Miami. Never converted at the telemetry layer. Allowed values: `EUR, USD`. |
| `supplier_id` | `string` | yes | Supplier whose pricing triggered the variance. |
| `unit_cost` | `number` | yes | Unit cost on the inbound order that triggered the check. |
| `historical_unit_cost` | `number` | yes | Historical average unit cost for this product/supplier. |
| `variance_pct` | `number` | yes | Percentage deviation from the historical unit cost (e.g. 0.12 for +12%). |
| `threshold_pct` | `number` | yes | Configured variance threshold that was crossed (e.g. 0.10 for 10%). |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633815Z",
  "sessionId": "sess-abc123",
  "userId": null,
  "event_type": "kit_cost_variance_detected",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "product_id": "product-001",
    "product_category": "training_kit",
    "programme_id": "programme-001",
    "currency": "EUR",
    "supplier_id": "supplier-001",
    "unit_cost": 12.5,
    "historical_unit_cost": 12.5,
    "variance_pct": 12.5,
    "threshold_pct": 12.5
  }
}
```

</details>


### Additional events identified

### 6. `login_failed`

**Category:** Authentication / Security · **Status:** Identified · **Actor:** Human user

- **Fires when:** An authentication attempt against the backoffice fails, for any reason (bad credentials, locked or disabled account).
- **Business/operational hypothesis:** "We capture `login_failed` because we need to know how many failed login attempts happen per day and whether they cluster on specific accounts."
- **Decision it enables:** Trigger account lockout/alerting policy and detect credential-stuffing or brute-force patterns.
- **Delivery:** **STREAM** — Repeated failed logins in a short window are a security signal; detecting a brute-force attempt requires near real-time visibility, not a next-day report.
- **Throttle/debounce:** Debounced per (userId or attempted_username, office): identical consecutive failures within a 5-second window are collapsed into one event with an attempt_count, so a scripted retry loop doesn't flood the pipeline.
- **Contains PII/sensitive data:** Yes — attempted_username may be an email; it is hashed (SHA-256) before being placed in properties, since a failed login is exactly the case where a real person's identifier is most likely to appear by mistake.

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office context of the login attempt, if known. Allowed values: `valencia, miami`. |
| `attempted_username_hash` | `string` | yes | SHA-256 hash of the attempted username/email. Never the raw value. |
| `failure_reason` | `string` | yes | Why authentication failed. Allowed values: `invalid_credentials, account_locked, account_disabled`. |
| `attempt_count` | `integer` | yes | Number of identical failures collapsed into this event by the debounce window. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633858Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "login_failed",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "attempted_username_hash": "example-attempted_username_hash",
    "failure_reason": "invalid_credentials",
    "attempt_count": 5
  }
}
```

</details>

### 7. `login_succeeded`

**Category:** Authentication / Security · **Status:** Identified · **Actor:** Human user

- **Fires when:** An authentication attempt against the backoffice succeeds.
- **Business/operational hypothesis:** "We capture `login_succeeded` because we need to know daily active users per office and role, and general login patterns (peak hours, weekday distribution)."
- **Decision it enables:** Size support/on-call staffing to actual usage hours; detect anomalous login volume as a secondary signal.
- **Delivery:** **BATCH** — Usage-pattern reporting is reviewed periodically (weekly executive report); no decision depends on knowing about a successful login within seconds.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No — userId in the envelope already identifies the actor; no additional personal data is placed in properties.

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office context of the login. Allowed values: `valencia, miami`. |
| `role` | `string` | yes | Role of the authenticated user (e.g. admin, ops, consultant). |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633877Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "login_succeeded",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "role": "example-role"
  }
}
```

</details>

### 8. `session_expired`

**Category:** Authentication / Security · **Status:** Identified · **Actor:** System/background process

- **Fires when:** A backoffice session times out without an explicit logout.
- **Business/operational hypothesis:** "We capture `session_expired` because we need to know how often sessions expire mid-task rather than via explicit logout, which may indicate the session timeout is too short for real workflows."
- **Decision it enables:** Tune session timeout duration in the backoffice.
- **Delivery:** **BATCH** — This is a UX-tuning metric reviewed in aggregate over weeks, not an urgent per-instance signal.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | yes | Office context of the expired session. Allowed values: `valencia, miami`. |
| `session_duration_seconds` | `integer` | yes | How long the session was active before expiring. |
| `last_section` | `string` | no | Last backoffice section the user was on before expiry, if known. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633941Z",
  "sessionId": "sess-abc123",
  "userId": null,
  "event_type": "session_expired",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "session_duration_seconds": 5,
    "last_section": "example-last_section"
  }
}
```

</details>

### 9. `api_latency_recorded`

**Category:** Performance · **Status:** Identified · **Actor:** System/background process

- **Fires when:** A backend request completes (success or failure) and its processing time is sampled per the throttle policy below.
- **Business/operational hypothesis:** "We capture `api_latency_recorded` because we need to know which API endpoints are slow and whether latency is degrading over time or under load."
- **Decision it enables:** Prioritize backend optimization work and set SLO-based alerting thresholds.
- **Delivery:** **STREAM** — Latency spikes that correlate with an incident need to be visible while the incident is happening, so on-call staff can correlate cause and effect in real time.
- **Throttle/debounce:** Sampled at 10% of requests under normal conditions, with 100% sampling automatically enabled for any endpoint currently returning elevated error rates. This keeps volume proportional to value: routine fast requests are rarely worth storing individually.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `endpoint` | `string` | yes | Route template, e.g. /inventory/orders/inbound (never the raw URL with path parameters). |
| `method` | `string` | yes | HTTP method. Allowed values: `GET, POST, PUT, PATCH, DELETE`. |
| `status_code` | `integer` | yes | HTTP status code returned. |
| `duration_ms` | `number` | yes | Server-side processing time in milliseconds. |
| `sampled` | `boolean` | yes | True if this event was captured under the sampling policy rather than the elevated-error-rate override. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.633996Z",
  "sessionId": "sess-abc123",
  "userId": null,
  "event_type": "api_latency_recorded",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "endpoint": "example-endpoint",
    "method": "GET",
    "status_code": 200,
    "duration_ms": 12.5,
    "sampled": true
  }
}
```

</details>

### 10. `validation_error_raised`

**Category:** Errors · **Status:** Identified · **Actor:** Human user

- **Fires when:** A backoffice form submission fails client- or server-side validation on one or more fields.
- **Business/operational hypothesis:** "We capture `validation_error_raised` because we need to know which fields/forms in the backoffice produce the most validation errors, which may indicate a confusing UI or unclear business rule."
- **Decision it enables:** Prioritize UX fixes for the forms with the highest error rates.
- **Delivery:** **BATCH** — This is a UX-quality metric reviewed in aggregate; no single validation error requires immediate reaction.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No — field_name and error_code identify the offending field and rule, never the value the user typed, so no accidental PII capture from free-text input.

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `office` | `string` | no | Office context, if applicable to the form. Allowed values: `valencia, miami`. |
| `form_name` | `string` | yes | Identifier of the form/section where the error occurred, e.g. inbound_order_form. |
| `field_name` | `string` | yes | Name of the field that failed validation. Never the submitted value. |
| `error_code` | `string` | yes | Machine-readable validation rule that failed, e.g. required, min_quantity, invalid_currency. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.634029Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "validation_error_raised",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "office": "valencia",
    "form_name": "example-form_name",
    "field_name": "example-field_name",
    "error_code": "example-error_code"
  }
}
```

</details>

### 11. `api_request_failed`

**Category:** Errors · **Status:** Identified · **Actor:** System/background process

- **Fires when:** A backend request returns a 5xx status code.
- **Business/operational hypothesis:** "We capture `api_request_failed` because we need to know when and where the API is returning 5xx errors, and whether failures cluster around a specific endpoint, office, or deployment."
- **Decision it enables:** Trigger on-call investigation and correlate with recent deployments (infra-40 Docker rollout and future releases).
- **Delivery:** **STREAM** — A cluster of 5xx errors is an active incident; this is the same urgency class as an outage and must be visible immediately, feeding the existing Incident Manager.
- **Throttle/debounce:** Deduplicated per (endpoint, status_code) within a 60-second rolling window: identical repeated failures are collapsed into one event with an occurrence_count, so a crash-looping endpoint doesn't flood the pipeline while still preserving the first-seen timestamp.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `endpoint` | `string` | yes | Route template that failed. |
| `method` | `string` | yes | HTTP method. Allowed values: `GET, POST, PUT, PATCH, DELETE`. |
| `status_code` | `integer` | yes | 5xx status code returned. |
| `error_class` | `string` | yes | High-level error classification, e.g. database_timeout, unhandled_exception, dependency_unavailable. |
| `occurrence_count` | `integer` | yes | Number of identical failures collapsed into this event by the dedupe window. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.634053Z",
  "sessionId": "sess-abc123",
  "userId": null,
  "event_type": "api_request_failed",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "endpoint": "example-endpoint",
    "method": "GET",
    "status_code": 500,
    "error_class": "example-error_class",
    "occurrence_count": 5
  }
}
```

</details>

### 12. `backoffice_section_viewed`

**Category:** Navigation · **Status:** Identified · **Actor:** Human user

- **Fires when:** A user navigates to a distinct backoffice section/route.
- **Business/operational hypothesis:** "We capture `backoffice_section_viewed` because we need to know which backoffice sections operators actually use, and which are ignored."
- **Decision it enables:** Prioritize which sections get further investment vs. which can be simplified or removed.
- **Delivery:** **BATCH** — This is a usage-analytics metric consumed in periodic (weekly) reporting; no operational decision needs to react to a single page view within seconds.
- **Throttle/debounce:** Debounced per (sessionId, section): repeated views of the same section within a 30-second window (e.g. a user idling on a page or a tab regaining focus) are collapsed into a single event.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `section` | `string` | yes | Identifier of the backoffice section/route, e.g. inventory_dashboard, incidents_list. |
| `office` | `string` | no | Office context of the acting user, if applicable. Allowed values: `valencia, miami`. |
| `referrer_section` | `string` | no | Section the user navigated from, for basic funnel/flow reconstruction. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.634073Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "backoffice_section_viewed",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "section": "example-section",
    "office": "valencia",
    "referrer_section": "example-referrer_section"
  }
}
```

</details>

### 13. `report_exported`

**Category:** Navigation · **Status:** Identified · **Actor:** Human user

- **Fires when:** A user downloads a report from the backoffice in any supported format.
- **Business/operational hypothesis:** "We capture `report_exported` because we need to know which reports operators actually export and how often, to prioritize which ones get built into the automated executive report first."
- **Decision it enables:** Prioritize the report-automation backlog (Laura's weekly executive report) by actual demand rather than guesswork.
- **Delivery:** **BATCH** — Feeds a periodic prioritization decision, not a real-time one.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `report_name` | `string` | yes | Identifier of the exported report, e.g. inventory_by_programme. |
| `office` | `string` | no | Office filter applied to the export, if any. Allowed values: `valencia, miami`. |
| `format` | `string` | yes | Export format chosen. Allowed values: `csv, pdf, xlsx`. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.634091Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "report_exported",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "report_name": "example-report_name",
    "office": "valencia",
    "format": "csv"
  }
}
```

</details>

### 14. `incident_created`

**Category:** Business · **Status:** Identified · **Actor:** Human user

- **Fires when:** A new incident is logged in the existing Incident Manager.
- **Business/operational hypothesis:** "We capture `incident_created` because we need to know how often operational incidents are logged, by severity and area, to see whether the system is stable enough to trust for business decisions."
- **Decision it enables:** Feed incident volume/severity into the same executive report as inventory metrics, and prioritize engineering time toward the noisiest area.
- **Delivery:** **STREAM** — Incident creation is itself an urgent operational event in the existing Incident Manager; telemetry should mirror that urgency rather than lag behind it.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `severity` | `string` | yes | Severity assigned at creation. Allowed values: `low, medium, high, critical`. |
| `area` | `string` | yes | System area the incident concerns, e.g. inventory, auth, suppliers. |
| `office` | `string` | no | Office context, if applicable. Allowed values: `valencia, miami`. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.634108Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "incident_created",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "severity": "low",
    "area": "example-area",
    "office": "valencia"
  }
}
```

</details>

### 15. `product_created`

**Category:** Business · **Status:** Identified · **Actor:** Human user

- **Fires when:** A new material item (product) is added to the catalogue.
- **Business/operational hypothesis:** "We capture `product_created` because we need to know how the material catalogue grows over time and by category, independent of stock movements."
- **Decision it enables:** Track catalogue breadth per programme as an input to Elena's L&D planning, separate from stock/consumption metrics.
- **Delivery:** **BATCH** — Catalogue growth is a slow-moving, periodic-review metric; a new product definition is not itself a stock event and carries no urgency.
- **Throttle/debounce:** Not applicable — event volume is naturally low.
- **Contains PII/sensitive data:** No — Recorded because it is metadata about a catalogue item, not a stock modification, so it does not conflict with the 'stock only changes via orders' business rule.

**Property allowlist** (nothing outside this list may be emitted in `properties`):

| Name | Type | Required | Description |
|---|---|---|---|
| `product_id` | `string` | yes | Identifier of the newly created product. |
| `product_category` | `string` | yes | Category of the new product. Allowed values: `training_kit, certification, onboarding_equipment`. |
| `programme_id` | `string` | yes | Programme the product belongs to. |

<details>
<summary>Example valid event</summary>

```json
{
  "eventId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-09-28T16:58:27.634130Z",
  "sessionId": "sess-abc123",
  "userId": "user-042",
  "event_type": "product_created",
  "schemaVersion": "1.0.0",
  "requestId": "req-9f8e7d6c",
  "properties": {
    "product_id": "product-001",
    "product_category": "training_kit",
    "programme_id": "programme-001"
  }
}
```

</details>


---

## Phase 2 — Event Envelope Design

Every event, regardless of `event_type`, is wrapped in the same standard envelope:

| Field | Type | Description |
|---|---|---|
| `eventId` | `string` (uuid) | Unique identifier for this event instance. |
| `timestamp` | `string` (ISO 8601) | When the event occurred, e.g. `2026-09-28T16:04:12.331Z`. |
| `sessionId` | `string` | Session the event belongs to. For system-emitted events, the triggering request's session if any, otherwise a synthetic job session id. |
| `userId` | `string \| null` | Authenticated user who performed the action. `null` for system/background-job-emitted events (e.g. `stock_threshold_triggered`, `kit_cost_variance_detected`). |
| `event_type` | `string` | `entity_action` taxonomy, e.g. `inbound_order_created`, `session_expired`, `api_latency_recorded`. |
| `schemaVersion` | `string` | Version of this event's schema, e.g. `1.0.0`. Consumers can branch on this if the shape changes. |
| `requestId` | `string` | Correlation id joining frontend, backend, and logs for the action that produced this event. |
| `properties` | `object` | Event-specific payload. Validated against a per-`event_type` allowlist — see `event-schemas.json`. |

**Taxonomy rule:** every `event_type` is `entity_action`, with consistent verbs across the
catalogue: `created` (a new record appears), `triggered` (a system condition fires),
`rejected` (an attempted action was blocked), `detected` (a system computation flags a
condition), `failed` (an attempted action did not succeed), `succeeded` (an attempted action
completed), `expired` (a time-based state change), `recorded` (a measurement was taken),
`raised` (a validation/error condition surfaced), `viewed` (a navigation event), `exported`
(a user-initiated download).

**Property allowlists:** every event's `properties` object is closed (`additionalProperties:
false`, enforced by `event-schemas.json`). Nothing can be added to an event's payload without
a conscious schema change — this is the mechanism that prevents the accidental PII/data
leakage the CONTEXT explicitly warns about (no candidate/client/consultant names, ever).

**PII handling:** only one event in this catalogue is designed to receive a value that could
be personally identifying at the input stage — `login_failed`, where the attempted username
is often an email address. It is hashed (SHA-256) before it reaches `properties`; the raw
value never enters the telemetry pipeline. All other events reference people only by role
(`recipient_role`), programme/kit identifiers, or the envelope's own `userId` — never by name,
per the CONTEXT constraint.

---

## Phase 3 — Delivery Strategy

### Stream vs. batch, by urgency of the decision it feeds

**Stream (real-time):** `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `login_failed`, `api_latency_recorded`, `api_request_failed`, `incident_created`

These all feed a decision that has to be made within minutes, not days: stock is about to run
out, a security control was bypassed, a login is possibly a brute-force attempt, the API is
actively failing, or an incident needs on-call attention right now.

**Batch (periodic):** `kit_cost_variance_detected`, `login_succeeded`, `session_expired`, `validation_error_raised`, `backoffice_section_viewed`, `report_exported`, `product_created`

These feed decisions made on a weekly/monthly cadence — supplier renegotiation, UX
prioritization, staffing, report-automation backlog, session-timeout tuning, catalogue
planning. Streaming them would add pipeline cost for no decision-speed benefit.

The choice was made per event based on the urgency of the decision it enables, per the brief
— never on which was technically simpler to build.

### Throttle / debounce strategy

High-frequency or easily-duplicated events carry an explicit dedupe/sampling rule so the
pipeline volume tracks decision value rather than raw traffic:

- **`stock_threshold_triggered`:** Debounced per product_id: once triggered, suppress duplicate events for the same product_id/office until stock rises back above threshold and falls below it again, so a single slow-moving shortage doesn't re-fire on every subsequent outbound order.
- **`login_failed`:** Debounced per (userId or attempted_username, office): identical consecutive failures within a 5-second window are collapsed into one event with an attempt_count, so a scripted retry loop doesn't flood the pipeline.
- **`api_latency_recorded`:** Sampled at 10% of requests under normal conditions, with 100% sampling automatically enabled for any endpoint currently returning elevated error rates. This keeps volume proportional to value: routine fast requests are rarely worth storing individually.
- **`api_request_failed`:** Deduplicated per (endpoint, status_code) within a 60-second rolling window: identical repeated failures are collapsed into one event with an occurrence_count, so a crash-looping endpoint doesn't flood the pipeline while still preserving the first-seen timestamp.
- **`backoffice_section_viewed`:** Debounced per (sessionId, section): repeated views of the same section within a 30-second window (e.g. a user idling on a page or a tab regaining focus) are collapsed into a single event.

Every other event fires once per real occurrence and needs no throttling — their natural
frequency is already low (a login, an order, a report export).

### Risks and exclusions

Events and data considered and deliberately **not** included in this plan:

- **Enrolment-specific events** (e.g. `enrolment_completed`, `certification_issued`) — Elena's
  future L&D dashboard will need these, but no `Enrolment` entity exists in the current system
  (only `Product`, `InboundOrder`, `OutboundOrder`). Designing schemas for an entity that
  doesn't exist yet would be speculative; this is flagged as a likely Phase-2 addition once
  enrolment tracking ships, not designed blind now.
- **Candidate/client/consultant names or any personal identifier in `properties`** — explicitly
  excluded per the CONTEXT constraint. Every event that references a person uses `userId`
  (already present in the envelope), a `recipient_role`, or a hashed identifier instead.
- **Full request/response body logging** — considered for `api_request_failed` and
  `api_latency_recorded` to ease debugging, but excluded: request bodies on inventory/auth
  endpoints routinely contain the exact data (order details, credentials) telemetry is meant
  to summarize, not duplicate, and this would multiply storage cost with no analytical
  benefit beyond `error_class` and `endpoint`.
- **Client-side mouse movement / keystroke-level tracking** for abandoned-flow detection —
  considered as a way to answer the tech lead's "flows that get abandoned halfway through"
  question, but excluded in favor of step-level navigation events (`backoffice_section_viewed`
  with `referrer_section`), which answer the same business question without the privacy and
  storage cost of raw interaction capture.
- **Client-side geolocation** — no business question in this plan needs finer location data
  than the existing `office` dimension (Valencia/Miami).
- **Currency conversion at the telemetry layer** — amounts are recorded in the office's local
  currency only (EUR/USD), per the CONTEXT business constraint; any conversion belongs in the
  reporting layer, not in the event itself, so telemetry never becomes a second source of
  truth for exchange rates.

### Hardest design decision

Deciding the actor and delivery mode for `stock_threshold_triggered` and
`kit_cost_variance_detected` was the hardest call: both are triggered by a system computation
rather than a direct user action, so `userId` had to become nullable in the envelope (rather
than adding a separate "system event" envelope variant), and each needed its own urgency
judgment — threshold breaches are operational alerts that must stream immediately, while cost
variance, though computed from the same inbound-order data, feeds a slower supplier-negotiation
decision and belongs in batch. Treating two events that share an entity and a trigger source
differently on delivery mode, purely because of decision urgency, is the crux of Phase 3.

---

## Appendix — Schema file

The machine-readable form of every event above lives in
[`event-schemas.json`](./event-schemas.json), JSON Schema draft-07, one schema per
`event_type` under `eventSchemas`, sharing the envelope defined in `definitions.envelope`.
Every event schema sets `additionalProperties: false` at both the envelope level and inside
`properties`, so an event that doesn't match its documented allowlist fails validation rather
than silently passing through with extra fields.
