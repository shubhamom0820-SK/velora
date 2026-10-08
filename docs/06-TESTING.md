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
- The face models (T-4.5) the same way: the real face match's tests (`tests/core/test_facematch.py`,
  the worker's model refusals) skip locally until `make models` has fetched them, and fail in CI,
  which fetches them first. They run on NASA's public-domain portraits in
  `tests/fixtures/faces/`, which prove the mechanism, never accuracy (D-260).
- Redis shares pub/sub channels across its databases, so a run's slot doesn't separate them: a
  test that listens for a wake (T-4.5) uses a channel of its own, never `wake:verify_selfie`, except
  the one end-to-end test that must, which reads only its own ids.

### Tests that commit rows (from T-5.1)

A race test needs committed rows on separate connections, so the per-test rollback can't clean up
after it. From T-5.1 a committed ledger row can never be deleted: the ledger refuses DELETE and
TRUNCATE, and foreign keys into `users` are RESTRICT. Each run's database is its own and starts
empty (P-55), but other tests in the same run commit too. So a test that commits:
- **Makes its own users:** fresh men, never onboarded, on phone numbers `make_user` never generates:
  `fresh_man(engine, credits=0)` in `tests/committed.py` (T-5.1), on `+9197…`, numbered one past
  the highest the database holds, never at random (two of fifty random numbers can collide).
  It never deletes them, and never uses the owner's trigger bypass. They last until the run's slot
  is next taken, which recreates its database; CI starts empty every run.
- **Scopes every assertion to the users it made.** Never a count of a whole table: such a test is
  right alone and wrong the moment anything else commits. That holds for every test, not only the
  ones that commit: from T-5.1 every run holds committed men, so `select(User)` or a count of
  `users` finds them too. T-5.1 found eleven such assertions (in `test_otp_verify.py`,
  `test_refresh.py` and `test_dob_gender.py`) and scoped each to the test's own number.
- **Takes the server's turn before opening many connections.** Every checkout shares one Postgres
  of 100 connections, so T-5.4's fifty-connection tests first take a server-wide advisory lock
  (`fifty_turn`, P-142) and a second run waits rather than failing for want of connections.
- **Takes back the payments it commits (T-8.2, the one exception to the bypass).** A committed
  `payments` row names its pack by a RESTRICT key, and the seed's and T-5.2's downgrades delete
  packs, so one left behind turns every later downgrade test red. A race test that must commit
  payments (T-8.2's captures at once) deletes them at the end with `take_back_payments(engine,
  ids)` in `tests/committed.py`: `payments_no_delete` switched off, the rows deleted, switched on
  again, in one transaction as the owner, so no other connection ever sees the trigger off. The
  ledger rows they credited stay; they name no pack. Any other test proves payments inside the
  rolled-back transaction, as T-8.1's same-key race does.
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
  `fake_providers.moderation.next = "reject:nudity"` (one-shot; also `"fail"`). The fake answers in
  Sightengine's own shape, through the real reader, as D-094's real check corrected it (T-4.4).

## Tests that must never be skipped 🔒

If any of these fails, nothing ships.

1. **Wallet concurrency** (T-5.4): 50 parallel debits on 10 Velas → exactly 2 succeed.
2. **Wallet idempotency** (T-5.4): same key 50× concurrently → one entry, for debits and credits
   alike; one event under two different keys → refused by the per-event index (D-077).
3. **Webhook idempotency** (T-8.2): same capture 5× concurrently → credited once.
4. **Webhook signature** (T-8.2): bad signature → no credit.
5. **Ledger reconciliation** (T-9.9): `balance == sum(delta)` for every wallet.
6. **Women never pay** (T-9.9): every paid action by a woman → zero ledger entries.
6b. **Free sends stay free** (T-8.9, D-231): each of a week's fifteen free sends creates a
    `gift_sends` row and **zero** ledger entries; the sixteenth creates exactly one, with the price
    from the `gifts` table.
6c. **A woman has no ledger rows** (T-5.1, D-076): the database refuses any ledger row, and any
    non-zero balance, for a user whose gender isn't `male`, including one with no gender yet.
    Proved by breaking each trigger, and by turning each into a blacklist.
7. **Age gate** (T-3.6): 17y364d refused, the account and everything attached deleted, and only
   the number's hash kept in `banned_identities` (D-072); exactly 18 today accepted. "Everything
   attached" is a row in every table the app role may delete from (D-078, P-54), and every file
   behind them, queued before the commit and read back as gone once the user is (D-090, T-4.2).
8. **Gender immutable** (T-1.16, T-3.6): second set → `IMMUTABLE_FIELD`; DB trigger also blocks.
8b. **No woman goes live unmatched** (T-4.8, D-310, D-008): finishing onboarding without a matched
    selfie → `VERIFICATION_REQUIRED` for anyone but a man, someone with no gender included; and the
    database refuses any write moving such a user to `done`, inserts too, and an upgrade over one
    already there. Proved by breaking the service's check, the trigger, and each into a blacklist.
9. **Blocks are total** (T-9.1): after a block, neither side appears to the other anywhere.
10. **Clearing is one-sided** (T-7.8): A clears → B still sees every message.
11. **Contact masking** (T-7.3): numbers, spaced digits, emails, UPI IDs, social handles masked in
    the first 20 messages; `body_raw` never returned by any user-facing endpoint.
12. **Expired thread** (T-7.6): his send → `THREAD_EXPIRED`, and hers is delivered (D-097); re-open charges exactly 2 (D-098); Extend charges 10 once, from expired too, never 2 beside it (D-253); his message never restarts the hour and hers does (D-097).
13. **A Knot is mutual** (T-7.7): one tap never converts; two taps always do.
14. **Private data** (T-4.4, T-4.5): processed images contain no EXIF; selfies never appear in
    any public response. From T-4.4: photos that genuinely carry a location
    (`tests/fixtures/located/`, confirmed by two readers that aren't Pillow) come out with none,
    in JPEG, PNG and WebP, and through the whole pipeline, every stored copy and what Sightengine
    is sent. From T-4.5: an approved selfie has no public copy or key, isn't among its owner's
    photos, can't be read as one, and `GET /verification/latest` carries no link, key or number;
    a selfie carrying a location is stored, and compared, with none; an under-18 refusal takes a
    selfie's file and its verification with the rest. From T-4.12: the face photo (D-391) joins
    what is never public unless chosen: approved, it has no public copy or key, is listed to its
    owner alone by a signed link and to nobody else (`GET /me/photos` and `GET /photos/{id}` are
    the same `NOT_FOUND` as no photo), the selfie is compared with it alone, and an under-18
    refusal takes its file too. Showing it on the profile is a public copy that goes through
    moderation like any upload.
15. **Refresh reuse** (T-3.4): replaying a refresh token rotated more than 10 seconds ago revokes
    the family; within 10 seconds it's refused without that (D-067).
16. **Firebase token** (T-3.14): forged, expired, wrong-audience and already-used ID tokens are all
    rejected, with wrong issuers, other sign-in providers and stale sign-ins among them, each the
    same `FIREBASE_TOKEN_INVALID` (D-085); a non-`+91` number never creates a user.
17. **The dev seed stays local** (T-1.15): `ENV` staging and production, a database on another
    host, and a local address to a database `make infra-up` didn't stamp are each refused before
    a row is written (D-064).

A test in this list is marked `@pytest.mark.critical`; CI runs them first and fails fast.

## E2E journeys

| # | Journey | Task |
|---|---|---|
| J1 | New man: phone → OTP → all onboarding → discover. T-3.13 ran it as far as the photos step; T-4.9 takes it the rest of the way: from T-4.12 he leaves the photos step with no photo at all (D-392), 5 interests, a PIN set and confirmed, `/discover` barred until he's done, "Skip for now" at the selfie (D-008, through T-4.8's completion), Discover inside the shell, and the PIN lock after a reload, opened by his PIN. Then each of the shell's four places from its nav, with the shell where the browser draws it at both widths (P-82): on the phone the nav is the screen's bottom edge and `<main>`'s content ends above it, on the desktop the nav sits in the header's box; `/login` and the birthday step have no nav at all. He shares a position in Phagwara, which the browser gives only under `geolocation=(self)`: the Permissions-Policy proved by its effect (T-4.10). Its twin, refused the position, picks an area from the API's 17 | T-3.13, T-4.10, T-4.9, T-4.12, P-82 |
| J2 | New woman: the same to the selfie, the PIN skipped; from T-4.12 her face photo (D-391) is what the browser uploads to the local S3, checked by the worker (the fake moderation) and approved, private, with no public photo; no "Skip for now", and `/discover` barred; the camera opens under `camera=(self)` (T-4.7) on Chromium's fake camera, playing a committed portrait; the shot is checked, sent, and compared on the worker by the real models (D-088) with her face photo, the same person's other portrait, and matched; "Continue" finishes sign-up (T-4.8) and a reload keeps her in | T-4.9, T-4.12 |
| J3 | Under-18 refused, same number can't retry | T-3.13 |
| J4 | Swipe → match → open thread (−5) → chat both ways live | T-7.13 |
| J5 | Voice note from woman → man unlocks (−5) → plays | T-7.13 |
| J6 | Both tie the knot → Knots tab, no countdown | T-7.13 |
| J7 | Thread expires → read-only → re-open (−2) | T-7.13 |
| J8 | Buy Velas (fake gateway) → balance updates | T-8.7 |
| J9 | Payment fails → retry sheet → success | T-8.7 |
| J10 | Report with also-block → confirmation shown → person gone everywhere | T-9.1 |
| J11 | Moderator resolves a report and freezes the account | T-9.5 |
| J12 | Clear chat → undo → restore from You tab | T-7.10 |

**How it runs (T-3.13, T-4.9).** `make e2e` (CI's `e2e` job, after `api` and `web` pass, on a
push that changed a path outside the docs allowlist, P-282 and D-410; locally it needs
`make infra-up` and `make models`): Playwright drives a production build of
the web (`next build && next start`, `APP_ENV=local`, so production's strict CSP is the one tested)
on `127.0.0.1:3100`, against the API from `api/tests/e2e_server.py` on `127.0.0.1:8100`. The
launcher takes a P-55 slot, so the run has a database and a Redis database of its own, created
empty: it never meets a pytest run, and every run starts with no accounts, bans or rate-limit
windows. Chromium at 390 × 844 and 1280 × 800; one worker, because the fake SMS's outbox lives in
the API's one process.
- **The whole stack, from T-4.9 (D-330):** storage is the local S3 (D-086), whose private bucket
  admits the E2E's origin by a CORS rule of its own (`infra/s3/private-cors.xml`, held by
  `api/tests/test_local_s3_cors.py`), since the browser uploads by presigned PUT; the launcher
  runs the worker beside the API, a child process on the same slot, with its settings in its
  environment and never from `api/.env`; moderation is the fake, which approves; the face match
  is the real one (D-088), so the launcher refuses to start without the models. The S3's two
  buckets are shared with every pytest run and `make dev` (P-55 gives the S3 no slot); each
  object's key carries its user's id, so runs never meet there.
- **The worker polls every 0.5 seconds here, not D-091's 10.** D-091's interval is Upstash's
  per-command price on the deployed Redis; this Redis is Docker's and free, and at 10 seconds a
  run would wait that long on every photo for nothing. The wake (D-261) decides the selfie either
  way. Nothing of D-091 is changed: it is the worker's setting, for this run alone.
- **The camera** is Chromium's fake one (`--use-fake-device-for-media-stream`,
  `--use-file-for-fake-video-capture`), playing NASA's 2017 portrait of Raja Chari from
  `api/tests/fixtures/faces`, copied at load as a one-frame MJPEG; J2's profile photo is his 2021
  portrait, so the models are given two photos of one person. The journeys run on the full
  Chromium in its new headless mode (`channel: "chromium"`), not Playwright's headless shell,
  which has no media capture. Firefox's by-hand run skips J2: the fake camera is Chromium's.
- **Codes** come from `POST /v1/test/sms/last-code` (04-API, local only): what the fake actually
  sent, so a number nothing was sent to, a banned one (D-073), gets none.
- **Any CSP violation fails the journey** (`web/e2e/fixtures.ts`), and the journeys check no URL
  holds the number (D-080).
- **Nothing is kept:** no traces, videos or screenshots, locally or in CI. A trace records request
  and response bodies (numbers, codes, access tokens), and a snapshot of the phone screen shows the
  number. `test-results/` is gitignored for the same reason.
- **T-3.10's session machinery** runs here too (`web/e2e/session.spec.ts`): reload, rotation, two
  tabs, sign-out.
- **The nonce routes' CSP** (`web/e2e/csp.spec.ts`, D-541), by its effect: a fresh nonce per
  response and no `'unsafe-inline'` on `/login`, and an injected inline handler that runs on `/`
  and is refused on `/login`. It uses plain `@playwright/test`, since it causes a violation on
  purpose.
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

`.github/workflows/ci.yml` (T-1.20) runs on every push: `api` (full-history secrets scan, lint,
migrate, pytest), `web` (lint, vitest, `next build`), `image` (the API image: no `.env` inside,
serves, fails fast) and `repo` (types are fresh, every pre-commit hook, the gates' own tests) in
parallel, then `e2e` (Playwright, T-3.13) after `api` and `web`. `/done` fast-forwards `main` only
when the run for that exact commit passed (D-044). **Minutes (P-282, D-410):** on `main` a first
job, `vouch`, asks GitHub for a passed branch run of the same SHA (`scripts/ci-vouch`) and, finding
one, the four jobs are skipped: the run is still a green run of the SHA on `main`, which the
deploy and the gates read; nothing vouching, as after a manual-path landing, runs them all. `e2e`
runs only when a changed path is outside the allowlist of what can't reach a journey, `docs/`,
`*.md`, `.claude/` (`scripts/ci-e2e-needed`, decided in the `api` job: on a branch, everything it
changed since it left `main`; on `main`, since the previous tip); skipped, it leaves the run
`success`. A second push to a task branch cancels the first's run, never on `main`. Each script
has its test beside it, run by `repo`. Within each job:

1. Lint first, failing fast: ruff + mypy · eslint + tsc + prettier
2. `pytest -m critical`, then the rest of pytest (`make test-api`) · vitest
3. `next build`
4. Playwright (from T-3.13, only if 1–3 pass)

CI runs pytest in file order. `pytest --shuffle-seed N` runs it in the order seed N gives (P-48's
plugin, committed in T-5.1: an option in `tests/conftest.py`, no dependency), and the header names
the seed, so a reported order can be run again. A test that passes only in file order leans on
something an earlier one left behind: a logger cached before its capture began, a row, a key.

**Breaking runs** prove a guard's test can fail: `uv run python -m tests.break_guards` (from
`api/`) weakens one guard at a time as a careless change would, runs that task's tests on a fresh
slot database with no bytecode, and restores each file byte for byte, proved by SHA-256. A case is
red only when every test it names failed; a run where Postgres refused the fifty connections is
inconclusive. `--list` names the cases (T-5.1's thirty-five, T-5.4's six), a prefix runs some
(`t54-`), and `--repeat N` reports a scheduler-dependent red as red in N of N (P-58).
`tests/test_break_guards.py` fails if a case's anchor leaves its file, so the claims stay
re-runnable. Not in CI: a full pass takes about twenty minutes. The web's are
`node scripts/break-guards.mts` (from `web/`, T-4.6: the CSP, the photo slots' states, the
transport boundary, the upload), the same shape with vitest, a prefix runs some (`t46-csp`), and
`src/lib/break-guards.test.ts` keeps their anchors honest.

Running CI's commands locally does not prove CI will pass, because the infrastructure differs:
T-1.20's first run failed only because the postgis image built CI's test database differently
from `infra/docker-compose.yml`, so CI now starts the same compose services. A step is verified
only where it actually runs — for T-1.22's migrations, that means on Supabase, which manages
extensions itself, not on local Postgres.

**GitHub only triggers a workflow that exists on the default branch.** `workflow_run`,
`workflow_dispatch`, and `gh run list --workflow <file>` all resolve against `main`, so a new or
renamed workflow can't be triggered or looked up by file from its own branch until it merges.
This cost T-1.20 (the gate's run lookup) and T-1.22 (the first deploy). **And a skipped job skips
every job downstream of it in the needs chain,** however green the jobs between, unless that
job's `if` opts out with a status function (`!cancelled()`) and names the results it needs:
P-282's first proof run had `e2e` skipped on a branch with `e2e=true` printed, because `vouch`
above it was (D-410).
