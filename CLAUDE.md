# CLAUDE.md — Velora

Read this file fully at the start of every session. It is short on purpose.
The detail lives in `docs/`. When a rule here conflicts with anything else, this file wins.

## What Velora is

A web-first dating app for India. Women use it free. Men buy **credits**.
Every conversation starts as a **Thread** that expires in 24 hours.
If both people tap "Tie the knot", it becomes a **Velora** — permanent and free forever.
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
| Web | Next.js (App Router) + React + TypeScript strict + Tailwind |
| Web data | TanStack Query (server state), Zustand (client state), Zod, React Hook Form |
| Swipe | @use-gesture/react + @react-spring/web |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg, Alembic |
| DB | PostgreSQL 16 + PostGIS + pg_trgm + pgcrypto + citext |
| Cache/queue | Redis + ARQ |
| HTTP out | httpx (async) — never `requests` |
| Storage | Cloudflare R2 via aioboto3, presigned URLs only |
| Hosting | Vercel (web) · Fly.io `bom` (api + worker) · Supabase `ap-south-1` · Upstash |
| Tooling | uv, ruff, mypy, pytest, pnpm, eslint, prettier, vitest, Playwright |

## Repo layout

```
velora/
  CLAUDE.md
  docs/                 plan, contracts, decisions
  .claude/commands/     /task /review /done
  .github/workflows/    CI pipelines
  api/                  FastAPI app
    app/core/           config, db, redis, security, errors, deps
    app/modules/<name>/ router.py service.py repository.py schemas.py models.py
    app/workers/        ARQ tasks + cron
    alembic/            migrations
    tests/              mirrors app/
  web/                  Next.js app — empty until T-1.17 scaffolds into it
  infra/                docker-compose.yml, fly.toml
  Makefile
```

`web/` is deliberately empty: `pnpm create next-app` (T-1.17) needs a clean directory. It creates
`src/app/` (route groups `(marketing)` `(auth)` `(app)` `admin`), `src/components/` (`ui/`
primitives + feature folders), `src/lib/` (api client, ws client, query keys, utils),
`src/types/api.ts` (GENERATED — never edit by hand) and `src/styles/tokens.css` (design tokens —
the only place colours live).

## Commands

```
make infra-up    # docker: postgres+postgis, redis, minio   (make infra-down to stop)
make infra-reset # stop the stack and DROP all data volumes (clean database)
make dev         # infra + api + worker + web
make worker      # ARQ worker only
make seed        # dev data: 20 profiles, test users (refuses in production)
make test        # api pytest + web vitest
make lint        # ruff + mypy + eslint + tsc --noEmit
make migrate     # alembic upgrade head   (make migrate-down to step back)
make migration m="message"   # new alembic revision
make types       # regenerate web/src/types/api.ts from OpenAPI
make e2e         # Playwright
```

## Golden rules — non-negotiable

1. **One task at a time.** Only work on the task ID you were given from `docs/05-PLAN.md`.
   Never start work that is not in the plan. If something is missing, stop, write it under
   "Proposed tasks" at the bottom of the plan, and ask.
2. **Plan before code.** Restate the task, list every file you will create or change, and wait for
   approval. Then implement. Then run `make lint test`. Then tick the checkbox in the plan.
3. **Stay in scope.** Do not touch files outside the task. No drive-by refactors, renames, or
   "improvements". Note them under "Proposed tasks" instead.
4. **No new dependencies** without asking. If approved, record it in `docs/01-DECISIONS.md`.
5. **Money is sacred.** Every credit change goes through `wallet.service.debit()` / `credit()`,
   which lock the wallet row with `SELECT ... FOR UPDATE` inside one transaction and append to
   `ledger_entries`. Never write `wallets.balance` anywhere else. The ledger is append-only.
6. **The server decides.** Prices, balances, expiry, gender, age, permissions — always computed
   server-side. Never trust a value the browser sends for these.
7. **Async only.** asyncpg, httpx, `asyncio.sleep`. Never `requests`, `psycopg2`, `time.sleep`.
   Read time only via `core.clock.now()` — never `datetime.now()`.
8. **Layers.** Router = parse + auth + call service. Service = business rules. Repository = SQL.
   Routers never touch the DB. Repositories never contain business rules.
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

## Do not build (unless a task says so)

Deferred to after beta: video/voice calls, Vibe Room, virtual gifts, native apps, iOS.
Rejected permanently: public ratings or reviews of people, paying to remove a review,
fake or operated profiles, gender self-change after signup.
