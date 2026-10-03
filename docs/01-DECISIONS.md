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
**Noted 3 October 2026:** this decision is load-bearing for the PPI exemption. Any Vela that reaches
a woman is a payment between people, so none ever may (D-076).

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
**Noted 3 October 2026:** a gift debits its sender and credits nobody, and `gift` is a debit-only
ledger reason (D-076, D-077).

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
**Noted 3 October 2026:** money goes back only for a payment with no Velas still standing against
it (D-076, rule 3).

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

**Amended 3 October 2026 (T-2.6): "forgetting to set it fails the same way" stopped being true at
P-0.3.** The gate fires only while a fact is missing, so it caught a missing `APP_ENV` only until
the last fact arrived (`72ef3a2`). Proved the same day: a build with `APP_ENV` unset passed, and
served every page `noindex`, an empty sitemap, and its canonical and share-image addresses on
`http://127.0.0.1:3000`. `next build` now checks `APP_ENV` itself, whatever the facts
(`web/src/lib/build-env.ts`, D-075). Likewise "until P-0.2 and P-0.3 are done" meant their facts:
P-0.2 stays open for PAN, GST and the current account, none of which a page shows.

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

**Amended 3 October 2026 (planning T-3.10 to T-3.13): `'unsafe-inline'` stays for the user's own
text, and is re-examined when a screen first renders another user's.** T-3.11 and T-3.12 are the
first screens to render text a user typed, but only the user's own, shown back to them: the first
name (letters only, T-3.7), the `@username` (`[a-z0-9._]`), hometown, city and about. The worst a
script there could do is self-XSS, behind React's escaping, which is the real defence. So the
allowance stays, and T-3.11 writes the reason in `security-headers.ts`.
**The trigger is a fact, not a task number: re-examine it when a screen first renders another
user's text.** Today that is T-6.5's discovery deck, with other people's names and about text. If
any screen gets there sooner (a profile, a chat preview, a notification), the re-examination moves
to it.
**Nonces are cheaper than this decision first priced them.** They were rejected because they make
every page dynamic. Scoped by Next's proxy to the signed-in routes, `(auth)` and `(app)`, they leave
the marketing pages static with their Lighthouse margin; the signed-in pages carry no performance
target and are never cached for anyone else. That is the option to weigh at the trigger.
Recommended by Claude in the joint plan for T-3.10 to T-3.13; answered by the advisor directing
that plan (Claude, in a separate chat), relayed by the founder, 3 October 2026.

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

**CI's keys are quoted in `ci.yml`, and a test parses them:** run 37078451050 showed why. GitHub
read the unquoted, all-digit test keys as numbers (`PHONE_PEPPER` arrived as
`7.07070707070707E+63`), and the key checks refused them on their first real run, before anything
deployed. A regex over the file's text had passed. The test now loads `ci.yml` with PyYAML, a dev
dependency only (`uv sync --no-dev` keeps it out of the image), and requires each value to come back
a string, hex, of the right length. PyYAML is YAML 1.1 and GitHub's parser isn't exactly that, so the
test proves that a YAML parser makes a string, and the quoting makes every parser agree. Keep
both. Added at the founder's direction on 3 October 2026.

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

### D-064 · The dev seed writes only to the local stack's database, on numbers that may be real — Locked
**The decision:** `make seed` (T-1.15) writes the prototype's 20 profiles and three test accounts
only when three independent facts hold, each an allowlist (rule 16), all before a row is written:
1. `ENV` is `local`;
2. `DATABASE_URL`'s host is `127.0.0.1`, `localhost` or `::1`;
3. the database itself carries the marker `make infra-up` stamps on it: a `COMMENT ON DATABASE`
   from `infra/postgres/stamp-local.sql`, run through psql inside the compose container, so it
   can reach no other database. `velora_test` is never stamped.

And the code isn't in the API image. It lives in `api/seed/`, outside `app/`;
`api/.dockerignore` excludes it, and CI checks the built image has no `/app/seed`.

**Why the database is asked, not just its address** (added by the advisor, 3 October 2026):
an SSH tunnel makes staging's database answer on `localhost:5432`, which passes the first two.
Only the local stack's database was stamped by `make infra-up`. A mistaken run is 23 rows today;
from T-5.1 the ledger refuses DELETE and TRUNCATE, so it would become permanent pollution of a
shared database, with phone numbers that may be real people's. Proved on 3 October 2026 by
Claude: pointed at `localhost:5433`, a second PostgreSQL server standing in for a tunnel, the
seed refused before its first write.

**Why out of the image:** code that isn't in the image can't run in production, whatever a bug
does to `ENV`. That beats any runtime guard.

**The numbers: India reserves no fictional range.** Claude found none on 3 October 2026, with
this caveat: Wikipedia's list of national fictional ranges covers nine countries and regions, and
India isn't among them, but the 2003 National Numbering Plan itself couldn't be read (dot.gov.in
answered 403 and its mirror timed out). Nor can a number `normalize_phone` accepts be known to be
dead. Its validity check is libphonenumber's, whose Indian mobile pattern (9.0.40) lists the 6, 7
and 8 series range by allocated range and takes the 9 series whole. So the seed's numbers, `+91
90000 00001`–`00003` for the test accounts and `00101`–`00120` for the profiles, may each belong
to someone. The guarantee lives in code instead: where `ENV` is local, T-3.2 sends a real SMS
only to numbers a developer lists, and T-3.14 keeps seeded numbers off Firebase's browser path
(D-065). The seed never prints a number.

**Reset is `make infra-reset`, never a targeted delete.** From T-5.1 on, the ledger refuses one
(T-1.12), and the only way round it is the owner's trigger bypass that T-1.22 took away from the
app. `infra-reset` can only touch local Docker volumes, whatever `DATABASE_URL` says. A second
run is insert-only: people are found by phone hash and never updated.

**Rejected:**
- Refusing only where `ENV` is production: a blacklist, which staging passes.
- The host check alone, which a tunnel passes.
- The seed inside `app/`, guarded by `ENV` alone.
- Landline, toll-free or 140 numbers: `normalize_phone` accepts them, but they're real lines, and
  real users sign up with mobiles (P-45).
- Numbers that can't be valid, such as `+91 00000 00001`, which are certainly dead but are rows
  `normalize_phone` can't produce: data that doesn't match what the app makes.
- A denylist of the seed's numbers in every environment's SMS provider: a real owner of one could
  never get a code in production.
- A targeted reset (above).

Decided on 3 October 2026 by an advisor directing T-1.15: Claude, in a separate chat, not the
founder. Approved by the founder on 3 October 2026.

### D-065 · Firebase test phone numbers never go in a project production uses — Locked
**The fact, in Firebase's own words** (its "Test with fictional phone numbers" documentation,
read by Claude on 3 October 2026): "When you provide the fictional phone number and send the
verification code, no actual SMS is sent. Instead, you need to provide the previously configured
verification code to complete the sign in." And: "The ID token minted during this process has
the same signature as a real phone number user."

**What follows (Claude's reading):** T-3.14's API checks a Firebase token's signature against
Google's keys and its audience against our project, so it can't tell a test number's token from
a real one. In a project production accepts tokens from, a test number and its code sign anyone
who has them into production as that number. Firebase's own advice is to "store these numbers
securely and to continuously recycle them": a secret that grants a production login, and nothing
fails when it leaks. In India it's worse, because no number is known to be fictional (D-064).
Firebase "does not allow you to set existing phone numbers used by real users as test numbers",
but it can only check the users it already has. A real owner signing up would get no SMS, only a
prompt for a code someone else holds.

**The decision:** a test phone number goes only in a Firebase project whose tokens production's
API never accepts. As first written, T-3.14's Done-when and T-3.13's staging run used one in the
single project P-0.12 sets up, which production shares. T-3.14 picks the way out: a Firebase
project for staging alone, whose different `FIREBASE_PROJECT_ID` production refuses as an
audience, or the founder's own phone.

**Rejected:** test numbers in the shared project with the code kept secret (above).

The finding is Claude's, from Firebase's documentation. An advisor directing T-1.15 (Claude, in
a separate chat, not the founder) had it recorded as a decision on 3 October 2026, and the
founder approved it the same day.

### D-066 · Path B codes: six digits, served only where chosen, with a ceiling in rupees — Locked
**The decision (T-3.2, T-3.3):**
- `/v1/auth/otp/send` and `/v1/auth/otp/verify` are served only where `AUTH_PHONE_PROVIDER` is
  `msg91` or `fake`, an allowlist (rule 16). Everywhere else they 404, so staging and production,
  on `firebase`, can't be made to send a Path B SMS at all.
- A code is six digits. It is stored as D-063's keyed HMAC, which stands: its "10,000 codes"
  becomes 1,000,000, and plain SHA-256 would still be reversed at once.
- Sending is limited to 5 per phone an hour and 20 per IP an hour, as planned, and also to 100 an
  hour per IPv6 /48, 10 per phone a day, and a global daily cap, `app_config.otp_sms_daily_cap`,
  seeded at 500. At the cap a send gets `503 PROVIDER_UNAVAILABLE`.
- Wrong codes: 5 per code, as planned, and 10 per phone across every code in 24 hours. At 10,
  verify answers `OTP_TOO_MANY` and send `RATE_LIMITED` until the 24 hours pass.
- A banned or unknown number gets exactly the answer any other number gets, and counts against
  exactly the same limits. A ban surfaces only at verify, once the person has proven they hold the
  number.
- Until P-46 builds it, the MSG91 sender is a stub that raises when called, never one that reports
  success: that would say "code sent" with no SMS, found only when a real user waits at an empty
  inbox. A test holds it to raising.
- Locally, D-064's guard is `SMS_LOCAL_ALLOWED_TO`, empty by default: a real provider is called
  only for the numbers listed, and any other gets `503 PROVIDER_UNAVAILABLE` naming the setting,
  its code discarded. Settings refuse the setting outside local, where it would look like
  protection it isn't.

**Why six digits** (the advisor's reversal of Claude's four): with 10 wrong codes a day allowed,
four digits give a 0.1% chance a day of guessing one targeted person's code, about 30% over a
year. For an app whose promise to women is safety, a one-in-three chance that a determined
stalker reaches a specific account isn't shippable. Six digits with the same cap: 0.001% a day,
about 0.4% a year. Indian banks, Paytm, PhonePe and Aadhaar all send six; four reads as an app
that doesn't know what it's doing. Six digits and the cap, both. The prototype's four boxes
change (08-DESIGN's `OtpInput`), not the code; Firebase's codes are six too (T-3.14).

**Why the ceiling.** The worst case with only 02-ARCHITECTURE §12's first limits, at D-035's MSG91
price of ₹0.20 an SMS (not yet confirmed, P-0.5): one attacker on one IPv4 address sends 20 an
hour, ₹96 a day; 10,000 rented residential IPs send 200,000 an hour, ₹40,000 an hour; one cloud
IPv6 /48 holds 65,536 /64 buckets and sends 1.3 million an hour, ₹2.6 lakh an hour. The per-phone
limit bounds harassment of one person (120 texts a day), not spending: an attacker rotates
numbers. MSG91 is prepaid, so the real ceiling would be the wallet, which is also when real users
stop getting codes. With the global cap the worst case is 500 × ₹0.20 = ₹100 a day. The cost: an
attacker can spend the cap and stop Path B sign-ins for the rest of the day, which is acceptable
while Firebase is the launch path.

**Revisit at P-0.5, not on a date:** when MSG91 goes live, the limits, the cap and the price behind
these figures are checked again before Path B is switched on.

**The 50% warning has nowhere to go yet.** At half the cap the API logs a warning to Fly's logs,
which nobody reads: that isn't an alert. Nothing routes alerts until T-9.12 (Sentry, after P-0.6's
account), which carries the line. Until then the gap is known: the first sign of an attack is the
cap being hit.

**Rejected:** four digits (above); the cap or six digits alone; a stub that pretends to send.

Recommended by Claude in the joint plan for T-3.2 to T-3.10, except four digits, which the advisor
directing that plan (Claude, in a separate chat) reversed to six; approved by the founder on
3 October 2026. Locked at T-3.3's `/done`, 3 October 2026.

### D-067 · Sessions: 30 days that slide, a 10-second grace, logout by cookie, a 15-minute tail — Locked
**The decision (T-3.3, T-3.4, T-3.5):**
- A refresh token is valid for 30 days from its own rotation, with no absolute cap: someone active
  never pays for another sign-in SMS.
- Who may sign in: `banned` gets `ACCOUNT_BANNED`, `frozen` gets `ACCOUNT_FROZEN`, `paused` may.
  `deleted` can't occur before T-9.6 and gets `FORBIDDEN` until T-9.6 decides.
- Sessions store no IP address and no user agent; both columns stay empty. `/privacy` lists
  neither, nothing reads them, and reading an address safely would pull in P-40. If T-9.2 needs
  them, it adds them with a line on `/privacy`.
- The CSRF cookie holds `new_csrf()`'s value, renewed at every rotation: readable (not HttpOnly),
  `Secure`, `SameSite=Lax`, `Path=/`, `Domain` from `COOKIE_DOMAIN` (host-only where that's empty,
  locally), for 30 days. The refresh cookie is D-054's and D-055's.
- Both cookies are `Secure` locally too. Safari keeps no `Secure` cookie over plain
  `http://127.0.0.1`, so local sign-in needs Chrome or Firefox, and Safari is tested on staging,
  which has HTTPS. CLAUDE.md says so (T-3.3).
- Two tabs refreshing at once: the second presents the token the first has just rotated. A token
  rotated less than 10 seconds ago gets `401 SESSION_REVOKED` without its family being revoked;
  after that, reuse revokes the whole family, as planned. The web serialises refreshes across tabs
  (the Web Locks API, T-3.10), so the grace rarely matters.
- Logout is authenticated like refresh, by the refresh cookie and `X-CSRF`, not the access token,
  so it still works once that has expired. It revokes the session's family and clears both
  cookies.
- `require_role` reads the user row `current_user` loads anyway, never the token's `role`: a
  demotion takes effect at the next request.
- **A revoked session's access token keeps working for up to 15 minutes**, because access tokens
  are self-contained (D-024). Logout, a reuse attack and five wrong PINs all leave that tail; bans
  and freezes don't, because `current_user` loads the user. Accepted. Read with D-069: the PIN
  lockout's revocation leaves this tail, and the PIN lock is a deterrent, not protection.

**Rejected:** an absolute cap (more sign-in SMS for little gained); revoking on every reuse (two
tabs sign each other out); logout by access token (it fails once that has expired); a session
check on every request to close the 15 minutes (a database or Redis read per request, for a tail
D-024 accepted); storing the IP and user agent before anything reads them.

Recommended by Claude in the joint plan for T-3.2 to T-3.10; answered by the advisor directing
that plan (Claude, in a separate chat); approved by the founder on 3 October 2026. Locked at T-3.5's
`/done`, 3 October 2026.


**Amended 3 October 2026 (planning T-3.10 to T-3.13): "Chrome or Firefox" above is expected, not
observed.** It came from how browsers are documented to treat `http://127.0.0.1`. No browser had
signed in to the web when it was written, and Firefox isn't installed on the development Mac.
CLAUDE.md now says so. T-3.10 records what Chrome and Safari do, and T-3.13 what Firefox does,
each dated; the decision itself, `Secure` everywhere, stands.
### D-068 · Onboarding: a step's endpoint works at the step or after it, never before — Locked
**The decision (T-3.6, T-3.7):**
- Each onboarding step's endpoint works at that step, advancing it, and after it, as an edit that
  doesn't advance. Before it: `ONBOARDING_INCOMPLETE`, with `details.step` the user's current step.
- `dob` and `gender` are the exception: once set, any change is `IMMUTABLE_FIELD`, and T-1.9's
  trigger refuses it too.
- `PATCH /me/profile` spans two steps: `profile` advances once first name, hometown and city are
  all set; `about` advances when about is set at that step. A field of a step not yet reached is
  `ONBOARDING_INCOMPLETE`.
- A username can change until onboarding is `done`; after that it is `IMMUTABLE_FIELD` until T-9.6
  designs changes. Usernames are stored in lowercase.
- Usernames never take a bare top-level path: the public page is D-001's `/@username`, and no
  route segment may ever begin with `@`. The `@` is the namespace, so the reserved list holds names
  that impersonate staff or the product, not route segments.
- Consequence: interests and the PIN come after photos, so a real user can't reach them before
  T-4.3; tests set the step directly.

**Why one rule:** every step works the same way, and later screens (settings) edit through the
same endpoints. **Why the username locks:** it is a link people share (D-001); changing it breaks
links and invites impersonation, and designing changes properly is T-9.6's. **Why never a bare
`/<username>`:** the reserved list would have to hold every present and future route segment, and
it would never be complete. Cheap to settle now, expensive once people own usernames (the
advisor).

**Rejected:** "only at your own step", which leaves no way to edit; `/u/<username>`, which the
advisor recommended in answer 27, because D-001's `/@username` already does the same job (the
founder, 3 October 2026).

Recommended by Claude in the joint plan for T-3.2 to T-3.10; answered by the advisor directing
that plan (Claude, in a separate chat); approved by the founder on 3 October 2026. Locked at T-3.7's
`/done`, 3 October 2026.

### D-069 · PIN: its rules, its reset, and what the lock doesn't do — Locked
**The decision (T-3.9):**
- A PIN is 4 digits (D-012). Refused: one digit four times; straight runs either way (0123…,
  9876…); alternating pairs (1212); the 20 most common PINs in DataGenetics' published study. The
  seed's `TEST_WOMAN_PIN`, 4829, passes, and a test holds it so (T-1.15).
- Changing a PIN needs the current one, except within 10 minutes of a fresh sign-in, read from the
  token's `auth_time` (D-071). That is also "forgot PIN": sign out, sign in by OTP, set a new one.
- Each wrong PIN adds one to `pin_failed`, in one atomic update; a correct PIN or a fresh sign-in
  resets it. **At 5, every session of the user is revoked** and the answer is `SESSION_REVOKED`.
  Read with D-067: each revoked session's access token still works for up to 15 minutes.
- A stored hash `verify_pin` refuses (other parameters, or unreadable) doesn't count: the answer
  is `PIN_INVALID` with `details.reset_required`, and the way out is the fresh sign-in above.
- Skipping the PIN at onboarding is `POST /me/pin/skip`, which moves `pin` to `selfie`; setting
  one at that step does the same.
- The PIN endpoints allow 10 a minute per user: each check holds 19 MiB for about 18 ms, two at
  once per process (D-062).

**What the lock doesn't do.** It deters whoever picks up an unlocked phone; it protects nothing.
The web keeps a working access token behind the lock screen, so the browser's devtools get past
it. Five wrong PINs revoke the sessions, but each one's access token keeps working for up to 15
minutes (D-067), and there is no server-side lock state. Together: **the PIN lockout locks nothing
for fifteen minutes.** Never build on the PIN as a security boundary; it's the `/admin` web gate's
lesson again (P-30). Recording what a feature does not do is what stops someone treating it as
security later (the advisor).

**Rejected:** server-side lock state (a check on every request, for an app lock D-012 never asked
to be more); counting a refused hash as a wrong PIN (it would lock out someone whose hash format
changed, with no way back).

**How the count works (found building T-3.9):** a try is counted, and committed, before the PIN is
checked, by a statement that refuses a sixth. So tries made at once are each counted, no more than
five are ever checked between resets, and past five nothing is checked, the right PIN included,
until a fresh sign-in. The lockout still locks nothing for fifteen minutes (above); it only stops
the guessing.

Recommended by Claude in the joint plan for T-3.2 to T-3.10; answered by the advisor directing
that plan (Claude, in a separate chat); approved by the founder on 3 October 2026. Locked at T-3.9's
`/done`, 3 October 2026.

### D-070 · Sign-in numbers are Indian mobiles only — Locked
**Supersedes** D-061's "a number is normalised to E.164, +91 only (D-035)", and T-3.1's text for
`normalize_phone`. From T-3.2, `normalize_phone` also refuses a valid Indian number that isn't a
mobile: landlines, toll-free 1800 numbers and the 140 series (P-45), as `VALIDATION_ERROR` on
`phone` ("isn't a mobile number"). The rest of D-061 stands.

**Why:** signing in sends an SMS, which these numbers can't receive, so T-3.2 would pay for it and
spend the sender's rate-limit slots. In the one function every path calls, every path gets it. The
seed's and `make_user`'s numbers are mobiles.

**How it lands:** T-3.1's tests of `normalize_phone` are updated to the new rule, still asserting
the exact error for each case, with the non-mobile cases added; never loosened. A locked decision
quietly widened is worse than one openly replaced (the advisor). Until T-3.2 lands, D-061's
sentence governs.

**What "a mobile" means in code (found building T-3.2):** libphonenumber's type is `MOBILE` or
`FIXED_LINE_OR_MOBILE`, an allowlist; everything else India's metadata has is refused:
`FIXED_LINE`, `TOLL_FREE` (1800), `UAN` (the 140 series), `SHARED_COST` (1860) and `PREMIUM_RATE`.
`FIXED_LINE_OR_MOBILE` is the library saying it can't tell, and it isn't rare. Of 200,000 random
valid numbers in each series, Claude measured with 9.0.40 on 3 October 2026: 33% of the 7 series and
38% of the 8 series came back `FIXED_LINE_OR_MOBILE` (the 6 series 0.08%, the 9 series none). The
library's own `FIXED_LINE` example for India is one of them. Those are shares of the numbering
plan, not of real subscribers, but requiring `MOBILE` alone, as P-45 first suggested, would turn
away real mobiles in exactly those ranges, which this decision never meant: it refuses numbers that
aren't mobiles, not numbers the library can't place. A test checks that exactly these two of India's
types sign in, so a type added later is refused until someone decides.

Recommended by Claude in the joint plan for T-3.2 to T-3.10; answered by the advisor directing
that plan (Claude, in a separate chat); approved by the founder on 3 October 2026. Locked at T-3.2's
`/done`, 3 October 2026.

### D-071 · Access tokens carry the sign-in time, `auth_time` — Locked
**Supersedes** D-060's "exactly `sub`, `role`, `aud`, `iat` and `exp`". From T-3.3, access tokens
carry exactly those and `auth_time`: when this device's session family signed in, by OTP or
Firebase, carried unchanged through every refresh (T-3.4).

**Why:** D-069's PIN reset has to know a sign-in is fresh, without a database read on every
request. `auth_time` is OpenID Connect's claim for exactly that.

**How it lands:** T-3.1's test that asserts the claim set is updated to the new exact set, never
loosened to "at least these", and `decode_access_token` requires `auth_time` like the rest. Until
T-3.3 lands, D-060's claim set governs.

**Where it lives (found building T-3.3):** on the session row, `sessions.auth_time`, which a
refresh copies to the new session unchanged. The opaque refresh token can't carry it, and the
family's first session can't be found again cheaply: it is rotated, so revoked, and the only index
on `sessions` is partial (`revoked_at IS NULL`), so every refresh would scan the table. One
additive migration, on a table nothing had written to yet.

Recommended by Claude in the joint plan for T-3.2 to T-3.10; answered by the advisor directing
that plan (Claude, in a separate chat); approved by the founder on 3 October 2026. Locked at T-3.3's
`/done`, 3 October 2026.

### D-072 · An under-18 refusal deletes the account and keeps only the number's hash — Locked
**The decision (T-3.6):** `UNDERAGE` deletes, in the transaction that refuses the date, the user
and everything attached: the user row with its encrypted number, the profile, wallet,
notification preferences and sessions. It keeps only what D-009 has always required, the number's
hash in `banned_identities` (`reason` `underage`), so the number can't sign up again.

**Why the deletion** (the advisor's answer 42): a user exists from the moment they sign in by OTP,
before the dob step, so when the date is refused the row already holds a minor's encrypted phone
number. T-3.6's first text kept it indefinitely, with status `banned`: more than `/privacy`
promises ("we refuse the sign-up and keep a hashed copy of the phone number"), and exactly the
data Velora shouldn't hold.

**Why the hash stays** (the founder, 3 October 2026): answer 42 dropped the hash too, on the
premise that a soft age gate had been chosen. No record says so. D-009 is a "Hard 18+ gate"; D-051
and D-061 rely on the hash; `/terms` promises to "bar that phone number from signing up again",
and `/privacy` to keep a hashed copy.

**An exception to 03-SCHEMA's "we don't hard-delete users":** at the dob step a user has nothing
moderation may need (no messages, reports, ledger or payments, rule 12), so nothing is lost.

**Test (🔒 7):** after `UNDERAGE` there is no user row, no session, no profile, wallet or
preferences row, and exactly one `banned_identities` row for the number. `/privacy` adds that
everything else is deleted at once (T-3.6).

**It makes D-032's "underage-banned" exclusion unreachable.** D-032 (Locked) excludes
underage-banned users from discovery, but under this decision no such user ever exists: the
account is deleted and only the hash is kept. The set is always empty and the clause never
matches. D-032 isn't edited for a no-op; this note is the reason the clause matches nothing.

**Rejected:** keeping the row with status `banned` (T-3.6's first text); dropping the hash too, a
soft gate, which would supersede D-009 and the published pages.

**If the premise fails (found building T-3.6):** the deletion clears exactly the six tables a user
can have rows in at the dob step, and every other foreign key into `users` is RESTRICT. So if an
under-18 account ever holds a row anywhere else, the deletion fails whole, a 500 with nothing
deleted and no hash kept, rather than taking a moderation or money record with it. A test holds
every key into `users` to that split; P-54 is the first route that could make it happen.

The deletion is the advisor's answer 42, approved by the founder; keeping the hash is the founder's
own decision, both on 3 October 2026. Locked at T-3.6's `/done`, 3 October 2026.

### D-073 · On Path B a banned number's codes stop arriving, with no message — Open
**The fact, built in T-3.2 and T-3.3:** a number whose hash is in `banned_identities` (D-009's
under-18 refusal, D-072, and whatever bans T-9.5 writes) gets exactly the answer any other number
gets from `/v1/auth/otp/send`, and nothing is sent (D-066). A code is stored for it all the same,
never sent, so a wrong guess at verify is answered as anyone's is.

**What follows (the advisor's reading, checked against the code):** the banned person never holds a valid code, so T-3.3's
`ACCOUNT_BANNED` for a banned number never fires in the normal flow; only a guess of the six-digit
code reaches it, at one in a million a try and ten tries a day. D-066's "a ban surfaces only at
verify, once the person has proven they hold the number" therefore never happens on Path B: they
can't prove it. D-066 is Locked and isn't edited for that; this entry is the record of it, as
D-072's note is for D-032's unreachable exclusion.

**What a banned person experiences on Path B:** codes simply stop arriving. No message, no error,
nothing that names the ban or points to grievance@.

**Not on Path A, the launch path:** Firebase sends its SMS from the browser whatever our list says
(T-3.14), so the person holds a valid token, and the exchange, which reuses T-3.3's sign-in
service, answers `ACCOUNT_BANNED`. A user whose account is banned by status, with no
`banned_identities` row, gets codes on both paths and `ACCOUNT_BANNED` at sign-in.

**Not decided here:** whether Path B's silence is acceptable, and what a banned person should be
told. That is P-51's, for T-9.5 or T-9.6, not T-3.x's.

The behaviour is Claude's, built in T-3.2; the advisor directing T-3.2 to T-3.10 (Claude, in a
separate chat) named its consequence and asked for this record, 3 October 2026. **Open** until
P-51 decides.

### D-074 · HSTS covers every subdomain, and is never preloaded before launch — Locked
Settles what D-059 left to T-2.6. The web sends `Strict-Transport-Security: max-age=63072000;
includeSubDomains`, set in `web/src/lib/security-headers.ts` rather than left to Vercel's default,
which was the same two years without the subdomains: a platform default nobody chose.

**Why `includeSubDomains`:** production's readable CSRF cookie is scoped to the whole of
`veloraapp.co.in` (D-055). A plain-HTTP response from any subdomain could set or overwrite a cookie
for the parent domain; once a browser has seen the header, it never makes a plain-HTTP request to
any subdomain, so that path is closed. Every subdomain serves HTTPS today (`staging.`, `api.`,
`api.staging.`, `www.`).

**What it costs:** every future subdomain must serve HTTPS, for two years after a browser last saw
the header. The one foreseeable exception is a bulk-mail service's click-tracking subdomain, so
T-9.15 carries a line: certificate first.

**Why never preload before launch:** preloading submits the domain to a list browsers hardcode.
Removal takes months and reaches people only through browser updates, so it is effectively
irreversible, and it forces HTTPS on every subdomain for every user from their very first visit.
It is never done before launch; doing it after launch is a decision of its own, with its own record.

**Rejected:** leaving HSTS to Vercel, where the header would change whenever Vercel's default did;
two years without `includeSubDomains`, which leaves the cookie path open; preload now. Decided by
the founder on 3 October 2026 (T-2.6).

### D-075 · Production releases from a tag, and only what staging proved — Locked
Production deploys only from `.github/workflows/deploy-production.yml`, when a tag `v*` is pushed
on a commit of `main`. Its gate, `scripts/release-gate`, is the `/done` gate (D-044) extended to
the live site, and refuses unless:
- the commit is on `main`;
- CI passed for that exact commit;
- staging deployed that exact commit, with its smoke check passing. Production only gets what
  staging proved.

**Staging's deploys are matched by name, not by the commit GitHub records.** A `workflow_run`'s
own head SHA is `main`'s newest commit when the run started, not always the commit it deployed,
and with several sessions pushing to `main` the two can differ. `deploy.yml` names each run
`Deploy staging <commit>`, and the gate matches that. On 3 October 2026 the twelve newest staging
deploys all matched: that shows the race hadn't happened yet, not that it can't.

**Only `v*` tags may deploy to the `production` environment,** so no branch's workflow can read
its secrets.

**The production Vercel token expires after a year.** The gate reads its expiry from Vercel on every
release, refuses a token Vercel won't accept, and warns on the run's page when it expires within 30
days: a date in a runbook is a date nobody reads (the founder). When it lapses, releases stop and
the site keeps serving.

**Every build says which environment it's for.** `next build` refuses an `APP_ENV` outside local,
ci, staging and production, and the smoke check compares the home page's canonical address with
the site it checks. An allowlist can catch an invalid value but never a valid, wrong one, such as
staging's value on the production project. D-053's amendment says why this became necessary.

**Rejected:** deploying production on every merge, as staging does; deploying it from a laptop,
which would skip the gate and put the owner's credentials outside CI (D-046); and trusting
GitHub's recorded commit for a staging run. Decided by the founder on 3 October 2026 (T-2.6).

**Amended 3 October 2026: the gate refuses until both paid plans are in place** (the founder).
P-0.15 and P-0.16 stop being notes someone must remember and become checks standing where the
release happens:
- **Vercel:** the team's plan, from `GET /v2/teams/{id}` with the production token, must be Pro
  or Enterprise. Hobby is non-commercial only, and a public dating app is commercial.
- **Supabase:** the gate reads the production project (`GET /v1/projects/{ref}`), takes its
  organisation from that answer, and requires that organisation's plan to be Pro, Team or
  Enterprise. Free keeps no backups, and the first real sign-up is the first thing worth losing.
  Read through the project, so the check can't be pointed at some other organisation.
- **Both are allowlists:** a plan the gate doesn't know, or an answer without one, is refused.
  Supabase's schema doesn't require the `plan` field, so its absence must fail closed.
- **The Supabase token is scoped:** read-only, to the production project and its organisation.
  Never a classic token, which carries the account's full power over every project, in a CI
  secret, for a read the gate needs once per release.

P-0.14, the registered office, is a judgement, not something an API can answer, so it stays a
Needs line on the release (REL-1).

**What the gate guards against:** mistakes, such as a tag on the wrong commit, an unpaid plan or
an expired token. A `v*` tag runs the workflow and the scripts at its own commit, so anyone who
can push tags could change them. Only the founder and his sessions can.

### D-076 · Velas stay a closed-system prepaid instrument — Locked
**The position.** In RBI's terms, Velas are a closed-system prepaid payment instrument (PPI), which
RBI neither regulates nor supervises. That holds only while four things stay true. Velas buy only
Velora's own services. They can't be turned into money. They can't move between accounts. And no
woman ever holds any. This entry is what keeps those true.

**The text.** RBI's Master Directions on PPIs, 2021, as updated to 30 September 2026
(`rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12156`, read 3 October 2026), ¶2.1: "Closed
System PPIs : These PPIs are issued by an entity for facilitating the purchase of goods and
services from that entity only and do not permit cash withdrawal. These instruments cannot be used
for payment or settlement for third party services. The issuance or operation of such instruments
is not classified as a payment system requiring approval / authorisation by RBI and are, therefore,
not regulated or supervised by RBI." ¶2.8 makes funds transfer a feature only Full-KYC PPIs carry.
On Small PPIs: "Funds transfer or cash withdrawal from such PPIs shall not be permitted." On
Full-KYC PPIs: "These PPIs shall be used for purchase of goods and services, funds transfer or cash
withdrawal." The Payment and Settlement Systems Act, 2007, s.2(1)(i), as RBI's own PSS FAQ (Q9,
`rbi.org.in/Scripts/FAQView.aspx?Id=73`) quotes it, defines a payment system as "a system that
enables payment to be effected between a payer and a beneficiary, involving clearing, payment or
settlement service or all of them". Q10: under section 4, "no person other than the Reserve Bank
can operate or commence a payment system unless authorized by the Reserve Bank". The Act's own text
wasn't fetched (India Code timed out), so it is quoted through RBI's FAQ.

**Why a transfer breaks the exemption for Velora, and why the general rule doesn't.** ¶2.1 says
nothing about transfers between users. On its words, a shop's gift card handed to a friend who
spends it in the same shop is still closed-system: the friend still buys only from the issuer. So
"a transfer between users breaks the exemption" is not a general rule, and this entry doesn't claim
it. Velora differs for one reason: **a woman can buy nothing with Velas.** Every price is 0 for her
(D-002, D-004), so a Vela in her hands buys nothing from Velora. Its only use there would be
payment between people. That is "payment or settlement for third party services" (¶2.1), payment
"between a payer and a beneficiary" (s.2(1)(i)), and "funds transfer" (¶2.8). **So D-002 is
load-bearing for the exemption.** Women paying nothing is exactly what makes any Vela that reaches
a woman a payment between people. "Fixing" D-002 generously, by letting a man send a woman Velas,
rewarding women in Velas, or paying women out for gifts they receive, takes Velora outside ¶2.1
and into operating a payment system without RBI's authorisation (s.4). D-002's rejected
alternative, payouts to women, now carries that weight too.

**The rules.**
1. **A woman has no ledger rows at all.** She is never credited, and never debited, because every
   price is 0 for her. **The database enforces it** (T-5.1): it refuses any `ledger_entries` row,
   and any `wallets.balance` other than 0, for a user whose gender isn't `male`. That is an
   allowlist. A user with no gender yet can't be credited and then choose female: T-1.9's
   immutability trigger stops a gender changing once set, not a first choice made after a credit.
   **Why the database and not the service:** this is the one invariant in the system with legal
   consequence. Any other rule here that breaks is a bug. This one breaking is Velora operating an
   unauthorised payment system. A service check holds only while every writer goes through the
   service. A migration, a repair script, an admin tool or a future task writing the ledger
   directly would bypass it, and nothing would go red. The service may refuse first, for a clear
   error, but the database is the guarantee, and the thing tested by breaking it. Consequences:
   T-8.1 refuses a woman's order; T-8.6 decides what a woman gets for a referral, and it is never
   Velas; T-9.5's grants can't reach her.
2. **Every ledger reason has one direction** (D-077). `gift` is a debit. A gift is a service the
   man buys from Velora, and nothing ever credits its recipient.
3. **Money goes back to a payment method only for a payment with no Velas still standing against
   it:** either none were granted (D-050's duplicate charge, which T-8.2 never credits), or the
   same step reverses them in the ledger. A balance is never refunded, spent or unspent. T-8.2
   handles Razorpay's refund and dispute events, T-8.3's repairs follow this rule, and so does
   T-9.15's live test. If a gateway asks for a refund policy (P-0.8), the answer is this rule,
   never "refund unspent Velas".
4. **The prototype's wallet screen offers the cash-out D-050 removed:** "Request a refund on unspent
   credits" and "Unspent credits refundable within 7 days." Neither is ever built (T-5.5,
   08-DESIGN).
5. **Never add any of these without reopening this entry:** a transfer between accounts; a gift
   that credits its recipient; a payout to anyone; a refund of a balance; Velas accepted for
   anything but Velora's own services.

**Expiry is not an RBI question.** ¶13 (one-year minimum validity, warnings in the 45 days before
expiry, and ¶13.3's three-year bar on moving expired balances to profit and loss) governs PPIs under
the Directions, and ¶2.1 puts closed systems outside them. Velas never expire anyway (D-050). **The
obligation is ours:** paid Velas that never expire and are never refunded are an open-ended promise
of service. That matters if Velora shuts down or is sold (P-0.7), and in the accounts: when GST is
due on a prepaid balance, and how unspent paid Velas are carried (P-0.17, a chartered accountant).

**What this reading is.** Claude's reading of the primary texts on 3 October 2026, at the direction
of the advisor directing Sprint 5 (Claude, in a separate chat). It is not legal advice, and no
lawyer has read it (P-0.7 has none booked).

**Rejected:**
- **"Inter-user transfers break the exemption" as a flat rule:** the advisor's first framing, which
  ¶2.1's text doesn't support (above). The narrower argument is the one that holds, and the one to
  keep.
- **A service-level check for rule 1:** Claude's first recommendation, overruled by the advisor. The
  ledger's reason directions, which carry no legal weight, were already enforced in both the
  service and the database (D-077). The highest-stakes rule can't have weaker enforcement than a
  lower-stakes one.
- **Letting women hold promotional Velas** (referrals, grants): harmless alone, but the precondition
  for a transfer, and a woman who bought them would pay for nothing she could use, with no refund
  under D-050.

Approved by the founder on 3 October 2026.

### D-077 · A ledger entry happens once — Locked
**How a double credit is made impossible, not just unlikely:** six layers. Each is proved by
breaking it and watching a test go red (T-5.1; T-5.4 and T-8.2 at scale).
1. **One row per key.** `ledger_entries.idempotency_key` is UNIQUE (T-1.12).
2. **One key per event.** The wallet module builds every key as `{user_id}:{reason}:{event}`. The
   event is the id of whatever justifies the entry: for a purchase, the `payments` row; for an album
   refund, the request; for a ban refund, the original debit. A key never comes from a random value,
   the clock or a raw client header. A client's `Idempotency-Key` only ever fills the event part.
   So webhook retries, concurrent deliveries and T-8.3's manual repair all compute the same key.
   (This settles P-19.)
3. **One row per event, even if a key is built wrong.** A partial unique index on
   `(user_id, reason, ref_type, ref_id)` covers every reason except `admin_grant` and
   `thread_reopen`, which legitimately repeat. Every reason except `admin_grant` requires a ref.
   **Each reason has exactly one `ref_type`, pinned in the database too**, because the index is
   only as good as `ref_type` being right, and a code-only rule holds just until the next writer.
   So a credit naming a payment can only be `purchase` or `purchase_bonus`, and T-8.3's repair
   uses the webhook's own reason and key.
4. **Repeats are read correctly.** The wallet row lock makes one user's money operations take
   turns. Under READ COMMITTED (Postgres's default, kept), the repeat check runs after the lock is
   granted, so it sees the first call's committed row and returns it. The same key with different
   details raises: returning the earlier entry silently would hide the bug that reused the key. The
   service never catches a unique violation and carries on: the transaction aborts, balance update
   included. `debit()` and `credit()` return the entry and whether it was newly applied.
5. **The payment side is anchored too.** `payments.provider_payment_id` is unique, and a paid
   payment must have one (T-1.12). The webhook marks the payment paid and credits it in one
   transaction.
6. **Each layer is proved,** by forced overlap and breaking runs. T-5.1 breaks each layer once,
   with a two-connection race test for layer 4. T-5.4 then shows 50 same-key calls give one row,
   and T-8.2 that five concurrent deliveries give one credit.

**Around it:**
- **Each reason has one direction,** checked in the service and by a database CHECK. `gift` is a
  debit.
- **The bare `refund` reason is refused, in the service only,** until a task gives it a meaning.
  Nothing writes it, and its name reads as money. **Why the service is enough here, when D-076's
  gender rule is in the database:** the gender rule's failure is a regulatory position, while
  `refund`'s worst case is a confusingly named credit, which the direction CHECK already keeps a
  credit. The level follows the stakes, as in the next paragraph.
- **Transactions:** both functions run only inside the caller's transaction and refuse otherwise. A
  transaction locks one wallet, or several in `user_id` order. Nothing external runs while a wallet
  is locked.
- **No status check:** the wallet never checks user status. A frozen man's captured payment must
  still be credited.

**Detected, not prevented: a balance written outside the service.** The app role can update
`wallets`, as it must, and T-9.9's reconciliation (`balance == sum(delta)`) catches a balance that
disagrees with its ledger. That is weaker than D-076's rule 1 **on purpose**. An inconsistent
balance is a bug we can repair, from the ledger, which is append-only and complete. A woman holding
Velas is a regulatory position we can never un-break. Preventing the first would take a trigger
checking each balance against the ledger at commit, plus a sequence column, because two entries from
one transaction share `created_at`. That isn't worth building for a repairable bug.

**Rejected:**
- The caller's raw key: P-19's collision between users.
- The key alone, with no per-event index: two code paths can spell one event two ways.
- Returning an earlier entry for a reused key with different details.
- A deferred balance trigger (above).

Directed by the advisor directing Sprint 5 (Claude, in a separate chat). Approved by the founder on
3 October 2026.

### D-078 · An under-18 refusal deletes everything the app may delete, files included — Locked
**Supersedes** D-072's paragraph "If the premise fails": that the deletion clears six tables, and
that a row anywhere else stops it whole. The rest of D-072 stands: the user and everything attached
are deleted in the transaction that refuses the date, and only the number's hash is kept.

**The decision (P-54):**
- An under-18 refusal deletes the user's rows in every table the app role may delete from, under
  every column that names the user. It keeps only what rule 12 keeps and the app role can't delete
  (T-1.22): `messages`, `reports`, `ledger_entries`, `payments` and `audit_log`. A user at the dob
  step can't have a row there; if one ever does, the deletion fails whole, a 500, and the bug is in
  whatever wrote the row.
- **Files go too, in this order.** In the transaction that deletes the rows, and before it deletes
  them, read the storage key of every file behind them: photos, selfies, and any file a later table
  stores behind a user row. Then delete the rows, commit, and enqueue the files' deletion with the
  keys read. The order is the decision: deleting the rows first and then looking up what to delete
  from storage loses the keys it needs. The job retries, and if it still fails it raises where
  someone sees it (T-9.12's alerts), never only a log line, since a file left behind is a minor's
  selfie in a bucket. The enqueue comes after the commit, so a refusal that rolls back deletes no
  file a kept row still points to; the moment between commit and enqueue is the implementing
  task's to close (a row written in the same transaction, which the job reads, is the usual way).
- A table added with a key to `users` fails CI, naming D-072, until it is listed as deleted or kept
  (T-3.6's test, which P-54 extends), so the deletion can't fall behind the schema.
- **Not either/or forever.** If a kept table ever genuinely needs a refusal before dob, that is a
  narrow guard on that one table, with its own reason, never a global rule.

**Why:** it is what D-072 already promises, "the user and everything attached"; refusing every
write before dob would be a different promise put in its place. CI keeps the list current without
more machinery, and it costs nothing until a minor signs up.

**Rejected:** (b), a database guard refusing a row in a kept table for any user whose dob is null.
It is D-068's step rule a second time, in the database, and a rule kept in two places drifts: a row
written before dob is a D-068 bug, fixed in the step rule. It needs an exception for staff, whose dob
can be null (the seed's moderator), and a guard that exempts a class of users is one widening from
not being a guard (the advisor: the week's other guards, the gender trigger and D-076's closed
system, hold because they have no exception). And it costs a lookup on every insert into busy
tables, paid by every user forever, against a state that arises only when other code is already
broken. Also rejected: deleting rule 12's tables too, which rule 12 forbids and the app role can't
do.

**How it lands:** P-54's row half, every table the app role may delete from, before T-4.2. The file
half in T-4.2, the first task to store a file behind a user row, whose keys it defines; T-4.5 adds
its selfies. Both inherit the rule: any file they store behind a user row joins the list.

The options were Claude's (P-54). (a) was chosen, with the condition on files, by the advisor
directing T-3.2 to T-3.10 (Claude, in a separate chat), relayed by the founder, 3 October 2026.
Locked at P-54's `/done`, 3 October 2026, with the row half built; the file half is T-4.2's.

### D-079 · The browser never judges the date of birth — Open
**The decision (T-3.11):** the birthday screen sends the date as typed, and the server alone works
out the age, in IST (rule 6, D-009). The browser has no under-18 check and computes no age ("you'll
appear as 25"). Before the date is sent, a confirm step shows it in words and says it can't be
changed. After `UNDERAGE` comes a final screen, and the session is cleared: D-072 has deleted the
account.

**Why no check in the browser:** it would make D-009's hard gate soft. A minor shown "you must be
18" changes the year, the server never sees the attempt, and the number is never barred. The usual
instinct, validate early, is wrong here: the refusal has to happen where it is recorded.

**Why the confirm step:** once sent, the date can't change (`IMMUTABLE_FIELD`, T-1.9's trigger), and
a date under 18 deletes the account and bars the number for good (D-072). A slipped year has to be
caught by the person before that, because nothing can undo it after.

**The prototype differs** (08-DESIGN lists it): it checks the age in the browser, and says "This
device can't be registered" when it is the number that is barred (`/terms`).

**Rejected:** the prototype's check in the browser; sending without a confirm step.

Recommended by Claude in the joint plan for T-3.10 to T-3.13; answered by the advisor directing
that plan (Claude, in a separate chat), relayed by the founder, 3 October 2026.
**Open** until T-3.11 builds it; its `/done` marks it Locked on the founder's word.

### D-080 · Onboarding URLs are stable slugs, and a phone number never goes in a URL — Open
**The decision (T-3.10, T-3.11):**
- Each `onboarding_t` step has a URL under `/onboarding/`, from one typed map in the web that stops
  compiling when the enum gains a value, with a test that the slugs are unique: `birthday`,
  `gender`, `looking-for`, `name`, `username`, `about`, `photos`, `interests`, `pin`, `selfie`.
  Renaming a step changes a key in the map, never a URL. T-4.10's location question, which has no
  step of its own, takes a slug in the same map.
- Phone and code are one page, `/login`, in two stages. The code screen needs the number, and a
  phone number never goes in a URL, where browser history and every log along the way keep it
  (rule 15).
- A URL for a step after the user's redirects to theirs; theirs or an earlier one loads, as an edit
  (D-068). There is no back arrow on the birthday, gender and looking-for screens: behind each is
  sign-in or an answer that can't change. Birthday or gender opened by URL after it's answered shows
  the answer read-only (the age only: `Me` carries no date of birth).

**Why slugs:** the enum is the database's name for a step, and a rename there shouldn't break a link
or show an internal name. **Why no back arrow there:** the prototype puts one on every screen,
including onto answers the server will refuse to change.

**Rejected:** the enum in the URL, as T-3.10's first text had it; the code screen at its own URL.

Recommended by Claude in the joint plan for T-3.10 to T-3.13; answered by the advisor directing
that plan (Claude, in a separate chat), relayed by the founder, 3 October 2026.
**Open** until T-3.11 builds it; its `/done` marks it Locked on the founder's word.

### D-081 · The web signs in by the path `APP_ENV` names — Open
**The decision (T-3.11):** builds where `APP_ENV` is `local` or `ci` sign in by Path B
(`/v1/auth/otp/*`, the fake provider locally); `staging` and `production` sign in by Firebase. It is
an allowlist (rule 16), like T-3.10's cookie suffixes, with no new Vercel variable, and the web
never reads `AUTH_PHONE_PROVIDER` (02-ARCHITECTURE §11 is corrected in T-3.11). Until T-3.14, a
Firebase build's `/login` says sign-in isn't open yet and links to the waitlist.

**Why:** staging and production run Firebase, where Path B answers 404 (D-066), and the landing
page's "Get started" goes to `/login`. Production's first release doesn't wait on T-3.14, so without
this it could show the public a sign-in form that can't work.

**The consent line naming Google moves to T-3.14.** It says Google's Firebase sends the code, and on
Path B nothing of Google's does: on T-3.11's screens it would be false.

**Rejected:** a `NEXT_PUBLIC_` variable the build refuses without (one more value on two projects,
when `APP_ENV` already says which environment it is); leaving `/login` broken until T-3.14.

Recommended by Claude in the joint plan for T-3.10 to T-3.13; answered by the advisor directing
that plan (Claude, in a separate chat), relayed by the founder, 3 October 2026.
**Open** until T-3.11 builds it; its `/done` marks it Locked on the founder's word.

### D-082 · Business rules are checked on the server only — Open
**The decision (T-3.11, T-3.12, and every form after):** the browser checks only what the API's
schema states: lengths, the username's format, a 6-digit code, a 4-digit PIN. Every rule beyond the
schema is the server's alone and comes back inline from `ApiError`: no links or phone numbers in
about (T-3.7), reserved usernames (D-068), weak PINs (D-069). For the PIN that means set, confirm,
send; a refusal returns to "set" with the server's reason.

**Why:** one copy of each rule. Two copies drift, and a validation bug then lives for a year in
whichever copy nobody tests.

**Rejected:** copying the rules into the browser for instant feedback.

Recommended by Claude in the joint plan for T-3.10 to T-3.13; answered by the advisor directing
that plan (Claude, in a separate chat), relayed by the founder, 3 October 2026.
**Open** until T-3.11 builds it; its `/done` marks it Locked on the founder's word.

### D-083 · Web forms: React Hook Form and zod — Open
T-3.11 added the web app's form tooling, the first forms to need it. Versions are pinned exactly.
- **react-hook-form** 7.89.0, **zod** 4.6.5 and **@hookform/resolvers** 5.9.1, all runtime
  `dependencies`: CLAUDE.md's stack pins the first two, and the resolvers join them (its peer ranges
  take react-hook-form ^7.55 and zod ^4). React Hook Form's 8.0 is a beta; the latest 7 was taken.
- **What zod checks, and what it never does (D-082):** only what the API's schema states, lengths,
  the username's format, ten digits for a number, six for a code. Every business rule stays on the
  server and comes back inline.
- **Not on the landing page.** T-2.3's waitlist form keeps plain React state, so neither library
  ships with the page whose performance score is measured (98–100, T-2.1).

**Rejected:** plain React state for every onboarding form, which would leave each screen to rebuild
validation, dirty tracking and submit state by hand.

Approved in the joint plan for T-3.10 to T-3.13 (decision 1), answered by the advisor directing it
(Claude, in a separate chat), relayed by the founder, 3 October 2026. **Open** until the founder
approves it in his own words, with D-079 to D-082.

---

## Adding a decision

Append `D-0NN · Title — Locked|Open`, with Decision, Why, Rejected. Never edit a Locked entry —
supersede it with a new one that references the old ID.
