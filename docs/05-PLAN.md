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
  **Classes 9, 42 and 45 searched on 3 October 2026, but not on the registry** (founder; findings
  in D-015). IP India's public search returned an empty page, so the search ran on mirror
  databases: no mark in those classes, and the only registered VELORA in India is in class 21,
  kitchen utensils. A mirror is only as current as its last copy of the registry, so that can't
  tick this box. US marks turned up too; they matter only at a US store listing or in US
  marketing (D-015, B-15).
  **Still owed:** the same search, Nice classes 45, 9 and 42 as Claude mapped them, on IP India's
  own public search once it answers. D-015 was closed and the domain bought (P-0.3) before it, so
  a conflict found there means a new name and a new domain.
- [ ] **P-0.2** Register company (OPC recommended) → PAN, GST, current account. Then fill the missing facts in `web/src/lib/legal.ts` (D-053), and change Terms' "Who we are" to name the company directly instead of pointing to the contact page: Terms should name the entity it binds.
  **The four legal facts are in** (the founder, 2 October 2026; D-058): a sole proprietorship,
  not the OPC recommended above, named "Shubham Kumar, sole proprietor", word for word as the
  PAN and bank account have it; the registered office in Hajipur; the courts at Hajipur; Shubham
  Kumar as Grievance Officer. They're in `legal.ts`, and Terms now names the proprietor directly.
  **Still open, for the founder to confirm separately:** PAN, GST and the current account. T-2.6
  stays blocked on P-0.3's two mailboxes: four of the six legal facts.
  **3 October 2026:** the mailboxes are in (P-0.3), so all six legal facts are known and a
  production build lets the legal pages through (D-053).
- [x] **P-0.3** Buy the domain (D-015 says why this one). Move its nameservers to Cloudflare. Then set up the support and Grievance Officer mailboxes: their addresses are the `supportEmail` and `grievanceOfficerEmail` facts in `web/src/lib/legal.ts`, and production can't build without them (D-053). Put each address there once it has received and sent a test message, and in the same change add Zoho to `/privacy` (`web/src/i18n/en.ts`) in both places: the list of who handles user data, since from then on it holds every support and grievance email, and "Where your data is", which lists what stays in India (D-048): that mail does, in Zoho's India data centre.
  **The domain is done:** `veloraapp.co.in`, registered 2 October 2026 with Hostinger, expiring
  2 October 2027. Claude read both dates and the registrar from the public WHOIS the same day.
  WHOIS privacy and auto-renewal are on and the registrant email is verified, per the founder.
  Web at the apex, API at `api.veloraapp.co.in` (T-2.6).
  **DNS goes to Cloudflare** (founder, 2 October 2026): T-4.1's R2 custom domain needs the zone
  there, and P-33's staging records go there too.
  **The mailboxes are on Zoho Mail** (founder, 2 October 2026): `support@veloraapp.co.in` and
  `grievance@veloraapp.co.in`. Planned on the free tier (five users, one domain), set up as two
  aliases on one paid user. Zoho sends as well as receives, so grievance acknowledgements go out
  from the grievance address. **Sign up on Zoho's India data centre (`zoho.in`):** it is chosen
  once and hard to move. The MX records point at Zoho; add its SPF and DKIM records and a DMARC
  record too, or those replies land in spam.
  **Rejected: Cloudflare Email Routing.** It's free but only forwards, so replies would go out from
  a personal Gmail address, which undercuts the Grievance Officer section (D-052).
  **Order:** nameservers first, then the mailboxes, then P-33.
  **Nameservers moved, 2 October 2026:** the `.in` registry delegated the domain to Cloudflare
  (`aaron` and `lilyana.ns.cloudflare.com`) by 14:58 IST, read from the registry by Claude. Both
  answered for the zone, with Hostinger's parking A and MX records gone; there was no DNSSEC to
  switch off. P-33 started from there.
  **The mailboxes, 3 October 2026:** both addresses are aliases on one paid Zoho Mail user in
  Zoho's India data centre, so support and grievance mail stays in India (D-048). They're in
  `legal.ts`, and `/privacy` names Zoho in both places this task asks for.
  **Proved by the mail, not a status page** (founder): a message from an outside account reached
  `grievance@` and a reply came back. Gmail's own `Authentication-Results` line on the reply read
  `dkim=pass` with `header.s=zmail` and `spf=pass` with `smtp.mailfrom=grievance@veloraapp.co.in`:
  Google checking the signature against the key in our DNS, not a checker reporting that a
  record exists.
  **That test's `dmarc=pass` wasn't Gmail's verdict.** Claude first put it down to Hostinger's
  stale zone (below); the founder found it was worse, and wrote it down in these words: "Gmail's
  own Authentication-Results line carried only dkim=pass and spf=pass. The dmarc=pass sat inside
  arc=pass(...), which is Gmail relaying what Zoho's own ARC seal asserted. So I quoted a
  vendor's self-report as the receiving server's verdict." It's a sharper version of the same
  trap: not only "which DNS answered" but "whose assertion am I reading". Our zone had no DMARC
  record then: Claude read its absence at both of our nameservers.
  **DMARC is `v=DMARC1; p=quarantine`** (founder, 3 October 2026), for two reasons, the second
  deciding. Only Zoho sends as this domain, so mail claiming to come from it that Zoho didn't
  send goes to spam, including mail posing as `support@` or `grievance@`. And the value tells the
  zones apart: a verdict showing `p=QUARANTINE` can only have come from ours, since Hostinger's
  stale record says `p=none`. Claude read it the same day from both of our nameservers, as
  authoritative answers, along with the MX records (`mx`, `mx2` and `mx3.zoho.in`), SPF
  (`v=spf1 include:zoho.in ~all`), the `zmail` DKIM key and Zoho's verification record.
  **Then Gmail's own verdict, for each address** (founder, 3 October 2026): each alias received a
  message from an outside account and replied, `grievance@` at 02:52 IST and `support@` at 03:11.
  On both replies Gmail's own line read `dkim=pass` with `header.i=@veloraapp.co.in` and
  `header.s=zmail`; `spf=pass` with that alias as `smtp.mailfrom`, so each line belongs to its own
  address, not both to one mailbox; and, as its own clause outside `arc=pass(...)`,
  `dmarc=pass (p=QUARANTINE sp=QUARANTINE dis=NONE) header.from=veloraapp.co.in`. Both went out
  from `103.117.158.11`, Zoho's India sender `sender-op-o11.zoho.in`: Claude read the name both
  ways, reverse and forward.
  **Zoho's own "verify all records" page showed MX and DKIM failing** while both were live, as
  the founder confirmed against a public resolver: Zoho's resolver had cached their earlier
  absence. A vendor's status indicator is a claim; the behaviour is the proof.
  **Not added, on purpose: two ZeptoMail records Zoho offered.** ZeptoMail, Zoho's service for
  sending transactional mail, is off. Don't "fix" the gap: the records come with whatever task
  turns ZeptoMail on.
  **Hostinger's old zone: emptied, not removed** (founder, 3 October 2026). After the move, its
  nameservers kept serving their own MX records (`mx1` and `mx2.hostinger.com`) and a `p=none`
  DMARC record. A resolver still holding the old delegation would deliver mail for `grievance@`,
  the address the legal pages publish, to Hostinger, where no mailbox exists. Hostinger's panel
  deletes only record by record, with no way to delete the zone, so the founder deleted all 11,
  both MX records, the SPF and the DMARC among them. **That's the state we ended up in, not the
  one we aimed for:** Hostinger's nameservers still answer for the domain, with authority, for an
  empty zone. A removed zone would answer `REFUSED`, as they do for a domain they don't host, so
  a resolver still holding the old delegation would fail for a while and retry until it found
  ours. An empty zone tells it there's nowhere to deliver, and a sender can bounce. That window
  closes as those resolvers' copies of the old delegation expire: 24 hours after the move, for
  most.
  **The deletion took time to reach every answer** (read by Claude): at 03:30 IST, Hostinger's
  IPv4 addresses already served the empty zone, at a new serial (`2026100205`), while its IPv6
  addresses still served the deleted MX and `p=none`, at full TTLs that didn't count down: a copy
  that hadn't caught up. This network's own resolver (Jio's) still returned Hostinger's MX in one
  of three tries at 03:32. For the next hour the IPv6 answers flipped between old and new. From
  04:34 all four addresses served the empty zone, three checks in a row five minutes apart, and a
  burst of 80 queries at 04:45 found no old answer, with serial `2026100205` everywhere. By then
  Jio's resolver returned only Zoho's MX.
  **D-053's gate, both ways:** on `main`, a production build (`APP_ENV=production`) refused and
  named the Grievance Officer's email and the support email (P-0.3); with the two addresses in,
  it builds, and the built `/contact` shows both. T-2.6 no longer waits on the mailboxes.
- [ ] **P-0.4** DLT (needed only to move off Firebase later — start it anyway, it is slow): entity → header → OTP template `{#var#} is your Velora verification code. Valid for 5 minutes. Do not share it.`
- [ ] **P-0.5** MSG91 account; link DLT IDs; send one test SMS to yourself.
  **When this is done (D-066):** revisit the OTP send limits, the global daily cap and the ₹0.20
  price behind D-066's figures before Path B is switched on, and build P-46, the MSG91 client.
- [ ] **P-0.12** Firebase: project, Phone provider on, App Check + reCAPTCHA Enterprise enforced, authorised domains, daily SMS quota cap, billing alert. Confirm the **real per-SMS price for IN** in the billing console and write it into D-035.
  **Never add a test phone number to a project production uses (D-065):** its fixed code signs anyone in as that number wherever the project's tokens are accepted, production included, and in India the number may be a real person's (D-064).
- [ ] **P-0.13** Create the Google Cloud billing account and complete India's identity verification. **Owner: the founder, Shubham Kumar. Start: 3 October 2026. Due: 30 days after the account is created, when Google suspends an unverified Indian account; by 2 November 2026 if it's created on the start date.** Blocks T-3.14 (Firebase's Blaze plan bills to this account) and P-49's move (the Compute Engine VM does too). Started late, the 30-day clock is what stalls T-3.14.
  **How:** an Indian billing address means Google's mandatory identity verification. As an individual: PAN or e-Aadhaar through DigiLocker, and proof of address. As a business: a GST or Udyam certificate. **GST:** the advisor directing T-3.2 to T-3.10 says Velora has none, deliberately, below the threshold; P-0.2 still lists GST as unconfirmed, so the founder confirms it there. Without GST or a Udyam registration, it goes through as an individual.
  **If the payment method is refused** (AWS's was, P-0.6), write down exactly what Google said, as P-36 did for Fly, before trying anything else.
- [ ] **P-0.14** Decide where the registered office is, before `v0.1.0`, production's first release (T-2.6). **Blocks that release, not the build.** `/contact` publishes D-058's registered office, the founder's home in Hajipur, and from `v0.1.0` it is public, crawled and archived: once Google and archive.org hold the address, no later change removes it.
  **Why it's a decision** (the founder, 3 October 2026): a sole proprietorship must publish a registered address, but it needn't be where the founder sleeps. A virtual-office or registered-address service in India, roughly ₹1,000 to ₹2,000 a month, meets the same requirement with a commercial address. For a dating app, where some users will be angry at whoever banned them, the difference matters.
  **If it changes:** a new decision supersedes D-058's office, `REGISTERED_OFFICE` in `web/src/lib/legal.ts` changes (its guard test names D-058), and the court follows the office (D-058), so a new city means a new court line too.
- [ ] **P-0.15** Move the Vercel team `knot11` to Pro before `v0.1.0` (T-2.6). **Blocks that release, not the build.** Vercel's own terms: "Hobby teams are restricted to non-commercial personal use only", with "advertising the sale of a product or service" among their examples of commercial use (its fair use guidelines, updated 14 September 2026). A public dating app is plainly commercial. Until the release, staging is `noindex` with no traffic, so the risk is close to zero and it waits (the founder, 3 October 2026). Pro is $20 a month with one deploying seat, covering both projects.
  **The trial doesn't fit** (Vercel's own page, read 3 October 2026): 14 days or until its usage limits, whichever comes first; one per user account; started only by creating a new team, not by upgrading `knot11`; without a payment method it falls back to Hobby. So it is worth at most one month's $20, and only if started the day `v0.1.0` goes public, in a new team production would then live in. Upgrade `knot11` itself on release day.
- [ ] **P-0.16** Move `velora-prod`'s Supabase organisation to Pro before `v0.1.0` (T-2.6). **Blocks that release, not the build.** The Free plan keeps no automatic backups, and the first real sign-up is the first thing worth losing (the founder, 3 October 2026). Pro is $25 a month per organisation with 7 days of daily backups; its $10 of included compute covers one project, which is why `velora-prod` has an organisation of its own (`infra/PRODUCTION.md`). Point-in-time recovery, a further add-on, is T-9.14's.
- [x] **P-0.6** Create accounts: GitHub, Supabase (Mumbai), Upstash, Cloudflare (R2 on), Fly.io (paid plan for `bom`), Vercel, Sentry, Sightengine, AWS (Rekognition, `ap-south-1`).
  **Ticked with three still to set up**, none needed before Sprint 4: Sightengine (T-4.4), AWS for
  Rekognition (T-4.5 — signed up, but its payment method failed verification) and Sentry (T-9.12).
  Each is on its task's **Needs** line, which `/task` checks before planning.
- [ ] **P-0.7** Review our own legal text before real users arrive — no lawyer at this stage (the founder's call, 1 October 2026). Check Terms, Privacy, Refunds and Contact (T-2.2) against the decisions they cite and against what the product actually does at go-live; against the IT Rules 2021 (Grievance Officer, timelines) and the DPDP Act (notice, consent, rights — section 16 and Rule 15 take effect on 13 May 2027; check for any restricted-country notification); and gender-based pricing. Start with the law-and-courts text (D-052), the weakest part we wrote ourselves. Look closely, not in passing, at the under-18 section: it keeps a hashed phone number of someone just identified as a minor (D-009). The mechanism and saying so openly are right, but minors plus retention is the most scrutinised combination there is. Privacy has no section yet on what happens to people's data if the app shuts down or is sold; add one when there is something honest to say. Gates T-9.15, not the production build (D-053). Terms' consumer-rights line (D-058) was written without a lawyer, by the founder and Claude: if the terms are ever reviewed properly, show it to one.
  **No lawyer is engaged: an open item, and its owner is the founder, Shubham Kumar** (recorded 3
  October 2026). This review is his own, with Claude; no lawyer has read the legal pages. D-048
  calls this item "the DPDP session" and P-36 "the DPDP lawyer session", but none is booked. A
  dating app holding women's photos and phone numbers, with Terms, Privacy and Refunds written
  in-house, needs a lawyer's review before launch (the advisor directing T-3.2 to T-3.10, Claude in
  a separate chat). When one is booked, record who and when here.
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
- [x] **Needs:** T-1.14, T-3.1
- **Why T-3.1:** every number goes through its `normalize_phone`, `hash_phone` and `encrypt_phone`, and the test woman's PIN through `hash_pin`, with the keys the local API reads, so login finds the seeded accounts. Parts that need later code live in those tasks: placeholder photos in T-4.4, verification rows in T-4.5, the test man's 60 Velas in T-5.1 (rule 5).
- [x] `make seed` runs `api/seed/`, which writes only when three independent facts hold, each an allowlist (rule 16, D-064): `ENV` is `local`; `DATABASE_URL`'s host is loopback; and the database itself carries the marker `make infra-up` stamps on it (`infra/postgres/stamp-local.sql`). The first two are checked before connecting; the marker is the connection's first read. A tunnel makes staging's database answer on `localhost`, and only the marker catches that. The seed lives outside `app/`: `.dockerignore` keeps it out of the image, and CI checks the image has none.
- [x] The 20 prototype profiles (`docs/prototype/`, the `P` array), each with the four rows `make_user` writes (users, profiles, wallets at 0, notification_prefs), a location scattered inside its neighbourhood, never on the centroid, so nobody is 0 m from anyone (`area_id`; within 750 m, derived from the username so every run is the same, and nearer its own centroid than any other area's; `city` Bengaluru until P-38, `hometown` from `from`), `users.created_at` from `joined`; women seek men, men seek women. Onboarding done, except Ishita, Riya and Pooja (the prototype's unverified women), who stop at the selfie step, unverified, so T-4.5 has women to verify; every onboarded woman is verified (D-008), and the men where the prototype has `v` (7). The profile flags (`show_kudos` from `showKudos`; `hide_age`, `hide_distance`, `show_gifts`, `is_hidden`) each take both values across the 20.
- [x] Swipes, never a like both ways, so no match: Ananya (a super-like, free for women), Meera and Tanvi like the test man (Tanvi's was Riya's in the prototype); Arjun and Rohan like the test woman. The test man passes on Diya and Nandini, and the test woman on Kabir, so their decks show that a profile already swiped doesn't come back.
- [x] A test man (`+91 90000 00001`, `test_man`, seeking women) and a test woman (`+91 90000 00002`, `test_woman`, seeking men, verified, a PIN), both onboarded at Koramangala; a moderator (`+91 90000 00003`, onboarding not started, so not in discovery). The 20 profiles take `+91 90000 00101`–`00120`. India reserves no fictional range, so these may be real people's numbers: T-3.2 and T-3.14 keep any OTP to them on the machine (D-064, D-065).
- [x] Interests: each profile keeps its 3 prototype tags plus 2 drafted by Claude from its `about` text; Kavya's "Carnatic" (not in the catalogue) is replaced. Intents: the prototype's value mapped — `serious` → Something serious, `longterm` → Long term, `short` → Casual dating, `chat` → Go with the flow — then roughly a third get a 2nd intent and a few a 3rd, fitting their `about`, so D-041's 1–3 and any-overlap filter run on real data. Show the founder all 20 (interests, the intent spread and the profile flags) before `/done`. The data file's note says the additions were drafted by Claude from the prototype's about text and reviewed by the founder.
- [x] The data is checked against the rules before anything is written: age 18 or over in IST, 5 distinct catalogue interests, 1–3 distinct intents, an about with no URL or phone number, every onboarded woman verified, swipes only between onboarded people, each pair once, and never a like both ways.
- [x] Running it again changes nothing: people are found by phone hash and never updated, in one transaction. Start over with `make infra-reset`, then `make infra-up migrate seed`; never a targeted delete, which the ledger refuses from T-5.1.
- [x] The seed's output never contains a phone number (rule 15).
- [x] **Done when:** `make seed` twice doesn't duplicate; `ENV` staging and production, a remote host and a loopback address to an unstamped database are each refused before a row is written (tests, 🔒); the test man's number, typed as people type it, finds him through `normalize_phone` and `hash_phone`.
- [x] **Commit:** `chore(dev): seed script [T-1.15]`

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
- [x] **Needs:** T-2.1
- [x] Metadata API titles/descriptions, OG image (static), `sitemap.xml`, `robots.txt`, favicon + icons.
- [x] **Kept out of search with `noindex`, never a robots.txt disallow.** Every page outside
  production says `noindex` (an allowlist on `APP_ENV`), and so do the `(app)` and `(auth)` groups
  in every environment, which covers the routes added to them later. robots.txt disallows
  nothing. A disallow stops Google reading a page's `noindex`, so the page can still surface from
  links elsewhere while we believe it's hidden, and listing a path advertises it (P-30). The
  obvious-looking fix, "just disallow it", is the wrong one (the founder, 2 October 2026).
- [x] **Done when, on staging:** Lighthouse mobile on `/` stays at ≥ 90 performance and 100
  accessibility over several runs, all reported (its SEO score is under 100 there by design:
  staging is `noindex`); `robots.txt` disallows nothing and names no sitemap; `/` and `/discover`
  say `noindex`; `og:image` is an absolute URL on the staging address; and the share image, the
  favicon and the apple icon each answer 200 with their type.
  **Proved on staging, 2 October 2026, by Claude,** on deploy run 37006559216 (commit `629d66e`,
  smoke passed). Fetched the way crawlers fetch, with no JavaScript and no cookies:
  - **Pages:** `/` as WhatsApp, Facebook, X and Google, and `/terms`, `/privacy`, `/refunds`,
    `/contact`, `/discover` and `/login` as Facebook. Each answered 200 with its own title,
    `noindex, nofollow`, and `og:image` absolute on `https://staging.veloraapp.co.in/`.
  - **The share image itself:** the URL the tag points to, fetched as WhatsApp, Facebook and X,
    answered 200 `image/jpeg`, 1200 × 630, 42,679 bytes: the committed file byte for byte
    (SHA-256). This is the check that would have caught T-2.4's first build, whose previews were
    blank while every tag looked right.
  - **The rest:** `robots.txt` is `Allow: /`, with no disallow and no sitemap; the sitemap is
    empty; the favicon (`image/x-icon`) and the apple icon (`image/png`) answer 200.
  - **Lighthouse** 13.5.0, mobile, simulated throttling, local Chrome, five runs fixed in advance
    and all reported: performance 98, 100, 99, 100, 99; accessibility 100 in all five; SEO 66 in
    all five, failing only `is-crawlable`, which is the `noindex` working. Same 158 KiB of script
    as T-2.3's runs (90, 100, 100, 100).
- [x] **Commit:** `feat(web): seo basics [T-2.4]`

### T-2.5 · Security headers
- [x] **Needs:** T-1.17
- [x] `next.config` headers (02-ARCHITECTURE §12, D-059), from `web/src/lib/security-headers.ts`: an enforced CSP exactly as strict as today's pages allow; framing forbidden by `frame-ancestors 'none'` and `X-Frame-Options: DENY`; `nosniff`; Referrer-Policy; and a Permissions-Policy denying the camera, the microphone and location. Each later task widens it deliberately, and the module's comment and each task's line name them. Not report-only: with no collector it protects nothing (T-9.12 wires reporting). HSTS stays Vercel's; preload is T-2.6's decision.
- [x] **Done when, on staging:** securityheaders.com grade A; the five headers as served, HSTS
  without `preload`, and no `X-Powered-By`; headless Chrome shows no CSP violation on the seven
  pages, client-side navigation works, and the waitlist form hydrates and joins for real (201, an
  `example.com` address); and Lighthouse mobile on `/`, five runs fixed in advance and all reported,
  keeps ≥ 90 performance and 100 accessibility.
  **Proved on staging, 2 October 2026,** on deploy run 37037751830 (commit `8b4604f`, smoke
  passed):
  - **Served headers, read by Claude:** all ten URLs checked (the seven pages, a script, the
    share image and robots.txt) carry exactly the five headers; HSTS is `max-age=63072000` with
    no `preload`; there's no `X-Powered-By`; the CSP names staging's API.
  - **The browser, by Claude in headless Chrome:** no CSP violation on the seven pages; a real
    join through the form answered 201 (`t-2.5-done-when-browser@example.com`); client-side
    navigation works; and framed from another origin, Chrome refused: "Framing
    'https://staging.veloraapp.co.in/' violates the following Content Security Policy
    directive: "frame-ancestors 'none'". The request has been blocked."
  - **securityheaders.com, read by the founder** in their own browser (Cloudflare refuses curl
    and headless Chrome), 17:09:50 UTC, results hidden: **grade A**. Six headers detected (CSP,
    Permissions-Policy, Referrer-Policy, HSTS, X-Content-Type-Options, X-Frame-Options), and one
    warning, the predicted one, capping it at A: "This policy contains 'unsafe-inline' which is
    dangerous in the script-src directive." It also found what our checks couldn't:
    `access-control-allow-origin: *` on the page, Vercel's default (P-43, D-059's amendment).
  - **Lighthouse** 13.5.0, mobile, five runs fixed in advance and all reported: performance 100,
    100, 99, 100, 100; accessibility 100 in all five; SEO 66, failing only `is-crawlable`
    (staging's `noindex`).
- [x] **Commit:** `feat(web): security headers [T-2.5]`

### T-2.6 · Production domains
- [x] **Needs:** P-0.3, T-1.22, and the **legal facts final** (P-0.2, P-0.3) — production can't build the legal pages while any is missing (D-053)
  **Ticked 3 October 2026 by what each Need protects,** as the approved plan proposed: all six legal
  facts are known and a production build passes (P-0.3); P-0.2 stays open only for PAN, GST and the
  current account, none of which a page shows; T-1.22's one open box, the R2 staging buckets, moved
  to T-4.1.
- [ ] `veloraapp.co.in` → Vercel prod; `api.veloraapp.co.in` → Fly prod app; SSL issued. Prod DB/Redis/R2 created but empty.
  **R2's production buckets move to T-4.1,** as staging's did: R2 isn't enabled on the account.
  **The Fly half is temporary:** P-49 moves the API to Mumbai before Sprint 4 and redoes it
  (`infra/PRODUCTION.md` lists what). Set up from `infra/PRODUCTION.md`.
  **Set up by Claude, 3 October 2026, each read back:**
  - the GitHub environment `production`, whose only allowed source is the tag rule `v*`;
  - the Fly app `velora-api`, with no machine yet, its free addresses, and a certificate for
    `api.veloraapp.co.in` waiting on the DNS record;
  - the Vercel project `velora-production`, with `APP_ENV` = `production` and the API's URL, both
    `encrypted` (Config), and its domains: the apex, `www` → apex (308), and its own
    `velora-production-one.vercel.app` → apex (308);
  - in the `production` environment: both Vercel IDs, a deploy token for `velora-api` only, and
    both URL variables.

  **Waiting on the founder:** Supabase `velora-prod` and its two connection strings, Upstash
  `velora-prod`, the one-year Vercel token, the `api` record at Cloudflare, and production's four
  keys, once their second copy is decided.
- [x] **Releases from a tag, and only what staging proved (D-075):** `deploy-production.yml` runs
  on a `v*` tag; `scripts/release-gate` refuses unless the commit is on `main`, CI passed for it,
  and staging deployed it, matched by the run's name, which `deploy.yml` now sets; it reads the
  Vercel token's expiry and warns within 30 days; `scripts/release-gate-test` runs it against fakes
  in CI. The `production` environment deploys only from `v*` tags.
  **Proved live, 3 October 2026, by Claude:**
  - **The gate refuses a commit that isn't on `main`:** a throwaway tag, `v0.0.0-gate-check`, on
    `c639832` (T-2.6's commit before it merged) ran the real workflow, run 37114027309. The gate
    said "Not releasing c639832. It isn't on main: production takes only commits that merged
    (D-075)", and every other job was skipped. The tag was deleted.
  - **No branch can use the environment:** a temporary branch whose workflow targeted `production`
    was stopped by GitHub before any step ran: "Branch "probe-production-env" is not allowed to
    deploy to production due to environment protection rules." (run 37114072837). The branch was
    deleted.
  - **Staging names each run for its commit:** run 37114304214 is "Deploy staging 9667bbf…", and
    passed, its web deployed with the token read from the environment and its smoke check's
    canonical line passing.
  - **The gate's tests:** 30 checks, passing in CI (run 37114146650). Four bugs planted in copies
    of the gate each failed them: matching staging by its recorded commit, the token as an
    argument, the 30-day boundary off by one, and no check for `main`.
- [x] **Every build says which environment it's for (D-053's amendment):** `next build` refuses an
  `APP_ENV` outside local, ci, staging and production, and the smoke check compares the home page's
  canonical address with the site it checks. Proved 3 October 2026, before and after: with
  `APP_ENV` unset the build had passed and served `noindex` and `127.0.0.1` addresses, and now
  refuses; a build for staging, smoked as another site, fails the canonical check by name.
- [ ] **`v0.1.0`, the first release, waits on the founder:** P-0.14 (the registered office), P-0.15
  (Vercel Pro), P-0.16 (Supabase Pro), and where production's keys keep their second copy (below).
  They block the release, and so the Done-whens below, not the build (the founder, 3 October 2026).
- [ ] The prod app's four keys (`JWT_SECRET`, `PHONE_PEPPER`, `PHONE_ENC_KEY`, `CODE_PEPPER`) freshly generated, never staging's: startup refuses the repo's test keys (D-060) but can't know a copy of staging's. Read their shapes on the machine, lengths only, and compare each with its stored copy by SHA-256 prefix, as T-3.1 did for staging.
- [ ] **And the only copy of production's keys must not be one Mac's Keychain** (the founder, 3 October 2026). Losing `PHONE_ENC_KEY` makes every stored phone number unreadable; losing `CODE_PEPPER` makes every PIN unverifiable; losing `PHONE_PEPPER` silently unbans every banned number, and login can't find any account until every number is re-hashed from its encrypted copy (D-061, D-062). Today that costs nothing, since no data depends on them. Decide here, where production's keys are born, where the second copy lives.
- [ ] **Done when:** `https://veloraapp.co.in` shows the landing page; `https://api.veloraapp.co.in/healthz` is 200. → **Unblocks P-0.8.**
- [ ] **Done when, T-2.4's production side, which only production can prove:** `robots.txt` names
  `https://veloraapp.co.in/sitemap.xml`; the sitemap lists the five public pages on that address;
  `/` has no `noindex` while `/discover` and `/login` still do; `og:image` is on `veloraapp.co.in`;
  and Lighthouse SEO on `/` is 100. Unit tests cover it until then; this is the real check.
- [ ] **Done when, the first release's own checks,** each reported and nothing re-run: the gate
  passed on `v0.1.0`; production's security headers are exactly the six expected (the CSP naming
  `api.veloraapp.co.in`, and HSTS once, with D-074's value), with no `X-Powered-By`, nothing else
  but P-43's known wildcard, and Chrome refusing a frame; the founder's securityheaders.com grade;
  `www` and the project's `vercel.app` address answering 308 to the apex; MX, SPF, DKIM and DMARC
  unchanged at our nameservers after the apex record; Supabase's SQL checks all true, with no seed
  data; Lighthouse performance and accessibility from the SEO runs; and the gate refusing, live, a
  throwaway tag on a commit that isn't on `main`. That last one is done already, on 3 October 2026
  (run 37114027309, above).
- [x] **HSTS, decided here with its own record (D-059).** Vercel sends `max-age=63072000` today. Whether to add `includeSubDomains` (every subdomain, staging included, HTTPS-only for two years) and whether to submit to the preload list is this task's decision, written down. Preload is close to irreversible: browsers hardcode it, and removal takes months. Never set in passing.
  **Decided: D-074.** `max-age=63072000; includeSubDomains`, set in `security-headers.ts`; never
  preloaded before launch, because preload is effectively irreversible. **Served on staging**
  (deploy run 37114304214, read by Claude on 3 October 2026): exactly one such header on every
  response checked (three pages, a 404 under the scripts' path, the share image and `robots.txt`),
  with no second one from Vercel; the home page's security headers are exactly the six, plus
  P-43's known wildcard.
- [x] **Commit:** `chore(infra): production domains [T-2.6]`

---

# Sprint 3 — Auth and onboarding (weeks 4–5)

### T-3.1 · Security primitives
- [x] **Needs:** T-1.21
- [x] `core/security.py`, every primitive from a vetted library (D-060; PyJWT, argon2-cffi, cryptography and phonenumberslite added): `normalize_phone()` (India only, E.164: `PHONE_NOT_SUPPORTED` for another country's number, `VALIDATION_ERROR` on `phone` for anything else), `hash_phone()` (HMAC-SHA256 keyed by `PHONE_PEPPER`), `encrypt_phone()`/`decrypt_phone()` (Fernet through MultiFernet, in the API, not pgcrypto: D-061), `make_access_token(user_id, role)` (15 min, `aud` = `ENV`), `decode_access_token()` (`AUTH_REQUIRED`, or `TOKEN_EXPIRED` only after a valid signature; expiry by `core.clock`), `new_refresh_token()` (32 random bytes, urlsafe), `hash_token()`, `hash_pin()`/`verify_pin()` (async: argon2id at D-062's exact parameters over a `CODE_PEPPER` key, at most two at once per process), `new_csrf()` and `csrf_matches()` (constant time; empty never matches).
- [x] Keys checked for shape at startup, everywhere; the repo's public test keys refused unless `ENV` is local (D-060). `CODE_PEPPER` added (D-062), which also keys T-3.2's OTP codes (D-063).
- [x] Unit tests for each, written so a deliberately weakened primitive fails: 31 weakened versions (a fixed salt, unchecked parameters, `==` for CSRF, the wall clock for expiry, no pepper and the rest), each turned at least one test red.
- [x] `make_user(gender="male", onboarded=True, credits=0, verified=None)` factory in `tests/conftest.py` returning `(user, access_token)` (moved from T-1.5; needs `users` from T-1.9). `verified` follows D-008 unless given; `credits` other than 0 raises until T-5.1 (rule 5).
- [x] **Staging made ready before `main` moved:** on 3 October 2026 Claude read staging's keys on the machine, lengths and hex only: `JWT_SECRET` at 128 lowercase hex characters, `PHONE_PEPPER` and `PHONE_ENC_KEY` at 64 each, matching `infra/STAGING.md`'s claim. `CODE_PEPPER` was generated into the Keychain and staged the same day (Fly lists it as `Staged`), so the deploy that needs it can start. There is no production Fly app yet. 20 hashes were timed on staging's machine: a median of 18.4 ms (D-062).
- [x] **Done when, on staging:** rebased onto `main`, which moved during the build, and gated on the rebased commit, not the one built, with P-0.3's lines in `05-PLAN.md` kept beside these (the founder, 3 October 2026); the deploy comes up on the new `Settings`; and `CODE_PEPPER`'s SHA-256 computed on the machine matches the Keychain copy's computed locally, first 8 hex characters. A shape check passes any 64 hex characters, so only a match proves the transfer landed intact. A mismatch costs nothing until the day Fly's copy is lost and restored from the Keychain: then every stored PIN becomes unverifiable at once.
  **Proved on staging, 3 October 2026,** on deploy run 37079492855 (commit `bcc3773`, smoke
  passed):
  - **Rebased and gated:** onto `72ef3a2` (P-0.3), whose plan lines stand beside these. The first
    commit's CI run, 37078451050, failed: GitHub's YAML read the unquoted, all-digit test keys as
    numbers (`PHONE_PEPPER` arrived as `7.07070707070707E+63`), and the new key checks refused them
    on their first real run, before anything deployed. `bcc3773` quotes them and makes the guard
    parse `ci.yml`. Its run, 37079193472, was green in 1 m 36 s: the `api` job took 63 s, against
    55 s before T-3.1.
  - **The deploy came up:** release v27, the machine started with its health check passing, and its
    image has `app/core/security.py`. Startup checks all four keys' shapes, so it couldn't have
    started on a malformed one.
  - **The match, read by Claude:** SHA-256 of each key computed on the machine and of its Keychain
    copy computed locally, first 8 hex characters, the values never leaving either place.
    `CODE_PEPPER`: `fd4ae0b5` on both. The other three, carried the same way in T-1.22 and never
    confirmed until now, match too: `JWT_SECRET` `f5fbdd09`, `PHONE_PEPPER` `f7d127c0`,
    `PHONE_ENC_KEY` `9d5de66c`.
- [x] **Commit:** `feat(auth): security primitives [T-3.1]`

### T-3.2 · OTP send
- [x] **Needs:** T-3.1
- [x] This is Path B (MSG91, used after DLT approval); the launch path is T-3.14. `/v1/auth/otp/send` and `/v1/auth/otp/verify` are served only where `AUTH_PHONE_PROVIDER` is `msg91` or `fake`, an allowlist (rule 16); everywhere else they 404, so staging and production, on `firebase`, can't send a Path B SMS at all (D-066).
- [x] `POST /v1/auth/otp/send {phone}` → `{resend_after_s}`. Normalise the phone; if its hash is in `banned_identities`, answer exactly as for any other number and send nothing. Generate a **6-digit** code (D-066), store `otp:{phone_hash}` = keyed HMAC of the code under `CODE_PEPPER`'s `otp/v1` key, not argon2 (D-063), + attempts 0, TTL 300 s; resend lock 45 s. Send via `SmsProvider`.
  **Built:** a banned number's code is stored too, never sent, so a wrong guess at verify gets the
  same `OTP_INVALID` as anyone's and the ban stays invisible to whoever doesn't hold the number.
  The 300 s and the resend lock run on `core.clock` (the stored expiry, a one-place window), so
  tests move them; Redis's TTL only clears the key.
- [x] `hash_otp` and its constant-time check join `core/security.py` beside the PIN's, under the `otp/v1` label T-3.1 reserved: HMAC over the number's hash and the code (D-063).
- [x] Limits (D-066, 02-ARCHITECTURE §12): 5 sends per phone an hour, 20 per IP an hour, 100 an hour per IPv6 /48, 10 per phone a day, and a global daily cap, `app_config.otp_sms_daily_cap`, a new key seeded at 500 by a new data migration (rule 11; list it in 03-SCHEMA §8). At the cap: `503 PROVIDER_UNAVAILABLE`, with a warning logged at 50%, which has nowhere to land until T-9.12 (D-066 records the gap). A banned or unknown number counts against every limit exactly as any other, and a phone at D-066's 10 wrong codes in 24 hours gets `RATE_LIMITED` here (T-3.3's verify keeps that count; T-3.2's test sets it directly).
- [x] **The worst case if the limits are wrong** (D-066, at D-035's unconfirmed ₹0.20 an SMS): with only the first two limits, ₹40,000 an hour from 10,000 rented IPs, and ₹2.6 lakh an hour from one cloud IPv6 /48. With the cap, ₹100 a day. Revisit at P-0.5, when MSG91 goes live.
- [x] **D-070: `normalize_phone` refuses a number that isn't a mobile** (landline, toll-free 1800, the 140 series), as `VALIDATION_ERROR` on `phone` ("isn't a mobile number"), which settles P-45. Update T-3.1's tests to the new rule, still asserting the exact error for each case; never loosen them.
  **Built as `MOBILE` or `FIXED_LINE_OR_MOBILE`, nothing else** (D-070): libphonenumber can't place
  a third or more of the 7 and 8 series as landline or mobile, and requiring `MOBILE` would refuse real
  mobiles there. Shared-cost (1860) and premium-rate numbers are refused too.
- [x] **A seeded number never gets a real SMS (T-1.15, D-064).** India reserves no fictional range, so the seed's `+91 90000 00xxx` numbers may be real people's. Where `ENV` is local, a real `SmsProvider` is called only for numbers in `SMS_LOCAL_ALLOWED_TO` (comma-separated, each passing `normalize_phone` at startup, empty by default); any other number gets `503 PROVIDER_UNAVAILABLE` naming the setting, before the provider is called, and its stored code is discarded. Settings refuse the setting outside local, where it would look like protection it isn't. Add it to 02-ARCHITECTURE §11 and `api/.env.example`.
- [x] `Msg91Sms` stays a stub that **raises** when called, never a fake success: a stub that reports success means "code sent" with no SMS, found only when a real user waits at an empty inbox (D-066). A test holds it to raising. The real client is P-46, after P-0.4 and P-0.5.
- [x] Tests: happy path, with a 6-digit code; resend too soon → `RATE_LIMITED`; 6th send in an hour → `RATE_LIMITED`; each of D-066's other limits; the global cap → `503 PROVIDER_UNAVAILABLE`; banned → the same 200 and no SMS; unknown → the same 200; a landline, a toll-free and a 140 number → `VALIDATION_ERROR`; 404 where `AUTH_PHONE_PROVIDER` is `firebase`; locally, with a real provider configured, a seeded number never reaches it (a recording stand-in proves it, since `Msg91Sms` has no HTTP client to watch until P-46); `Msg91Sms` raises.
- [x] **At `/done`:** D-070 becomes Locked; tick P-45.
- [x] **Commit:** `feat(auth): send otp [T-3.2]`

### T-3.3 · OTP verify and signup
- [x] **Needs:** T-3.2, and the **cookie scope settled**, because this task sets the first cookies and its tests would lock in a wrong scope. Settled 2 October 2026: the refresh cookie is host-only on the API (D-054), and both cookies are named for their environment (D-055)
- [x] `POST /v1/auth/otp/verify {phone, otp}`. Wrong code → attempts+1, `OTP_INVALID` with `details.attempts_left`; 5th wrong → delete key, `OTP_TOO_MANY`; no code stored (expired, or never sent) → `OTP_EXPIRED`. Correct → delete key. A phone at 10 wrong codes in 24 hours → `OTP_TOO_MANY` (D-066).
  **Built:** the try that reaches either limit, the code's fifth or the number's tenth that day,
  is the one answered `OTP_TOO_MANY`; `attempts_left` is the nearer of the two, so it never
  promises tries the number's lock would refuse. The right code is used up atomically (it must
  still be the code that was checked), so it signs in once.
- [x] Find user by `phone_hash`, or create in **one transaction**: `users` (+ referral code), `profiles`, `wallets` (0), `notification_prefs`. A referral code is 8 characters of Crockford base32 without 0, O, 1, I or L, in capitals, drawn again on a collision.
- [x] Who may sign in (D-067): `banned` → `ACCOUNT_BANNED`; `frozen` → `ACCOUNT_FROZEN`; `paused` may; `deleted` can't occur before T-9.6 and gets `FORBIDDEN` until T-9.6 decides.
- [x] Create session (family), valid 30 days from each rotation, storing no IP address or user agent (D-067). Set the refresh cookie (`refresh_prod`, `refresh_staging`, `refresh_local`; `HttpOnly; Secure; SameSite=Lax; Path=/v1/auth`, no `Domain`: host-only on the API, D-054), and the readable CSRF cookie (`csrf_prod`, `csrf_staging`, `csrf_local`): `new_csrf()`'s value, `Secure; SameSite=Lax; Path=/`, `Domain` from `COOKIE_DOMAIN` (host-only where that's empty, locally), 30 days. Return `{access_token, user: Me}`. Both names come from `ENV` with no fallback (D-055), and both cookies are `Secure` locally too (D-067).
- [x] **D-071: access tokens gain `auth_time`,** the session family's sign-in time. Update T-3.1's test of the claim set to the new exact set; never loosen it to "at least these".
  **Stored as `sessions.auth_time`** (D-071), a new column T-3.4 copies at each rotation: the
  family's first session is revoked by then, and the only index on `sessions` is partial.
- [x] **P-42, moved here:** a middleware in `create_app()` adds `X-Content-Type-Options: nosniff` to every response and `Cache-Control: no-store` to every `/v1` response, verify's included, since it carries an access token. Tests read both off real responses.
- [x] Set staging's `COOKIE_DOMAIN` to `staging.veloraapp.co.in` in `infra/fly.api.toml` (P-33 leaves it unset).
- [x] Point `make_user` (T-3.1) and `make seed` (T-1.15) at this find-or-create service: both write these four rows by hand until now. The 20 prototype profiles get generated referral codes. The three test accounts keep fixed, readable ones, `TESTMAN`, `TESTWOMAN` and `MODERATOR`: test accounts may be special, and looking up a random code every time is the friction the seed exists to remove (T-8.6 looks codes up and never checks their format).
- [x] CLAUDE.md: say why Safari can't sign in locally. It keeps no `Secure` cookie over plain `http://127.0.0.1`, so local sign-in needs Chrome or Firefox; Safari is tested on staging, which has HTTPS (D-067). Written down, the hour isn't lost later.
- [x] Tests: new user creates all 4 rows; existing user doesn't duplicate; banned → `ACCOUNT_BANNED`; frozen → `ACCOUNT_FROZEN`; `OTP_INVALID` carries `attempts_left`; 10 wrong codes in 24 hours → `OTP_TOO_MANY`; the refresh cookie has no `Domain`; both cookies' names follow `ENV`; both are `Secure`; the referral code's format; the access token carries `auth_time`; P-42's two headers; sessions keep no IP address or user agent.
- [x] **At `/done`:** D-066 and D-071 become Locked; tick P-42.
- [x] **Commit:** `feat(auth): verify otp and create account [T-3.3]`

### T-3.4 · Refresh and logout
- [x] **Needs:** T-3.3, and **P-33** (staging's web and API on one site, or the refresh cookie can't flow there)
- [x] `POST /v1/auth/refresh`: require `X-CSRF` equal to this environment's CSRF cookie (D-055); look up the `token_hash` of this environment's refresh cookie. If it was revoked less than 10 seconds ago → `SESSION_REVOKED`, leaving its family alone: two tabs refreshing at once cause it (D-067). If longer ago → revoke the whole family (reuse attack) → `SESSION_REVOKED`. Else rotate: a new session valid 30 days, old `revoked_at` + `replaced_by`, a new CSRF value, `auth_time` carried unchanged (D-071).
  **Built:** the presented session is read `FOR UPDATE`, so two refreshes at once rotate it once
  and the second lands in the grace; a test on two connections proves it, and failed without the
  lock. A missing or mismatched `X-CSRF`, a missing cookie, another environment's cookie, an unknown
  token or a session past its 30 days is `AUTH_REQUIRED`. An account that can't sign in (D-067)
  can't refresh either: the new token needs the user's role, so the row is read anyway.
- [x] `POST /v1/auth/logout`: authenticated like refresh, by the refresh cookie and `X-CSRF`, not the access token, so it still works once that has expired (D-067). Revokes the session's family and clears both cookies → 204.
- [x] Tests: rotation works; reuse after 10 seconds kills the family (🔒 15); reuse within 10 seconds is refused and doesn't; missing CSRF → 401; logout works with an expired access token and clears both cookies; `auth_time` survives rotation.
- [x] **Commit:** `feat(auth): refresh rotation and logout [T-3.4]`

### T-3.5 · Current user
- [x] **Needs:** T-3.4
- [x] `deps.current_user` (decode JWT, load user, reject frozen → `ACCOUNT_FROZEN`, banned → `ACCOUNT_BANNED`, deleted → `FORBIDDEN`), `deps.onboarded_user` (also require `done`, else `ONBOARDING_INCOMPLETE` with `details.step`), and `deps.require_role()`, which reads the user row `current_user` loads anyway, never the token's `role`: a demotion takes effect at the next request (D-067).
- [x] 02-ARCHITECTURE §12's default limit, 300 a minute per user, goes in `current_user`, so every authenticated route inherits it.
- [x] **The 15-minute tail (D-067):** a revoked session's access token works until it expires. Bans and freezes are immediate anyway, since `current_user` loads the user; logout, a reuse attack and five wrong PINs (D-069) are not. Accepted, and read with D-069: the PIN lock is a deterrent, not protection.
- [x] `GET /v1/me` → `Me` (04-API): the age, never the date of birth, which no screen shows, and no phone number: data nothing displays isn't sent (D-067's discipline). Throttled `last_active_at` update (Redis key, once per 60 s).
  **Built in `current_user`, not only `/me`:** "last active" has to mean any signed-in request, or
  someone swiping without reloading would look away; the Redis key is a one-place window on
  `core.clock`, so tests move it. `current_user` reads the user in a transaction of its own and
  ends it, so a route's service can open another; a bare read would leave one open and every
  `async with session.begin()` after it would fail. The who-may-sign-in allowlist moved to
  `users.service`, one rule for sign-in, refresh and every request.
- [x] **At `/done`:** D-067 becomes Locked.
- [x] **Commit:** `feat(users): current user and /me [T-3.5]`

### T-3.6 · DOB, gender, seeking
- [x] **Needs:** T-3.5
- [x] `POST /me/dob`: compute age in IST. Under 18 → **D-072**: in one transaction, delete the user and everything attached (the user row with its encrypted number, profile, wallet, notification preferences, sessions), keep only the number's hash in `banned_identities` (`reason` `underage`, D-009), and return `UNDERAGE`. A date in the future, or more than 100 years ago → `VALIDATION_ERROR`. Otherwise advance.
  **Built:** the deletion clears exactly six tables' rows (sessions, notification preferences,
  wallet, profile intents, profile interests, profile) and then the user, and commits before
  `UNDERAGE` is sent. Every other foreign key into `users` is RESTRICT, so a row anywhere else
  stops the deletion whole: a 500, nothing deleted, no hash kept, rather than a moderation or
  money record taken with the account (rule 12); a test holds every key into `users` to that
  split, so a later table that cascades fails it (P-54). A date is only `YYYY-MM-DD`: pydantic
  alone reads a number as a Unix timestamp in UTC, the wrong day in India for part of every day.
  "More than 100 years ago" is before this day 100 years back, so 100 years to the day is accepted.
- [x] `/privacy`'s under-18 paragraph (`web/src/i18n/en.ts`) adds that everything else is deleted at once (D-072); `/terms` already says the number is barred.
- [x] `POST /me/gender`: only if null → set, advance; else `IMMUTABLE_FIELD`.
  **Built:** the same value sent again is `IMMUTABLE_FIELD` too, for gender and dob alike, as
  "only if null" says; a client retrying after a lost answer reads `/me` instead.
- [x] The database also refuses the change (T-1.9's `users_identity_immutable` trigger) with SQLSTATE `23514` `check_violation`, which SQLAlchemy raises as `IntegrityError`. Map it to `IMMUTABLE_FIELD` by that SQLSTATE — never by the message text, which Postgres can reword.
  **Built:** mapped only where `users` is written, which has no CHECK constraint, so 23514 there
  is the trigger's; `profiles`' length CHECKs raise the same SQLSTATE and are never mapped. A test
  switches the service's own check off and gets `IMMUTABLE_FIELD` from the trigger, for both fields.
- [x] `GET /intents`; `POST /me/seeking {seeking, intent_ids}`: seeking women, men or everyone, as the prototype offers; 1 to 3 valid distinct ids (D-041), replace the set in one tx → advance.
- [x] **The step rule (D-068):** each step's endpoint works at its step, advancing it, and after it, as an edit that doesn't advance; before it → `ONBOARDING_INCOMPLETE` with `details.step`, the user's current step. Once set, dob and gender are `IMMUTABLE_FIELD` instead.
  **Built:** `users.service.at_step`, called by every onboarding write after it re-reads the user
  `FOR UPDATE`, so two writes at once take turns. A test on two connections proves it for seeking,
  and failed without the lock: the user ended with both sets of intents.
- [x] Tests for each branch, including "17 years 364 days" and "exactly 18 today"; after `UNDERAGE` nothing survives but one `banned_identities` row: no user, session, profile, wallet or preferences row (🔒 7); a future date and one 101 years ago → `VALIDATION_ERROR`; a step before its turn → `ONBOARDING_INCOMPLETE` with the current step; an edit after it doesn't move the step.
- [x] **At `/done`:** D-072 becomes Locked.
- [x] **Commit:** `feat(onboarding): dob, gender, seeking [T-3.6]`

### T-3.7 · Name, places, username
- [x] **Needs:** T-3.6
- [x] `PATCH /me/profile`: first_name 1–30 characters after trimming, letters in any script (Devanagari, Gurmukhi and the rest), single spaces, and an apostrophe or hyphen inside a name; hometown, city ≤ 40; about 40–300, trimmed, no URLs, no phone numbers. It spans two steps (D-068): `profile` advances once first_name, hometown and city are all set, `about` when about is set at that step; a field of a step not yet reached → `ONBOARDING_INCOMPLETE`.
  **Built** (`profiles/rules.py`, which `make seed` now checks its people against too): text is
  trimmed and put in NFC before it is measured or stored. A letter is any Unicode letter, and the
  marks after it, since no Devanagari or Gurmukhi name is written without vowel signs and viramas;
  digits in any script, zero-width joiners and no-break spaces are refused, and two spaces in a row
  are refused, not collapsed. The apostrophe is `'` or `’`, which a phone's keyboard types.
  Hometown and city refuse control and format characters, where a NUL would have been a 500. A
  null field is "not sent"; every refused field is named at once; and a field of a step not
  reached refuses the whole request, the fields sent beside it too.
- [x] "No URLs, no phone numbers" in about: URLs, `www.` and bare domains; and a phone number is a **run** of 10 or more digits with at most two separators (space, dash or dot) inside it, never digits scattered across a sentence. Ten, because the check exists to catch a reachable Indian mobile number, which is exactly ten digits; below ten it catches dates, and "2010-2015" is a life story, not a contact detail (the advisor directing T-3.2 to T-3.10, approved by the founder, 3 October 2026; seven was a guess). T-7.3's contact masking builds its own, broader check later.
  **Built:** a link is a scheme, `www.`, or a bare domain: a name, a dot and an ending from a list
  people type for links, India's and the shorteners' included (`wa.me`, `t.me`, `bit.ly`). Not
  every ending there is: that would refuse words run together. The ending must be lowercase, so a
  sentence after a missed space ("chai.In the evenings") passes, and the name two characters or
  more, so "B.Com" and "B.Tech" pass, unless a path follows (`x.com/ravi`). Digits in any script
  count toward a phone number. Allowed as the rule is written, and pinned by tests at its edges:
  "98 765 43 210" (three separators) and "98765 - 43210" (three separator characters).
- [x] `GET /usernames/{u}/available` → `{available, suggestion?}`, 30 a minute per user: the regex, then the reserved list (D-068): admin, administrator, mod, moderator, support, help, helpdesk, staff, team, official, root, system, security, api, www, mail, billing, payments, legal, privacy, terms, grievance, knot, knots, thread, threads, vela, velas, me, null, undefined, and the brand from `APP_NAME`, so a rename moves it (rule 17). Matching ignores case, dots and underscores (`ad.min` is admin). The suggestion is the name plus two random digits, checked free.
  **Built:** a name outside the format is `VALIDATION_ERROR`; a reserved or taken one is
  `available: false`, and `PUT` answers `USERNAME_TAKEN` for both. A reserved name gets no
  suggestion: the name with two digits after it is the impersonation the list exists to stop. A
  user's own name is available to them. The suggestion trims the name to 18 characters, so it
  fits 20. `APP_NAME` moved from `app/main.py` to `app/core/config.py`, where a service can read it
  (a service importing `main` would be a cycle).
- [x] `PUT /me/username`: typed in any case, stored in lowercase; handles the unique-violation race → `USERNAME_TAKEN`. Changeable until onboarding is `done`, then `IMMUTABLE_FIELD` until T-9.6 designs changes (D-068). The public page stays D-001's `/@username`: usernames never take a bare top-level path, so the reserved list needn't hold route segments.
  **Built:** the race is proved on two connections, both finding the name free before either
  writes; only the unique index tells them apart, and it is read by SQLSTATE `23505` and the
  constraint's name, `uq_profiles_username`, never the message.
- [x] Tests: each first-name rule both ways; "9876543210", "98765 43210", "+91 98765 43210" and "Call me on 98765 43210" refused; "I lived in Delhi 2010-2015" and "I was born in 1998 and moved here in 2015" allowed; a reserved name, a dotted variant of one, and the brand; `USERNAME_TAKEN` in the race; capitals stored lowercase; a change after `done` → `IMMUTABLE_FIELD`; a field before its step → `ONBOARDING_INCOMPLETE`.
- [x] **At `/done`:** D-068 becomes Locked.
- [x] **Commit:** `feat(onboarding): profile basics and username [T-3.7]`

### T-3.8 · Interests
- [x] **Needs:** T-3.7
- [x] `GET /interests`; `PUT /me/interests` exactly 5 valid distinct ids → replace set in one tx.
  **Built:** like seeking's: the user re-read `FOR UPDATE`, D-068's step rule, all different and all
  in the catalogue, exactly 5 in the request's schema (the web's contract, read back from OpenAPI by
  a test) and again in the service (03-SCHEMA). `GET /interests` is public, as 04-API marks it, with
  no limit of its own: 24 rows of catalogue, nobody's data. A two-connection test proves the lock.
- [x] The interests step comes after photos (D-068), so a real user reaches it only after T-4.3; tests set the step directly.
- [x] **Commit:** `feat(onboarding): interests [T-3.8]`

### T-3.9 · PIN
- [ ] **Needs:** T-3.5, and T-3.6's step rule (D-068), which the `pin` step follows
- [ ] `POST /auth/pin/set {pin, current_pin?}` → 204: 4 digits (D-012), refusing one digit four times, straight runs either way (0123…, 9876…), alternating pairs (1212) and the 20 most common PINs in DataGenetics' published study → `VALIDATION_ERROR` (D-069). Changing an existing PIN needs `current_pin`, except within 10 minutes of a fresh sign-in, read from `auth_time` (D-071); that is also "forgot PIN": sign out, sign in by OTP, set a new one. At the `pin` onboarding step, setting one advances to `selfie`.
- [ ] `POST /me/pin/skip` → `Me`: moves `pin` → `selfie` (D-069).
- [ ] `POST /auth/pin/verify {pin}` → 204, or `PIN_INVALID` with `details.attempts_left`. `pin_failed` goes up by one per wrong PIN, in one atomic update; a correct PIN resets it, and so does a fresh sign-in (add that to T-3.3's sign-in service). **At 5, every session of the user is revoked** → `SESSION_REVOKED`; each revoked session's access token still works for up to 15 minutes (D-067).
- [ ] A stored hash `verify_pin` refuses (other parameters, unreadable) doesn't count against `pin_failed`: `PIN_INVALID` with `details.reset_required`, and the way out is the fresh sign-in above (D-069). `hash_pin`/`verify_pin` are T-3.1's (D-062).
- [ ] The PIN endpoints: 10 a minute per user; each check holds 19 MiB for about 18 ms, two at once per process (D-062).
- [ ] **What the lock doesn't do (D-069, with D-067):** it deters whoever picks up an unlocked phone; it protects nothing. The web keeps a working access token behind the lock screen, so the browser's devtools get past it, and five wrong PINs leave the revoked sessions' tokens working for up to 15 minutes. Never build on it as a security boundary.
- [ ] The seed's test-woman PIN (`TEST_WOMAN_PIN` in `api/seed/data.py`, T-1.15) must stay valid under these rules; a test here checks it, so the seed doesn't break the day the rules land.
- [ ] Tests: each refused shape, and 4829 accepted; a change without `current_pin` refused, and allowed within 10 minutes of sign-in; 5 wrong → every session revoked; a refused hash doesn't count and sets `reset_required`; skip advances; the rate limit.
- [ ] **At `/done`:** D-069 becomes Locked.
- [ ] **Commit:** `feat(auth): pin lock [T-3.9]`

### T-3.10 · Web auth client
- [ ] **Needs:** T-1.18, T-3.4, T-3.5 (`useMe()` reads `Me`) and T-3.9 (the lock reads `has_pin` and calls `/auth/pin/verify`)
- [ ] Access token in Zustand (memory only). On load, in the `(auth)` and `(app)` layouts only, call `/auth/refresh` once to restore a session, sending `X-CSRF` from this environment's CSRF cookie (D-055). Marketing pages never call the API: they stay static (Lighthouse, P-37).
- [ ] Cookie names at build time: `next.config` maps `APP_ENV` to the suffix (production → `prod`, staging → `staging`, anything else under `next dev` → `local`); no new Vercel variable. The api client sends `credentials: "include"` on `/v1/auth/*` only, the refresh cookie's path. Until now it sends no credentials at all, so no cookie would arrive.
- [ ] On any 401 `TOKEN_EXPIRED`: single-flight refresh, then retry the request once. Refreshes are serialised across tabs with the Web Locks API, so two tabs never rotate one token (D-067's 10-second grace covers what's left).
- [ ] `useMe()` query; `<OnboardingGate>` redirects to `/onboarding/<step>`, named by `onboarding_t`, placeholders until T-3.11 and T-3.12 build the screens; `(app)` routes require `done`; a failed refresh goes to `/login`.
- [ ] PIN lock screen (the prototype's PinPad): shown on load and after 5 min hidden if `has_pin`. A deterrent, not protection (D-069).
- [ ] Local development at `127.0.0.1` only: `localhost:3000` → `127.0.0.1:8000` is cross-site, so the `Lax` refresh cookie silently isn't sent. Remove `localhost` from the local `CORS_ORIGINS` (`api/.env.example`, the test settings), so that mistake fails loudly.
- [ ] **Commit:** `feat(web): auth session, refresh, route gates, pin lock [T-3.10]`

### T-3.11 · Web onboarding 1–7
- [ ] **Needs:** T-3.10, T-3.7
- [ ] **New dependencies, the first forms to use them:** web `react-hook-form` and `zod`, with `@hookform/resolvers` to join them. CLAUDE.md pins them, but nothing has installed them: T-2.3's waitlist form uses plain React state on purpose, because two form libraries for one email field would spend the landing page's performance score (98–100, T-2.1). Ask before installing, and record them in `01-DECISIONS.md` (rule 4).
- [ ] **Re-examine the CSP's `'unsafe-inline'` for scripts here (D-059).** It was justified while no user-supplied text rendered, and this is the first task that renders some: the user's own name and `@username`. Decide again, nonces or keep it, and write the reason down (a new decision if it changes). React's escaping is the real defence; the CSP is the second line. T-6.5 re-examines it again.
- [ ] Screens from the prototype: phone, OTP (6 boxes, not the prototype's 4: D-066 and 08-DESIGN's `OtpInput`; paste support, resend timer from `resend_after_s`), DOB (native date input; under-18 message), gender (with lock warning), seeking + intents (pick 1–3), name/hometown/city, username (debounced availability 400 ms, shows `veloraapp.co.in/@name`).
- [ ] Each screen: submit disabled until valid; server errors shown inline from `ApiError.code` via `en.ts`.
- [ ] Decide whether onboarding URLs carry the step's enum value, as T-3.10's placeholders do, or a stable slug of their own, so renaming a step never breaks a link.
- [ ] Phone step: a consent line naming Google before the code is sent — Google's Firebase sends it, processes the number in the United States and keeps it for abuse prevention (D-048, `/privacy`). Firebase asks apps to get this consent.
- [ ] **Commit:** `feat(web): onboarding steps 1-7 [T-3.11]`

### T-3.12 · Web onboarding 8, 10, 11
- [ ] **Needs:** T-3.11, T-3.8, T-3.9
- [ ] About (40–300 counter), interests (exactly 5), PIN (set + confirm, skip). Photos (9) and selfie (12) come in Sprint 4 — route placeholder that says "coming next".
- [ ] Interests and PIN come after photos in the step order (D-068), so until T-4.3 a real user can't reach these two screens: test them by setting the step. Their URLs follow T-3.11's enum-or-slug decision.
- [ ] **Commit:** `feat(web): onboarding about, interests, pin [T-3.12]`

### T-3.14 · Firebase phone sign-in (launch path)
- [ ] **Needs:** T-3.3, T-3.10 (it restores the session on reload, which the Done-when checks), T-3.11 (its phone and OTP screens, which this task's web step puts Firebase on), and **P-0.13** (the Google billing account, verified: Firebase's Blaze plan bills to it)
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
  6-digit code box (Path B's codes are 6 digits too since D-066, so the OTP screen is the same
  on both paths), resend cooldown, friendly copy for `auth/too-many-requests`,
  `auth/invalid-phone-number`, `auth/code-expired`.
- [ ] Sign the user out of Firebase immediately after the exchange — we keep our own session.
- [ ] **Widen the CSP here, deliberately (D-059).** T-2.5's policy allows no outside script, connect or frame host, so Firebase's SDK and its reCAPTCHA check fail at sign-in until this task adds exactly the Google hosts Firebase documents (`script-src`, `connect-src`, `frame-src`), each with its reason in `web/src/lib/security-headers.ts`. A CSP error at sign-in is this line, not a Firebase bug.
- [ ] **Seeded numbers and test numbers (D-064, D-065).** Firebase sends its code from the
  browser, so no server guard can stop a text to a seeded number (`+91 90000 00xxx`, T-1.15)
  when the local web runs on Firebase. Locally, seeded users sign in on
  `AUTH_PHONE_PROVIDER=fake`; this task decides how the local web keeps a seeded number from
  reaching Firebase. A Firebase test number signs anyone in as that number wherever its project's
  tokens are accepted, so it never goes in a project production uses.
- [ ] Tests: forged token rejected; expired rejected; reused token rejected; non-Indian number
  rejected; banned phone rejected; a valid token creates exactly one user.
- [ ] **Done when:** on staging, sign in at `https://staging.veloraapp.co.in` with a Firebase
  test phone number (fixed code, no SMS, no cost) in a Firebase project production doesn't use
  (D-065). As first written, the number lived in the one project P-0.12 sets up, which would let
  its code sign anyone into production too. This task picks the way out: a Firebase project for
  staging alone, or the founder's own phone. Then reload, and the session is still there,
  restored by `/auth/refresh`. This is the first real sign-in staging can do (D-045 allows only
  real providers there), so it is the first proof that P-33's subdomains carry the refresh cookie.
  Until it passes, P-33 is believed, not proven.
- [ ] **This is the first time any of Sprint 3's session machinery runs outside a test process.**
  T-3.3's cookies, T-3.4's rotation and logout, T-3.5's `current_user` and P-42's headers have been
  proved only in-process against the local stack: staging runs `firebase`, so Path B answers 404
  there, and nothing has signed in on it. So T-3.14 is not just Firebase sign-in, and its Done-when
  must prove each of these in a real browser against staging, observed on the wire (devtools'
  network and cookie panes), never inferred from a green test:
  1. **The refresh cookie crosses P-33's subdomains.** Set by `api.staging.veloraapp.co.in` as
     `refresh_staging` with no `Domain` (host-only, D-054), kept by the browser, and sent back on
     `/v1/auth/refresh` when the page at `staging.veloraapp.co.in` calls it with
     `credentials: "include"`: a reload restores the session.
  2. **The CSRF cookie's `Domain` works.** `csrf_staging`, scoped to `staging.veloraapp.co.in`
     (D-055), is readable by the page there and sent back as `X-CSRF`, and refresh accepts it.
  3. **`Secure` cookies are kept by real browsers over HTTPS**: Chrome, Firefox and Safari. Safari
     can't be tested locally (D-067, CLAUDE.md), so staging is its only proof.
  4. **Rotation in the browser:** a refresh replaces both cookies, and the next refresh uses the
     new values, not the old ones.
  5. **Logout clears both cookies in the browser** (the clearing cookies must match each cookie's
     path and domain, or the browser keeps the originals), and a reload lands on `/login`.
  6. **Two tabs reloaded together both stay signed in** (T-3.10's Web Locks, D-067's 10-second
     grace), and neither signs the other out.
  7. **P-42's headers on a signed-in response:** `Cache-Control: no-store` and
     `X-Content-Type-Options: nosniff` on `/v1/me`.
  And expect it slow while the API is in Singapore: about 4 s for a first sign-in, about 3 s per
  `/me`, measured as round trips (P-49, P-50). Slow is not failed; record the times beside the
  result.
- [ ] **Commit:** `feat(auth): firebase phone sign-in [T-3.14]`

### T-3.13 · E2E signup
- [ ] **Needs:** T-3.12
- [ ] Playwright against local stack with `AUTH_PHONE_PROVIDER=fake` (OTP read from a test-only endpoint enabled only when `ENV=local`): new man reaches the photos step; under-18 is refused and can't retry with the same number (D-072: the account is deleted and only the number's hash kept).
- [ ] One staging run against the real Firebase path using a Firebase **test phone number** (fixed code, no SMS sent, no cost), only from a Firebase project production doesn't use (D-065), as T-3.14 settles.
- [ ] **Commit:** `test(e2e): signup flow [T-3.13]`

---

# Sprint 4 — Photos and verification (weeks 6–7)

### T-4.1 · Storage provider
- [ ] **Needs:** T-1.21, T-1.2, and **R2 enabled on the Cloudflare account, with the staging buckets
  `velora-staging-public` and `velora-staging-private`** (`infra/STAGING.md` §3) — not enabled yet
  (T-1.22); and **P-49**: the API moves to Mumbai before Sprint 4, so T-4.4's worker is built once,
  on the new host (directed by the advisor on 3 October 2026; the founder decides). With R2
  enabled, also create **production's buckets, `velora-prod-public` and `velora-prod-private`**
  (`infra/PRODUCTION.md` §3, moved from T-2.6).
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
  Add its pool to the connection budget in `infra/STAGING.md`. It shares `Settings`, so it needs
  the API's four keys as secrets, the same values (from the Keychain, `infra/STAGING.md`):
  otherwise it can't read the numbers or hashes the API wrote, or doesn't start (D-060, D-061).
- [ ] `moderate_photo(photo_id)`: fetch raw → Pillow open (reject if not an image) → `ImageOps.exif_transpose` → resize longest side 1600 → save JPEG q85 **without EXIF** → `ModerationProvider.check()` → approve (write public copy for `public` kind) or reject with reason (`nudity`, `minor_suspected`, `no_face`, `text_overlay`, `other`). `minor_suspected` also opens an internal report.
- [ ] Idempotent: re-running on an approved photo does nothing.
- [ ] Sightengine: turn on deleting each image right after its check, so photos don't stay on its
  servers in the US and Europe — `/privacy` says they're deleted there (D-048).
- [ ] Tests with the fake provider for approve and each reject path; test that output has no EXIF.
- [ ] Extend `make seed` (T-1.15): an approved public photo at position 0 for every seeded user past the photos step (everyone but the moderator, including the three women at the selfie step) — a placeholder from the prototype's `c1`/`c2` gradient, re-encoded like any upload and stored through `StorageProvider`. Re-running creates no duplicates.
- [ ] **Commit:** `feat(worker): photo moderation pipeline [T-4.4]`

### T-4.5 · Selfie verification
- [ ] **Needs:** T-4.4, and a **working AWS account for Rekognition in `ap-south-1`** — signed up, but its payment method failed verification (P-0.6)
- [ ] `POST /verification/challenge` → random pose from a list (turn left, turn right, look up, smile) stored on the row. `POST /verification/{id}/submit {photo_id}` → enqueue `verify_selfie`.
- [ ] `verify_selfie`: re-encode; `FaceMatchProvider.compare(selfie, approved_public_photos)`; similarity ≥ 85 and exactly one face → `approved`, `users.is_verified = true`; else `rejected` with reason. Max 5 attempts / day.
- [ ] Selfies are never public and never shown to other users.
- [ ] Extend `make seed` (T-1.15): an approved verification row, with a placeholder selfie in the private bucket, for every seeded user marked verified — 15: the test woman, and the prototype's 14 `v` profiles (7 women, 7 men). Ishita, Riya and Pooja stop at the selfie step, unverified, with no row: they're who this task verifies against (the advisor directing T-1.15, Claude in a separate chat, 3 October 2026).
- [ ] **Commit:** `feat(verification): selfie challenge and face match [T-4.5]`

### T-4.6 · Web photos step
- [ ] **Needs:** T-4.3, T-3.12
- [ ] 6-slot grid; tap empty slot → file picker (`accept="image/*"`, `capture` not forced); client resize to ≤ 2000 px before upload (canvas) to save data; PUT to presigned URL with progress; states per slot: uploading %, checking, approved, rejected (with reason + retry). Drag to reorder (or up/down buttons on mobile).
- [ ] Women see the private-album note.
- [ ] **Widen the CSP here (D-059):** `connect-src` for R2's upload endpoint (the presigned PUT), and `img-src` for `PUBLIC_CDN_URL` and `blob:` previews. Uploads and previews fail with a CSP error until then.
- [ ] **Commit:** `feat(web): photo upload step [T-4.6]`

### T-4.7 · Web selfie step
- [ ] **Needs:** T-4.5, T-4.6
- [ ] Request challenge → show pose instruction → `getUserMedia({video:{facingMode:"user"}})` → live mirrored preview → capture to canvas → upload as `kind=selfie` → submit → poll `GET /verification/latest` every 2 s (max 60 s) → result. Handles permission denied with instructions per browser.
- [ ] Men: "Skip for now". Women: cannot skip.
- [ ] **Allow the camera here (D-059):** T-2.5's Permissions-Policy has `camera=()`, so `getUserMedia` is refused until this task makes it `camera=(self)`; add `blob:` wherever the captured frame shows. T-4.9's fake-camera E2E fails until then.
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
- [ ] The seed (T-1.15) gives each profile both its `area_id` and a location scattered near that area's centroid, as if it had shared its position. If `{lat,lng}` here leaves `area_id` empty, or sets it some other way, make the seed match.
- [ ] **Allow location here (D-059):** T-2.5's Permissions-Policy has `geolocation=()`, so the browser refuses the position without ever asking until this task makes it `geolocation=(self)`. Until then everyone silently lands on the area picker.
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
- [ ] `make_user(credits=N)` (T-3.1) credits through `credit(reason='admin_grant')`; until then it refuses anything but 0, so no test writes a balance (rule 5).
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
- [ ] **Re-examine the CSP's `'unsafe-inline'` again here (D-059):** the first task that renders other people's text, their names and bios. If T-3.11 kept the allowance, the threat is now someone else's input on your page.
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
- [ ] `/@username` is D-001's link, and the `@` keeps usernames out of the routes' namespace: no route segment may begin with `@` (D-068). Next.js reads an `@folder` as a parallel-route slot, so serve `/@username` through a rewrite to an internal route.
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
- [ ] **Allow the microphone here (D-059):** T-2.5's Permissions-Policy has `microphone=()`, so recording is refused until this task makes it `microphone=(self)`; add `media-src` for voice notes' storage origin and `blob:` for the preview.
- [ ] **Commit:** `feat(web): conversation screen [T-7.11]`

### T-7.12 · Web real-time client
- [ ] **Needs:** T-7.4, T-7.11
- [ ] `src/lib/ws.ts`: ticket → connect; exponential backoff 1→30 s with jitter; pause when tab hidden > 5 min; on reconnect refetch open thread + list. Events update TanStack Query caches (append message, bump row, update wallet, knot state).
- [ ] **Widen the CSP here (D-059):** `connect-src` for `wss://` on the API host. The socket fails with a CSP error until then.
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
- [ ] **`raw_webhook` keeps no payer details, whatever city the database is in** (directed 3 October
  2026, from P-49's residency read): it stores an allowlist of the verified payload's fields and
  nothing else, Razorpay's payment and order ids, amount, currency, status, method, error code and
  timestamps. Never the payer's email, phone (`contact`), UPI ID (`vpa`), card or bank details:
  RBI's own list of payment data, and not ours to keep. An allowlist, never a list of fields to
  strip, so a field Razorpay adds later stays out. Test: a payload with every payer field set is
  stored with exactly the allowlisted keys.
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
- [ ] `POST /referrals/apply {code}` only before onboarding `done`, not own code, once. Reward both (Velas from `app_config`) when the referee completes selfie verification or first purchase, whichever first; idempotent. `GET /referrals/me`. Apply looks a code up and never checks its format: the seed's three test accounts carry readable codes outside the generated one (T-3.3).
- [ ] **Commit:** `feat(referrals): codes and rewards [T-8.6]`

### T-8.7 · Web store and checkout
- [ ] **Needs:** T-8.2, T-5.5
- [ ] Store sheet from the prototype (packs, per-Vela and per-thread price, first-purchase banner). Load Razorpay Checkout script on demand. On success callback → poll `/payments/{id}` every 1.5 s (max 60 s) → toast + wallet refresh. Failure/dismiss → "Payment didn't go through" sheet with retry.
- [ ] **Widen the CSP here (D-059):** Razorpay Checkout's script, frame and connect hosts, exactly as Razorpay documents them. The CSP has been enforced since T-2.5, so checkout fails with a CSP error until this lands.
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
- [ ] Sessions store no IP address or user agent (D-067), and "> 3 devices in 7 days" needs one of them. Add what this task needs here, with a line on `/privacy`, which lists neither today.
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
- [ ] **User search finds a phone number only in full, never by prefix or part** (D-061). Numbers are
  stored as a keyed hash and an encrypted copy, so search normalises and hashes the number typed and
  matches it exactly. "Whose number ends in 4321?" has no answer, by design: support asks for the
  whole number.
- [ ] **Commit:** `feat(admin): moderation panel [T-9.5]`

### T-9.6 · Settings and data rights
- [ ] **Needs:** T-3.5
- [ ] Hide profile, hide age, hide distance, show kudos; pause (hidden + no notifications); export (JSON of own data, generated by worker, signed link valid 24 h); delete (status `deleted`, profile hidden immediately, anonymised after 30 days by cron; payments and ledger kept, detached from identity). What's erased and kept follows D-051, which `/privacy` states: messages stay in the other person's chat as from "Deleted account" and as moderation records, and a hashed phone number is kept so deletion can't escape a ban. Change the page with the code.
- [ ] Two things T-3.3 and T-3.7 left here: what a `deleted` account gets at sign-in (`FORBIDDEN` until now, D-067), and whether and how a username can change after onboarding (locked until now, D-068; D-001's `/@username` links depend on it).
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
- [ ] Route D-066's OTP warning, logged at half of `otp_sms_daily_cap`, to the alert channel: until this task it lands only in Fly's logs, which nobody reads.
- [ ] **Widen the CSP here, and wire its reporting (D-059):** `connect-src` for Sentry's ingest host, and the CSP's reports (`report-to`, with `report-uri` as the fallback) sent to Sentry's security endpoint. Until then the enforced policy is silent: a violation in production stays invisible until a user complains.
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
  **DKIM before the first send, or the launch email goes to spam:** our DMARC record says
  `p=quarantine` (P-0.3), so mail that isn't authenticated as `veloraapp.co.in` is sent to spam.
  Set up the service's DKIM for our domain, and prove it with a test send: the receiving server's
  own `Authentication-Results` line must show `dkim=pass` for our domain and `dmarc=pass`, not a
  result relayed inside `arc=pass(...)` (P-0.3 says why).
  **A certificate before any click-tracking subdomain (D-074):** HSTS covers every
  `*.veloraapp.co.in` for two years after a visit, so if the sending service rewrites links through
  a subdomain of ours, that subdomain must serve HTTPS before the first send. Otherwise every link
  in the launch email fails for anyone who has visited the site.
- [ ] **Commit:** `chore(release): v1.0.0 [T-9.15]`

---

# Sprint 10 — Closed beta operations (weeks 16–19)

- [ ] **T-10.1** Invite codes: signup requires a code during beta (`app_config.beta_invite_only`); women's codes unlimited, men's limited per code.
- [ ] **T-10.2** Product analytics (PostHog, EU/India region if available): events `signup_step_completed`, `swipe`, `match`, `thread_opened`, `message_sent`, `knot_tied`, `thread_expired_unanswered`, `purchase_started`, `purchase_paid`, `report_filed`. No message content, no phone numbers. Update `/privacy` (T-2.2) to say what it collects and where it goes. Widen the CSP here for the provider's script and connect hosts, deliberately (D-059).
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
| B-15 | Native Android (React Native + Expo) | only if beta gates are met. **Before listing:** Velora Studios LLC holds VELORA as a US mark for software and polices it, so a listing in the US store could draw a complaint (P-0.1, D-015) |
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
  **Reconsider the catalogue with the city, not before it** (the advisor directing T-1.15,
  Claude in a separate chat): once P-38 moves
  the launch city to Phagwara, Carnatic stops fitting anyway, and Punjabi music is the gap that
  matters there. Until then, the seed's Kavya carries Indie music in its place.
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

  The registered office is in Hajipur, and that's deliberate (D-058): these areas stay
  Phagwara's, the launch city. Don't make the two agree; a test in `legal.test.ts` says why.

  **The migration must fail with a message, not a bare foreign-key error (from T-1.15).** On a
  seeded dev database, 22 profiles point at Bengaluru areas (`area_id`, `on delete restrict`),
  so removing those areas raises a restrict violation that says nothing about why. Before it
  removes anything, the migration counts profiles whose area it would remove and, if there are
  any, stops with a message naming the fix: on a dev database that's the seed, so `make
  infra-reset`, then `make infra-up migrate seed` once `api/seed/data.py` has moved. Anywhere
  else it's real users, whose areas need moving, not deleting. Move the seed in the same task:
  its 14 localities, `AREA_CITY` in `api/seed/run.py`, and the about texts that name Bengaluru
  or places near it (Ananya's, Sanya's, Siddharth's), for the founder to review.
  `SCATTER_RADIUS_M` (750 m) is under half the gap between Bengaluru's two closest centroids; a
  test fails if any profile lands nearer another area's centroid, so check it against Phagwara's.
  Reconsider the interests catalogue in the same task (P-27): Punjabi music is the gap there.

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
  forged header doesn't change `request.client`. Still true after T-3.3: sessions store no address
  (D-067).

  Found in T-2.3.
- [ ] P-41 · Give `Avatar` size classes instead of an inline style. **Before any production page
  renders it.** Worst case: the first page that does shows avatars at the wrong size, because the
  CSP (D-059) blocks the server-rendered `style="width:…;height:…"`; the size never recovers after
  hydration, and the tempting fix, `style-src 'unsafe-inline'`, loosens every page. Today `Avatar`
  appears only on `/dev/ui`, where `next dev`'s allowances cover it. Map its sizes to classes on
  the spacing scale (08-DESIGN §3), and check the page shows no CSP violation.

  Found in T-2.5.
- [x] P-42 · Security headers on the API's responses. **Before T-3.5's `/me`, the first
  authenticated response a browser can cache.** Worst case: a browser or shared cache keeps one
  person's `/me`, threads or messages and shows them later (a shared phone, the back button), or a
  browser sniffs a JSON body as HTML. The web's headers (D-059) cover only the web; the API on Fly
  sends none. Two matter: `X-Content-Type-Options: nosniff` on every response, and
  `Cache-Control: no-store` on every authenticated one. A Starlette middleware in `create_app()`,
  with tests that read both off real responses, a public one and an authenticated one. Low urgency
  until then.
  **Moved:** now a step in T-3.3, since its verify is the first response to carry an access token,
  earlier than `/me` — tick this with T-3.3. **Done in T-3.3.**

  Found in T-2.5.
- [ ] P-43 · Decide `Access-Control-Allow-Origin` on the web's own responses. **Before any
  authenticated content renders.** Worst case: Vercel's blanket `access-control-allow-origin: *`
  reaches production on authenticated responses, telling every site it may read them. Browsers
  refuse credentialed requests against a wildcard, so today it's near enough harmless (the pages
  are public and no cookies are involved), but nobody chose it and it has no place on an
  authenticated surface. securityheaders.com flagged it in the founder's scan (T-2.5): "This is a
  very lax CORS policy. Such a policy should only be used on a public CDN." Claude's HEAD of `/`
  showed it too, before T-2.5. **First establish where it appears:** every response, or only
  prerendered ones. Then set what we want in `web/src/lib/security-headers.ts`, beside the other
  headers, and make the check "exactly these headers, and nothing else" (D-059's amendment): an
  inclusion check can never find a header we didn't want.

  Found in T-2.5's Done-when.
- [x] P-45 · Decide whether `normalize_phone` accepts only mobile numbers. **Decide in T-3.2.**
  Worst case: T-3.2 pays for an SMS, and spends the sender's rate-limit slots, on a number that
  can't receive one. `normalize_phone` (T-3.1) checks that a number is valid, not what type it
  is, so it accepts landlines (`+91 22 2222 2222`), toll-free 1800 numbers and the 140 series
  (libphonenumber 9.0.40 types them `FIXED_LINE`, `TOLL_FREE` and `UAN`; checked by Claude, 3
  October 2026). Sign-in needs an SMS-capable number. Requiring `PhoneNumberType.MOBILE` would
  refuse them up front, with a test each way; Firebase's path (T-3.14) may already refuse them,
  which is worth checking before duplicating it.
  **Decided:** D-070, mobiles only, built in T-3.2 — tick this with T-3.2. **Done in T-3.2.**

  P-44 is skipped on purpose: the advisor directing T-1.15 (Claude, in a separate chat) recalls
  it as T-3.1's PIN pepper, closed there, though no file or commit in the repo names it. Never
  give the number to anything else.

  Found while planning T-1.15.
- [ ] P-46 · Build the MSG91 client. **Needs P-0.4 and P-0.5**: the DLT template and the account.
  Worst case without it: Path B can't send a single code, because T-3.2's `Msg91Sms` raises by
  design (D-066), so switching `AUTH_PHONE_PROVIDER` to `msg91` breaks sign-in outright. Build it
  on httpx against MSG91's own documentation, with the DLT template, tested against a mocked
  transport, then prove it with one real SMS to the founder's own phone. D-064's local guard wraps
  it unchanged. Revisit D-066's limits and cap in the same task (P-0.5).
  **And make a banned number take as long as any other** (T-3.2): send answers a banned number
  exactly as any other but skips the SMS. With the fake, that costs nothing; with a real HTTP call
  to MSG91, a banned number would answer a few hundred milliseconds sooner, and a stopwatch would
  tell whoever asks whether a number is banned. Send the SMS off the request (an ARQ job, or a
  background task) so every number's answer takes the same time, or pad to it; and keep T-3.2's
  `503` for D-064's local refusal, which happens before anything is sent.
  **And keep httpx from logging the number** (found in P-48): httpx logs every request's URL at
  INFO through the stdlib, which reaches Fly's logs. If MSG91's API takes the mobile number in the
  query string, each send would log a phone number (rule 15). Send it in the body, or lower httpx's
  logger, and test it with `captured_logs`.

  Found while planning T-3.2 to T-3.10.
- [ ] P-47 · Give `app_config` its 60-second cache. **With T-6.4**, the first hot path to read a
  setting (the men's daily swipe limit, on every swipe). Worst case without it: a database read
  per request for a value that changes a few times a year. T-3.2's reader
  (`admin.service.config_int`) reads fresh, on purpose for now: its one caller, OTP send's daily
  cap, is rate-limited, and fresh means a lowered cap applies at once. A cache must be per app
  (`app.state`), not per process, or tests that tune a setting would read another test's value.
  Found in T-3.2.
- [x] P-48 · Make `structlog.testing.capture_logs` see every log line in tests. Worst case: a test
  that nothing secret is logged (rule 15) passes having captured nothing. structlog caches a
  logger at first use against the processor list configured then, and every `create_app()` calls
  `configure_logging()`, which installs a new list; `capture_logs` edits only the current one, so
  a logger first used in an earlier test escapes it. T-3.2's tests swap in a fresh logger and
  assert they saw the event they expect; T-3.1's PIN-hash log test relies on test order. Fix at
  the root: configure logging once per process, or keep one processor list and change it in place.
  Found in T-3.2.
  **Done, 3 October 2026:** `configure_logging()` keeps one processor list and changes it in place,
  so every logger, cached or not, reaches `capture_logs`. Proved by shuffling the whole suite (a
  seeded plugin, no new dependency): before the fix, T-3.1's PIN-hash log test failed in 8 of 8
  orders; with T-3.2's fresh-logger workaround switched off, its two log tests and T-3.3's failed
  in 8 of 8 too, loudly only because each asserts an event it expects. After the fix, with the
  workaround removed, all 749 pass in file order and in 8 of 8 shuffled orders. Two tests could never
  fail, asserting only absence on paths that log nothing (T-1.21's OTP check, T-2.3's waitlist
  email check via `capfd`, which can miss a logger bound to an earlier stream); both now use a new
  `captured_logs` fixture whose probes, through structlog and the stdlib, must arrive, and each goes
  red when a leak is planted.
- [ ] P-49 · Colocate the API and the database, and decide which city. **Before Sprint 6**, whose
  discovery pays the split below several times per request. Worst case if it stays: every
  authenticated request costs seconds before any work, in an app whose complaint driver is lag
  (09-RESEARCH C7). The user's own hop is one round trip; the API's to the database are a dozen or
  more per request. Putting the two in one city fixes that whichever city it is.
  - **Why the API is in Singapore (D-048, P-36):** Fly retired Mumbai (`bom`) on 25 September 2026
    and refused new machines there. **Still true:** on 3 October 2026 Fly's own region list (flyctl
    0.4.110) has 17 regions and none in India.
  - **Measured from the staging machine, 3 October 2026,** through the app's own engine and Redis
    client: 165.6 ms per Postgres round trip (D-048 had 165), 165 ms per Redis command, 2,865 ms to
    open a connection, and 993 ms, six round trips, for a pooled request that runs one select
    (checkout, BEGIN, the select, COMMIT). **The per-checkout liveness ping is three of those round
    trips, not one:** asyncpg's ping runs BEGIN, `;` and ROLLBACK, about 495 ms on staging. D-048
    priced it at 165 ms, and it's Locked, so the correction lives here. Cross-checked on staging
    itself: `/readyz` (one pooled checkout and select, and a Redis ping) answers 1.1 s after
    `/healthz`, 6.6 round trips' worth.
  - **Round trips per endpoint,** counted locally by a proxy that delays every packet, and matched
    against each endpoint's statement log: OTP send about 14, verify for a new account about 25,
    refresh about 9, `GET /me` about 17. At 165 ms that is 2.3 s, 4.1 s, 1.5 s and 2.8 s of server
    time. `current_user` alone is about 8 round trips, 1.3 s. P-52 and P-53 take `/me` to about 11
    round trips, still about 1.8 s split as it is.
  - **Unexplained, measured after P-53 deployed (3 October 2026):** from the staging machine,
    staging's own Redis host now answers a TCP connect in 55.5 ms over IPv4 (its PING took 56 ms,
    against 165 that morning), while its Postgres host still takes 164.6 ms over IPv6. Mumbai to
    Singapore can cost about 56 ms; our Postgres path costs three times that, over both of
    Supabase's paths (D-048). Worth one traceroute or a question to Supabase before deciding: at
    56 ms a round trip, the split would cost about 0.6 s per `/me`, not 1.8 s, still far above
    either colocation.
  - **The same city, measured:** from the staging machine in Singapore, a TCP connect to Supabase's
    Singapore endpoint takes 6.9 ms (AWS Singapore 4.0 ms); to its Mumbai endpoint, the control, 171
    ms, which matches the query round trip above. **The user's hop,** from the founder's machine:
    Singapore 92 ms (153 ms an hour earlier, through curl: the routes vary), Mumbai 54 to 58 ms.
  - **Option A, both in Mumbai.** A round trip of about a millisecond (an estimate: no machine there
    to measure from), so `/me` costs about 70 ms in all. It means leaving Fly for the API. **AWS
    `ap-south-1` may not be open to us:** the account's payment method failed verification (P-0.6),
    which also holds up Rekognition (T-4.5). **Google Cloud Run `asia-south1`** is the realistic
    one: it rides the Google billing account Firebase needs anyway (P-0.12, not done yet). Either
    needs WebSockets checked (D-025), `deploy.yml` and `infra/STAGING.md` rewritten, secrets moved,
    the smoke check repointed, and `/privacy`'s "handled by our servers in Singapore" changed.
  - **Option B, both in Singapore.** Keeps Fly: a new Supabase project in `ap-southeast-1` and Upstash
    in Singapore, by dump and restore. A round trip of about 5 to 7 ms, so `/me` costs about 150 to
    230 ms in all, one user hop slower than A, a hop paid once per request rather than per query.
    **It is the cheapest it will ever be:** staging's database holds the schema, the reference data
    and test waitlist rows, and no users (the seed runs only locally, D-064); nothing is live. Every
    sprint makes it dearer.
  - **What decides whether B is on the table: residency.** Claude's reading of the primary texts
    on 3 October 2026, not legal advice:
    - **D-048's reason was our promise, not the law.** In its words: "Postgres (Supabase) and Redis
      (Upstash) stay in **Mumbai**, so Indian users' data stays in India. Moving it out would take a
      new decision, after the DPDP session (P-0.7)." Its amendment: "'Data stays in India' was our
      own promise, not a legal requirement." And: "Moving the database after launch, with live user
      data, is not [cheap]. Keeping it in Mumbai is what keeps the India option open."
    - **DPDP requires no localisation of ordinary personal data.** Section 16(1) lets the Central
      Government "by notification, restrict the transfer of personal data ... to such country or
      territory outside India as may be so notified": a blacklist, and none has been notified as
      far as Claude found (the repo's last check was September 2026; P-0.7 re-checks). Section 16(2)
      keeps any stricter sectoral law. Rule 15 of the DPDP Rules, 2025 allows transfers, subject to
      requirements the Government may set about making data available to a foreign State. Both
      take effect on 13 May 2027. **The one localisation lever is Rule 13, for Significant Data
      Fiduciaries,** who can be made to keep specified data in India. Velora isn't one; designation
      weighs volume and sensitivity, and a dating app's data is sensitive, so at scale it could be.
      Then data in Singapore might have to come home, at that day's price.
    - **RBI's payment-data storage directive doesn't reach us as a merchant.** The circular of 6
      April 2018, per RBI's own FAQ (questions 1 and 2), binds payment system providers RBI
      authorises and the "service providers, intermediaries, payment gateways, third party vendors
      and other entities" they engage for payment services: Razorpay, not its merchants.
    - **The Vela ledger isn't payment system data.** Velas buy only Velora's own services, have no
      cash value and can't be transferred (D-050), and a gift moves no Velas to its recipient
      (D-016): a closed-system prepaid instrument, which RBI's PPI FAQ (question 7, 22 November
      2022) says is "not classified as a payment system requiring approval / authorisation by RBI
      and are, therefore, not regulated or supervised by RBI".
    - **The closest call is `payments.raw_webhook`** (T-8.2), which keeps Razorpay's verified payload:
      it can carry the payer's email, phone and UPI ID, all in RBI's own list of payment data. As
      written, the directive binds Razorpay, not us; storing less (ids, amount, status) removes the
      question. A design point for T-8.2 whichever city is chosen.
    - **The binding constraint is our own published page.** `/privacy` says the profile, messages,
      Velas, payment records and our encrypted copy of each number are "stored in Mumbai, India",
      and waitlist emails too. Option B changes that page in the same task, before any data moves.
    - **No lawyer is scheduled.** P-0.7 is the founder's own review ("no lawyer at this stage", 1
      October 2026), though D-048 calls it "the DPDP session" and P-36 "the DPDP lawyer session". So
      B is the founder's call on our own promise, unless he books a lawyer first.
  - **Directed, 3 October 2026: both in Mumbai, before Sprint 4** (the advisor directing T-3.2 to
    T-3.10, Claude in a separate chat; the founder decides, and it stays open until he does). Why
    Mumbai, though Singapore is cheaper today: the latency a person feels includes their own hop, so
    Singapore is two to three times Mumbai end to end, not the few tens of milliseconds the server
    side suggests (from the founder's machine, `/me` would be about 160 to 220 ms against 70 to 90);
    `/privacy`'s "stored in Mumbai, India" is something a woman deciding whether to upload her
    photos can check, a trust asset worth more than the latency; and Rule 13 is the tail risk, so
    moving out now and back later is worse than not moving. Why before Sprint 4: T-4.4 makes the
    worker a second Fly app, so moving now migrates one thing, and after Sprint 4 two, with every
    sprint adding Fly-specific secrets, checks, CI and `infra/STAGING.md` to rewrite. It is on
    T-4.1's Needs line, so `/task` stops there until it's done or decided otherwise.
  - **The three checks the direction asked for, done 3 October 2026:**
    1. **Cloud Run cold starts and cost.** One instance kept warm (`min-instances` 1) has no cold
       start; only instances added for a burst start cold. Our part of a start, the imports and
       `create_app()`, takes about 330 ms on the founder's Mac; Cloud Run adds pulling the image and
       starting the container on one vCPU, unmeasured without an account. Mumbai (`asia-south1`) has
       been on Cloud Run's cheaper Tier 1 since 15 November 2024. For one instance of 1 vCPU and 512
       MiB over a 30-day month, at list prices: **kept warm but idle, about $10** (request-based
       billing's idle rates); **busy all month, about $49** (instance-based billing) **to $65**
       (request-based). An open WebSocket counts as busy, so T-7.4's chat keeps instances busy
       whenever anyone is connected, and T-4.4's worker, which polls Redis all the time, needs an
       always-on instance of its own: about $49 more. So production with chat live is roughly $100
       to $115 a month on Cloud Run, against Fly's roughly $3 to $4 per small machine (published
       rates; flyctl's size list shows no prices), $7 to $8 for an API and a worker. **A Compute
       Engine VM in Mumbai** under the same Google billing account, `e2-small` at $14.69 a month on
       demand (`e2-micro` $7.34), runs the API, the worker and WebSockets flat, with no cold starts,
       at the cost of looking after a VM (OS updates, TLS, the deploy). **What this changes:** the
       warm instance is cheap; WebSockets and the worker are what make Cloud Run the dearest of the
       three. Mumbai stands; the host is the founder's choice between Cloud Run's management and a
       VM's flat price.
    2. **The Postgres-versus-Redis gap is not the pooler.** The API reaches Postgres over Supabase's
       direct connection, IPv6, not its pooler (`infra/STAGING.md`), and the pooler measured 171 ms
       anyway. Both hosts are Amazon's, in Mumbai: from the founder's machine in India, Upstash's four
       addresses answer in 61 to 68 ms, like AWS Mumbai's own 66, so no nearer edge fronts them. The
       gap is Fly's routing from Singapore, which differs by destination and changed during the day:
       165 to 171 ms to every AWS Mumbai address tried (Supabase direct and pooler, AWS's EC2 API),
       while Upstash's fell from 165 that morning to 56. So nothing in our configuration is free to
       recover, and inside Mumbai the detour doesn't exist, so the Mumbai estimate stands. A route
       that moves threefold in a day is one more reason not to depend on it.
    3. **Whether Google can be paid: not confirmed, and only the founder can confirm it.** This
       machine has no Google Cloud CLI to ask with. Google's own page says an Indian billing account
       must complete mandatory identity verification within 30 days or be suspended: an individual
       by PAN or e-Aadhaar through DigiLocker and proof of address, a business by a GST or Udyam
       certificate (P-0.2's PAN and GST are still unconfirmed). Firebase's Blaze plan (P-0.12) needs
       the same billing account, so it is owed anyway. Until a billing account exists and is
       verified, no plan should rest on Google either.
  - **Host, directed 3 October 2026: a Compute Engine VM in Mumbai, not Cloud Run** (the advisor
    directing T-3.2 to T-3.10, Claude in a separate chat; the founder decides). Threads and Knots
    are the product, so "busy whenever anyone is connected" is close to always: Cloud Run's roughly
    $100 to $115 a month against the VM's roughly $15 is a different budget, pre-revenue, not a
    trade-off (about ₹1 lakh a year against ₹15,000, the advisor's figures).
    **What the VM costs, accepted, not overlooked:**
    - OS updates, TLS renewal, deploys and restarts become ours. Caddy terminates TLS and renews
      its certificates itself; Docker Compose runs the API, the worker and Caddy, as Compose already
      runs the stack locally.
    - One VM is one point of failure, and a deploy is a restart unless built around: open WebSockets
      drop and clients reconnect (T-7.12). At launch, in one city, with no users yet, survivable.
    - **Revisit when** revenue exists, or when a restart during a live Thread becomes a real
      complaint.
    **Considered and not chosen: DigitalOcean in Bangalore.** Droplets from $6 a month and App
    Platform from $5 a container, with workers, both in Bangalore: managed deploys and TLS would cut
    the ops above. But Bangalore isn't Mumbai, so it is another split: an estimated 15 to 20 ms per
    round trip to Supabase and Upstash (unmeasured: no machine there), paid about 13 times per `/me`
    (11 round trips to Postgres, 2 to Redis), so about 200 to 260 ms of server time, where a VM in
    Mumbai pays about 15 to 25 ms. It doesn't beat Compute Engine clearly, and one Google account
    for hosting and Firebase is worth something on its own. Colocating in Bangalore would mean
    leaving Supabase for DigitalOcean's own Postgres: a bigger move, not this one.
  - **Not decided here.** The founder decides the city and the host; this is the measurement, the
    reading and the advisor's direction. The move is a task of its own and writes the decision
    superseding D-048 (and D-023's region); no D- number is taken before then.
  - **What the move inherits from T-2.6 and must redo** (the founder, 3 October 2026). T-2.6 built
    production's API half on Fly knowing this move would replace it: closing Sprint 2 was worth the
    rework, and `api.veloraapp.co.in` carries no traffic in between, so the DNS change costs
    nothing. The move redoes, for production:
    - the Fly app `velora-api` and its machine, and `infra/fly.api.production.toml`;
    - its secrets, moved with the **same values**: new keys would make every stored phone number
      and PIN unreadable (D-061, D-062);
    - the `api` record at Cloudflare;
    - the `api` and `migrate` jobs in `.github/workflows/deploy-production.yml`, with
      `infra/PRODUCTION.md`'s Fly section and its Fly cost line.

    The web, the release gate, the smoke check and the domains stay.

  Found reviewing T-3.2 to T-3.5, at the direction of the advisor directing them (Claude, in a
  separate chat), who added option B and the residency question.
- [ ] P-50 · Cut the round trips every request pays. **Before Sprint 6 adds routes on
  `current_user`; worth doing wherever the API runs.** Worst case without it: the fixed cost in P-49
  multiplies with every route that inherits it. Measured on 3 October 2026 (P-49's method):
  - `pool_pre_ping` costs three round trips per checkout. Recycle connections by age instead
    (`pool_recycle` below Supabase's and Fly's idle timeouts) and retry a request once on a dropped
    connection: about 495 ms a checkout on staging.
  - **T-3.5 doubled the checkouts:** `current_user` reads the user in a transaction of its own (so a
    service's `async with session.begin()` can follow), and a committed `AsyncSession` hands its
    connection back, so the service checks out again and pays the ping again. One checkout per
    request (bind the request's session to one connection) keeps T-3.5's reason and drops the second.
  - `Me` is four selects after the user row (profile, balance, intents, interests); one query does it.
  - The rate limit and the activity throttle are two Redis scripts per request; one script does both.
  - Sign-up: one query for the ban and the user lookup, the referral code drawn by insert-and-retry
    instead of a check first, the four rows in one statement, no reads back after insert, and the
    code's peek, read and use as one Redis script: about 25 round trips to about 9.
  Each with a test that counts round trips (the delay proxy, or statement and command counts), so a
  change that adds one goes red.

  Found reviewing T-3.2 to T-3.5.
  **Split, 3 October 2026:** the first two items are our own waste, worth fixing whatever P-49
  decides, so they are P-52 (the second checkout) and P-53 (the ping), done now. The rest waits for
  P-49's answer.
  **P-49's answer, as directed (3 October 2026): both in Mumbai.** There a round trip costs about a
  millisecond, so what's left here saves tens of milliseconds a request, not seconds: `/me` is about
  11 round trips after P-52 and P-53. So the rest waits for the move, and after it is done only where
  a route proves slow, measured with `tests/roundtrips.py`. If the founder keeps the split instead,
  it is worth doing at once: at 165 ms a round trip it is most of `/me`'s remaining 1.8 s.
- [ ] P-51 · Decide what a banned number is told. **In T-9.5, where bans are written, or T-9.6.**
  Worst case: a person barred by mistake, or a minor's family, has no way to learn why sign-in stopped
  working, or that grievance@ exists, which the IT Rules' grievance obligations (D-052) assume.
  D-073 records what happens today: on Path B, a number in `banned_identities` is answered like any
  other and its codes simply stop arriving, with no message. On Path A, Firebase's own SMS still
  arrives and the exchange answers `ACCOUNT_BANNED`, which the web can turn into copy naming
  grievance@. Whether Path B's silence is acceptable is this task's question.

  Found reviewing T-3.2 to T-3.5, at the direction of the advisor directing them.
- [x] P-52 · One connection per request: stop the second checkout T-3.5 added. **Now, before
  T-3.6.** Worst case left: every authenticated request checks out twice and pays the liveness ping
  twice, about 990 ms on staging, in every environment, colocated or not. `current_user` reads the
  user in a transaction of its own and ends it, so the route's service can begin another (T-3.5),
  and a session bound to the engine hands its connection back at every commit, so the service
  checks out again. The fix: the request's session checks out one connection at its first query and
  keeps it until the request ends, so later transactions reuse it; a request that never reaches the
  database, a bad token say, still checks out nothing. Proved on the real `get_session` by counting
  pool checkouts, failing with the old session.
  **Done, 3 October 2026:** `core/db.py`'s `RequestSession` opens its connection inside `get_bind`
  at the first query and hands it back from `close`, `reset` and `invalidate`. On the real
  `get_session`: two transactions in a request take one checkout, as do `current_user` and `/me`'s
  route together; a bad token takes none. Every way a session ends returns the connection, between
  transactions too, where only the session knows it holds one (the first version of that test,
  mid-transaction only, missed a leak from `invalidate`). Six weakenings, each red. Measured by the
  delay proxy: `/me` from about 17 round trips to about 14, one liveness ping fewer, about 495 ms on
  staging; single-transaction endpoints unchanged.

  Split from P-50, at the direction of the advisor directing T-3.2 to T-3.10.
- [x] P-53 · Make the liveness ping cheap. **Now, before T-3.6.** Worst case left: `pool_pre_ping`
  costs three round trips on every checkout, about 495 ms on staging (D-048 priced it at 165):
  asyncpg's ping wraps `;` in BEGIN and ROLLBACK for PgBouncer's transaction mode, which we don't
  use (staging connects direct, `infra/STAGING.md`). The fix: no ping for a connection used in the
  last 30 seconds; one idle longer is pinged, and if dead, replaced before the request sees it; and
  the pool hands out its newest connection first, so a quiet pool keeps reusing a warm one. Proved
  by counting the round trips a request makes, and by killing an idle connection's backend and
  seeing the next request succeed.
  **Done, 3 October 2026:** `build_engine` drops `pool_pre_ping`, checks a connection only after
  `CHECK_IF_IDLE_FOR` (30 s) idle, never a new one, and hands out the newest first. A new test
  helper, `tests/roundtrips.py`, counts round trips at the wire, deterministically (a client send
  after the server's answer is one): a warm connection's request is three (BEGIN, the select,
  COMMIT), where `pool_pre_ping` made six; after 30 s idle, seven the first time (asyncpg also
  prepares `;`) and six after. A killed idle connection is replaced before the request sees it; one
  killed within 30 s of use fails one request, then is replaced, pinned by a test as the price.
  Eight weakenings, each red. Found on the way: the kill helper's wait read Postgres's
  `pg_stat_activity`, which keeps one snapshot per transaction, so it sometimes waited on a stale
  answer until it timed out; a fresh transaction per poll fixed it (fifteen runs clean).
  **Measured with P-52, by the delay proxy:** OTP send about 14 round trips to about 11, verify for a
  new account about 25 to about 12, refresh about 9 to about 6, `/me` about 17 to about 11. Most of
  verify's drop is LIFO, not the check: with only LIFO off it is about 21, because a pool handing
  out its oldest connection first kept moving verify to connections that hadn't prepared its
  statements yet. That part is a cold-pool effect; in a long-warm pool the gap closes.
  **Proved on staging, 3 October 2026,** after deploy run 37109881416 (commit `c228739`), read on
  the machine and from outside: a pooled request with one select fell from 993 ms to 497 ms, six
  round trips to three, as the wire count predicted; `/readyz` now answers 535 ms after `/healthz`,
  against 1,097 ms that morning.

  Split from P-50, at the direction of the advisor directing T-3.2 to T-3.10.
- [ ] P-54 · Keep D-072's deletion possible once T-8.6 lets a referral code be applied during
  onboarding. **With T-8.6.** Worst case: someone under 18 applies a code before the dob step, then
  gives their date; the referral's row, RESTRICT to `users`, stops the deletion, they get a 500, and
  their account, encrypted number included, stays: the data D-072 exists not to hold. T-3.6 made
  it fail closed (nothing deleted, no hash kept), and a test fails if any key into `users`
  cascades. T-8.6 either refuses `/referrals/apply` until dob is set, or adds its table to
  `UNDERAGE_DELETES` (`api/app/modules/users/repository.py`) with a test. The same goes for any 🔐
  route that writes a row before dob: D-068's step rule already keeps photos (T-4.2) and the selfie
  (T-4.5) behind their steps. Found in T-3.6.
- [ ] P-55 · Let two checkouts' test suites run at once. **Before the next time two sessions build
  in parallel.** Worst case: a session sees tests fail that nothing in its change broke, and spends
  an hour on them or "fixes" them. Seen on 3 October 2026: T-3.7's username rate-limit test and
  four of T-2.6's OTP rate-limit tests failed in the same minute, because both suites use
  `velora_test` and Redis db 1, and `test_redis` clears every `ratelimit:*` key, so each run wiped
  the other's windows; alone, each passed. The database is shared too: two runs' uncommitted rows
  with the same unique values (`make_user`'s serial phone numbers) wait on each other. Give each run
  its own Redis database or key prefix and its own test database (by worktree, or by a run id),
  with a test that two runs can't see each other's keys. Found in T-3.7.
