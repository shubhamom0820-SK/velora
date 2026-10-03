# 06 · Testing

## The rule

A task isn't done until its tests pass. Tests are written in the same task as the code — not
"later". A bug fix starts with a failing test that reproduces it.

## Layers

| Layer | Tool | What | Speed target |
|---|---|---|---|
| Unit (api) | pytest | pure functions: security, masking regexes, pricing, ranking score, fraud weights | < 5 s total |
| Service (api) | pytest + real Postgres + fake providers | business rules through the service layer | < 60 s total |
| API (api) | pytest + httpx AsyncClient | status codes, error codes, auth, schemas | inside the above |
| Unit (web) | vitest + Testing Library | primitives, hooks, formatters, countdown | < 20 s |
| E2E | Playwright (Chromium, mobile viewport 390×844 + desktop 1280×800) | the user journeys below | < 5 min |

No mocking of the database — tests use a real Postgres (`velora_test`). External services always
use the **fake** providers from `app/core/providers/`.

## Test database (api)

- Tests run on `velora_test` (created by `make infra-up`). Override the location with
  `TEST_DATABASE_URL` — test-only, so it is documented here, not in `02-ARCHITECTURE.md` §11.
- The harness **refuses to start** unless the database name ends in `_test`, and it forces
  `DATABASE_URL`/`REDIS_URL` to the test values, so an exported dev `DATABASE_URL` can never
  put tests on the dev database.
- Every test runs inside a transaction that is rolled back, commits included (savepoints).
  The app under test shares it: a route sees what the test wrote. A test that reaches the
  database without the `db` fixture fails instead of writing for real.
- Postgres or Redis down: **skipped locally, listed by `-ra`; a hard failure when `CI` is
  set.** A missing database in CI must never pass quietly.

## Fixtures (api)

- `db` — session inside a transaction rolled back after each test.
- `client` — AsyncClient on the app with dependency overrides for providers.
- `make_user(gender="male", onboarded=True, credits=0, verified=None)` → `(user, token)` (T-3.1):
  the four rows signup creates (through T-3.3's find-or-create service from then on, as `make seed`
  does), and a token the `app` fixture accepts. `verified` follows D-008
  unless given, and an onboarded woman who isn't verified can't be made; `credits` other than 0
  raises until T-5.1 credits them through `wallet.service.credit()` (rule 5).
- `make_thread(a, b, status="active", messages=0)`.
- `clock` — freezes/advances "now" for expiry tests (the app reads time only through
  `core.clock.now()` — never `datetime.now()` directly).
- `fake_providers` (T-1.21) — every external service as its in-memory fake; the `app` fixture
  installs it, so no test reaches a real provider. `fake_providers.sms.last_code(phone)`,
  `fake_providers.payments.capture(order_id)` (a signed webhook to deliver),
  `fake_providers.moderation.next = "reject:nudity"` (one-shot).

## Tests that must never be skipped 🔒

If any of these fails, nothing ships.

1. **Wallet concurrency** (T-5.4): 50 parallel debits on 10 Velas → exactly 2 succeed.
2. **Wallet idempotency** (T-5.4): same key 50× concurrently → one entry.
3. **Webhook idempotency** (T-8.2): same capture 5× concurrently → credited once.
4. **Webhook signature** (T-8.2): bad signature → no credit.
5. **Ledger reconciliation** (T-9.9): `balance == sum(delta)` for every wallet.
6. **Women never pay** (T-9.9): every paid action by a woman → zero ledger entries.
6b. **Free gifts stay free** (T-8.9): a free gift creates a `gift_sends` row and **zero** ledger
    entries; a paid gift creates exactly one with the price from the `gifts` table.
7. **Age gate** (T-3.6): 17y364d refused, the account and everything attached deleted, and only
   the number's hash kept in `banned_identities` (D-072); exactly 18 today accepted.
8. **Gender immutable** (T-1.16, T-3.6): second set → `IMMUTABLE_FIELD`; DB trigger also blocks.
9. **Blocks are total** (T-9.1): after a block, neither side appears to the other anywhere.
10. **Clearing is one-sided** (T-7.8): A clears → B still sees every message.
11. **Contact masking** (T-7.3): numbers, spaced digits, emails, UPI IDs, social handles masked in
    the first 20 messages; `body_raw` never returned by any user-facing endpoint.
12. **Expired thread** (T-7.6): sending → `THREAD_EXPIRED`; re-open charges exactly 3.
13. **A Knot is mutual** (T-7.7): one tap never converts; two taps always do.
14. **Private data** (T-4.4, T-4.5): processed images contain no EXIF; selfies never appear in
    any public response.
15. **Refresh reuse** (T-3.4): replaying a refresh token rotated more than 10 seconds ago revokes
    the family; within 10 seconds it's refused without that (D-067).
16. **Firebase token** (T-3.14): forged, expired, wrong-audience and already-used ID tokens are all
    rejected; a non-`+91` number never creates a user.
17. **The dev seed stays local** (T-1.15): `ENV` staging and production, a database on another
    host, and a local address to a database `make infra-up` didn't stamp are each refused before
    a row is written (D-064).

A test in this list is marked `@pytest.mark.critical`; CI runs them first and fails fast.

## E2E journeys

| # | Journey | Task |
|---|---|---|
| J1 | New man: phone → OTP → all onboarding → discover | T-3.13, T-4.9 |
| J2 | New woman: blocked until selfie approved | T-4.9 |
| J3 | Under-18 refused, same number can't retry | T-3.13 |
| J4 | Swipe → match → open thread (−5) → chat both ways live | T-7.13 |
| J5 | Voice note from woman → man unlocks (−5) → plays | T-7.13 |
| J6 | Both tie the knot → Knots tab, no countdown | T-7.13 |
| J7 | Thread expires → read-only → re-open (−3) | T-7.13 |
| J8 | Buy Velas (fake gateway) → balance updates | T-8.7 |
| J9 | Payment fails → retry sheet → success | T-8.7 |
| J10 | Report with also-block → confirmation shown → person gone everywhere | T-9.1 |
| J11 | Moderator resolves a report and freezes the account | T-9.5 |
| J12 | Clear chat → undo → restore from You tab | T-7.10 |

Run E2E on every PR touching `web/` and nightly against staging.

## What not to test

Third-party SDK internals, Tailwind classes, exact copy text (test by role/label instead),
and anything already enforced by the type checker.

## CI order

`.github/workflows/ci.yml` (T-1.20) runs on every push as three parallel jobs: `api` (full-history
secrets scan, lint, migrate, pytest), `web` (lint, vitest, `next build`) and `repo` (types are
fresh, every pre-commit hook, the `/done` gate's own tests). `/done` fast-forwards `main` only when
the run for that exact commit passed (D-044). Within each job:

1. Lint first, failing fast: ruff + mypy · eslint + tsc + prettier
2. `pytest -m critical`, then the rest of pytest (`make test-api`) · vitest
3. `next build`
4. Playwright (from T-3.13, only if 1–3 pass)

Running CI's commands locally does not prove CI will pass, because the infrastructure differs:
T-1.20's first run failed only because the postgis image built CI's test database differently
from `infra/docker-compose.yml`, so CI now starts the same compose services. A step is verified
only where it actually runs — for T-1.22's migrations, that means on Supabase, which manages
extensions itself, not on local Postgres.

**GitHub only triggers a workflow that exists on the default branch.** `workflow_run`,
`workflow_dispatch`, and `gh run list --workflow <file>` all resolve against `main`, so a new or
renamed workflow can't be triggered or looked up by file from its own branch until it merges.
This cost T-1.20 (the gate's run lookup) and T-1.22 (the first deploy).
