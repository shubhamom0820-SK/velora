# CLAUDE.md — Velora

Read this file fully at the start of every session. It is short on purpose.
The detail lives in `docs/`. When a rule here conflicts with anything else, this file wins.

## What Velora is

A web-first dating app for India. Women use it free. Men buy **Velas**.
Every conversation starts as a **Thread** that expires after an hour, restarted only by her
messages (D-097, built by T-7.6). Extend buys a day.
If both people tap "Tie the knot", it becomes a **Knot** — permanent and free forever.
Permanence is granted by the other person, never bought.

## Read order

1. `docs/05-PLAN.md` — find the task you were given. This is the only source of what to build.
2. `docs/01-DECISIONS.md` — why things are the way they are. Do not re-open locked decisions.
3. `docs/03-SCHEMA.md` and `docs/04-API.md` — the contracts. Match them exactly.
4. `docs/02-ARCHITECTURE.md`, `docs/06-TESTING.md`, `docs/07-CHECKLISTS.md`, `docs/08-DESIGN.md` — as needed.
5. `docs/09-RESEARCH.md` — why the product is shaped this way; read before proposing product changes.

## Stack (pinned — do not substitute)

| Layer | Choice |
|---|---|
| Web | Next.js (App Router) + React + TypeScript strict + Tailwind; lucide-react icons (D-042) |
| Web data | TanStack Query (server state), Zustand (client state), Zod, React Hook Form |
| Swipe | @use-gesture/react + @react-spring/web |
| Sign-in | Firebase phone auth (D-035): the web's `firebase` SDK; the API checks its tokens with PyJWT and httpx, no `firebase-admin` (D-085) |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg, Alembic, GeoAlchemy2 (D-040); PyJWT, argon2-cffi, cryptography, phonenumberslite (D-060) |
| API logging | structlog (JSON logs); responses serialised by FastAPI/Pydantic — D-038 |
| DB | PostgreSQL 16 + PostGIS + pg_trgm + pgcrypto + citext locally and in CI; Supabase runs 17 (D-047, P-34) |
| Cache/queue | Redis + ARQ |
| HTTP out | httpx (async) — never `requests` |
| Storage | Cloudflare R2 via aioboto3, presigned URLs only |
| Hosting | Vercel (web) · Fly.io `sin` (api + worker) · Supabase `ap-south-1` · Upstash Mumbai — data stays in India (D-048) |
| Tooling | uv, ruff, mypy, pytest, pnpm, eslint, prettier, vitest + Testing Library, Playwright, pre-commit, gitleaks — D-039, D-042 |

## Repo layout

```
velora/
  CLAUDE.md
  docs/                 plan, contracts, decisions
  .claude/commands/     /task /review /done
  .github/workflows/    CI pipelines
  api/                  FastAPI app
    app/core/           config, db, redis, events, security, errors, deps, providers (fakes local-only),
                        storage_keys, pagination (every list's page and cursor, D-270), audio
                        (what a voice note is and how long, by its bytes, D-620), vapid (Web
                        Push's keys and token; `python -m app.core.vapid` pipes a new pair, D-856)
    app/modules/<name>/ router.py service.py repository.py schemas.py models.py
    app/workers/        ARQ worker (main.py, `python -m app.workers`) + tasks/
    app/tools/          checks run by hand inside a deployed machine (storage_probe, T-4.1;
                        sightengine_shape, T-4.4; selfie_review, the founder's, T-4.5, D-264)
    alembic/            migrations
    seed/               make seed: dev data, local stack only, never in the image (D-064)
    bench/              benchmarks run by hand, never in the image nor `make test`: liveness/,
                        T-4.11's probe and weights check, its torch and onnxruntime only in its
                        own Dockerfile (D-381); discovery/, T-6.2's feed timed at 50k profiles;
                        realtime/, T-7.4's 1,000 sockets on one API process (D-557)
    tests/              mirrors app/ (and seed/, bench/)
  web/                  Next.js app (App Router, TypeScript strict, Tailwind v4)
  infra/                docker-compose.yml, fly.api.toml + fly.worker.toml + STAGING.md (staging's
                        runbook), fly.api.production.toml + PRODUCTION.md (production's: released by tag)
  scripts/              ci-gate, push-gate, release-gate, ci-vouch + ci-e2e-needed (CI's minutes,
                        D-410), with-tools, staging-smoke, check-image-no-env,
                        check-image-no-bench-tools, migrate-with-url
  Makefile
```

`web/` is Next.js 16, scaffolded in T-1.17: `src/app/` (route groups `(marketing)` `(auth)`
`(app)` `(share)` `admin`; `(share)` is `/@username`'s page through a rewrite, D-068, D-544), `src/styles/tokens.css` (design tokens — the only place colours live; a pre-commit
hook enforces it, with one exception, `src/styles/theme-color.ts`) and `src/i18n/en.ts` (every
user-facing string, read through `t()`, with one exception, `src/app/opengraph-image.alt.txt`, which
Next reads as a file; a test holds it to `en.ts`); `src/i18n/claims.test.ts` holds every one to D-262:
none says a person is verified, real, live or who they say (T-4.5). `src/lib/site.ts` says where the site lives and
that only production is indexed (T-2.4), from `APP_ENV`, which `next build` refuses unless it is
local, ci, staging or production (`src/lib/build-env.ts`, T-2.6). `src/lib/security-headers.ts` is
the CSP and the other security headers, exactly as strict as today's pages: a task that needs more
widens it there (D-059); HSTS covers every subdomain (D-074). The sign-in and app routes, and
`/@username` (`NONCE_ROUTES` there) get a nonce per response in place of `'unsafe-inline'`, from `src/proxy.ts`,
and render per request; a new signed-in place joins that list (D-541). `src/lib/storage-origins.ts` says
where photos live by `APP_ENV`, each bucket by its path, for the CSP (T-4.6).
`src/lib/firebase.ts` is the only code that touches the Firebase SDK (ESLint enforces it), loaded
on demand by a Firebase build's `/login`;
`src/lib/firebase-config.ts` holds the public web config by `APP_ENV`, staging and production only,
so local and ci builds can't reach Firebase (D-085). `src/components/ui/` holds the shared primitives (T-1.19),
each with a vitest test beside it; `/dev/ui` shows them all under `next dev` and 404s everywhere
else. Feature components go in `src/components/<feature>/`. A person's profile has one route,
`/people/[id]` (the deck's tap, T-6.5; T-6.8's screen). One conversation is `/chats/[id]`
(T-7.11, `src/components/conversation/`); `src/lib/voice-recorder.ts` is the only MediaRecorder,
and `/dev/voice` records with it under `next dev` alone (P-520's recordings). `web/bench/` holds benchmarks run by
hand, never in `make test`: T-6.5's deck frame rate (`pnpm exec playwright test -c bench`), and
T-8.7's Razorpay CSP against its live Checkout (`-c bench/razorpay-csp.config.ts`). The app's header and bottom nav are
`src/components/shell/AppShell.tsx`, inside `(app)`'s gate and PIN lock (T-5.6): its sizes are the
`--shell-*` tokens and its shape is that one file, which `look.test.ts` holds. Server data (T-1.18):
`src/lib/api.ts` is the only code that calls `fetch`, and `src/lib/upload.ts` the only
`XMLHttpRequest`, the photo PUT with its progress (T-4.6); ESLint enforces both. `api.ts` is
typed from `src/types/api.ts` (GENERATED by `make types` — never edit by hand) and throwing
`ApiError` on any non-2xx; components read it through the TanStack Query hooks in `src/lib/queries/`, with keys from
`keys.ts`. `src/store/session.ts` holds the access token, in memory only. `src/store/store-sheet.ts`
says whether the store sheet is open: the balance pill, "Buy Velas" and any mutation refused with
`INSUFFICIENT_CREDITS` open it (the query client's mutation cache; queries never). **A mutation
that spends or credits Velas sets `meta: { touchesWallet: true }`**, so the balance and history
are asked again when it settles (T-5.5). **And it sends `shown_price`, the price it displayed from `/prices`:**
the API compares it and refuses a different one with `PRICE_CHANGED` (P-56, D-600). The store (T-8.7)
pays by `src/lib/razorpay.ts`, the only code that loads Razorpay's script, on Razorpay builds, and
by a stand-in on local and CI ones (`src/lib/checkout-path.ts`, from `APP_ENV`, D-761). Notifications (T-9.4): **anything that tells a person something goes through
`notifications.service.notify()`**, in the transaction that makes it true. That covers the in-app row and
the push in `push_outbox`, for an active account only. `src/lib/push.ts` is the only code that touches
the service worker and PushManager, and `/sw.js` is generated by `src/lib/push-worker.ts` from
`en.ts` and `notification-view.ts`'s tables (D-859). The socket is `src/lib/ws.ts`, the only `WebSocket` (ESLint enforces
it), mounted under `(app)`'s gate; what its events write into the caches is
`src/lib/queries/realtime.ts`, which never writes a Thread's state, only asks it again (T-7.12,
D-881). Next.js 16 ships its own docs in `web/node_modules/next/dist/docs/` — the
reference for its APIs, which differ from older versions.

## Commands

```
make infra-up    # docker: postgres+postgis, redis, s3 (SeaweedFS, D-086); stamps the dev db as local;
                 # sets the private bucket's CORS rule for the local web (T-4.6)   (make infra-down to stop)
make infra-reset # stop the stack and DROP all data volumes (clean database)
make dev         # infra + api + worker + web on 127.0.0.1
make worker      # ARQ worker only: moderate_photo, delete_files, verify_selfie, match_photo,
                 # blur_photo (D-543), watermark_album (D-730), export_data, expire_export (polls every 10 s, D-091; a selfie's wake runs it at
                 # once, D-261); two daily crons: log_turnover at 09:00 IST, the year's turnover at
                 # warning from ₹15 lakh (D-483), and erase_accounts at 03:30 IST (D-500); and
                 # once a minute in its own loop, not ARQ's, the Thread's clock: expire_threads and
                 # warn_expiring (T-7.6, D-640); and pushes, never ARQ jobs: push_outbox sent on a
                 # wake (wake:send_push) and in that minute (T-9.4, D-850)
make models      # fetch the face models into api/models, checked by SHA-256 (D-088; needed
                 # where FACEMATCH_PROVIDER=sface, and by the face-match tests)
make seed        # dev data: 20 profiles, test users (local only; a re-run changes nothing, infra-reset starts over)
make test        # api pytest + web vitest   (test-api / test-web for one side)
make lint        # ruff + mypy + eslint + tsc --noEmit + prettier check   (lint-api / lint-web)
make hooks       # install the git hooks (once per clone, from its main checkout; a worktree is refused, P-143)
make migrate     # alembic upgrade head   (make migrate-down to step back)
make migration m="message"   # new blank alembic revision (written by hand)
make migration-auto m="message"   # autogenerated from the models — review the diff
make types       # regenerate web/src/types/api.ts from OpenAPI
make e2e         # Playwright: a production build vs the API, the worker and the local S3 on a
                 # P-55 slot (needs infra-up and models; T-4.9, D-330)
git tag vX.Y.Z <commit> && git push origin vX.Y.Z   # release to production: only a commit
                 # on main that CI passed and staging deployed, both paid plans in place
                 # (D-075, infra/PRODUCTION.md)
```

**Local sign-in: Chrome, at `http://127.0.0.1`, never `localhost`.** Both auth cookies are `Secure`
everywhere, locally too (D-067). **Seen in Chrome on 3 October 2026** (T-3.10, read from Chrome's
own network events): it keeps both over plain `http://127.0.0.1`, sends them back on refresh,
rotates them, and clears them at sign-out. `localhost` fails for a different reason:
`localhost:3000` calling `127.0.0.1:8000` is cross-site, so the `Lax` refresh cookie isn't sent,
and the API's local CORS refuses `localhost` so that mistake fails loudly. **Safari over plain
`http://127.0.0.1` isn't a case to carry:** with D-074's HSTS, production is never plain HTTP, so
no user can reach it. Safari's real case is HTTPS, **unverified until T-3.14's staging check**.
**Firefox: seen on 3 October 2026 in Playwright's own Firefox 155 build**
(T-3.13), not stock Firefox: every E2E journey passed, sign-in, reload, rotation, two tabs and
sign-out among them, so it keeps both `Secure` cookies over plain `http://127.0.0.1`. Until 3
October 2026 this line said "Chrome or Firefox" as fact, from documentation alone.

**Never run `make infra-reset` without telling the founder first, and never while another session
is testing.** Every worktree on this machine shares one Docker stack, so a reset drops every
session's databases mid-run: `velora`, every test run's, the local S3 and Redis. From T-5.1 it is also the
only reset of `velora`: the ledger refuses DELETE and TRUNCATE, so a user with Velas can't be
removed any other way. Tests need no reset: each run has a database and a Redis database of its
own, created empty when it starts (P-55, 06-TESTING), so breaking a constraint to prove a test
touches no other session.

## Golden rules — non-negotiable

1. **One task at a time.** Only work on the task ID you were given from `docs/05-PLAN.md`.
   Never start work that is not in the plan. If something is missing, stop, write it under
   "Proposed tasks" at the bottom of the plan, and ask.
2. **Plan before code.** Restate the task, list every file you will create or change, and wait for
   approval. Then implement. Then run `make lint test`. Then tick the checkbox in the plan.
3. **Stay in scope.** Do not touch files outside the task. No drive-by refactors, renames, or
   "improvements". Note them under "Proposed tasks" instead.
4. **No new dependencies** without asking. If approved, record it in `docs/01-DECISIONS.md`.
5. **Money is sacred.** Every change in Velas goes through `wallet.service.debit()` / `credit()`,
   which lock the wallet row with `SELECT ... FOR UPDATE` inside one transaction and append to
   `ledger_entries`. Never write `wallets.balance` anywhere else. The ledger is append-only.
6. **The server decides.** Prices, balances, expiry, gender, age, permissions — always computed
   server-side. Never trust a value the browser sends for these.
7. **Async only.** asyncpg, httpx, `asyncio.sleep`. Never `requests`, `psycopg2`, `time.sleep`.
   Read time only via `core.clock.now()` — never `datetime.now()`. This governs **Python** code;
   database defaults and triggers use `now()` (transaction start time) by design — don't "fix" them.
8. **Layers.** Router = parse + auth + call service. Service = business rules. Repository = SQL.
   Routers never touch the DB. Repositories never contain business rules.
   The one documented exception: `modules/health/` calls `core.db.check_database()` and
   `core.redis.check_redis()` directly — probes have no business rules and no tables.
9. **Every endpoint** has a Pydantic request + response schema, an auth dependency, a rate limit if
   it can be abused, and at least one test. Errors use the format in `docs/02-ARCHITECTURE.md`.
10. **Types follow the API.** Any change to a response schema → `make types` in the same commit.
11. **Migrations** are one change each, reversible, and never edited after they are merged.
12. **Nothing is hard-deleted** that moderation may need: messages, reports, ledger, payments.
    Clearing a chat is one-sided and only hides it for that user.
13. **Secrets** live in environment variables only. Nothing secret in the web bundle.
    `NEXT_PUBLIC_*` means public.
14. **Frontend:** server data only through TanStack Query hooks in `src/lib/queries/`.
    No `fetch` inside components. No hex colours outside `tokens.css`.
    Every screen handles loading, empty, and error states.
15. **Privacy:** re-encode every uploaded image server-side (strips EXIF/GPS). Never log phone
    numbers, OTPs, tokens, or message bodies.
16. **Environment gates are allowlists, never blacklists.** A gate names the environments where
    something IS served or allowed (`ENV == "local"`), never the ones where it isn't
    (`ENV != "production"`). A blacklist fails open the moment a new environment name exists.
17. **The brand and the product nouns are separate, and never substitute for each other.**
    Velora is the company name and may still change (D-015); code reads it from `APP_NAME`.
    Thread and Knot are product nouns and never change with the brand. A future rename touches
    the brand only — never a find-replace across the docs. The one deliberate exception is
    **Vela**, the unit of paid balance (D-049): it derives from the brand and is renamed with it,
    in copy and prose only, never in identifiers.

## Landing: the push asks the checks itself

A push that moves `main` is refused unless `make lint` and `make test` both passed on that exact
commit's tree, in that checkout, and CI passed for it on the branch it ran on, which must be pushed
first (`scripts/push-gate`, the pre-push hook `make hooks` installs; `make lint` and `make test`
mark a clean tree when they pass, `scripts/mark-checked`). So a gate whose exit code a pipe
swallowed can't land anything. `main`'s own run then vouches from that branch run (P-282, D-410):
one short job, still a green run of the SHA for the deploy and the gates; nothing vouching runs
the full CI there, and e2e runs only when a changed path is outside the docs allowlist.
**Why (4 October 2026):** two sessions in one night landed past a
red `make test` hidden by `| grep` and `| tail -1`. Never `git push --no-verify` to `main`; /done's
manual path skips only the CI half, with `VELORA_PUSH_GATE_MANUAL_PATH=1`.

**Shell traps this project has hit.** The Bash tool runs zsh on the founder's Mac.
1. **A pipe hides an exit code:** `make test | tail -1` reports `tail`'s. Read a check's status on
   its own; the landing guard above exists for this (4 October 2026).
2. **zsh doesn't word-split an unquoted `$var`:** a loop or flag list built from one reaches the
   command as a single argument and comes back empty, silently. Run such checks under `bash -c`
   or with arrays (2 October 2026).
3. **An action placed after its check runs whatever the check found:** `scan; git push` pushed
   `6764a90` past the scan that should have stopped it. Chain it: `scan && git push` (4 October
   2026).
4. **zsh reads `$var:r…` as a modifier:** `git push origin $SHA:refs/heads/main` sends a mangled
   name and is refused. Write `"${SHA}:refs/heads/main"`, or run under bash. A push refused like
   this is not GitHub misbehaving, and pushing again "to see why" is a landing: diagnose with
   `--dry-run`. T-5.2's first docs push to `main` went up that way, unchained to its ancestor
   check, and ended well only because the commit was the gated one (5 October 2026).
5. **`status` is read-only in zsh:** a wrapper `make lint test; status=$?; …; exit $status`
   typed into the tool dies after make has finished, so the checks' exit code is lost and the
   run reads as failed when it wasn't. Name it `rc`, or run the wrapper under `bash -c`. Repo
   scripts and GitHub's `run` steps are bash and keep `status` (8 October 2026, P-282).

## P- and D-numbers: a block per session

Each session is given a block of ten P-numbers and a block of ten D-numbers in its opening brief,
and numbers its Proposed tasks and decisions only inside them, never outside. A session with no
block asks for one before filing. Numbers are never claimed by scanning branches. P blocks start
at P-100 and D blocks at D-200, each a clear gap above every number held on `main`, any branch or
any worktree when this was written (P-85, D-101). The two pair up: P-100 to P-109 goes with D-200
to D-209, P-110 to P-119 with D-210 to D-219. Numbers a block doesn't use stay unused: a gap in the
list costs nothing. Blocks are assigned outside the repo, in the brief, so there is no race to
resolve. **Why (4 October 2026):** with five sessions filing at once, two items of T-5.6's were
renumbered three times in an hour, each time onto numbers another live branch already held. Every
renumbering risks a stale reference surviving where nobody re-reads. And once a single command
pushed the branch before its scan's result could stop it, so `6764a90` went up carrying numbers
T-4.6's branch held. The process was right and one command's ordering defeated it: a rule that
survives only careful sequencing isn't a rule. D-numbers raced the same way that day: `main` holds
D-097 to D-100 with D-096 left to T-4.6's unlanded branch. At the direction of the advisor (Claude,
in a separate chat), relayed by the founder; extended to D-numbers the same day.

## Naming

- Python: `snake_case` modules and functions, `PascalCase` classes. Tables plural `snake_case`.
- TypeScript: `camelCase` variables, `PascalCase` components, one component per file.
- API paths: `/v1/<plural-noun>`, kebab-case. JSON fields: `snake_case` (matches Pydantic).
- Branches: `t-<task-id>-short-name` e.g. `t-3.2-otp-verify`.
- Commits: Conventional Commits with the task ID — `feat(auth): verify OTP [T-3.2]`.

## Definition of done (every task)

- [ ] Acceptance criteria in the plan are all met
- [ ] Tests written and passing; `make lint test` clean
- [ ] Types regenerated if the API changed
- [ ] No TODOs left without a matching "Proposed task"
- [ ] Checkbox ticked in `docs/05-PLAN.md`
- [ ] One commit (or a small, clean series) referencing the task ID
- [ ] CI green for that exact commit — `/done` fast-forwards `main` only then (D-044)
- [ ] Every check a claim rests on is in the repo: the script, plugin or test. **A fix whose
      mechanism isn't in the repo is not a fix.** P-48 was reported done with its shuffle plugin
      never committed, so "survives a shuffled order" was a claim no later report could re-check.

## Do not build (unless a task says so)

Deferred to after beta: video/voice calls, Vibe Room, native apps, iOS.
Rejected permanently: public ratings or reviews of people, paying to remove a review,
fake or operated profiles, gender self-change after signup.
