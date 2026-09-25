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
- [ ] **P-0.2** Register company (OPC recommended) → PAN, GST, current account.
- [ ] **P-0.3** Buy domain `velora.app` (or chosen name). Point DNS to Cloudflare.
- [ ] **P-0.4** DLT (needed only to move off Firebase later — start it anyway, it is slow): entity → header → OTP template `{#var#} is your Velora verification code. Valid for 5 minutes. Do not share it.`
- [ ] **P-0.5** MSG91 account; link DLT IDs; send one test SMS to yourself.
- [ ] **P-0.12** Firebase: project, Phone provider on, App Check + reCAPTCHA Enterprise enforced, authorised domains, daily SMS quota cap, billing alert. Confirm the **real per-SMS price for IN** in the billing console and write it into D-035.
- [ ] **P-0.6** Create accounts: GitHub, Supabase (Mumbai), Upstash, Cloudflare (R2 on), Fly.io (paid plan for `bom`), Vercel, Sentry, Sightengine, AWS (Rekognition, `ap-south-1`).
- [ ] **P-0.7** Lawyer session: gender-based pricing, IT Rules 2021 obligations, DPDP consent. Get Terms, Privacy, Refund policy drafted.
- [ ] **P-0.8** After T-2.2 is live: apply to Razorpay and Cashfree.
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
- [ ] **Needs:** T-1.4
- [ ] `alembic init -t async`; `env.py` reads `DATABASE_URL`; `target_metadata` from a shared `Base` with naming convention (`pk_`, `fk_`, `uq_`, `ix_`, `ck_`).
- [ ] `make migrate`, `make migration m="…"`, `make migrate-down`.
- [ ] Test harness: `test_engine` in `tests/conftest.py` migrates `velora_test` to head once per session (moved from T-1.5).
- [ ] mypy: allow untyped code in `api/alembic/` (strict stays on `app/` and `tests/`, T-1.6); add it to `[tool.mypy] files` once its layout exists.
- [ ] **Done when:** an empty revision upgrades and downgrades cleanly.
- [ ] **Commit:** `chore(db): alembic async setup [T-1.7]`

### T-1.8 → T-1.13 · Schema migrations
One migration per task, each with a working `downgrade()`. Build exactly `03-SCHEMA.md`.
- [ ] **T-1.8** Extensions, all enums, `set_updated_at()` trigger function. — `feat(db): extensions and enums [T-1.8]`
- [ ] **T-1.9** Identity + profile: `users`, `sessions`, `banned_identities`, `profiles`, `areas`, `interests`, `profile_interests`, `photos`, `verifications`, plus trigger making `users.gender`/`users.dob` immutable once non-null. — `[T-1.9]`
- [ ] **T-1.10** Discovery + conversations: `swipes`, `profile_views`, `liked_you_reveals`, `matches`, `threads`, `messages`, `message_unlocks`, `thread_clears`. — `[T-1.10]`
- [ ] **T-1.11** Album, kudos, safety: `album_requests`, `kudos`, `gifts`, `gift_sends`, `blocks`, `reports`, `fraud_scores`, `fraud_events`. — `[T-1.11]`
- [ ] **T-1.12** Money: `wallets`, `ledger_entries` (+ no-update/delete trigger), `action_prices`, `credit_packs`, `payments`, `refund_requests`, `referrals`. — `[T-1.12]`
- [ ] **T-1.13** Notifications + ops: `push_subscriptions`, `notification_prefs`, `notifications`, `audit_log`, `app_config`, `waitlist`. — `[T-1.13]`
- [ ] **Done when (each):** `make migrate && make migrate-down && make migrate` succeeds; SQLAlchemy models match.

### T-1.14 · Reference data migration
- [ ] **Needs:** T-1.13
- [ ] Data migration inserting `interests` (21), `gifts` (6, D-016), `action_prices` (D-004), `credit_packs` (D-005: 25/₹1,500 · 50/₹2,500 · 75/₹3,375 · 100/₹4,000, variant A; variant B entry pack ₹999/25 for the beta test), `app_config` seeds, `areas` for the launch city.
- [ ] **Done when:** counts match; re-running is a no-op (`ON CONFLICT DO NOTHING`).
- [ ] **Commit:** `feat(db): reference data [T-1.14]`

### T-1.15 · Dev seed
- [ ] **Needs:** T-1.14
- [ ] `make seed` (dev only, refuses if `ENV=production`): the 20 prototype profiles with approved placeholder photos in MinIO, locations spread in the launch city, 3 of the women pre-liking the test man; a test man (`+91 90000 00001`, 60 credits), a test woman (`+91 90000 00002`, verified), a moderator.
- [ ] **Done when:** `make seed` twice doesn't duplicate.
- [ ] **Commit:** `chore(dev): seed script [T-1.15]`

### T-1.16 · Schema tests
- [ ] **Needs:** T-1.13, T-1.5
- [ ] Tests that prove: `wallets.balance` can't go negative; ledger UPDATE/DELETE raises; `threads` rejects `user_low >= user_high`; `users.gender` can't change once set; username regex enforced; unique `(sender_id, client_msg_id)`.
- [ ] **Commit:** `test(db): constraint tests [T-1.16]`

### T-1.17 · Web skeleton
- [ ] **Needs:** T-1.1
- [ ] `pnpm create next-app web` — TypeScript, App Router, Tailwind, ESLint, `src/` dir.
- [ ] `tsconfig` strict + `noUncheckedIndexedAccess`; path alias `@/`.
- [ ] Route groups: `(marketing)`, `(auth)`, `(app)`, `admin` with placeholder pages.
- [ ] `src/styles/tokens.css` from `08-DESIGN.md`; Tailwind theme reads the CSS variables.
- [ ] `src/i18n/en.ts` string dictionary + `t()` helper.
- [ ] Verify the prettier and eslint pre-commit hooks from T-1.6 run on `web/` files; prettier must be a `web/` devDependency (create-next-app adds ESLint, not Prettier).
- [ ] **Done when:** `pnpm dev` shows placeholders; `pnpm lint && pnpm tsc --noEmit` clean.
- [ ] **Commit:** `feat(web): next.js skeleton with tokens [T-1.17]`

### T-1.18 · Web data layer
- [ ] **Needs:** T-1.17, T-1.3
- [ ] `make types` → `openapi-typescript $API/openapi.json -o web/src/types/api.ts`.
- [ ] `src/lib/api.ts` — typed fetch wrapper: base URL, JSON, attaches access token, parses the error envelope into `ApiError {code, message, details, status}`.
- [ ] `QueryClientProvider` in root layout; `src/lib/queries/keys.ts` (query key factory).
- [ ] Zustand `src/store/session.ts` (access token in memory, user id).
- [ ] **Done when:** a dev page calls `/healthz` via a query hook and renders the result.
- [ ] **Commit:** `feat(web): api client, query setup, type generation [T-1.18]`

### T-1.19 · UI primitives
- [ ] **Needs:** T-1.17
- [ ] From the prototype, in `src/components/ui/`: `Button` (primary/ghost/danger, sm/md, loading), `Chip`, `Sheet` (bottom on mobile, centred on desktop, focus trap, Esc closes), `Field`, `TextArea` (counter), `Toast` + `useToast`, `Icon` (lucide-react), `Avatar`, `Spinner`, `EmptyState`, `ErrorState`, `Toggle`, `Skeleton`.
- [ ] `/dev/ui` page (dev only) showing every primitive in every state.
- [ ] Vitest + Testing Library; one test per primitive (renders, interaction, a11y role).
- [ ] **Commit:** `feat(web): ui primitives [T-1.19]`

### T-1.20 · CI
- [ ] **Needs:** T-1.5, T-1.6, T-1.19
- [ ] GitHub Actions `ci.yml`: job `api` (postgis + redis services, `uv sync`, migrate, ruff, mypy, pytest); job `web` (pnpm install, lint, tsc, vitest, `next build`). Required on PRs to `main`.
- [ ] **Commit:** `ci: api and web pipelines [T-1.20]`

### T-1.21 · Provider adapters
- [ ] **Needs:** T-1.3
- [ ] `app/core/providers/`: `SmsProvider`, `PaymentsProvider`, `ModerationProvider`, `FaceMatchProvider`, `PushProvider`, `StorageProvider` as `Protocol`s. Each has `Fake…` (in-memory, records calls; fake SMS logs the OTP to console in local only) and a real implementation stub raising `NotImplementedError`. Selection by env var.
- [ ] `fake_providers` fixture in `tests/conftest.py` overriding every provider with its fake (moved from T-1.5).
- [ ] **Done when:** tests can assert "an SMS was sent to X" via the fake.
- [ ] **Commit:** `feat(api): provider interfaces with fakes [T-1.21]`

### T-1.22 · Staging deploy
- [ ] **Needs:** T-1.4, T-1.17, P-0.6
- [ ] `api/Dockerfile` (multi-stage, uv, non-root, gunicorn + uvicorn workers). `infra/fly.api.toml` and `infra/fly.worker.toml`, region `bom`, health check `/readyz`, release command `alembic upgrade head`.
- [ ] Supabase staging project (enable PostGIS, pg_trgm, citext); Upstash staging DB; R2 staging buckets.
- [ ] Vercel project for `web/` with staging env vars.
- [ ] GitHub Actions `deploy.yml`: on push to `main` → deploy staging API + worker; Vercel deploys web itself.
- [ ] **Done when:** staging web loads and staging `/readyz` is 200.
- [ ] **Commit:** `ci: staging deploy [T-1.22]`

---

# Sprint 2 — Public site (week 3)

### T-2.1 · Landing page
- [ ] **Needs:** T-1.19
- [ ] `(marketing)/page.tsx` from the prototype: header, hero, three feature cards, waitlist box, footer links. Server-rendered, no client JS except the waitlist form.
- [ ] **Done when:** Lighthouse mobile ≥ 90 performance, 100 accessibility on staging.
- [ ] **Commit:** `feat(web): landing page [T-2.1]`

### T-2.2 · Legal pages
- [ ] **Needs:** T-2.1
- [ ] `/terms`, `/privacy`, `/refunds`, `/contact` as MDX or TSX pages. Contact shows company name, address, support email, **Grievance Officer name + email** (IT Rules). Text from the lawyer (P-0.7); until then clearly marked placeholder.
- [ ] Footer links on every marketing page.
- [ ] **Done when:** all four reachable, linked, and printable.
- [ ] **Commit:** `feat(web): legal pages [T-2.2]`

### T-2.3 · Waitlist
- [ ] **Needs:** T-1.13, T-2.1
- [ ] API `POST /v1/waitlist {email, city?}` — validate email, citext unique (duplicate → 201 anyway), rate limit 5/min/IP.
- [ ] Web form with success state.
- [ ] **Commit:** `feat: waitlist [T-2.3]`

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
- [ ] **Needs:** P-0.3, T-1.22
- [ ] `velora.app` → Vercel prod; `api.velora.app` → Fly prod app; SSL issued. Prod DB/Redis/R2 created but empty.
- [ ] **Done when:** `https://velora.app` shows the landing page; `https://api.velora.app/healthz` is 200. → **Unblocks P-0.8.**
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
- [ ] **Needs:** T-3.2
- [ ] `POST /v1/auth/otp/verify`. Wrong code → attempts+1, `OTP_INVALID` with attempts left; 5th wrong → delete key, `OTP_TOO_MANY`. Correct → delete key.
- [ ] Find user by `phone_hash`, or create in **one transaction**: `users` (+ referral code), `profiles`, `wallets` (0), `notification_prefs`.
- [ ] Create session (family), set refresh cookie (`HttpOnly; Secure; SameSite=Lax; Domain=COOKIE_DOMAIN; Path=/v1/auth`), set readable `csrf` cookie, return `{access_token, user: Me}`.
- [ ] Refuse if user status `banned`.
- [ ] Tests: new user creates all 4 rows; existing user doesn't duplicate; banned → `ACCOUNT_BANNED`.
- [ ] **Commit:** `feat(auth): verify otp and create account [T-3.3]`

### T-3.4 · Refresh and logout
- [ ] **Needs:** T-3.3
- [ ] `POST /v1/auth/refresh`: require `X-CSRF` equal to `csrf` cookie; look up `token_hash`; if revoked → revoke whole family (reuse attack) → `SESSION_REVOKED`; else rotate (new session, old `revoked_at` + `replaced_by`).
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
- [ ] `POST /me/seeking {seeking, intent}` → advance.
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
- [ ] Access token in Zustand (memory only). On app load: call `/auth/refresh` once to restore a session.
- [ ] On any 401 `TOKEN_EXPIRED`: single-flight refresh, then retry the request once.
- [ ] `useMe()` query; `<OnboardingGate>` redirects to the correct step from `onboarding_step`; `(app)` routes require `done`.
- [ ] PIN lock screen: shown on load and after 5 min hidden if a PIN is set.
- [ ] **Commit:** `feat(web): auth session, refresh, route gates, pin lock [T-3.10]`

### T-3.11 · Web onboarding 1–7
- [ ] **Needs:** T-3.10, T-3.7
- [ ] Screens from the prototype: phone, OTP (4 boxes, paste support, resend timer from `resend_after_s`), DOB (native date input; under-18 message), gender (with lock warning), seeking + intent, name/hometown/city, username (debounced availability 400 ms, shows `velora.app/@name`).
- [ ] Each screen: submit disabled until valid; server errors shown inline from `ApiError.code` via `en.ts`.
- [ ] **Commit:** `feat(web): onboarding steps 1-7 [T-3.11]`

### T-3.12 · Web onboarding 8, 10, 11
- [ ] **Needs:** T-3.11, T-3.8, T-3.9
- [ ] About (40–300 counter), interests (exactly 5), PIN (set + confirm, skip). Photos (9) and selfie (12) come in Sprint 4 — route placeholder that says "coming next".
- [ ] **Commit:** `feat(web): onboarding about, interests, pin [T-3.12]`

### T-3.14 · Firebase phone sign-in (launch path)
- [ ] **Needs:** T-3.3
- [ ] **New dependencies (approved, recorded in D-035):** api `firebase-admin`; web `firebase`.
- [ ] Firebase console: project created, Phone provider enabled, **App Check with reCAPTCHA
  Enterprise enforced on Authentication**, authorised domains = `velora.app` + Vercel preview +
  `localhost`, daily SMS quota capped, billing alert set at a fixed rupee amount.
- [ ] `POST /v1/auth/firebase {id_token}`: verify signature and `aud`/`iss`/`exp` against Google's
  public keys (cached); require `phone_number` and `firebase.sign_in_provider == "phone"`;
  reject non-`+91` → `PHONE_NOT_SUPPORTED`; reject a reused `jti` (Redis until expiry) →
  `FIREBASE_TOKEN_INVALID`; throttle 10/IP/hour and 5/phone/hour.
- [ ] Then reuse the exact same service as T-3.3: banned check → find-or-create user + profile +
  wallet + prefs → session + cookies → `{access_token, user}`.
- [ ] Web: Firebase JS SDK on the phone screen (invisible reCAPTCHA), `signInWithPhoneNumber`,
  6-digit code box (Firebase codes are 6 digits, not 4 — the OTP screen adapts to
  `AUTH_PHONE_PROVIDER`), resend cooldown, friendly copy for `auth/too-many-requests`,
  `auth/invalid-phone-number`, `auth/code-expired`.
- [ ] Sign the user out of Firebase immediately after the exchange — we keep our own session.
- [ ] CSP updated for Firebase Auth and reCAPTCHA domains (follow-up to T-2.5).
- [ ] Tests: forged token rejected; expired rejected; reused token rejected; non-Indian number
  rejected; banned phone rejected; a valid token creates exactly one user.
- [ ] **Commit:** `feat(auth): firebase phone sign-in [T-3.14]`

### T-3.13 · E2E signup
- [ ] **Needs:** T-3.12
- [ ] Playwright against local stack with `AUTH_PHONE_PROVIDER=fake` (OTP read from a test-only endpoint enabled only when `ENV=local`): new man reaches the photos step; under-18 is refused and can't retry with the same number.
- [ ] One staging run against the real Firebase path using a Firebase **test phone number** (fixed code, no SMS sent, no cost).
- [ ] **Commit:** `test(e2e): signup flow [T-3.13]`

---

# Sprint 4 — Photos and verification (weeks 6–7)

### T-4.1 · Storage provider
- [ ] **Needs:** T-1.21, T-1.2
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
- [ ] **Needs:** T-4.2
- [ ] ARQ worker bootstrap (`workers/main.py`) + `make worker`.
- [ ] `moderate_photo(photo_id)`: fetch raw → Pillow open (reject if not an image) → `ImageOps.exif_transpose` → resize longest side 1600 → save JPEG q85 **without EXIF** → `ModerationProvider.check()` → approve (write public copy for `public` kind) or reject with reason (`nudity`, `minor_suspected`, `no_face`, `text_overlay`, `other`). `minor_suspected` also opens an internal report.
- [ ] Idempotent: re-running on an approved photo does nothing.
- [ ] Tests with the fake provider for approve and each reject path; test that output has no EXIF.
- [ ] **Commit:** `feat(worker): photo moderation pipeline [T-4.4]`

### T-4.5 · Selfie verification
- [ ] **Needs:** T-4.4
- [ ] `POST /verification/challenge` → random pose from a list (turn left, turn right, look up, smile) stored on the row. `POST /verification/{id}/submit {photo_id}` → enqueue `verify_selfie`.
- [ ] `verify_selfie`: re-encode; `FaceMatchProvider.compare(selfie, approved_public_photos)`; similarity ≥ 85 and exactly one face → `approved`, `users.is_verified = true`; else `rejected` with reason. Max 5 attempts / day.
- [ ] Selfies are never public and never shown to other users.
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
- [ ] **Needs:** T-3.5
- [ ] `PUT /me/location` accepts `{lat,lng}` (must be inside India bounding box) or `{area_id}` (uses centroid). `GET /areas?city=`.
- [ ] Web: onboarding asks permission once with a clear reason; on deny → area picker. Location refreshed on app open if > 6 h old.
- [ ] **Commit:** `feat(profiles): location [T-4.10]`


---

# Sprint 5 — Credits core (week 8)

Built before discovery and chat because swipes, threads and unlocks all spend credits.

### T-5.1 · Wallet service
- [ ] **Needs:** T-1.12, T-1.5
- [ ] `wallet.service.debit(session, user_id, amount, reason, ref_type, ref_id, idempotency_key)` and `credit(...)`.
- [ ] Inside the caller's transaction: `SELECT … FROM wallets WHERE user_id = :u FOR UPDATE` → check `balance >= amount` else raise `INSUFFICIENT_CREDITS {required, balance}` → update balance → insert `ledger_entries` with `balance_after`.
- [ ] Idempotency: if `idempotency_key` already exists, return the existing entry and change nothing.
- [ ] `amount <= 0` → programming error (raise, don't silently accept).
- [ ] Publishes `wallet.updated` after commit (not before).
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
- [ ] Repository implements the query in `02-ARCHITECTURE.md §8` with feeds: `foryou` (ranked), `new` (joined ≤ 7 days first), `online` (active ≤ 5 min). Filters: intent[], verified.
- [ ] Excludes: self, swiped, blocked either way, hidden, not `done`, status ≠ active, fraud band `freeze`; `shadow` band users only shown to others in `shadow`.
- [ ] Response `Card`: id, first_name, age (null if hide_age), username, city, hometown, distance_km (null if hide_distance, else ≥ 1), intent, bio line (first 90 chars of about), main photo URL, is_verified, is_online, is_new.
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
- [ ] Match celebration sheet → "Open thread · 5 credits" / "Keep swiping".
- [ ] Empty states: no one nearby / filters too narrow (clear button).
- [ ] 60 fps on the test phone (check Chrome performance panel).
- [ ] **Commit:** `feat(web): discover deck [T-6.5]`

### T-6.6 · Search and @username
- [ ] **Needs:** T-6.3
- [ ] `GET /search?q=`: `@` prefix → exact-then-prefix username match (ignores distance/filters, still respects blocks/hidden); otherwise trigram on first_name/username + city/intent/interest matches within radius. `GET /users/by-username/{u}`.
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
- [ ] Public shareable page `velora.app/@username` (SSR): logged-out visitors see first name, age, city, main photo, and "Join Velora to message"; logged-in users are redirected to the in-app profile.
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
- [ ] `GET /packs`: active packs for the user's price-test variant (`users.id` hash → A/B, stable). `POST /payments/orders {pack_id}` + `Idempotency-Key`: copy amount + credits from the pack, compute first-purchase bonus, create provider order, insert `payments` (`created`), return checkout params.
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
- [ ] `POST /refund-requests` (own payment, within 7 days, only if credits from it are unspent — compute from ledger). Admin processes the gateway refund manually in MVP and records it (`payments.status = refunded`, `wallet.debit(refund)` of the unspent credits).
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
  either "Free" or the credit price. Free ones show the remaining daily count.
- [ ] Sending: optimistic disable, success toast, balance updates from `wallet.updated`.
  `GIFT_LIMIT_REACHED` / `GIFT_COOLDOWN` → friendly inline copy with when they can send again.
  `INSUFFICIENT_CREDITS` → store sheet.
- [ ] Received gifts row on her own profile and in You tab; toggle `show_gifts` in privacy settings.
- [ ] Notification opens the sender's profile.
- [ ] **Commit:** `feat(web): gifts on profile [T-8.10]`

### T-8.6 · Referrals
- [ ] **Needs:** T-8.2
- [ ] `POST /referrals/apply {code}` only before onboarding `done`, not own code, once. Reward both (credits from `app_config`) when the referee completes selfie verification or first purchase, whichever first; idempotent. `GET /referrals/me`.
- [ ] **Commit:** `feat(referrals): codes and rewards [T-8.6]`

### T-8.7 · Web store and checkout
- [ ] **Needs:** T-8.2, T-5.5
- [ ] Store sheet from the prototype (packs, per-credit and per-thread price, first-purchase banner). Load Razorpay Checkout script on demand. On success callback → poll `/payments/{id}` every 1.5 s (max 60 s) → toast + wallet refresh. Failure/dismiss → "Payment didn't go through" sheet with retry.
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
- [ ] On ban: find credits other users spent on this person in the last 7 days (threads opened with them, voice unlocks, album requests) → `wallet.credit(refund_banned_partner)` each, idempotent per ref, notify.
- [ ] **Commit:** `feat(safety): refunds for banned partners [T-9.3]`

### T-9.4 · Notifications
- [ ] **Needs:** T-7.4
- [ ] VAPID keys; `POST/DELETE /push/subscriptions`; `send_push` worker (drop subscriptions on 404/410); notification prefs; in-app `notifications` list. Kinds: match, message (only if not connected), like, knot requested/accepted, thread expiring, album decided, low balance.
- [ ] Web: Serwist service worker (push + notificationclick → open the right route), permission asked **after the first match**, not on load; generic-text option; iOS note when not installed.
- [ ] **Commit:** `feat(notifications): web push and in-app list [T-9.4]`

### T-9.5 · Admin panel
- [ ] **Needs:** T-9.2
- [ ] API: all `/admin/*` routes in `04-API.md`, `require_role(moderator)`; credit grants and bans `admin` only; every call writes `audit_log`; viewing messages of a thread logs who looked and why (reason required).
- [ ] Web `/admin`: metrics tiles, report queue with SLA timer (24 h), user search + detail (photos, reports, fraud signals, ledger, threads), moderation queue (approve/reject), actions with confirmation dialogs, audit log.
- [ ] **Commit:** `feat(admin): moderation panel [T-9.5]`

### T-9.6 · Settings and data rights
- [ ] **Needs:** T-3.5
- [ ] Hide profile, hide age, hide distance, show kudos; pause (hidden + no notifications); export (JSON of own data, generated by worker, signed link valid 24 h); delete (status `deleted`, profile hidden immediately, anonymised after 30 days by cron; payments and ledger kept, detached from identity).
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
- [ ] **Needs:** T-1.22
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
- [ ] **Needs:** T-9.13, T-9.14, P-0.5, P-0.8
- [ ] Production env: real SMS, real Razorpay live keys + webhook URL, real moderation and face match, VAPID keys. Run the pre-launch checklist in `07-CHECKLISTS.md`. Do one real ₹ purchase yourself and refund it.
- [ ] **Commit:** `chore(release): v1.0.0 [T-9.15]`

---

# Sprint 10 — Closed beta operations (weeks 16–19)

- [ ] **T-10.1** Invite codes: signup requires a code during beta (`app_config.beta_invite_only`); women's codes unlimited, men's limited per code.
- [ ] **T-10.2** Product analytics (PostHog, EU/India region if available): events `signup_step_completed`, `swipe`, `match`, `thread_opened`, `message_sent`, `knot_tied`, `thread_expired_unanswered`, `purchase_started`, `purchase_paid`, `report_filed`. No message content, no phone numbers.
- [ ] **T-10.3** Metrics queries for the weekly review: D1/D7 retention, thread → knot rate, % threads expiring with zero replies, paying conversion (men), revenue per paying user, reports per 100 users, active gender ratio.
- [ ] **T-10.4** Price test: variant A (₹1,500 / 25 credits) vs B (₹999 / 25) assigned 50/50; compare revenue per paying man after 3 weeks.
- [ ] **T-10.7** First-thread-free test (risk R1 in `09-RESEARCH.md`): half of new men get their first thread free. Measure paying conversion, threads per man, and revenue per man — not just the free-thread take-up.
- [ ] **T-10.5** Moderator runbook: report handling per reason, SLA, escalation (minor suspected → immediate ban + preserve evidence), canned replies.
- [ ] **T-10.6** Feedback loop: in-app "Send feedback" → `feedback` table; weekly triage into Proposed tasks.

---

# Backlog — after beta (Sprint 11+)

Each becomes a full task with steps when it's pulled in.

| ID | Feature | Notes |
|---|---|---|
| B-1 | Voice calls (knots only, 4 cr/min, first 60 s free) | Agora Web SDK, server-minted tokens |
| B-2 | Video calls (10 cr/min) + live frame moderation | biggest cost line — check unit economics first |
| B-3 | Vibe Room (3-min anonymous text, mutual reveal → thread) | needs strong moderation |
| B-4 | Boost (30 cr / 30 min) | ranking multiplier |
| B-5 | Who viewed you (15 cr reveal) | `profile_views` already recorded in T-6.3 |
| B-6 | Wink (2 cr) | |
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
- [ ] P-08 · `TEST_REDIS_URL` override — `TEST_DATABASE_URL` can be overridden but the test Redis
  is fixed at `127.0.0.1:6379/1`. If T-1.20's CI runs Redis anywhere else, the harness reports the
  stack unreachable and CI hard-fails by design. Add the override alongside T-1.20. Found in review
  of T-1.5.
- [ ] P-09 · Run gitleaks in CI — the pre-commit hook only protects clones that ran `make hooks`,
  and `git commit --no-verify` skips it. T-1.20's CI steps list ruff, mypy and pytest but not
  gitleaks, so nothing server-side enforces checklist E's "no secrets in repo". Add a
  `gitleaks git` step to T-1.20's `api` job. Found in review of T-1.6.
- [ ] P-10 · Hooks must work from GUI git clients — the ruff and mypy hooks call `uv` by name. VS
  Code's Source Control panel (which the user commits from) and other GUI clients run hooks
  without the shell profile, so `uv` may not be on `PATH` and every commit fails. Resolve `uv`
  robustly (absolute path or a wrapper that locates it) and test a commit from VS Code. Found in
  review of T-1.6.
