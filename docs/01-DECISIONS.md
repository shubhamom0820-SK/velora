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
| Reveal one "liked you" | 20; **1 from 8 October 2026 (the founder)** |
| Tie the knot / message in a knot | Free |

Women pay nothing for any action.
**Superseded in part, 4 October 2026, by D-098:** re-opening is 2, and Extend (10), private messages
(8, then 2) and viewing private pictures (1) are added. Whether the rows D-098 doesn't name stay is
open, on T-5.2's Needs line.
**Superseded in part, 4 October 2026, by D-231:** the direct message above is the private message,
now 8 and then 2; the album request is viewing private pictures, now 1, and a decline returns
nothing (D-230). The voice-note unlock, Super Like and "liked you" reveal stay, by default.
**Noted 8 October 2026: the "liked you" reveal is 1 Vela,** the founder's word ("koi like kiya
reveal karne ka ek vela"). A value change, since the values are tunable (D-098): the row changes
and no decision reopens. P-370's data migration `e4e517f62ce3` moved the row from 20 to 1 the
same day, before T-6.7 charges it.

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

**Amended 7 October 2026 (the founder): the selfie and its face match are mandatory; liveness waits
until after launch (D-380).** A woman's profile still goes live only once her selfie has been
compared with her photos and matched (T-4.5): that is built, and the database refuses anything
else (`users_done_needs_a_match`, D-310). Liveness moves to T-4.11, which is no longer in REL-1's
tag or on T-9.15's Needs line. The sentence above stands as written, struck by this amendment where
it says liveness. Men stay optional. Why, in the founder's words, is D-380's.

**Amended again, 7 October 2026 (the founder; D-391): the selfie is compared with her face photo,
not her profile photos.** A woman's profile still goes live only once her selfie has been
compared and matched, and the database still refuses anything else; what it is compared with is
the one photo she gives for the check, private unless she chooses to show it (D-391). Her profile
photos need show no face, and she needs none (D-392). The amendment above stands as written,
struck where it says "with her photos". What others see of the match is D-393's badge, a
separate rule. Built by T-4.12.

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

The seeded areas were Bengaluru's, from when Bengaluru was this decision's default, until P-38
replaced them with Phagwara's (5 October 2026). Closed by the founder on 1 October 2026.

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

**Amended 8 October 2026 (D-410): on `main` the run vouches from the branch run of the same SHA;
full CI there only when nothing vouches.** The decision isn't reopened: CI is binding through
`/done` as above, and `main`'s run still completes green for the exact commit, which is what the
deploy and both gates read.


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
**Noted 8 October 2026, D-470:** a man's hashed number is also kept so his number gets welcome
Velas once, ever: a later account on it gets none. `/privacy` says why the hash is kept ("so that
deleting an account can't be used to escape a ban or a report"), and T-8.11 adds this reason there.

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
**Superseded in part, 8 October 2026, by D-541:** the trigger came at T-6.6's search, not T-6.5;
the sign-in and app routes now carry a nonce per response instead of `'unsafe-inline'`, and the
marketing pages keep this policy and stay static.

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
**Where the check stands (5 October 2026):** two uploads on staging through T-4.6's photos step
were accepted by `complete`, which reads the bytes on arrival and refuses HEIC, so neither was
HEIC; whether they were JPEG rather than PNG or WebP is unknown, since the worker replaces the
upload with its re-encode within seconds. Still Open: which device made them is the founder's to
confirm (T-4.6's Done-when).
**Why it stays Open (the founder, 5 October 2026, in his own words):** T-4.6's box is closed on
that evidence, which excludes the real risk, a HEIC refused breaking every iPhone sign-up. It is
not Locked, because two things are still open: whether an iPhone sends JPEG rather than PNG or
WebP, and which device and browser made those uploads, which wasn't recorded. P-165 records an
iPhone's upload before REL-1.

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
**Noted 8 October 2026 (T-8.1, D-483):** the worker now runs one cron, `log_turnover`, once a day.
ARQ checks cron schedules in the heartbeat each poll already makes, so the sum above is unchanged
but for one job's enqueue, run and cleanup a day, about a dozen commands: a few hundred a month,
under 0.1% of Free. Estimated from arq's source, not measured.

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

Recommended and built by Claude in T-4.6, 4 October 2026. Approved as built by the advisor
directing T-4.6 (Claude, in a separate chat), relayed by the founder, 5 October 2026, in the
advisor's words, not the founder's; the advisor says the founder hasn't read it yet. **Open until
the founder approves it.**

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
(the advisor's rule, Open until the founder's word; Locked on it 8 October 2026).

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

**Answered 8 October 2026 (the founder): the hour is hers alone.** The two questions D-250 moved
to P-150, decided at 12:40 at night, in his words:
- (a) "P-150 ka a ka nahi": **his own message never restarts the hour.** Only hers does, as step 2
  says; step 2 was silent on his, and now isn't. So he can't keep a Thread open alone by writing
  every 59 minutes, and an hour of her silence expires it whatever he sent.
- (d) "ghanta uske aakhri message se gina jayega": **when Extend's 24 hours end, the hour is
  counted from her last message,** not from the moment Extend ends. Extend bought 24 hours, never
  25. So a Thread he extended can expire the instant the extension ends, if her last message is
  more than an hour old by then: the case P-150 named as the worst if guessed, now decided, not
  guessed.
Nothing above changes; the five steps stand, and step 2's "restarted by her message" now means
hers only. Written up by Claude, 8 October 2026.

**Written 8 October 2026: the 1-hour task is T-7.6** (P-150). It sets `thread_hours` to 1 with
the copy that promises it, and sells Extend; how it keeps the hour is D-560. Until it lands, 24
hours still runs.

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
**Noted 8 October 2026: welcome 5 + reveal 1 = a new man can reveal five people who liked him for
nothing.** Every new man gets 5 Velas when he finishes sign-up (D-470), and a "liked you" reveal is
now 1 Vela (D-004's note). The founder chose this knowing it.

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
**Noted 8 October 2026, D-450:** these prices are GST-inclusive (the founder, after a chartered
accountant, by phone). A user pays ₹1,500 today, with Velora unregistered, and ₹1,500 after
registration, when ₹1,271 is Velora's and ₹229 the government's. The table's rupees don't move;
what moves is the split.
**Noted 8 October 2026: the number falls on his second Thread, not his first** (the founder, on
the advisor's recommendation, Claude in a separate chat, relayed by the founder). The welcome 5
Velas (D-470) cover a man's first Thread, so the one he first pays for is his second. Its ₹250
and ₹111 don't move. Nothing else in this entry changes.

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
**The reveal is 1 Vela from 8 October 2026 (the founder),** a value change, not this entry
reopened (D-004's note); P-370 moves the row.
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
founder's word; Locked on it 8 October 2026), and never moved: P-150 keeps (a)
and (d). **(a) and (d) were answered 8 October 2026** (the founder; D-097's amendment): his own
message never restarts the hour, and when Extend's 24 hours end the hour runs from her last
message.

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

### D-253 · Extend is one price, at any time, an expired Thread included — Locked (the advisor's rule, on the founder's word)
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

**Locked 8 October 2026 on the founder's word:** "d 253 ka sahi hai" (D-253's is right). The rule
and its reason above are the advisor's, as written; the founder's word makes them his. Nothing
above changes.

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

**Amended 7 October 2026 (the founder; D-391, D-392): `no_face` applies to the face photo and
never to a public photo.** Item 3 stands as written, struck where it says a public photo: a public
photo with no real face passes, since nobody need see the person's face there (D-392); the face
photo, whose only job is the selfie check, is rejected `no_face` exactly as item 3 says; a private
album photo needs none, as before. The selfie's own `no_face` is D-263's, YuNet's count on the
worker, not this threshold. Items 1, 2 and 4 apply to every kind, the face photo included. Built
by T-4.12.

### D-280 · Required status checks work without pull requests, so D-044's reason for rejecting them was false — Open
**The correction (T-4.6, 4 and 5 October 2026):** D-044 (Locked) rejected required status checks
because "GitHub attaches them to pull requests, and this project merges by fast-forward without
pull requests, so there is nothing to require them on." GitHub's own page says otherwise: "After
all required status checks pass, any commits must either be pushed to another branch and then
merged or pushed directly to the protected branch." (About protected branches, read by Claude from
the page itself, 4 October 2026.) Pushed directly is our flow exactly: the task branch is pushed,
CI runs on it, and `main` is fast-forwarded to that same commit. With "Do not allow bypassing the
above settings" it binds admins too. **This supersedes D-044's rejection of required status checks
(its "Rejected: required status checks" sentences) and nothing else of D-044;** D-044 is not
edited.

**Why it isn't on today:** GitHub refuses it for this repository. Asked for `main`'s protection
on 4 October 2026, its API answered 403: "Upgrade to GitHub Pro or make this repository public to
enable this feature." GitHub's plans page lists protected branches in private repositories among
what GitHub Pro adds.

**What covers it meanwhile:** the landing guard (`76bda6f`, `scripts/push-gate`, installed by
`make hooks`): a push that moves `main` is refused unless `make lint`, `make test` and CI passed
for that exact commit. Checked by Claude on 5 October 2026 through the installed hook: an
unchecked commit pushed as `main`, piped through `tail -1` with `&&` after, ran the `&&` and
landed nothing ("push-gate: refused: make lint and make test hasn't passed on 3c589da's tree in
this checkout."). **A hook protects the clones that installed it; a required check at GitHub
protects every clone that will ever exist,** and is the one `git push --no-verify` can't skip.
Today there is one machine and the guard covers it; before production deploys matter, that stops
being true. P-180 turns the check on before REL-1.

**Why recorded now, before it can be used:** a decision resting on a false premise is worse than
none, because it looks settled, and the next reader of D-044 would take "nothing to require them
on" as fact. The finding is Claude's, from T-4.6 (GitHub's page, and its 403 for this repository);
recording it now, superseding rather than editing, is at the direction of the advisor directing
T-4.6 (Claude, in a separate chat), relayed by the founder, 5 October 2026. **Open until the
founder approves it.**

### D-260 · The face-match threshold is SFace's published number, unmeasured on our users — Locked
**The decision (T-4.5; the founder, 4 October 2026, in his own words: "test kiye bina aage
badho", go ahead without testing):** selfie face matching ships at **0.363 cosine similarity**,
and **the measurement set T-4.5 planned (50 consenting people, 5 selfies each) is dropped. It is
not happening before launch,** and no task pretends otherwise.

**Whose number it is, plainly.** OpenCV's face recognition tutorial
(`doc/tutorials/dnn/dnn_face/dnn_face.markdown`, read by Claude on 5 October 2026) publishes
SFace's thresholds per dataset: LFW 0.363, CALFW 0.340, CPLFW 0.275, AgeDB-30 0.277, CFP-FP 0.212,
and says two faces are the same identity "if the cosine distance is greater than or equal to
0.363". It doesn't say how the thresholds were chosen. The model was trained and provided by the
SFace paper's authors (the tutorial's thanks). **So 0.363 is the model's authors' number, measured
on their data (LFW: photos of celebrities), not a number we chose or measured on ours.** It is the
strictest of their five. Nobody knows our false-accept rate.

**Supersedes** D-088's "Rejected: … OpenCV's published threshold as the final one". D-088 is
Locked and not edited; the rest of it stands. It is final until P-160 measures one.

**What carries the risk instead** (the advisor directing T-4.5, Claude in a separate chat,
relayed by the founder; D-262 and D-264 record each):
1. **The words.** Nothing published says "verified" or anything read as a guarantee (D-262).
2. **A human.** The founder looks at every decision, at launch volumes (D-264).

**What face matching does and doesn't do, said plainly so nobody reads more into it.** It
catches a careless impostor: a selfie of someone other than the person in the profile's photos.
**It does not stop a man who has a woman's photos and one real selfie of her:** that selfie
matches her photos closely, nowhere near the threshold. Only liveness (T-4.11) or a person looking
at the selfie stops that. Until one of them exists, the human isn't optional. Found by Claude in
T-4.5's plan: it refuted the near-threshold review the advisor first proposed as the stand-in for
the measurement set, since that list would have shown nothing and felt like cover.

**Amended 7 October 2026 (D-380): passive liveness doesn't stop it either.** The sentence above,
"Only liveness (T-4.11) or a person looking at the selfie stops that", stands as written, struck by
this amendment where it names liveness: T-4.11's research (Claude, 5 October 2026) found that a
single-photo liveness check, ours or Sightengine's, can't stop this attack on the web. The selfie
reaches the server as bytes, by a presigned PUT (`photos/service.py`, `storage.presign_put`), so
the server can't tell a camera from a file: the man uploads her real selfie as it is, a photo of a
live face, which such a model is built to call real. What would stop it is a freshness mechanism,
something in the selfie that couldn't exist before the request, and that is a separate decision
(D-380, its first). The human stays not optional, as above.

**Locked** on the founder's words, confirmed by him on 5 October 2026 as his own (the
surrounding reasoning is the advisor's, relayed).

### D-261 · A selfie is woken onto the worker, and the queue still guarantees it — Open
**The decision (T-4.5, answering D-091's "how the selfie avoids the 10 seconds"):** after
`POST /verification/{id}/submit` commits, the API publishes the verification's id on the Redis
channel `wake:verify_selfie` (`core/queue.py`, `Queue.wake`). The worker keeps one subscribed
connection (`app/workers/wake.py`) and runs the comparison the moment it hears it, one at a time.
**The queued `verify_selfie` job is still queued, and is the path sure to run:** a wake lost while
the listener reconnects or the worker restarts costs those 10 seconds, never the selfie. Both may
compare the same selfie; the decision is written once, with the user's row locked (tested with the
overlap forced, `test_race.py`). D-091's poll interval doesn't change.

**What it costs Upstash's Free plan** (D-091's budget): nothing while idle. The connection is kept
alive by PING every 30 seconds, which Upstash doesn't charge. Per selfie: one PUBLISH, plus its
delivery if Upstash counts deliveries (its pricing and billing pages don't say; measured on
staging). Per reconnect: one SUBSCRIBE, backing off to one every 5 minutes, and back to a second
only after a connection held 5 minutes, so even a connection that never holds costs at most 8,640
a month (1.7% of Free). A wake that fails or hangs (1 second) is logged and never fails the
request. A test listens on a channel of its own, since Redis shares channels across databases.

**What she sees** (T-4.7's line): what is happening, "comparing your selfie with your photos";
and if no result has come after about 15 seconds, plainly that it can take a minute and she can
leave, the result there when she is back.

**Rejected:** lowering the poll interval (D-091's arithmetic: 2 seconds is 1.3 million commands a
month); comparing faces in the API (it would put the image parser that reads uploads, and about
300 MB of models, into the API: D-092's reasons); a second ARQ worker polling a selfie queue fast
(the same arithmetic); `BLPOP` (a blocked call can't be health-checked on its connection, and
needs a timeout loop that costs commands while idle); an HTTP port on the worker (a second way in).

Proposed by Claude in T-4.5's plan; approved by the advisor directing T-4.5 (Claude, in a
separate chat), relayed by the founder, 5 October 2026. **Open** until the founder approves it in
his own words.

### D-262 · What we say about the selfie: what is done, never a guarantee — Open
**The decision (T-4.5):** no word we publish (the UI, `/privacy`, `/terms`, the landing page, any
badge, onboarding copy) says or implies that a person is verified, real, live, or who they say
they are. It says what happens: the selfie is compared with the profile's photos. The four strings
T-4.5 found, rewritten:
- `/privacy`: "Your selfie, which we compare with the photos on your profile. Other people on
  {app} never see it; our team may look at it to check a comparison." **"Our team may look at it"
  must stay, and is never softened later:** it is literally true, since the founder looks at every
  one (D-264). The old "It's never shown to anyone" was false the day review began.
- The landing page: "Checked and moderated"; "Selfies compared with profile photos, and every
  photo checked." **The old clause "reports that actually remove people" is cut:** reporting is
  T-9.1 and acting on a report T-9.5, neither built, so it promised something that doesn't exist.
  It comes back with them, in words they make true.
- The badge: "Selfie matches photos", **with a face (lucide's `ScanFace`), not a shield**: a
  shield reads as a security guarantee, beside words that say only that a selfie matched photos.
- `/terms`: "Before a woman's profile goes live, she takes a selfie, which we compare with her
  profile photos; for men it's optional."

**Held by a test** (`web/src/i18n/claims.test.ts`): every string in `en.ts` and the share image's
alt text is searched for "verif", "really you", "who you say", "real person", "live person",
"liveness", "genuine", "authentic", "guarantee" and identity "confirm"s; two strings are allowed
by name, each with why (the sign-in code's "Verify"; D-093's Locked "We couldn't verify this
photo"), and the allowed list is held exact. The API's field `is_verified` and the query `verified=`
are identifiers, not copy, and stay. The prototype's "Face matched — verified" and "verified
profiles get noticeably more replies" are overridden here (08-DESIGN).

**When it may change:** only after P-160 measures the threshold, and then by the founder's decision.

Rewrites proposed by Claude; approved with two changes (the reports clause, the icon) by the
advisor directing T-4.5 (Claude, in a separate chat), relayed by the founder, 5 October 2026.
**Open** until the founder approves it in his own words.

**Amended 7 October 2026 (the founder; D-393): the badge's icon is a tick in `--accent`, the
founder's choice.** He chose it knowing a tick reads as "verified" where the words may not say it;
the face (`ScanFace`) above is struck. **The words don't move:** the badge's label and aria-label
say "Selfie matched", every string stays under `claims.test.ts`, and nothing on this list is
loosened. The strings above that say "profile photos" are rewritten once more by T-4.12, since the
selfie is compared with the face photo (D-391) and public photos with a face are compared with
the selfie for the badge (D-393), inside this rule; and the face photo's name in copy never
matches `/verif/i` ("face photo", the advisor's recommendation). 08-DESIGN's item 14 carries the
same amendment.

### D-263 · A verification's shape, without a migration — Open
**The decision (T-4.5):**
- **No pose** (the founder, 4 October 2026). `POST /verification/challenge` becomes
  `POST /verification/start`, returning `Verification`; the `challenge` column, `text not null`,
  holds the literal `none`. `liveness_ok` stays null: nothing checks it until T-4.11.
- **`Verification`** is `{id, status, submitted, reject_reason, attempts_left}`: never a number, a
  link or the selfie, so an answer can't tune an impostor's next try. The owner hears a reason by
  name only from a list (`no_face`, `many_faces`, `no_match`, `no_photos`, `unreadable`,
  `unavailable`); anything else reads `other`.
- **The numbers go in the selfie's `moderation` record** (`photos.moderation`, already "the scores
  the decision read"): each compared photo's id and cosine similarity, exactly; the best; the
  threshold at the time; the model; whether a wake or the queue decided; and, later, the founder's
  verdict. **`verifications.similarity` stays empty:** `numeric(5,2)` stores two places, so an
  approved 0.3634 would read 0.36, below the threshold that approved it. Widening it is a
  migration, P-164, when it is wanted; T-4.5 doesn't wait on P-65 for it.
- **Five selfies in a rolling 24 hours,** counted at start and at submit: `RATE_LIMITED` with
  `retry_after_s`. A selfie uploaded and never sent is replaced by the next upload (`replaced`, its
  file deleted), so nobody is stuck behind one.

Proposed by Claude in T-4.5's plan; option (a) of its precision question chosen by the advisor
directing T-4.5 (Claude, in a separate chat), relayed by the founder, 5 October 2026. **Open**
until the founder approves it in his own words.

### D-264 · The founder looks at every selfie, by `fly ssh` — Open
**The decision (T-4.5):** until P-160 measures the threshold, the founder looks at every decision at
launch volumes, a woman's whatever its number, with `python -m app.tools.selfie_review` run over
`flyctl ssh` ("Looking at selfies" in infra/STAGING.md and PRODUCTION.md). It lists every decision
of the last 7 days without a verdict, newest first, marking those near the threshold (0.25 to 0.50,
a guess) and approved profiles whose other photos didn't match ("mixed", P-162); `--near` narrows to
those. Decisions are made automatically and reviewed after: holding them needs someone online
whenever anyone signs up, which is not a system, and holding wouldn't catch the attack D-260 names
anyway.

**Each verdict is the measurement.** `--verdict <id> same|different` writes into the selfie's
record whether the selfie and the photos show the same person. Those verdicts, gathered from real
decisions while protecting the people in them, build the data the dropped measurement set would
have (P-160). It changes nothing else; overturning a decision is P-163.

**An exception to `storage_probe`'s house style, recorded so nobody "fixes" it:** this tool
prints links. The founder has to see each selfie, and a selfie is never public, so each is a
signed link to the private bucket lasting 10 minutes, printed to the terminal of whoever runs it
behind Fly's own login, and never logged. **Rejected:** an admin API endpoint and page listing
women's selfies: more convenient, but a role check is a weaker gate than Fly's login, and a bug in
it would expose every selfie. Claude never runs the tool against real people's selfies; on
staging, only its own test accounts'.

Proposed by Claude in T-4.5's plan; chosen, with the verdicts, by the advisor directing T-4.5
(Claude, in a separate chat), relayed by the founder, 5 October 2026. **Open** until the founder
approves it in his own words.

### D-270 · Every list pages by an unsigned cursor, 1 to 50 at a time, refused outside that — Locked
**The decision (T-5.3, the first list):** every endpoint that returns a list a page at a time does
it one way, through `app/core/pagination.py`:
- **The cursor isn't signed.** It is the last item's sort key: a position, never a permission.
  Every list's query also filters by who is asking, so an edited or borrowed cursor only moves
  within the caller's own list. Signing it would add a secret to keep, rotate and keep out of logs,
  guarding nothing that filter doesn't.
- **Its format:** the sort key as compact JSON, then base64url without padding (the ledger's is
  `(created_at, id)`). The client treats it as opaque and only sends back what it was given. A
  cursor is accepted only if it is exactly what the API would write for the position it names;
  anything else, the same position spelt another way included, is `VALIDATION_ERROR` on `cursor`
  (400).
- **`limit` is 1 to 50, 20 when absent, and refused outside that, never clamped:**
  `VALIDATION_ERROR` on `limit`. A caller asking for 500 and given 50 would get something it
  never asked for, and the web's bug would never show.
- **Each list names its page:** `class LedgerEntryPage(Page[LedgerEntry])`, so the OpenAPI schema
  and `web/src/types/api.ts` say `LedgerEntryPage`, not Pydantic's `Page_LedgerEntry_`. A page is
  `{items, next_cursor}`, `next_cursor` null on the last. Each list fetches one row more than its
  page, so a last page that is exactly full still ends with null.

**Why a decision, not only 02-ARCHITECTURE §3's line:** every later list (discovery, threads,
messages, gifts, notifications, admin) follows this, and a later task could change a line in §3
without knowing it was a rule.

**Rejected:**
- a signed cursor, for the reason above;
- clamping `limit`;
- a cursor on `created_at` alone, which skips or repeats entries that share one (every entry of one
  transaction does);
- offset paging, which shifts as rows arrive.

Proposed by Claude in T-5.3's plan, 5 October 2026. The answers to that plan, pasted by the founder
the same day, chose `limit` refused rather than clamped and asked for this as a decision with these
four parts. **Locked by the founder, in his own words, 5 October 2026**, answering T-5.3's report:
all four are settled for every list, and no later task reopens them.

### D-220 · The location question: after Name, inside India's box, the nearest area within 2 km — Locked
**The decision (T-4.10):**
- **Where it's asked:** after Name and before Username, at `/onboarding/location`, a slug in D-080's
  map. It has no `onboarding_t` step and never moves the step: `PUT /me/location` works from
  `username` on, and before that is `ONBOARDING_INCOMPLETE` (D-068's rule, Name being the step it
  follows). `Me.profile.location` says `none`, `fresh` or `stale`, and while it's `none` the web
  sends anyone past Name to the question (`placeOf`, `web/src/lib/onboarding.ts`). Onboarding is 13
  screens. No migration.
- **`PUT /me/location` answers `Me`,** not the 204 04-API first said: every other onboarding write
  answers `Me`, and the web routes by it. With 204 it would ask `GET /me` again, 1.8 to 3 s on
  staging (P-49).
- **A shared position must be inside India's bounding box:** latitude 6.5 to 37.5, longitude 68.0
  to 97.5. These are the mainland's extents (8°4′N to 37°6′N, 68°7′E to 97°25′E) and Indira Point
  (6°45′N), rounded outward to the half degree. Outside it: `VALIDATION_ERROR` naming `lat`, `lng`
  or both, and the web shows the area picker. **What a box can't do:** it also holds Nepal, Bhutan,
  Bangladesh, much of Pakistan, Sri Lanka and parts of China and Myanmar. No box can follow a
  border, and a test says so (`test_the_box_is_known_to_hold_some_neighbours_too`). Who can sign up
  narrows this more than the box: only `+91` numbers (`PHONE_NOT_SUPPORTED`, and Firebase's SMS
  region policy, India only, T-3.14). That bounds the number, not where its holder stands: a `+91`
  phone abroad still signs up, and if its position is outside the box, it picks an area.
- **A shared position's area** is the nearest one whose centroid is within 2 km, or none, replacing
  any area picked before. Someone in Jalandhar is in none of Phagwara's areas. The seed already
  matched: its profiles sit within 250 m of their own centroid, nearer it than any other. A test now
  holds the seed to the API's own rule and query.
- **A picked area** stores exactly its centroid as the location (D-034).
- **`area_id` is never shown to anyone.** `/privacy` promises that other people see only a
  distance, rounded to the kilometre; an area's name would be more than that.
- **Stale is the server's word:** over 6 hours old by `core.clock`. When the app opens, the web
  refreshes a `stale` location only if the browser already allows it (the Permissions API says
  `granted`), so never with a prompt nobody tapped for. Judged by the phone's clock, a phone set
  wrong would refresh on every open, or never (rule 6).
- **`GET /areas`** answers `{id, city, name}`, never a centroid, by city then name in any case,
  whatever the database's collation. `city` is optional, matched in any case. The web asks for
  every area: the launch city lives only in the data (D-013), and filtering by the city a person
  typed would leave someone who typed "Jalandhar" with an empty picker and no way on.
- **10 an hour per user** (02-ARCHITECTURE §12). It slows someone moving themselves about to measure
  distances, and doesn't stop them: three readings are enough (P-120).
- **The screen has no prototype** (08-DESIGN §5). It is the onboarding frame's existing parts, not a
  design: one more case of P-57's gap, not a new one.

**Rejected:** a new `onboarding_t` value, a migration for a question whose only state is
`location_updated_at`; a shared position leaving `area_id` empty, which would cost the seed its
areas and make `area_id` mean only "picked by hand"; the nearest area at any distance, which puts
Delhi in Hadiabad; `stale` judged by the phone's clock; 204.

Proposed by Claude in T-4.10's plan; approved, all six of its questions, by the advisor directing
T-4.10 (Claude, in a separate chat), relayed by the founder, 5 October 2026. **Locked** by the
founder in his own words the same day, confirmed when asked: the question after Name and before
Username, `onboarding_step` never moving, `{lat,lng}` inside India's box or else an area's
centroid, the 2 km rule, `PUT /me/location` answering `Me`, stale by the server's clock at 6 hours,
and `GET /areas`'s shape; and no later task reopens them (his words, translated from Hindi).

### D-310 · Finishing onboarding: what `done` needs, its refusals, completeness, and a guard in the database — Open
**The decision (T-4.8):**
- **`POST /me/onboarding/complete` answers `Me`:** the `selfie` step's way to `done`. A man's "Skip
  for now" and a match's "Continue" both call it. D-068's rule: before `selfie`,
  `ONBOARDING_INCOMPLETE`; at it, it finishes; once `done`, it answers `Me` unchanged, checking and
  recomputing nothing. No body, and no rate limit: a few reads and one row, nothing sent anywhere,
  like every other onboarding step.
- **What `done` needs,** each named in `PROFILE_INCOMPLETE` (403) `details.missing`, all at once, in
  the order onboarding asks for them, so the first is the earliest screen to go back to: `seeking`,
  `intents` (1 to 3, D-041), `first_name`, `hometown`, `city`, `location` (T-4.10), `username`,
  `about`, `photo`, `interests` (exactly 5). Seeking and intents are included because discovery
  reads both (T-6.2 filters by `intent_ids`).
- **A photo means an approved public photo with its public copy.** One still being checked doesn't
  count: the discovery card shows only approved photos, so a profile that finished on a pending one
  would show none if moderation then refused it. Nor does one its owner removed: `DELETE
  /photos/{id}` rejects it as `user_deleted` and keeps its `public_key` (T-4.3), so the status is
  checked, not the key alone. A breaking run found that, against a test that had assumed otherwise.
- **The selfie:** anyone but a man needs `users.is_verified`, which is T-4.5's own record of the
  match, set in the same transaction as the verification's `approved`, and what its `start` reads.
  It is an allowlist (`MAY_FINISH_UNMATCHED`, men only), as the web's "Skip for now" is: a woman, or
  someone with no gender, gets `VERIFICATION_REQUIRED` (403). What's missing is said first: the
  selfie is compared with the photos.
- **In the database too:** `users_done_needs_a_match` (migration `15a9b138750b`) refuses any insert,
  or update of `onboarding_step`, that moves a user to `done` unless they are a man or
  `is_verified`. It raises `check_violation` naming itself, as D-076's triggers do. It checks only
  the move to `done`: a row already there is left alone, so what happens when a live woman's match
  is cleared stays P-161's and P-163's to decide. Its upgrade first counts users already `done`
  who are neither men nor verified, and fails if there are any. The deploy's readback
  (`scripts/migrate-with-url`, P-65) checks it beside D-076's two, and the app's database role
  can't disable it.
- **Completeness:** 50 for meeting the requirements, plus 10 for each approved public photo after
  the first, up to 100 (six places). It is computed once, at `done`. P-210 keeps it current after
  that, before T-6.2 ranks by it. The seed's finished profiles get it by the same rule: 50 each, one
  photo apiece.
- **The web:** "Skip for now" and "Continue" call it and go where the `Me` it returns says
  (`/discover`). A refusal says the first thing missing, with a link to its screen ("Take me
  there"), or that the selfie hasn't matched, and then reads `Me` and the latest verification
  afresh. T-4.7's stand-in panel and its string are gone.

**Why:** the server decides (rule 6, D-082). The screen only hides "Skip for now" from women; this
check is what stops one finishing. A service check holds only while every writer goes through the
service, and D-008 (Locked) says a woman's profile never goes live without the selfie, so the
database refuses it too, rather than a rule written down. Completeness is already in the schema and
ranking reads it (D-032): at 100 for everyone the column would mean nothing, and a later task would
have to build it again. (The reasons are the advisor's, given with the answers below.)

**Rejected:** every finished profile at 100; a pending photo counted, which would leave a card with
no photo; seeking and intents left out, without which no profile can be ranked or filtered; the
trigger left to a Proposed task, leaving a service check that any later code path can bypass;
`ONBOARDING_INCOMPLETE` reused with a step the person is already past, when D-068 says
`details.step` is their current step; a trigger that also refuses rows already `done`, which would
decide P-161 and P-163 for them; a rate limit.

Proposed by Claude in T-4.8's plan, 5 October 2026. Its five questions were answered by the
advisor directing T-4.8 (Claude, in a separate chat), relayed by the founder, 5 October 2026:
completeness as above; approved photos only; seeking and intents required; the trigger built in
this task; the seed's completeness set, with a test. **Open:** the answers are the advisor's, not
the founder's own words (his, the same day).

**Amended 7 October 2026 (the founder; D-392): `photo` leaves what `done` needs, and completeness
is unchanged.** Anyone, a man or a woman, may finish with no approved public photo, so `photo`
leaves `details.missing`; the bullet above that defines a photo stands for the completeness count
and for the badge. The formula stays exactly as written: 50 for meeting the requirements, 10 for
each approved public photo after the first. So zero photos is 50, the same as one, and such a
profile sits at the bottom of discovery's ranking (D-032): chosen, not overlooked. The trigger
`users_done_needs_a_match` is unchanged. Built by T-4.12.

### D-330 · The E2E runs the whole stack: the local S3, the worker, the real face match, a fake camera — Open
**The decision (T-4.9), extending D-084, which stays as it is:** D-084 says what the E2E is (a
production build, Chromium, a P-55 slot, nothing kept). From T-4.9 its journeys reach `/discover`,
and that needs more than `make infra-up` gave them:
- **Storage is the local S3** (D-086), as `make dev`'s is, with `STORAGE_PROVIDER=s3` in
  `api/tests/e2e_server.py`: the browser uploads photos and a selfie by presigned PUT, which the
  fake's `fake-storage://` links can't take. The private bucket admits the E2E's origin,
  `http://127.0.0.1:3100`, by a CORS rule of its own beside `make dev`'s
  (`infra/s3/private-cors.xml`, held by `api/tests/test_local_s3_cors.py`), PUT and Content-Type
  only. CI's `e2e` job starts the S3 and runs `s3-init`, as the `api` job does. The buckets are
  shared with every pytest run and `make dev`; each key carries its user's id.
- **The worker runs beside the API,** a child of the launcher on the same slot, its settings in its
  environment and never from `api/.env` (a working directory outside `api/`): photo moderation and
  the selfie's comparison are its jobs, and without it no photo is approved, so T-4.8's completion
  refuses everyone. It stops when the API does, from the signal handler uvicorn puts back.
- **It polls every 0.5 seconds, not D-091's 10.** D-091's interval is Upstash's per-command price on
  the deployed Redis; the E2E's Redis is Docker's, where a command costs nothing, and at 10 seconds
  every run would wait that long on each photo for no benefit. D-091 is not changed: this is the
  worker's own setting, set for this run alone, and the deployed worker keeps 10.
- **Moderation is the fake** (Sightengine has no local stand-in; the fake approves), **and the face
  match is the real one** (`sface`, D-088): J2's "your selfie matches your photos" is the models'
  own verdict on what the browser sent. With the fake every selfie matches, so that line would be
  true whatever the browser sent, and a test that can't fail proves nothing. The launcher refuses
  to start without the models (`make models`; CI's `e2e` job fetches them, cached, as the `api`
  job does).
- **The camera is Chromium's fake one** (`--use-fake-device-for-media-stream`,
  `--use-file-for-fake-video-capture`), playing NASA's 2017 portrait of Raja Chari from
  `api/tests/fixtures/faces`, copied at load as a one-frame MJPEG; J2's profile photo is his 2021
  portrait. Nothing new is committed. The journeys run on the full Chromium in its new headless
  mode (`channel: "chromium"`), because Playwright's headless shell has no media capture
  (`getUserMedia` there: "NotSupportedError: Not supported", 5 October 2026). Firefox's by-hand
  run skips J2.

**Why:** the E2E's purpose is the chain as a person meets it, and the two places it could have
been faked, storage and the match, are the two where a fake passes whatever the browser does.
Without this entry a reader of D-084 (Locked, and not edited) would take `make infra-up` for
enough.

**Rejected:** the fake face match (above); the worker's 10-second poll in the E2E (a minute added to
every run for nothing); a third Playwright `webServer` for the worker (it can't know the slot the
launcher took); committing a camera video (a copy of a committed JPEG, remade in a second).

Proposed by Claude in T-4.9's plan, 5 October 2026. Its three questions, the real models, the
0.5-second poll with its reason written down, and this entry, were answered by the advisor
directing T-4.9 (Claude, in a separate chat), relayed by the founder, 5 October 2026; the founder
confirmed whose words they were the same day. **Open** until the founder approves it in his own
words.

### D-380 · Liveness waits until after launch: six decisions on T-4.11's research — Open
**The decisions (the founder, 7 October 2026),** on six questions the advisor (Claude, in a
separate chat) put to him from Claude's T-4.11 research report of 5 October 2026, and taken on the
advisor's advice:
1. **T-4.11 is for a print, a screen or a replay held in front of the camera.** A selfie that
   already exists, uploaded as a file, isn't its to stop: that needs a freshness mechanism, which
   is a separate decision. The pose challenge stays rejected (the founder, 4 October 2026); the
   research didn't evaluate it.
2. **Passive liveness is not D-008's "liveness verification".**
3. **The measurement set (30 consenting people, 1,350 captures) isn't now:** after launch
   (P-280).
4. **MiniFASNet's training-data flag goes onto P-0.7 beside SFace's, never softened.**
5. **DAMO's model-card tag is not a licence.**
6. **Both Proposed tasks are filed:** P-280, the measurement set; P-281, the worker held to one
   image at a time by a check, not a comment.

**What changes with them:** D-008 is amended (the selfie and its face match mandatory, liveness
after launch), and so is D-260 (passive liveness doesn't stop its attack either). T-4.11 leaves
REL-1's tag and T-9.15's Needs line; its research half is ticked, its accuracy half open on P-280.

**What they rest on** (T-4.11's research, Claude, 5 October 2026: T-4.11's line has it in full,
and `api/bench/liveness/` re-runs its numbers, D-381):
- **Passive single-photo liveness doesn't stop D-260's attack** (D-260's amendment says how). A
  NASA portrait, never in front of our camera, scored 0.8949 "real" through the real pipeline: one
  image, not a rate.
- **Retries:** an attacker gets 5 tries a day (D-263); at 1% a try he passes within a week 29.7%
  of the time. Passive liveness slows a stubborn attacker; it doesn't stop him.
- **MiniFASNet** (minivision, Apache-2.0) costs single-digit MB more at peak through OpenCV's DNN
  (409 to 410 MB, mostly 410, against a baseline of 392 to 406, mostly 403 to 404), with no new
  dependency, and its weights are verified; DAMO's two models carry a model card's tag and no
  licence text. **The probe's baseline varies 392 to 406 MB run to run with no code change, so a
  difference under about 15 MB between two routes is not something this probe can tell apart.
  MiniFASNet's +6 MB is inside that; the decision rests on single-digit MB against about 400, not
  on the 6.**
- **Sightengine's** liveness is on its Pro plan, $99 a month, which the founder declined on 4
  October 2026 (about ₹1 lakh a year), and it judges a single photo too.
- **What a measurement can show:** 30 people, none breached, bounds the rate at 9.5% (95%), no
  lower. "Nobody can be impersonated" can't be shown at that size.

**The founder's reason, in his words** (written by the advisor and approved by the founder, 7
October 2026, as the brief relayed them): "Liveness ka kaam fake rokna hai. Maine 7 October 2026
ko tay kiya ki fake account ban sakte hain — ek aurat apni asli photo dikhane ko majboor nahi. Aur
research ne naapa ki passive liveness upload wala attack rokta hi nahi. To ₹1 lakh saal
(Sightengine Pro) ya 30 logon ka measurement set, dono us chhed ke liye hain jo main pehle hi khula
chhod chuka hoon. Liveness launch ke baad, asli users ke saath." In English: "Liveness exists to
stop fakes. On 7 October 2026 I decided that fake accounts can be made: a woman isn't forced to
show her real photo. And the research measured that passive liveness doesn't stop the upload
attack at all. So ₹1 lakh a year (Sightengine Pro) and a 30-person measurement set are both for a
hole I have already left open. Liveness after launch, with real users."

**The reason quotes a decision this entry doesn't record:** that fake accounts can be made and a
woman isn't forced to show her real photo (the founder, 7 October 2026). It isn't on `main`; the
next session files it, from its own block (P-290 to P-299). It meets two things already built,
T-4.5's match against her approved public photos and D-101's `no_face`; working that out is the
filing session's. **Filed, 7 October 2026: D-390 to D-393, built by T-4.12.**

**Rejected:** Sightengine Pro (the founder, 4 October 2026: about ₹8,300 a month before the
product has a single paying user; and it judges a single photo, the same blind spot); DAMO's
models (decision 5).

**Open:** the reason's words are the advisor's, approved by the founder. The founder can Lock this
entry with one line saying they are his.

### D-381 · torch and onnxruntime: the liveness bench's, and nowhere else — Open
**The decision (the founder, 7 October 2026, under rule 4), with three conditions:** T-4.11's
probe (`api/bench/liveness/`) needs torch (2.14.1, CPU-only, from PyTorch's own index) and
onnxruntime (1.30.0) for two of its routes and for its weights check, since minivision's own
`.pth` files run only through torch. Approved on these conditions:
1. **They are installed in `api/bench/liveness/Dockerfile` and nowhere else:** never in
   `uv.lock`, never in the API image.
2. **A check holds it, because "never" is a claim** (the founder's condition).
   `tests/bench/liveness/test_bench_only.py` reads `uv.lock` (neither, nor a variant of either's
   name), the API's Dockerfile (its RUN lines exactly the four it has, the only installs the
   lock's, and neither named anywhere) and `api/.dockerignore` (`bench` kept out); each guard was
   broken on 7 October 2026 and went red (`python -m tests.break_guards t411-`, cases 01 to 04).
   CI's `scripts/check-image-no-bench-tools` looks inside the built image with the image's own
   Python.
3. **A `.pth` file is a pickle, which can run code as it loads, so it is never in production.** The
   probe loads one only with `weights_only=True`, which refuses anything but tensors.

**Not `uv.lock`'s dev group** (Claude's reasoning): that would install about 150 MB of torch into
every developer's and CI's environment for a probe run by hand, and the lock is what the image is
built from.

**Open:** the conditions are the founder's, relayed in the brief of 7 October 2026. The founder can
Lock this entry with one line saying so.

### D-390 · Gender isn't verified, and that is deliberate — Open
**The decision (the founder, 7 October 2026; written by the advisor, Claude in a separate chat,
relayed by the founder):** nothing checks that someone who chose "Woman" at sign-up is a woman:
no model, no person. A man can choose "Woman", upload his own photos and his own face photo, take
his own selfie, and the selfie matches, since it is his face; the match is genuine and the badge
follows (D-393). The founder accepts this for now. **No gender check is built.** What stands
against it at beta is D-264's human review: the founder looks at every decision.

**What the vendor has, so nobody assumes a model would fix this** (read by Claude, 7 October
2026): the three Sightengine models the worker calls (`nudity-2.1`, `face-age`, `text`; D-101)
returned no gender field in the shape T-4.4 recorded on 4 October 2026 (D-094), and Sightengine's
current Face Analysis page names no gender attribute. Its deprecated `face-attributes` model once
offered one: a search result that day named female and male probabilities, while the page itself,
read the same day, names only `minor` and `sunglasses`. None of that decides anything: the
decision is that no gender check is built, whether or not a vendor sells one.

**Why, in the founder's words** (D-380's quote, approved by him): "ek aurat apni asli photo
dikhane ko majboor nahi", a woman isn't forced to show her real photo. The same decision that lets
a woman show no face (D-392) means nothing in the product can tell her from a man who says he is
one; this entry says so plainly so the two are read together.

**What follows:** docs/09-RESEARCH.md's C2 "fake profiles" row leaves "Closed by design", where it
never belonged: the face match compares a face with a face, not a gender. D-380's reason quotes
this decision, and its "the next session files it" paragraph now points here.

**Rejected:** a gender check of any kind, by a model or by a person (the founder, 7 October 2026).

**Open:** the decision is the founder's; the words are the advisor's. The founder can Lock this
entry with one line saying so.

### D-391 · A face photo for the selfie check, private unless she chooses; the selfie is compared with it alone — Open
**The decision (the founder, 7 October 2026; written by the advisor, Claude in a separate chat,
relayed by the founder):**
- **One photo whose only job is the selfie check.** `PhotoKind` gains `verification`, an
  identifier like `is_verified`; in copy the photo is never called that, since
  `web/src/i18n/claims.test.ts` refuses `/verif/i` ("face photo", the advisor's recommendation;
  T-4.12 chooses). It must show a face: D-101's `no_face` applies to it, and so do D-101's other
  three checks, since she may choose to show it.
- **Private by default.** It lives in the private bucket, has no public copy, is listed to its
  owner alone (`GET /me/photos`, `GET /photos/{id}`) and appears in nobody else's response, as a
  selfie doesn't (06-TESTING #14). **She chooses whether it also shows on her profile,** a toggle
  on the photos step; its mechanism is T-4.12's plan's (Claude recommends a separate `public` row
  from the same scored bytes, so every reader of "public photo" stays as it is).
- **The selfie is compared with it alone,** never with the public photos: `verify_selfie` reads
  the face photo where it read `approved_public_photos`, and `no_photos` comes to mean "no face
  photo yet". The public photos' own comparison with the selfie is D-393's, for the badge, a
  different purpose.
- **Where and how many:** uploaded at the `photos` step or after (D-068), in a slot of its own;
  one live per person, as the selfie, a new one replacing an unsent old one. Replacing it after a
  match is T-4.12's plan's (Claude recommends refusing while a verification is approved, as a
  selfie's removal is refused; a change then goes through P-163's path).
- **Men may add one;** it is needed only if a man takes the optional selfie (D-008).
- **An under-18 refusal takes it** with the rest (D-078, P-54): it is a photo row, so
  `UNDERAGE_FILES` already reads its key; a test says so, as T-4.5's did for the selfie.
- **`/privacy` says it:** a photo of her face is kept for the check and never shown unless she
  chooses, and why: so the photos others see need not show her face (D-392). The selfie line and
  "where your data is" say the face photo where they say "the photos on your profile" today.

**Why:** today the selfie is compared with her approved public photos, so a woman must show her
face to strangers to be on the app at all. The founder's decision is that she needn't (D-390's
quote). A face photo nobody sees keeps a face to compare the selfie with, and keeps D-008: she
still doesn't go live until her selfie has matched.

**Rejected:** comparing the selfie with the public photos (today's shape, which forces a face
onto the profile); a face photo that is always public; a face photo without the `no_face` check,
which would leave the selfie's `no_photos` to catch a faceless one, after the fact.

**Open:** the decision is the founder's; the words are the advisor's and Claude's. The founder can
Lock this entry with one line saying so.

**8 October 2026:** the toggle's mechanism, the face photo's name in copy and its replacement after
a match are decided in D-400; this entry changes nowhere else.

### D-392 · Public photos need no face; nobody needs a public photo; completeness unchanged; the card with no photo — Open
**The decision (the founder, 7 October 2026; written by the advisor, Claude in a separate chat,
relayed by the founder):**
- **A public photo may show anything D-101's other three checks allow.** Hair over the face, a
  mask, a crop, a photo from behind, an emoji over the face: all pass. `no_face` leaves public
  photos (D-101 amended) and applies to the face photo and the selfie only.
- **Zero public photos may finish onboarding, for everyone.** `photo` leaves what `done` needs
  (D-310 amended) and T-4.3's "one public photo, pending or approved" leaves the photos step; the
  last public photo may be removed past the step. **Men too** (the founder, 7 October 2026): one
  rule is simpler than one per gender, and a man with no photo gets no likes, which corrects
  itself.
- **Completeness is unchanged** (D-310's formula): 50 at zero photos, the same as at one, so a
  profile that shows nothing sits at the bottom of discovery's ranking (D-032). Deliberate, not an
  oversight. The ranking's `is_verified` term is P-290's question.
- **The card:** a photo shows as it is, whatever it shows; with none, a grey silhouette with the
  name (T-6.2's `Card`, its main photo URL null). The `Avatar` primitive's initial-on-gradient
  fallback (08-DESIGN §4) is another fallback for another place; whether the two align is the
  design pass's (P-57).

**The trade-off, weighed, and written here so a later reader knows the cost was seen and not
missed** (the founder, 7 October 2026): on a dating app a card with no face gets far fewer swipes.
The woman this change is for may arrive, show nothing, receive nothing, and conclude the app
doesn't work. The founder weighed that and chose to let her in rather than stop her at the door.

**Rejected:** a rule by gender (women may show no photo, men must); a face photo counted toward
completeness; a profile hidden from discovery at zero photos (it would make "let her in" a door
that opens onto nothing); `no_face` kept for public photos with an exemption she asks for.

**Open:** the decision is the founder's; the words are the advisor's and Claude's. The founder can
Lock this entry with one line saying so.

**8 October 2026:** who may leave the photos step without a face photo, and the step's exit, are
decided in D-400; this entry changes nowhere else.

### D-393 · The badge: the selfie matched the face photo, and a shown face matched the selfie; a red tick — Locked
**The decision, in the founder's words, 7 October 2026:** "agar ladki photo nahi daal rahi to usko
verified mat dikhao; jiska ho jaye usko red tick badge de do." In English: if a woman isn't putting
up a photo, don't show her as verified; whoever's matches, give them the red tick badge. It is
option (b) of the filing's first question (P-161 made wider: the redesign had turned "a photo
added after the check" into every public photo, since the selfie is compared with the face photo
alone, D-391). The rule:
1. **The badge shows when `is_verified` is true** (the selfie matched the face photo, D-391) **and
   at least one approved public photo's face matched the selfie.**
2. **Each approved public photo with a face** (`photos.moderation.faces >= 1`, which T-4.4 already
   records for every moderated photo) **is compared with the kept selfie:** when it is approved,
   if a selfie has been decided; when the selfie is decided, for the photos already there. The
   result goes in that photo's `moderation` record, as the selfie's numbers go in its own (D-263).
   One comparison at a time, on the worker (P-281).
3. **A public photo that doesn't match isn't rejected; it doesn't count toward the badge**
   (Claude's recommendation, taken by the founder). Her photo from behind, in sunglasses or with a
   friend stays on her profile.
4. **No shown face, no badge:** zero public photos, or public photos with no face, means no badge,
   verification or not.
5. **The same rule for men;** their selfie stays optional (D-008).
6. **`/privacy`'s "we compare your selfie with the photos on your profile" stays true,** and the
   face photo joins it (D-391).
7. **The icon is a tick in `--accent`.** The founder chose a tick on 7 October 2026, knowing a tick
   reads as "verified" where the words may not say it (D-262). The words still never say it: the
   badge's label and aria-label are "Selfie matched" (today's "Selfie matches photos" is also true
   under this rule; T-4.12 keeps one, neither claiming more), and `claims.test.ts` holds them.
   08-DESIGN's item 14 and D-262 carry the amendment; a shield stays rejected.

**Why (b) and not a badge whose words shrink** (the filing's other option; Claude's reasoning, 7
October 2026): under (a) the badge would mean "a selfie matched a photo you can't see", which a
viewer can do nothing with, and the founder's own condition, no badge without a shown face, would
do no work for honesty, since that face was never compared. Under (b) the badge is literally true
where it shows, and T-6.9's "verified only" filter filters on something a viewer can see.

**What it costs, so the next reader knows:** D-260's unmeasured threshold is now applied to every
face on a profile, not one, so real women's side-on or sunglasses photos may not count and the
badge hides though the selfie matched; D-264's review grows by those comparisons, and its `mixed`
flag (P-162) keeps its meaning on the badge's side; the worker does one SFace comparison per face
photo, about 400 MB at peak (T-4.5's measurement on Fly), one at a time. The selfie is read again
later, privately, which `/privacy` already covers ("we compare your selfie with the photos on your
profile").

**Rejected:** (a), the badge's words shrunk to what one hidden comparison shows (above); clearing
`is_verified` when a public photo doesn't match (P-161's other option: a cleared badge on a live
woman's profile is P-163's path, never an automatic one); the badge on `is_verified` alone (the
founder's words).

**Locked** on the founder's words, 7 October 2026. The rule's seven parts and the icon are his; the
reasoning paragraphs are Claude's and the advisor's, relayed. Built by T-4.12.

### D-450 · No GST until the threshold: inclusive prices, receipts silent on it, unspent Velas a liability — Open
**The decision (the founder, Shubham Kumar, 8 October 2026, after a phone call with a chartered
accountant; written by the advisor, Claude in a separate chat, relayed by the founder):**
1. **No GST registration now.** Services have a threshold of ₹20 lakh aggregate turnover in a
   financial year, Section 22 of the CGST Act as the CA put it. It is the law's number, not the
   founder's preference. Until Velora crosses it, Velora is unregistered and collects no GST from
   anyone. P-350 is the registration, within 30 days of the crossing.
2. **Prices are GST-inclusive.** A user always pays the pack's price, ₹1,500 for the entry pack
   (D-099). Registration doesn't change it: Velora's share becomes ₹1,271 and ₹229 is tax (18%,
   digital services). The exact paise split is the registration task's (P-350).
3. **Unregistered, no receipt or invoice mentions GST:** not "incl. GST", not a rate, not a GSTIN.
   The total alone. Showing or collecting GST without a GSTIN is against the law, as the founder
   relayed it from the CA; T-8.1 holds it with a test that the word appears nowhere.
4. **Unspent paid Velas are a liability** (deferred revenue), revenue when spent. An accounting
   rule, separate from GST; P-0.17's first point was right as written.
5. **The voucher-timing question**, whether GST falls due when Velas are sold or when they are
   spent, is asked of the CA on registration day (P-350), not before. While unregistered it does
   not arise.

**Why:** the one question P-0.17 couldn't answer without a CA, now answered by one. Below the
threshold a registration would have Velora collect and remit a tax the law doesn't ask of it, at
18% of every sale or a price rise at launch; above it, not registering accrues penalty and interest
from the first day over. The inclusive price keeps the store's numbers (D-099) true on either side
of the threshold. Point 3 follows from point 1: a receipt can't name a tax Velora has no number to
collect under.

**What is built, and where:** T-8.1 carries `gst_paise` (0 until registered), a `gst_rate_bps`
config (1800 once registered), a receipt that shows the total alone while unregistered, with a
test that "GST" appears nowhere, and the aggregate turnover counter with its ₹15 lakh alert, the
only thing that can tell anyone the threshold is near. P-350 registers, asks the timing question,
flips `GST_REGISTERED` and files the timing rule as a decision of its own.

**Not decided here, and a question for the CA before the first sale, not a reading of the law
(Claude, 8 October 2026):** whether the ₹20 lakh threshold holds as stated when the business sits
in Bihar (D-058) and its users are across India, an inter-state supply of services. Neither Claude
nor the advisor has read the GST Act, and this entry makes no claim about it; the founder puts the
question to the CA when the name is recorded, and the answer goes here.

**Rejected (the alternative each point closes):** registering voluntarily now, tax on every sale
below a threshold that doesn't ask for it; GST-exclusive prices, where registration would raise
the user's price by 18% (the founder: the user pays ₹1,500, always); "incl. GST" on an
unregistered receipt as a courtesy, unlawful without a GSTIN; asking the timing question now, for
a registration that may be a year off (the CA: it doesn't arise until then).

**Open:** the decision is the founder's and the figures the CA's; the words are the advisor's,
relayed. **Lock** when the CA's name is recorded here and on P-0.17.

### D-410 · CI minutes: `main`'s run vouches from the branch run, e2e only off the docs allowlist, no cancel on `main` — Open
**The decision (P-282; the founder, 8 October 2026, on the advisor's recommendation, Claude in a
separate chat, relayed):** three cuts to what a landing costs in GitHub Actions minutes, each
shaped so that `deploy.yml`, `scripts/ci-gate`, `scripts/release-gate` and `scripts/push-gate` go
on reading exactly what they read today: a completed, green run of the CI workflow for the exact
SHA, on the branch they ask about. None of the four changed.

1. **On `main`, the run vouches.** A first job, `vouch`, runs only on a push to `main` and asks
   GitHub (`scripts/ci-vouch`) for a completed, passed push run of the CI workflow for exactly
   this SHA on a branch other than `main`, re-checking SHA, workflow, event, branch and
   conclusion in jq (P-140). Landing is a fast-forward to a commit whose branch run the gate
   read (D-044), so `main`'s full run repeated 17 minutes for nothing. When one exists the other
   jobs are skipped, and a run of one green job and skipped jobs concludes `success`, so the
   staging deploy fires on it and the gates read it as passed. Anything the script can't be
   sure of is "false": no run, a red, cancelled or unfinished one, another workflow or event,
   GitHub not answering, the script itself crashing. False runs the full CI on `main`, which is
   what a manual-path landing (`/done`, GitHub unreachable) gets, since no branch run vouches
   for it. A run started by hand on `main` never vouches, so it stays the way to run everything
   there.
2. **`main`'s runs are never cancelled.** `cancel-in-progress` is
   `github.ref != 'refs/heads/main'`, the form GitHub's own docs give: a second push to a task
   branch still supersedes the first's run, and `ci-gate` still reads a cancelled run as not
   green; a second landing no longer cancels the first's run, which left the first commit with
   no green run and so no deploy. `main`'s runs queue, first in, first out. GitHub keeps one
   pending run per concurrency group, so a third landing inside the window replaces the
   second's pending run; with `main`'s run at about a minute that needs three landings in a
   minute. GitHub's `queue: max` would hold up to a hundred, but can't combine with a true
   `cancel-in-progress`, and whether it takes an expression is untested: the fix if that is ever
   seen, not used now.
3. **The journeys run only when a changed path could reach one.** `scripts/ci-e2e-needed`, a
   step at the top of the `api` job, which has the full history for gitleaks and which `e2e`
   needs anyway, so the decision costs no billed minute of its own. The allowlist names what
   can't reach a journey, never what counts as code (CLAUDE.md rule 16): `docs/`, any `.md`
   file, `.claude/`. Anything else runs them, the workflow and these scripts included. A
   skipped `e2e` leaves the run's conclusion `success`, as the gates expect, so a required
   status check (P-180) must never name `e2e`. **What it measures from:** on `main`, the push's
   previous tip (`before`), right because `main` only moves by fast-forward; zeros, no SHA (a
   dispatch) or one the clone doesn't have all run the journeys. On a branch, the merge base
   with `main`, never the push's `before`: a code push whose run a quick docs push cancelled
   would otherwise leave the branch tip with no e2e run on its tree, since the second push's
   diff is docs only. The merge base sees everything the branch adds over `main`, so every tree
   that reaches `main` is an e2e-tested tree or allowlisted paths away from one. **A trap the
   first proof run found (37684502234, 8 October 2026):** GitHub carries a skip down the whole
   needs chain, so `vouch`, skipped on every branch, skipped `e2e` too, however green `api` and
   `web` were and with `e2e=true` printed, because `e2e`'s condition had no status function.
   Every job downstream of `vouch` therefore opts out with `!cancelled()` and names the results
   it needs itself.

**Why:** on 7 October 2026 GitHub Free's 2,000 Actions minutes a month ran out mid-week. GitHub
then refuses to start a job and closes a green run as "failure" (P-282 names the runs), the gate
reads exit 1 as it must, and every session is blocked at once with nothing to fix on any branch.
Measured on that day's ten CI runs, each job rounded up to the minute as GitHub bills: 189
minutes for five landings, every one docs-only, 36 to 38 a landing; with the three cuts, 71, 14
to 15 a landing. What each cut was seen to do, run by run, is on P-282's tick.

**Rejected:** skipping `api` and `web` on docs-only commits too (another 11 minutes): a separate
question with couplings of its own, and `repo`, whose pre-commit pass reads every file, runs
either way. Not running `main`'s workflow at all (`paths-ignore`, or no trigger on `main`): the
deploy fires on `workflow_run` of CI on `main` and both gates read `main`'s run, so it must
complete, green, for the SHA. A required status check in place of the vouch: GitHub refuses them
on this plan (D-280, P-180). The push's `before` on a branch: the cancel hole above. A job of its
own for the e2e decision: a billed minute on every run, which is what the cut saves. Open until
the first week of landings shows the deploys firing as before.

### D-400 · T-4.12's four answers: the toggle's row, the photos step's allowlist and exit, "face photo", no change after a match — Locked
**The decision (the founder, 8 October 2026, each answer on the advisor's recommendation, Claude in
a separate chat, relayed by the founder; the four points T-4.12's plan left open, D-391, D-392):**
1. **The toggle is a separate public row.** "Also show it on my profile" makes an ordinary public
   photo from the face photo (`POST /photos/{id}/show`), in the first free place, carrying
   `from_photo_id` in its record; every reader of "public photo" (discovery, completeness, T-6.3,
   the badge's comparison) stays as it is, and turning it off is `DELETE /photos/{copy}`,
   `user_deleted`, as for any photo. Rejected: giving the face row itself a place and a public
   copy, which touches every one of those readers and makes "private unless she chooses" a status
   rather than a fact about the row.
2. **A woman can't leave the photos step without a face photo, pending or approved**, by an
   allowlist: `MAY_LEAVE_PHOTOS_WITHOUT_A_FACE_PHOTO = {male}`, the same shape as D-310's
   `MAY_FINISH_UNMATCHED`, so no gender is refused too. Pending counts, as a pending public photo
   did under T-4.3: moderation takes seconds, and a `no_face` refusal sends her back from the
   selfie step's `no_photos`. The step has an exit of its own, since a man may leave with nothing
   uploaded at all: `POST /me/photos/done` → `Me`, beside `/me/photos/order` and after
   `/me/pin/skip`'s pattern, a step's own exit under `/me/<step>` (the founder's suggestion, taken
   by Claude; the plan had proposed `/me/onboarding/photos/done`). The refusal is
   `FACE_PHOTO_REQUIRED` (403). No database trigger: a woman who slipped past is stopped at the
   selfie by `no_photos` anyway, so the stake doesn't justify one (unlike D-310's `done`).
3. **"face photo" in copy, everywhere.** It says what it is and claims nothing (D-262);
   "selfie-check photo" reads as a claim about checking. The identifier stays `verification`
   (`PhotoKind`), never in copy; `claims.test.ts` refuses `/verif/i` and a web breaking run
   (`t412-copy-02`) proves it goes red on "verification photo".
4. **The face photo can't change once the selfie matched, nor while one is being compared.** The
   match would be left pointing at a photo that is gone; a change after a match is P-163's path.
   Before either, a new face photo replaces the old (`replaced`, its file deleted after the
   commit), one live per person, as a selfie never sent is replaced (D-263). Both `POST
   /photos/upload-url` and `DELETE /photos/{id}` refuse with `NOT_ALLOWED`.

**The five questions of the plan, answered the same day by the founder:** the badge's label and
aria-label are "Selfie matched", D-393 item 7's words, for both genders (the canvas's "her photos"
was wrong under rule 5 and the design canvas now says "Selfie matched" too); the seed sets the
badge's record on the 15 seeded verified profiles' public photos on the seed's word (`decided_by:
seed`, no number, no face claimed), so the badge shows on their cards in dev; this entry, one for
the four answers; the names stay (`from_photo_id`, `FACE_PHOTO_REQUIRED`, `/photos/{id}/show`),
the exit renamed as above; P-300 filed.

**What the build changed from the plan, Claude's call, for the founder to confirm (8 October
2026):** the plan said the copy `show` makes is "approved at once from the face photo's scored
bytes". Built, it is **pending, and goes through moderation like any upload.** Why: a presigned
PUT URL outlives `complete` by up to five minutes (P-79), so the face photo's private copy may not
be the bytes moderation scored, and T-4.4's rule is that a public copy is only ever made from
scored bytes. The copy therefore carries the face photo's `from_photo_id`, is scored and published
from what was scored, and on approval `_record` queues `match_photo` for it with a selfie kept,
exactly as for any approved public photo with a face: the gap the founder named (a woman whose only
shown face is that copy) closes by the same path, with no special case in the badge query. Cost:
one more Sightengine call per toggle-on, and "checking" for a few seconds instead of at once.
The same five-minute window is why P-301 is filed for private photos.

**Why:** D-391 and D-392 left these four to the build; each was decided as recommended, and the
reasons are above beside each.

**Rejected:** see each point.

**Locked** on the founder's words, 8 October 2026, on the advisor's recommendation (Claude, in a
separate chat), relayed by the founder: the four answers above; and the three things the build
asked him to confirm, all three confirmed: `show`'s copy is pending and moderated, the same path
as any public photo, one Sightengine call per toggle-on accepted; `replaced` reaches the owner by
name; and the race test and the worker's wake test delete the photo and verification rows they
commit. The mechanism's words are Claude's.

### D-470 · Welcome Velas: 5 for every new man at sign-up, once per number — Locked
**The decision (the founder, 8 October 2026: "5 velas free new registration pe add karo"):** every
man gets 5 Velas when he finishes sign-up. Built by T-8.11. The shape:
- **When:** at onboarding `done` (T-4.8's `onboarding.complete()`), in the transaction that moves
  him there. Never at sign-in, when his gender and date of birth aren't known yet.
- **Who:** men only, gender `male`, an allowlist the service checks before it credits. **Never a
  woman** (D-076). The database refuses her a ledger row anyway, but a service that left it to
  the database would abort her whole sign-up, so the service skips her and her sign-up completes.
- **How much:** `app_config.welcome_velas`, 5, tunable like the prices (D-005, D-098). At 0
  there is no grant and no ledger row.
- **How:** always `wallet.service.credit()`, with a new ledger reason, `welcome` (rule 5);
  `ledger_reason_t` is rebuilt both ways, as T-5.2's `4a7e20790605` did (D-251). Never a default
  balance on `wallets` (rules 5 and 6).
- **Once per phone number, ever** (the founder, 8 October 2026, answering P-371). Once per account
  by the ledger, and a hash of every number that received a grant is kept, as D-072 keeps one,
  and survives T-9.6's anonymisation: a later account on that number gets no grant. D-051's kept
  hash gains this reason, and `/privacy` says so (T-8.11).

**The ledger's shape for `welcome`** (Claude's, by D-077's rules): a credit; `ref_type` `user`,
naming the man himself; his id is the event, so the key is `{user_id}:welcome:{user_id}`; inside
the one-per-event index, so one account never holds two, however the key is built. The ledger
can't see a second account, which is a new `user_id`: the number's hash is what stops that.

**What 5 Velas are.** One Thread (D-098), ₹250 at the entry pack (D-099), or five "liked you"
reveals at 1 Vela each (D-098's note). They are unpaid, like the first-purchase bonus: no payment,
nothing in T-8.1's turnover counter, and not the paid Velas that D-450's point 4 calls a
liability. How unpaid Velas are counted when spent beside paid ones is a question for the CA, as
it already is for the bonus.

**The worst case, accepted (P-371):** a fresh number is a fresh account, and each gets its 5: one
free Thread with a woman per number, a first message that paid Velas otherwise stand in front of
(09-RESEARCH's R1: "it is what keeps the inbox clean for women"). Nothing here stops it. D-072's
hash is written only when a date of birth is refused, and `users.phone_hash` is unique per
number, not per person. Velas can't move between accounts (D-076), so a man with many numbers
holds many single Threads, never one large balance. The founder chose this knowing it.

**Under-18 (D-078).** The grant is at `done`, and `dob` is onboarding's first step (D-068), so a
date refused as under-18 is refused before any grant could happen: no under-18 account holds a
`welcome` row, and D-078's premise, that a user at the dob step has no ledger row, holds. If a bug
ever wrote one, D-078's deletion fails whole, a 500, as it says, and the row is kept (rule 12).

**R1 and T-10.7.** 5 Velas is one Thread, so this is R1's candidate fix, "the first thread free,
once per account", given to every new man as Velas he spends as he chooses. T-10.7 now tests this
grant, not a free Thread.

**Rejected:**
- **A default balance of 5 on `wallets`:** no ledger row behind it (rule 5), and a wallet exists
  from sign-in, a woman's too, where D-076's trigger refuses a balance anyway.
- **A grant at sign-in:** before the gender is set, when the database refuses any credit, and
  before the date of birth, when an under-18 account could come to hold a ledger row.
- **Once per account only:** a man could delete his account, wait out T-9.6's 30 days and sign up
  again for another 5 (P-371, closed by the founder).
- **Women:** never (D-076).

The grant is the founder's decision, 8 October 2026, in the words above. Its shape is the
advisor's (Claude, in a separate chat), relayed by the founder; the ledger's shape is Claude's.
P-371's answers are the founder's, on the advisor's recommendation, relayed the same day.

**Built 8 October 2026 (T-8.11).** `onboarding.complete()` grants it as the step moves to `done`:
the number claimed in `welcome_grants` (`INSERT ... ON CONFLICT DO NOTHING`, one statement), then
`wallet.credit(welcome)`, in one transaction under the user's row lock. Migrations acfda05a9f20
(the reason), a7e4f06d6b3f (its shape), 39e51f5fb85a (`welcome_grants`, append-only, its
downgrade refused while it holds a row) and 105ae9a99be1 (`welcome_velas`). What happens when
the setting is missing, the backfill and the line a new man sees: D-530.

### D-480 · Variant B is shown A's packs until T-10.4; no man ever gets an empty store — Locked
**The decision (the founder, 8 October 2026, on the advisor's recommendation, Claude in a separate
chat, relayed by the founder):** a man is still put in price-test variant A or B by a hash of his
id, stable for as long as he exists (`payments/rules.py`, `variant_of`: SHA-256 of a salt and the
id's bytes). Since T-5.2 retired `entry-25`, B has no active pack (D-250), so an allowlist,
`SHOWN_AS = {"B": "A"}`, shows B the A packs until T-10.4 proposes a new test. A variant shows its
own packs unless it is named there. **If a man's store would be empty**, because every pack it
shows is inactive, `GET /packs` is a 500 and an error line (`payments.store_empty`, naming the
variant), never an empty list: an empty store looks like a working page with nothing to buy, and
nobody would hear of it. An order can name only a pack in the man's own store; any other, retired
or another variant's, is `NOT_FOUND`.

**Why:** the store is where money comes in, and B's men would otherwise find nothing to buy (the
worst case on T-8.1's box). Keeping the hash costs nothing and is what T-10.4 will need; showing B
the A packs means every man sees D-099's ladder today. This settles P-23: B sees four packs.

**Rejected:** dropping the hash until T-10.4 (option (b), the same store for everyone, but T-10.4
would rebuild the split); putting `entry-25` back for B (D-250 retired it below the ladder); an
empty list for a store with no packs.

### D-481 · An order's `Idempotency-Key` lives on its `payments` row, unique per man — Locked
**The decision (T-8.1, Claude's shape in the plan the founder approved, 8 October 2026):**
`payments.idempotency_key`, NOT NULL, with `uq_payments_user_id_idempotency_key` on `(user_id,
idempotency_key)`. `POST /payments/orders` requires the header, 8 to 64 letters, digits, `-` or
`_` (a UUID fits). The same key again returns the same order, as it was made, however much later;
the same key for another pack is `409 ALREADY_EXISTS`, since returning the first order would hide
the client's bug (D-077's reasoning). Two men may send the same key: it is the client's, unique per
man only. **Under a race** the gateway's order is created outside any transaction, so two requests
with one key may each create one; the insert is `ON CONFLICT` on the key, so only one row is
written, and the loser answers with the winner's order. The loser's gateway order is never handed
out, so it can't be paid. The test forces that interleaving rather than hoping for it.

**Why:** a retried click must never become a second order the man could pay. Postgres holds the
guarantee permanently; a Redis store expires and can be flushed (02-ARCHITECTURE §3).

**Rejected:** a Redis replay store (it isn't the guarantee, and none is needed beside the row);
returning the first order for a key reused with another pack; a unique key across all men.

### D-482 · GST while unregistered: `gst_paise` 0, no GST anywhere a user looks, registering refused until P-350 — Locked
**The decision (the founder, 8 October 2026, on the advisor's recommendation, relayed; the shape
Claude's, in T-8.1's plan), D-450's points 1 to 3 built:**
- `payments.gst_paise`, 0 for every payment while unregistered, with a check holding it inside
  `amount_paise` (`ck_payments_gst_within_amount`): registration splits the inclusive price and
  never adds to it (D-099).
- `GST_REGISTERED`, an environment setting, false. **The API refuses to start with it true**,
  naming P-350: the split and its rounding, and the receipt's GST line, rate and GSTIN, are that
  task's, and the flag alone would change nothing and look as if it had. `payments.rules.gst_paise`
  refuses a registered split too, the second lock.
- `app_config.gst_rate_bps`, 1800, seeded now and read by nothing until P-350.
- **No response a user is shown carries GST:** not a field, not a word. Today that is the order's
  response and `GET /packs`; a test reads both, as delivered, for the letters "gst" in any case.
  `GET /payments/{id}` (T-8.2), T-8.7's copy and T-5.5's history take the same rule.

**Why:** D-450 point 3: showing or collecting GST without a GSTIN is against the law. A field
holding 0 would still put the word in front of the web, and so on a screen one day.

**Rejected:** a `gst_paise: 0` field in responses; `gst_rate_bps` as an environment setting (it
is a rate, tuned by a row, like the rest of `app_config`); accepting `GST_REGISTERED=true` and
ignoring it.

### D-483 · Aggregate turnover: paid payments in India's financial year, an admin's read, and a daily line — Locked
**The decision (T-8.1; the ₹20 lakh error line and an admin-only, audited route approved by the
founder, 8 October 2026):**
- **What counts:** the sum of `amount_paise` of `payments` with `status = 'paid'` and `paid_at` in
  the financial year. Never the ledger: turnover is money in, and bonus Velas aren't money. A
  refunded payment isn't counted.
- **The year:** 1 April to 31 March **in IST**, so 18:30 UTC on 31 March is already the next year.
- **Who reads it:** `GET /v1/admin/turnover?year=`, admin only (not a moderator: it is revenue),
  this year by default; each call writes `audit_log` (`turnover.read`).
- **The alert:** the worker's `log_turnover` cron, once a day at 03:30 UTC (09:00 IST), logs
  `payments.turnover` with the figure: info below ₹15 lakh, **warning from ₹15 lakh**, **error from
  ₹20 lakh** ("register within 30 days", P-350). Until T-9.12 it reaches Fly's logs only (P-381).

**Why:** P-350's worst case is crossing ₹20 lakh unnoticed, with penalty and interest from the
first day over. The counter is the only thing that can say the threshold is near.

**Rejected:** counting from the ledger (bonus Velas aren't turnover); the year in UTC (a sale at
11 pm IST on 31 March would land in the wrong year); a moderator's read.
### D-490 · Positions are stored on a 1 km grid, never exactly — Locked
**Decision.** `profiles.location` holds only points of a 0.01° grid (`profiles.rules.GRID_DEG`):
cells about 1.1 km north to south and 1.0 km east to west at Phagwara, a little wider in the
south. A shared position is snapped as it is written, a picked area's centroid too; the exact
point is never stored. `ck_profiles_location_on_grid` refuses anything else, so no writer, the
seed and later tasks included, can store an exact one by forgetting. Discovery's radius, the
`Card`'s `distance_km` and the ranking all read the stored point, so all three are measured
between grid points. The area a shared position takes is still found from the exact position,
before snapping (D-220 unchanged). Built by P-120's commit on T-6.2's branch, 8 October 2026:
migration `4c71a9e2b058` moved the rows already stored, and `9b4e0d2c7a15` added the CHECK.

**Why: the worst case is a stalker finding where a woman lives (P-120).** `PUT /me/location`
takes any point in India, so anyone can read her from places of their choosing. Two leaks, and
the second is the sharper: her whole-kilometre `distance_km` from three places crosses where she
is; and **whether she is in the feed at all**, the 25 km radius's edge, is a circle exact to the
metre, with `hide_distance` on or off. On grid points a move inside one cell changes nothing, so
both leaks end at her cell, about a square kilometre, never her home. The rate limit (D-220's 10
an hour) only slows the reading, and a second account starts its own hour; the fix had to be the
distance's.

**What it costs.** Two people in one cell read as 1 km apart (D-034's floor), and the dev seed's
profiles share a few points instead of sitting apart. The exact positions stored before the
migration are gone, on purpose: its downgrade can't restore them, and says so.

**Rejected:**
- **Snapping only in the query, keeping the exact point:** her home would still sit in the
  database, and the radius filter would need an index of its own on the snapped expression.
- **Distance bands ("2–5 km"):** D-034 (Locked) shows whole kilometres, and bands leave the
  radius's edge exact.

The founder's choice, 8 October 2026, of the option Claude recommended in T-6.2's plan (P-120),
on the advisor's recommendation (Claude, in a separate chat), relayed by the founder.

### D-491 · Discovery's ranking: D-032's four terms, weighted, measured at the scroll's start — Locked (values tunable)
**Decision.** T-6.2 ranks a feed by

    score = 0.40 · D + 0.30 · R + 0.15 · V + 0.15 · C

- **D, distance:** 1 / (1 + km / 5), between grid points (D-490): 1 at one point, 0.5 at 5 km,
  about 0.17 at the radius's 25 km.
- **R, recency:** 1 / (1 + hours since last active / 24): 0.5 a day ago, 0 for someone never
  active.
- **V, `is_verified`:** the selfie matched (D-032 unchanged). It stays whether or not the badge
  shows (P-290, answered by the founder 8 October 2026): ranking is not a claim, and D-262 is about
  copy.
- **C, completeness / 100:** 0.5 to 1.0 (D-310), kept current since P-210.

Each term is 0 to 1, so a score is too. The `new` feed adds 1 for anyone who joined within 7
days, which puts every new face first and ranks them among themselves as the rest are. `online`
keeps only those active within 5 minutes. Ties go by user id. The weights are constants in
`api/app/modules/discovery/rules.py`, tuned by a change there, not by data: a tuning is a
decision to record beside this one.

**The cursor carries the scroll's first instant: `(as_of, score, user_id)`.** R and `new` depend
on the time, so every unswiped card's score drifts down as minutes pass. Ranked again at each
page's own time, the card that ended page 1 would score lower when page 2 is asked for, and come
back. Measured at `as_of`, the instant the first page was ranked, a scroll is one ranking: each
card comes once. 02-ARCHITECTURE §3 says "the cursor is the last item's sort key", and the sort
key is the score at `as_of`, so `as_of` belongs in it. It is still a position, never a permission
(D-270): an edited `as_of` only ranks the caller's own feed at another instant.

**Why these weights:** distance first because Velora is "people nearby" and D-490's cells make
anything under a kilometre one point; recency next, since a match nobody answers is the thinnest
feed of all; verified and completeness as tie-breakers of real worth, at equal weight. A worked
case: someone at your own point, never active, scores 0.40 + 0.15 + 0.075 = 0.625 (a woman,
verified, at 50); someone 24 km away and active now, 0.068 + 0.30 + 0.15 + 0.075 = 0.593. Distance
wins, narrowly, as intended.

**Rejected:** ranking at each page's own time (the drift above); a stored score (it would be stale
the moment someone moves or is active).

The founder's approval, 8 October 2026, of the formula Claude proposed in T-6.2's plan, the weights
as constants in `rules.py`, on the advisor's recommendation (Claude, in a separate chat), relayed by
the founder.

### D-494 · The `Card`: its badge is `shows_badge`, its photo the lowest place — Locked
**Decision.** T-6.2's `Card` names D-393's badge `shows_badge`, the same name as the rule's query
(`verification.repository.shows_badge`, now read through `badge_of`), and never carries raw
`is_verified`, which stays the owner's, in `Me`. Its photo, `main_photo_url`, is the owner's
approved public photo at the lowest place (P-75, the founder's answer of 8 October 2026): the
server moves no photo, so with a gap in the places the lowest is still the main one, and with no
approved public photo it is null (D-392). Its other fields are T-6.2's list in the plan:
`distance_km` is whole kilometres between grid points, half rounded up, never under 1 (D-034,
D-490); `bio_line` is the first 90 characters of `about`, cut at a character, not a word, with
nothing added (the web shows an ellipsis if it wants one).

**Why `shows_badge`:** the plan left the field's name to T-6.2 (D-393); one name for one rule, so
nobody reads a field called `is_verified` on a card as the thing it isn't.

The founder's answers to P-75 and the badge (8 October 2026, relayed), written up by Claude in
T-6.2.

### D-495 · The feed scores every candidate; a nearest-N window was tried and saves nothing; the launch shape is accepted above 80 ms; JIT off — Locked
**What was tried, so nobody tries it again.** T-6.2's bench at 50,000 profiles missed 02-ARCHITECTURE
§8's p95 < 80 ms in the launch shape (everyone within Phagwara's 25 km): 191.0 to 246.1 ms across
10 rounds, because every one of 23,000 eligible candidates is scored on every request. The
founder chose a window (8 October 2026, the advisor's recommendation, relayed): rank only the
nearest 2,000 the viewer could see, every exclusion and filter before the limit, ties by id, by
the GIST index's distance order. **It was built and measured, and saved nothing:** 173.0 to 274.7
ms launch p95 over the 5 rounds run. Postgres never read the index nearest-first; it still read all
23,000 and sorted them. Three reasons, each read from the plan on the bench's own database:

1. **The radius is estimated at 5 rows**, in both shapes, where it holds 50,001 (launch) and 2,815
   (spread). PostGIS estimates `ST_DWithin`'s bounding box well (50,001 and 2,671) and then
   multiplies in a near-zero selectivity for its distance test, so every join is planned for a
   handful of rows.
2. **The tie-break by id stops the index ordering the window.** The index gives distance order,
   never distance-then-id, so Postgres sorts whatever it reads, even forced.
3. **The points are few:** 50,000 people on 1,793 distinct grid points (D-490). Forced to read the
   index nearest-first, without the tie-break (`enable_sort` and `enable_seqscan` off), the scan
   alone took 52 ms to its first row, the window 82 to 101 ms in the launch shape and 71 to 82 in
   the spread one, three times slower than today's spread (psql, 5 runs each, while other sessions'
   tests loaded the machine). And with no tie-break, who sits at the window's edge changes between
   requests.

**Decision.** No window: the feed scores every candidate, as D-491 says. **The 80 ms target holds
for the spread shape, what beta looks like.** **The launch shape is accepted above 80 ms**, its
p95 on record as a range (T-6.2's tick, the bench of 8 October 2026: 197.1 to 209.0 ms over 10
rounds, under other sessions' load), far beyond beta scale: it needs 50,000 people inside one
city's 25 km. Its fix, ranking by grid cell first, is P-391, before any city passes 10,000
eligible profiles or when P-390's staging numbers say so. `api/bench/discovery` judges the spread
shape and reports the launch one.

**JIT off, for the feed's transaction only:** `SET LOCAL jit = off`, never for the database.
Postgres's JIT compiled the statement on every request and the compiling cost more than the
query (psql, 3 runs each: 112 to 113 ms without it, 399 to 575 ms with it). Whether Supabase's
setting and pooler leave it so is P-390's. `test_the_feed_runs_with_jit_off_for_its_own_transaction_only`
holds it.

**The worst case, accepted:** a city crowded far past beta scale gets a slow deck, about 200 ms a
page at 50,000 people within 25 km, until P-391.

**Rejected:** the window (above); forcing the planner with `enable_sort` or `enable_seqscan` (slower
for beta's shape, nondeterministic at the edge); copying gender, status and the fraud band onto
`profiles` (a schema change that leaves the per-candidate scoring in place).

The founder's decision, 8 October 2026, on the advisor's recommendation (Claude, in a separate
chat), relayed by the founder, after Claude built and measured the window and reported its
numbers; written up by Claude in T-6.2. The advisor's own words on its recommendation: "option 1
was wrong".

### D-493 · Who may open a public profile — Locked
**Decision (T-6.3).** `GET /v1/users/{id}` answers to anyone discovery's `visible_to` allows, **without
seeking or the radius**: a profile is reached by link too (T-6.8's share page, T-6.6's
`@username`), so a man seeking women may open a man's, and anyone's across India. Its other
conditions all stand: no block either way, onboarding `done`, status `active`, not in the `freeze`
band, `shadow` only to the shadowed (D-031). **A hidden profile** (`is_hidden`) opens only to
someone it already shares a match or a Thread with, so a chat's header keeps working; it stays out
of the feed and search. A block beats that exception. **Your own profile** always opens, hidden or
not, and records no view. **Every refusal is the same `NOT_FOUND`** as an id nobody holds: the
asker never learns which reason (04-API: a blocked user is `NOT_FOUND`). A view is one
`profile_views` row per pair, its time moved and its count raised on each later view, never written
for your own profile or a refusal (B-5 reads it later).

**Why:** the plan's question, answered by the founder; the hidden exception because a hidden profile
otherwise broke every conversation it was in.

**Rejected:** applying seeking (a shared link would 404 for half its readers); hiding a hidden
profile from its own matches and Threads.

The founder's approval, 8 October 2026, of Claude's Q4 in T-6.2's plan, on the advisor's
recommendation (Claude, in a separate chat), relayed by the founder.

### D-500 · Deleting an account: deleted at once, restored by signing in, erased on day 29 or 30 — Locked
**The decision (T-9.6):**
- **`DELETE /me`** sets `deleted` and `deleted_requested_at` and revokes every session and push
  subscription, in one transaction under the row's lock. It answers `202 {erase_by}`, 30 days on.
  Who may delete is who may sign in, checked again under the lock, so a ban or a freeze that
  lands while the request is in flight still stops it (D-051: never a route around a ban).
- **What a `deleted` account gets** (D-067 left it to this task): a request on an access token's
  last minutes is `401 SESSION_REVOKED`, so the web goes to sign-in. **Signing in again before
  the erasure restores the account**: `active`, the request cleared, everything as it was, the
  balance included. Proving the number proves the account (D-069). This replaces D-067's
  "`FORBIDDEN` until T-9.6 decides"; anything else not on `MAY_SIGN_IN` stays `FORBIDDEN`.
- **The erasure** is a daily job, `erase_accounts`, at 03:30 IST (the worker's cron, its only
  one). It erases every account deleted at least **29** days ago, so each is erased on day 29 or
  30, and `/privacy` keeps "within 30 days". `/privacy` gives "within 29 days" as the window to
  sign back in. One transaction per account, under the row's lock. Its files are deleted and
  read back as gone first (D-090), then D-503's rows, then the row is anonymised. A file that
  won't go rolls that account back for the next day's run.
- **The `users` row stays**, since kept rows name it: `anonymised_at` set, `phone_enc`, dob
  (D-501), the PIN, `last_active_at` emptied, and the referral code replaced. **`phone_hash`
  stays on it** (D-051): `ix_users_phone_hash` finds every row a number ever had, for T-9.5.
  It is unique among live accounts only (`uq_users_phone_hash_live`), so **after the erasure the
  number starts a new account**, unless `banned_identities` holds it. The database holds the row
  to this: `anonymised_at` never changes once set, only a `deleted` row carries it, and an
  anonymised row has no number, dob or PIN (migration `a3c12afe34d5`).
- **The race.** A sign-in and the erasure both lock the row. If the erasure commits first, the
  sign-in's lookup no longer matches the erased row and it starts a new account; if the sign-in
  commits first, the account is restored and the erasure finds nothing due. A test forces each
  order and asserts that the second waited.
- **Cost against D-091:** ARQ checks its cron at each poll without asking Redis. The job costs
  one enqueue and its own few commands, once a day. D-091's sum, 260,640 a month idle, is
  unchanged; a test holds the cron to no Redis command until it is due.

**Rejected:** `FORBIDDEN` at sign-in with an explicit restore endpoint (a second step for the
same proof); a deferred job per deletion (lost if Redis is wiped, where the daily job reads the
database); erasing at 30 days or more (a daily job would land past "within 30 days"); clearing
`phone_hash` (D-051 keeps it).

Recommended by Claude in T-9.6's plan; approved by the founder on the advisor's recommendation
(Claude, in a separate chat), relayed, 8 October 2026.

### D-501 · The erasure clears the date of birth; gender stays — Locked
**The decision (T-9.6):** dob is personal data, and nothing needs it once an account is erased,
so the erasure clears it. T-1.9's trigger makes dob immutable once set. It now has one exception:
dob may become null **in the update that sets `anonymised_at`**, and in no other. Afterwards
`ck_users_anonymised_is_empty` keeps it null. Otherwise the trigger's first-set rule would let a
date be written back to the anonymised row. **Gender stays:** D-076's triggers read it, and on
its own it identifies no one.

**Rejected:** keeping dob (pseudonymous beside the hash, but nothing needs it); clearing gender
(the ledger's and wallets' triggers read it, and the ledger is kept).

Approved by the founder on the advisor's recommendation, relayed, 8 October 2026.

### D-502 · A copy of your data: JSON of your own, a link for 24 hours, then deleted — Locked
**The decision (T-9.6):** `POST /me/export` makes an export row and queues `export_data`. The
worker writes the JSON to the private bucket and marks it `ready`. `GET /me/export` signs a link
to it only until `expires_at`, 24 hours after it was ready, and never past it (the link's TTL is
what remains). `expire_export`, queued 24 hours on, deletes the file, reads it back as gone and
marks the row `expired`; the daily job sweeps any file left behind. Asking again returns the
export being made, or a ready one, rather than a second; a pending one stuck for an hour is
replaced; 5 asks a day. The key is recorded before the file is written, so no file ever exists
that no row points to.

**What's in it:**
- **Account:** your phone number (decrypted on the worker, D-061), date of birth and gender.
- **Profile:** your own location, interests and intents.
- **Photos and voice notes:** each with a 24-hour link.
- **Messages you sent**, with threads numbered within the export.
- **Your activity:** your swipes, blocks, kudos, gifts and album requests, with what and when
  only; reports **you filed**.
- **Money:** your ledger (reason, delta, balance, time; never `ref_id`, which can name another
  person) and payments (never `raw_webhook`).
- **The rest:** notifications (kind and time; never the payload), notification settings and
  sessions (times).

**What's never in it:** anyone else's id, name, username, number, location or words. Reports
about you aren't in it (T-9.1: never told who reported, or that anyone did), and neither are
fraud signals or moderation's notes. A test fills the other person's name, username, phone,
location, about and message text with markers and finds none of them in the file. Logs name an
export by its id only (rule 15).

**Rejected:** emailing it (sign-in is by phone; there is no address); messages received (the
other person's words); a link stored on the row (one is signed at each read instead).

Approved by the founder ("your sent messages only"), on the advisor's recommendation, relayed,
8 October 2026.

### D-503 · What the erasure takes and keeps, column by column — Locked
**The decision (T-9.6):** `api/app/modules/account/erasure.py` lists every column holding a key
to `users` as erased or kept. A test holds the lists to the database, so a table or column added
later fails CI, naming D-503, until someone decides.
- **Erased:** profiles, intents, interests, photos and verifications (files deleted), data
  exports (files deleted), swipes, reveals, profile views and matches (both sides), the person's
  own blocks, thread clears and voice unlocks, kudos *to* them, notifications, notification
  settings, push subscriptions and sessions.
- **Kept:** ledger, payments, refund requests and the wallet (money); messages and threads (rule
  12, D-051); reports and the audit log (rule 12); fraud events and scores (moderation records);
  other people's blocks of them; kudos *from* them (the other person's); gift sends, album
  requests and referrals (records the ledger names).
- **Kept by name before it exists:** `welcome_grants`, T-8.11's hash of every number that
  received welcome Velas (D-470, P-371). Its name is provisional: T-8.11 renames the entry if it
  chooses another. The check asks for it to move into the kept list once the table exists.
  `banned_identities` has no key to `users` and is never touched.

This is not D-072's list. An under-18 refusal happens before anything rule 12 keeps can exist,
and deletes everything; the erasure happens to an account that may have lived for years.

Approved by the founder on the advisor's recommendation, relayed, 8 October 2026; the welcome
entry at the founder's direction.
**Built 8 October 2026 (T-8.11):** `welcome_grants` exists under that name, and is in `KEPT` by its
one column keyed to users, `user_id`; `KEPT_WHEN_BUILT` is empty, its check kept for the next.

### D-504 · A deleted account's unspent Velas are lost at the erasure — Locked
**The decision (T-9.6):** a man's unspent Velas are lost when his account is erased, with no
refund (D-230). His ledger and balance stay as records, and T-9.9's reconciliation still holds.
Restored within the window, his balance is untouched, so the Velas come back with the account.
The delete confirmation shows his balance in plain words before he confirms, as the number from
the API (`Me.balance`), never written into the copy; that screen is T-9.8's. `/privacy` and
`/refunds` say it.

The founder's own decision, 8 October 2026.

### D-505 · Usernames stay locked after onboarding for the beta; an erased one is freed — Locked
**The decision (T-9.6, the second of D-068's questions):** a username still can't change after
onboarding, `IMMUTABLE_FIELD` as before. It is a link people share (D-001's `/@username`), and
changing it breaks links and invites impersonation. A design for changing it (an old name
redirecting for a while, then retired) waits until after the beta, if anyone asks. **At the
erasure the username is freed** along with the profile: D-051 erases what others could see, and
keeping a name reserved forever would keep identifying data the person asked us to erase.

**Rejected:** changes now (redirects and a retired-name list for a case nobody has raised);
retiring erased names forever (keeps identifying data).

Approved by the founder on the advisor's recommendation, relayed, 8 October 2026.
### D-492 · Who may be swiped, and what counts toward men's daily cap — Locked (values tunable)
**Decision (T-6.4).** `POST /v1/swipes` takes a like, a pass or a Super Like on **someone the feed
could show the swiper**: discovery's `visible_to`, mutual (each wants the other's gender), every
exclusion of 02-ARCHITECTURE §8, **without the radius**, so someone found by their `@username`
across India may still be liked; anyone else, yourself included, is the one `NOT_FOUND`. One swipe
per pair, ever: a second, whichever way, is `ALREADY_EXISTS`, and charges nothing.

**The cap is a man's alone:** `app_config`'s `swipe_daily_limit_men` (50), by the IST day, reset
at IST midnight, read through P-47's cache. **A like and a pass count; a Super Like doesn't**: it
is its own, paid action (D-250), 5 Velas for a man through `pricing.charge` and so the wallet's
`debit()` (rule 5), nothing for a woman (D-002), its ledger row's ref the other person, once per
pair (03-SCHEMA). Over the cap: `SWIPE_LIMIT_REACHED`, with `details.limit` and
`details.resets_at`. The count lives in Redis, one key per man per IST day; a swipe takes its
place before the transaction and gives it back if nothing is written (a duplicate, a refusal, a
402), so the count is of swipes made. `swipes_left` is null for anyone uncapped.

**A like or Super Like back makes the pair's match**, once (`matches`' unique pair, the order the
database's own), and each of them is told: `match.created` on their socket, `{match_id,
user_id}`, and an in-app notification of kind `match` (T-9.4 sends the pushes). The pair is
locked for the transaction (an advisory lock on the ordered pair), so two people liking each other
at once are one after the other, and the second makes the match; `test_race.py` forces the overlap.

**Rejected:** the radius on a swipe (a profile reached by link could never be liked); counting the
Super Like (it is paid, and D-250 says it isn't swiping); counting swipes in the database (two
swipes at once on different people could both take the last place).

The founder's approval, 8 October 2026, of Claude's Q5 in T-6.2's plan, a Super Like not counting,
on the advisor's recommendation (Claude, in a separate chat), relayed by the founder.

### D-520 · Refunds and chargebacks take a payment's Velas back at once; spent Velas are a shortfall — Locked
**The decision (T-8.2; the founder, 8 October 2026, on the advisor's recommendation (Claude, in a
separate chat), relayed; the shape Claude's, in T-8.2's plan), D-076's rule 3 built:**
- **When they go back:** at `refund.created`, the moment the money is committed to go back, never
  days later at `refund.processed`; and at `payment.dispute.created`, though Razorpay deducts the
  money only if the dispute is lost. A refund that fails (`refund.failed`) or a dispute that is won
  (`payment.dispute.won`) gives back **exactly what its reversal took**, read from that reversal's
  own entry, and nothing if it took nothing.
- **The status follows the money:** `refunded` at `refund.processed` or `payment.dispute.lost`. A
  disputed payment stays `paid` until it is lost, so turnover (D-483) counts it while the money is
  still ours.
- **If he has spent them:** whatever balance is left is taken, down to 0, through
  `wallet.service.reverse()`, which never refuses with `INSUFFICIENT_CREDITS` and writes nothing at
  0 (`CHECK (balance >= 0)` holds). The rest is a shortfall: an error log line, and on a dispute a
  `fraud_events` signal, `chargeback_shortfall`, weight 0 until T-9.2 says what it counts for,
  `meta` `{what, payment_id, shortfall}`. **No automatic freeze:** freezing is a moderation
  decision.
- **Only payments calls `reverse()`,** and only for `purchase_reversal`: a test holds it as an
  allowlist, as `debit()`'s callers are held (T-5.2).

**Added by Claude while building, beyond the approved plan; kept by the founder, 8 October 2026:**
- **A reversal never takes more than its payment granted, less what was already taken back for
  it** (reversals less restores). One payment refunded in two parts, or refunded and then
  disputed, would otherwise take the whole amount twice, the second time from Velas he bought
  another time.
- **A refund of a payment that wasn't the one credited** (a second payment on one order, T-8.3's
  duplicate charge) takes nothing: no Velas were granted for it.
- **A gap left open, P-420:** at a balance of 0 nothing is written, so a redelivery of the same
  refund or dispute after he has bought more takes from the new Velas, up to the shortfall.

**Why:** D-076's rule 3: money never goes back while its Velas stand. Reversing only when the
money leaves (`processed`, `lost`) lets him spend the Velas through a dispute that lasts weeks.

**Rejected:** reversing at `.processed` and `.lost` only; a negative balance; freezing on a
shortfall; refusing the reversal when the balance is short (`debit()`), which would leave every
Vela standing.

### D-521 · `purchase_reversal` and `purchase_restored`: two ledger reasons, one per refund or dispute — Locked
**The decision (T-8.2; approved with D-520):** `ledger_reason_t` gains `purchase_reversal`, a
debit, and `purchase_restored`, a credit, each with `ref_type` `payment`. Both **repeat for one
payment, the event named by the caller**, as `thread_extend` does: the event is the refund's or
dispute's own Razorpay id (`rfnd_…`, `disp_…`), so the key is
`{user_id}:purchase_reversal:{rfnd_…}`, one entry per refund or dispute, and the one-per-event
index leaves both out. Two migrations in T-5.2's pattern: `e9a09934aeb7` rebuilds the type (never
`ALTER TYPE ... ADD VALUE`, `4a7e20790605`'s reasons), its downgrade refused while any ledger row
uses either; `fb0a7ce8dd16` names them in `ck_ledger_entries_reason_direction`,
`ck_ledger_entries_reason_ref_type` and `uq_ledger_entries_one_per_event`. `wallet/rules.py` and
`test_guards.py` change with them. The history shows "Purchase reversed" and "Purchase restored"
(the founder's words, 8 October 2026).

**Why:** a reversal is no purchase and no priced action: it needs its own reason, in the right
direction, so the ledger says what happened. A payment may be refunded in parts, or refunded and
disputed, so the reason can't be one per payment.

**Rejected:** reusing `refund` (refused until a task gives it a meaning, D-077, and its name says
money, not Velas); one reversal per payment; `admin_grant` for the restore.

### D-522 · The first-purchase bonus is decided at capture, under the wallet's lock — Locked
**The decision (T-8.2, closing P-380; approved with D-520):** T-8.1 sets `bonus_credits` at order
time, when a man may have two orders open, neither paid. So the capture decides: inside its
transaction, `purchase` is credited first, which locks the wallet row until the commit; **then**
the capture asks whether any other payment of his is `paid` or `refunded`. Under READ COMMITTED
that read runs after the lock is granted, so a concurrent capture that committed while this one
waited is seen. If none is, `purchase_bonus` is credited with the row's `bonus_credits`; if one
is, none, the row's `bonus_credits` becomes 0 so the poll tells the truth, and
`payments.bonus_withheld` is logged. A race test forces two captures of one man into overlap at
the wallet's lock and asserts one bonus.

**Why:** P-380's worst case, a bonus on each of two packs bought at once, up to 90 + 90 Velas. The
fix belongs where Velas are granted, under the lock that serialises them (D-077).

**Rejected:** deciding at order time only; a lock of its own for the bonus; reading before the
wallet's lock, which two captures at once both pass.

### D-523 · The webhook: verified, one transaction per event, the anchor set only by a capture — Locked
**The decision (T-8.2; approved with D-520):**
- **Signature:** `X-Razorpay-Signature`, hex HMAC-SHA256 of the raw body with
  `RAZORPAY_WEBHOOK_SECRET`, compared in constant time. Bad or missing: `400 VALIDATION_ERROR` and
  a warning, the body never logged. No secret: every signature refused, with an error naming the
  setting (P-382 now covers it too).
- **One order, several attempts:** a failed attempt never sets `provider_payment_id`, the anchor,
  and a capture still goes through on a `failed` row: Razorpay's own example is a `payment.failed`
  then a `payment.captured` for one order (a UPI retry). A second, different payment captured on
  a paid order credits nothing and logs an error for T-8.3.
- **Order isn't guaranteed:** a refund or dispute event that reaches an order not yet captured
  applies the capture first, from the signed payment inside that same event, then reverses it.
  **Added by Claude while building; kept by the founder, 8 October 2026:** `refund.processed` and
  `payment.dispute.lost` do the same and take the Velas back themselves if their `.created`
  hasn't arrived (once per refund or dispute, by its key): marking a payment `refunded` without
  its anchor is impossible (`ck_payments_paid_has_anchor`), and without its reversal would leave
  Velas standing until `.created` came.
- **`paid_at` is our clock at capture** (`core.clock.now()`), never Razorpay's timestamp: a
  webhook takes seconds, and the turnover year (D-483) turns at midnight IST.
- **Its answers:** signed but unreadable, `500`, so Razorpay retries while we fix the reader; an
  unknown order or an event we don't handle, `200`, logged. **No rate limit:** every request is
  verified, and a flood is the edge's to stop (02-ARCHITECTURE §12).
- **Concurrency:** the row is locked by its order (`SELECT ... FOR UPDATE`) for the event's whole
  transaction, and the wallet's key (D-077) catches anything past it. Five deliveries of one
  webhook at once are credited once, the overlap forced and asserted.
- **Logs** name the event, our payment's id and the order's: never payer data, never the body.

**Why:** Razorpay redelivers by design and doesn't promise order (its docs, read 8 October 2026).

**Rejected:** the anchor on any attempt (a real capture after a failure would be skipped);
Razorpay's `x-razorpay-event-id` as the guard (the row's state and the wallet's key already are);
a `400` for an unreadable signed body (Razorpay would stop retrying a real payment).

### D-524 · `raw_webhook` is an allowlist of the event's fields — Locked
**The decision (T-8.2, the direction of 3 October 2026 built):** `payments.raw_webhook` keeps the
last verified event's fields, exactly these and nothing else, flattened: `event`, `created_at`;
`payment`: `id`, `order_id`, `amount`, `currency`, `status`, `method`, `error_code`,
`created_at`; `refund` and `dispute`: `id`, `payment_id`, `amount`, `currency`, `status`,
`created_at`. Never `email`, `contact`, `vpa`, `card*`, `bank`, `wallet`, `acquirer_data`,
`notes`, `description`, nor any field Razorpay adds later. A test stores a payload with every
payer field set, and one nobody has listed, and reads back exactly these keys.

**Why:** the payer's details are RBI's own list of payment data, and not ours to keep (P-49's
residency read); an allowlist keeps out what a strip list can't know about.

**Rejected:** storing the payload whole; a list of fields to strip.

### D-560 · The hour lives in `expires_at` alone; Extend is sold by T-7.6 — Open (the mechanism, until T-7.6 builds it)
**Decision.** T-7.6 keeps D-097's hour in the one column the schema already has. Each event moves
`expires_at`, in its own transaction with the Thread row locked:

| event | `expires_at` becomes |
|---|---|
| open (T-7.1) | `now + thread_hours` |
| her message, on a live Thread | `max(expires_at, sent_at + thread_hours)` |
| his message | unchanged (D-097's amendment, a) |
| Extend, live or expired | `max(expires_at, now) + thread_extend_hours` |
| re-open, untie | `now + thread_hours` |

Every move later clears `expiry_warned_at`. **A Thread is expired once `expires_at` has passed**,
whatever its status says: the cron only catches the status up. Extend is sold by
`POST /threads/{id}/extend`, in T-7.6, as P-150 proposed.

**Why one column carries all of it.** The `max` with her message is D-097's amendment (d): an
Extend ending finds the Thread expired unless she wrote in its last hour, which pushed
`expires_at` past it, with no column for when Extend ends. Extend's `max(expires_at, now)` is the
founder's answer that a second Extend adds to what is left, and from expired it is simply `now`.
Expiry by the clock closes the minute between crons, in which his send would otherwise pass and
her message would revive a Thread that had run out. The settings (`thread_hours` 1,
`thread_extend_hours` 24, `thread_warn_minutes` 10), re-open's fresh hour and the one warning are
the founder's answers, 8 October 2026, on the advisor's recommendation (Claude, in a separate
chat), written into T-7.6.

**Rejected:** columns of their own for her last message and the end of an Extend, with expiry
computed from them, which is more state that can disagree, and a cron that can't use the partial
index on `expires_at`; expiry by the status column alone, which leaves the minute's gap above.

**Open** because the mechanism is Claude's, written in P-150, 8 October 2026, and T-7.6 may find a
better one while building; the rules it keeps are Locked where they are written (D-097, D-098,
D-250, D-253, and T-7.6's five answers), and no change to the mechanism may change them.

### D-550 · A private message is a Thread of origin `dm` that never expires — Locked
**The decision (T-7.1, approved by the founder 8 October 2026 on the advisor's recommendation,
relayed):** D-231's private message is a Thread of origin `dm`, the same one row per pair as a
Thread from a match. While active it carries no `expires_at`: `ck_threads_active_expires` reads
`status <> 'active' OR expires_at IS NOT NULL OR origin = 'dm'` (migration `ddf84381ef6c`), so the
expiry cron (T-7.6), which reads `expires_at`, never reaches it. A Knot still carries none.
- **Opening** costs him `dm_open` (8) with its first message (1 to 500 characters); her nothing.
  **Each message of his after it** costs `dm_message` (2), charged in T-7.3's send, the message
  as its ref (D-251), and nothing once the Thread is knotted.
- **Whom:** someone the public profile's rule lets you reach (D-493) who also wants your gender,
  as swipes ask (D-492's `visible_to`, mutual, the radius aside). A link reaches a profile outside
  her seeking; it doesn't let him message her. Every refusal is `NOT_FOUND`.
- **One Thread per pair:** if the pair matches later, the match points at the private message's
  Thread, and nothing is charged.
- **Untying** (T-7.7) a private-message Knot returns it to never expiring, not to a fresh hour;
  noted on T-7.7.

The downgrade refuses while an active private-message Thread exists, rather than inventing an
expiry for a conversation both people were told never ends.

**Rejected:** a far-future `expires_at` (a lie the cron would one day act on); a status of its
own (every list, filter and Knot rule would need a fourth case).

### D-552 · What a message may say: the prototype's lists, three corrections — Locked
**The decision (T-7.1, D-030 built; the founder, 8 October 2026):** `messages/filters.py` holds
the prototype's lists ("text safety filters"). Refused, on every message ever, with
`MESSAGE_REJECTED` and `details.rule`: `abuse` (its eight words, as a prefix) and `solicitation`
(paytm, gpay, phonepe, western union, and money phrases). Masked, in a Thread's first
`mask_first_n_messages`: phone numbers, anything@something (email and every UPI app's handle),
and social handles. A refusal writes a `message_rejected` fraud event, weight 0, naming the rule
and never the text, in a transaction of its own so the refusal can't roll it back.

**Three corrections to the prototype, each because it hid or refused ordinary sentences:**
1. "transfer" and "upi" refuse only inside a money phrase ("transfer money", "send 500 rupees",
   "upi id"): "I'm transferring jobs" passes. The founder's choice, from Claude's plan.
2. A handle needs its app named and then a separator (`insta: x`, `snap @x`, `insta id x`,
   `my insta is x`): the prototype's `wa` followed by any three letters hid "watching" and
   "water". The known cost, accepted: "whatsapp is down" is masked in the first 20 messages.
3. Any `name@handle` is masked, rather than the prototype's five UPI suffixes.
Found and made by Claude building T-7.1; (2) and (3) weren't in the plan the founder approved,
and are reported to him with the task.

**Not yet:** Hindi and Hinglish words, payment-app asks and "number do": P-450, the founder's
list, before REL-1.

### D-553 · A woman's daily limits: settings, by the IST day, `RATE_LIMITED` — Locked (values tunable)
**The decision (T-7.1, T-7.3; the founder, 8 October 2026, building D-098's limits):**
- `women_new_men_daily_limit` (30): different men a day she opens a Thread with or writes to
  first. The same man twice in a day counts once; a woman she writes to never counts.
- `women_private_messages_daily_limit` (30): her messages a day in private-message Threads,
  the first included.
Both in `app_config` (migration `386bbc188276`), counted in Redis by the IST day, `RATE_LIMITED`
past either with `details.retry_after_s` to the next IST midnight. A place is taken before the
transaction and given back if nothing is written, as swipes' cap (D-492). Limits, never prices:
she is never charged (D-098), and nothing limits a man here.

### D-554 · Her side carries no countdown: `expires_at` is a man's alone — Locked
**The decision (T-7.1, approved 8 October 2026 on the advisor's recommendation):** `Thread` and
`ThreadRow` send `expires_at` to a man only; a woman's is null, so the server decides, and her
screen can't show her a countdown by mistake (D-097, 08-DESIGN §8: "No countdown, no price, no
locked state"). `status` stays true for both. An allowlist: a person with no gender is shown
none.

**Rejected:** the same data for both and the screen hiding it.

### D-580 · A broken payment's claim: two kinds, resolved by what the gateway says — Locked
**The decision (T-8.3; the founder, 8 October 2026, on the advisor's recommendation (Claude, in a
separate chat), relayed; the shape Claude's, in T-8.3's plan), D-050's broken payments built:**
- **Two kinds, never a change of mind** (D-050, D-230): `missing_velas`, the money went through
  and no Velas came, and `duplicate_charge`, charged twice for one purchase. `POST
  /refund-requests {payment_id, reason}` takes the caller's own payment (anyone else's is
  `NOT_FOUND`, the same as none), nothing in his words, one open claim per payment
  (`ALREADY_EXISTS`), and refuses `missing_velas` on a payment whose Velas were granted
  (`NOT_ALLOWED`). 10 a day per user.
- **Statuses:** `open`, then `granted`, `refunded` or `rejected`; the database holds the shape
  (a resolved claim has `resolved_at`, a refund names the gateway's payment and refund, a
  rejection has a note).
- **The admin acts, the gateway decides** (rule 6): a resolution first asks the gateway for every
  payment on the order (`GET /v1/orders/{id}/payments`), never the claim's kind or the admin's
  word, and does only what that shows:
  - **grant**, while the row has credited nothing, of the first captured, untouched payment for
    exactly the order's amount, **through the webhook's own capture**: `purchase` and, by D-522's
    rule, `purchase_bonus`, under the webhook's key (D-077), **never `admin_grant`**, so the
    webhook arriving after the repair is a repeat.
  - **refund**, in full in the gateway, of a captured, untouched payment no Velas can ever stand
    against (D-076 rule 3): never the credited one, and never one a grant could credit, whose fix
    is the grant. The claim's id is Razorpay's `receipt`, which it takes once.
  - **reject**, with a note. **Two orders, both credited, are rejected:** both purchases completed
    and nothing is broken (D-230). If the founder ever returns money anyway, he refunds from
    Razorpay's dashboard, and T-8.2's webhook takes those Velas back.
- **A refund's record is the claim's** (`refunded`, the gateway's payment and refund ids). **The
  credited payment's row is never touched.** This corrects T-8.3's plan line, which said
  "`payments.status = refunded`": the payment refunded has no row of its own, so marking the row
  would call the purchase that stands refunded and drop it from turnover (D-483).
- **One resolution at a time:** the claim's row is locked for the whole of it, the gateway's
  calls included; the payment row's lock and the wallet's come only after the gateway has
  answered (D-077). A race test forces two admins into overlap at that lock and asserts one
  refund.

**Why:** a broken payment is ours to fix (D-050), and a fix that trusts a claim or an admin's
word could grant Velas nobody paid for, or return money whose Velas still stand.

**Rejected:** `payments.status = refunded` for a duplicate (above); `admin_grant` for missing
Velas (a later webhook would credit them again); the claim's kind choosing the action (a
`missing_velas` payment for the wrong amount is fixed by a refund); refunding a payment a grant
could still credit.

### D-581 · Every refund and dispute handled is recorded once, whatever it took (P-420) — Locked
**The decision (T-8.3, closing P-420; approved with D-580):** `payment_reversals` records each
refund and dispute the webhook handles, once, by its own Razorpay id (`rfnd_…`, `disp_…`,
unique), with what its reversal took and what it couldn't (`taken`, `shortfall`), 0 and 0 when
nothing was outstanding. The webhook's repeat check reads it first; the ledger's own entry still
counts for a reversal made before the table existed. Append-only (`refuse_change()`, and no UPDATE
or DELETE for the app role), keyed to `payments` only, never `users`, so an erasure (D-500)
neither takes it nor needs to. Its downgrade refuses while any row exists.

**Why:** P-420's worst case. A refund or dispute reaching a man who had spent every Vela of that
payment took 0, and a ledger entry can't be 0, so nothing marked it handled. A redelivery after he
bought Velas again took from the new ones, up to the shortfall, and a dispute recorded its
`chargeback_shortfall` signal a second time. A test buys again between the two deliveries and
finds the new Velas untouched; another delivers one such refund five times at once and finds one
record.

**Rejected:** a list of handled ids on the `payments` row (an append-only fact kept in a mutable
row); writing the record only when something was taken (the case P-420 is about).

### D-582 · The claims' admin routes: admin only, audited — Locked
**The decision (T-8.3; approved with D-580):** `GET /admin/refund-requests?status=&cursor=&limit=`,
the claims in a status (`open` if absent), oldest first by `(created_at, id)` (D-270), and `POST
/admin/refund-requests/{id}/resolve {action, note?}`. `require_role(admin)`, never a moderator: a
claim moves Velas or money. Every list and every resolution writes `audit_log`; a refused one
changes nothing and writes nothing. T-9.5's panel uses them (P-480); the user's claim form is
T-8.7's (P-481).

**Rejected:** `python -m app.tools.refund_claims` over `fly ssh`, as D-264's selfie review is
run: Fly's login is a stronger gate than a role check, but `audit_log` needs an actor, and the
tool would serve no panel later.

### D-540 · Search: `@` and a username's start anywhere, or text nearby; a `SearchResult` per row — Locked
**The decision (T-6.6):** `GET /v1/search?q=` has two modes, chosen by `q`.
- **`@` and 1 to 20 of `[A-Za-z0-9._]`**: usernames starting with it, in any case, the exact one
  first and marked `exact`, then the rest in byte order. Who: discovery's `visible_to` **without
  seeking and without the radius**, as a link reaches (D-493), so a username finds its person
  across India; never a hidden profile, even one the searcher shares a match or Thread with
  (D-493: hidden stays out of the feed and search); swiped or not. `_` and `%` are characters,
  never LIKE's wildcards.
- **Text, 2 to 50 characters**: within `discovery_radius_km`, `visible_to` mutual, as the feed,
  swiped or not. A person matches on a name or username by trigram similarity (0.3, set for the
  transaction, never left to the database's default) or by prefix, a city by prefix, or an intent
  or interest whose catalogue label holds the text. Best name match first, then by id.
- Either way only `active` accounts (T-9.6, D-500), nobody blocked either way, not yourself, and
  the `freeze` and `shadow` bands as the feed has them. Anything else, an empty `q`, one
  character, `@` and a character outside the alphabet, more than 50, is `VALIDATION_ERROR` on
  `q`. 60 a minute per user.
- **A row is a `SearchResult`**: `id`, `first_name`, `age` (null if hidden), `username`, `city`,
  `main_photo_url` (D-494's), `shows_badge` (D-393's, never `is_verified`), `is_online`, `exact`.
  No distance: a row across India would carry one nobody asked for. Each field is the `Card`'s,
  computed by the same code.
  **Named `SearchResult`, not 04-API's first name for it, `CardLite`:** T-7.2 landed a `CardLite`
  of its own the same day (the chats list's other person, a different shape), and two schemas of
  one name collide in the OpenAPI the web is typed from. The shape and the rules are as above.
- **`GET /users/by-username/{u}`** is `GET /users/{id}` by another key: the same rule (D-493),
  the same `PublicProfile`, a view recorded the same way, every refusal and a name nobody holds
  (an erased one's, D-505) the same `NOT_FOUND`.
- **The web's field** sits on a chrome bar at the top of the search screen, under the shell's
  header, whose shape stays `AppShell.tsx`'s alone; 08-DESIGN §8 drew it inline in the header.

**Why:** the plan's line ("`@` prefix … ignores distance/filters, still respects blocks/hidden;
otherwise trigram … within radius"), with the shape 04-API named but never gave. People already
swiped stay findable: search is a lookup, not a deck. Ranked by name, not by D-491's score: a
person searching for "Simran" wants Simran first.

**Rejected:** a distance on the row (a `@` row across India); hidden profiles in `@` search for
matches (D-493 keeps them out); ranking text results by the feed's score.

Approved by the founder on the advisor's recommendation (Claude, in a separate chat), relayed, 8
October 2026, as Claude's plan for T-6.6 proposed it; written up by Claude.

### D-541 · The sign-in and app routes carry a nonce, not `'unsafe-inline'` — Locked
**The decision (T-6.6, D-059's trigger):** T-6.6's search rows are the first screen to render
another person's text (their names, usernames and cities), so the re-examination D-059's
amendment of 3 October 2026 set moved here from T-6.5. The routes `NONCE_ROUTES` names in
`web/src/lib/security-headers.ts`, `/login`, `/onboarding`, `/discover`, `/chats`, `/wallet` and
`/you`, each and all beneath it, are served by `web/src/proxy.ts` with `script-src 'self'
'nonce-<nonce>' 'strict-dynamic'`, a fresh 128-bit nonce per response, and never
`'unsafe-inline'`. Every other directive is the static policy's, from the same build
(`CSP_WITH_NONCE`, built in `next.config.ts` from the build's environment, with a slot the proxy
fills; a build without it serves those routes nothing rather than no policy). Next puts the nonce
on its own scripts; `'strict-dynamic'` lets what they load run (Next's chunks, Firebase's
reCAPTCHA on a Firebase build) and nothing injected. The `(auth)` and `(app)` layouts render per
request (`force-dynamic`): a page built ahead carries no nonce. Every other page keeps the static
policy with `'unsafe-inline'` and stays static: none renders anyone's text but ours. `/admin`
waits for T-9.5, the first admin screen with anyone's text; today it is a `next dev` placeholder.

**Proved by effect, in the E2E** (`web/e2e/csp.spec.ts`): an injected `<img onerror>` runs on `/`
and is refused on `/login` with a `script-src` violation; every journey runs through `/login`,
onboarding and `/discover` with no violation. `next build` lists those routes as dynamic and the
marketing pages as static.

**Why:** React's escaping is the defence for someone else's text, and the CSP the second line; a
`script-src` with `'unsafe-inline'` is no second line. Scoped to the signed-in routes, the cost
D-059 rejected nonces for (every page dynamic) falls only on pages with no performance target,
never cached for anyone else.

**Rejected:** nonces on every page (the marketing pages lose their static rendering and margin);
Next's experimental hash-based SRI (experimental); keeping `'unsafe-inline'` (the trigger is met).
**Unverified until staging:** Firebase's reCAPTCHA under `'strict-dynamic'`. The local E2E signs in
by the fake SMS, so it never loads reCAPTCHA; T-3.14's staging check is where it is seen.

The founder's answer to Q1 of Claude's plan for T-6.6, 8 October 2026, on the advisor's
recommendation (Claude, in a separate chat), relayed; written up by Claude.

---

### D-530 · Welcome Velas: a missing setting skips with a warning, no backfill, and a toast — Locked
**The decision (T-8.11; the founder, 8 October 2026, on the advisor's recommendation, Claude in a
separate chat, relayed by the founder):** three things D-470 left to T-8.11's plan.
1. **A missing `welcome_velas` row skips the grant and logs a warning,** and never fails a
   sign-up: `onboarding.welcome_config_missing` at warning level, naming the user and the key. A
   value that isn't a whole number is treated the same, and a negative one skips with
   `onboarding.welcome_config_negative`. **Its worst case:** a skip is silent to the man, so a
   lost row grants nobody until someone reads the warning. What notices a row lost by a
   migration is `tests/test_reference_data.py`, which holds the migrated database to
   `welcome_velas = 5`; a row deleted by hand in production is only the warning.
2. **No backfill** for men already at `done`: before launch they are test and seed accounts. The
   dev seed writes `done` directly, never through `complete()`, so seed men get nothing.
3. **One line tells a new man about his Velas:** a toast as he finishes, "5 Velas are in your
   wallet, to start you off." (one Vela in the singular), the number his balance in the `Me`
   that finishing returns, never written into the copy. Nothing else can credit a man before
   `done`, so a balance then is his welcome; at 0 (his number had its welcome, or the grant is
   off) there is no toast. Inside D-262's rule (`claims.test.ts`).

**Why:** a sign-up that fails over a setting costs a real person; a skipped grant costs 5 Velas
and is logged. The toast's words are Claude's draft, approved as written.

**Rejected:** failing the sign-up when the row is missing (a person locked out over our
configuration); a default of 5 in code when the row is missing (a second source for a tunable
number); backfilling existing men.

The founder's approval, 8 October 2026, of the advisor's three recommendations as T-8.11's plan
put them, relayed by the founder.

### D-551 · What his messages cost, and what hers move — Locked
**The decision (T-7.3; the founder, 8 October 2026: D-250 and the plan's Q4, Q5 and Q7):**
- **The opener paid to open.** In a Thread from a match, the man who opened it (`thread_open`, 5)
  writes free while it is live.
- **His first message in a Thread she opened:** if she has written, the 2-Vela re-open,
  `thread_reopen` (D-250), keyed `answer:{thread}` so it is charged once however he retries; if
  she hasn't, `thread_open`'s 5, since a man's first message opens a Thread (D-097 step 1).
  Otherwise a woman opening first would hand him a free Thread.
- **A private message:** every message of his after the one that opened it costs `dm_message`
  (2), the message as its ref (D-251), and in one she opened every message of his does (he never
  pays 8 there). Nothing once knotted.
- **A Knot is free** (D-003); a woman pays 0 for everything (D-098), decided by `pricing`, never
  by the send.
- **The hour, built here to D-560 and T-7.6's text** (the founder's Q7): her message on a live
  Thread from a match sets `expires_at` to the later of itself and `now + thread_hours`, and
  clears `expiry_warned_at` when it moves; his message never moves it (D-097's amendment, a), so
  a longer hour bought by Extend is never cut short and, once it ends, the hour counts from her
  last message (d).
- **Expired is the clock** (D-560): a Thread whose `expires_at` has passed refuses his send with
  `THREAD_EXPIRED` though the cron hasn't caught its status up, in sending and in opening (T-7.1's
  open path takes the same check), and her message is delivered and moves nothing.

### D-555 · Sending to a deleted account is `ACCOUNT_DELETED` — Locked
**The decision (T-7.3, the plan's Q8, approved 8 October 2026):** a message to someone whose
account is `deleted` (D-500) is refused with `ACCOUNT_DELETED` (410): "They deleted their
account." Their row already says "Deleted account" (T-7.2), so the code reveals nothing new, and
the web can say what happened rather than a generic refusal. Their messages stay, named as from a
deleted account (D-051). Signing in again restores the account (D-500), and with it the Thread.

**Rejected:** `NOT_ALLOWED` (422), which the web couldn't tell from a voice note or a gift.

### D-556 · `websockets`, a dev dependency, for the load test's client — Locked
**The decision (T-7.4, the plan's Q11, approved by the founder 8 October 2026):** `websockets`
(17.1, already in `uv.lock` through `uvicorn[standard]`, which serves the API's sockets with it) is
declared in the dev group, for `bench/realtime/sockets.py`'s thousand clients. Nothing in `app/`
imports it; the API's own sockets are Starlette's. The tests use no client library at all:
`tests/ws.py` calls the app as ASGI, in process.

**Rejected:** a hand-written handshake in the bench (a client of our own, tested by nothing).

### D-557 · The socket: a ticket, the web's origin, one subscription an instance, closed by the server — Locked
**The decision (T-7.4, building 02-ARCHITECTURE §6; the plan approved 8 October 2026):**
- **A ticket** (`POST /v1/ws/ticket`, onboarded, 30 a minute): 32 random bytes, kept in Redis
  30 seconds by its SHA-256 alone, naming the user, taken with `GETDEL` as a socket presents it.
  The access token never goes in a URL, which proxies and logs keep.
- **`/ws?ticket=`, at the root:** refused before it opens (4403) unless its `Origin` is one of
  the API's exact CORS origins; closed (4401) without a live ticket. The gateway reads no
  database, so a socket holds no connection (P-52).
- **One `PubSub` per instance**, never per socket: a user's first socket subscribes
  `user:{id}`, their last unsubscribes. Each socket has an outbox of 100; one that fills is
  closed (1013) and reconnects, never waited for.
- **Heartbeat:** the client's `ping` gets `pong`; 60 seconds of silence closes the socket (4408).
- **Closing:** `socket.close` (`core/events.py`'s `close_sockets`) is queued in the transaction
  that revokes a user's sessions (sign-out, a replayed refresh, five wrong PINs, a deleted
  account), and closes every socket of theirs (4000), on every instance. It is the server's own
  and never reaches a client. A freeze or a ban does the same when a task writes one (T-9.2,
  T-9.5; noted on both).
- **Measured** (`bench/realtime/sockets.py`, the founder's Mac, 8 October 2026, eleven runs):
  1,000 sockets open and 1,000 events delivered in every run; the API process held 104 to
  120 MB idle, 137 to 210 MB with every socket open, and 170 to 198 MB after the events. Under
  256 MB in every run, the worst by about 46 MB. A local measure, never Fly's.

**Amended 8 October 2026 by D-670 (T-7.5):** a relayed `typing` reads the database once, in a
short session closed before the next frame is read, after two checks in Redis. Between events a
socket still holds no connection.

**Corrected in planning:** Claude's plan (Q10) said Fly caps a machine at about 25 connections
unless `[http_service.concurrency]` says otherwise. Fly's own reference (read 8 October 2026)
says the default is `type = "connections"`, a `soft_limit` of 20, a load-balancing preference,
and no `hard_limit` at all. So nothing in `infra/` changed.

### D-600 · A charge is refused when its price isn't the one shown: `shown_price`, `PRICE_CHANGED` — Locked
**The decision (P-56; the founder, 8 October 2026, on the advisor's recommendation, Claude in a
separate chat, relayed by the founder):**
- **Every paid action's request carries `shown_price`**, the price in Velas the screen showed for
  it: `POST /swipes` (a Super Like), `POST /threads` (opening one, from a match or a private
  message) and `POST /threads/{id}/messages` (his first message in a Thread she opened, and each
  paid private message). An integer from 0; **optional, and absent means 0**, "no price was shown".
- **`pricing.service.charge()` compares it, never charges it.** It reads the price fresh, as
  before (T-5.2), and refuses with `PRICE_CHANGED` (409, `details.price`, the price now) when the
  two differ either way, before anything is debited; the transaction rolls back, so nothing the
  action would have written stays. What is debited is always the row's price (rule 6). `shown`
  is a required argument of `charge()`, so mypy refuses a new paid action that forgets it.
- **Only a priced action compares.** A like or a pass, a Thread that already exists (returned,
  nothing charged), a `client_msg_id` sent again, and a message that costs nothing aren't
  compared: nothing is charged, so nothing can surprise. A woman's price is 0 (D-098), so she
  needs nothing, and a screen that showed her a price is refused.
- **Why absent means 0, not "skip":** a client that forgets the field can't charge a man
  anything, so the check fails closed. Free actions, women and old clients need nothing.
  Required on all three bodies was the alternative; every free message would carry a 0 for it.

**Rejected:** a client price that is charged (rule 6); a field absent meaning "don't compare",
which fails open; a refusal only when the price went up (a screen that is wrong either way is
shown again, never guessed); a cache of prices with a version number (P-47, P-50: none is
measured slow).

**Where it reaches next** (pointers on each task's line): T-6.7's reveal, T-7.6's re-open and
Extend, T-7.9's unlock, the album request and T-8.9's gifts, which debit outside `charge()` and
so compare by hand. Built with T-6.5, the first screen where a man taps a price.

### D-601 · The deck's gestures: `@use-gesture/react` and `@react-spring/web` — Locked
**The decision (T-6.5; the founder, 8 October 2026):** the two libraries CLAUDE.md's pinned stack
names for the swipe, added now that the deck exists, pinned exactly as every web dependency is
(D-042, D-043): `@use-gesture/react` 10.3.1 and `@react-spring/web` 10.1.2, both runtime
`dependencies`. The gesture library measures the drag (movement, velocity, direction, and a tap
told apart from a drag); the spring library moves the card by writing its transform straight to
the element, never through a React render, which is what keeps a drag at the display's rate.
Both are used only in `web/src/components/discover/Deck.tsx`.

**Rejected:** a drag written by hand on pointer events (velocity, taps, pointer capture and
springs are each a small library's worth, and the stack already names these two); CSS
transitions alone (a release can't continue the finger's velocity); Framer Motion (not the
pinned stack, and larger).

### D-700 · An approved private photo's scored copy at a key of its own: `photos.scored_key` — Locked
**The decision (P-79 and P-301; the founder, 4 October 2026 for the separate key, 8 October 2026
for the column, on the advisor's recommendation):** when moderation approves a private photo, the
re-encoded bytes Sightengine scored are written to `scored/{user_id}/{photo_id}.jpg` in the private
bucket, and the row's new `scored_key` names it. Anything that shows a private photo reads that
key and never `raw_key`: T-8.4's album renders only from it, and the owner's own link to an
approved private photo is signed for it, so the owner sees what a viewer would.

**Why:** a presigned PUT URL lasts five minutes (D-027) and outlives `complete`, and moderation
wrote the scored bytes back over the upload (T-4.4, D-092). A PUT after approval, inside those
minutes, replaced the approved photo with bytes nobody scored, and a private photo had no other
copy. A public photo was already safe: its shown copy is `p/{photo_id}.jpg`, written from the
scored bytes. No PUT URL is ever made for anything outside `raw/`, so the scored copy is out of
the upload's reach, which closes the hole rather than narrowing it.

**A column, not a key worked out from the id:** the erasure's file list (D-500) and D-078's are
held by their tests to every `*_key` column on the tables they take, so the column puts the new
file on both lists or fails. A key derived in code would have needed both lists changed by hand,
with nothing to say so. The migration's downgrade refuses while any row has one.

**Not set** for a rejected private photo (shown to nobody), a public photo (its public copy is the
shown one) or the face photo (its owner's alone, D-391). Private photos approved before this
change have none; T-8.4 shows only rows that do.

**Rejected:** a key derived from the photo's id with no column (above); revoking the URL at
`complete` by moving the object (one more copy step on every upload, and a PUT racing the move
still lands); T-8.4 re-moderating each album photo when granted (a Sightengine call per grant, and
the window reopens at every grant).

### D-542 · Liked you: a handle, never the id, until he pays; one charge per pair — Locked
**The decision (T-6.7):**
- **Who is listed** (`GET /v1/likes`): everyone whose like or Super Like of you is still waiting
  on your swipe, from someone discovery's `visible_to` lets you see **mutually**, the radius aside,
  as a swipe back needs (D-492): no block either way, active, done, not hidden, not frozen,
  `shadow` only to the shadowed. Newest first. `GET /v1/likes/count` counts the same list.
- **A `LikeCard`** is `{handle, is_super, card, blurred_photo_url}`. A woman's `card` is always the
  person's `Card` (D-002). A man's is null until he has revealed them, and until then the only
  picture is `blurred_photo_url`, the server's blur of their main photo (D-543), or null.
- **`handle`, never the person's id.** An id would open their profile for free (`GET
  /users/{id}`, D-493), so nothing a man is sent before he pays names the person: not the item,
  not the cursor. The handle is the first 128 bits of HMAC-SHA256 over the viewer's id and the
  liker's, keyed by HKDF from `JWT_SECRET` (info `velora liked-you handle v1`), in hex, computed
  by the database (pgcrypto) so the list is ordered and paged by it. Another viewer's handle
  names nothing of yours. Rotating `JWT_SECRET` changes every handle: a list open across it gets
  `NOT_FOUND` on reveal and reloads.
- **`POST /v1/likes/{handle}/reveal`** replaces 04-API's `/likes/{user_id}/reveal`. It returns
  the `PublicProfile` (a view recorded, as D-493's), and charges the `liked_you_reveal` row's
  price through `pricing.charge`, so a woman pays nothing and a man the row's value, 1 Vela from
  8 October 2026 (P-370), its ledger ref the other person. **Once per pair, held twice:** the
  `liked_you_reveals` row is written first (`ON CONFLICT DO NOTHING`) and only the request that
  wrote it asks to pay; and the wallet keys the debit by the man, the reason and the other person
  (D-077), so a second debit would be a replay of the first, never a charge. A second reveal, at
  once or later, gets the profile free. Weakening the first layer alone stays green, since the
  wallet's key still holds: T-6.7's breaking runs found it, and T-5.1's break the key itself.
  The request carries `shown_price` (P-56, D-600), passed to `charge(..., shown=)`: a price that
  isn't the one his screen showed is `PRICE_CHANGED` with nothing charged or written. 402 when he can't afford it,
  `NOT_ALLOWED` when the row is switched off, each writing nothing. A handle that names no like
  still waiting on you, a malformed one, another's, or one blocked since, is the one `NOT_FOUND`.

**Why:** the plan's line ("for men, unrevealed entries return only a blurred thumbnail URL and no
name"), and the founder's answers to Q2 and Q3 of Claude's plan (the handle in the path; a count
endpoint, since a `Page` has no total, D-270).

**Rejected:** the user id in the path (the paywall leaks through `GET /users/{id}`); a total on
`LikeCardPage` (D-270's `Page` is items and a cursor); charging before writing the reveal's row
(two at once would both pay).

Approved by the founder on the advisor's recommendation (Claude, in a separate chat), relayed, 8
October 2026; written up by Claude.

### D-543 · The blurred copy: the server's, 24 pixels, under a key of its own — Locked
**The decision (T-6.7):** each approved public photo gets a blurred copy, made on the worker
(`blur_photo`, queued when the photo is approved): shrunk to 24 pixels on its longest side,
softened, spread back to 240, a JPEG at quality 70, in the public bucket at `b/<a fresh random
id>.jpg`, recorded in `photos.blur_key`. **Never a key derived from the photo's id:**
`p/<photo id>.jpg` is the photo itself, so a derived key would hand over the unblurred one. A
photo approved before T-6.7 gets its blur when `GET /likes` first needs it (the founder's Q7);
until then a man's tile shows no picture. The blur is deleted with the photo: at its owner's
removal, the underage deletion (D-078, `UNDERAGE_FILES`) and the erasure (D-503, `FILES`), each
of which a test holds to every `*_key` column. A photo removed while its blur was being made
keeps none: the file just written is deleted.

**Proved, not asserted:** YuNet, the selfie check's own detector (D-088), finds the face in each
NASA portrait in `tests/fixtures/faces` and none in its blur; and a blur, shrunk to 24 pixels and
spread back, is what it was.

**Why:** the plan's "server-generated blur, not CSS": a CSS filter over the real photo is one
DevTools click from the photo.

**Rejected:** a CSS blur; blurring on each request (a read of every photo per page); a key from
the photo's id.

Approved by the founder with Claude's plan for T-6.7 (Q7 its backfill), 8 October 2026, on the
advisor's recommendation (Claude, in a separate chat), relayed; written up by Claude.

### D-610 · A clearing is stamped with the newest message, under the Thread's lock — Locked
**The decision (T-7.8):** `thread_clears.cleared_at` is the newest message's `created_at` in the
Thread when the clearing runs, or the Thread's opening before any message: a point in the
messages' own clock, never the time of the tap. The clearing takes the Thread's row `FOR UPDATE`,
the lock every send takes (T-7.3), and reads the newest message in a statement of its own after
the lock is granted, so it sees what a send it waited for wrote. Everything that existed when it
ran is hidden from the one who cleared; everything written after it shows (03-SCHEMA: "if a new
message arrives after `cleared_at`, it reappears showing only messages newer than it").

**Why:** a message's `created_at` is its send's transaction start (the database's `now()`), taken
before the send waits for the Thread's row. A clearing stamped with its own time would hide for
good a message whose send began just before the tap and was written just after it: the clearer
never saw it, and it would never come back. The newest message's own stamp can't fall after a
message written later under the same lock. It reads no Python clock, so a frozen test clock
can't skew it either. `test_clear_race.py` forces the three ways a clearing and a send meet,
each overlap seen by Postgres itself (`pg_blocking_pids`).

**What remains, accepted:** two sends and a clearing within the same instant can still hide one
message from the clearer, when a send whose transaction began first takes the lock after
another's. The message is kept, the other person sees it, and a restore (D-611) shows it. It
is T-7.3's stamp, not the clearing's, and needs nothing now.

**Rejected:** `cleared_at = now()` (the case above); a clearing outside the Thread's lock (it
races a send under way); restamping messages after the lock (T-7.3's send, out of scope, and the
residue above doesn't earn it).

Approved by the founder on the advisor's recommendation (Claude, in a separate chat), relayed, 8
October 2026, as Claude's plan for T-7.8 proposed it; written up by Claude.

### D-611 · Restoring a clearing brings back the whole history; bulk clearing skips what isn't yours — Locked
**The decision (T-7.8):**
- **`DELETE /threads/{id}/clear` deletes the clearing row:** every message shows again, those
  before an earlier clearing too, not one step back. A clearing is the person's own view, never a
  moderation record (D-503 already erases them with the account), so deleting it keeps rule 12;
  the messages were never touched. Again, or on a Thread never cleared, it changes nothing (204).
- **`POST /threads/clear {thread_ids}` skips an id that isn't yours, or one across a block,** and
  counts only those cleared, never refusing the rest: a block landing while she is in select mode
  mustn't stop the others clearing. Each skipped id is as unknown as one nobody holds.
- **`{expired: true}` clears the Threads in your list that have expired by the clock** (D-560:
  `expired`, or `active` past `expires_at` before the cron catches up), never one already hidden
  with nothing newer; so its count is the prototype's "Clear expired (n)". Knots and private
  messages never expire, so it never reaches them.
- **Nothing tells the other person,** and nothing about the Thread or its messages changes: not
  `read_at` (their "Read"), not the status, expiry or knot taps (D-097, T-7.6, T-7.7 untouched).

**Why:** the undo toast (T-7.10) and the You tab's restore (T-9.8) both mean "show me my chat
again"; the whole history coming back is that, and an earlier clearing to step back to would need
a column for a case nobody asked for.

**Rejected:** restoring one step (a `previous_cleared_at` column and a migration); refusing the
whole bulk request on one id (`NOT_FOUND`).

Approved by the founder on the advisor's recommendation (Claude, in a separate chat), relayed, 8
October 2026, as Claude's plan for T-7.8 proposed it; written up by Claude.

### D-544 · `/@username`: a public link, off until its owner turns it on — Locked
**The decision (T-6.8):** `profiles.public_link`, a sixth privacy switch in `PATCH /me/settings`,
**false for everyone, those already here included**. `GET /v1/public-profiles/{username}` (public,
60 a minute per address) answers only when it is on and the profile is active, done, not hidden,
and in neither the `freeze` nor the `shadow` band (a shadowed person's page would invite strangers
to message someone they can't reach); every other case is the one `NOT_FOUND`. It says
`username`, `first_name`, `age` (null if hidden), `city` and `main_photo_url`, never an id, a
badge, a distance or the about, and records no view. The in-app profile doesn't read the switch.

**The page:** `/@username` is served by next.config's rewrite to `/share/[username]`, since an
`@` never begins a route segment (D-068); only a username follows the `@` (`USERNAME_IN_PATH`,
one pattern for the rewrite, the proxy's matcher and the static policy). It renders per request,
is a nonce route (D-541), is never indexed in any environment, and names `/@username` as its
canonical address. Someone signed in and onboarded is sent to the in-app profile, by the id
`GET /users/by-username` gives, whatever the switch says; anyone else sees the four facts and
"Join to message", or that the profile isn't public. Its group, `(share)`, restores a session,
which a marketing page never does (T-3.10).

**Why:** the founder's choice (8 October 2026): the worst case it closes is a woman's photo, first
name, age and city on the open internet without her choosing it.

**Rejected:** on by default; showing it with a profile hidden or shadowed; a public page for
anything past those four facts.
**Known, not closed here:** the page's server render asks the API from the web's server, so the
per-address limit counts that server, not each visitor (P-446). No screen sets the switch yet
(P-447).

The founder's addition to Claude's plan for T-6.8, 8 October 2026, on the advisor's recommendation
(Claude, in a separate chat), relayed; written up by Claude.

### D-545 · A profile has one route in the app, `/people/[id]` — Locked
**The decision (T-6.8):** a person's profile in the app is `/people/[id]`, the one route a
profile has: the deck's tap (T-6.5), search's rows (T-6.6), Liked you's revealed tiles (T-6.7) and
`/@username`'s redirect all lead there. It replaces the plan's `/u/[username]`, agreed with
T-6.5's session (8 October 2026, the founder's rule: never two routes for one profile). The screen
is 08-DESIGN §8's: the gallery with its dots, the thread, name, age, the badge (D-393, never
`is_verified`) and its note, "Online now", city, distance and hometown, the intents and interests
as chips from `en.ts` by id (P-26), the about, the kudos when shown, the private album's count,
the ⋯ menu, and Like. **Waiting for their tasks:** "Open thread" (P-440), "Ask to view" (P-441),
and Report and Block in the ⋯ menu (P-442); until then the ⋯ menu shares the `/@username` link.
Your own profile has no action bar.

**Why:** one route means one place a profile's rules are applied, and no link that one screen
makes and another doesn't know.

**Rejected:** `/u/[username]` (the profile is opened by id everywhere but the share page, and an
id reaches a hidden profile its matches may open, D-493).

Agreed between T-6.5's and T-6.8's sessions, 8 October 2026, under the founder's rule; written up
by Claude.

### D-670 · Typing reads the database once a relay, in a short session; read receipts to the other person alone — Locked
**The decision (T-7.5; the founder, 8 October 2026, on the advisor's recommendation (Claude, in a
separate chat), relayed by the founder; the shape Claude's, in T-7.5's plan):**
- **Typing** (02-ARCHITECTURE §6): the client's `{type: "typing", data: {thread_id}}` reaches the
  other person in that Thread as `{thread_id}` and nothing more, never the typist's own sockets.
  Two checks in Redis come first, both through `core/ratelimit.py`: **one a Thread every 3
  seconds** (§6's throttle) and **40 a minute in all**, so a client naming Thread after Thread
  can't turn typing into a stream of database reads. Only then does the gateway open **one short
  session** (`core/db.py`'s `session_opener`) to ask whether the typist is one of the Thread's two
  with no block either way (T-7.3's `thread_of`), and close it before it publishes. Anything
  else (a malformed envelope, someone else's Thread, a block, a throttled or capped one) is
  dropped quietly, and the socket stays open: §6 has no error frame. A relay waits at most 1
  second; a failure is logged and never ends the socket.
- **This amends D-557's "the gateway reads no database".** The socket still holds no
  connection between events: each relay's session takes one from the pool and hands it back
  before the next frame is read. At most 40 reads a minute a user.
- **Read receipts:** `POST /v1/threads/{id}/read {up_to_message_id}` → 204 marks the other
  person's messages not yet read, up to and including the one named, after the reader's
  clearing, with `clock.now()`. A `read_at` once set never moves. `message.read`
  (`{thread_id, up_to_message_id, read_at}`, naming the newest message it marked) goes to **the
  other person alone**, and only when something was marked; the reader's other devices read
  their counts from the list. Neither event carries an expiry or a price, whoever reads or types
  (D-554). A message from before the reader's clearing is never marked (they never saw it, so
  her "Not seen yet" stays true), and naming one is `NOT_FOUND`, as is anyone else's Thread, one
  across a block, or another Thread's message. Clearing itself never touches `read_at` (T-7.8).
  The route keeps `current_user`'s 300 a minute: a read that marks nothing tells nobody.

**Rejected:** a REST `POST /threads/{id}/typing` (§6 puts typing on the socket, and a request a
keystroke is heavier than a frame); caching who may hear whom in Redis (a block would go unseen
until the entry expired); a session held for the socket's life (P-52, D-557); `message.read` to
the reader's own sockets too (§6 names the other person).

## Adding a decision

Append `D-0NN · Title — Locked|Open`, with Decision, Why, Rejected. Never edit a Locked entry —
supersede it with a new one that references the old ID.
