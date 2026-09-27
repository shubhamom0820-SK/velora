# 03 · Database schema

PostgreSQL 16. Extensions: `postgis`, `pg_trgm`, `pgcrypto`, `citext`.
Conventions: every table has `created_at timestamptz not null default now()`; mutable tables also
have `updated_at` (set by trigger `set_updated_at`). PKs are `uuid default gen_random_uuid()` unless
noted. FKs are `on delete restrict` unless noted — we don't hard-delete users (see `users.status`).

The Alembic migrations in Sprint 1 create **everything below in this order**.

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
                   'super_like','liked_you_reveal')
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
| phone_hash | text not null unique | peppered SHA-256 of E.164 |
| phone_enc | bytea not null | pgcrypto-encrypted E.164 |
| gender | gender_t null | immutable after set (trigger) |
| dob | date null | immutable after set (trigger) |
| role | role_t not null default 'user' | |
| status | user_status_t not null default 'active' | |
| onboarding_step | onboarding_t not null default 'dob' | |
| is_verified | boolean not null default false | selfie verified |
| pin_hash | text null | argon2 |
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
| user_agent | text | truncated 200 |
| ip | inet | |
| expires_at | timestamptz not null | |
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
| username | citext unique | `^[a-z0-9._]{4,20}$` |
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
| completeness | smallint default 0 | 0–100, computed by service |

Indexes: `GIST(location)`, `GIN(username gin_trgm_ops)`, `GIN(first_name gin_trgm_ops)`,
`(is_hidden)`. Intent lives in `profile_intents` (D-041).

### areas  (seed data for location fallback)
`id uuid pk, city text, name text, centroid geography(Point,4326)`. Unique `(city, name)`.
Seed: 40 Bengaluru neighbourhoods (D-013's default), centroids approximate to about 1 km (T-1.14).

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
| moderation | jsonb | provider response summary |
| width, height | int null | |

Indexes: `(user_id, kind, position)`, `(status) where status='pending'`.
Unique `(user_id, position) where kind='public' and status <> 'rejected'`.

### verifications
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| selfie_photo_id | uuid fk photos | |
| challenge | text | the random pose asked for |
| liveness_ok | boolean null | |
| similarity | numeric(5,2) null | vs approved photos |
| status | review_status_t default 'pending' | |
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
Check `status <> 'knotted' OR (knotted_at IS NOT NULL AND expires_at IS NULL)` — a Velora never
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
| credits | int not null check (credits >= 0) | 0, 2 or 4 |
| sort | smallint not null default 0 | display order |
| active | boolean not null default true | |

Seed (D-016): `smile` 0 · `wave` 0 · `rose` 2 · `coffee` 2 · `chocolate` 4 · `teddy` 4.
Labels are the ids capitalised; assets are emoji (😊 👋 🌹 ☕ 🍫 🧸).

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

---

## 6. Money

### wallets
| column | type | notes |
|---|---|---|
| user_id | uuid pk fk users | created with the user |
| balance | int not null default 0 | **CHECK (balance >= 0)** |
| updated_at | timestamptz | |

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

### action_prices
`action text pk, credits int not null check (credits >= 0), active boolean not null default true, updated_at`.
Seed (D-004): the keys are the seven debit reasons of `ledger_reason_t` — `thread_open` 5 ·
`dm_open` 5 · `thread_reopen` 3 · `voice_unlock` 5 · `album_request` 5 · `super_like` 5 ·
`liked_you_reveal` 20. The free knot actions have no row: permanence is never bought (D-003).

### credit_packs
`id text pk, credits int not null, price_paise int not null, bonus_first_pct smallint not null default 20,
active boolean not null default true, sort smallint not null default 0, variant text not null default 'A'`
(for the beta price test). Checks — invariants, not policy: `credits > 0`, `price_paise > 0`,
`bonus_first_pct between 0 and 100`. The values themselves stay free to tune (D-005).
Seed (D-005): `pack-25` 25/₹1,500 · `pack-50` 50/₹2,500 · `pack-75` 75/₹3,375 · `pack-100`
100/₹4,000 (variant A, sort 1–4); `entry-25` 25/₹999 (variant B, the beta price test, T-10.4).

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
| raw_webhook | jsonb null | last verified payload |

Check `status NOT IN ('paid','refunded') OR (provider_payment_id IS NOT NULL AND paid_at IS NOT NULL)` —
once money has moved the idempotency anchor exists, or a payment could be credited twice.
Triggers `payments_no_delete` and `payments_no_truncate`: payments are never hard-deleted
(rule 12); status updates are allowed. Both raise `restrict_violation` (23001) (T-1.12).

### refund_requests
`id uuid pk, user_id uuid fk users, payment_id uuid fk payments, reason text, status text not null default 'open', created_at`.
`status` is free text on purpose: T-8.3 owns the refund workflow and defines its values.

### referrals
`referee_id uuid pk fk users, referrer_id uuid fk users, rewarded_at timestamptz null, created_at`.
Check `referee_id <> referrer_id` — a self-referral would farm credits on both sides of one account.
Reward (both get credits) only after the referee's first paid purchase or selfie verification.

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
`gift_free_daily_limit=3`, `gift_same_recipient_cooldown_h=24`.

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
- **dev only** (`make seed`): the 20 prototype profiles (10 women, 10 men) with photos,
  a moderator account, and a man with 60 credits for testing.

The reference data is two data migrations — T-1.14's, and P-25's for intents — with every insert
`ON CONFLICT DO NOTHING`: re-running them changes nothing and never resets a value tuned since.
