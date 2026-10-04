# CLAUDE.md — Velora

Read this file fully at the start of every session. It is short on purpose.
The detail lives in `docs/`. When a rule here conflicts with anything else, this file wins.

## What Velora is

A web-first dating app for India. Women use it free. Men buy **Velas**.
Every conversation starts as a **Thread** that expires in 24 hours.
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
                        storage_keys
    app/modules/<name>/ router.py service.py repository.py schemas.py models.py
    app/workers/        ARQ tasks + cron
    app/tools/          checks run by hand inside a deployed machine (storage_probe, T-4.1)
    alembic/            migrations
    seed/               make seed: dev data, local stack only, never in the image (D-064)
    tests/              mirrors app/ (and seed/)
  web/                  Next.js app (App Router, TypeScript strict, Tailwind v4)
  infra/                docker-compose.yml, fly.api.toml + STAGING.md (staging's runbook),
                        fly.api.production.toml + PRODUCTION.md (production's: released by tag)
  scripts/              ci-gate, release-gate, with-tools, staging-smoke, check-image-no-env, migrate-with-url
  Makefile
```

`web/` is Next.js 16, scaffolded in T-1.17: `src/app/` (route groups `(marketing)` `(auth)`
`(app)` `admin`), `src/styles/tokens.css` (design tokens — the only place colours live; a pre-commit
hook enforces it, with one exception, `src/styles/theme-color.ts`) and `src/i18n/en.ts` (every
user-facing string, read through `t()`, with one exception, `src/app/opengraph-image.alt.txt`, which
Next reads as a file; a test holds it to `en.ts`). `src/lib/site.ts` says where the site lives and
that only production is indexed (T-2.4), from `APP_ENV`, which `next build` refuses unless it is
local, ci, staging or production (`src/lib/build-env.ts`, T-2.6). `src/lib/security-headers.ts` is
the CSP and the other security headers, exactly as strict as today's pages: a task that needs more
widens it there (D-059); HSTS covers every subdomain (D-074). `src/lib/firebase.ts` is the only code
that touches the Firebase SDK (ESLint enforces it), loaded on demand by a Firebase build's `/login`;
`src/lib/firebase-config.ts` holds the public web config by `APP_ENV`, staging and production only,
so local and ci builds can't reach Firebase (D-085). `src/components/ui/` holds the shared primitives (T-1.19),
each with a vitest test beside it; `/dev/ui` shows them all under `next dev` and 404s everywhere
else. Feature components go in `src/components/<feature>/`. The app's header and bottom nav are
`src/components/shell/AppShell.tsx`, inside `(app)`'s gate and PIN lock (T-5.6): its sizes are the
`--shell-*` tokens and its shape is that one file, which `look.test.ts` holds. Server data (T-1.18):
`src/lib/api.ts` is the only code that calls `fetch` (ESLint enforces it), typed from
`src/types/api.ts` (GENERATED by `make types` — never edit by hand) and throwing `ApiError` on any
non-2xx; components read it through the TanStack Query hooks in `src/lib/queries/`, with keys from
`keys.ts`. `src/store/session.ts` holds the access token, in memory only. The WebSocket client
arrives with T-7.12. Next.js 16 ships its own docs in `web/node_modules/next/dist/docs/` — the
reference for its APIs, which differ from older versions.

## Commands

```
make infra-up    # docker: postgres+postgis, redis, s3 (SeaweedFS, D-086); stamps the dev db as local   (make infra-down to stop)
make infra-reset # stop the stack and DROP all data volumes (clean database)
make dev         # infra + api + web on 127.0.0.1 (worker joins with T-4.4)
make worker      # ARQ worker only
make seed        # dev data: 20 profiles, test users (local only; a re-run changes nothing, infra-reset starts over)
make test        # api pytest + web vitest   (test-api / test-web for one side)
make lint        # ruff + mypy + eslint + tsc --noEmit + prettier check   (lint-api / lint-web)
make hooks       # install the git pre-commit hooks (once per clone)
make migrate     # alembic upgrade head   (make migrate-down to step back)
make migration m="message"   # new blank alembic revision (written by hand)
make migration-auto m="message"   # autogenerated from the models — review the diff
make types       # regenerate web/src/types/api.ts from OpenAPI
make e2e         # Playwright: a production build vs the API on a P-55 slot (needs infra-up)
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

## P-numbers: a block per session

Each session is given a block of ten P-numbers in its opening brief, and numbers its Proposed tasks
only inside that block, never outside it. A session with no block asks for one before filing.
Numbers are never claimed by scanning branches. Blocks start at P-100, a clear gap above every
number held on `main` or any branch when this was written (P-85). Numbers a block doesn't use stay
unused: a gap in the list costs nothing. Blocks are assigned outside the repo, in the brief, so
there is no race to resolve. **Why (4 October 2026):** with five sessions filing at once, two items
of T-5.6's were renumbered three times in an hour, each time onto numbers another live branch
already held. Every renumbering risks a stale reference surviving where nobody re-reads. And once
a single command pushed the branch before its scan's result could stop it, so `6764a90` went up
carrying numbers T-4.6's branch held. The process was right and one command's ordering defeated
it: a rule that survives only careful sequencing isn't a rule. At the direction of the advisor
(Claude, in a separate chat), relayed by the founder.

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
