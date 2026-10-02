# 05 · Build plan

The only list of what gets built, in the order it gets built. Nothing is built that isn't here.

## How to use this with Claude Code

1. Pick the **first unticked task** whose "Needs" are all ticked.
2. In Claude Code run: `/task T-3.2` (see `.claude/commands/task.md`).
3. Claude restates the task and lists files. **Read it. Approve or correct.** Then it builds.
4. Run `/review` — it checks the work against the task and `07-CHECKLISTS.md`.
5. Run `/done T-3.2` — ticks the box, commits with the task ID.
6. One task per session is ideal. Start a fresh session for the next one.

If Claude discovers work that isn't planned, it goes under **Proposed tasks** at the bottom —
never done silently.

**Task format:** Needs → Steps → Done when → Commit.
**Legend:** `[ ]` todo · `[x]` done · `[~]` in progress · `[-]` dropped (say why).

---

# Phase 0 — Founder tasks (no code, run in parallel)

- [ ] **P-0.1** Trademark search for the name on the IP India public search. Record result in D-015.
  **Partly done:** the founder searched the public web on 1 October 2026 (findings in D-015).
  **Still owed:** a class-specific search of the Indian trademark registry for dating services and
  software (Nice classes 45, 9 and 42, as Claude mapped them). D-015 was closed and the domain
  bought (P-0.3) before it, so a conflict found here means a new name and a new domain.
- [ ] **P-0.2** Register company (OPC recommended) → PAN, GST, current account. Then fill the missing facts in `web/src/lib/legal.ts` (D-053), and change Terms' "Who we are" to name the company directly instead of pointing to the contact page: Terms should name the entity it binds.
- [ ] **P-0.3** Buy the domain (D-015 says why this one). Move its nameservers to Cloudflare. Then set up the support and Grievance Officer mailboxes: their addresses are the `supportEmail` and `grievanceOfficerEmail` facts in `web/src/lib/legal.ts`, and production can't build without them (D-053). Put each address there once it has received and sent a test message, and in the same change add Zoho to `/privacy` (`web/src/i18n/en.ts`) in both places: the list of who handles user data, since from then on it holds every support and grievance email, and "Where your data is", which lists what stays in India (D-048): that mail does, in Zoho's India data centre.
  **The domain is done:** `veloraapp.co.in`, registered 2 October 2026 with Hostinger, expiring
  2 October 2027. Claude read both dates and the registrar from the public WHOIS the same day.
  WHOIS privacy and auto-renewal are on and the registrant email is verified, per the founder.
  Web at the apex, API at `api.veloraapp.co.in` (T-2.6).
  **DNS goes to Cloudflare** (founder, 2 October 2026): T-4.1's R2 custom domain needs the zone
  there, and P-33's staging records go there too.
  **The mailboxes are on Zoho Mail's free tier** (founder, 2 October 2026; five users, one
  domain): `support@veloraapp.co.in` and `grievance@veloraapp.co.in`. Zoho sends as well as
  receives, so grievance acknowledgements go out from the grievance address. **Sign up on Zoho's
  India data centre (`zoho.in`):** it is chosen once and hard to move. The MX records point at
  Zoho; add its SPF and DKIM records and a DMARC record too, or those replies land in spam.
  **Rejected: Cloudflare Email Routing.** It's free but only forwards, so replies would go out from
  a personal Gmail address, which undercuts the Grievance Officer section (D-052).
  **Order:** nameservers first, then the mailboxes, then P-33.
  **Nameservers moved, 2 October 2026:** the `.in` registry delegated the domain to Cloudflare
  (`aaron` and `lilyana.ns.cloudflare.com`) by 14:58 IST, read from the registry by Claude. Both
  answered for the zone, with Hostinger's parking A and MX records gone; there was no DNSSEC to
  switch off. P-33 started from there.
  **Still to do:** the mailboxes, which T-2.6 waits on.
- [ ] **P-0.4** DLT (needed only to move off Firebase later — start it anyway, it is slow): entity → header → OTP template `{#var#} is your Velora verification code. Valid for 5 minutes. Do not share it.`
- [ ] **P-0.5** MSG91 account; link DLT IDs; send one test SMS to yourself.
- [ ] **P-0.12** Firebase: project, Phone provider on, App Check + reCAPTCHA Enterprise enforced, authorised domains, daily SMS quota cap, billing alert. Confirm the **real per-SMS price for IN** in the billing console and write it into D-035.
- [x] **P-0.6** Create accounts: GitHub, Supabase (Mumbai), Upstash, Cloudflare (R2 on), Fly.io (paid plan for `bom`), Vercel, Sentry, Sightengine, AWS (Rekognition, `ap-south-1`).
  **Ticked with three still to set up**, none needed before Sprint 4: Sightengine (T-4.4), AWS for
  Rekognition (T-4.5 — signed up, but its payment method failed verification) and Sentry (T-9.12).
  Each is on its task's **Needs** line, which `/task` checks before planning.
- [ ] **P-0.7** Review our own legal text before real users arrive — no lawyer at this stage (the founder's call, 1 October 2026). Check Terms, Privacy, Refunds and Contact (T-2.2) against the decisions they cite and against what the product actually does at go-live; against the IT Rules 2021 (Grievance Officer, timelines) and the DPDP Act (notice, consent, rights — section 16 and Rule 15 take effect on 13 May 2027; check for any restricted-country notification); and gender-based pricing. Start with the law-and-courts text (D-052), the weakest part we wrote ourselves. Look closely, not in passing, at the under-18 section: it keeps a hashed phone number of someone just identified as a minor (D-009). The mechanism and saying so openly are right, but minors plus retention is the most scrutinised combination there is. Privacy has no section yet on what happens to people's data if the app shuts down or is sold; add one when there is something honest to say. Gates T-9.15, not the production build (D-053).
- [ ] **P-0.8** After T-2.2 is live: apply to Razorpay and Cashfree. Before applying, confirm each gateway's exact refund and cancellation-policy requirement against `/refunds` (D-050).
- [ ] **P-0.9** Buy a ₹10–12k Android phone for testing.
- [ ] **P-0.10** 15 conversations with women aged 22–28 in the launch city about why they left their last dating app. Write findings in `docs/research.md`.
- [ ] **P-0.11** Decide D-013 (city), D-014 (theme), confirm D-005 (packs).

---

# Sprint 1 — Foundation (weeks 1–2)

### T-1.1 · Monorepo skeleton
- [x] **Needs:** —
- [x] Create folders exactly as in `CLAUDE.md` "Repo layout". Empty folders get a `.gitkeep`.
- [x] Root files: `.gitignore` (Python, Node, `.env*` except `.env.example`, `.DS_Store`), `.editorconfig`, `README.md` (one paragraph + `make dev`), `Makefile` with the targets from `CLAUDE.md` (stubs that `echo "not yet"` are fine).
- [x] Copy `CLAUDE.md`, `docs/`, `.claude/commands/` into the repo.
- [x] **Done when:** `git status` shows the tree; `make` lists targets.
- [x] **Commit:** `chore(repo): monorepo skeleton [T-1.1]`

### T-1.2 · Local infrastructure
- [x] **Needs:** T-1.1
- [x] `infra/docker-compose.yml`: `postgis/postgis:16-3.4` (db `velora`, plus `velora_test` via init script), `redis:7-alpine`, `minio/minio` (S3-compatible stand-in for R2, buckets `velora-public`, `velora-private` created by an init container).
- [x] Healthchecks on all three; named volumes; ports 5432, 6379, 9000/9001.
- [x] `make infra-up` / `make infra-down`.
- [x] **Done when:** `make infra-up` → all healthy; `psql` connects; MinIO console shows both buckets.
- [x] **Commit:** `chore(infra): docker compose for postgres, redis, minio [T-1.2]`

### T-1.3 · API skeleton
- [x] **Needs:** T-1.2
- [x] `uv init api`; add runtime deps from `02-ARCHITECTURE.md` stack; dev deps pytest, pytest-asyncio, httpx, polyfactory, faker, ruff, mypy.
- [x] `app/core/config.py` — `Settings` with every var in `02-ARCHITECTURE.md §11`; fail fast on missing required vars; `.env.example`.
- [x] `app/main.py` — app factory `create_app()`; CORS from settings; request-id middleware (header `X-Request-ID`, generated if missing); structlog JSON logging with request id; orjson responses.
- [x] `app/core/clock.py` — `now()` returning timezone-aware UTC; the **only** way app code reads the time (tests freeze/advance it). `today_ist()` helper.
- [x] `app/core/errors.py` — `AppError(code, message, status, details)`; handlers for `AppError`, `RequestValidationError` (→ `VALIDATION_ERROR`), and unhandled (→ 500 `INTERNAL`, logged, Sentry).
- [x] **Done when:** `uvicorn app.main:app` starts; unknown route returns the error envelope.
- [x] **Commit:** `feat(api): app factory, config, logging, error envelope [T-1.3]`

### T-1.4 · Health endpoints
- [x] **Needs:** T-1.3
- [x] `app/core/db.py` async engine + `get_session` dependency; `app/core/redis.py` client.
- [x] `GET /healthz` → 200 always. `GET /readyz` → checks `SELECT 1` and Redis `PING`, 503 if either fails.
- [x] **Done when:** `/readyz` is 200 with infra up and 503 with Redis stopped.
- [x] **Commit:** `feat(api): health and readiness [T-1.4]`

### T-1.5 · Test harness
- [x] **Needs:** T-1.4
- [x] `pytest.ini`/`pyproject` config: asyncio mode auto, test DB `velora_test`, `@pytest.mark.critical` registered.
- [x] Fixtures in `tests/conftest.py`: per-test transaction rolled back; `client` (httpx AsyncClient on the app, sharing the test's transaction); `clock` (freeze/advance, always unfrozen). Moved to the tasks that build what they need: migrating once per session → T-1.7, `fake_providers` → T-1.21, `make_user` → T-3.1.
- [x] One sample test for `/healthz`.
- [x] **Done when:** `make test` runs green in < 10 s.
- [x] **Commit:** `test(api): pytest harness and fixtures [T-1.5]`

### T-1.6 · Lint, types, hooks
- [x] **Needs:** T-1.3
- [x] ruff (lint + format) config; mypy with `strict = true` for `app/` (allow untyped for alembic).
- [x] `.pre-commit-config.yaml`: ruff, ruff-format, mypy, gitleaks, end-of-file-fixer, prettier + eslint for `web/`.
- [x] **Done when:** `make lint` passes; a fake secret in a file is blocked by gitleaks.
- [x] **Commit:** `chore: ruff, mypy, pre-commit, gitleaks [T-1.6]`

### T-1.7 · Alembic
- [x] **Needs:** T-1.4
- [x] `alembic init -t async`; `env.py` reads `DATABASE_URL`; `target_metadata` from a shared `Base` with naming convention (`pk_`, `fk_`, `uq_`, `ix_`, `ck_`).
- [x] `make migrate`, `make migration m="…"`, `make migrate-down`.
- [x] Test harness: `test_engine` in `tests/conftest.py` migrates `velora_test` to head once per session (moved from T-1.5).
- [x] mypy: `api/alembic/` added to `[tool.mypy] files` and kept **strict** — the async `env.py` and generated revisions are already typed. A hand-written migration that genuinely needs loosening uses a per-file `# mypy: disallow-untyped-defs=False`.
- [x] **Done when:** an empty revision upgrades and downgrades cleanly.
- [x] **Commit:** `chore(db): alembic async setup [T-1.7]`

### T-1.8 → T-1.13 · Schema migrations
One migration per task, each with a working `downgrade()`. Build exactly `03-SCHEMA.md`.
- [x] **T-1.8** Extensions, all enums, `set_updated_at()` trigger function. — `feat(db): extensions and enums [T-1.8]`
- [x] **T-1.9** Identity + profile: `users`, `sessions`, `banned_identities`, `profiles`, `areas`, `interests`, `profile_interests`, `photos`, `verifications`, plus trigger making `users.gender`/`users.dob` immutable once non-null. — `[T-1.9]`
- [x] **T-1.10** Discovery + conversations: `swipes`, `profile_views`, `liked_you_reveals`, `matches`, `threads`, `messages`, `message_unlocks`, `thread_clears`. — `[T-1.10]`
- [x] **T-1.11** Album, kudos, safety: `album_requests`, `kudos`, `gifts`, `gift_sends`, `blocks`, `reports`, `fraud_scores`, `fraud_events`. — `[T-1.11]`
- [x] **T-1.12** Money: `wallets`, `ledger_entries` (+ no-update/delete trigger), `action_prices`, `credit_packs`, `payments`, `refund_requests`, `referrals`. — `[T-1.12]`
- [x] **T-1.13** Notifications + ops: `push_subscriptions`, `notification_prefs`, `notifications`, `audit_log`, `app_config`, `waitlist`. — `[T-1.13]`
- **For T-1.10 → T-1.13 (from T-1.9):** autogenerate drops `create_type=False` on every enum column,
  and the line wrapping varies, so **parse the migration file to verify it — never eyeball it.**
- [x] **Done when (each):** `make migrate && make migrate-down && make migrate` succeeds; SQLAlchemy models match.

### T-1.14 · Reference data migration
- [x] **Needs:** T-1.13
- [x] Data migration inserting `interests` (24), `gifts` (6, D-016), `action_prices` (D-004), `credit_packs` (D-005: 25/₹1,500 · 50/₹2,500 · 75/₹3,375 · 100/₹4,000, variant A; variant B entry pack ₹999/25 for the beta test), `app_config` seeds, `areas` for the launch city.
- [x] **Done when:** counts match; re-running is a no-op (`ON CONFLICT DO NOTHING`).
- [x] **Commit:** `feat(db): reference data [T-1.14]`

### T-1.15 · Dev seed
- [ ] **Needs:** T-1.14, T-3.1
- **Why T-3.1:** phone numbers are hashed and encrypted with its `core/security.py`, so the seeded test accounts are the ones login finds. Parts that need later code live in those tasks: placeholder photos in T-4.4, verification rows in T-4.5, the test man's 60 Velas in T-5.1 (rule 5).
- [ ] `make seed` (local only — refuses unless `ENV` is `local`; an allowlist, so an environment added later can't pass by default): the 20 prototype profiles (`docs/prototype/`, the `P` array), each with the rows signup creates (T-3.3), onboarding done, `is_verified` where the prototype has `v`, and a location at its neighbourhood's centroid (`area_id`; `city` Bengaluru, `hometown` from `from`); prototype women seek men and men seek women. 3 of the women — the prototype's `likedYou`: Ananya, Meera, Riya — like the test man. A test man (`+91 90000 00001`, `test_man`, seeking women), a test woman (`+91 90000 00002`, `test_woman`, seeking men, verified), and a moderator (`+91 90000 00003`, onboarding not started, so not in discovery).
- [ ] Interests: each profile keeps its 3 prototype tags plus 2 drafted by Claude from its `about` text; Kavya's "Carnatic" (not in the catalogue) is replaced. Intents: the prototype's value mapped — `serious` → Something serious, `longterm` → Long term, `short` → Casual dating, `chat` → Go with the flow — then roughly a third get a 2nd intent and a few a 3rd, fitting their `about`, so D-041's 1–3 and any-overlap filter run on real data. Show the founder all 20 (interests and the intent spread) before `/done`. The data file's note says the additions were drafted by Claude from the prototype's about text and reviewed by the founder.
- [ ] The seed's output never contains a phone number (rule 15).
- [ ] **Done when:** `make seed` twice doesn't duplicate.
- [ ] **Commit:** `chore(dev): seed script [T-1.15]`

### T-1.16 · Schema tests
- [-] **Needs:** T-1.13, T-1.5
- [-] Tests that prove: `wallets.balance` can't go negative *(covered in T-1.12)*; ledger UPDATE/DELETE raises *(covered in T-1.12, TRUNCATE too)*; `threads` rejects `user_low >= user_high` *(covered in T-1.10)*; `users.gender` can't change once set *(covered in T-1.9, `tests/test_schema.py`)*; username regex enforced *(covered in T-1.9)*; unique `(sender_id, client_msg_id)` *(covered in T-1.10)*.
- [-] **Commit:** `test(db): constraint tests [T-1.16]`
- **Dropped:** every constraint above is tested in `tests/test_schema.py` by the task that built it
  (T-1.9 through T-1.12); nothing is left to add. Closed during T-1.14.

### T-1.17 · Web skeleton
- [x] **Needs:** T-1.1
- [x] `pnpm create next-app web` — TypeScript, App Router, Tailwind, ESLint, `src/` dir.
- [x] `tsconfig` strict + `noUncheckedIndexedAccess`; path alias `@/`.
- [x] Route groups: `(marketing)`, `(auth)`, `(app)`, `admin` with placeholder pages.
- [x] `src/styles/tokens.css` from `08-DESIGN.md`; Tailwind theme reads the CSS variables.
- [x] `src/i18n/en.ts` string dictionary + `t()` helper.
- [x] Verify the prettier and eslint pre-commit hooks from T-1.6 run on `web/` files; prettier must be a `web/` devDependency (create-next-app adds ESLint, not Prettier).
- [x] **Done when:** `pnpm dev` shows placeholders; `pnpm lint && pnpm tsc --noEmit` clean.
- [x] **Commit:** `feat(web): next.js skeleton with tokens [T-1.17]`

### T-1.18 · Web data layer
- [x] **Needs:** T-1.17, T-1.3
- [x] `make types` → `openapi-typescript $API/openapi.json -o web/src/types/api.ts`.
- [x] `src/lib/api.ts` — typed fetch wrapper: base URL, JSON, attaches access token, parses the error envelope into `ApiError {code, message, details, status}`.
- [x] `QueryClientProvider` in root layout; `src/lib/queries/keys.ts` (query key factory).
- [x] Zustand `src/store/session.ts` (access token in memory, user id).
- [x] ESLint enforces rule 14's "no `fetch` inside components": `fetch` is banned in `web/src`
  except `src/lib/`, so server data only reaches components through the api client and query
  hooks. Deferred from T-1.17 to here, where `src/lib/` is created — a rule goes in when the thing
  it protects exists.
- [x] **Done when:** a dev page calls `/healthz` via a query hook and renders the result.
- [x] **Commit:** `feat(web): api client, query setup, type generation [T-1.18]`

### T-1.19 · UI primitives
- [x] **Needs:** T-1.17
- [x] From the prototype, in `src/components/ui/`: `Button` (primary/ghost/danger, sm/md, loading), `Chip`, `Sheet` (bottom on mobile, centred on desktop, focus trap, Esc closes), `Field`, `TextArea` (counter), `Toast` + `useToast`, `Icon` (lucide-react), `Avatar`, `Spinner`, `EmptyState`, `ErrorState`, `Toggle`, `Skeleton`.
- [x] `/dev/ui` page (dev only) showing every primitive in every state.
- [x] Vitest + Testing Library; one test per primitive (renders, interaction, a11y role).
- [x] **Commit:** `feat(web): ui primitives [T-1.19]`

### T-1.20 · CI
- [x] **Needs:** T-1.5, T-1.6, T-1.19
- [x] GitHub Actions `ci.yml`: job `api` (postgis + redis services, `uv sync`, migrate, ruff, mypy, pytest); job `web` (pnpm install, lint, tsc, vitest, `next build`). Runs on every push, to any branch. Nothing is marked "required": there are no pull requests to attach required checks to. CI is binding anyway, through `/done` (next step, D-044).
- [x] Secrets scan in CI (from P-09): a `gitleaks git` step in the `api` job. The pre-commit hook
  only protects clones that ran `make hooks`, and `git commit --no-verify` skips it — without this,
  nothing server-side enforces checklist E's "no secrets in repo".
- [x] Hooks work from GUI git clients (from P-10): the ruff and mypy hooks resolve `uv`, and the
  prettier and eslint hooks `pnpm` (live since T-1.17), without relying on the shell's `PATH` (an
  absolute path, or a wrapper that locates it). VS Code's Source Control panel runs hooks without
  the shell profile, so either may be missing and every commit fails. Test a commit from VS Code.
- [x] Types are fresh (from T-1.18, rule 10): CI runs `make types` and fails if
  `web/src/types/api.ts` changes. `make types` works offline (D-043), so this needs no running
  API. Without it, a response schema can change with stale web types and only a reviewer notices.
- [x] `/done` gate (D-044): `/done` pushes the branch, runs `scripts/ci-gate`, and fast-forwards
  `main` only when CI passed for that exact commit. The gate finds the run by the commit's SHA,
  never "the latest run on the branch", and fails closed: no run within 3 minutes, no finish
  within 20, a cancelled or failed run, or GitHub not answering all stop `/done` with a message.
  `done.md` documents a manual path for GitHub being unreachable (exit 4) — never for a red run
  or an error GitHub answered (exit 5). `scripts/ci-gate-test` proves each case against a fake
  `gh`, and runs in CI.
- [x] **Commit:** `ci: api and web pipelines [T-1.20]`

### T-1.21 · Provider adapters
- [x] **Needs:** T-1.3
- [x] `app/core/providers/`: `SmsProvider`, `PaymentsProvider`, `ModerationProvider`, `FaceMatchProvider`, `PushProvider`, `StorageProvider` as `Protocol`s. Each has `Fake…` (in-memory, records calls; fake SMS logs the OTP to console in local only) and a real implementation stub raising `NotImplementedError`. Selection by env var.
- [x] `fake_providers` fixture in `tests/conftest.py` overriding every provider with its fake (moved from T-1.5).
- [x] **Done when:** tests can assert "an SMS was sent to X" via the fake.
- [x] **Commit:** `feat(api): provider interfaces with fakes [T-1.21]`

### T-1.22 · Staging deploy
- [x] **Needs:** T-1.4, T-1.17, P-0.6
- [x] `api/.dockerignore` excluding `.env*`, before the first image is built (from P-32). A `.env`
  in the image is a secrets leak: it bakes the JWT secret, the database password and every
  provider key into an image pushed to Fly's registry, and Docker keeps deleted files in earlier
  layers, so once pushed every one of them must be rotated. It would also set `ENV=local` and
  switch off D-045. CI checks that the built image has no `.env` in any layer.
- [x] `api/Dockerfile` (multi-stage, uv, non-root, base images pinned by digest). uvicorn with 2
  workers, not gunicorn: uvicorn restarts dead workers itself, and the image checks settings once
  before any worker starts, so a configuration error stops the container instead of crash-looping.
  `infra/fly.api.toml`, region `sin` (D-048: Fly retired `bom`), health check `/readyz`. No release command: migrations run
  from CI as the owner (D-046). The worker's Fly app moved to T-4.4, which builds the worker.
- [ ] Supabase staging project (enable PostGIS, pg_trgm, citext); Upstash staging DB; R2 staging buckets.
  All by hand, from `infra/STAGING.md`. **Open, for R2 alone (1 October 2026):** Supabase (Mumbai,
  migrated to head) and Upstash (Mumbai) are serving staging (deploy run 36845884410). R2 isn't
  enabled on the Cloudflare account yet, which only its dashboard can do, so there are no buckets.
  **Moved:** R2 is now on T-4.1's Needs line, the first task that uses the buckets — tick this with
  T-4.1.
- [x] Supabase's Data API off, and the app-role migration strips `anon` and `authenticated` of every
  privilege on our tables. Left on, it serves every table in `public` over REST to anyone with the
  project's anon key. The runbook ends with a SQL check that those roles hold nothing.
  Checked 1 October 2026: that query returned no rows, and every row of the app-role check was
  true. The Data API was never enabled, per the founder at setup.
- [x] Database pool sized for 2 workers (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`): each worker opens its
  own pool, so staging's budget is 2 × (5 + 2) = 14 connections, recorded in `infra/STAGING.md`.
- [x] Note: Supabase manages extensions from its dashboard. T-1.8's migration uses `create extension if not exists`, so upgrade is a no-op there — but its `downgrade()` drops them, so never downgrade a Supabase database to base.
- [x] Least-privilege database role (from P-18): the API and worker connect as a role that doesn't
  own the tables and can't `ALTER` them or set `session_replication_role`; migrations run as the
  owner, from CI (D-046), so the owner's credentials are never on Fly beside the app. The guards on `ledger_entries`, `payments` and `audit_log` are
  triggers — they stop application bugs, but an owner or superuser connection bypasses them with
  `SET session_replication_role = replica` or `ALTER TABLE … DISABLE TRIGGER`.
- [x] Tests, connected as that role: the writes each guard refuses are refused — UPDATE, DELETE and
  TRUNCATE on `ledger_entries` and `audit_log`; DELETE and TRUNCATE on `payments`, whose UPDATE
  stays allowed because a payment's status moves — and both bypasses are denied.
- [x] A separate Vercel project `velora-staging`, with no Git connection, deployed with `--prod` from
  `deploy.yml`: one stable URL, which the API's `CORS_ORIGINS` names. Its URL is
  `https://velora-staging-black.vercel.app`: `velora-staging.vercel.app` is another company's site
  (D-015, `infra/STAGING.md`). Deployed by run 36845884410; no Git connection, checked through
  Vercel's API on 1 October 2026.
- [x] Serve `/openapi.json` and `/docs` only when `ENV == "local"` (from P-31). `create_app()`
  serves them everywhere but production — a blacklist — so public staging would publish the full
  schema of the wallet, payment and admin routes. Nothing needs them outside local: `make types`
  reads the schema offline (D-043). Test staging and production: 404, and no schema in the body.
- [x] `/admin` returns 404 outside `next dev` (from P-30), with the same allowlist as `/dev/ui`
  and a test; check the staging 404's body, not just its status. Until T-9.5 there is no admin
  page to protect, only a placeholder that shouldn't be public.
- [x] GitHub Actions `deploy.yml`: on push to `main` → deploy staging API + worker, but only a commit whose CI passed — a second check after `/done`'s gate (D-044). Vercel deploys web itself from Git, which ignores CI by default: make its web deploys wait for CI too (e.g. deploy from `deploy.yml` with the Vercel CLI), or record why not.
  Also runnable by hand for any commit whose CI passed. GitHub runs `workflow_run` and
  `workflow_dispatch` workflows only from the default branch, so the first deploy follows the merge.
- [x] After every deploy, `scripts/staging-smoke` checks staging from the outside, bodies included.
- [x] **Done when:** staging web loads and staging `/readyz` is 200. **Proved by deploy run
  36845884410** (commit `c57634f`), whose smoke job passed every check against
  `https://velora-staging-black.vercel.app`, including that the web is our build calling this API.
  Run 36843892361 also went green but proves nothing: its smoke job checked another company's site.
- [x] **Commit:** `ci: staging deploy [T-1.22]`

---

# Sprint 2 — Public site (week 3)

### T-2.1 · Landing page
- [x] **Needs:** T-1.19
- [x] `(marketing)/page.tsx` from the prototype: header, hero, three feature cards, footer links. Server-rendered, with no page-level client JS. The waitlist box moved to T-2.3, with its form.
- [x] **Checklist A exception, on purpose:** the landing copy writes `app_config.thread_hours` out
  ("Threads last a day", and "24-hour" twice) instead of reading the setting. 03-SCHEMA's
  never-hardcode rule is about behaviour: the API must never hardcode the number when it computes
  expiry. Landing copy is a promise, not a computation, and making the page dynamic to render one
  number would cost the static prerender the Lighthouse target rests on. Comments in
  `web/src/i18n/en.ts`, 03-SCHEMA §8 and the seed test (`api/tests/test_reference_data.py`) say to
  change the copy with the setting. The seed migration is merged, so it can't carry one (rule 11).
- [x] **Done when:** Lighthouse mobile ≥ 90 performance, 100 accessibility on staging.
  **Measured 1 October 2026 by Claude**, on `https://velora-staging-black.vercel.app/` serving
  `c10e589` (deploy run 36892558024, smoke passed): Lighthouse 13.5.0, mobile, simulated
  throttling, three runs. Performance 98, 99 and 100; accessibility 100 in all three, with every
  weighted audit passing. The LCP element was the hero's paragraph, so it measured this page. Run
  locally with Chrome, because PageSpeed Insights' shared keyless quota was spent (HTTP 429).
- [x] **Commit:** `feat(web): landing page [T-2.1]`

### T-2.2 · Legal pages
- [x] **Needs:** T-2.1
- [x] `/terms`, `/privacy`, `/refunds`, `/contact` as TSX pages, written in plain language from our own decisions — no lawyer, no copied policy. Contact shows the company name, registered office, support email and **Grievance Officer name + email** (IT Rules). A fact we don't have yet shows as "To be confirmed", and production can't build while any is missing (D-053).
- [x] Footer links on every marketing page; the footer's city is Phagwara (D-013).
- [x] **Checklist A exception, on purpose:** the pages write out two `app_config` values in words — `thread_hours` ("lasts a day") and `mask_first_n_messages` ("first 20 messages") — for T-2.1's reason: copy is a promise, not a computation. Comments in `en.ts`, 03-SCHEMA §8 and the seed test say to change the copy with the setting.
- [x] **Done when:** all four reachable, linked, and printable. **Proved on staging, 1 October 2026,**
  by deploy run 36903641112 (commit `1d52ee5`, attempt 2): its smoke job passed every check,
  each legal page returning 200 with its title. Every marketing page's footer links all four
  (checked on `/`, `/terms`, `/privacy`, `/refunds` and `/contact`). Each page, printed from
  staging to PDF, prints the policy alone, on white, sections whole, footer and back link dropped.
  Attempt 1 failed closed: `APP_ENV` had been stored as a Vercel Secret, which `vercel pull`
  writes as `[SENSITIVE]`, and the gate refused it (D-053). It is now Config (`infra/STAGING.md`).
- [x] **Commit:** `feat(web): legal pages [T-2.2]`

### T-2.3 · Waitlist
- [x] **Needs:** T-1.13, T-2.1, and **P-33** (slotted before it, so the form is built once, against staging's final addresses)
- [x] API `POST /v1/waitlist {email, city?}` — validate email, citext unique (duplicate → 201 anyway), rate limit 5/min/IP.
- [x] The landing page's waitlist box, from the prototype (moved from T-2.1): heading, text, form
  and success state arrive together, so nothing on the page asks for an email it can't keep. The
  form is the landing page's one client component: add it to `CLIENT_COMPONENTS_ALLOWED` in
  `(marketing)/page.test.tsx`. The prototype's 48 px below the box is off the spacing scale; round
  it per 08-DESIGN §3.
- [x] **Done when, on staging:** joining from `https://staging.veloraapp.co.in` shows "You're on
  the list"; a sixth try within a minute gets `429 RATE_LIMITED` even when every try forges a
  different `Fly-Client-IP` and `X-Forwarded-For`, which proves Fly's proxy overwrites the header
  its docs don't promise to (D-056); and Lighthouse mobile on `/` stays at ≥ 90 performance and
  100 accessibility with the form on the page.
  **Proved on staging, 2 October 2026, by Claude,** on deploy run 37001771137 (commit `1b259d3`,
  smoke passed). Every test row's email is at `example.com`, so ours are told apart from people's.
  - **Joining:** headless Chrome joined from `https://staging.veloraapp.co.in` as
    `t-2.3-done-when-ui@example.com`. `POST /v1/waitlist` answered 201, "You're on the list"
    appeared inside the live region, and the form went away.
  - **The forged header:** six tries over IPv4, each forging a different `Fly-Client-IP`
    (198.51.100.1–6) and `X-Forwarded-For` (203.0.113.1–6), got five 201s, then `429
    RATE_LIMITED`. An unforged try was refused too, so the forged ones had counted against this
    machine's real address. An IPv6 try from the same machine 20 s later was allowed, so clients
    don't share one bucket either. Fly's proxy overwrites a forged `Fly-Client-IP` (D-056).
  - **Lighthouse** 13.5.0, mobile, simulated throttling, local Chrome: performance 90, 100, 100,
    100, and accessibility 100 in all four, with no weighted accessibility audit failing. The 90
    was the first run, with the same 158 KiB of script and the same server response as the rest:
    a cold first measurement, not the form. A fifth run hit a Chrome error page from this
    network's flaky DNS and isn't counted.
- [x] **Commit:** `feat: waitlist [T-2.3]`

### T-2.4 · SEO and sharing
- [ ] **Needs:** T-2.1
- [ ] Metadata API titles/descriptions, OG image (static), `sitemap.xml`, `robots.txt` (disallow `/admin`, `/(app)` routes), favicon + icons.
- [ ] **Commit:** `feat(web): seo basics [T-2.4]`

### T-2.5 · Security headers
- [ ] **Needs:** T-1.17
- [ ] `next.config` headers from `02-ARCHITECTURE.md §12`; CSP in report-only first, then enforce after T-8.7 adds Razorpay.
- [ ] **Done when:** securityheaders.com grade A on staging.
- [ ] **Commit:** `feat(web): security headers [T-2.5]`

### T-2.6 · Production domains
- [ ] **Needs:** P-0.3, T-1.22, and the **legal facts final** (P-0.2, P-0.3) — production can't build the legal pages while any is missing (D-053)
- [ ] `veloraapp.co.in` → Vercel prod; `api.veloraapp.co.in` → Fly prod app; SSL issued. Prod DB/Redis/R2 created but empty.
- [ ] **Done when:** `https://veloraapp.co.in` shows the landing page; `https://api.veloraapp.co.in/healthz` is 200. → **Unblocks P-0.8.**
- [ ] **Commit:** `chore(infra): production domains [T-2.6]`

---

# Sprint 3 — Auth and onboarding (weeks 4–5)

### T-3.1 · Security primitives
- [ ] **Needs:** T-1.21
- [ ] `core/security.py`: `normalize_phone()` (phonenumbers, India only, E.164), `hash_phone()` (SHA-256 + pepper), `encrypt_phone()`/`decrypt_phone()`, `make_access_token(user_id, role)` (15 min), `decode_access_token()`, `new_refresh_token()` (32 random bytes, urlsafe), `hash_token()`, `hash_pin()`/`verify_pin()` (argon2), `new_csrf()`.
- [ ] Unit tests for each, including invalid/expired JWT and non-Indian numbers.
- [ ] `make_user(gender=…, onboarded=True, credits=0, verified=False)` factory in `tests/conftest.py` returning `(user, access_token)` (moved from T-1.5; needs `users` from T-1.9).
- [ ] **Commit:** `feat(auth): security primitives [T-3.1]`

### T-3.2 · OTP send
- [ ] **Needs:** T-3.1
- [ ] This is Path B (MSG91, used after DLT approval). Build it behind `AUTH_PHONE_PROVIDER`; the launch path is T-3.14.
- [ ] `POST /v1/auth/otp/send`. Normalise phone → reject if in `banned_identities` (respond generic, don't reveal). Rate limits per `02-ARCHITECTURE.md §12`. Generate 4-digit code, store `otp:{phone_hash}` = argon2(code) + attempts 0, TTL 300 s; resend lock 45 s. Send via `SmsProvider`.
- [ ] Tests: happy path; resend too soon → `RATE_LIMITED`; 6th send in an hour → `RATE_LIMITED`; banned → 200 but no SMS sent.
- [ ] **Commit:** `feat(auth): send otp [T-3.2]`

### T-3.3 · OTP verify and signup
- [ ] **Needs:** T-3.2, and the **cookie scope settled**, because this task sets the first cookies and its tests would lock in a wrong scope. Settled 2 October 2026: the refresh cookie is host-only on the API (D-054), and both cookies are named for their environment (D-055)
- [ ] `POST /v1/auth/otp/verify`. Wrong code → attempts+1, `OTP_INVALID` with attempts left; 5th wrong → delete key, `OTP_TOO_MANY`. Correct → delete key.
- [ ] Find user by `phone_hash`, or create in **one transaction**: `users` (+ referral code), `profiles`, `wallets` (0), `notification_prefs`.
- [ ] Create session (family), set the refresh cookie (`refresh_prod`, `refresh_staging`, `refresh_local`; `HttpOnly; Secure; SameSite=Lax; Path=/v1/auth`, no `Domain`: host-only on the API, D-054), set the readable CSRF cookie (`csrf_prod`, `csrf_staging`, `csrf_local`), scoped to `COOKIE_DOMAIN`, return `{access_token, user: Me}`. Both names come from `ENV` with no fallback (D-055).
- [ ] Set staging's `COOKIE_DOMAIN` to `staging.veloraapp.co.in` in `infra/fly.api.toml` (P-33 leaves it unset).
- [ ] Refuse if user status `banned`.
- [ ] Tests: new user creates all 4 rows; existing user doesn't duplicate; banned → `ACCOUNT_BANNED`; the refresh cookie has no `Domain`; both cookies' names follow `ENV`.
- [ ] **Commit:** `feat(auth): verify otp and create account [T-3.3]`

### T-3.4 · Refresh and logout
- [ ] **Needs:** T-3.3, and **P-33** (staging's web and API on one site, or the refresh cookie can't flow there)
- [ ] `POST /v1/auth/refresh`: require `X-CSRF` equal to this environment's CSRF cookie (D-055); look up the `token_hash` of this environment's refresh cookie; if revoked → revoke whole family (reuse attack) → `SESSION_REVOKED`; else rotate (new session, old `revoked_at` + `replaced_by`).
- [ ] `POST /v1/auth/logout`: revoke current session, clear cookies.
- [ ] Tests: rotation works; reusing an old token kills the family; missing CSRF → 401.
- [ ] **Commit:** `feat(auth): refresh rotation and logout [T-3.4]`

### T-3.5 · Current user
- [ ] **Needs:** T-3.4
- [ ] `deps.current_user` (decode JWT, load user, reject frozen/banned/deleted), `deps.onboarded_user` (also require `done`), `deps.require_role()`.
- [ ] `GET /v1/me` → `Me` schema. Throttled `last_active_at` update (Redis key, once per 60 s).
- [ ] **Commit:** `feat(users): current user and /me [T-3.5]`

### T-3.6 · DOB, gender, seeking
- [ ] **Needs:** T-3.5
- [ ] `POST /me/dob`: compute age in IST; < 18 → add phone hash to `banned_identities`, set status `banned`, revoke sessions, return `UNDERAGE`. Advance step.
- [ ] `POST /me/gender`: only if null → set, advance; else `IMMUTABLE_FIELD`.
- [ ] The database also refuses the change (T-1.9's `users_identity_immutable` trigger) with SQLSTATE `23514` `check_violation`, which SQLAlchemy raises as `IntegrityError`. Map it to `IMMUTABLE_FIELD` by that SQLSTATE — never by the message text, which Postgres can reword.
- [ ] `GET /intents`; `POST /me/seeking {seeking, intent_ids}` — 1 to 3 valid distinct ids (D-041), replace the set in one tx → advance.
- [ ] Steps must happen in order; out-of-order → `ONBOARDING_INCOMPLETE` with the expected step.
- [ ] Tests for each branch, including "17 years 364 days" and "exactly 18 today".
- [ ] **Commit:** `feat(onboarding): dob, gender, seeking [T-3.6]`

### T-3.7 · Name, places, username
- [ ] **Needs:** T-3.6
- [ ] `PATCH /me/profile` (first_name 1–30 letters/spaces, hometown, city ≤ 40, about 40–300 — trimmed, no URLs, no phone numbers).
- [ ] `GET /usernames/{u}/available` (regex, reserved words list: admin, knot, support, help, moderator…); `PUT /me/username` handles the unique-violation race → `USERNAME_TAKEN`.
- [ ] **Commit:** `feat(onboarding): profile basics and username [T-3.7]`

### T-3.8 · Interests
- [ ] **Needs:** T-3.7
- [ ] `GET /interests`; `PUT /me/interests` exactly 5 valid distinct ids → replace set in one tx.
- [ ] **Commit:** `feat(onboarding): interests [T-3.8]`

### T-3.9 · PIN
- [ ] **Needs:** T-3.5
- [ ] `POST /auth/pin/set` (4 digits, not `0000`/`1234`/all-same), `POST /auth/pin/verify` (5 fails → revoke all sessions, `SESSION_REVOKED`). Skippable in onboarding.
- [ ] **Commit:** `feat(auth): pin lock [T-3.9]`

### T-3.10 · Web auth client
- [ ] **Needs:** T-1.18, T-3.4
- [ ] Access token in Zustand (memory only). On app load: call `/auth/refresh` once to restore a session, sending `X-CSRF` from this environment's CSRF cookie (D-055).
- [ ] On any 401 `TOKEN_EXPIRED`: single-flight refresh, then retry the request once.
- [ ] `useMe()` query; `<OnboardingGate>` redirects to the correct step from `onboarding_step`; `(app)` routes require `done`.
- [ ] PIN lock screen: shown on load and after 5 min hidden if a PIN is set.
- [ ] **Commit:** `feat(web): auth session, refresh, route gates, pin lock [T-3.10]`

### T-3.11 · Web onboarding 1–7
- [ ] **Needs:** T-3.10, T-3.7
- [ ] **New dependencies, the first forms to use them:** web `react-hook-form` and `zod`, with `@hookform/resolvers` to join them. CLAUDE.md pins them, but nothing has installed them: T-2.3's waitlist form uses plain React state on purpose, because two form libraries for one email field would spend the landing page's performance score (98–100, T-2.1). Ask before installing, and record them in `01-DECISIONS.md` (rule 4).
- [ ] Screens from the prototype: phone, OTP (4 boxes, paste support, resend timer from `resend_after_s`), DOB (native date input; under-18 message), gender (with lock warning), seeking + intents (pick 1–3), name/hometown/city, username (debounced availability 400 ms, shows `veloraapp.co.in/@name`).
- [ ] Each screen: submit disabled until valid; server errors shown inline from `ApiError.code` via `en.ts`.
- [ ] Phone step: a consent line naming Google before the code is sent — Google's Firebase sends it, processes the number in the United States and keeps it for abuse prevention (D-048, `/privacy`). Firebase asks apps to get this consent.
- [ ] **Commit:** `feat(web): onboarding steps 1-7 [T-3.11]`

### T-3.12 · Web onboarding 8, 10, 11
- [ ] **Needs:** T-3.11, T-3.8, T-3.9
- [ ] About (40–300 counter), interests (exactly 5), PIN (set + confirm, skip). Photos (9) and selfie (12) come in Sprint 4 — route placeholder that says "coming next".
- [ ] **Commit:** `feat(web): onboarding about, interests, pin [T-3.12]`

### T-3.14 · Firebase phone sign-in (launch path)
- [ ] **Needs:** T-3.3, T-3.10 (it restores the session on reload, which the Done-when checks), and T-3.11 (its phone and OTP screens, which this task's web step puts Firebase on)
- [ ] **New dependencies (approved, recorded in D-035):** api `firebase-admin`; web `firebase`.
- [ ] Firebase console: project created, Phone provider enabled, **App Check with reCAPTCHA
  Enterprise enforced on Authentication**, authorised domains = `veloraapp.co.in` + `staging.veloraapp.co.in`
  (the Done-when signs in there) + Vercel preview + `localhost`, daily SMS quota capped, billing alert set at a fixed rupee amount.
- [ ] `POST /v1/auth/firebase {id_token}`: verify signature and `aud`/`iss`/`exp` against Google's
  public keys (cached); require `phone_number` and `firebase.sign_in_provider == "phone"`;
  reject non-`+91` → `PHONE_NOT_SUPPORTED`; reject a reused `jti` (Redis until expiry) →
  `FIREBASE_TOKEN_INVALID`; throttle 10/IP/hour and 5/phone/hour.
- [ ] Then reuse the exact same service as T-3.3: banned check → find-or-create user + profile +
  wallet + prefs → session + cookies → `{access_token, user}`.
- [ ] The phone screen shows T-3.11's consent line naming Google before `signInWithPhoneNumber`
  runs (D-048, `/privacy`). Deleting the Firebase user after sign-in is P-39, not this task.
- [ ] Web: Firebase JS SDK on the phone screen (invisible reCAPTCHA), `signInWithPhoneNumber`,
  6-digit code box (Firebase codes are 6 digits, not 4 — the OTP screen adapts to
  `AUTH_PHONE_PROVIDER`), resend cooldown, friendly copy for `auth/too-many-requests`,
  `auth/invalid-phone-number`, `auth/code-expired`.
- [ ] Sign the user out of Firebase immediately after the exchange — we keep our own session.
- [ ] CSP updated for Firebase Auth and reCAPTCHA domains (follow-up to T-2.5).
- [ ] Tests: forged token rejected; expired rejected; reused token rejected; non-Indian number
  rejected; banned phone rejected; a valid token creates exactly one user.
- [ ] **Done when:** on staging, sign in at `https://staging.veloraapp.co.in` with a Firebase
  test phone number (fixed code, no SMS, no cost), reload, and the session is still there,
  restored by `/auth/refresh`. This is the first real sign-in staging can do (D-045 allows only
  real providers there), so it is the first proof that P-33's subdomains carry the refresh cookie.
  Until it passes, P-33 is believed, not proven.
- [ ] **Commit:** `feat(auth): firebase phone sign-in [T-3.14]`

### T-3.13 · E2E signup
- [ ] **Needs:** T-3.12
- [ ] Playwright against local stack with `AUTH_PHONE_PROVIDER=fake` (OTP read from a test-only endpoint enabled only when `ENV=local`): new man reaches the photos step; under-18 is refused and can't retry with the same number.
- [ ] One staging run against the real Firebase path using a Firebase **test phone number** (fixed code, no SMS sent, no cost).
- [ ] **Commit:** `test(e2e): signup flow [T-3.13]`

---

# Sprint 4 — Photos and verification (weeks 6–7)

### T-4.1 · Storage provider
- [ ] **Needs:** T-1.21, T-1.2, and **R2 enabled on the Cloudflare account, with the staging buckets
  `velora-staging-public` and `velora-staging-private`** (`infra/STAGING.md` §3) — not enabled yet
  (T-1.22)
- [ ] Real `StorageProvider` on aioboto3 (works for R2 and MinIO): `presign_put(bucket, key, content_type, max_bytes, ttl=300)`, `presign_get(bucket, key, ttl=600)`, `get_bytes`, `put_bytes`, `copy`, `delete`.
- [ ] Key helpers: `raw/{user_id}/{photo_id}`, `p/{photo_id}.jpg`, `voice/{thread_id}/{message_id}.webm`, `album/{photo_id}/{viewer_id}.jpg`.
- [ ] **Commit:** `feat(storage): r2 presigned urls [T-4.1]`

### T-4.2 · Upload URL and complete
- [ ] **Needs:** T-4.1, T-3.5
- [ ] `POST /photos/upload-url {kind, position?}` — public max 6 (positions 0–5), private max 6, selfie 1 active. Creates `photos` row `pending`, returns presigned PUT (image/jpeg|png|webp|heic, ≤ 8 MB).
- [ ] `POST /photos/{id}/complete` — object exists and size ok → enqueue `moderate_photo` (public/private) or leave for `verify_selfie` (selfie).
- [ ] **Commit:** `feat(photos): upload url and completion [T-4.2]`

### T-4.3 · Manage photos
- [ ] **Needs:** T-4.2
- [ ] `GET /me/photos`, `PATCH /me/photos/order`, `DELETE /photos/{id}` (soft: status `rejected` + reason `user_deleted`, object removed from public bucket).
- [ ] Onboarding `photos` step completes when ≥ 1 public photo is `approved` **or** `pending` (pending ones stay invisible to others until approved).
- [ ] **Commit:** `feat(photos): list, reorder, delete [T-4.3]`

### T-4.4 · Moderation worker
- [ ] **Needs:** T-4.2, T-1.15, and a **Sightengine account with API keys** — not created yet (P-0.6)
- [ ] ARQ worker bootstrap (`workers/main.py`) + `make worker`.
- [ ] Deploy the worker to Fly staging (moved from T-1.22): `infra/fly.worker.toml` beside
  `fly.api.toml`, the same image and least-privilege role, deployed by `deploy.yml` after the API.
  Add its pool to the connection budget in `infra/STAGING.md`.
- [ ] `moderate_photo(photo_id)`: fetch raw → Pillow open (reject if not an image) → `ImageOps.exif_transpose` → resize longest side 1600 → save JPEG q85 **without EXIF** → `ModerationProvider.check()` → approve (write public copy for `public` kind) or reject with reason (`nudity`, `minor_suspected`, `no_face`, `text_overlay`, `other`). `minor_suspected` also opens an internal report.
- [ ] Idempotent: re-running on an approved photo does nothing.
- [ ] Sightengine: turn on deleting each image right after its check, so photos don't stay on its
  servers in the US and Europe — `/privacy` says they're deleted there (D-048).
- [ ] Tests with the fake provider for approve and each reject path; test that output has no EXIF.
- [ ] Extend `make seed` (T-1.15): an approved public photo at position 0 for every onboarded seeded user — a placeholder from the prototype's `c1`/`c2` gradient, re-encoded like any upload and stored through `StorageProvider`. Re-running creates no duplicates.
- [ ] **Commit:** `feat(worker): photo moderation pipeline [T-4.4]`

### T-4.5 · Selfie verification
- [ ] **Needs:** T-4.4, and a **working AWS account for Rekognition in `ap-south-1`** — signed up, but its payment method failed verification (P-0.6)
- [ ] `POST /verification/challenge` → random pose from a list (turn left, turn right, look up, smile) stored on the row. `POST /verification/{id}/submit {photo_id}` → enqueue `verify_selfie`.
- [ ] `verify_selfie`: re-encode; `FaceMatchProvider.compare(selfie, approved_public_photos)`; similarity ≥ 85 and exactly one face → `approved`, `users.is_verified = true`; else `rejected` with reason. Max 5 attempts / day.
- [ ] Selfies are never public and never shown to other users.
- [ ] Extend `make seed` (T-1.15): an approved verification row, with a placeholder selfie in the private bucket, for every seeded user marked verified — the test woman and the prototype's 14 `v` profiles.
- [ ] **Commit:** `feat(verification): selfie challenge and face match [T-4.5]`

### T-4.6 · Web photos step
- [ ] **Needs:** T-4.3, T-3.12
- [ ] 6-slot grid; tap empty slot → file picker (`accept="image/*"`, `capture` not forced); client resize to ≤ 2000 px before upload (canvas) to save data; PUT to presigned URL with progress; states per slot: uploading %, checking, approved, rejected (with reason + retry). Drag to reorder (or up/down buttons on mobile).
- [ ] Women see the private-album note.
- [ ] **Commit:** `feat(web): photo upload step [T-4.6]`

### T-4.7 · Web selfie step
- [ ] **Needs:** T-4.5, T-4.6
- [ ] Request challenge → show pose instruction → `getUserMedia({video:{facingMode:"user"}})` → live mirrored preview → capture to canvas → upload as `kind=selfie` → submit → poll `GET /verification/latest` every 2 s (max 60 s) → result. Handles permission denied with instructions per browser.
- [ ] Men: "Skip for now". Women: cannot skip.
- [ ] **Commit:** `feat(web): selfie verification step [T-4.7]`

### T-4.8 · Finish onboarding
- [ ] **Needs:** T-4.5, T-4.10
- [ ] Service `onboarding.complete()`: requires profile fields, username, 5 interests, ≥ 1 public photo, location (T-4.10), and for women an `approved` verification → step `done`, compute `completeness`.
- [ ] **Commit:** `feat(onboarding): completion rules [T-4.8]`

### T-4.9 · E2E onboarding
- [ ] **Needs:** T-4.7, T-4.8, T-4.10
- [ ] Playwright with fake camera flags: man completes without selfie; woman is blocked until selfie approved.
- [ ] **Commit:** `test(e2e): full onboarding [T-4.9]`


### T-4.10 · Location
- [ ] **Needs:** T-3.5, and **P-38** (the seeded areas are still Bengaluru's; D-013 is Phagwara)
- [ ] `PUT /me/location` accepts `{lat,lng}` (must be inside India bounding box) or `{area_id}` (uses centroid). `GET /areas?city=`.
- [ ] Web: onboarding asks permission once with a clear reason; on deny → area picker. Location refreshed on app open if > 6 h old.
- [ ] **Commit:** `feat(profiles): location [T-4.10]`


---

# Sprint 5 — Velas core (week 8)

Built before discovery and chat because swipes, threads and unlocks all spend Velas.

### T-5.1 · Wallet service
- [ ] **Needs:** T-1.12, T-1.5, T-1.15
- [ ] `wallet.service.debit(session, user_id, amount, reason, ref_type, ref_id, idempotency_key)` and `credit(...)`.
- [ ] Inside the caller's transaction: `SELECT … FROM wallets WHERE user_id = :u FOR UPDATE` → check `balance >= amount` else raise `INSUFFICIENT_CREDITS {required, balance}` → update balance → insert `ledger_entries` with `balance_after`.
- [ ] Idempotency: if `idempotency_key` already exists, return the existing entry and change nothing.
- [ ] `amount <= 0` → programming error (raise, don't silently accept).
- [ ] Publishes `wallet.updated` after commit (not before).
- [ ] Extend `make seed` (T-1.15): credit the test man 60 through `credit(reason='admin_grant', idempotency_key='seed:test-man-credits')`, so a re-run changes nothing.
- [ ] **Commit:** `feat(wallet): row-locked debit and credit [T-5.1]`

### T-5.2 · Prices
- [ ] **Needs:** T-5.1
- [ ] `pricing.service.price_for(user, action)` → 0 for women, else `action_prices` value (Redis cache 60 s). `GET /prices`.
- [ ] Every paid action must call `price_for` — never a literal number in code (grep check in `/review`).
- [ ] **Commit:** `feat(pricing): server-side prices [T-5.2]`

### T-5.3 · Wallet endpoints
- [ ] **Needs:** T-5.1
- [ ] `GET /wallet`, `GET /wallet/ledger?cursor=` (human label per `reason` in the response).
- [ ] **Commit:** `feat(wallet): balance and history [T-5.3]`

### T-5.4 · The concurrency test 🔒
- [ ] **Needs:** T-5.1
- [ ] Give a user 10 credits. Fire **50 concurrent** debits of 5 using separate DB connections (`asyncio.gather`). Assert exactly **2** succeed, 48 get `INSUFFICIENT_CREDITS`, final balance 0, exactly 2 ledger rows, and `sum(delta) == balance`.
- [ ] Same with a repeated idempotency key: 50 concurrent calls → exactly 1 entry.
- [ ] This test must never be skipped or marked flaky. If it fails, stop everything.
- [ ] **Commit:** `test(wallet): concurrency and idempotency [T-5.4]`

### T-5.5 · Web wallet
- [ ] **Needs:** T-5.3, T-3.10
- [ ] Header balance pill (men) / "Free access" (women); wallet screen: black balance card, price list from `/prices`, ledger history (infinite scroll).
- [ ] Global handler: any `INSUFFICIENT_CREDITS` → opens the store sheet (placeholder "coming soon" until T-8.7).
- [ ] **Commit:** `feat(web): wallet screen and balance pill [T-5.5]`

---

# Sprint 6 — Discovery (weeks 9–10)

> Location lives in Sprint 4 as T-4.10, because onboarding needs it first. Discovery starts at T-6.2.

### T-6.2 · Discovery query
- [ ] **Needs:** T-4.10, T-4.8
- [ ] Repository implements the query in `02-ARCHITECTURE.md §8` with feeds: `foryou` (ranked), `new` (joined ≤ 7 days first), `online` (active ≤ 5 min). Filters: `intent_ids` (any overlap, D-041), verified.
- [ ] Excludes: self, swiped, blocked either way, hidden, not `done`, status ≠ active, fraud band `freeze`; `shadow` band users only shown to others in `shadow`.
- [ ] Response `Card`: id, first_name, age (null if hide_age), username, city, hometown, distance_km (null if hide_distance, else ≥ 1), intent_ids, bio line (first 90 chars of about), main photo URL, is_verified, is_online, is_new.
- [ ] Cursor = (score, user_id).
- [ ] Performance test: seed 50k profiles, assert p95 < 80 ms with `EXPLAIN ANALYZE` showing the GIST index.
- [ ] **Commit:** `feat(discovery): ranked nearby feed [T-6.2]`

### T-6.3 · Public profile
- [ ] **Needs:** T-6.2
- [ ] `GET /users/{id}` → `PublicProfile`: card fields + full about, all approved public photos, interests, kudos (if `show_kudos`), album photo count, existing thread/knot state with me. Blocked either way → 404 `NOT_FOUND`. Records a profile view (for later "viewed you").
- [ ] **Commit:** `feat(profiles): public profile [T-6.3]`

### T-6.4 · Swipes and matching
- [ ] **Needs:** T-6.3, T-5.1
- [ ] `POST /swipes {target_id, dir}`: men's daily cap from `app_config` (IST day, Redis counter) → `SWIPE_LIMIT_REACHED`; `super` debits price (women free) via wallet; duplicate swipe → `ALREADY_EXISTS`.
- [ ] If `like`/`super` and the target already liked me → create `matches` row (ordered pair), publish `match.created` to both, notification.
- [ ] **Commit:** `feat(swipes): swipe, daily cap, super like, match [T-6.4]`


### T-6.5 · Web discover deck
- [ ] **Needs:** T-6.2, T-6.4
- [ ] `useDiscover(feed, filters)` infinite query; keep 3 cards rendered; prefetch next page at 5 left.
- [ ] Card with `@use-gesture/react` + `@react-spring/web`: drag with rotation, LIKE/PASS overlays by drag distance, fling threshold 100 px or velocity, up = super. Tap = open profile. Keyboard ← → ↑ on desktop.
- [ ] Optimistic swipe: advance immediately, rollback + toast on error.
- [ ] Action row: pass, super (price tag for men), like. Swipes-left counter for men.
- [ ] Match celebration sheet → "Open thread · 5 Velas" / "Keep swiping".
- [ ] Empty states: no one nearby / filters too narrow (clear button).
- [ ] 60 fps on the test phone (check Chrome performance panel).
- [ ] **Commit:** `feat(web): discover deck [T-6.5]`

### T-6.6 · Search and @username
- [ ] **Needs:** T-6.3
- [ ] `GET /search?q=`: `@` prefix → exact-then-prefix username match (ignores distance/filters, still respects blocks/hidden); otherwise trigram on first_name/username + city, intent and interest matches within radius. `GET /users/by-username/{u}`.
- [ ] Web search bar with debounce; @-mode list results.
- [ ] **Commit:** `feat(search): search and username lookup [T-6.6]`

### T-6.7 · Liked you
- [ ] **Needs:** T-6.4, T-5.1
- [ ] `GET /likes`: people who liked/super-liked me and whom I haven't swiped; for men, unrevealed entries return only a blurred thumbnail URL (server-generated blur, not CSS) and no name. `POST /likes/{id}/reveal` debits 20 and records `liked_you_reveals`.
- [ ] Web "Liked you" tab: grid, count badge, reveal flow.
- [ ] **Commit:** `feat(discovery): liked you with paid reveal [T-6.7]`

### T-6.8 · Profile pages
- [ ] **Needs:** T-6.3
- [ ] In-app profile screen from the prototype (gallery, chips, kudos, message button, album section, ⋯ menu).
- [ ] Public shareable page `veloraapp.co.in/@username` (SSR): logged-out visitors see first name, age, city, main photo, and "Join Velora to message"; logged-in users are redirected to the in-app profile.
- [ ] **Commit:** `feat(web): profile screens and share page [T-6.8]`

### T-6.9 · Filters
- [ ] **Needs:** T-6.5
- [ ] Filter sheet: intent multi-select, verified only, online now; active count badge; stored in URL search params.
- [ ] **Commit:** `feat(web): discovery filters [T-6.9]`

---

# Sprint 7 — Threads, knots, chat (weeks 11–12)

### T-7.1 · Open a thread
- [ ] **Needs:** T-6.4, T-5.5-ready wallet (T-5.1)
- [ ] `POST /threads` from `{match_id}` (origin `match`) or `{user_id, first_message}` (origin `dm`, first message required, 1–500 chars).
- [ ] Rules: not blocked; both onboarded; if a thread already exists for the pair → `active`/`knotted` returns it (no charge), `expired` → `THREAD_EXPIRED` (client offers re-open).
- [ ] In one transaction: debit (men only, `thread_open` or `dm_open`), insert thread (`expires_at = now + thread_hours`), link match, insert first message if dm. Notify the other person.
- [ ] Tests: man pays once; woman pays nothing; double-tap race creates one thread and one charge.
- [ ] **Commit:** `feat(threads): open thread [T-7.1]`

### T-7.2 · Thread list
- [ ] **Needs:** T-7.1
- [ ] `GET /threads?tier=threads|knots&filter=&q=`: excludes cleared (unless newer message), blocked; each row has other person's card-lite, last message preview (voice → "Voice note"), unread count, status, `expires_at`, whether I've tapped tie.
- [ ] **Commit:** `feat(threads): list [T-7.2]`

### T-7.3 · Messages
- [ ] **Needs:** T-7.2
- [ ] `GET /threads/{id}/messages?cursor=` (newest first, respects my `cleared_at`; voice notes locked for men without unlock → no media URL).
- [ ] `POST /threads/{id}/messages`: participant only; thread `expired` → `THREAD_EXPIRED`; text 1–2000; abuse/solicitation rules → `MESSAGE_REJECTED` (+ fraud event); masking if `message_count < mask_first_n` (store `body_raw`, set `masked`); dedupe on `client_msg_id` (return existing); update `last_message_at`, `message_count`; publish `message.new`; notify recipient if not connected.
- [ ] Tests for masking patterns (+91 numbers, spaced digits, emails, UPI handles, "insta: x"), rejection, dedupe, expired.
- [ ] **Commit:** `feat(messages): list and send with safety filters [T-7.3]`

### T-7.4 · Real-time server
- [ ] **Needs:** T-7.3
- [ ] `POST /ws/ticket` (Redis, 30 s, single use). `/ws` endpoint: validate ticket, register connection, subscribe `user:{id}`, heartbeat, close on logout/freeze. Publishing helper `realtime.publish(user_id, type, data)` used by services.
- [ ] Load test: 1,000 concurrent sockets on one instance stay under 256 MB.
- [ ] **Commit:** `feat(realtime): websocket gateway [T-7.4]`

### T-7.5 · Read receipts and typing
- [ ] **Needs:** T-7.4
- [ ] `POST /threads/{id}/read` sets `read_at` up to a message, publishes `message.read`. Client `typing` relay throttled.
- [ ] **Commit:** `feat(realtime): read receipts and typing [T-7.5]`

### T-7.6 · Expiry and re-open
- [ ] **Needs:** T-7.4
- [ ] Cron `expire_threads` (every minute, batches of 500, `FOR UPDATE SKIP LOCKED`) → `expired` + event. Cron `warn_expiring` (< 2 h, once) → push + event.
- [ ] `POST /threads/{id}/reopen` (expired only) → debit 3 (men), `active`, `expires_at = now + 24h`, reset warning.
- [ ] Tests using a controllable clock.
- [ ] **Commit:** `feat(threads): expiry, warnings, reopen [T-7.6]`

### T-7.7 · Tie the knot
- [ ] **Needs:** T-7.6
- [ ] `POST /threads/{id}/knot`: set my `*_knot_at`; if both set → `knotted`, `knotted_at`, `expires_at = null`, publish `knot.accepted` to both; else publish `knot.requested` to the other. Works on `expired` threads too (converts directly if both).
- [ ] `DELETE /threads/{id}/knot`: untie → `active`, fresh 24 h, clear both taps, notify.
- [ ] **Commit:** `feat(threads): tie and untie knot [T-7.7]`

### T-7.8 · Clearing
- [ ] **Needs:** T-7.2
- [ ] `POST /threads/{id}/clear`, `POST /threads/clear` (ids or `expired: true`), `DELETE /threads/{id}/clear` (restore). Upsert `thread_clears`. Never touches `messages`.
- [ ] Test: after A clears, B still sees everything; admin still sees everything.
- [ ] **Commit:** `feat(threads): one-sided clearing [T-7.8]`

### T-7.9 · Voice notes
- [ ] **Needs:** T-7.3, T-4.1
- [ ] `POST /media/voice-upload-url` (women only, ≤ 60 s, ≤ 2 MB, audio/webm|ogg|mp4), then send message `kind=voice` with `media_key`, `duration_s`.
- [ ] `POST /messages/{id}/unlock` (men, debit 5, insert `message_unlocks`, idempotent) → signed URL. `GET /messages/{id}/media` for sender or unlocked.
- [ ] **Commit:** `feat(messages): voice notes and unlocks [T-7.9]`

### T-7.10 · Web chat list
- [ ] **Needs:** T-7.2, T-7.8
- [ ] Threads / Knots tabs with counts; live countdown per row (one shared 1 s ticker, not one per row); Knots filters; search; select mode + bulk clear; "Clear expired (n)"; trash per row with 5 s undo toast; unread dots; empty states.
- [ ] **Commit:** `feat(web): chats list [T-7.10]`

### T-7.11 · Web conversation
- [ ] **Needs:** T-7.3, T-7.7, T-7.9
- [ ] Bubbles, day separators, "Sent/Read" on my last message, typing dots, voice player (locked card with price for men), icebreakers when empty, knot bar (tie / waiting), expired panel (re-open · 3 / tie), header with countdown or "Knotted · permanent", ⋯ → profile menu.
- [ ] Composer: text (Enter sends, Shift+Enter newline), mic for women (MediaRecorder, hold or tap-to-record, 60 s cap, preview before send). Optimistic send with `client_msg_id`; failed → retry.
- [ ] Rejected message → inline explanation, text kept in composer.
- [ ] **Commit:** `feat(web): conversation screen [T-7.11]`

### T-7.12 · Web real-time client
- [ ] **Needs:** T-7.4, T-7.11
- [ ] `src/lib/ws.ts`: ticket → connect; exponential backoff 1→30 s with jitter; pause when tab hidden > 5 min; on reconnect refetch open thread + list. Events update TanStack Query caches (append message, bump row, update wallet, knot state).
- [ ] **Commit:** `feat(web): realtime client [T-7.12]`

### T-7.13 · E2E chat
- [ ] **Needs:** T-7.12
- [ ] Two browser contexts: man + woman. Match → open thread (balance −5) → messages both ways live → woman voice note → man unlocks (−5) → both tie → Knots tab. Expiry via test clock endpoint (local only).
- [ ] **Commit:** `test(e2e): threads and knots [T-7.13]`

---

# Sprint 8 — Payments, album, kudos, referrals (week 13)

### T-8.1 · Packs and orders
- [ ] **Needs:** T-5.1, T-1.21
- [ ] `GET /packs`: active packs for the user's price-test variant (`users.id` hash → A/B, stable). `POST /payments/orders {pack_id}` + `Idempotency-Key`: copy amount + `credits` from the pack, compute first-purchase bonus, create provider order, insert `payments` (`created`), return checkout params.
- [ ] Fake provider: returns a fake order and exposes a local-only endpoint that simulates the webhook.
- [ ] **Commit:** `feat(payments): packs and order creation [T-8.1]`

### T-8.2 · Webhook
- [ ] **Needs:** T-8.1
- [ ] `POST /payments/webhook`: verify `X-Razorpay-Signature` (HMAC SHA-256 of raw body with webhook secret) → else 400 and log. Handle `payment.captured` and `payment.failed` only; others → 200 ignore.
- [ ] Captured: find by order id; if `provider_payment_id` already set → 200 no-op. Else one transaction: set paid + ids + `raw_webhook`, `wallet.credit(purchase)`, `wallet.credit(purchase_bonus)` if any, referral reward check (T-8.6). Always return 200 quickly.
- [ ] Amount mismatch vs row → mark `failed`, alert, no credit.
- [ ] `GET /payments/{id}` for the client poll.
- [ ] Tests: same webhook delivered 5 times concurrently → credited once; bad signature → no credit; amount mismatch → no credit.
- [ ] **Commit:** `feat(payments): verified idempotent webhook [T-8.2]`

### T-8.3 · Refund requests
- [ ] **Needs:** T-8.2
- [ ] `POST /refund-requests` for **broken transactions only** (D-050): a payment that went through without granting Velas, or a duplicate charge for one purchase. A change of mind isn't a claim — purchases are final. In MVP an admin resolves each claim: missing Velas are granted through `wallet.credit()` (idempotent on the payment), and a duplicate charge is refunded to the original payment method in the gateway and recorded (`payments.status = refunded`). This task defines the claim kinds and the `status` values.
- [ ] **Commit:** `feat(payments): refund requests [T-8.3]`

### T-8.4 · Private album
- [ ] **Needs:** T-4.4, T-5.1
- [ ] Requests (debit 5 for men, `credits_charged` stored), incoming list for owner, decide (grant → enqueue `watermark_album`; decline → `wallet.credit(refund_album_declined)`), revoke (delete watermarked copies, status `revoked`).
- [ ] `watermark_album`: for each private photo render a copy with the viewer's `@username` tiled diagonally at ~20% opacity.
- [ ] `GET /users/{id}/album` → signed URLs of the viewer's copies only.
- [ ] **Commit:** `feat(album): requests, grants, watermarking [T-8.4]`

### T-8.5 · Kudos
- [ ] **Needs:** T-7.3
- [ ] `POST /kudos` (thread with ≥ `kudos_min_messages`, one per pair ever, fixed kinds only), `GET /me/kudos`, visibility via `show_kudos` setting. Public profile shows distinct kinds received, never who sent them.
- [ ] **Commit:** `feat(kudos): positive-only notes [T-8.5]`

### T-8.9 · Gifts
- [ ] **Needs:** T-5.1, T-6.3
- [ ] `GET /gifts` (active, sorted, cached 60 s).
- [ ] `POST /gifts/send {recipient_id, gift_id}` with `Idempotency-Key`. Rules, each with a test:
  recipient must be a woman with onboarding `done` (else `NOT_ALLOWED`); sender must be a man
  (women sending → `NOT_ALLOWED`); blocked either way → `BLOCKED`; frozen sender → `ACCOUNT_FROZEN`;
  free gifts capped by `gift_free_daily_limit` per IST day → `GIFT_LIMIT_REACHED`;
  same gift to the same person inside `gift_same_recipient_cooldown_h` → `GIFT_COOLDOWN`.
- [ ] Paid gifts: `wallet.debit(reason="gift", ref_type="gift_send")` **in the same transaction**
  as the `gift_sends` insert. Price read from the `gifts` row, never a literal.
- [ ] Links `thread_id` if an active or knotted thread already exists. Never creates a thread.
- [ ] Publishes `gift.received` on the socket and a notification (respects prefs).
- [ ] `GET /me/gifts` (received, paginated, sender card) and `GET /users/{id}/gifts` (counts only,
  hidden when `show_gifts` is false).
- [ ] **Commit:** `feat(gifts): catalogue, sending, limits [T-8.9]`

### T-8.10 · Web gifts
- [ ] **Needs:** T-8.9, T-5.5
- [ ] Gift button on a woman's profile → sheet with the 6 gifts in a 3×2 grid: asset, label, and
  either "Free" or the price in Velas. Free ones show the remaining daily count.
- [ ] Sending: optimistic disable, success toast, balance updates from `wallet.updated`.
  `GIFT_LIMIT_REACHED` / `GIFT_COOLDOWN` → friendly inline copy with when they can send again.
  `INSUFFICIENT_CREDITS` → store sheet.
- [ ] Received gifts row on her own profile and in You tab; toggle `show_gifts` in privacy settings.
- [ ] Notification opens the sender's profile.
- [ ] **Commit:** `feat(web): gifts on profile [T-8.10]`

### T-8.6 · Referrals
- [ ] **Needs:** T-8.2
- [ ] `POST /referrals/apply {code}` only before onboarding `done`, not own code, once. Reward both (Velas from `app_config`) when the referee completes selfie verification or first purchase, whichever first; idempotent. `GET /referrals/me`.
- [ ] **Commit:** `feat(referrals): codes and rewards [T-8.6]`

### T-8.7 · Web store and checkout
- [ ] **Needs:** T-8.2, T-5.5
- [ ] Store sheet from the prototype (packs, per-Vela and per-thread price, first-purchase banner). Load Razorpay Checkout script on demand. On success callback → poll `/payments/{id}` every 1.5 s (max 60 s) → toast + wallet refresh. Failure/dismiss → "Payment didn't go through" sheet with retry.
- [ ] CSP enforced now (T-2.5 follow-up).
- [ ] **Commit:** `feat(web): store and razorpay checkout [T-8.7]`

### T-8.8 · Web album, kudos, referral UI
- [ ] **Needs:** T-8.4, T-8.5, T-8.6
- [ ] Album section on profile (locked / pending / granted with watermark note); incoming requests list for women with grant/decline; kudos prompt in chat after the threshold; referral code field in onboarding (optional) and share card in You tab.
- [ ] **Commit:** `feat(web): album, kudos, referrals [T-8.8]`

---

# Sprint 9 — Safety, admin, notifications, hardening (weeks 14–15)

### T-9.1 · Reports and blocks
- [ ] **Needs:** T-7.2
- [ ] `POST /reports` (≤ 10/day, details ≤ 500, optional `also_block`), `POST /blocks`, `DELETE /blocks/{id}`, `GET /blocks`.
- [ ] Block effects, each with a test: removed from both discovery feeds, search, likes; profile → 404 both ways; threads hidden for both and sending → `BLOCKED`; realtime events stop; existing album grants revoked.
- [ ] Reported person is never told who reported.
- [ ] **Commit:** `feat(safety): reports and blocks [T-9.1]`

### T-9.2 · Fraud scoring v1
- [ ] **Needs:** T-9.1
- [ ] Signals written as `fraud_events` by services: report received, contact-info masked, message rejected (abuse / solicitation), > 30 new threads in 24 h, identical first message to > 10 people, > 3 devices in 7 days, location jumps > 500 km in 1 h.
- [ ] `recompute_fraud` worker: weighted sum with 7-day decay → `fraud_scores` + band. Actions: `shadow` → shown only to other shadowed users; `freeze` → status `frozen`, sessions revoked, admin notified. 3 reports from different users in 24 h → freeze immediately.
- [ ] **Commit:** `feat(safety): fraud scoring and auto-freeze [T-9.2]`

### T-9.3 · Refund when a partner is banned
- [ ] **Needs:** T-9.2, T-5.1
- [ ] On ban: find Velas other users spent on this person in the last 7 days (threads opened with them, voice unlocks, album requests) → `wallet.credit(refund_banned_partner)` each, idempotent per ref, notify. The 7 days is also stated on `/refunds` (D-050): change both together.
- [ ] **Commit:** `feat(safety): refunds for banned partners [T-9.3]`

### T-9.4 · Notifications
- [ ] **Needs:** T-7.4
- [ ] VAPID keys; `POST/DELETE /push/subscriptions`; `send_push` worker (drop subscriptions on 404/410); notification prefs; in-app `notifications` list. Kinds: match, message (only if not connected), like, knot requested/accepted, thread expiring, album decided, low balance.
- [ ] Web: Serwist service worker (push + notificationclick → open the right route), permission asked **after the first match**, not on load; generic-text option; iOS note when not installed.
- [ ] Update `/privacy` (T-2.2) to say what push notifications carry and who delivers them.
- [ ] **Commit:** `feat(notifications): web push and in-app list [T-9.4]`

### T-9.5 · Admin panel
- [ ] **Needs:** T-9.2
- [ ] API: all `/admin/*` routes in `04-API.md`, `require_role(moderator)`; Vela grants and bans `admin` only; every call writes `audit_log`; viewing messages of a thread logs who looked and why (reason required).
- [ ] Web `/admin`: metrics tiles, report queue with SLA timer (24 h), user search + detail (photos, reports, fraud signals, ledger, threads), moderation queue (approve/reject), actions with confirmation dialogs, audit log.
- [ ] Web `/admin` renders only for `role in (moderator, admin)`, read through `useMe()`; anyone else
  gets the 404 page — replacing T-1.22's `next dev`-only gate (from P-30). **This gate is UX, not
  protection:** anyone can download the page's JavaScript, and the Next.js server never sees a
  session there (D-024). Every `/admin/*` endpoint must carry its own `require_role(...)`; the
  API's role check is the only thing guarding admin data.
- [ ] **Commit:** `feat(admin): moderation panel [T-9.5]`

### T-9.6 · Settings and data rights
- [ ] **Needs:** T-3.5
- [ ] Hide profile, hide age, hide distance, show kudos; pause (hidden + no notifications); export (JSON of own data, generated by worker, signed link valid 24 h); delete (status `deleted`, profile hidden immediately, anonymised after 30 days by cron; payments and ledger kept, detached from identity). What's erased and kept follows D-051, which `/privacy` states: messages stay in the other person's chat as from "Deleted account" and as moderation records, and a hashed phone number is kept so deletion can't escape a ban. Change the page with the code.
- [ ] **Commit:** `feat(settings): privacy and data rights [T-9.6]`

### T-9.7 · PWA
- [ ] **Needs:** T-9.4
- [ ] Web manifest (name, icons 192/512/maskable, theme colour from tokens, `display: standalone`), install prompt banner (Android `beforeinstallprompt`; iOS instructions), offline shell page.
- [ ] **Commit:** `feat(web): installable pwa [T-9.7]`

### T-9.8 · You tab complete
- [ ] **Needs:** T-9.6, T-8.8
- [ ] Profile summary + edit, verification status, kudos, knots list with untie, blocked list with unblock, reports filed, cleared chats with restore, settings rows, lock now, log out.
- [ ] **Commit:** `feat(web): you tab [T-9.8]`

### T-9.9 · Ledger audit
- [ ] **Needs:** everything above
- [ ] One test per paid action (thread open, dm, re-open, voice unlock, album, super like, liked-you reveal): man → exactly one ledger entry with the right reason and amount; woman → zero entries; insufficient → nothing created.
- [ ] Reconciliation test: for every user, `wallets.balance == sum(ledger.delta)`. Also as a daily cron that alerts on mismatch.
- [ ] **Commit:** `test(wallet): paid action audit and reconciliation [T-9.9]`

### T-9.10 · Performance pass
- [ ] **Needs:** T-9.8
- [ ] On the ₹10k test phone over throttled 4G: first load of `/discover` < 3 s, swipe at 60 fps, JS bundle for `(app)` < 250 KB gzipped, images served at the right size. Fix the top 3 offenders.
- [ ] **Commit:** `perf(web): mobile performance pass [T-9.10]`

### T-9.11 · Accessibility pass
- [ ] **Needs:** T-9.8
- [ ] Keyboard reachable everything, visible focus, labels on icon buttons, colour contrast AA from tokens, reduced-motion respected by the deck, screen-reader names for swipe actions.
- [ ] **Commit:** `a11y(web): accessibility pass [T-9.11]`

### T-9.12 · Observability
- [ ] **Needs:** T-1.22, and a **Sentry account** — not created yet (P-0.6)
- [ ] Sentry in api, worker, web (release = git sha). Alerts: 5xx > 1% for 5 min, webhook signature failures, any job failing 3×, ledger reconciliation mismatch, queue depth > 1,000. Uptime check on `/readyz`.
- [ ] **Commit:** `chore(ops): error tracking and alerts [T-9.12]`

### T-9.13 · Security review
- [ ] **Needs:** T-9.9
- [ ] Walk the security checklist in `07-CHECKLISTS.md` line by line; fix findings; run Claude Code `/security-review` on the branch; commission the external review of auth + wallet + payments (budget line in cost doc).
- [ ] **Commit:** `fix(security): review findings [T-9.13]`

### T-9.14 · Backups and restore drill
- [ ] **Needs:** T-2.6
- [ ] Confirm Supabase PITR on production; restore last night's backup into a scratch project and run the reconciliation query against it. Document the steps in `docs/runbook.md`.
- [ ] **Commit:** `docs(ops): backup and restore runbook [T-9.14]`

### T-9.15 · Go live
- [ ] **Needs:** T-9.13, T-9.14, P-0.5, P-0.7, P-0.8
- [ ] Production env: real SMS, real Razorpay live keys + webhook URL, real moderation and face match, VAPID keys. Run the pre-launch checklist in `07-CHECKLISTS.md`. Do one real ₹ purchase yourself and refund it.
- [ ] **Write to the waitlist** (T-2.3): its copy promises to tell people when Velora opens near them. Nothing can send bulk email yet, so choose how before launch day, or the list is one we can't write to. A sending service is a new dependency and another processor `/privacy` must name, and its From address needs SPF and DKIM, like the mailboxes (P-0.3). B-14, a second city, writes to it again, by city.
- [ ] **Commit:** `chore(release): v1.0.0 [T-9.15]`

---

# Sprint 10 — Closed beta operations (weeks 16–19)

- [ ] **T-10.1** Invite codes: signup requires a code during beta (`app_config.beta_invite_only`); women's codes unlimited, men's limited per code.
- [ ] **T-10.2** Product analytics (PostHog, EU/India region if available): events `signup_step_completed`, `swipe`, `match`, `thread_opened`, `message_sent`, `knot_tied`, `thread_expired_unanswered`, `purchase_started`, `purchase_paid`, `report_filed`. No message content, no phone numbers. Update `/privacy` (T-2.2) to say what it collects and where it goes.
- [ ] **T-10.3** Metrics queries for the weekly review: D1/D7 retention, thread → knot rate, % threads expiring with zero replies, paying conversion (men), revenue per paying user, reports per 100 users, active gender ratio.
- [ ] **T-10.4** Price test: variant A (₹1,500 / 25 Velas) vs B (₹999 / 25) assigned 50/50; compare revenue per paying man after 3 weeks.
- [ ] **T-10.7** First-thread-free test (risk R1 in `09-RESEARCH.md`): half of new men get their first thread free. Measure paying conversion, threads per man, and revenue per man — not just the free-thread take-up.
- [ ] **T-10.5** Moderator runbook: report handling per reason, SLA, escalation (minor suspected → immediate ban + preserve evidence), canned replies.
- [ ] **T-10.6** Feedback loop: in-app "Send feedback" → `feedback` table; weekly triage into Proposed tasks.

---

# Backlog — after beta (Sprint 11+)

Each becomes a full task with steps when it's pulled in.

| ID | Feature | Notes |
|---|---|---|
| B-1 | Voice calls (knots only, 4 Velas/min, first 60 s free) | Agora Web SDK, server-minted tokens |
| B-2 | Video calls (10 Velas/min) + live frame moderation | biggest cost line — check unit economics first |
| B-3 | Vibe Room (3-min anonymous text, mutual reveal → thread) | needs strong moderation |
| B-4 | Boost (30 Velas / 30 min) | ranking multiplier |
| B-5 | Who viewed you (15 Velas reveal) | `profile_views` already recorded in T-6.3 |
| B-6 | Wink (2 Velas) | |
| B-7 | Paid incognito | |
| B-8 | Daily streaks | |
| B-9 | Rewarded ads | needs an ad network that supports web rewarded |
| B-10 | Auto top-up | needs saved payment mandate |
| B-11 | View-once photos | |
| B-13 | Hindi UI | `hi.ts` alongside `en.ts` |
| B-14 | Second city | |
| B-15 | Native Android (React Native + Expo) | only if beta gates are met |
| B-16 | **Closure kit for knots** — "End chat" with a reason, closure message to the other person, and a gentle nudge after 48 h of no reply | answers C4/R2 in `09-RESEARCH.md`; cheap and hits the most emotional complaint |
| B-17 | **Date safety kit** — share plans with a friend, check-in timer, emergency contact | strongest women-side differentiator for India (C5) |
| B-18 | **Profile prompts** — 3 of ~20 short questions instead of one about field | fewer bots, better openers (C2/C7) |
| B-19 | **Visibility transparency** — a plain-words page on how ranking works; never throttle reach to sell boost | answers R3; keep the fraud `shadow` band fraud-only |

---

# Timeline

15 weeks full-time to go-live (Sprints 1–9), then 4 weeks of beta. At 2–3 hours a day, expect
roughly double. Re-estimate after Sprint 2 using your real pace.

---

# Proposed tasks

Claude Code adds items here instead of doing unplanned work. Format:
`- [ ] P?-NN · short title — why it's needed — found during T-x.y`

- [ ] P-01 · Decide the Postgres image for Apple Silicon — `postgis/postgis:16-3.4` publishes no
  arm64 manifest, so it runs under emulation on the dev Mac. It works, but it is slow, and T-1.5
  targets `make test` green in under 10 s. Either accept the cost, switch to an arm64 PostGIS
  image, or build one — needs a D-entry either way — found during T-1.2
- [ ] P-02 · Record the MinIO registry and pinning in `01-DECISIONS.md` — `minio/minio` on Docker
  Hub is no longer publicly pullable, so the stack pulls from `quay.io/minio/*` at pinned RELEASE
  tags. The tag also matters because newer MinIO community builds drop the web console that T-1.2's
  acceptance depends on — found during T-1.2
- [x] P-03 · Decide the response-class strategy — FastAPI 0.141 deprecates `ORJSONResponse`
  ("FastAPI now serializes data directly to JSON bytes via Pydantic"), but T-1.3 specifies orjson
  responses, so every error response currently emits a `FastAPIDeprecationWarning`. Either keep it
  and silence the warning, or drop `default_response_class` and keep orjson only where we serialise
  by hand. Worth settling before T-1.20 turns warnings into CI noise — found during T-1.3
  **Resolved in T-1.6:** moved off `ORJSONResponse` (handlers use `JSONResponse`; routes serialise
  natively via Pydantic), orjson removed, D-038 amended. 21 warnings → 0.
- [ ] P-04 · Exception logging may leak values — tracebacks currently log exception messages
  verbatim, which can carry row values or tokens once real data exists. Violates CLAUDE.md rule 15.
  Found during T-1.3.
- [x] P-05 · `create_app(settings)` does not reach the database or Redis — the lifespan calls
  `get_engine()` / `get_redis()`, which read the global `get_settings()`, so settings passed to
  `create_app` drive CORS, logging and docs but not the connections. Verified: `create_app` given
  `velora_test` connected to `velora`. A T-1.5 harness passing test settings would silently run
  against the dev database. Fix with a test, and add the missing test for `get_session`.
  **Fix before or at the start of T-1.5.** Found in review of T-1.4.
- [ ] P-06 · Harden the public `/readyz` — it is unauthenticated and unthrottled, and each call
  checks out a pooled Postgres connection and hits Redis, so a flood during a slow-database incident
  can hold connections up to 2 s each and starve real requests. It also tells anyone which
  dependency is down. Rate-limit it with the rate-limit work, and decide whether production should
  hide per-dependency details before T-1.22 exposes `api.velora.app`. Found in review of T-1.4.
- [ ] P-07 · Harness mode for concurrency tests — the `db` fixture is one session inside one
  rolled-back transaction, so concurrent requests through it fail (measured: 5 concurrent requests →
  `[200, 500, 500, 500, 500]`, `InvalidRequestError`), and row locks inside a single transaction never
  contend anyway. The 🔒 tests #1–#3 in `06-TESTING.md` (wallet concurrency and idempotency, T-5.4;
  webhook idempotency, T-8.2) need genuinely committed transactions on separate connections, with
  the tables truncated afterwards. **Needed before T-5.4.** Found in review of T-1.5.
  **Note from T-1.12:** truncation won't work — `ledger_entries` refuses UPDATE, DELETE *and*
  TRUNCATE, and `payments` refuses DELETE and TRUNCATE. Decide the cleanup in T-5.4, where the
  constraint is felt: a throwaway database per run, or fresh user ids per run (production never
  deletes from the ledger either).
- [ ] P-08 · `TEST_REDIS_URL` override — `TEST_DATABASE_URL` can be overridden but the test Redis
  is fixed at `127.0.0.1:6379/1`. If T-1.20's CI runs Redis anywhere else, the harness reports the
  stack unreachable and CI hard-fails by design. Add the override alongside T-1.20. Found in review
  of T-1.5.
- [ ] P-09 · Run gitleaks in CI — the pre-commit hook only protects clones that ran `make hooks`,
  and `git commit --no-verify` skips it. T-1.20's CI steps list ruff, mypy and pytest but not
  gitleaks, so nothing server-side enforces checklist E's "no secrets in repo". Add a
  `gitleaks git` step to T-1.20's `api` job. Found in review of T-1.6.
  **Moved:** now a step in T-1.20 — tick this with T-1.20.
- [ ] P-10 · Hooks must work from GUI git clients — the ruff and mypy hooks call `uv` by name. VS
  Code's Source Control panel (which the user commits from) and other GUI clients run hooks
  without the shell profile, so `uv` may not be on `PATH` and every commit fails. Resolve `uv`
  robustly (absolute path or a wrapper that locates it) and test a commit from VS Code. Found in
  review of T-1.6.
  **Moved:** now a step in T-1.20 — tick this with T-1.20.
- [ ] P-11 · Test DB stamped at a revision the checkout doesn't have — every task works on its own
  branch, and from T-1.8 each adds migrations. Run the tests on a branch with a new migration, switch
  to one without it, and `velora_test` still records that revision: every database test then errors
  with `ResolutionError: No such revision`. Happened for real during T-1.7. `velora_test` is
  disposable, so the harness should detect an unknown stamp and rebuild the schema (drop and
  recreate `public`, migrate to head) rather than fail. Until then, recover with
  `make infra-reset`. Found during T-1.7.
- [x] P-12 · Drop `typing.Union` from the revision template — `api/alembic/script.py.mako` imports
  `Union`, the post-write ruff hook rewrites the annotations to `X | Y`, and T-1.7's F401 exemption
  for `alembic/versions/*` then keeps the now-unused import in every new revision. Write the
  template with `|` and no `Union` import. Found during T-1.8 (removed by hand there).
  **Done:** template now imports `Sequence` from `collections.abc` and writes `str | Sequence[str] | None`;
  a generated revision has no `Union` and passes strict mypy and ruff.
- [x] P-13 · Public photos must have a position — `ck_photos_public_position_range` is
  `kind <> 'public' OR position BETWEEN 0 AND 5`; with `position` NULL, `BETWEEN` is unknown and
  Postgres passes a CHECK on unknown, and the partial unique index treats NULLs as distinct. So any
  number of slot-less public photos can be inserted, though 03-SCHEMA.md ("0–5 for public; 0 =
  main") implies every public photo holds a slot. Needs a **new** migration now that T-1.9 is
  merged (rule 11): `… OR (position IS NOT NULL AND position BETWEEN 0 AND 5)`, plus a test.
  **Before T-4.x (photo upload).** Found in review of T-1.9.
  **Done:** migration `36af56c36916` recreates the check with `position IS NOT NULL AND …`;
  a public photo with no position is now refused (`23514`), other kinds still need none.
- [x] P-14 · Say `thread_hours`, not "24h" — T-1.10's note in 03-SCHEMA.md (threads) and the
  `threads` model docstring say every way into `active` sets "a fresh 24h", but the lifetime is
  `app_config.thread_hours` (seeded 24). Reword both so T-7.x reads the config instead of copying
  a literal (checklist A). The CHECKs don't depend on the value. **Before T-7.x.** Found in review
  of T-1.10.
  **Done:** both now name `app_config.thread_hours` (seeded 24).
- [ ] P-15 · Bound `messages.body_raw` and `duration_s` (optional) — `body` is capped at 2000
  characters but `body_raw` is unbounded, and `duration_s` accepts 0 or negative seconds. API input
  validation (T-7.x) is the primary bound; matching CHECKs would be defence in depth. Needs a new
  migration now that T-1.10 is merged (rule 11). Found in review of T-1.10.
- [ ] P-16 · Decide whether unblocking keeps history — `blocks` is one row per pair with no
  history, so unless T-9.1 designs otherwise, unblock is a `DELETE` and the fact that A blocked B is
  gone. Rule 12's explicit list doesn't name blocks, but its principle does ("nothing is hard-deleted
  that moderation may need"), and "blocked by many people" is a fraud and moderation signal. Options:
  soft-unblock (`unblocked_at`, primary key replaced by a partial unique index) or accept the loss.
  Needs a new migration (T-1.11 is merged). **Before T-9.1.** Found in review of T-1.11.
- [ ] P-17 · Refuse DELETE and TRUNCATE on `messages` and `reports` — rule 12 names messages,
  reports, ledger and payments as never hard-deleted. T-1.12 enforces it in the database for the
  ledger and payments (`refuse_change()`, `restrict_violation` 23001); `messages` and `reports`
  were merged earlier without it. Reuse `refuse_change()` in a new migration (rule 11). Clearing a
  chat stays one-sided (`thread_clears`), so no legitimate path deletes messages. Found during T-1.12.
- [x] P-18 · App connects as a least-privilege database role — T-1.12's guards (append-only ledger,
  never-deleted payments) and T-1.13's (append-only `audit_log`) are triggers: they stop application
  bugs, not a privileged role. Proven on the ledger, and again on `audit_log` in review of T-1.13:
  as table owner or superuser, `SET session_replication_role = replica` or `ALTER TABLE … DISABLE
  TRIGGER` lets a `DELETE` straight through. If the API connects to Supabase as the owning role, an
  injection or stray script has those bypasses. The API must use a role that doesn't own the tables
  and can't `ALTER` them or set `session_replication_role`; migrations run as the owner. Its tests
  cover every guarded table. **Before T-1.22.** Found in review of T-1.12.
  **Moved:** now two steps in T-1.22 — tick this with T-1.22.
- [ ] P-19 · Namespace ledger idempotency keys per user — `ledger_entries.idempotency_key` is unique
  across all users, and money routes accept a client `Idempotency-Key` header (02-ARCHITECTURE §3).
  Stored raw, two users sending the same key collide: the second user's genuine debit is refused —
  or, if the service reads a unique violation as "already applied", reported as paid when it wasn't.
  `wallet.service` must store a namespaced key, e.g. `{user_id}:{operation}:{client key}`.
  **Design into T-5.x.** Found in review of T-1.12.
- [ ] P-20 · Audit automated actions as a system user — ruled in T-1.13: `audit_log.actor_id` is
  NOT NULL, because null could not tell "the system did it" from "a bug forgot to set it", and the
  system user is created when auto-freeze first needs it, by T-9.2. T-9.2's text says neither that
  auto-freeze writes `audit_log` nor that the user must exist; the ruling lives only in 03-SCHEMA §8
  and the `AuditLogEntry` docstring. T-9.2 adds a data migration creating the user — it must never
  log in or appear anywhere users are listed — and writes each automated freeze to `audit_log` as
  it. **Fold into T-9.2.** Found in review of T-1.13.
- [ ] P-21 · Correct two comments — the `PushSubscription` docstring calls `p256dh` and `auth`
  "secrets": `auth` is a shared secret, but `p256dh` is the browser's public key. The comment above
  `test_updated_at_triggers_are_on_exactly_the_mutable_tables` says "five mutable tables"; it has
  been wrong since T-1.10 and the set is now 17. Comments only. Found in review of T-1.13.
- [x] P-22 · Commit the prototype to the repo — it is "the visual reference for every screen"
  (08-DESIGN) and the source for T-1.15's 20 dev profiles, T-1.19's UI primitives, T-2.1's landing
  page, T-3.11's onboarding screens and T-8.7's store sheet, but it has never been in the repo or its
  history. T-1.14 had to ask for the interests list for the same reason. Suggested home:
  `docs/prototype/`. **Before T-1.15.** Found during T-1.14.
  **Done:** committed as `docs/prototype/velora-prototype-reference.html`. It predates the Velora
  rename, so it says "Knot": the screens and flows are the reference, not the name.
- [ ] P-23 · Define what a variant-B man sees in `GET /packs` (T-8.1) — T-1.14 seeds variant B as
  one row, `entry-25` (25 Velas, ₹999). Read literally, "active packs for the user's price-test
  variant" gives a B user a one-pack store. What D-005 describes is A's ladder with the entry pack
  in place of `pack-25`. Decide in T-8.1, with a test that B sees four packs. Found during T-1.14.
- [ ] P-24 · Make the catalogue columns NOT NULL — `areas.city`, `areas.name`, `areas.centroid`,
  `interests.slug` and `interests.label` are nullable (T-1.9). A catalogue row with no name means
  nothing, and nullable unique keys (`(city, name)`, `slug`) don't stop duplicate NULLs, so a
  re-run could duplicate such a row. The T-1.14 seed sets them all. New migration (rule 11).
  Found during T-1.14.
- [x] P-25 · Intent becomes a multi-select catalogue, the same shape as interests — interests are
  who you are; intents are what you're looking for. **Do right after T-1.14.** Its own migration,
  because T-1.8 and T-1.9 are merged (rule 11).
  - Drop `profiles.intent` (and its index `ix_profiles_intent`) and the `intent_t` enum.
  - Add `intents` (`id smallint pk, slug text unique, label text`) and `profile_intents`
    (`user_id, intent_id, pk(user_id, intent_id)`).
  - Seed 10, in sentence case like interests (both show as chips on the same profile): Something
    serious, Long term, Situationship, Casual dating, Just one night, No strings attached, Open
    relationship, Discreet, Friendship, Go with the flow.
  - Users pick 1 to 3, enforced in the service.
  - Update 03-SCHEMA, 04-API (`POST /me/seeking` takes a list), and the T-3.6 and T-6.2 steps,
    since discovery filters on intent.
  - Also touches (found while filing): 04-API `GET /discover`'s `intent=` param and T-6.2's `Card`
    (one `intent` today); T-6.6 search ("city/intent/interest matches"); T-6.9's filter sheet;
    T-3.11's "seeking + intent" screen; 08-DESIGN's intent badge; 02-ARCHITECTURE §8's query
    sketch; and in code `Intent` / `PG_ENUMS` in `app/core/enums.py`, whose test expects 20 enums.
  **Done:** migrations `edf91547331e` (schema) and `c4193b88d395` (the 10 intents); decision
  recorded as D-041, with `GET /intents` (🔐, T-3.6) added to 04-API.
- [ ] P-26 · Catalogue labels on screen come from `en.ts`, keyed by id — D-033 puts every
  user-facing string in `web/src/i18n/en.ts`, but 03-SCHEMA calls `gifts.label` "shown in UI", and
  `GET /gifts` returns `label` (04-API), and `GET /interests` will. **Resolved:** the database
  label is the admin-facing name and the fallback; the UI reads `en.ts` keyed by id. That is what
  lets Hindi work later without a data migration. Applies to `gifts.label`, `interests.label` and,
  after P-25, `intents.label`. Reword 03-SCHEMA's notes on those columns to match; the tasks that
  show them — T-3.12's interests picker, T-6.8's profile chips, T-8.10's gift sheet, and P-25's
  intent screens — add the `en.ts` entries and read them. Found during T-1.14.
- [ ] P-27 · Consider Indian classical music in the interests catalogue — the 24 have Indie music
  and Old Hindi cinema but nothing classical, and a prototype profile needed it: Kavya's about
  opens "Trained in Carnatic vocal since I was six", and T-1.15 has to replace her "Carnatic" tag.
  Adding it is a data migration; existing ids stay fixed, so it would take id 25. Found while
  planning T-1.15.
- [x] P-28 · Test that `theme-color` equals `--chrome` — `<meta name="theme-color">` can't read a
  CSS variable, so `web/src/styles/theme-color.ts` holds the literal `#141113`: the one documented
  exception to rule 14 (08-DESIGN §1). The day `--chrome` changes in `tokens.css`, that copy drifts
  and nobody notices. **After T-1.19** (vitest): a test that reads `tokens.css` and asserts
  `THEME_COLOR` equals `--chrome`. Found in T-1.17.
  **Done in T-1.19:** `web/src/styles/theme-color.test.ts`. Proven both ways: it fails when the
  copy is one digit off, and passes once it's restored.
- [ ] P-29 · Reject spacing values that aren't on the scale. 08-DESIGN §3's spacing scale was
  settled in T-1.19: 2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 20 · 24 · 32 · 40 · 56 px. The prototype's
  32 one-off values (18, 22, 26, 28, 36, 48, 64) are to be rounded when their screens are built,
  but nothing enforces that — the same gap P-28 closed for theme-color. Extend the
  `colours-only-in-tokens` pre-commit hook (same hook, same `pygrep` pattern, same `^web/src/`
  scope) to also reject Tailwind padding, margin, gap and space utilities, in every axis and side
  form, whose value is off the scale. That covers both arbitrary values (`p-[18px]`) and off-scale
  steps (`mt-7` is 28 px, `gap-4.5` is 18 px, `p-9` is 36 px). Prove it both ways: it flags
  those, and passes `p-3.5`, `gap-2.5` and `px-0.5`. Found in T-1.19.
- [ ] P-30 · Keep `/admin` off the public internet until it is gated. **Due before T-1.22.**

  **The web gate on `/admin` is UX, not protection.** Anyone can download the page's JavaScript,
  and the Next.js server never sees a session there: D-024 keeps the access token in browser
  memory, and checklist E scopes the refresh cookie to `/v1/auth`. The only thing guarding admin
  data is the API's role check. Every `/admin/*` endpoint must carry its own
  `require_role(...)`; never ship one on the strength of the page gate.

  Why now: `web/src/app/admin/page.tsx` is a placeholder that returns 200 from the production
  build, and T-1.22 puts that build on a public staging URL. The plan gates the admin API (T-9.5),
  but nothing gates the web route. T-3.10's gate covers `(app)` only, and T-2.4's `robots.txt`
  disallow only asks crawlers to stay away — it also advertises the path. Two parts:
  - **Before T-1.22:** `/admin` returns 404 outside `next dev`, using the allowlist `/dev/ui` uses
    (`notFound()` unless `NODE_ENV === "development"`), with a test. Check the staging 404's
    *body*, not just its status: in T-1.19 a 404 still carried the page's `metadata` title.
  - **In T-9.5, replacing the gate above:** the web `/admin` renders only for
    `role in (moderator, admin)`, read through `useMe()`, and anyone else gets the 404 page. It can
    only be a client-side check (see above), so it is there for the user, not for security.

  Found while closing T-1.19.
  **Moved:** the 404 is now a step in T-1.22, and the role gate a step in T-9.5 — tick this with
  T-9.5.
- [x] P-31 · Stop serving the API schema and docs outside local. **Due before T-1.22.**
  `create_app()` serves `/openapi.json` and `/docs` unless `ENV` is `production` — a blacklist,
  so staging serves both, with the full schema. Checked in T-1.18: `local` and `staging` return
  200 with every path; `production` returns 404 with no schema in the body. T-1.22 makes staging
  public, and a public schema of the wallet, payment and admin routes is free reconnaissance.
  Since T-1.18 nothing needs the endpoint: `make types` reads the schema offline (D-043). Make it
  an allowlist, served only when `ENV == "local"`, and test both `staging` and `production`:
  `/openapi.json` and `/docs` return 404, and the bodies contain no schema. Found in T-1.18.
  **Moved:** now a step in T-1.22 — tick this with T-1.22.
- [x] P-32 · Keep `api/.env` out of every image — a secrets leak, not a config problem.
  **Due with T-1.22's Dockerfile.** Docker's build context ignores `.gitignore`, so building from
  `api/` copies a developer's `api/.env` into the image unless it's excluded. That bakes the JWT
  secret, the database password and every provider key into an image pushed to Fly's registry.
  Docker keeps deleted files in earlier layers, so removing the file later doesn't remove the
  secrets: once pushed, every one of them must be rotated. It also sets `ENV=local` inside the
  image, which switches D-045's check off and allows fake payments and fake sign-in. Add
  `api/.dockerignore` excluding `.env*` before the first image is built, and a CI check that the
  built image contains no `.env` in any layer. Found in T-1.21.
  **Moved:** now a step in T-1.22 — tick this with T-1.22.
- [x] P-33 · Put staging's web and API on one site, or sign-in can't keep a session there. **Due
  before T-2.3**, where the founder slotted it on 2 October 2026: built between tasks while nothing
  is in flight, so T-2.3 is built once, against staging's final addresses. On T-2.3's and T-3.4's
  Needs lines. **Needs:** the nameservers on Cloudflare (P-0.3).
  Staging's web is `*.vercel.app` and its API `*.fly.dev`: different sites, so D-024's
  `SameSite=Lax` refresh cookie never flows between them. Refresh and logout (T-3.4) could then
  only be tested locally.
  **The fix, approved 2 October 2026:** web at `staging.veloraapp.co.in`, API at
  `api.staging.veloraapp.co.in`, both DNS records DNS-only. The API nests under the web's name so
  staging's CSRF cookie, scoped to `staging.veloraapp.co.in`, never reaches production (D-055).
  The old address, `velora-staging-black.vercel.app`, redirects to the new one: left serving, it
  would be a live URL that looks like our product while CORS quietly refuses its API calls, and
  it's in old docs. Staging's `COOKIE_DOMAIN` stays unset until T-3.3 sets it.
  **Unblocked 2 October 2026:** the domain is bought (P-0.3, D-015), ahead of the trademark search
  (P-0.1), so a rename forced by that search would mean buying again.
  **Cookie scope settled:** staging's subdomains are the same site as production's, so a site-wide
  production cookie would reach staging. The refresh cookie is host-only on each API host
  (D-054), so neither environment's reaches the other; both cookies are named for their
  environment (D-055), so production's and staging's never collide.
  **Its own check can't prove a cookie flows:** nothing sets one before T-3.3. T-3.14's Done-when
  is that proof, a session surviving a reload on staging. Found planning T-1.22.
  **Done, proved by deploy run 36995339160** (commit `017f71a`, 2 October 2026): its smoke job,
  pointed at `https://api.staging.veloraapp.co.in` and `https://staging.veloraapp.co.in`, passed
  every check, including that the web is our build calling the new API and that CORS allows the
  new origin. Both certificates are Let's Encrypt's and verify; both records are DNS-only CNAMEs.
  Run by hand by Claude the same day, the check passes on that pair and fails on both old
  addresses: the old web address, which now 308-redirects to the new one (9 failures, CORS among
  them), and the old API address, which the new build doesn't call (1 failure). That the cookie
  flows is still T-3.14's to prove.
- [ ] P-34 · Move local and CI to Postgres 17, closing the gap with Supabase (D-047). Staging runs
  Postgres 17.11 with PostGIS 3.3.7; local and CI run 16 with PostGIS 3.4. Switch
  `infra/docker-compose.yml`, and with it CI (which starts the same compose services), to a pinned
  `postgis/postgis:17-*` image, run the full suite, and update CLAUDE.md's stack row. **This closes
  the gap, not eliminates it:** the `postgis:17` images ship PostGIS 3.5, not Supabase's 3.3, so
  PostGIS behaviour is only ever verified on staging. Consider matching Supabase's layout too — the
  extensions in an `extensions` schema rather than `public` — since that difference hid the bug
  `67e81c6c203d` fixed. Best done before discovery leans on PostGIS (T-6.2). Found setting up
  staging in T-1.22.
- [x] P-36 · Decide where the API and worker run, now that Fly won't provision in Mumbai. **Blocks
  T-1.22's Done-when. The decision is open, and the founder makes it fresh, not against a deadline.**
  - **What Fly said** (deploy run 36793830288, 2026-10-01 00:01 UTC, request ID
    `01M3TC93PM16F2PE40187YC8D7-iad`): "Region bom is deprecated and cannot have new resources
    provisioned. Please consider using an alternate region such as sin". `fly platform regions`
    (flyctl 0.4.110) no longer lists `bom`.
  - **Temporary or permanent is not confirmed.** The wording isn't Fly's capacity error, which reads
    "could not find a good candidate…", so waiting a day probably won't help. But Fly hasn't
    announced it: its region-consolidation post lists Mumbai as an active region, not among the
    retired ones. And in September 2025 a different `bom` refusal ("…organization is on a legacy or
    non-paid plan") turned out to be a Fly bug, fixed after a community post. **Next step: ask Fly
    support whether `bom` is retired for good or refused for this account, quoting the request ID.**
  - **Constraint:** Indian users' data (photos, phone numbers) stays in India until the DPDP lawyer
    session (P-0.7) says otherwise. Moving to Singapore is a legal and positioning question, not a
    latency tradeoff, and it's off the table for now. If `bom` is gone for good, the founder leans
    towards another host in Mumbai for the API and worker (for example AWS `ap-south-1` or Google
    Cloud Run `asia-south1`). That gets decided properly, with WebSocket support (D-025) checked,
    and recorded as a decision superseding D-023's region.
  - **Staging as it stood when this was filed** (it has deployed since; see T-1.22):
    - Supabase (Mumbai) is migrated to head.
    - Fly app `velora-api-staging` has five staged secrets, a shared IPv4 and a dedicated IPv6, and
      no machines.
    - Vercel project `velora-staging` exists but hasn't been deployed.
    - R2 isn't enabled.

    Until this is settled, every push to `main` runs `deploy.yml`, which migrates and then fails at
    its `api` job. That's harmless, but expect the red run.

  Found during T-1.22's first deploy.
  **Decided (D-048):** the API and worker run on Fly in Singapore; Postgres and Redis stay in Mumbai.
- [ ] P-37 · Give the staging smoke check a new identity marker before the web's providers move
  off marketing pages. **Due in whichever task moves them.** Worst case: every deploy's smoke
  check fails with a misleading cause ("another site at that URL, or NEXT_PUBLIC_API_URL unset"),
  and the quick fix is to weaken the check, which reopens the hole where another company's site
  passed for our staging (T-1.22). The check passes because `/`'s scripts contain the API's URL,
  and they do only because the root layout mounts `QueryProvider`, which imports `src/lib/api.ts`.
  A task that moves the providers to the `(app)` and `(auth)` layouts, for example to make the
  landing page lighter, must replace the marker in the same commit with one that only our build
  carries, and prove it both ways: it fails against another site and passes against ours. The
  coupling is also written above the check in `scripts/staging-smoke`.

  Found while planning T-2.1.
- [ ] P-38 · Seed Phagwara's areas, replacing Bengaluru's. **Due before T-4.10** (on its Needs
  line). Worst case: someone in Phagwara who denies location access is offered a list of
  Bengaluru neighbourhoods, so their area, and every distance shown to them, is wrong. D-013 is
  now Phagwara, but the reference-data migration seeded 40 Bengaluru neighbourhoods as the
  decision's old default, and `make seed`'s profiles sit in Bengaluru localities. A new data
  migration replaces the areas (never an edit of the merged one, rule 11), and the dev seed's
  localities follow. Label the centroids with who drafted and who reviewed them, as T-1.14's were.

  Found while planning T-2.2.
- [ ] P-39 · Delete the Firebase user right after sign-in. **After T-3.14 works plainly.** Worst
  case without it: every user's phone number sits in Firebase's records in the United States for
  as long as the account exists, and up to 180 days after we delete it. Deleting the Firebase user
  straight after the token exchange shrinks that to the sign-in itself. Google's abuse-prevention
  copy stays either way (D-048), so this shrinks the footprint, not the disclosure on `/privacy`.
  Kept out of T-3.14 on purpose: auth is where cleverness causes outages, so sign-in works plainly
  first.

  Found while planning T-2.2.
- [ ] P-40 · Stop uvicorn trusting every proxy's `X-Forwarded-For`. **Before anything reads
  `request.client`.** Worst case: code that reads `request.client.host` gets an address the client
  chose, so a limit, a ban or an audit-log entry built on it can be forged. The image runs uvicorn
  with `--proxy-headers --forwarded-allow-ips '*'`, which fills `request.client` from the leftmost
  `X-Forwarded-For` entry, and the client writes that entry. Nothing reads it today: per-IP limits
  read `Fly-Client-IP` (D-056). Drop `--proxy-headers`, or trust only Fly's proxy, and test that a
  forged header doesn't change `request.client`.

  Found in T-2.3.
