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
"Tie the knot" converts it to a **Velora**: permanent, free messaging for both, forever.
An expired thread is archived read-only, never deleted, and can be re-opened for 3 credits.
**Rule:** permanence is granted by the other person, never bought.

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

### D-013 · Launch city — Open (default: Bengaluru)
One city only for beta and launch. Discovery radius default 25 km.

### D-014 · Theme — Locked (black · white · red blend)
The app has one theme, the blend: black chrome (header, bottom nav, hero, sheets), soft-white
content, red accent. Its tokens are in `08-DESIGN.md` §1 and match the prototype
(`docs/prototype/`) value for value. Colours live only in `web/src/styles/tokens.css`.

**Why now:** locked by the founder before T-1.17 creates `tokens.css` — T-1.19's primitives,
Sprint 2's landing page and everything after inherit whatever goes in there.

**Rejected:** the other two prototypes, dark and soft light. Their tokens remain in git history
(08-DESIGN before this lock); a dark mode, if ever wanted, would be a new decision.

### D-015 · Name "Velora" — Open
Trademark search pending ("The Velora" is an established wedding brand). Keep the name in one
constant (`APP_NAME`) in both apps so a rename is trivial.

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

---

## Adding a decision

Append `D-0NN · Title — Locked|Open`, with Decision, Why, Rejected. Never edit a Locked entry —
supersede it with a new one that references the old ID.
