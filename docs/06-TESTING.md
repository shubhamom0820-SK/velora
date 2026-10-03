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

No mocking of the database — tests use a real Postgres, a database of each run's own. External services always
use the **fake** providers from `app/core/providers/`.

## Test database (api)

- **Each run has a database and a Redis database of its own (P-55).** Every checkout on the
  machine shares one Postgres and one Redis, and runs that shared a database failed each other's
  tests (two full runs at once failed 45 and 42 tests that pass alone). So a run takes a slot,
  2 to 15, for as long as its process lives: a Postgres advisory lock on a connection
  `tests/infra.py` keeps open, so a run that crashes or is killed frees its slot when the
  connection closes. The slot gives it `velora_slot<n>_test` and Redis database `<n>`, dropped and
  created empty (the Redis database flushed) when the run takes the slot, so nothing a previous
  run left reaches it. pytest's header names the slot. Redis databases 0 and 1 are `make dev`'s
  and the shared test database used before P-55, which `make infra-up` still creates as
  `velora_test` for branches cut before it.
- `TEST_DATABASE_URL` names a database of your own instead of the slot's; the run still takes a
  slot for its Redis database. Test-only, so it is documented here, not in `02-ARCHITECTURE.md` §11.
- The harness **refuses to start** unless the database name ends in `_test`, and it forces
  `DATABASE_URL`/`REDIS_URL` to the test values, so an exported dev `DATABASE_URL` can never
  put tests on the dev database.
- Every test runs inside a transaction that is rolled back, commits included (savepoints).
  The app under test shares it: a route sees what the test wrote. A test that reaches the
  database without the `db` fixture fails instead of writing for real.
- Postgres or Redis down: **skipped locally, listed by `-ra`; a hard failure when `CI` is
  set.** A missing database in CI must never pass quietly.

### Tests that commit rows (from T-5.1)

A race test needs committed rows on separate connections, so the per-test rollback can't clean up
after it. From T-5.1 a committed ledger row can never be deleted: the ledger refuses DELETE and
TRUNCATE, and foreign keys into `users` are RESTRICT. Each run's database is its own and starts
empty (P-55), but other tests in the same run commit too. So a test that commits:
- **Makes its own users:** fresh men, never onboarded, on phone numbers `make_user` never generates:
  `fresh_man(engine, credits=0)` in `tests/committed.py` (T-5.1), on `+9197…`.
  It never deletes them, and never uses the owner's trigger bypass. They last until the run's slot
  is next taken, which recreates its database; CI starts empty every run.
- **Scopes every assertion to the users it made.** Never a count of a whole table: such a test is
  right alone and wrong the moment anything else commits. That holds for every test, not only the
  ones that commit: from T-5.1 every run holds committed men, so `select(User)` or a count of
  `users` finds them too. T-5.1 found eleven such assertions (in `test_otp_verify.py`,
  `test_refresh.py` and `test_dob_gender.py`) and scoped each to the test's own number.
- **Never commits a wallet that disagrees with its ledger.** T-9.9's reconciliation is global by
  design, so a test proving it catches a mismatch runs inside the rolled-back transaction.
- **Breaks constraints only on a database of its own.** Every run's is (P-55), so a guard broken to
  prove a test catches it touches no other session, and the next run to take the slot starts
  clean. A run pointed at a shared database by `TEST_DATABASE_URL` loses that.

## Fixtures (api)

- `db` — session inside a transaction rolled back after each test.
- `client` — AsyncClient on the app with dependency overrides for providers.
- `make_user(gender="male", onboarded=True, credits=0, verified=None)` → `(user, token)` (T-3.1):
  the four rows signup creates (through T-3.3's find-or-create service from then on, as `make seed`
  does), and a token the `app` fixture accepts. `verified` follows D-008
  unless given, and an onboarded woman who isn't verified can't be made; `credits` are granted
  through `wallet.service.credit()` as an `admin_grant` (T-5.1, rule 5), so anyone but a man is
  refused by the wallet (D-076).
- `make_thread(a, b, status="active", messages=0)`.
- `clock` — freezes/advances "now" for expiry tests (the app reads time only through
  `core.clock.now()` — never `datetime.now()` directly).
- `captured_logs` (P-48) — every log line, structlog's and the stdlib's, with a probe through each.
  A rule-15 test ends with `captured_logs.assert_listening()` beside its "nothing secret" check:
  an absence proves something only if the capture was listening. Read logs from it, never from
  `capfd` or `capsys`, which can miss a logger bound to an earlier test's stream.
- `fake_providers` (T-1.21) — every external service as its in-memory fake; the `app` fixture
  installs it, so no test reaches a real provider. `fake_providers.sms.last_code(phone)`,
  `fake_providers.payments.capture(order_id)` (a signed webhook to deliver),
  `fake_providers.moderation.next = "reject:nudity"` (one-shot).

## Tests that must never be skipped 🔒

If any of these fails, nothing ships.

1. **Wallet concurrency** (T-5.4): 50 parallel debits on 10 Velas → exactly 2 succeed.
2. **Wallet idempotency** (T-5.4): same key 50× concurrently → one entry, for debits and credits
   alike; one event under two different keys → refused by the per-event index (D-077).
3. **Webhook idempotency** (T-8.2): same capture 5× concurrently → credited once.
4. **Webhook signature** (T-8.2): bad signature → no credit.
5. **Ledger reconciliation** (T-9.9): `balance == sum(delta)` for every wallet.
6. **Women never pay** (T-9.9): every paid action by a woman → zero ledger entries.
6b. **Free gifts stay free** (T-8.9): a free gift creates a `gift_sends` row and **zero** ledger
    entries; a paid gift creates exactly one with the price from the `gifts` table.
6c. **A woman has no ledger rows** (T-5.1, D-076): the database refuses any ledger row, and any
    non-zero balance, for a user whose gender isn't `male`, including one with no gender yet.
    Proved by breaking each trigger, and by turning each into a blacklist.
7. **Age gate** (T-3.6): 17y364d refused, the account and everything attached deleted, and only
   the number's hash kept in `banned_identities` (D-072); exactly 18 today accepted. "Everything
   attached" is a row in every table the app role may delete from (D-078, P-54).
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
| J1 | New man: phone → OTP → all onboarding → discover. T-3.13 runs it as far as the photos step; the rest is T-4.9's | T-3.13, T-4.9 |
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

**How it runs (T-3.13).** `make e2e` (CI's `e2e` job, on every push, after `api` and `web` pass):
Playwright drives a production build of the web (`next build && next start`, `APP_ENV=local`, so
production's strict CSP is the one tested) on `127.0.0.1:3100`, against the API from
`api/tests/e2e_server.py` on `127.0.0.1:8100`. The launcher takes a P-55 slot, so the run has a
database and a Redis database of its own, created empty: it never meets a pytest run, and every run
starts with no accounts, bans or rate-limit windows. Chromium at 390 × 844 and 1280 × 800; one
worker, because the fake SMS's outbox lives in the API's one process.
- **Codes** come from `POST /v1/test/sms/last-code` (04-API, local only): what the fake actually
  sent, so a number nothing was sent to, a banned one (D-073), gets none.
- **Any CSP violation fails the journey** (`web/e2e/fixtures.ts`), and the journeys check no URL
  holds the number (D-080).
- **Nothing is kept:** no traces, videos or screenshots, locally or in CI. A trace records request
  and response bodies (numbers, codes, access tokens), and a snapshot of the phone screen shows the
  number. `test-results/` is gitignored for the same reason.
- **T-3.10's session machinery** runs here too (`web/e2e/session.spec.ts`): reload, rotation, two
  tabs, sign-out.
- **Firefox** is Playwright's own build, run by hand (`E2E_FIREFOX=1 make e2e`), never in CI.
- **Against staging, nightly,** is P-67, whose Needs line carries P-66, a Firebase project for
  staging alone. Staging signs in by Firebase, where Path B and the fake don't exist, so a run
  nobody attends needs a Firebase test number, and none ever goes in `velora-ic`, the project
  production uses (D-065). Until then, staging's sign-in has one check, T-3.14's, made by hand
  with the founder's own phone.

There are no pull requests (D-044): "every push" is the trigger, through `/done`'s gate.

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

CI runs pytest in file order. `pytest --shuffle-seed N` runs it in the order seed N gives (P-48's
plugin, committed in T-5.1: an option in `tests/conftest.py`, no dependency), and the header names
the seed, so a reported order can be run again. A test that passes only in file order leans on
something an earlier one left behind: a logger cached before its capture began, a row, a key.

Running CI's commands locally does not prove CI will pass, because the infrastructure differs:
T-1.20's first run failed only because the postgis image built CI's test database differently
from `infra/docker-compose.yml`, so CI now starts the same compose services. A step is verified
only where it actually runs — for T-1.22's migrations, that means on Supabase, which manages
extensions itself, not on local Postgres.

**GitHub only triggers a workflow that exists on the default branch.** `workflow_run`,
`workflow_dispatch`, and `gh run list --workflow <file>` all resolve against `main`, so a new or
renamed workflow can't be triggered or looked up by file from its own branch until it merges.
This cost T-1.20 (the gate's run lookup) and T-1.22 (the first deploy).
