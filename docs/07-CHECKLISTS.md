# 07 · Checklists

`/review` walks the relevant sections below. Copy a section into the PR description and tick it.

## A. Every task

- [ ] Only files listed in the approved plan were changed
- [ ] Every acceptance item in `05-PLAN.md` for this task is met
- [ ] Tests added in the same change; `make lint test` clean
- [ ] No `print`, no commented-out code, no stray TODO without a Proposed task
- [ ] Any test that implements an item on `06-TESTING.md`'s never-skip list carries
      `@pytest.mark.critical`, so CI runs it first
- [ ] No literal prices, limits or durations in code — read from `action_prices` / `app_config`
- [ ] No hex colours outside `tokens.css`; no user-facing string outside `en.ts`
- [ ] Types regenerated (`make types`) if any API schema changed
- [ ] Checkbox ticked; commit message has the task ID

## B. New API endpoint

- [ ] Listed in `04-API.md` (add it there first if missing — that's a contract change, ask)
- [ ] Pydantic request and response models; response never includes `body_raw`, phone, tokens
- [ ] Correct auth dependency (🔓 🔐 ✅ 🛡)
- [ ] Rate limit if it can be spammed or costs money
- [ ] Participant/ownership check (can user A read user B's thing? test it)
- [ ] Blocks respected (blocked → 404 or `BLOCKED`)
- [ ] Error codes from the table in `04-API.md` only
- [ ] Tests: happy path, unauthenticated, wrong user, each error code
- [ ] Paid? → `price_for()` + `wallet.debit()` in the **same transaction** as the thing bought

## C. New migration

- [ ] One logical change; name describes it
- [ ] `downgrade()` works: `make migrate && make migrate-down && make migrate`
- [ ] Constraints and indexes from `03-SCHEMA.md` included, named by convention
- [ ] Large tables: new index created `CONCURRENTLY` (separate non-transactional migration)
- [ ] Never edits a migration already on `main`
- [ ] SQLAlchemy model updated in the same commit

## D. New screen (web)

- [ ] Matches the prototype layout; tokens only
- [ ] Loading (skeleton), empty, and error states all designed and reachable
- [ ] Works at 360 px wide and at 1280 px
- [ ] Server data via a hook in `src/lib/queries/`; mutations invalidate the right keys
- [ ] Optimistic update only where rollback is handled
- [ ] Buttons disabled while submitting; double-tap can't double-charge
- [ ] Keyboard and screen-reader usable; icon buttons have `aria-label`
- [ ] Error codes mapped to friendly copy in `en.ts`

## E. Security (run fully at T-9.13, partially on every money/auth PR)

- [ ] Refresh cookie `HttpOnly; Secure; SameSite=Lax`, scoped to `/v1/auth`, host-only: no `Domain` attribute (D-054)
- [ ] CSRF header required on refresh
- [ ] Both auth cookies named for their environment (`refresh_prod`, `csrf_staging`, …), never a bare name (D-055)
- [ ] Access token never in localStorage, never in a URL
- [ ] WebSocket uses single-use tickets only
- [ ] Webhook signature verified on raw body before JSON parsing
- [ ] Webhook and wallet idempotency tests pass
- [ ] All user-owned resources checked for ownership (IDOR sweep of every `/{id}` route)
- [ ] Presigned URLs short-lived; private bucket never public; content-type and size enforced
- [ ] Uploaded images re-encoded; EXIF gone
- [ ] Rate limits active on OTP, swipes, messages, reports
- [ ] Firebase App Check enforced, and a send-code request without an App Check token refused (P-68: by its effect, not the switch); billing alert set (it alerts, never caps); `velora-ic` still on plain Firebase Authentication, so Firebase's fixed 3,000 SMS a day still applies (no console field caps SMS: P-0.18); `/auth/firebase` throttled per IP and per phone; ID tokens single-use
- [ ] No secrets in repo (gitleaks) or in the web bundle (grep build output for key prefixes)
- [ ] Admin routes role-checked; every admin action in `audit_log`
- [ ] CSP enforced; no `unsafe-eval`
- [ ] Logs contain no phone numbers, OTPs, tokens, or message bodies
- [ ] Dependencies scanned (`pip-audit`, `pnpm audit`) — no high/critical

## F. Before go-live (T-9.15)

- [ ] **Before launch, and by 2 January 2027 whatever the go-live date: the Google Cloud billing
      account converted from its free trial to paid, after App Check is enforced and proved by
      its effect** (P-0.18, in that order; P-68), or sooner if the trial's credit runs out first.
      On that date Firebase Auth stops and nobody signs in, staging or production, with nothing
      wrong in the code and no deploy to blame. Budgets alert; they never cap. No console field
      caps SMS: Firebase's fixed 3,000 a day is inherited, and only on plain Firebase
      Authentication.
- [ ] Legal pages reviewed by the founder (P-0.7), every legal fact filled in (D-053), Grievance Officer published
- [ ] **No published word claims verification** — in the app, the site, the stores, ads or posts: nothing says a person is verified, real, live or who they say they are, unless P-160 has measured the face-match threshold and the founder has decided what may be said (D-260, D-262). `en.ts` is held by `web/src/i18n/claims.test.ts`; words outside the repo are this line's to check
- [ ] Sign-in works on 3 networks (Jio, Airtel, Vi) on the live provider; if using Path B, DLT template approved
- [ ] Firebase App Check rejects a request from an unauthorised domain
- [ ] Razorpay live keys; webhook URL set to production; one real purchase + refund done
- [ ] Moderation and face-match providers on live keys; test image rejected correctly
- [ ] Production DB: PITR on; restore drill done (T-9.14)
- [ ] Sentry + alerts firing to your phone (trigger a test error)
- [ ] Seed data NOT in production (only reference data)
- [ ] `ENV=production` blocks all test-only endpoints (OTP peek, clock control, fake webhook)
- [ ] Moderator account created; runbook printed
- [ ] Beta invite-only flag on
- [ ] Tested end-to-end on the ₹10k Android phone on mobile data

## G. Weekly ops (from beta onward)

- [ ] Report queue: zero items older than 24 h
- [ ] Fraud: review every `freeze` and a sample of `shadow` (`audit_log`'s `fraud.freeze` and `fraud.band` rows, by the system user, D-905); lift a wrong freeze with `python -m app.tools.unfreeze` (D-906)
- [ ] Ledger reconciliation cron: zero mismatches
- [ ] Payments: dashboard totals match `payments` table
- [ ] Metrics review (T-10.3) — write 3 lines in `docs/weekly.md`
- [ ] Sentry: top 5 errors triaged into Proposed tasks
- [ ] Backup still running (check last restore point)
