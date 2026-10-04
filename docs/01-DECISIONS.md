# 01 · Decisions

Every decision that shapes the code. **Locked** means do not re-open it in a coding session —
if it seems wrong, raise it with the founder, don't change it. **Open** means a default is in
place so work can continue; the founder will confirm.

Format: Decision · Why · Rejected alternatives. The number comes from the session's own block,
given in its brief, from D-200 up (CLAUDE.md, "P- and D-numbers: a block per session"); never from
scanning branches.

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
**Superseded in part, 4 October 2026, by D-097:** a Thread lasts 1 hour, restarted by her message,
and re-opening costs 2 Velas (D-098). An expired Thread stays archived read-only, as above, for
both: he can't send until he re-opens it. The Knot, and the rule above, stand. The code still runs
24 hours until D-097's own task.

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
**Superseded in part, 4 October 2026, by D-098:** re-opening is 2, and Extend (10), private messages
(8, then 2) and viewing private pictures (1) are added. Whether the rows D-098 doesn't name stay is
open, on T-5.2's Needs line.
**Superseded in part, 4 October 2026, by D-231:** the direct message above is the private message,
now 8 and then 2; the album request is viewing private pictures, now 1, and a decline returns
nothing (D-230). The voice-note unlock, Super Like and "liked you" reveal stay, by default.

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
**Superseded, 4 October 2026, by D-099:** four new packs, ₹1,500 to ₹10,000 for 30 to 450 Velas, and
the number to watch is now ₹250 and ₹111. The first-purchase bonus and T-10.4's variant are open,
on T-5.2's Needs line.
**Noted 4 October 2026, D-231:** the first-purchase bonus above stays, on D-099's packs. T-10.4's
variant is still open. **Superseded 4 October 2026 by D-250:** the entry variant, `entry-25`, is
retired.

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
**Superseded in part, 4 October 2026, by D-098:** a paid gift costs 5, 10, 15 or 20 Velas, and 15
gifts a week are free, in place of the prices above and `gift_free_daily_limit = 3`. The
catalogue's shape is open, on T-5.2's Needs line.
**Superseded in part, 4 October 2026, by D-231:** four gifts at 5, 10, 15 and 20 replace the six,
with no free kind, and fifteen free sends a week replace the daily cap. The rest stands.

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

**Amended 4 October 2026 (the founder): there is no daily SMS cap to set.** The second
mitigation above, "Firebase console quotas set to a sane daily SMS cap", assumed a console field,
and so did the founder's first ordering of P-0.18 ("my assumption", the founder). The bullet
stands as written, struck by this amendment. Google documents none an owner can set (read by
Claude on 3 October 2026): Firebase's limits page gives plain Firebase Authentication a fixed
3,000 verification SMS a day and 900 a minute per project, and Identity Platform's quotas page
lists "No SMS/day limit" for a project with a billing instrument. `velora-ic` is on plain Firebase
Authentication (the console offers SMS multi-factor authentication behind "Upgrade to enable",
and the founder didn't take it; P-0.18), so its 3,000 a day is a ceiling inherited, not one we
configured, and it goes if the project is ever upgraded. What bounds an SMS flood on this path is
App Check (P-68, proved by its effect), the India-only region policy and Firebase's own fixed
limits. This decision's own trade-off still holds: our server's limits don't apply, since the SMS
is triggered from the browser. The billing alert stays, as an alert: budgets never cap.

**Amended 4 October 2026 (T-3.14): the dependencies.** The web's `firebase`, 12.19.0, pinned
exactly, its two install scripts denied in `web/pnpm-workspace.yaml` (neither does anything we
use). The API's `firebase-admin`, approved in T-3.14's plan, was not added, approved by the
advisor directing T-3.14 (Claude, in a separate chat), relayed by the founder: D-085 says why, and
how tokens are checked instead.

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
**Superseded in part, 4 October 2026, by D-230:** neither automatic return above stands; there is
no product refund of any kind (and D-100: an unanswered message's Velas aren't returned). The
fixes for a broken payment stand. `/refunds` is wrong until P-130 rewrites it.

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

**Amended 3 October 2026 (the founder, before T-3.14): staging shares `velora-ic`, so the way
out is the founder's own phone.** In the founder's words: "staging and production share
velora-ic, and no Firebase test number ever goes in it. Not one, not temporarily. A test number is
a fixed phone plus a fixed code that signs you in without an SMS. In a project that serves
production, that is a permanent sign-in bypass for anyone who learns the pair — the same shape as
/v1/test/sms/last-code, which we spent this evening proving was correctly gated. We are not going
to build that hole by hand in the console right after closing it in code." T-3.14's staging check
signs in with the founder's own phone. A Firebase project for staging alone, with its own test
numbers, is P-66, due when a staging check that signs in first has to run unattended, "because a
check that needs a human holding a phone is a check that stops being run" (the founder). Sharing
the project puts staging's sign-ins in production's user pool: "acceptable while there are no
real users, and it is not acceptable after launch" (the founder). So P-66 is on the Needs line of
T-9.15, Go live (Claude's placement), and of REL-1 if REL-1's tag includes T-3.14, the condition
written beside it: REL-1 is what makes real users possible (the founder, agreeing, the same day).
Its first use, the Playwright run moved out of T-3.14, is P-67, whose Needs line carries it.

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
**Noted 4 October 2026:** D-098 adds that a paid tier for women, considered and deferred, can't be
sold in Velas without reopening this entry. Rule 3's reversal stands unchanged (D-100).

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

### D-079 · The browser never judges the date of birth — Locked
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
Approved by the founder in his own words, 3 October 2026: "approved as built and tested in T-3.10
and T-3.11." **Locked** 3 October 2026.

### D-080 · Onboarding URLs are stable slugs, and a phone number never goes in a URL — Locked
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
Approved by the founder in his own words, 3 October 2026: "approved as built and tested in T-3.10
and T-3.11." **Locked** 3 October 2026.

### D-081 · The web signs in by the path `APP_ENV` names — Locked
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
Approved by the founder in his own words, 3 October 2026: "approved as built and tested in T-3.10
and T-3.11." **Locked** 3 October 2026.

### D-082 · Business rules are checked on the server only — Locked
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
Approved by the founder in his own words, 3 October 2026: "approved as built and tested in T-3.10
and T-3.11." **Locked** 3 October 2026.

### D-083 · Web forms: React Hook Form and zod — Locked
T-3.11 added the web app's form tooling, the first forms to need it. Versions are pinned exactly.
- **react-hook-form** 7.89.0, **zod** 4.6.5 and **@hookform/resolvers** 5.9.1, all runtime
  `dependencies`: CLAUDE.md's stack pins the first two, and the resolvers join them (its peer ranges
  take react-hook-form ^7.55 and zod ^4). React Hook Form's 8.0 is a beta; the latest 7 was taken.
- **What zod checks, and what it never does (D-082):** only what the API's schema states, lengths,
  the username's format, ten digits for a number, six for a code. Every business rule stays on the
  server and comes back inline.
- **Not on the landing page.** T-2.3's waitlist form keeps plain React state, so neither library
  ships with the page whose performance score is measured (98–100, T-2.1).
- **zod never compiles its parsers here** (added after T-3.11's Chrome check, before this entry was
  locked). zod 4 probes `new Function("")` to see whether it may, and production's CSP has no
  `'unsafe-eval'` (D-059): the probe is blocked and caught, but the browser still reports a
  `script-src eval` violation, which Chrome did against a production build. So `src/lib/zod.ts`
  sets `jitless` once and is the only place `"zod"` may be imported (ESLint refuses it anywhere
  else); the rerun had no violation. The cost is zod's interpreted parse, nothing a form notices.

**Rejected:** plain React state for every onboarding form, which would leave each screen to rebuild
validation, dirty tracking and submit state by hand.

Approved in the joint plan for T-3.10 to T-3.13 (decision 1), answered by the advisor directing it
(Claude, in a separate chat), relayed by the founder, 3 October 2026.
**Approved by the founder, 3 October 2026, without having read this text**, and recorded so: he
approved it on T-3.11's 31 broken guards, its agreement with D-082, and the cost of holding the batch
another round against a bounded risk, since a Locked decision is superseded, never edited. If
anything here surprises him on reading, he supersedes it. **Locked** 3 October 2026.

### D-084 · The E2E: Playwright, Chromium in CI, nothing kept — Locked
T-3.13 added the end-to-end tests 06-TESTING has named since Sprint 1. Pinned exactly.
- **@playwright/test** 1.63.0, a `devDependency`: CLAUDE.md's stack pins Playwright. Its browsers
  are downloads, not packages: Chromium in CI (`playwright install --with-deps chromium`), and
  Playwright's own Firefox build by hand (`E2E_FIREFOX=1`), never in CI.
- **A production build, not `next dev`,** so production's strict CSP is the one the journeys run
  under, and any violation fails them: `next dev`'s `'unsafe-eval'` hid T-3.11's CSP finding, zod's
  eval probe, until a production build ran.
- **The API on a P-55 slot of its own** (`api/tests/e2e_server.py`), so an E2E run and any pytest
  run never meet, and each starts empty.
- **Nothing is kept from a run (decision 22):** no traces, videos or screenshots, and CI uploads no
  artifact. A trace records request and response bodies, phone numbers, codes and access tokens
  among them; a page snapshot shows the phone screen. Failures speak through their assertions.
- **Codes come from a test-only endpoint** (04-API, local only) reading the fake SMS's outbox: what a
  phone would have received, so D-073's silent ban is testable.
- **That endpoint's gate is an allowlist, proved against a name nobody has listed** (the founder's
  question before approving this entry). Its code signs anyone in, so if it ever answered outside
  local, a phone number alone would be account takeover. `create_app()` mounts it only where `ENV`
  is in `{"local"}` and `SMS_PROVIDER` in `{"fake"}`, and Settings refuses any fake provider outside
  local anyway (D-045). Broken into a blacklist of today's names, "not staging or production", the
  cases written with today's names passed, and only `preview` and `env-nobody-has-named-2031`, a
  name listed nowhere else, went red; broken into "not production", staging went red too. Read
  from pytest's own result for each case (`tests/modules/e2e/test_last_code.py`):

  | The gate broken into | staging | production | preview | never named | msg91 |
  |---|---|---|---|---|---|
  | "not staging or production" (today's names) | passed | passed | **failed** | **failed** | passed |
  | "not production" | **failed** | passed | **failed** | **failed** | passed |

  **A blacklist can't be tested with the names you already know:** every case written with them
  passes. Only a name nobody has listed catches it. Keep that case in the test.

**Rejected:** running against `next dev` (its CSP allowances hide what production blocks); keeping
traces on failure (they would hold the very data rule 15 keeps out of logs); reading codes from the
fake's terminal echo (masked numbers, parsing, and codes in CI's log).

Approved in the joint plan for T-3.10 to T-3.13 (decisions 1, 19, 21 and 22), answered by the advisor
directing it (Claude, in a separate chat), relayed by the founder, 3 October 2026.
**Approved by the founder, 3 October 2026,** once the gate's table was in: the three layers, `ENV`,
`SMS_PROVIDER` and Settings refusing to start, are the depth an endpoint handing out sign-in codes
needs. **Locked** 3 October 2026.

### D-085 · Firebase sign-in: tokens checked with PyJWT, used once by their hash, served only for firebase — Open
**The decision (T-3.14):**
- **The API checks a Firebase ID token itself,** as Google's "verify ID tokens using a third-party
  JWT library" says (read 4 October 2026), with PyJWT (D-060). Google's keys are the X.509
  certificates at `securetoken@system.gserviceaccount.com`, fetched with httpx and kept for their
  `Cache-Control` max-age; a token naming a key we don't hold fetches again, at most once a
  minute. A token must be RS256, signed by the key Google lists under its `kid`; `aud` the
  project in `FIREBASE_PROJECT_ID` and nothing else, `iss` `https://securetoken.google.com/` and
  that project; `exp` in the future, `iat` and `auth_time` in the past, read from `core.clock`
  (rule 7) with 30 seconds for Google's clock running ahead, never for expiry; `sub` 1 to 128
  characters; a `phone_number`; `firebase.sign_in_provider` `phone`. Then T-3.3's `sign_in()`,
  India only (`PHONE_NOT_SUPPORTED`) and banned numbers included.
- **A sign-in older than 5 minutes is refused** (`auth_time`). Our web exchanges its token seconds
  after the code is confirmed, so it never comes near.
- **Used once, keyed on the token's SHA-256,** held in Redis until the token would expire anyway.
  Firebase ID tokens carry no `jti`: Google's list of their claims has none. A replayed token is
  refused before the phone's limit counts it, so replaying someone's token can't lock them out.
- **Every refusal is one answer,** `401 FIREBASE_TOKEN_INVALID`, so a forger learns nothing about
  which check failed; the logs get a reason, never the token, its claims or the number (rule 15).
  Google's keys unreachable is `503 PROVIDER_UNAVAILABLE`: not the token's fault.
- **Served only where `AUTH_PHONE_PROVIDER` is `firebase`,** an allowlist (rule 16), the shape of
  D-066: 404 elsewhere, a provider nobody has named included. `make types` reads
  `contract_openapi()`, which holds both paths, so the web is typed against both.
- **No service account,** and `FIREBASE_PROJECT_ID` is required where the provider is `firebase`,
  shape-checked at startup. Staging and production both name `velora-ic` (D-065) until P-66.
- **The web config is committed,** in `web/src/lib/firebase-config.ts`, by `APP_ENV`: staging and
  production only. Local and ci builds get none, so nothing built on a dev machine reaches
  Firebase and no seeded number (D-064) can be texted from one. Its API key carries gitleaks'
  allow marker, with the reason: Firebase's own page says such keys "are not used to control
  access to backend resources" and "are OK to include in code or checked-in config files".
- **The SDK only through `web/src/lib/firebase.ts`** (ESLint enforces it): loaded on demand, so only
  a Firebase build's `/login` downloads it; Firebase's user in memory only, never IndexedDB, and
  signed out once our API has answered, whatever it answered; no popup or redirect resolver, so
  Google's `apis.google.com` iframe never loads; invisible reCAPTCHA, rendered as the screen opens.
- **The CSP widens on Firebase builds only** (D-059): reCAPTCHA's own list (its FAQ) for
  `script-src`, `frame-src` and `connect-src`, and the SDK's two API hosts,
  `identitytoolkit.googleapis.com` and `securetoken.googleapis.com`. Path B builds keep the policy
  byte for byte. Firebase publishes no CSP for Auth.

**Why not `firebase-admin`,** the plan's approved dependency (Claude's case, from its 7.7.0 source;
approved by the advisor directing T-3.14, Claude in a separate chat, relayed by the founder on
4 October 2026): its check is synchronous and fetches Google's keys with
`requests`, against rule 7; it reads the wall clock, against D-060, so tests can't move expiry; its
auth client asks for a credential when it starts (`google.auth.default()`), which Fly doesn't have;
and it brings Firestore, Cloud Storage and gRPC. The advisor called the last the strongest:
"adding a library that demands the service account we just proved unnecessary would have
manufactured the secret we deleted tonight."

**Why the 5 minutes** (the advisor, relayed by the founder): "It closes a real hole — a leftover Firebase session should
not be able to mint a Velora session hours later — and our own flow can't trip it."

**Why the hash** (the advisor, relayed by the founder): "it identifies without storing the thing." It stays out of logs
like any other token material.

**Why a committed module, not variables** (the advisor, relayed by the founder): local and ci getting nothing "makes 'no
seeded number can reach Firebase from a dev machine' structural rather than a rule someone has to
remember". `.env.*` files are git-ignored in both `.gitignore`s, and D-081 already rejected one more
`NEXT_PUBLIC_` value on two Vercel projects when `APP_ENV` says which environment it is.

**Proved by breaking each guard** (4 October 2026, each file restored to its SHA-256): fourteen in
the API and seven in the web, every one red. Among them: a token spent every time it's used, the
audience's strictness, the five minutes, expiry, the issuer, the sign-in provider, the phone's
limit counted before the token is spent, the India check, the route served for `fake`, and a
blacklist ("served wherever Path B isn't"), which `fake` and `msg91` passed and only a provider
nobody has named failed (D-084's lesson); and on the web, the region refusal's copy, signing out
of Firebase only on success, Google's hosts on every build, and a config for `local`.

**Rejected:** `firebase-admin` (above); a `jti` check (there is none); serving the exchange for
every provider; `NEXT_PUBLIC_FIREBASE_*` variables in Vercel; the config in `.env.production`
(git-ignored, and every build, local and ci included, would carry it).

Recommended by Claude in T-3.14's plan; approved by the advisor directing T-3.14 (Claude, in a
separate chat), relayed by the founder on 4 October 2026: "PyJWT and httpx it is. Record D-085 as
Open; I'm approving it now in these words." That line is the advisor's (the founder, the same
day). **Open** until the founder locks it in his own words.

### D-086 · The local S3 is SeaweedFS, because MinIO is archived — Locked
**The decision (T-4.1):** local development and CI stand in for R2 with **SeaweedFS**
(`chrislusf/seaweedfs`, Apache-2.0) in `infra/docker-compose.yml`: its S3 gateway on
`127.0.0.1:9000`, path-style; credentials, and anonymous read on `velora-public` only (it mirrors
the CDN-served bucket, D-027), in `infra/s3/s3.json`; a one-shot `s3-init` that creates whichever
bucket is missing. It replaces MinIO. **Supersedes D-036's list of ports** (D-036 is Locked and
not edited): published now are Postgres 5432, Redis 6379 and S3 9000, each on `127.0.0.1`, as
D-036 requires; MinIO's 9001 went with it. **Settles P-02**, the registry and the pinning:
Docker Hub, by version `4.48` and by the digest of its multi-arch index, both in the compose file,
so a re-tag can't change what runs, and a digest that disappears fails loudly at `make infra-up`
and in CI, never silently.

**Why MinIO had to go: it is archived.** Its maintainers stopped publishing images to Docker Hub
and Quay on 23 October 2025 and archived the repository in February 2026 (read 4 October 2026).
That day quay.io answered "no such manifest" for every MinIO tag tried, `latest` included, and
Docker Hub refused, so T-4.1's first CI run (37195913766) couldn't start it. Any fresh
`make infra-up` failed with it, Postgres and Redis included, since one `up` starts all three;
the founder's Mac worked only from its image cache.

**Why not a rebuilt MinIO.** Chainguard's free MinIO images pull without a login and passed the
same checks as SeaweedFS below. The founder chose against them; **the reasoning is advice he
adopted, not words he wrote** (his correction, 4 October 2026): "it's about expectation, not
purity". They pin us to someone else's build of a dead project, and a server calling itself RELEASE.2026-09-22 when the repository was archived in
February 2026 means nobody here can say whose source it came from. They are free today and cost a
day on whatever morning the image goes, which can't be predicted; switching costs an hour or two
once, and the work was already stopped. The risk is contained: local and CI only, never
production or a user's photo.

**Why SeaweedFS and not Garage:** the one provable faster (the brief was "whichever of the two you
can prove faster"). SeaweedFS grants anonymous read on one bucket at its path-style URL, which is
how the tests and the local `PUBLIC_CDN_URL` stand in for the CDN; Garage serves public reads only
through a separate website endpoint chosen by hostname. **Proved before the switch** (4 October
2026, on spare ports, then in a throwaway compose project): T-4.1's storage probe passed every
step against it; an expired presigned PUT and an unsigned read of the private bucket were refused
(403); an anonymous read of the public bucket was served (200) and an anonymous write refused
(403); a missing object maps to `ObjectNotFound` for get, head and copy; and `s3-init` run a second
time creates nothing and exits 0.

**If it stops emulating S3 well enough for our tests,** that shows in a local run, never in
production: fall back to Chainguard's MinIO, pinned by digest, and tell the founder (the
instruction that came with the choice).

**What the switch cost (T-5.4, 4 October 2026):** an afternoon of CI. A fresh SeaweedFS claims
7 volumes per collection at its first write and was started with no `-volume.max`, so on CI the
collection written last could find none: every write to `velora-public` failed with
`InternalError` once the first storage write came about 25 s later than usual. It was latent on
`main` from the switch: T-5.4's 50-connection tests lengthened the critical pass by that much and
went red twice, and `main` plus a test that only sleeps 25 s went red on the same four tests. The
fix (P-77): `-volume.max=100`, and `s3-init` claiming both buckets' volumes at startup. It doesn't
change the decision: MinIO's images were gone, and there was no staying put.

**Rejected:** Chainguard's MinIO (above); our cached MinIO images copied to GitHub's registry
(frozen without MinIO's October 2025 security fix, and every fresh clone would need a GitHub login
to pull); building MinIO from source in CI (a dead project, rebuilt on every run).

The options were Claude's (T-4.1). **The choice is the founder's** (option (c), picked after the
options were laid out for him); **its reasoning is advice he accepted**, recorded as advice, not as
his words: "Don't attribute reasoning to me that I didn't write. The record is more useful accurate
than flattering" (the founder, 4 October 2026). Locked on his word the same day.

### D-087 · AWS is out of Velora entirely — Locked
**The decision, in the founder's words, 4 October 2026:** "AWS is out of Velora entirely. Not
Rekognition, not an IAM user, not a payment verification." He had said it on 3 October 2026 too,
and it was never written down, which is how it survived.

What it changes:
- No AWS account, IAM user or AWS service of ours, now or behind any provider. Selfie face matching
  runs on our own worker (D-088). P-0.6's AWS account is dropped, its failed payment verification
  abandoned, and T-4.5's Needs line no longer names AWS.
- `FACEMATCH_PROVIDER`'s real option is `sface`, not `rekognition`, and the `AWS_*` settings are
  gone from the API.
- `/privacy` no longer lists Amazon Web Services among those who handle data, and says the selfie
  is compared on our own servers.

**What it doesn't mean, so nobody reads it as more:** Supabase and Upstash run on Amazon's cloud in
Mumbai (Supabase's region is `ap-south-1`; P-49 measured both hosts as Amazon's). They are
processors we contract with, not AWS services of ours, and D-048 stands. The aioboto3 parameters
named `aws_access_key_id` and `aws_secret_access_key` in `core/providers/storage.py` carry R2's
keys: the S3 protocol's names, not an Amazon service.

**Superseded by it:** the plan's Rekognition face match for T-4.5, and the Rekognition
`DetectFaces` pose check that Sprint 4's plan proposed as its question D9 (a numbered question in a
plan, never recorded here, so there is no D- entry to supersede). D-048 is Locked and not edited:
it names AWS `ap-south-1` as a deferred home for the API, an option this decision closes, as it
closes P-49's AWS host.

Asked whether the pasted words were his, the founder confirmed it on 4 October 2026: "my own
words, twice, in my own language". **Locked** on his word.

### D-088 · Selfie face matching runs on our own worker: YuNet and SFace — Locked
**The decision (T-4.5):** at the founder's direction (4 October 2026), face matching moves onto our
own worker, with no third party; the model is Claude's pick:
- **Detection: YuNet**, `face_detection_yunet_2023mar.onnx` (232,589 bytes, SHA-256
  `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`), **MIT licence**.
- **Recognition: SFace**, `face_recognition_sface_2021dec.onnx` (38,696,353 bytes, SHA-256
  `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`), **Apache-2.0**: a
  MobileFaceNet trained with the SFace loss; 99.40% on LFW by OpenCV Zoo's own evaluation.
- Both run through OpenCV's DNN module (`cv2.FaceDetectorYN`, `cv2.FaceRecognizerSF`) from
  `opencv-python-headless`, Apache-2.0, with numpy: **a new dependency, asked for at T-4.5** as
  rule 4 requires. Both models come from OpenCV Zoo, fetched when the image builds and checked
  against the SHA-256s above (the sizes and hashes are the Zoo's Git LFS records, read 4 October
  2026), never committed.

**The licences, plainly:** the code and the weights permit commercial use (MIT, Apache-2.0). **The
weights' training data is a separate question:** OpenCV Zoo doesn't say which set trained the
shipped SFace model, and the SFace paper's experiments used CASIA-WebFace, VGGFace2 and
MS-Celeb-1M, collections of faces of people who weren't asked. That is a question about the model's
origins, not a restriction on using it; it goes to P-0.7's review with the processors' terms.

**What the worker needs** (measured on the founder's Mac, arm64, Python 3.12, 4 October 2026):
peak memory about 290 to 330 MB for Python, OpenCV and both models after one comparison (OpenCV
4.14 and 5.0 both load them); detection about 35 ms on a 1600-pixel photo, one embedding 6 to 24
ms. The worker also runs the app, so on Fly it needs **1 GB, not 512 MB**. Fly's own pricing page
(read that day) prices a shared-cpu-1x 1 GB machine in Singapore at $8.50 a month; 512 MB there is
about $4.68 ($3.69 at its base rate, scaled by Singapore's ratio in the same example), so about
$3.80 a month more. On P-49's VM it costs no machine of its own. The image grows by about 150 MB
(OpenCV about 122 MB installed, numpy about 24 MB) plus the 39 MB model. Linux amd64 figures are
measured in T-4.5, where it runs.

**How accurate it is, is ours now:** there is no vendor to blame when it's wrong, so T-4.5 says how
it is measured, what counts as a right and a wrong match, and the threshold it starts at.

**Rejected:** InsightFace's models (its README: "available for non-commercial research purposes
only"); a hosted face-match API (D-087's reason, and the selfie leaving our servers); OpenCV's
published threshold as the final one (it is calibrated on LFW, celebrities' photos, not on
selfies against profile photos of people in India).

**Approved by the founder, 4 October 2026, with two conditions:** YuNet and SFace through OpenCV,
`opencv-python-headless` as a dependency, and the 1 GB Fly machine at about $8.50 a month ("the
$3.80 is not worth optimising").
1. **The machine's size is locked only once its peak is measured on the actual Fly machine**, not
   transferred from this Mac's arm64 figure: "1 GB has headroom, but a measured number beats a
   transferred one." T-4.5 measures it where the worker runs.
2. **The training-data flag stays on P-0.7 exactly as written above, and is never softened:** the
   weights' licence permits commercial use, and the datasets behind the paper are a separate, real
   concern; both facts stay in the record.

The InsightFace rejection, on its licence, stands and isn't revisited. **Locked**, the machine size
excepted until condition 1 is met.

### D-089 · Uploads are JPEG, PNG or WebP, judged by their bytes — Open
**The decision (T-4.2; the founder, 4 October 2026, correcting Claude's recommendation):**
- **Formats: JPEG, PNG and WebP. No HEIC**, which Pillow can't open without pillow-heif and its
  LGPL and GPL codecs.
- **The server judges the bytes.** When an upload completes, it reads the object's first bytes and
  decides from them. The type the browser declares is sent with the request, because a presigned PUT
  signs it and the upload must carry it, but it is **a hint for a better error message, never the
  authority**: the client supplies it, and it can say anything. A file whose bytes are a PNG
  declared as `image/jpeg` is handled as a PNG; bytes that are none of the three are refused
  whatever they are declared as. Proved by a test that fails if the code trusts the declared type.
- **The refusal says what to do:** "JPEG, PNG or WebP", not only that the format is unsupported.

**Claude's recommendation was "with the type sent in the request".** The founder's correction: the
declared type is the client's to choose, so it can't be what decides (CLAUDE.md rule 6, the server
decides).

**Open until one check, on a real iPhone, on our own control:** does iOS Safari send JPEG from
T-4.6's upload control, or HEIC? Tested on the real control, not reasoned about. If it sends HEIC,
"no HEIC" silently breaks every iPhone sign-up, and we would find out from users, not from tests. On
T-4.6's Done-when; if HEIC arrives, stop and tell the founder before anything ships. Locked when
that check passes.

### D-090 · An under-18 refusal queues its files' deletion before it commits — Locked
**Supersedes one sentence of D-078:** "The enqueue comes after the commit, so a refusal that rolls
back deletes no file a kept row still points to". D-078 is Locked and not edited; the rest of it
stands, the keys read in the deleting transaction before the rows go among it.

**The decision (T-4.2; option (a) of Sprint 4's plan, approved by the founder, 4 October 2026):**
- The storage keys are read in the refusing transaction, before the rows go (D-078).
- **The deletion job is queued before the commit,** delayed 60 seconds, and **deletes only if the
  user is gone.** Precisely, since the queue is Redis and the refusal is Postgres: they don't
  commit together; the order is what makes it safe. If queuing fails, the refusal fails with it and
  nothing is deleted. If the commit fails, or the process dies between queuing and committing, the
  job finds the user still there and deletes nothing. So a refusal that committed always has its
  job, and the guard stops us deleting a photo of someone who was never refused. A user still
  present at 60 seconds is checked once more at 5 minutes, in case the transaction was slow; after
  that, present means rolled back.
- **The object goes; the record that a refusal happened stays.** Rule 12 applies to the record,
  not the image: D-072's `banned_identities` row (the number's hash, reason `underage`) is kept, and
  is both the legally useful thing and the correct one.
- **The log line keeps rule 15:** no phone number, no object key, no signed URL. An internal id is
  enough to find it later: the `banned_identities` row's id.
- **The deletion is verified, not assumed.** After deleting, the job checks that each object is
  actually gone from R2, and succeeds only if every one is; a delete call that returns success is
  not proof the object left. The check is tested to fail when pointed at an object that still
  exists. It retries three times; a final failure is logged at error level, with that id, and
  until T-9.12's alerts exist, that log line is all there is (on T-9.12's list).

### D-091 · Upstash's Free plan, with the worker polling every 10 seconds — Locked
**The decision (the founder, 4 October 2026):** `velora-staging` and `velora-prod` stay on
Upstash's Free plan, and the ARQ worker polls every **10 seconds**, not ARQ's default 0.5 or the 2
Claude proposed. A photo then waits up to 10 seconds more for moderation, acceptable for moderation.

**The arithmetic, from the code and Upstash's page, both read 4 October 2026:**
- **Upstash's limit:** "500K" commands a month on Free, and "Operational commands like AUTH, HELLO,
  SELECT, COMMAND, CONFIG, INFO, PING, RESET, and QUIT are not charged."
- **The worker, idle** (arq 0.28's own loop, read from its source): one `ZRANGEBYSCORE` a poll, and
  once an hour a `ZCARD` and a `PSETEX` for its health key; abort and cron add none unless switched
  on. At 10 seconds over a 30-day month: 259,200 + 1,440 = **260,640 commands, 52% of Free**. At 2
  seconds it would be 1,297,440, and at the default 0.5 seconds 5,185,440: both over.
- **Fly's `/readyz` checks**, every 15 seconds, send `PING`, which isn't charged: 0. (Claude first
  counted them as 172,800 a month, before reading that line; corrected here.)
- **What's left for real traffic:** about 239,000 commands a month per database, each request
  spending one or two (the rate-limit script, the activity throttle), more on sign-in. Measured
  against real use before launch, not assumed.

**One poll site is user-interactive, and 10 seconds is not acceptable there:** `verify_selfie`
(T-4.5). A woman at the selfie step waits on its result (T-4.7 polls for up to 60 seconds), so a
10-second pickup is up to 10 seconds of her watching a spinner. Photo moderation isn't: the photos
step completes on a pending photo (T-4.3). How the selfie avoids the 10 seconds is T-4.5's to
propose and the founder's to decide; the poll interval doesn't change for it.

**If 10 seconds ever exceeds Free,** report the number and stop; never quietly pick a paid plan
(the founder).

### D-092 · Pillow re-encodes every photo, pinned, bounded and proved — Locked
**The decision (T-4.4; approved by the founder, 4 October 2026, with three conditions):** Pillow, a
new dependency (rule 4), opens and re-encodes every uploaded photo on the worker. It is an image
parser reading hostile input, the most dangerous code we run, so:
1. **A full decode and re-encode, never a metadata strip.** Decoding to pixels and encoding a new
   JPEG drops EXIF, stray ICC data and anything appended after the image. **Proved with a photo
   that genuinely carries GPS EXIF:** the test fails if any location survives. Of the three, this
   one matters most (the founder's message: a woman's photo carrying her home coordinates is the
   worst bug this product could ship).
2. **The decompression is bounded.** A small file can expand to gigabytes and take the worker down,
   so Pillow's pixel limit is set explicitly, never left to its default, and **tested with an actual
   bomb file**, not by reading the docs.
3. **The version is pinned exactly** (`==` in `api/pyproject.toml`, where the rest use `>=` and the
   lock pins them), **and it is updated when CVEs land:** this line is the reminder, and T-9.13's
   security review checks it.

### D-093 · A possible-minor photo is rejected and recorded as a signal, never an accusation — Locked
**The decision (T-4.4; option (a) of Sprint 4's plan, approved by the founder, 4 October 2026, with
four conditions):** a photo Sightengine scores as possibly showing a minor is rejected, and a
`fraud_events` row records it; the internal report itself waits for T-9.2's system user. It is a
probability, not a finding, and young-looking adults will be caught by it, so:
1. **The message doesn't accuse.** The person is told "We couldn't verify this photo — try a
   different one", and nothing that says they look underage: getting that wrong to a real woman is
   a harm we would inflict ourselves.
2. **Repeated flags never auto-ban.** They escalate to a human, the founder at this size. No human
   path exists yet, so it is a named open item, P-72, not a silent auto-action left to grow into one.
3. **The fraud event is a signal, not proof:** its `signal` and `meta` say it is a model's score for
   one photo, and nothing downstream (T-9.2's scoring, T-9.5's queue) may read it as an established
   fact about the person.
4. **D-090's shape: the photo goes, the record stays.** The image and every copy of it are deleted;
   the record holds the minimal thing (the user, when, the score and the model), never the image.

### D-094 · Sightengine is built on a fake and proved by one real check of its response's shape — Locked
**The decision (T-4.4; approved by the founder, 4 October 2026, with one condition):** T-4.4 builds
and tests moderation against a fake shaped like Sightengine's documented responses, and its last
step is one real call. **The real call compares the shape, not only the status:** field names,
nesting and types of Sightengine's actual response against the fake's. A fake that spells a field
differently makes every green test a fiction, and a call that returns 200 wouldn't catch it. **The
date of that check and the shape seen are recorded** (on T-4.4), so that when Sightengine changes
something, the record shows whether it was us who went stale or them. The plain image moderation
API only, as T-4.4 already constrains: never hybrid review, never the Feedback API.

### D-095 · The worker deploys to Fly staging now, and moves with the API at P-49 — Locked
**The decision (T-4.4; the founder, 4 October 2026):** T-4.4 deploys the ARQ worker to Fly staging,
as a second Fly app beside the API (`infra/fly.worker.toml`, a 1 GB machine per D-088, a deploy job
after the API's), rather than waiting for P-49's move to a VM in Mumbai, which itself waits on
P-68 and then P-0.18. When P-49 lands it moves two apps, not one.

**Why: the asymmetry.** Waiting means weeks of a staging that accepts uploads and never approves
one, so every demo and every staging check from T-4.6 on dead-ends. Deploying now costs an hour or
two of worker config redone at P-49, and about $8.50 a month until then. Claude first recommended
waiting (option (a) of Sprint 4's plan, D2), then reversed it once the gap to P-49 was clear; the
founder chose the reversal.

**Supersedes** the advisor's direction of 3 October 2026 that P-49 come before Sprint 4 so the
worker is built once on its new host (on T-4.1's Needs line, waived there for T-4.1).

### D-096 · A rejected photo's reason reaches its slot by a read of that photo, and never names a possible minor — Open
**The decision (T-4.6, which the plan asked to decide before building the "rejected" state):**
- **`GET /v1/photos/{id}`:** one of the owner's public or private photos, in any status, rejected
  ones included, as `Photo`. Someone else's photo, a selfie, or no photo: the same 404, so ids
  can't be probed.
- **How the step uses it:** while any photo is pending, the photos step asks `GET /me/photos`
  again every 5 seconds, only while the tab is visible. A photo it saw pending that leaves the list
  is read once by this endpoint; if it was rejected, other than by its owner (`user_deleted`), the
  slot that showed it says why, with "Choose another" and a cross that clears it. Clearing closes
  the gap, so place 0 stays the main photo (03-SCHEMA).
- **The owner hears a reason by name only from a list,** in every `Photo` the API returns:
  `abandoned`, `too_large`, `unsupported_format`, `user_deleted`, `nudity`, `no_face`,
  `text_overlay`. Every other reason, `minor_suspected` included, reaches the owner as `other`,
  which the web says in D-093's words: "We couldn't verify this photo — try a different one". The
  row keeps the true reason for moderation (rule 12).

**Why a read of the one photo:** `GET /me/photos` stays the grid's one source, listing live photos
only, as T-4.3 made it. A rejection is a fact about one photo, which never changes, so it is read
once.

**Why the API masks the reason, not only the web's copy:** D-093's first condition is that nothing
tells the person they look underage, and `"reject_reason": "minor_suspected"` in the response is
exactly that, one tap away in any browser's tools. A list fails closed: a reason T-4.4 or T-9.5 adds
later reaches the owner as `other` until someone decides to name it.

**What it doesn't do:** the page remembers which photos it watched only while it is open. A
rejection that lands after a reload, or after the person has gone on, isn't shown on the photos
step: the slot is simply empty again. Telling them then is P-74.

**Rejected:**
- `GET /me/photos` listing recent rejections too: it changes T-4.3's contract, needs a time window
  or a "seen" flag (a migration), and every caller would have to drop them before reordering.
- Reading the reason from `POST /photos/{id}/complete`, which returns a decided photo as it stands:
  no API change, but a POST used as a read, and it would have handed out `minor_suspected` as it
  was.
- One message for every moderation rejection: no API change, but "no face" and "text over the
  photo" are things the person can fix if told.

Recommended and built by Claude in T-4.6, 4 October 2026. **Open until the founder approves it.**

### D-097 · A Thread lasts an hour; Extend buys a day; a Knot is unchanged — Locked
**The names.** One word, one meaning: CLAUDE.md rule 17 exists for exactly this.
- **Thread** is the live chat. One thing, one name, and it lasts **1 hour**.
- **Extend** is the paid 24-hour option, 10 Velas. It is **not** a Knot, and nothing calls it one:
  a "24-hour knot" is Extend. Like Thread and Knot, it is a product noun, never renamed with the
  brand.
- **Knot** is unchanged (D-003): both people tap "Tie the knot", and it is permanent and free.
  Extend buys time, never permanence, which is granted by the other person.

**How a Thread lives.**
1. A man's first message opens it: 5 Velas, and the hour starts.
2. She replies inside the hour: it stays open, the hour restarts from her message, and nothing more
   is charged. It is the same hour throughout, at the first message or the hundredth.
3. The hour passes: the Thread expires and becomes unavailable to him: he can't send in it until he
   re-opens it. Its history stays readable to both of them.
4. She messages later: it is delivered, and he can see that it is there. He pays 2 Velas to re-open
   the Thread and reply, every time, and it carries on as before.
5. Extend, at any point: 10 Velas, and for 24 hours the Thread doesn't expire.

**Her side** shows only that her message hasn't been seen. Nothing more: no locked state, no
prompt, and never that money stands between her message and his reply. She is never charged.

**Expiry is a state, never a deletion.** Rule 12 holds: nothing in the five tables the app role
can never delete from (`messages`, `reports`, `ledger_entries`, `payments`, `audit_log`; 03-SCHEMA)
is hard-deleted, and her later message reaching him proves the history is still there.
"Unavailable" means he can't send, never that anything is hidden or removed.

**Supersedes two parts of D-003:** "expires 24h after opening" (1 hour, restarted by her message)
and "re-opened for 3 credits" (2 Velas, D-098). D-003's "archived read-only, never deleted" stands,
and so do its Knot and its rule that permanence is never bought.

**Decided, not built.** Today's code, tests and copy still give a Thread 24 hours
(`app_config.thread_hours`, seeded 24). Moving them to 1 hour is surgery on built, tested code and
gets a task of its own, not yet written, which lists every place that says 24 hours. Until it
lands, 24 hours is what runs and 1 hour is what is decided; nothing is changed to match it before
then.

**What this entry leaves open** is on T-5.2's Needs line, with every pricing question, each with
the files it touches. **Answered or moved 4 October 2026 by D-250:** a man answering her first
message pays the 2-Vela re-open; Extend can be bought again and again; (a) and (d) went to
P-150. (c)'s own two were answered by D-253, 5 October 2026: Extend from expired is 10 in all
(the advisor's rule, Open until the founder's word).

**Answered 4 October 2026 (the founder): an expired Thread stays readable.** "Unavailable" means he
can't send, not that he can't read: the history he paid 5 Velas for stays visible to both of them.
**Why:** he bought that conversation, and hiding it would be both harsher than intended and a
change to a live page for no gain. So `/terms` ("kept, read-only") stands as published, and so do
D-003, 06-TESTING's J7 and the prototype. **Corrected with it:** this entry's first version,
written by Claude, glossed "unavailable" as "not shown, never removed", and listed D-003's
"archived read-only" among the parts it superseded, while the same entry put readability down as
an open question. That prejudged the question, and wrongly; both lines are corrected above.

**Noted 4 October 2026: an expired Thread refuses his sends and accepts hers.** That asymmetry is
the product: she sends, he sees it is there, he pays 2 Velas to re-open and reply. She is free
throughout and is never told that money stands in the way. So `THREAD_EXPIRED` is his alone, and
every place that raises or tests it says so (04-API, T-7.1, T-7.3, 06-TESTING's case 12). It
follows from step 4 and the founder's answer above; Claude first wrote it down, and the advisor
(Claude, in a separate chat) confirmed it, relayed by the founder.

The names, the lifetime and the rules are the founder's decision, 4 October 2026. The write-up
they came in is the advisor's (Claude, in a separate chat), relayed by the founder.

### D-098 · What things cost: men pay per action, women pay nothing — Locked (values tunable)
Prices stay data (D-004, D-016): `action_prices` and `gifts`, changed by a row, not a deploy.

| Action | Velas |
|---|---|
| Open a Thread (his first message) | 5 |
| Re-open an expired Thread, every time | 2 |
| Extend a Thread, 24 hours (D-097) | 10 |
| First private message | 8 |
| Every private message after it | 2 |
| View private pictures | 1 |
| Virtual gift | 5 / 10 / 15 / 20 |
| Swiping, either way | Free |
| Tie the knot, and messaging in a Knot (D-003, unchanged) | Free |

15 virtual gifts a week are free. Private messages never expire.

**Women pay nothing, anywhere.** Rate limits only: a woman messages at most 30 men and sends at
most 30 private messages a day. A paid tier above those limits was considered and deliberately
deferred, so **no charging path for women is built: none enabled, and none disabled in the code.**
If it is ever revived, it can't be sold in Velas without reopening D-076, whose rule 1 the
database enforces: no woman ever holds a Vela.

**Re-open and Extend move together.** Extend costs what five re-opens do, so it pays for itself
after five lapses, which one slow day of conversation reaches with a 1-hour Thread. Change neither
price without the other.

**What a message costs in rupees** is in D-099, beside the packs that set it.

**Supersedes** D-004's re-open price (3), and D-016's gift prices (two free, two at 2, two at 4)
and free-gift limit (`gift_free_daily_limit`, 3 a day, now 15 a week). D-016's other rules stand.

**What this entry leaves open** is on T-5.2's Needs line, each question with the files it touches:
D-004's other rows, what a private message is, viewing private pictures, and the gifts. This entry
supersedes only what it names, so until the founder rules, D-004 and D-016 still say the rest.
**Answered 4 October 2026 by D-231,** all but whether a Super Like counts as swiping.
**And that by D-250:** it doesn't, and keeps 5 Velas, by default.

The prices and the rules are the founder's decision, 4 October 2026. The reasoning beside them
(re-open and Extend moving together) is the advisor's write-up (Claude, in a separate chat),
relayed by the founder.

### D-099 · Four packs, and the ₹4,500 one is dominated on purpose — Locked (values tunable)
| Price | Velas | Per Vela | Opening one Thread (5 Velas) |
|---|---|---|---|
| ₹1,500 | 30 | ₹50 | ₹250 |
| ₹4,500 | 100 | ₹45 | ₹225 |
| ₹6,000 | 250 | ₹24 | ₹120 |
| ₹10,000 | 450 | ₹22.22 | ₹111 |

Packs stay rows of `credit_packs` (D-005), priced in paise (D-029).

**The number that decides whether men buy at all:** one message, the 5 Velas that open a Thread,
costs **₹250 at the entry pack and ₹111 at the largest**. Anyone revisiting the pricing starts
here. D-005's was ₹300 and ₹200.

**The ₹4,500 pack is dominated, knowingly.** ₹1,500 more buys 150 more Velas at the next pack, so
few should rationally buy it. It was priced that way on purpose: don't "fix" it by accident. Each
larger pack is still cheaper per Vela, as D-005 required.

**Supersedes** D-005's four packs (25 to 100 Velas, ₹1,500 to ₹4,000) and its number to watch.

**What this entry leaves open** is on T-5.2's Needs line, each question with the files it touches:
the first-purchase bonus, T-10.4's price test, the prototype's packs and its "Most popular" tag on
the dominated pack, and 09-RESEARCH's "about ₹300".
**Answered 4 October 2026 by D-231,** all but T-10.4's price test and whether "Most popular" can
be true on day one. **D-250:** `entry-25` is retired; the day-one question moved to T-8.7.

The packs are the founder's decision, 4 October 2026. The reasoning beside them (the dominated
pack, the ₹250 and ₹111) is the advisor's write-up (Claude, in a separate chat), relayed by the
founder; the arithmetic was checked by Claude.

### D-100 · An unanswered message's Velas aren't returned, and Velas never expire — Locked
**Velas spent on a message that goes unanswered are not returned.** The existing refunds stand
unchanged: a declined album request and Velas spent on a banned user (D-050; T-8.4, T-9.3), a
chargeback reversal (D-076 rule 3, T-8.2) and a duplicate charge (D-050, T-8.3). `/refunds` stays
accurate as published. The bare `refund` ledger reason stays unused, and nothing new uses it
(D-077).

**Velas never expire.** Bought is bought: no expiry job, no dormancy sweep, no balance that quietly
ages out. D-050 already said so; this holds it.

**Every Vela moves through the wallet:** `wallet.service.debit()` or `credit()` (rule 5), gifts and
the weekly free fifteen included. Whatever form the fifteen take (D-098), any Vela they move goes
through one of the two, and no path adds or removes a balance any other way. A paid gift is a
`gift` debit and credits nobody (D-076 rule 2).

**Corrected 4 October 2026, the day it was written.** The first version of this entry said "No
refunds", that "no refund path, no reversal and no pending balance is built", and that a wallet
carrying a quiet, unused refund branch is worse than one without. That came from the advisor's
write-up (Claude, in a separate chat), and it was wrong. The founder's answer had been about one
case, the Velas spent on a first private message that never gets a reply; the write-up generalised
it into a rule against every refund. That rule contradicted `/refunds`, a published page, and
D-050, D-076's rule 3, T-8.2, T-8.3, T-8.4, T-9.3 and two ledger reasons already in code
(`refund_album_declined`, `refund_banned_partner`). Claude's list of those conflicts, reported the
same day, is how it was caught, and the advisor narrowed the entry to the rule above (relayed by
the founder). The wrong version stays recorded here: a wrong rule that was caught is worth more in
the record than a clean one that was lucky.

The rules are the founder's decision, 4 October 2026. The words are the advisor's (Claude, in a
separate chat), relayed by the founder, as corrected above.
**Superseded in part, 4 October 2026, by D-230:** of "the existing refunds" above, the declined
album request and the banned user's return are gone, and `/refunds` stops being accurate until
P-130. The chargeback reversal and the duplicate charge stand.

### D-230 · No product refunds: nothing comes back on a ban or a declined request — Locked
**Nothing is returned on a ban. Nothing is returned when an album request is declined. There is no
product refund of any kind:** Velas spent are spent.

**Supersedes** D-050's "Two cases return Velas automatically" (a declined album request, and Velas
spent on someone banned, for the 7 days before the ban), and D-100's "the existing refunds stand
unchanged" for those two. T-9.3 is dropped; T-8.4's decline returns nothing; 02-ARCHITECTURE's
banned-partner refund goes.

**Two things are not product refunds, and stay:**
- **A chargeback reversal** (D-076 rule 3, T-8.2). The bank takes the money back, not us, and the
  payment's Velas are reversed in the same step.
- **A duplicate charge** (D-050, T-8.3). Our own billing error, where we took money and gave
  nothing; it goes back to the payment method.

Keeping money from either is not a pricing choice: it is a mistake left unfixed. The plan agrees on
both (read 4 October 2026: D-050, D-076 rule 3, T-8.2, T-8.3, and `/refunds`' "When we fix a
payment").

**The two ledger reasons that served the returns stay unused.** `refund_album_declined` and
`refund_banned_partner` are in `ledger_reason_t` and `wallet/rules.py`; nothing writes either, and
neither is ever repurposed for something else. The bare `refund` stays unused too (D-100).

**`/refunds` is wrong as published,** and is rewritten to say this plainly: its "When Velas come
back on their own" section, and the opening line that promises it. It is on staging only today,
since production isn't public yet (REL-1). **P-130 rewrites it, and REL-1 and T-8.1 both need
P-130:** the page can't go public, and no Velas can be sold, while it promises returns that don't
exist.

The rule is the founder's decision, 4 October 2026. The words are the advisor's write-up (Claude,
in a separate chat), relayed by the founder.

### D-231 · Private messages, private pictures, gifts and packs, answered — Locked (values tunable)
The founder's answers, 4 October 2026, to the questions D-098 and D-099 left open.

**A private message is sent from a profile directly, with no swipe and no match.** That is what it
is, and why it costs what it does: 8 Velas for the first, 2 for each after it, and it never expires.
D-004's "Direct message (no match), 5" is the same thing under an older name and an older price: 5
is dead, it is 8. Its identifiers today are `dm_open` and the `dm` origin (T-7.1).

**Private pictures are one thing, not two.** The album request (T-8.4) and "view private pictures"
are the same, at 1 Vela. The 5-Vela request is gone, and so is its refund on a decline (D-230).

**Gifts:** four, at 5, 10, 15 and 20 Velas. The old six (0, 0, 2, 2, 4 and 4) are gone, and so is
the cap of three free a day. **Fifteen gift sends a week are free,** and the sixteenth costs its
price. They are free sends, not a grant of Velas: a free send moves no Vela and writes no ledger
row.

**Packs:** D-099's four stand. The prototype's 30, 100, 150 and 250 Velas are stale: 08-DESIGN §5
records the departure, since the prototype itself is never edited (P-22). **The first-purchase
bonus, +20%, stays, and applies to these packs.** It gives whole Velas on each (6, 20, 50 and 90),
and on a first purchase it moves D-099's number: opening a Thread then costs about ₹208 at the
entry pack and ₹93 at the largest, rather than ₹250 and ₹111 (arithmetic checked by Claude).

**"Most popular" stays on the ₹4,500 pack, chosen knowingly.** It is the dominated pack (D-099):
₹1,500 more buys 150 more Velas. The tag was kept with that arithmetic in front of us. **A separate
problem, the founder's to settle:** at launch nobody has bought anything, so the words are not true
of the world on day one. That is not the value question, and it is open on T-5.2's Needs line.

**Carried by default, not by decision:** unlocking a voice note (5), a Super Like (5) and
revealing one "liked you" (20) stay at D-004's prices. The founder had no preference, so they
survived because nobody said to remove them; recorded so it is visible to anyone revisiting.
Whether a Super Like counts as "swiping", free under D-098, is still open.

**Supersedes** D-004's direct-message row (5) and album-request row (5, refunded if declined);
D-016's six gifts, its two free kinds and `gift_free_daily_limit`; and the questions D-098 and
D-099 left open on these. D-005's bonus stands. 09-RESEARCH's "about ₹300" was stale, not a
decision, and now says ₹250.

**Still open, on T-5.2's Needs line:** whether a Super Like is swiping; the "Most popular" tag on
day one; T-10.4's price test, which these answers didn't reach; and four things about how a Thread
lives (D-097). **Answered or moved 4 October 2026 by D-250.**

The answers are the founder's decision, 4 October 2026. The words are the advisor's write-up
(Claude, in a separate chat), relayed by the founder.

### D-250 · T-5.2's last questions, answered — Locked (values tunable)
The founder's answers, 4 October 2026, to what D-097, D-098, D-099 and D-231 left open on T-5.2's
Needs line, and to three questions Claude raised planning T-5.2.

**A Super Like is not swiping.** Free swiping (D-098) is an ordinary left or right swipe. A Super
Like is its own action and keeps D-004's 5 Velas. **That price survived by default, not by
decision:** the founder had no preference on D-004's other prices (D-231), so it stands because
nobody said to change it, recorded so anyone revisiting it knows it was never weighed.

**`entry-25` is retired, not repriced:** the new packs replace it. **Why, in one number:** ₹999
for 25 is ₹40 a Vela, and D-099's entry pack is ₹50 a Vela, so keeping it would have left the
cheapest pack sitting below the ladder. T-10.4 can propose a fresh test against the new packs when
there are users to test on. Retired is `active = false`, never a deletion: `payments` points at
packs (rule 12).

**T-5.2 replaces the packs** with D-099's four, by a data migration of its own, as 03-SCHEMA said.

**When she wrote first, he pays to answer: the 2-Vela re-open,** `thread_reopen`, a priced action
with a ledger reason of its own (T-5.2's item 10(b)).

**Extend can be bought more than once for one Thread.** Ten Velas buys another 24 hours, as many
times as he likes, so its reason repeats for one ref and D-077's "one entry per event" index leaves
it out, as it does `thread_reopen` (D-251). **Why:** a Thread that hasn't knotted otherwise falls
back to 1-hour windows forever, and a man willing to pay for another day should be able to. It is
also the simpler rule to explain. This answers T-5.2's own "if Extend can be bought more than once",
which Claude's summary to the founder had put as item 10(c). **It doesn't answer (c) as written:**
can he Extend a Thread that has already expired, and do the 10 Velas include the 2 to re-open it?

**Moved, and still open.** Whether "Most popular" can show before anyone has bought goes to T-8.7,
which owns the screen, on its Needs line; the tag stays on the ₹4,500 pack, chosen knowingly
(D-231). D-097's (a), whether his own message restarts the hour, and (d), when the hour starts
after Extend, go to P-150, the 1-hour task, with a pointer at T-7.6; (c)'s two questions go with
them, moved by Claude (the founder to confirm), since they touch no file of T-5.2's either.
**(c)'s two were answered instead, 5 October 2026, by D-253** (the advisor's, Open until the
founder's word), and never moved: P-150 keeps (a)
and (d).

**Supersedes** D-005's beta entry variant (₹999 for 25).

The answers are the founder's decision, 4 October 2026, relayed with the reasons beside them by the
advisor (Claude, in a separate chat). Written up by Claude in T-5.2.

### D-251 · Two new debit reasons: `thread_extend` and `dm_message` — Locked
D-098's two new priced actions each get a ledger reason of their own (T-5.2): Extend is
`thread_extend` (10 Velas) and each private message after the first is `dm_message` (2). The
names are the founder's, 4 October 2026; the shape is Claude's, by D-077's rules:

| reason | direction | `ref_type` | the event in the key | "one entry per event" index |
|---|---|---|---|---|
| `thread_extend` | debit | `thread` | named by the caller | left out: it repeats for one Thread (D-250) |
| `dm_message` | debit | `message` | the message's id | in: one charge per message, ever |

`dm_open` stays the first private message, with the Thread as its ref. `dm_message` refs the
message it paid for, so the index refuses charging one message twice, however its key was built.
Like every reason, each is an `action_prices` key, so `pricing.service` prices it from a row.

The names are the founder's decision, 4 October 2026, relayed by the advisor (Claude, in a separate
chat); the shape is Claude's, in T-5.2.

**Built 4 October 2026 (T-5.2).** `ledger_reason_t` is rebuilt both ways rather than given `ALTER
TYPE ... ADD VALUE` (migration 4a7e20790605 says why), and the downgrade refuses once the ledger
holds either reason, since the ledger keeps every row. Its first version read the type's values
through a `'ledger_reason_t'::regtype` literal, which a prepared statement fixes to an OID: on a
connection that had rebuilt the type once, it read the dropped type's values, none, and built a type
of two. T-5.2's own round-trip test caught it before anything landed; it now joins on the type's
name. P-151 carries the general case.

### D-252 · The four gifts: a coffee, a rose, chocolates, a teddy — Locked (values tunable)
D-231's four gifts at 5, 10, 15 and 20 Velas are four of D-016's six, repriced in place (T-5.2):

| id | label | asset | Velas | sort |
|---|---|---|---|---|
| `coffee` | Coffee | ☕ | 5 | 1 |
| `rose` | Rose | 🌹 | 10 | 2 |
| `chocolate` | Chocolate | 🍫 | 15 | 3 |
| `teddy` | Teddy | 🧸 | 20 | 4 |

`smile` and `wave`, D-016's two free kinds, are retired: `active = false`, never deleted, since
`gift_sends` points at gifts (rule 12).

**Why these four:** they are the ones D-016 already charged for (2, 2, 4 and 4), and a smile at 5
Velas reads wrong. The ladder reads as a casual hello, a romantic one, a treat and a big one.
**Why in place, not new ids:** `gift_sends.credits_charged` copies the price when a gift is sent,
so repricing a row rewrites no history, and no `gift_sends` row existed anywhere when this was
written (T-8.9 builds sending). Every id stays what `gift_sends` points at, and no new artwork is
needed. **Rejected:** a chai and a bouquet, the advisor's first proposal, which would have needed
new assets to say the same thing.

Proposed by Claude in T-5.2, 4 October 2026; confirmed 5 October 2026 in the advisor's relay
(Claude, in a separate chat), with the reasons above. **The choice is the advisor's:** the founder
gave it the gifts to choose (the advisor, 5 October 2026). It is Locked on that delegation, which
is the founder's word.

### D-253 · Extend is one price, at any time, an expired Thread included — Open (the advisor's rule)
**Extend costs 10 Velas and can be bought at any time, on an expired Thread too. From expired, the
10 both re-opens the Thread and extends it: he never pays 2 and then 10.** In the ledger that is
one `thread_extend` debit (D-251), never a `thread_reopen` beside it.

**Why:** any other rule makes a man who wants a day of conversation pay 12 instead of 10 for the
privilege of deciding slowly, and leaves us explaining a stacking rule to people who just want to
talk. One price, one effect, always available.

It answers T-5.2's item 10(c), whose two questions Claude had moved to P-150 (D-250); they were
answerable, so P-150 keeps only (a) and (d). Building it is P-150's: no task sells Extend yet.

The rule and its reason came 5 October 2026 in the advisor's relay (Claude, in a separate chat).
**The rule is the advisor's,** not the founder's (the advisor, 5 October 2026), so it stays Open
until he approves it: an advisor's decision is Locked only on the founder's word. It was first
written Locked; corrected the same day.

### D-101 · What moderation's scores mean — Locked (the minor threshold revisited from real scores)
**The decision (T-4.4; proposed by Claude, decided by the founder, 4 October 2026):** the worker
asks Sightengine for `nudity-2.1`, `face-age` and `text` in one plain `check.json` call
(`face-age`, because Sightengine marks `face-attributes` deprecated), and decides in this order,
the first that holds deciding (`api/app/modules/photos/moderation.py`, each threshold one
constant, each held at its edge by `tests/modules/photos/test_moderation_rules.py`):
1. **`minor_suspected`:** any real face scored **0.35** or more as a minor's. First, so a photo
   that also scores as sexual is handled as D-093 says (P-81 asks the lawyer about that case).
   **0.35 was chosen for an asymmetry, not from data:** nobody has seen how this model scores real
   photos. Claude proposed 0.5; the founder lowered it: "The two errors are not symmetric. A false
   positive costs a young-looking woman a polite 'try a different photo'. A false negative puts a
   minor's photo on a dating app. When the costs differ that much, the threshold belongs on the
   cautious side of the coin flip." (Sightengine says faces near 18 score close to 0.5.)
   **Revisited once there are real scores to look at** (on T-9.5, where they are first seen).
2. **`nudity`:** sexual activity, sexual display, erotica or "very suggestive" at 0.5 or more.
   Swimwear, a bare chest and the merely suggestive pass: ordinary on dating profiles.
3. **`no_face`:** a public photo with no real face (drawings, statues and masks don't count). A
   private one needs none: only people its owner chose see it (T-8.4).
4. **`text_overlay`:** embedded text at 0.8 or more. Overlaid numbers and handles would get round
   the chat's masking (T-7.3); text in the scene is "natural" and passes.

The founder approved 2, 3 and 4 as proposed, and changed 1.

**The reader is strict only where it reads** (the founder, the same day): the fields these four
read fail closed if renamed, moved, missing or retyped; any other field may change or go, and a
field never seen before is logged by name, once a process (`moderation.unknown_fields`), never
refused. "A vendor adding something harmless" must not stop every upload.

**What the owner reads is T-4.6's to decide,** not this entry's: the column keeps the reason
for moderation (rule 12), and T-4.6 proposes naming to the owner only reasons on a list, so
`minor_suspected` reaches them as `other`, in D-093's words.

**Its number predates the D-number blocks** (CLAUDE.md, "P- and D-numbers"): it was on `main`
before that rule, so it keeps it; renumbering would risk the stale reference the rule prevents.
---

## Adding a decision

Append `D-0NN · Title — Locked|Open`, with Decision, Why, Rejected. Never edit a Locked entry —
supersede it with a new one that references the old ID.
