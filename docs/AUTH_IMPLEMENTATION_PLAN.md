# Auth Implementation Plan — AUTH-01, AUTH-02, AUTH-03

Consolidated planning notes across three sequential milestones. Each
becomes its own branch and its own PR against `main`, in this order,
since each depends on the last.

## Status

- [x] AUTH-01 (feature/auth-api) — backend complete, verified end-to-end
      against a running server (registration, login, /auth/me with and
      without a token, 5 newly-protected routes correctly reject
      unauthenticated calls)
- [ ] AUTH-02 (feature/auth-frontend) — not started
- [ ] AUTH-03 (feature/password-reset) — not started

## Build order

1. `feature/auth-api` — backend: users, profiles, login, route protection
2. `feature/auth-frontend` — frontend: login/register/account views, route guard
3. `feature/password-reset` — backend + frontend: forgot/reset/change password

## AUTH-01 — Backend (feature/auth-api)

### Non-negotiable requirements
- `uv add "python-jose[cryptography]" "libpass[bcrypt]"` — never pip/pipenv
- Import stays `from passlib.hash import bcrypt` (libpass is a drop-in fork) —
  verified working with `libpass==1.9.3`
- `User` = credentials only (`id`, `email`, `hashed_password`, `is_active`,
  `role`, `created_at`). Never display name/contact fields.
- `Profile` = display/contact data (`name`, `phone`, `address`), linked via
  `user_id`, one-to-one.
- `role` is a closed enum: `admin`, `manager`, `user`. New registrations via
  `POST /users` always default to `user` — verified: even if a client sends
  `"role": "admin"` in the payload, it's ignored (no `role` field exists on
  `UserCreate` at all).
- Stateless JWT only — no sessions, no cookies.
- Passwords hashed via bcrypt, never compared in plaintext.
- Two distinct failure modes: `401` (no/invalid/expired token) vs. `403`
  (valid token, but caller isn't allowed to touch this resource).
- User/Profile live in TinyDB permanently, even after Supabase is
  introduced in a later milestone — other tables will reference the TinyDB
  user id as a plain `user_uuid` string, not a real foreign key.

### Architectural decisions made
- **`password_changed_at`** field added to `User` now (not required by
  AUTH-01's literal field list, but AUTH-03 needs server-side reset-token
  invalidation, and TinyDB has no migrations — adding it now avoids a
  painful retrofit later). Bumped on both login-password-change and
  future reset-password.
- JWT payload carries `sub` (user id), `role`, `type: "access"`, `iat`,
  `exp`. The `type` claim exists so a future `type: "reset"` token
  (AUTH-03) can never be replayed against a normal protected route, and
  vice versa.
- `OAuth2PasswordBearer(tokenUrl="/auth/login")` used only to register the
  Bearer scheme in OpenAPI and to extract the token from the header.
  `POST /auth/login` itself is a plain JSON body (`{email, password}`),
  consistent with every other endpoint in this API — not an OAuth2 form
  submission. Known consequence, confirmed in testing: Swagger's built-in
  "Authorize" button doesn't work cleanly with this combination (it expects
  form-encoded credentials at the tokenUrl), so manual verification was
  done via curl with the copied token instead — still "verified manually
  via the interactive docs" in spirit, just not via that specific button.
- `PUT /users/{id}`: self-or-admin required for any update; changing
  `role` specifically requires the caller to be an admin, even on their
  own account (a user can't self-promote).
- `DELETE /users/{id}`: same self-or-admin rule applied for consistency,
  though the README only states this explicitly for `PUT`.

### Which 5+ existing routes get protected
- `POST /suppliers`
- `PATCH /suppliers/{id}/rate`
- `PATCH /suppliers/{id}/status`
- `DELETE /suppliers/{id}`
- `POST /api/incidents/analyze`

Left public: `GET /suppliers` (list/filter), `GET /suppliers/{id}`,
`GET /api/incidents/results/export`.

### Verified before handoff and again in the real repo
Registration + duplicate-email rejection, role-escalation-on-registration
ignored, wrong-password login (401), correct login, `/auth/me` with/without
token, self-vs-other-vs-admin update logic (200/403 correctly for each),
self-vs-other delete + cascading profile delete, expired/malformed/
tampered-signature tokens (all 401 in sandbox TestClient), and the 5
newly-protected routes correctly rejecting unauthenticated calls in the
real running server (curl-verified).

## AUTH-02 — Frontend (feature/auth-frontend)

### Scope decision
Auth flows and route protection apply to **`uis/backoffice` only**.
Reasoning: the README says protection applies to every view "that
requires an authenticated session" — not every app by name.
`uis/talent-pipeline-tracker` calls an entirely external playground API,
never our own protected endpoints, so none of its views meet that
condition. `uis/website` is excluded explicitly and isn't a Next.js app
regardless.

### Non-negotiable requirements
- Token in `localStorage`, sent as `Authorization: Bearer <token>` on
  every protected call.
- No Next.js middleware for route protection (it can't read
  `localStorage`) — client-side layout guard or hook only.
- Registration is two API calls: `POST /users` then `POST /auth/login`
  with the same credentials (registration itself returns no token).
- A `401` from any protected call anywhere must globally clear the token
  and redirect to `/login` — implemented once in the shared fetch layer,
  not per-page.
- `uis/backoffice`'s existing `lib/incidents-api.ts` and
  `lib/suppliers-api.ts` must be retrofitted to send the Bearer header,
  since their mutating calls are now protected by AUTH-01.

### Views to build
`/login`, `/register`, `/account/profile` (reads `GET /auth/me`, edits via
`PUT /profiles/me`).

## AUTH-03 — Password reset (feature/password-reset)

### Non-negotiable requirements
- Reset token must be invalidatable after one use — a JWT `exp` claim
  alone is explicitly insufficient per the README.
- `POST /auth/forgot-password` always returns `200`, regardless of
  whether the email exists (anti-enumeration).
- `POST /auth/reset-password` returns `400` for invalid, expired, or
  already-used tokens.
- `POST /auth/change-password` verifies the current password before
  accepting a new one; wrong current password → `400`.
- Email service: **Resend**, account created under `edenjoybot` (kept
  separate from the developer's personal inbox on purpose). API key in
  `.env` as `RESEND_API_KEY`, never committed.
- **Known sandbox limitation**: without domain verification, Resend can
  only send to the email the account is registered under. The test user
  used to verify this flow end-to-end must use the `edenjoybot` address.

### Architectural decision made
Reset-token invalidation via the `password_changed_at` field already
added in AUTH-01: the reset JWT carries `iat`; on
`POST /auth/reset-password`, reject if `token.iat <= user.password_changed_at`.
On successful reset, bump `password_changed_at`. No separate token-tracking
table needed. The reset JWT also carries `type: "reset"`, distinct from
`type: "access"`, so a leaked access token can't be replayed here.

### Frontend routes
`/forgot-password` (always shows confirmation, disables form after
submit), `/reset-password` (reads `token` from URL query string, redirects
to `/login` on success), `/account/change-password`. `/login` gets a
"Forgot your password?" link.
