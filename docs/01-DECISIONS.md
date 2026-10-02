# 01 · Decisions

Every decision that shapes the code. **Locked** means do not re-open it in a coding session —
if it seems wrong, raise it with the founder, don't change it. **Open** means a default is in
place so work can continue; the founder will confirm.

Format: Decision · Why · Rejected alternatives.

---

## Product

### D-001 · Web first, native later — Locked
Ship a responsive, installable web app (PWA). Native Android only after beta metrics hold (month 7+).
**Why:** app stores take 15–30% of every credit sale; web pays ~2% + GST. No store review, no
closed-testing requirement, instant updates, shareable `velora.app/@username` links.
**Rejected:** React Native first.

### D-002 · Women free, men pay credits — Locked
**Why:** the core supply/demand balance of the product. No payout programme for women.
**Rejected:** paying women per message (creates fake-engagement incentives).

### D-003 · Threads and Knots — Locked
Every conversation opens as a **Thread** that expires 24h after opening. Both people tapping
"Tie the knot" converts it to a **Knot**: permanent, free messaging for both, forever.
An expired thread is archived read-only, never deleted, and can be re-opened for 3 credits.
**Rule:** permanence is granted by the other person, never bought.
**Corrected 1 October 2026:** from `f85315e` until today the body read "converts it to a
**Velora**", a drafting slip that contradicted its own heading. The slip spread to CLAUDE.md, the
README, 03-SCHEMA, 06-TESTING and three code comments; this entry and all of them were corrected
to Knot in the same commit. Velora is the company name, and Thread and Knot are product nouns
(CLAUDE.md rule 17).

### D-004 · Action prices — Locked (values tunable)
Prices live in the `action_prices` table, not in code, so they can change without a deploy.

| Action | Credits |
|---|---|
| Open a thread from a match | 5 |
| Direct message (no match) | 5 |
| Re-open an expired thread | 3 |
| Unlock a voice note | 5 |
| Request private album | 5 (refunded if declined) |
| Super Like | 5 |
| Reveal one "liked you" | 20 |
| Tie the knot / message in a knot | Free |

Women pay nothing for any action.

### D-005 · Credit packs — Locked
| Credits | Price | Per credit | Cost of one thread (5 cr) |
|---|---|---|---|
| 25 | ₹1,500 | ₹60 | ₹300 |
| 50 | ₹2,500 | ₹50 | ₹250 |
| 75 | ₹3,375 | ₹45 | ₹225 |
| 100 | ₹4,000 | ₹40 | ₹200 |

First purchase gets +20% bonus credits.

**Why this ladder:** each larger pack is cheaper per credit, so buying up is rewarded and the big
packs actually sell. The earlier draft had the 50 pack cheaper per credit than the 75 and 100 packs,
which would have made those two dead inventory.

Optional cosmetic rounding if you prefer 9-endings: ₹1,499 · ₹2,499 · ₹3,399 · ₹3,999. Keep the
descending per-credit order whatever you choose.

Packs live in `credit_packs`, so price changes are a row update, not a deploy. Beta runs a cheaper
entry variant (₹999 / 25) against variant A — see T-10.4. The number to watch is what a man pays
for his first real conversation: ₹300 at the entry pack, ₹200 at the largest.

### D-006 · Clearing is one-sided — Locked
Clearing hides a chat from *your* list only. The other person keeps their copy. The server keeps
everything for moderation. UI copy says "Cleared from your chats", never "Deleted".
**Why:** two-sided delete lets an abuser destroy the victim's evidence before a report.

### D-016 · Gifts — Locked (catalogue is data)
Six gifts, sendable **from a woman's profile** by men. Two are free, two cost 2 credits, two cost
4 credits. Prices live in the `gifts` table, not in code.

- Free gifts exist to let a man open a conversation without paying, and to give women a low-noise
  signal of interest. They are rate-limited (see below) or they become spam.
- A gift does **not** open a thread and does not bypass the credit wall for messaging.
  It creates a notification and appears on her profile if she allows it (`profiles.show_gifts`,
  default on) — the same rule as kudos: the recipient controls what is shown.
- Women pay nothing for anything, so gifts are one-directional in MVP: men → women.
- Anti-spam (values in `app_config`): `gift_free_daily_limit = 3`,
  `gift_same_recipient_cooldown_h = 24` (per gift kind), blocked users can't send, frozen users
  can't send. Paid gifts have no daily cap but respect the cooldown.
- Gift sends are permanent records (`gift_sends`) and are visible to moderation.

**Rejected:** gifts that unlock private photos or messaging (that would make permanence buyable,
against D-003), and gifts sent anonymously (a gift with no name is a harassment vector).

### D-007 · Kudos, not reviews — Locked
After a few messages the sender may pick one of four fixed positive notes. It goes privately to
the recipient, who alone decides whether it shows on their profile.
**Rejected permanently:** public ratings or written reviews of people; paying to remove a review;
fake or operated profiles.

### D-008 · Gender locked, selfie rules — Locked
Gender is chosen once at signup and cannot be changed by the user. Selfie liveness verification is
mandatory for women before the profile goes live, optional (but encouraged) for men.

### D-009 · Hard 18+ gate — Locked
Date of birth under 18 → signup refused; the phone hash is added to `banned_identities`.
Age is recomputed server-side; the browser's value is never trusted.

### D-010 · MVP scope — Locked
**In MVP:** gifts on profiles (D-016), landing + legal, OTP signup, 12-step onboarding, photos + moderation, selfie
verification, discovery + swipe + match, search + @username, filters, liked-you (paid reveal),
Threads + Knots + real-time chat, voice notes (women send, men unlock), private album requests,
kudos, report + block, one-sided clearing, credits + wallet + ledger, Razorpay, first-purchase
bonus, referral codes, web push, PIN lock, privacy basics (hide profile, hide age, hide distance),
admin panel, fraud scoring v1, contact masking.
**After beta (backlog, Sprint 11+):** voice/video calls, Vibe Room, boost, who-viewed-you,
wink, paid incognito, streaks, rewarded ads, auto top-up, view-once photos, Hindi UI, native Android.

### D-011 · Screenshots can't be blocked on web — Locked
Mitigation: private album images are rendered with the viewer's username watermarked in,
server-side, per viewer.

### D-012 · PIN lock — Locked
Optional 4-digit PIN locks the app on this device. Stored as an argon2 hash server-side.
5 wrong attempts → session revoked, must re-login by OTP.

### D-013 · Launch city and registered office: Phagwara — Locked
One city only for beta and launch. Discovery radius default 25 km. **Phagwara, Punjab, India** is
both the launch city and the company's registered office (P-0.2). The footer and the Contact page
read it from `web/src/lib/legal.ts`.

**Why this is the low-risk way round:** the launch city is cheap to change later — it is seed data
(`areas`) and a default — while a registered office is not. Committing to Phagwara for both costs
a data migration if the launch city ever has to move.

The seeded areas are still Bengaluru's, from when Bengaluru was this decision's default; P-38
replaces them before T-4.10 reads them. Closed by the founder on 1 October 2026.

### D-014 · Theme — Locked (black · white · red blend)
The app has one theme, the blend: black chrome (header, bottom nav, hero, sheets), soft-white
content, red accent. Its tokens are in `08-DESIGN.md` §1 and match the prototype
(`docs/prototype/`) value for value. Colours live only in `web/src/styles/tokens.css`.

**Why now:** locked by the founder before T-1.17 creates `tokens.css` — T-1.19's primitives,
Sprint 2's landing page and everything after inherit whatever goes in there.

**Rejected:** the other two prototypes, dark and soft light. Their tokens remain in git history
(08-DESIGN before this lock); a dark mode, if ever wanted, would be a new decision.

### D-015 · Name "Velora", domain `veloraapp.co.in` — Locked
The brand is **Velora**. Keep the name in one constant (`APP_NAME`) in both apps so a rename is
trivial.

**The domain is `veloraapp.co.in`, not velora-something.** Every sensible Velora domain was either
registered or premium-priced: `velora.app` alone was ₹85,101, the price the founder was quoted when
buying on 2 October 2026. So the brand keeps its name and the domain carries "app". That domain
search has been done; don't reopen it. Bought from Hostinger on 2 October 2026 (P-0.3).

Web at `veloraapp.co.in`, API at `api.veloraapp.co.in` (T-2.6). Where an earlier decision says
`velora.app` (D-001, D-024, D-025), read `veloraapp.co.in`. The shape is unchanged: web at the
apex, API on `api.`, one site. D-024's cookie scope is changed separately, by D-054.

**Closed on a partial trademark search.** "The Velora" is an established wedding brand, and
another business trades as "Velora" on Vercel (below). The founder searched the public web on
1 October 2026 and found more Indian entities trading as Velora: VELORA HARDWARE (INDIA) PVT LTD,
which holds Indian trademarks; VELORA CHEMICALS; VELORA ENTERPRISES; VELORA LABS LLP; VELORAQ
PRIVATE LIMITED, in Punjab; and a registered "velora-kitchen" mark. Outside India, VELORA LLC in
the US.

**Not done:** a class-specific search of the Indian trademark registry for dating services or
software. P-0.1 stays open for it. If it forces a new name, a new decision supersedes this one,
the domain is bought again, and Vela is renamed with the brand (D-049). Closed by the founder on
2 October 2026.

**Searched again on 3 October 2026, on mirrors, not the registry** (founder). IP India's public
search returned an empty page, so the class search ran on mirror databases, which are only as
current as their last copy of the registry. **India:** the only registered VELORA found is
application 2699359, in class 21 (household and kitchen utensils), registered in 2014; no mark was
found in classes 9, 42 or 45. Unrelated companies carry the name in other trades: Velora
Chemicals, Velora Weaves, Velora Enterprises. **United States:** Velora Studios LLC holds two
registered marks, VELORA (3947376) and VELORA STUDIOS (3947378), issued in 2011 and renewed in
2020, for design, web, hosting, software and technology services. It publishes a page warning
against using the name for software, SaaS and digital products, so the marks are actively
policed. **Nothing is blocked today:** a US registration doesn't reach India, and Velora is
web-first, with no app-store listing. **It would matter at a US app-store listing or in US
marketing,** so a line goes wherever either is first planned: the only app-store listing planned
is native Android (B-15), which carries it, and US marketing isn't planned anywhere. P-0.1 stays
open until the registry itself is searched.

**Recorded 1 October 2026, not assessed:** another business trades as "Velora" and holds the name
on Vercel. `https://velora-staging.vercel.app`, the address staging was meant to have, is that
business's site, titled "Velora | Bespoke fronts for IKEA systems". Vercel gave our project
`velora-staging-black.vercel.app` because the name was taken. Seen by Claude while checking the
staging deploy (T-1.22), by loading that page and its 404 page, and nothing more: nothing else
about the business was looked up. Recorded at the founder's request, for before the domain is
bought (P-0.3).

### D-041 · Intent is a multi-select catalogue — Locked
Intent — what someone is looking for — is a catalogue, the same shape as interests: the `intents`
table (10 rows) and `profile_intents`, **1 to 3 per user**, enforced in the service (P-25). This is
why intent is not an enum like the app's other classifications. Discovery's intent filter matches
on **any overlap**. Labels are sentence case, since intents and interests show as chips on the same
profile; the UI reads them from `en.ts` keyed by id (P-26).

**Why any overlap:** ticking two intents means "either of these is fine", not "I demand both".
Requiring every selected intent would mean someone who ticks "Something serious" and "Long term"
only sees people who picked both — and where the gender ratio is already the hard problem, that
shrinks a thin feed to nothing.

**Why 10:** the 20 first proposed included near-duplicates that users wouldn't distinguish, which
turns a filter into noise. "Just sexuality" and "Exploring fantasies" were deliberately left out for
the launch market; they can be added (a data migration) if that is decided otherwise.

**Rejected: a single enum value** (`profiles.intent`, type `intent_t`) — what intent was until
P-25. **Rejected: matching every selected intent** — see "Why any overlap".

---

## Architecture

### D-020 · Modular monolith — Locked
One FastAPI app, split into modules with router → service → repository layers. One database.
**Rejected:** microservices (distributed transactions and deploy overhead for a solo founder).

### D-021 · PostgreSQL with row-locked ledger — Locked
Credits change only inside a transaction that locks the wallet row (`SELECT … FOR UPDATE`) and
appends a ledger entry. `wallets.balance` has `CHECK (balance >= 0)`.
**Rejected:** Firebase/Firestore (no geo+filter queries, no true row lock, per-read billing),
MongoDB.

### D-022 · Async everywhere — Locked
asyncpg, httpx, aioboto3, ARQ. **Rejected:** psycopg2, requests, Celery.

### D-023 · Hosting split — Locked
Web on Vercel. API + worker on Fly.io Mumbai (`bom`). Postgres on Supabase Mumbai. Redis on Upstash.
**Why the split:** serverless platforms cannot hold long-lived WebSocket connections.

### D-024 · Domains and auth cookies — Locked
Web at `velora.app`, API at `api.velora.app` (same site). Access token: JWT, 15 min, kept in memory,
sent as `Authorization: Bearer`. Refresh token: opaque random, 30 days, rotating, stored hashed in
`sessions`, delivered as an `HttpOnly; Secure; SameSite=Lax` cookie scoped to `.velora.app`.
Refresh endpoint also requires the `X-CSRF` double-submit header.

### D-025 · Real-time via WebSocket — Locked
Client gets a single-use 30-second ticket from `POST /v1/ws/ticket`, then connects to
`wss://api.velora.app/ws?ticket=…` (never a JWT in a URL). Fan-out across API instances via Redis
pub/sub, one channel per user. A message is persisted before it is acknowledged.

### D-026 · Payments — Locked
Razorpay (primary), second gateway applied for as backup. The server creates the order.
**Credits are granted only by the verified webhook**, idempotent on `razorpay_payment_id`.
The browser's success callback only triggers a status poll.

### D-027 · Storage — Locked
Cloudflare R2, two buckets: `velora-public` (moderated profile photos, served via CDN) and
`velora-private` (originals, selfies, private album, voice notes — signed GET, 10 min).
Uploads go browser → R2 via presigned PUT (5 min). Every image is re-encoded server-side.

### D-028 · External providers behind adapters — Locked
SMS, payments, moderation, face-match and push each sit behind an interface in `app/core/providers/`
with a **fake** implementation used locally and in tests. Real keys are swapped in by environment.
**Why:** coding never waits for DLT or gateway approval.

### D-029 · Numbers — Locked
Credits are integers. Money is integer paise. No floats for either, anywhere.
IDs are UUID (`gen_random_uuid()`). Timestamps are `timestamptz` in UTC; display in IST.

### D-030 · Contact masking — Locked
In a thread's first 20 messages, phone numbers, emails, UPI IDs and social handles are masked
server-side before storing the display text (original kept in `body_raw` for moderation).
Messages matching abuse or payment-solicitation patterns are rejected with an error code.

### D-037 · No reach throttling as a sales tactic — Locked
Visibility is never reduced to push someone toward a paid product. The fraud model's `shadow` band
exists **only** for suspected fraud and abuse, never for monetisation, inactivity or "desirability".
How ranking works is published in plain words (B-19).
**Why:** users across every major app already believe they are being hidden to sell boosts, and that
belief is the category's deepest trust problem (see `09-RESEARCH.md` §C6, R3).

### D-031 · Fraud scoring v1 — Locked
Rule-based weighted score (0–100) over behavioural signals, recomputed by a worker.
Bands: <30 normal · 30–60 monitor · 60–80 shadow-limit · >80 freeze. Three independent reports in
24h auto-freezes regardless of score. **Rejected for now:** ML models (no training data yet).

### D-032 · Discovery ranking v1 — Locked
PostGIS radius filter, then a rule score: distance decay + recency of activity + verified +
profile completeness. Excludes: already swiped, blocked either way, hidden, frozen, underage-banned.

### D-033 · Strings — Locked
All user-facing strings in `web/src/i18n/en.ts`. Hindi file added after beta. No i18n library in MVP.

### D-035 · Phone sign-in via Firebase first, own SMS later — Locked
OTP is delivered by **Firebase Phone Authentication** at launch. The browser runs the Firebase JS
SDK, gets a Firebase ID token, and our API exchanges it for our own access + refresh tokens. Our
session model (D-024) does not change — Firebase only proves the phone number.

**Why:** TRAI DLT registration takes weeks and blocks the very first screen. Firebase needs no DLT
paperwork of ours, so signup can be built and launched immediately.

**Costs (verify before launch):** published rates for India range from $0.01 to $0.07 per SMS
depending on the source; Google's Identity Platform page is the authority — check the IN row in the
billing console. Domestic gateways (MSG91, Plivo) are ₹0.10–0.20. Only the first 10 SMS per day are
free, and phone auth requires the Blaze (billing-attached) plan.

**The trade-off to watch:** with Firebase the SMS is triggered **from the browser**, so our
server-side OTP rate limits do not apply. Mitigations are mandatory, not optional:
- Firebase **App Check** (reCAPTCHA Enterprise) enforced on Authentication
- Firebase console quotas set to a sane daily SMS cap, and a billing alert at a fixed rupee amount
- Allow only `+91` numbers in the client and reject anything else server-side
- Our own per-IP and per-phone throttle on `/auth/firebase` so a stolen token can't be replayed

**Other trade-offs:** the sender ID is Google's, not `VELORA`, so the SMS is unbranded and there is
no DLT registration of ours to show a carrier if asked. Per-OTP cost is far above a domestic
gateway at volume.

**Migration path:** `AUTH_PHONE_PROVIDER = firebase | msg91`. Both paths are built in Sprint 3 and
both create the same session. Switch to MSG91 when DLT is approved, or when monthly SMS spend
exceeds roughly ₹10,000 — whichever comes first. No user is affected: the phone number is the
identity, not the provider.

### D-034 · Location — Locked
Browser geolocation on onboarding, stored as a PostGIS point. Distances shown rounded to whole km,
minimum "1 km". If permission is denied, the user picks their area from a seeded list of
neighbourhoods with centroids.

### D-038 · structlog and orjson; Sentry SDK deferred — Locked
The API logs through **structlog** (JSON in deployed environments, console locally) and serialises
responses with **orjson**. Both were named in T-1.3's plan text but were missing from the pinned
stack table in `CLAUDE.md`, which has now been corrected.

**sentry-sdk is deliberately not a dependency yet.** `SENTRY_DSN` is declared in `Settings` and the
unhandled-exception handler logs with the request id already bound, so T-9.12 adds the SDK and one
reporting call with nothing else to change.
**Why defer:** a dependency that is installed but not configured is a liability — it ships code,
CVEs and import cost for no behaviour. It arrives when it is actually wired up.

**Amended in T-1.6 (P-03): orjson removed.** FastAPI 0.141 deprecates `ORJSONResponse` because it
now serialises responses itself, through Pydantic, whenever a route declares its return type —
and rule 9 requires one on every route. Error handlers use plain `JSONResponse`. With nothing
left using orjson it was removed, by the same rule as sentry-sdk above: no unused dependencies.

### D-039 · pre-commit and gitleaks; golden rules enforced by lint — Locked
**pre-commit** runs hooks on every commit; install once per clone with `make hooks`. **gitleaks**
blocks secrets before they reach a commit. Both were named in T-1.6's plan text but missing from
the tooling row in `CLAUDE.md`, which has now been corrected.

- ruff and mypy run as **local hooks through `uv`**, so their versions come from `api/uv.lock` and
  match `make lint` exactly. The usual isolated mypy hook cannot see FastAPI or Pydantic, so
  strict mypy would fail there.
- gitleaks is a pinned hook that **pre-commit builds itself**, bootstrapping Go if needed — no
  system install on any machine, CI included. Verified: a fake GitHub token in a real
  `git commit` is blocked and `HEAD` does not move.
- **Golden rules are lint errors, not review items.** ruff bans `print` (`T20`), and `requests`,
  `psycopg2`, `time.sleep`, `datetime.now`/`utcnow`/`today` and `date.today` (`TID251`, rule 7).
  The one sanctioned wall-clock read, in `core/clock.py`, is exempt by a single-line `noqa` — not
  a per-file ignore, which would also have exempted `requests` in that file.
- mypy is `strict` for `app/` and `tests/`, with pydantic's plugin (ships inside pydantic).

**Why:** a rule that only a reviewer catches is a rule that eventually gets missed.

### D-040 · GeoAlchemy2 for geography columns — Locked
`profiles.location` and `areas.centroid` are `geography(Point,4326)`, which SQLAlchemy has no
type for. **GeoAlchemy2** provides it: the models declare real `Geography` columns, the
models-match test can reflect and compare them, and discovery queries (`ST_DWithin`, T-4.x) are
typed. Columns set `spatial_index=False` and declare their GIST index explicitly, so index names
follow our naming convention rather than GeoAlchemy2's `idx_…`.

**Rejected: a hand-written `geography` type with no dependency.** The models-match test could not
compare those two columns — silently, which is exactly the drift it exists to catch — and
discovery would lose typing.

### D-036 · Local infrastructure binds to loopback only — Locked
Every port published by `infra/docker-compose.yml` is bound to `127.0.0.1`, never the Docker
default of `0.0.0.0`: Postgres 5432, Redis 6379, MinIO 9000 and 9001.
**Why:** the dev stack runs with development credentials and a Redis with no password at all. Bound
to `0.0.0.0`, all three are reachable by anyone on the same network — a café, a coworking space, a
shared flat. This was measured during T-1.2, not assumed: from the host's own LAN address the dev
Redis answered `PING`, Postgres accepted `velora`/`velora`, and the public bucket served anonymous
reads. Nothing outside the host needs these ports; the API, worker and web all run on the host or
inside the compose network.
**If a service ever must be reachable from another device** (a phone on the same wifi testing the
web app), publish that one port deliberately and say why — do not revert the whole file.

### D-042 · Web unit tests and icons — Locked
T-1.19 added the web app's unit-test tooling and its icon set. Versions are pinned exactly.
- **lucide-react** (icons). The only runtime addition, so the only one in `dependencies`. The
  plan names it, and the prototype's icons are Lucide's own paths. Components import each icon by
  name, so only the icons used are bundled.
- **vitest** with **vite** (a required peer of vitest 5) and **jsdom**, the DOM that Next 16's
  Vitest guide uses.
- **Testing Library**: `@testing-library/react` with its peer `@testing-library/dom`;
  `@testing-library/user-event`, because the Sheet's focus trap needs real Tab and Shift+Tab, which
  `fireEvent` can't produce; and `@testing-library/jest-dom` for matchers such as `toHaveFocus` and
  `toHaveAccessibleName`.
- All the test tooling is in `devDependencies`, so none of it ships in the production bundle.
  `@types/node` moved from `^20` to `^24`, matching `engines` and vitest's peer range.

**Rejected: `@vitejs/plugin-react` and `vite-tsconfig-paths`**, which Next's guide adds. Vite 8
compiles JSX from `tsconfig`'s `jsx` setting and resolves `@/` itself (`resolve.tsconfigPaths`),
so neither is needed. **Also rejected: a headless UI or focus-trap library.** The plan asks for
the primitives to be built, and the Sheet's trap is about 30 lines with tests on both Tab
directions, Esc and focus return.


### D-043 · Web data layer — Locked
T-1.18 added the web app's data layer. Versions are pinned exactly.
- **@tanstack/react-query** and **zustand**, both in the pinned stack and both runtime
  `dependencies`. TanStack Query holds server state; zustand holds the session, in memory only
  (D-024).
- **openapi-typescript**, a `devDependency`. `make types` generates `web/src/types/api.ts` from
  the API's OpenAPI schema **offline**: it imports the FastAPI app and dumps `app.openapi()`, so
  it needs no running server, no infrastructure and no exposed `/openapi.json`. That makes it
  deterministic, which is what lets CI fail when the committed types are stale (T-1.20, rule 10).
- `src/lib/api.ts` is typed straight from the generated `paths`: a path or method the API doesn't
  have won't compile. It throws `ApiError {code, message, details, status}` on any non-2xx.
- Queries retry a 5xx or network failure twice and never a 4xx. Mutations never retry: a retried
  payment is a double charge.

**Rejected: `openapi-fetch`.** It does the same typing, but the wrapper is one small file with
no runtime dependency, and it throws instead of returning `{data, error}`, which is what
TanStack Query wants. **Deferred: zod.** Nothing parses user input yet; it arrives with React
Hook Form when Sprint 3's forms need it.


### D-044 · CI is binding through /done, not through pull requests — Locked
CI (`.github/workflows/ci.yml`, T-1.20) runs on every push, to any branch, and is binding from
T-1.20: `/done` pushes the task branch, waits for CI on that exact commit (`scripts/ci-gate`), and
fast-forwards `main` only when that run passed. T-1.22's staging deploy checks again — a second
gate, not the first.
- The gate finds the run by the commit's SHA and checks the run's `headSha`, never "the latest run
  on the branch": between a push and its run appearing, that is an older commit's run.
- It fails closed. No run within 3 minutes, a run not finished within 20, a failed or cancelled
  run, or GitHub not answering all stop `/done` with a message, and `main` stays where it is.
  `scripts/ci-gate-test` proves each case against a fake `gh`, asserting on the message as well
  as the exit code.
- It matches the workflow by name, not with `gh run list --workflow ci.yml`: GitHub resolves that
  against the default branch, so it 404s until the file is on `main` — found by T-1.20's own run.
- "Couldn't reach or authenticate with GitHub" (exit 4) and "GitHub answered with an error"
  (exit 5) are separate. Only exit 4 opens `/done`'s written manual path, whose first step is
  checking the token, since a bad token is the usual cause. An ordinary API error can never
  reach the bypass.
- CI runs every pre-commit hook and a full-history gitleaks scan, because `git commit --no-verify`
  skips the local hooks, and the colour-token hook runs nowhere else.
- Third-party actions are pinned to commit SHAs. gitleaks is its release binary, with the checksum
  committed in the workflow, so a tampered release fails instead of running.

**Rejected: required status checks.** GitHub attaches them to pull requests, and this project
merges by fast-forward without pull requests, so there is nothing to require them on. The `/done`
gate does the same job without one. **Rejected: `gitleaks/gitleaks-action`** — third-party code in
CI, for what a checksum-verified binary does.


### D-045 · Fake providers run only where ENV is local — Locked
Every external service sits behind a provider (D-028; storage joined in T-1.21), selected by a
`*_PROVIDER` setting whose default is `fake`. `Settings` refuses to start when any of them is
`fake` and `ENV` is not `local`, naming each one: staging and production must set a real provider
for all seven, `AUTH_PHONE_PROVIDER` included. It is an allowlist (`FAKES_ALLOWED_IN`, CLAUDE.md
rule 16), and it is only as good as `ENV` itself, which therefore has no default — a deploy that
forgets it fails to start instead of quietly becoming `local`.

**Why:** the fakes are the two worst failures this app could have. A fake payments gateway grants
credits nobody paid for; a fake phone sign-in lets anyone in as anyone. With `fake` as a silent
default, forgetting one variable in a deploy would ship either.

**Rejected: defaults of real providers.** Local development and tests would then need every
real provider's keys, which D-028 exists to avoid. **Rejected: refusing fakes only in
production** — a blacklist, which staging and any environment named later would pass.


### D-046 · Staging deploys from CI, migrations run as the owner from CI — Locked
Staging (T-1.22, `infra/STAGING.md`) deploys only a commit whose CI passed: `deploy.yml` runs after
CI on `main` and first re-checks that exact commit with `scripts/ci-gate` — a second gate after
`/done`'s (D-044). Migrations then run **from CI, as the database owner**, over Supabase's IPv4
session pooler. The API on Fly connects as `velora_api`, a login role in `velora_app`, which reads
and writes rows and nothing more (P-18). The web deploys from the same workflow with the Vercel
CLI, into its own project with no Git connection, so it can't go live around the gate. After every
deploy, `scripts/staging-smoke` checks staging from the outside, bodies included.

**Why:** the owner can switch off the ledger's triggers (`ALTER TABLE … DISABLE TRIGGER`), and those
triggers are the last line protecting money. Owner credentials on Fly, beside the app, would put
that one code-execution bug away.

**Rejected: Fly's release command** for migrations — it runs with the app's own secrets, so the
owner's credentials would live on Fly. **Rejected: Vercel's Git integration** — it deploys every
push, ignoring CI. **Rejected: gunicorn** — a new dependency for what uvicorn's `--workers` already
does; the image checks settings before the workers start, so a bad configuration exits instead of
crash-looping. **Deferred:** the worker's Fly app, to T-4.4, which builds the worker.


### D-047 · Local and CI run Postgres 16; Supabase runs 17 — Open
Supabase created the staging project on **Postgres 17.11 with PostGIS 3.3.7**, the version it gives
every new project. Local and CI run **Postgres 16 with PostGIS 3.4** (`postgis/postgis:16-3.4`).
The layout differs too: Supabase installs the extensions in an `extensions` schema, locally they
sit in `public`.

**Why it matters:** local passing proves nothing about staging (06-TESTING). The layout difference
has already hidden one bug: the app role had no USAGE on `extensions`, which no local test could
see, found only by connecting to staging (fixed by migration `67e81c6c203d`). A version difference
can hide the next one.

**Decided now:** the gap is known and accepted for the moment; P-34 moves local and CI to 17. That
closes the gap without eliminating it: `postgis:17` images ship PostGIS 3.5, and Supabase's is 3.3,
so staging stays the only place PostGIS behaviour is verified.


### D-048 · The API runs on Fly in Singapore; the data stays in Mumbai — Locked
Supersedes D-023's region for the API and worker: they run on Fly.io in **Singapore (`sin`)**.
Postgres (Supabase) and Redis (Upstash) stay in **Mumbai**, so Indian users' data stays in India.
Moving it out would take a new decision, after the DPDP session (P-0.7).

**The cost, plainly — measured, not estimated:** every request crosses Singapore to Mumbai and back
several times. Measured from the staging API machine on 1 October 2026:
- **165 ms per round trip**, the same over Supabase's direct host (IPv6) and its pooler (IPv4), so
  the route itself costs that;
- **1,156 ms for a pooled connection checkout plus one query** — SQLAlchemy spends round trips on a
  liveness ping, `BEGIN`, the query and `ROLLBACK`;
- **2.85–3.5 s to open a new connection** (TLS, authentication, first-connect queries);
- so **a profile load, with a few queries, costs about 1–1.5 s of server time**, on top of the
  user's own latency to Singapore.

**Amended 1 October 2026:** the decision was first recorded on an estimate of "roughly 350 ms", the
founder's. The measurements above show that was wrong by 3–4×. The decision stands — the founder
is shipping on Singapore — but on the true cost. 09-RESEARCH's C7 (basic quality, swipe lag first)
names lag as a real complaint driver, so this works against something we said we'd be better at.

**A known optimisation:** dropping the per-checkout liveness ping (`pool_pre_ping`, one round trip
on every request) in favour of recycling connections by age saves 165 ms per request. The round
trips themselves stay for as long as the API is in Singapore and the data in Mumbai.

**Why anyway:** Fly deprecated `bom` on 25 September 2026 (the date per the founder), and no India
region remains on Fly. On 1 October its API refused new machines there: "Region bom is deprecated
and cannot have new resources provisioned" (P-36). Shipping now matters more than the latency does
at this stage.

**Why the data stays in Mumbai:** moving the API back to an India host later is cheap — a different
host, a redeploy, a DNS change. Moving the database after launch, with live user data, is not.
Keeping it in Mumbai is what keeps the India option open.

**Rejected: everything in Singapore** (Supabase and Upstash moved too). That would move Indian
users' photos and phone numbers out of India before the DPDP session — a legal and positioning
question, not a latency one. **Deferred: another India host for the API** (for example AWS
`ap-south-1` or Google Cloud Run `asia-south1`). It's the right home eventually, but it means
redesigning the deploy just built, and it waits while shipping matters more.

**Amended 1 October 2026: what actually stays in India.** The database (profiles, messages, the
ledger, payments and our hashed and encrypted copy of each phone number) and Redis are in Mumbai.
The rest is not: Firebase Authentication processes phone numbers in the United States and Google
keeps them for abuse prevention (D-035); Cloudflare R2, which has no India location, stores
photos, selfies, voice notes and album images; Sightengine moderates photos on servers in the US
and Europe; and every request is processed in Singapore. "Data stays in India" was our own
promise, not a legal requirement: DPDP section 16 allows transfers except to countries the
government restricts, none is restricted as of September 2026, and the section takes effect on
13 May 2027. The rejection of "everything in Singapore" rested partly on keeping photos and phone
numbers in India, which this setup doesn't do either. What still holds: the database carries most
of the personal data, and moving it later, with live data, is the expensive move. The Privacy
page says where each kind of data goes (T-2.2).

**Follow-ups decided the same day:** the R2 buckets use the `apac` location hint, for latency; it
is best effort, so the Privacy page says only "stored by Cloudflare, outside India" and never
names a region we aren't guaranteed (`infra/STAGING.md`). Sightengine deletes each image right
after its check (T-4.4). The phone step asks for consent and names Google (T-3.11, T-3.14);
deleting the Firebase user right after sign-in waits for P-39.

### D-049 · Vela is the unit of paid balance — Locked
What men buy and spend is a **Vela** (plural **Velas**): "1 Vela", "5 Velas". It replaces
"credits" in everything users read and in the docs' prose. In the schema, the API and code the
unit keeps its neutral accounting name, `credits`, so renaming the unit never needs a migration or
an API change. Earlier decisions say "credits"; read it as Velas.

**A deliberate coupling:** Vela derives from the brand, so if D-015 forces a new name, the unit is
renamed with it. That is the one exception to CLAUDE.md rule 17, and because only copy carries the
name, it stays a copy change.

"Token" was never the unit; auth, design and platform tokens keep their names.

**Rejected: renaming the schema, API and code identifiers too** — a migration across live money
tables and an API break, repeated whenever the brand changes. Decided by the founder on
1 October 2026.

### D-050 · Velas are final and never expire; broken payments are fixed — Locked
**Purchases are final.** Someone who bought Velas and changed their mind gets nothing back, whether
or not they spent them.

**A broken payment is ours to fix.** A payment that went through without granting Velas, or a
duplicate charge for one purchase, is a broken transaction, not a change of mind: the missing
Velas are granted, and the duplicate charge is refunded to the original payment method.
Webhook-only grants, idempotent on the payment (D-026), are what make both fixable.

**Two cases return Velas automatically**, because the product works that way: a declined request
to see a private album (D-004), and Velas spent on someone who is then banned, for the 7 days
before the ban (T-9.3).

**Velas never expire.** They have no cash value and can't be transferred or given to another
account. Expiry would earn a little and cost a lot in anger, chargebacks and support, and it cuts
against D-003's principle that permanence is granted, never bought.

`/refunds` and `/terms` say all of this plainly (T-2.2). Payment gateways require a visible refund
and cancellation policy for merchant approval; P-0.8 confirms each gateway's exact requirement.
**Supersedes** T-8.3's earlier plan to refund unspent credits within 7 days of purchase: T-8.3 now
handles broken-transaction claims only. Decided by the founder on 1 October 2026.

### D-051 · What deleting an account erases, and what it keeps — Locked
**Erased:** the profile, photos, private album and everything else other people can see of the
person, except their messages.

**Messages stay.** The other person keeps their copy, with the sender shown as "Deleted account",
and the messages stay as moderation records. Erasing them would let an abuser destroy a victim's
evidence by deleting their account: the hole D-006 closes for clearing a chat.

**Kept:** the ledger and payment records, reports and moderation records, and a hashed phone
number, so a banned or reported person can't delete and re-register to escape it. Deletion must
not be a route around a ban.

The Privacy page says this plainly (T-2.2): users deserve to know what survives, including Google's
copy of the phone number, which is outside our control (D-048). Decided by the founder on
1 October 2026.

### D-052 · Terms we can stand behind — Locked
**Law and courts:** Indian law, and the courts with jurisdiction over the registered office in
Phagwara (D-013). The exact court is named once registration completes (P-0.2) and shows as
outstanding until then. No liability language the founder can't explain and stand behind.

**Grievances:** the IT Rules' timelines exactly: acknowledged within 24 hours, resolved within 15
days. Nothing faster is promised: a solo founder can't keep a shorter promise, and a missed
promise on that page is worse than the statutory one.

The law-and-courts text is the first thing P-0.7's review checks: of the text we wrote ourselves,
it is the weakest. Decided by the founder on 1 October 2026.

### D-053 · Missing legal facts can't reach production — Locked
The legal pages (T-2.2) state facts we don't have yet: the company's name, registered office
address and court, and the Grievance Officer's name (P-0.2), and the support and grievance emails
(P-0.3). `web/src/lib/legal.ts` holds every fact, each either known or marked missing with the
plan item that brings it, and a missing one shows as "To be confirmed".

A page with a missing fact builds only under `next dev` or where `APP_ENV` is `local`, `ci` or
`staging`: an allowlist with no default (CLAUDE.md rule 16, the D-045 pattern). Anywhere else,
`next build` fails and names every missing fact. Production sets `APP_ENV=production`, so it can't
ship until P-0.2 and P-0.3 are done; forgetting to set it fails the same way.

It blocks on facts only, never on a review. P-0.7 is the founder's own review of the text and
gates going live (T-9.15), not the build.

**Rejected: a check in the production deploy workflow** — T-2.6 hasn't built that workflow yet,
and a check that lives in a future file can be forgotten; a build that fails closed can't.
Decided by the founder on 1 October 2026.

### D-054 · The refresh cookie is host-only on the API — Locked
Supersedes D-024's cookie scope. The refresh cookie carries no `Domain` attribute, so the browser
keeps it for the API's own host and sends it nowhere else: `api.veloraapp.co.in` in production,
staging's API host on staging. It is still `HttpOnly; Secure; SameSite=Lax; Path=/v1/auth`, and
the rest of D-024 stands.

**Why:** the cookie is HttpOnly, so only the API ever reads it; the web never can. Scoping it to
the whole site was always wider than anything needed, so host-only is the right scope on its own
merits. Staging stops receiving production refresh tokens as a consequence: staging's subdomains
are the same site as production's (P-33), and a site-wide cookie would reach staging's API. Each
environment's refresh cookie stays on its own API host, so the two never reach each other.

**Not covered: the readable `csrf` cookie.** The web reads it to send `X-CSRF` (D-024), so it
can't be host-only on the API: in production it must be scoped to `veloraapp.co.in`, which
reaches staging too. It isn't a credential on its own, so nothing leaks. But staging's pages then
see two cookies named `csrf`, and staging's refresh can fail for anyone signed in to production.
It is settled before T-3.3 (on its Needs line).

**Rejected: staging on a domain of its own.** It would keep the environments apart but leave
production's refresh cookie wider than anything needs. Decided by the founder on 2 October 2026.

### D-055 · Auth cookies are named for their environment — Locked
Settles what D-054 left open. Both auth cookies carry their environment in their names: the
refresh cookie is `refresh_prod`, `refresh_staging` or `refresh_local`, and the readable CSRF
cookie `csrf_prod`, `csrf_staging` or `csrf_local`. No environment gets a bare name. The CSRF
cookie's `Domain` is `COOKIE_DOMAIN`, so the web can read it: `veloraapp.co.in` in production,
`staging.veloraapp.co.in` on staging.

**Why the CSRF cookie:** the web reads it to send `X-CSRF` (D-024), so it can't be host-only on
the API like the refresh cookie (D-054). Production's must be scoped to the whole of
`veloraapp.co.in`, which reaches staging. Named apart, the two never collide: staging reads only
`csrf_staging`. Staging's own is scoped to `staging.veloraapp.co.in`, which is why staging's API
is `api.staging.`, not `staging-api.`: its cookie never reaches production (P-33).

**Why the refresh cookie too:** host-only (D-054) already keeps each environment's apart, but that
protection rests on a single property. If the cookie is later made domain-scoped, by undoing D-054
by accident or copying a snippet, the collision comes back silently and sign-in starts failing at
random. With per-environment names, the same mistake shows up as two differently named cookies
sitting harmlessly side by side. It is the shape of D-053's gate and rule 16: when a thing can
fail invisibly, make it fail visibly instead. One rule for both cookies also leaves no exception
for anyone to remember.

**Why production is named too:** a bare name would make production the implicit default that
every future environment collides with: a preview deploy, a second staging, a local build pointed
at staging. Name every environment and none is the one the others shadow. It is rule 16's
principle, no implicit default.

**Rejected, both Claude's proposals:** a bare `csrf` in production beside `csrf_staging`, which
leaves production as that implicit default; and an unnamed refresh cookie, which is safe only
while nothing changes its scope. Decided by the founder on 2 October 2026.

### D-056 · Per-IP limits key on the address Fly's proxy saw — Locked
A per-IP rate limit reads the client's address from `CLIENT_IP_HEADER`, which on Fly is
`Fly-Client-IP`, set by Fly's proxy. Never from `X-Forwarded-For`, whose leftmost entries the
client writes, and never from `request.client` outside local: behind Fly the socket is the proxy,
and uvicorn, started with `--forwarded-allow-ips '*'`, fills `request.client` from that same
client-written header. Settings refuse to start outside local without `CLIENT_IP_HEADER` (rule
16's allowlist). An IPv6 address counts as its /64, since one home connection usually gets a whole
/64. A missing or garbled header puts the request in one shared bucket, so leaving the header out
escapes nothing.

**Why it's a decision:** the failure is invisible. A limiter keyed on a client-written header
passes every test, because no test forges a header, and limits nothing. Someone later
"simplifying" it back to `request.client.host` would silently remove the limit, and nothing would
go red. This entry is what stops that. The tests forge the header for the same reason: keyed on
`X-Forwarded-For` instead, five of them fail (checked in T-2.3).

**Proved on staging, not taken from Fly's docs:** they don't say whether the proxy overwrites a
`Fly-Client-IP` the client sends, so the only honest answer is to forge it and watch the limit
hold. T-2.3's Done-when does that.

**Rejected:** `request.client.host` and `X-Forwarded-For`, for the reasons above. Decided by the
founder on 2 October 2026.

### D-057 · The waitlist answers a repeat exactly as a new email — Locked
`POST /v1/waitlist` answers `201` with `{}` whether the email is new or already on the list, in
any case (citext), and a repeat changes nothing, not even the city.

**Why:** a different answer for a repeat would make the endpoint an email checker: anyone could
test whether an address is on our list.

**Rejected:** `409 ALREADY_EXISTS` for a repeat, the API's usual answer to a duplicate. Decided by
the founder on 2 October 2026.

### D-058 · Registered office in Hajipur, launch city Phagwara — Locked
Supersedes D-013, which bundled two facts into one place. They are now two places, both correct:
- **The registered office**, where legal notice is served: Shubham Kumar, House No. 163, Anwarpur
  Chowk, Hajipur, Vaishali, Bihar – 844101. It lives in `web/src/lib/legal.ts` with the other
  legal facts (P-0.2).
- **The launch city**, the seeded areas and the first users: Phagwara, Punjab, unchanged, with
  D-013's 25 km default radius. P-38 is unaffected.

**They differ on purpose. Don't reconcile them.** Hajipur in `legal.ts` and Phagwara in the seed
data isn't a mismatch: one is where the business is registered and served notice, the other is
where the app opens first. Making them agree would put a wrong address on the legal pages or the
wrong city in the product. A test in `legal.test.ts` fails if the registered office changes, and
its message sends whoever changed it here.

**The footer's town is read from the registered office**, not written separately: one fact
rendered twice (in full on Contact and in Terms, as its town in the © line), not two facts that
can drift apart.

**The business is a sole proprietorship** (P-0.2 had recommended an OPC). Its name on record is
"Shubham Kumar, sole proprietor", and Shubham Kumar is the Grievance Officer. **The name must
match the proprietor's PAN and bank account exactly:** Razorpay's KYC compares them, and a
mismatch stalls payouts later. Don't tidy it up. The legal pages label it "Run by", not "Company":
calling a proprietorship a company is a small untruth on pages whose whole job is being true, the
same reason T-2.2 wrote its own policies instead of copying one and D-053 never invents a fact.

**The court follows the registered office, not the launch city:** the courts at Hajipur, Vaishali
district, Bihar. A Bihar address with a Punjab jurisdiction clause reads as careless, and it's the
first thing anyone would pick at. This replaces D-052's "in Phagwara"; the rest of D-052 stands.

**The clause carries less than it looks like.** Under the Consumer Protection Act 2019 an Indian
consumer may file where they reside, whatever the terms say, so it governs commercial disputes,
not users' complaints. Terms says so in one plain sentence: it discloses a right that exists
whether or not we mention it, and creates no obligation, so its only downside is being redundant.
Without it, the clause reads as though a user must come to Bihar to complain, which isn't true.
**Neither the founder nor Claude is a lawyer:** if the terms are ever reviewed properly, show this
line to one (P-0.7).

Decided by the founder on 2 October 2026.

### D-059 · The CSP is as strict as today's pages, and each task widens it — Locked
**Enforced from T-2.5, not report-only:** `default-src 'self'; script-src 'self' 'unsafe-inline';
connect-src 'self' <the API>; object-src 'none'; base-uri 'none'; form-action 'self';
frame-ancestors 'none'`, with `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: strict-origin-when-cross-origin` and a `Permissions-Policy` denying the camera,
the microphone, location and Chrome's ad topics. `web/src/lib/security-headers.ts` builds it.
Under `next dev` only (an allowlist, rule 16) it adds what React's tooling and `/dev/ui` need.

**Each task widens it there, deliberately; nothing is loosened ahead of time** for features that
don't exist yet. Firebase sign-in (T-3.14), photos (T-4.6), the selfie camera (T-4.7), location
(T-4.10), voice notes (T-7.11), real time (T-7.12), checkout (T-8.7), Sentry (T-9.12) and
analytics (T-10.2) each fail until their task widens it, and the failure would look like the new
feature's bug rather than the policy's. So the coupling is written where each builder will stand:
in the policy's comment, and as a line on each task.

**`'unsafe-inline'` for scripts is a trade with an expiry.** Next writes its page data as inline
scripts, and without the allowance the waitlist form never hydrates (T-2.5's trial). Nonces would
render every page per request, with no CDN cache and a slower first byte, spending the Lighthouse
margin. The allowance was justified by a threat model in which no user-supplied text renders.
That stops being true at T-3.11 (the user's own name and `@username`) and sharply at T-6.5 (other
people's names and bios), and both carry a line to re-examine it there. React's escaping is the
real defence for user text; the CSP is the second line, and a weakened `script-src` matters
exactly then.

**Framing is forbidden explicitly** (`frame-ancestors 'none'` and `DENY`), never left to a
default: a dating app is never framed.

**Silent until T-9.12.** An enforced policy with no reporting doesn't say when it blocks something
real; a violation in production stays invisible until a user complains. T-9.12 wires its reports
to Sentry.

**Left out:** `upgrade-insecure-requests`, never measured, and by its definition it would break
`next start` and the E2E over local http. HSTS is Vercel's (max-age two years). `includeSubDomains`
and preload are T-2.6's decision, with their own record: preload is close to irreversible, because
browsers hardcode it and removal takes months.

**02-ARCHITECTURE §12 now describes what is served.** Until T-2.5 it described the eventual policy
(Razorpay, the CDN, Firebase, and the camera, microphone and location allowed) as though it were
running. That's the error D-048's "what actually stays in India" amendment (1 October 2026)
corrected: a document stating the intended thing as the running thing. Widening happens at the
task that needs it, and §12 changes with it.

**Rejected:** report-only (it protects nothing, and no collector exists to read it); nonces (every
page dynamic, spending the margin); Next's experimental hash-based SRI (experimental, and not shown
to cover the inline page data); loosening ahead of time for the tasks above. Decided by the
founder on 2 October 2026.

**Amended 2 October 2026 (T-2.5's Done-when): check "exactly these, and nothing else".** The
founder's securityheaders.com scan found `access-control-allow-origin: *` on the page response:
Vercel's default, never decided, the same shape as `X-Powered-By`. Our checks missed it because
they asked whether the five headers we wanted were present. That's an inclusion check, and it can
never find a sixth header we didn't want. Where we care about what is served, the check is
"exactly these, and nothing else". P-43 deals with the wildcard. The outside grader stays in
Done-whens: we had read the headers, watched Chrome refuse the frame and run Lighthouse, and the
outsider still saw the thing we hadn't thought to look for.

### D-060 · Security primitives come from vetted libraries — Locked
**The libraries (rule 4):** PyJWT for access tokens, argon2-cffi for PINs, cryptography for phone
encryption (Fernet) and key derivation (HKDF), phonenumberslite for parsing numbers, and `hmac`,
`hashlib` and `secrets` from the standard library. `core/security.py` writes no primitive of its
own. PyJWT was already installed, because `redis` depends on it, and is declared directly anyway:
what another package happens to pull in is no promise. cryptography arrives with T-3.14 regardless
(`firebase-admin` needs `pyjwt[crypto]`, and `google-auth` needs cryptography).

**What we write is policy:** India only, which key does what, the token's claims, exactly one
accepted set of argon2 parameters (D-062), the rule that an empty CSRF value never matches, and
expiry. PyJWT checks the signature, the algorithm (HS256 only), the audience and that every claim
is present, but it reads the wall clock, which rule 7 forbids and tests can't move. So expiry is
compared against `core.clock`, and only after the signature: a forged token is never told it
expired.

**Access tokens carry `aud` = `ENV`,** and exactly `sub`, `role`, `aud`, `iat` and `exp`, for 15
minutes (D-024). Separate `JWT_SECRET`s keep staging's tokens out of production; that rests on one
property, so the audience is a second one (D-055's reasoning). Refresh tokens and CSRF values are
32 random bytes; a refresh token is stored as plain SHA-256, since 256 random bits leave nothing to
guess.

**Keys are hex, checked at startup in every environment:** `JWT_SECRET` at least 128 characters
(`openssl rand -hex 64`); `PHONE_PEPPER`, `CODE_PEPPER` and each `PHONE_ENC_KEY` exactly 64
(`openssl rand -hex 32`). A short key fails nothing later, it just protects less, so it fails at
startup, with a message that names the setting and never echoes the value.

**The repo's test keys work only where `ENV` is local** (`PUBLIC_TEST_KEYS`, rule 16). The tests
and CI need valid keys, and committed keys are public. If one reached staging or production by
copy and paste, anyone who can read the repo could sign an admin's access token, and nothing would
fail. Startup refuses them anywhere else, compared as bytes so capitals don't hide one. A test
holds CI's four keys to that list, and CI's container checks, which run as staging, draw throwaway
keys instead.

**The token lifetime and the argon2 cost are constants, not `app_config`:** an exception to
checklist A. A security value that a database write could change, with nothing failing, isn't
one.

**phonenumberslite, not phonenumbers:** the same library and release without the geocoder, carrier
and timezone data we never read, 1.2 MB unpacked against 21.9 MB. It validates against number
ranges that Google updates with each release, so an old copy refuses newly issued Indian numbers at
signup. Upgrade it with the other dependencies; never pin it and forget it.

**Rejected:** full phonenumbers (above); PyJWT's own expiry check (the wall clock); relying on
redis's copy of PyJWT. Decided by the founder on 3 October 2026.

### D-061 · Phone numbers are encrypted in the API, not with pgcrypto — Locked
**This supersedes prose, not a decision.** 02-ARCHITECTURE §4 and 03-SCHEMA said "pgcrypto" from
the first docs commit (`f85315e`). It was never a numbered decision: no version of this log
mentions it (checked by Claude with `git log -S`). Those lines now point here.

**The decision:** a number is normalised to E.164, +91 only (D-035). Its lookup key,
`users.phone_hash`, is HMAC-SHA256 keyed by `PHONE_PEPPER`. Its stored copy, `users.phone_enc`, is
encrypted in the API with Fernet through MultiFernet: the first key in `PHONE_ENC_KEY` encrypts,
and every key listed decrypts. The column stays `bytea`, so there was no migration.

**Why:** pgcrypto runs inside Postgres, so the key would travel to Supabase with every insert and
select, beside the plain number, and could land in its statement logs; pgcrypto's own
documentation warns about exactly this. Encrypted in the API, the key stays on Fly and Supabase
only ever holds ciphertext: a dump, a backup or a log gives away no numbers. Fernet is a complete
recipe (authenticated encryption, a random IV, a version byte), so we write no cipher code. D-048
doesn't change: the API in Singapore already handles the plain number to hash it, and the stored
copy stays in Mumbai. The pgcrypto extension stays installed (T-1.8); nothing uses it for numbers.

**What it rules out:** decrypting a number in SQL. No planned task needs to (checked by Claude on
3 October 2026 against every mention of "phone" in the docs). Login, bans and an admin's search by
number all go through `phone_hash`, which finds exact numbers only. The few places that show a
number (T-9.5's user detail, T-9.6's export in the worker) decrypt it in Python. The worker shares
`Settings`, so it needs the API's keys (T-4.4).

**Rotation:** `PHONE_ENC_KEY` takes a new key first and the old one after it: a config change.
Re-encrypting old rows can follow at leisure (`MultiFernet.rotate`). `PHONE_PEPPER` never changes
once any number is banned. `banned_identities` keeps only the hash (D-009, D-051), recomputing it
would need the plain number, which a ban doesn't keep, and a new pepper would silently unban
everyone.

**Rejected:** pgcrypto (above); AES-GCM from cryptography's hazmat layer (we'd manage the nonces,
where Fernet manages everything); SHA-256 of the pepper and the number concatenated (HMAC is the
construction for a keyed hash). Decided by the founder on 3 October 2026, on condition that the
code built on MultiFernet from day one, which it does.

### D-062 · PINs: argon2id over a pepper kept off the database — Locked
**The decision:** a PIN is stored as argon2id over an HMAC of it, under a key derived from
`CODE_PEPPER` (HKDF, label `pin/v1`). argon2id with 19 MiB of memory, 2 passes, 1 lane, a 16-byte
salt and a 32-byte hash: OWASP's minimum. `verify_pin` accepts exactly these parameters. A stored
hash made with any others, weaker or stronger, is refused, where argon2-cffi alone would verify
it.

**Why the pepper:** a database leak reveals no PINs at all. Without `CODE_PEPPER`, which lives on
Fly and never in the database, a stored hash can't be tested against even one guess. That matters
because people reuse their UPI and ATM PINs.

**Why this cost, measured:** on staging's machine, one shared AMD EPYC vCPU with 512 MB and two
workers, by Claude on 3 October 2026 over 20 hashes: a median of 18.4 ms (17.1 to 27.0) to hash and
18.1 ms to verify at 19 MiB. RFC 9106's 64 MiB setting, argon2-cffi's default, took 156.9 ms there.
Each hash holds its memory while it runs, so a process runs at most two at once, at most 76 MiB
across both workers, and a burst queues. Hashing runs in a thread, so the event loop keeps serving
(rule 7).

**Raising it buys nothing, so the headroom is not spare capacity.** 18.4 ms is well under the 30 to
60 ms estimated beforehand, and a gap like that invites spending it. Don't. With `CODE_PEPPER` in
place, a leak of the database alone reveals no PINs at any cost. The cost matters only in a full
compromise that takes the pepper too, and there a 4-digit PIN falls in 3 minutes at 19 MiB or 26 at
64 MiB: 10,000 candidates on one core like staging's. Neither is protection; the pepper is. And
memory is the binding constraint anyway: at 64 MiB the same two-at-a-time cap holds
2 × 2 × 64 MiB, 256 MiB of a 512 MB machine.

**A decision, not a tuning knob.** The warning stands at the constant: lowering it weakens every
PIN stored from then on, and nothing fails. Changing it in either direction makes every stored PIN
fail `verify_pin` until it is set again, so a change ships with a migration plan (accept the old
set, re-hash on success). Tests use these exact parameters, and no cheaper set exists in the code.
If a suite ever needs one, it is allowed only where `ENV` is local, opted into explicitly, with a
test that staging and production refuse it; never by lowering these. A test pins them.

**`CODE_PEPPER` is its own key, not `PHONE_PEPPER`,** because their lives differ: `PHONE_PEPPER`
can never change once a number is banned (D-061), and this one can. PINs are optional, so a
rotation can clear them, and people set a new one after their next sign-in by OTP; or a later task
can verify under the old pepper and re-hash. It also keys OTP codes, under their own label
(D-063).

**Rejected:** RFC 9106's 64 MiB profile (8.5 times the time on staging and 3.4 times the memory,
for minutes more against a leak that already includes the pepper); a cheaper test-only profile
(nothing leaks if none exists); the pepper later, in T-3.9. This entry's reason would then have
changed under a locked decision, and the key's machinery is built here anyway. Decided by the
founder on 3 October 2026.

### D-063 · OTP codes are hashed with a keyed HMAC, not argon2 — Locked
**The decision:** T-3.2 stores each code as HMAC-SHA256 over the number's hash and the code, under
a key derived from `CODE_PEPPER` (HKDF, label `otp/v1`, reserved by T-3.1), and compares in
constant time. Not argon2, as the plan first had it.

**Why:** an OTP's protection is its 5 tries and its 5-minute life, not the hash's cost. On an
unauthenticated endpoint argon2 is a DoS amplifier: one cheap request costs us 19 MiB and about
18 ms (measured on staging, D-062) against two slots per process, so a flood stalls every real
OTP behind the cap. With the pepper kept off the database and Redis, a leak of either reveals no
codes.

**Rejected:** argon2 (above); plain SHA-256 (10,000 codes, reversed at once); a separate OTP key,
which would be another secret with the same life, where one key with two labels keeps the uses
apart. Decided by the founder on 3 October 2026; T-3.2 builds it.

---

## Adding a decision

Append `D-0NN · Title — Locked|Open`, with Decision, Why, Rejected. Never edit a Locked entry —
supersede it with a new one that references the old ID.
