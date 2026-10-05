# 03 · Database schema

PostgreSQL 16. Extensions: `postgis`, `pg_trgm`, `pgcrypto`, `citext`.
Conventions: every table has `created_at timestamptz not null default now()`; mutable tables also
have `updated_at` (set by trigger `set_updated_at`). PKs are `uuid default gen_random_uuid()` unless
noted. FKs are `on delete restrict` unless noted — we don't hard-delete users (see `users.status`),
with one exception: an under-18 refusal deletes the new account, and its rows in every table the
app role may delete from, and keeps only the number's hash (D-072, D-078).

The Alembic migrations in Sprint 1 create **everything below in this order**.

**Roles (T-1.22):** migrations run as the owner; the app connects as a login role in `velora_app`,
which reads and writes rows and nothing more — no TRUNCATE, no DDL, no UPDATE or DELETE on
`ledger_entries` and `audit_log`, no DELETE on `payments`, `messages` or `reports` (rule 12). New
tables get SELECT, INSERT, UPDATE and DELETE by default, so **a new append-only or never-deleted
table's migration revokes what the app shouldn't have**; `tests/test_app_role.py` fails for any
table whose `refuse_change()` trigger the app role could reach. Where the extensions live in an
`extensions` schema (Supabase), `velora_app` also has USAGE on it, or it couldn't use `citext`,
`geography` or PostGIS; locally they're in `public`.

---

## Enums

```sql
gender_t          ('male','female')
seeking_t         ('women','men','everyone')
onboarding_t      ('dob','gender','seeking','profile','username','about','photos','interests','pin','selfie','done')
user_status_t     ('active','paused','frozen','banned','deleted')
role_t            ('user','moderator','admin')
photo_kind_t      ('public','private','selfie')
review_status_t   ('pending','approved','rejected')
swipe_dir_t       ('like','pass','super')
thread_status_t   ('active','expired','knotted')
thread_origin_t   ('match','dm')
msg_kind_t        ('text','voice','system')
album_req_t       ('pending','granted','declined','revoked')
report_reason_t   ('fake','scam','harass','sexual','minor','other')
report_status_t   ('open','actioned','dismissed')
kudos_t           ('great_conversation','genuinely_funny','easy_to_talk_to','really_thoughtful')
ledger_reason_t   ('purchase','purchase_bonus','referral_reward','admin_grant','refund','gift',
                   'refund_banned_partner','refund_album_declined',
                   'thread_open','dm_open','thread_reopen','voice_unlock','album_request',
                   'super_like','liked_you_reveal',
                   'thread_extend','dm_message')   -- the last two T-5.2's (D-251)
payment_status_t  ('created','paid','failed','refunded')
fraud_band_t      ('normal','monitor','shadow','freeze')
ban_kind_t        ('phone_hash','device_id')
```

Intent is not an enum: it is the `intents` catalogue, picked 1 to 3 per user (D-041, P-25).

---

## 1. Identity

### users
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| phone_hash | text not null unique | HMAC-SHA256 of E.164, keyed by `PHONE_PEPPER` (D-061) |
| phone_enc | bytea not null | E.164, Fernet-encrypted in the API, never by the database (D-061) |
| gender | gender_t null | immutable after set (trigger) |
| dob | date null | immutable after set (trigger) |
| role | role_t not null default 'user' | |
| status | user_status_t not null default 'active' | |
| onboarding_step | onboarding_t not null default 'dob' | moves to `done` only for a man or `is_verified` (trigger `users_done_needs_a_match`, D-310) |
| is_verified | boolean not null default false | the selfie matched the profile's photos (T-4.5, D-260); never "verified" in copy (D-262) |
| pin_hash | text null | argon2id over a pepper kept off the database (D-062) |
| pin_failed | smallint not null default 0 | |
| referral_code | citext unique not null | generated at creation |
| last_active_at | timestamptz null | updated at most once per minute |
| deleted_requested_at | timestamptz null | 30-day deletion window |

Indexes: `(status, last_active_at desc)`.

### sessions
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users on delete cascade | |
| family_id | uuid not null | rotation family |
| token_hash | text not null unique | SHA-256 of refresh token |
| user_agent | text | stays empty: nothing reads it, and `/privacy` doesn't list it (D-067) |
| ip | inet | stays empty, likewise (D-067) |
| expires_at | timestamptz not null | 30 days from this session's own rotation (D-067) |
| auth_time | timestamptz not null | when the family signed in, copied unchanged at each rotation: every access token's `auth_time` (D-071) |
| revoked_at | timestamptz null | |
| replaced_by | uuid null | next session in the family |

Index: `(user_id) where revoked_at is null`.

### banned_identities
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| kind | ban_kind_t | |
| value | text | hash |
| reason | text | e.g. `underage`, `ban` |
Unique `(kind, value)`.

---

## 2. Profile

### profiles  (1:1 with users, pk = user_id)
| column | type | notes |
|---|---|---|
| user_id | uuid pk fk users | |
| first_name | text | 1–30 chars |
| username | citext unique | `^[a-z0-9._]{4,20}$`. ASCII only, and load-bearing: first names take every script, so look-alike letters can copy a display name, but never an @username (P-59) |
| about | text | 40–300 chars |
| hometown | text | ≤ 40 |
| city | text | ≤ 40 |
| area_id | uuid null fk areas | manual fallback |
| location | geography(Point,4326) null | |
| location_updated_at | timestamptz | |
| seeking | seeking_t | |
| is_hidden | boolean default false | privacy: hide profile |
| hide_age | boolean default false | |
| hide_distance | boolean default false | |
| show_kudos | boolean default true | |
| show_gifts | boolean default true | received gifts on profile |
| completeness | smallint default 0 | 0–100, computed by service: 50, and 10 for each approved public photo after the first, set when onboarding finishes (T-4.8, D-310); kept current after that by P-210 |

Indexes: `GIST(location)`, `GIN(username gin_trgm_ops)`, `GIN(first_name gin_trgm_ops)`,
`(is_hidden)`. Intent lives in `profile_intents` (D-041).

### areas  (seed data for location fallback)
`id uuid pk, city text, name text, centroid geography(Point,4326)`. Unique `(city, name)`.
Seed: 17 Phagwara areas (D-013), from P-38, which replaced T-1.14's 40 Bengaluru neighbourhoods.
Drafted by Claude from OpenStreetMap; each centroid is a point inside the locality, not a measured
centre, and its migration (`bc589ac265c2`) says, row by row, where it came from and whether the
founder confirmed it. The two closest are 510 m apart.

### interests  (seed: 24, T-1.14)
`id smallint pk, slug text unique, label text`.
Who you are — hobbies and vibe. Ids 1–24 are fixed in seed order, because the API takes
`interest_ids`; slugs are the labels in kebab-case (`filter-coffee`).

### profile_interests
`user_id uuid fk, interest_id smallint fk, pk(user_id, interest_id)`. Exactly 5 per user — enforced
in the service.

### intents  (seed: 10, P-25)
`id smallint pk, slug text not null unique, label text not null`.
What you're looking for (D-041). Ids 1–10 are fixed in seed order, because the API takes
`intent_ids`; slugs are the labels in kebab-case (`something-serious`). Labels are sentence case,
like interests — both show as chips on the same profile.

### profile_intents
`user_id uuid fk users, intent_id smallint fk intents, pk(user_id, intent_id)`. 1 to 3 per user —
enforced in the service. Index `(intent_id)`: discovery filters on intent, matching any overlap.

### photos
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users | |
| kind | photo_kind_t | |
| position | smallint | 0–5 for public; 0 = main |
| raw_key | text | private bucket key |
| public_key | text null | set when approved (public kind only) |
| status | review_status_t default 'pending' | |
| reject_reason | text null | |
| moderation | jsonb | every score the decision read (T-4.4): provider, models, `minor` (the highest face's, kept below the threshold too, so D-101's is revisited from real scores), `explicit`, `faces`, `artificial_faces`, `text_artificial`; never the image or the request. A selfie's (T-4.5, D-263): `threshold`, `decided_by` (`wake`, `queue`, or `seed`), `provider`, `faces`, `best`, and `compared` (each photo's id and cosine similarity, exactly); later `review` (the founder's `same`/`different`, D-264) |
| width, height | int null | |

Indexes: `(user_id, kind, position)`, `(status) where status='pending'`.
Unique `(user_id, position) where kind='public' and status <> 'rejected'`.

### verifications
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| selfie_photo_id | uuid fk photos | |
| challenge | text | `none` since T-4.5: no pose is asked (D-263) |
| liveness_ok | boolean null | null: nothing checks liveness until T-4.11 |
| similarity | numeric(5,2) null | empty since T-4.5: two places can't hold a cosine near 0.363 (an approved 0.3634 would read 0.36). The exact numbers are in the selfie's `photos.moderation` (D-263); widening is P-164 |
| status | review_status_t default 'pending' | the selfie photo's own status and `reject_reason` follow it |
Index `(user_id, created_at desc)`.

---

## 3. Discovery and matching

### swipes
| column | type | notes |
|---|---|---|
| swiper_id | uuid fk users | |
| target_id | uuid fk users | |
| dir | swipe_dir_t | |
| created_at | timestamptz | |
PK `(swiper_id, target_id)`. Index `(target_id, dir) where dir in ('like','super')` — powers "liked you".

### profile_views
`viewer_id uuid fk users, viewed_id uuid fk users, last_viewed_at timestamptz, view_count int default 1, pk(viewer_id, viewed_id)`.
Index `(viewed_id, last_viewed_at desc)`. Not written when the viewer is incognito (backlog B-7).

### liked_you_reveals
`viewer_id uuid fk users, liker_id uuid fk users, created_at, pk(viewer_id, liker_id)`.

### matches
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_low | uuid fk | smaller uuid of the pair |
| user_high | uuid fk | |
| thread_id | uuid null fk threads | set when a thread is opened |
Check `user_low < user_high`. Unique `(user_low, user_high)`.

---

## 4. Conversations

### threads  (one row per pair, forever)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_low | uuid fk | |
| user_high | uuid fk | |
| origin | thread_origin_t | |
| opened_by | uuid fk users | |
| status | thread_status_t default 'active' | |
| expires_at | timestamptz null | null once knotted |
| low_knot_at | timestamptz null | user_low tapped tie |
| high_knot_at | timestamptz null | user_high tapped tie |
| knotted_at | timestamptz null | both tapped |
| expiry_warned_at | timestamptz null | |
| last_message_at | timestamptz null | |
| message_count | int default 0 | for masking + call gates |
Check `user_low < user_high`. Unique `(user_low, user_high)`.
Check `status <> 'knotted' OR (knotted_at IS NOT NULL AND expires_at IS NULL)` — a Knot never
carries an expiry, so the expiry cron can never kill a conversation both people were told is
permanent. Check `status <> 'active' OR expires_at IS NOT NULL` — an active thread always expires;
every way into `active` (open, reopen, untie) sets a fresh expiry of `app_config.thread_hours`
(seeded 24) — read the setting, never hardcode the number (T-1.10).
Indexes: `(expires_at) where status='active'`, `(user_low, last_message_at desc)`,
`(user_high, last_message_at desc)`.

### messages
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| thread_id | uuid fk threads | |
| sender_id | uuid fk users | |
| kind | msg_kind_t | |
| body | text null | displayed text (masked) ≤ 2000 |
| body_raw | text null | original, moderation only, never returned to users |
| media_key | text null | voice note in private bucket |
| duration_s | smallint null | voice |
| client_msg_id | uuid not null | dedupe |
| masked | boolean default false | |
| read_at | timestamptz null | |
Unique `(sender_id, client_msg_id)`. Index `(thread_id, created_at desc)`.

### message_unlocks  (men paying to hear a voice note)
`user_id uuid fk users, message_id uuid fk messages, created_at, pk(user_id, message_id)`.

### thread_clears  (one-sided hide)
`user_id uuid fk users, thread_id uuid fk threads, cleared_at timestamptz, pk(user_id, thread_id)`.
A cleared thread is hidden from that user's list; if a new message arrives after `cleared_at`,
it reappears showing only messages newer than `cleared_at`.

---

## 5. Album, kudos, safety

### album_requests
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| requester_id | uuid fk users | |
| owner_id | uuid fk users | |
| status | album_req_t default 'pending' | |
| credits_charged | int not null default 0 | refunded on decline; check `>= 0` |
| decided_at | timestamptz null | |
Unique `(requester_id, owner_id) where status in ('pending','granted')`. Check `requester_id <> owner_id`.

### kudos
`id uuid pk, from_id uuid fk users, to_id uuid fk users, kind kudos_t, thread_id uuid fk threads, created_at`.
Unique `(from_id, to_id)`. Check `from_id <> to_id` — self-kudos would manufacture social proof. Only allowed after the thread has ≥ 6 messages.

### gifts  (catalogue, seeded)
| column | type | notes |
|---|---|---|
| id | text pk | slug, e.g. `rose` |
| label | text not null | shown in UI |
| asset | text not null | emoji or icon key |
| credits | int not null check (credits >= 0) | 0, 2 or 4 as seeded; 5, 10, 15 or 20 by D-231 |
| sort | smallint not null default 0 | display order |
| active | boolean not null default true | |

Seed (D-016): `smile` 0 · `wave` 0 · `rose` 2 · `coffee` 2 · `chocolate` 4 · `teddy` 4.
Labels are the ids capitalised; assets are emoji (😊 👋 🌹 ☕ 🍫 🧸).
**Since T-5.2** (D-231, D-252), by a data migration of its own: four active gifts, `coffee` 5 ·
`rose` 10 · `chocolate` 15 · `teddy` 20, sorted 1–4 and repriced in place (`gift_sends` copies
the price at send time). `smile` and `wave` are retired, `active = false`, never deleted (rule 12).
Fifteen free sends a week replace `gift_free_daily_limit` (`app_config`).

### gift_sends
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| sender_id | uuid fk users | |
| recipient_id | uuid fk users | |
| gift_id | text fk gifts | |
| credits_charged | int not null default 0 | copied at send time; check `>= 0` |
| thread_id | uuid null fk threads | set if a thread already existed |
| created_at | timestamptz | |
Indexes: `(recipient_id, created_at desc)`, `(sender_id, created_at desc)`,
`(sender_id, recipient_id, gift_id, created_at desc)` for the cooldown check.
Check `sender_id <> recipient_id`. No check pins prices to particular values — prices are data (D-016).

### blocks
`blocker_id uuid fk users, blocked_id uuid fk users, created_at, pk(blocker_id, blocked_id)`. Index `(blocked_id)`.
Check `blocker_id <> blocked_id`.

### reports
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| reporter_id | uuid fk users | |
| reported_id | uuid fk users | |
| reason | report_reason_t | |
| details | text null | ≤ 500 (check) |
| thread_id | uuid null fk threads | context |
| status | report_status_t default 'open' | |
| action | text null | check: one of `freeze` / `ban` / `warn` / `none` |
| resolved_by | uuid null fk users | |
| resolved_at | timestamptz null | |
Indexes: `(status, created_at)`, `(reported_id, created_at desc)`.
Check `reporter_id <> reported_id` — a self-report could probe the auto-freeze rule (D-031).

### fraud_scores
`user_id uuid pk fk users, score smallint not null default 0, band fraud_band_t not null default 'normal', signals jsonb, updated_at`.
Check `score between 0 and 100` (D-031). Bands are policy, so no check ties them to the score.

### fraud_events
`id uuid pk, user_id uuid fk users, signal text not null, weight smallint not null, meta jsonb, created_at`.
Index `(user_id, created_at desc)`.
A signal, never a verdict. `possible_minor_photo_score` (T-4.4, D-093): a model's score that one
photo may show a minor, weight 0 until T-9.2 says what it may count for; `meta` is `{what, model,
score}`, and never the image or which photo.

---

## 6. Money

Users see Velas (D-049). Every column, table and constraint here keeps the neutral name `credits`
(`credits`, `bonus_credits`, `credits_charged`, `credit_packs`), so a rename never needs a migration.

### wallets
| column | type | notes |
|---|---|---|
| user_id | uuid pk fk users | created with the user |
| balance | int not null default 0 | **CHECK (balance >= 0)** |
| updated_at | timestamptz | |

Trigger `wallets_only_men` (T-5.1, D-076): before any insert or update that leaves a balance other
than 0, refuses unless the owner's gender is `male`, so moving a wallet's `user_id` can't hand a
balance to anyone else either. Written only by `wallet.service` (rule 5).

### ledger_entries  (append-only)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users | |
| delta | int not null | CHECK (delta <> 0) |
| balance_after | int not null | CHECK (balance_after >= 0) |
| reason | ledger_reason_t not null | |
| ref_type | text null | e.g. `thread`, `payment` |
| ref_id | uuid null | polymorphic, so no fk |
| idempotency_key | text not null unique | |
| created_at | timestamptz | |
Index `(user_id, created_at desc)`. Check `(ref_type IS NULL) = (ref_id IS NULL)`.
Trigger `ledger_no_update_delete`: raises on UPDATE or DELETE. Trigger `ledger_no_truncate`
(statement-level): raises on TRUNCATE, which skips row triggers — without it one command could
wipe the money record. Both raise `restrict_violation` (23001) (T-1.12).

**The ledger's shape (T-5.1, D-077).** Each reason has one direction and exactly one `ref_type`:

| reason | direction | `ref_type` | the event in the key |
|---|---|---|---|
| `purchase`, `purchase_bonus` | credit | `payment` | the payment's id |
| `referral_reward` | credit | `referral` | the referee's id (`referrals`' key) |
| `admin_grant` | credit | `audit_log`, **optional** | named by the caller |
| `refund` | credit | `ledger_entry` | refused by the service until a task gives it a meaning |
| `refund_banned_partner` | credit | `ledger_entry` | unused since D-230: never repurposed |
| `refund_album_declined` | credit | `album_request` | unused since D-230: never repurposed |
| `gift` | debit | `gift_send` | the send's id |
| `thread_open`, `dm_open` | debit | `thread` | the thread's id |
| `thread_reopen` | debit | `thread` | named by the caller |
| `thread_extend` | debit | `thread` | named by the caller: Extend repeats for one Thread (D-250, D-251) |
| `dm_message` | debit | `message` | the message's id: each private message after the first, once (D-251) |
| `voice_unlock` | debit | `message` | the message's id |
| `album_request` | debit | `album_request` | the request's id |
| `super_like`, `liked_you_reveal` | debit | `user` | the other person: once per pair, ever, as a swipe is (the founder, 3 October 2026) |

- `ck_ledger_entries_reason_direction`: credits positive, debits negative. Both lists are
  allowlists, so a reason added to `ledger_reason_t` can't be written until a migration names it.
- `ck_ledger_entries_ref_required`: every reason but `admin_grant` names its ref.
- `ck_ledger_entries_reason_ref_type`: the pinned `ref_type` or none, so a credit naming a payment
  can only be `purchase` or `purchase_bonus`.
- `uq_ledger_entries_one_per_event`: partial unique index on `(user_id, reason, ref_type, ref_id)`
  where the reason is not `admin_grant`, `thread_reopen` or `thread_extend`, the three that repeat
  for one ref (the third since T-5.2's a1d7de534ef7): one
  entry per event, even if a key is built wrong.
- `idempotency_key` is `{user_id}:{reason}:{event}`, built by the wallet module, never by a caller;
  a client's `Idempotency-Key` only ever fills the event part.
- Trigger `ledger_entries_only_men` (D-076): before every insert, refuses unless the user's gender
  is `male`. With `wallets_only_men`, one function, `refuse_credits_unless_male()`; an allowlist,
  so a user with no gender yet is refused too. Both raise `check_violation` (23514) naming the
  trigger as the constraint.

`wallet/rules.py` holds the same table, and `tests/modules/wallet/test_guards.py` proves the
database agrees with it, reason by reason. Change one, change both.

### action_prices
`action text pk, credits int not null check (credits >= 0), active boolean not null default true, updated_at`.
Seed (D-004): the keys are the seven debit reasons of `ledger_reason_t` — `thread_open` 5 ·
`dm_open` 5 · `thread_reopen` 3 · `voice_unlock` 5 · `album_request` 5 · `super_like` 5 ·
`liked_you_reveal` 20. The free knot actions have no row: permanence is never bought (D-003).
**Since T-5.2** (D-098, D-231, D-250), by data migrations of its own: `thread_reopen` 2 and
`thread_extend` 10 (Extend), in one migration since they move together (D-098); `dm_open` 8 (the
first private message) and `dm_message` 2 (each one after it); `album_request` 1 (viewing private
pictures). `super_like` stays 5, by default: it isn't swiping (D-250). Read only through
`pricing.service.price_for()` (T-5.2): fresh, in the debit's transaction, 0 for a woman, a missing
row a 500 and an inactive one `NOT_ALLOWED`.

### credit_packs
`id text pk, credits int not null, price_paise int not null, bonus_first_pct smallint not null default 20,
active boolean not null default true, sort smallint not null default 0, variant text not null default 'A'`
(for the beta price test). Checks — invariants, not policy: `credits > 0`, `price_paise > 0`,
`bonus_first_pct between 0 and 100`. The values themselves stay free to tune (D-005).
Seed (D-005): `pack-25` 25/₹1,500 · `pack-50` 50/₹2,500 · `pack-75` 75/₹3,375 · `pack-100`
100/₹4,000 (variant A, sort 1–4); `entry-25` 25/₹999 (variant B, the beta price test, T-10.4).
**Since T-5.2** (D-099, D-231, D-250), by data migrations of its own: variant A's active packs are
`pack-30` 30/₹1,500 · `pack-100` 100/₹4,500 (repriced in place) · `pack-250` 250/₹6,000 ·
`pack-450` 450/₹10,000, sort 1–4, with the 20% bonus kept. `pack-25`, `pack-50`, `pack-75` and
`entry-25` are retired, `active = false`, never deleted (`payments` points at packs): `entry-25`
was ₹40 a Vela, below the ladder's ₹50 (D-250), so variant B has no active pack (T-8.1).

### payments
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users | |
| pack_id | text fk credit_packs | |
| amount_paise | int not null | copied from pack at order time; check `> 0` |
| credits | int not null | copied; check `> 0` |
| bonus_credits | int not null default 0 | check `>= 0` |
| provider | text not null default 'razorpay' | |
| provider_order_id | text unique not null | |
| provider_payment_id | text unique null | **idempotency anchor** |
| status | payment_status_t not null default 'created' | |
| paid_at | timestamptz null | |
| raw_webhook | jsonb null | the last verified payload's allowlisted fields only: ids, amount, currency, status, method, error code, timestamps; never the payer's email, phone, UPI ID, card or bank details (T-8.2) |

Check `status NOT IN ('paid','refunded') OR (provider_payment_id IS NOT NULL AND paid_at IS NOT NULL)` —
once money has moved the idempotency anchor exists, or a payment could be credited twice.
Triggers `payments_no_delete` and `payments_no_truncate`: payments are never hard-deleted
(rule 12); status updates are allowed. Both raise `restrict_violation` (23001) (T-1.12).

### refund_requests
`id uuid pk, user_id uuid fk users, payment_id uuid fk payments, reason text, status text not null default 'open', created_at`.
`status` is free text on purpose: T-8.3 owns the refund workflow and defines its values.

### referrals
`referee_id uuid pk fk users, referrer_id uuid fk users, rewarded_at timestamptz null, created_at`.
Check `referee_id <> referrer_id` — a self-referral would farm Velas on both sides of one account.
Reward (both get Velas) only after the referee's first paid purchase or selfie verification.

---

## 7. Notifications

### push_subscriptions
`id uuid pk, user_id uuid fk users, endpoint text not null unique, p256dh text not null,
auth text not null, last_ok_at timestamptz null, created_at`.
One subscription per endpoint, across accounts. `p256dh` and `auth` are the subscription's keys:
never logged, never returned (rule 15).

### notification_prefs  (pk user_id)
`user_id uuid pk fk users`; `match, message, likes, knot, expiry, balance, generic_text` —
booleans, not null, defaults true except `generic_text` false; `updated_at`.
The column is `likes` because `like` is a reserved word in Postgres. The model attribute and the
API field of `Prefs` (04-API) stay `like` (T-1.13).

### notifications  (in-app list)
`id uuid pk, user_id uuid fk users, kind text not null, payload jsonb null, read_at timestamptz null,
created_at`. Index `(user_id, created_at desc)`.

---

## 8. Ops

### audit_log  (append-only)
`id uuid pk, actor_id uuid not null fk users, action text not null, target_type text null,
target_id uuid null, meta jsonb null, created_at`.
`target_id` is polymorphic, so no fk. Check `(target_type IS NULL) = (target_id IS NULL)`, as on
`ledger_entries.ref_*`. `actor_id` is never null — null could not tell "the system did it" from
"a bug forgot to set it"; automated actions use a dedicated system user, created by T-9.2.
Triggers `audit_log_no_update_delete` and `audit_log_no_truncate` (statement-level) reuse T-1.12's
`refuse_change()` and raise `restrict_violation` (23001): the person with a reason to erase the
trace is exactly the person with admin access (T-1.13).

### app_config  (key/value, cached 60 s)
`key text pk, value jsonb not null, updated_at`. Seeds: `swipe_daily_limit_men=50`,
`discovery_radius_km=25`, `thread_hours=24`, `mask_first_n_messages=20`, `kudos_min_messages=6`,
`gift_free_daily_limit=3` (replaced by T-5.2's data migration with `gift_free_weekly_limit=15`,
fifteen free sends a week, D-231),
`gift_same_recipient_cooldown_h=24`; and, by its own data migration
(T-3.2), `otp_sms_daily_cap=500`: the most Path B sign-in codes sent in one IST day across every
number, ₹100 a day at D-035's unconfirmed ₹0.20 an SMS (D-066).
Two settings are also promised in copy, in `web/src/i18n/en.ts`, written out because copy is a
promise, not a computation. Change the copy with the setting:
- `thread_hours`: the landing page ("Threads last a day", "24-hour", T-2.1), `/terms` ("lasts
  a day", T-2.2), and the share image, whose pixels say "Threads last a day"
  (`web/src/app/opengraph-image.jpg`, T-2.4): the easiest one to forget. 08-DESIGN §7 says how to
  regenerate it.
- `mask_first_n_messages`: `/terms` and `/privacy` ("first 20 messages", T-2.2).

### waitlist
`id uuid pk, email citext not null unique, city text null, created_at`.
Unique ignores case (citext). No format check in the database: T-2.3 validates in the API.

---

## 9. Seed data (Sprint 1, `alembic` data migration + `make seed` for dev)

- `interests` — 24 rows
- `intents` — 10 rows (P-25, D-041)
- `gifts` — 6 rows (D-016)
- `action_prices`, `credit_packs`, `app_config` — from D-004 / D-005 / §8
- `areas` — 40 neighbourhoods for the launch city
- **dev only** (`make seed`, T-1.15): the 20 prototype profiles (10 women, 10 men), a test man,
  a test woman and a moderator, written only to the local stack's database (D-064). Their photos
  arrive with T-4.4, verification rows with T-4.5, and the test man's 60 Velas with T-5.1.

The reference data is two data migrations — T-1.14's, and P-25's for intents — with every insert
`ON CONFLICT DO NOTHING`: re-running them changes nothing and never resets a value tuned since.
