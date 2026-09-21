# Testing — Nexova API

## Running the tests

```bash
cd services/api
uv add --dev pytest pytest-cov httpx
uv run pytest                          # run everything
uv run pytest tests/ --cov=app.auth --cov-report=term-missing   # with coverage
```

All tests use an isolated, throwaway TinyDB file per test (see `tests/conftest.py`'s
`isolated_db` fixture) — nothing here touches `db.json`, and tests never see each
other's data.

## Test plan (AUTH-088)

Every authentication endpoint gets a happy-path, an edge-case, and a failure-mode
test at minimum, plus direct unit tests on the token/password primitives in
`security.py` — those are tested independently of any endpoint because they're
exactly the layer where the regression described in this ticket happened
(silent token-expiration breakage). An endpoint test alone can't easily prove an
expired token is rejected without manipulating time; `test_security.py` does
that directly by hand-crafting tokens with known `exp` values.

| Endpoint | Happy path | Edge case(s) | Failure mode(s) |
|---|---|---|---|
| `POST /auth/login` | Valid credentials → working token that decodes to the right user | Wrong password vs. nonexistent email return **identical** status/message (no user enumeration); password matching is case-sensitive | Inactive account rejected even with correct password; empty password rejected |
| `GET /auth/me` | Valid token → correct identity | User with no linked profile still returns 200 (`profile: null`); role in the response reflects the *current stored* role, not whatever was in the token at issue time | Missing token; malformed token; a reset token can't be used as an access token |
| `POST /auth/forgot-password` | Registered email → send is triggered, generic message returned | Unregistered email gets the **same** response and never triggers a send; response body is byte-identical either way | Email provider throwing still returns 200 with the same message (this is deliberate — see `router.py`'s comment); malformed email rejected before any send is attempted |
| `POST /auth/reset-password` | Valid token → password actually changes (verified via `verify_password`, not just the response code) | **The same token cannot be used twice** (replay protection via `jti`) — this is the single most important test in the suite, given the ticket's context; new password below the 8-char minimum rejected | Malformed token; an access token can't be used as a reset token; token for a since-deleted user; token with a non-numeric `sub` claim |
| `POST /auth/change-password` | Correct current password → change succeeds | New password identical to the old one is accepted (documented as intentional — there's no password-history check) | Wrong current password rejected; no token rejected **and** password confirmed unchanged afterward |
| `security.py` primitives (no endpoint) | Access/reset token round-trip; each reset token gets a unique `jti` | A token expiring in exactly 1 more second still decodes | A token expired 1 second ago is rejected; a token expired since year 2000 is rejected the same way; wrong signing secret rejected; garbage input rejected; hashing the same password twice produces two different (salted) hashes |
| `validate_reset_token` (direct) | Returns the token's `jti` for a genuinely valid, unused token | — | An access-type token is rejected at the type check; a token issued for a different user id is rejected |

## Coverage

```
Name                   Stmts   Miss  Cover   Missing
----------------------------------------------------
app/auth/__init__.py       0      0   100%
app/auth/email.py         13      6    54%   11, 15-21
app/auth/models.py        23      0   100%
app/auth/router.py        63      0   100%
app/auth/security.py      74     10    86%   60-61, 68, 72-73, 80, 108, 112-113, 118
----------------------------------------------------
TOTAL                    173     16    91%
```

`91%` overall, well above the 70% bar — `router.py` and `models.py` are fully
covered. `email.py`'s uncovered lines are the actual `resend.Emails.send(...)`
call itself (lines 15–21): every test mocks `send_reset_email` at the router's
import site rather than calling the real function, since a unit test should
never make a real third-party API call. `security.py`'s remaining gaps are
defensive fallback branches inside `validate_reset_token`/`get_current_user`
(e.g. a token with no `jti` at all) that are one step past what the endpoint
and direct-unit tests already exercise — reasoned as low-value to chase further
per the "well-reasoned 70% beats a mechanical 95%" note in the brief.

## AI-assisted workflow

Per the checklist: the edge cases in this suite were proposed by Claude, not
just boilerplate-generated from a spec. Specifically:

- **The login-endpoint enumeration test** (`test_wrong_password_and_nonexistent_email_give_identical_errors`)
  came from Claude flagging that distinguishing "wrong password" from "no such
  account" in the response is itself a security bug (user enumeration), not
  just an edge case to check for correctness — the ticket didn't explicitly
  name this case.
- **The token-replay test** (`test_the_same_reset_token_cannot_be_used_twice`)
  was prioritized as "the single most important test in the suite" by Claude
  given the ticket's own context (a silent token-logic regression causing a
  real incident) — this is the test most directly analogous to the bug that
  prompted AUTH-088 in the first place.
- **The cross-type-token tests** (a reset token used where an access token is
  expected, and vice versa) were suggested as a failure mode worth pinning
  explicitly, since both token types are valid JWTs signed with the same
  secret and differ only by a `type` claim — a natural place for a future
  refactor to silently break.

Every generated test was reviewed and run against the real logic before being
kept; none were committed without understanding why they pass.

**Known limitation, disclosed rather than hidden:** `app/profiles/models.py`
and `app/profiles/service.py` were not available at the time this suite was
written and were reconstructed from their call signatures as used elsewhere
in the codebase (`auth/router.py`'s `/me` endpoint, `users/service.py`'s
`create_user`). The reconstructed versions are internally consistent and the
tests pass against them, but **should be diffed against the real files**
before merging — if the real `ProfileOut` has different required fields, the
happy-path assertions in `test_me.py` that touch `profile` may need
adjustting (none currently assert on a populated profile's contents, only on
`profile is None`, so the risk is contained to future tests that do).

No app-logic bugs were found by this suite — every test passed against the
real `router.py`/`security.py` on the first correctly-configured run. (One
environment issue was caught and fixed during development: a `bcrypt` package
version newer than `passlib` supports caused every password-hashing test to
fail with an internal passlib self-test error unrelated to the app code —
pinning `bcrypt<4.1` resolved it. Worth adding as a version constraint if your
`pyproject.toml` doesn't already pin bcrypt indirectly through `libpass`.)
