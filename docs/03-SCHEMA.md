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
intent_t          ('serious','longterm','short','onenight','chat','discreet')
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
| intent | intent_t | |
| is_hidden | boolean default false | privacy: hide profile |
| hide_age | boolean default false | |
| hide_distance | boolean default false | |
| show_kudos | boolean default true | |
| show_gifts | boolean default true | received gifts on profile |
| completeness | smallint default 0 | 0–100, computed by service |

Indexes: `GIST(location)`, `GIN(username gin_trgm_ops)`, `GIN(first_name gin_trgm_ops)`,
`(intent)`, `(is_hidden)`.

### areas  (seed data for location fallback)
`id uuid pk, city text, name text, centroid geography(Point,4326)`. Unique `(city, name)`.

### interests  (seed: the 21 from the prototype)
`id smallint pk, slug text unique, label text`.

### profile_interests
`user_id uuid fk, interest_id smallint fk, pk(user_id, interest_id)`. Exactly 5 per user — enforced
in the service.

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
every way into `active` (open, reopen, untie) sets a fresh 24h (T-1.10).
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
| requester_id | uuid fk | |
| owner_id | uuid fk | |
| status | album_req_t default 'pending' | |
| credits_charged | int default 0 | refunded on decline |
| decided_at | timestamptz null | |
Unique `(requester_id, owner_id) where status in ('pending','granted')`.

### kudos
`id uuid pk, from_id uuid, to_id uuid, kind kudos_t, thread_id uuid, created_at`.
Unique `(from_id, to_id)`. Only allowed after the thread has ≥ 6 messages.

### gifts  (catalogue, seeded)
| column | type | notes |
|---|---|---|
| id | text pk | slug, e.g. `rose` |
| label | text | shown in UI |
| asset | text | emoji or icon key |
| credits | int not null check (credits >= 0) | 0, 2 or 4 |
| sort | smallint | display order |
| active | boolean default true | |

Seed (D-016): `smile` 0 · `wave` 0 · `rose` 2 · `coffee` 2 · `chocolate` 4 · `teddy` 4.

### gift_sends
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| sender_id | uuid fk users | |
| recipient_id | uuid fk users | |
| gift_id | text fk gifts | |
| credits_charged | int not null default 0 | copied at send time |
| thread_id | uuid null fk threads | set if a thread already existed |
| created_at | timestamptz | |
Indexes: `(recipient_id, created_at desc)`, `(sender_id, created_at desc)`,
`(sender_id, recipient_id, gift_id, created_at desc)` for the cooldown check.

### blocks
`blocker_id uuid, blocked_id uuid, created_at, pk(blocker_id, blocked_id)`. Index `(blocked_id)`.

### reports
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| reporter_id | uuid fk | |
| reported_id | uuid fk | |
| reason | report_reason_t | |
| details | text null | ≤ 500 |
| thread_id | uuid null | context |
| status | report_status_t default 'open' | |
| action | text null | freeze / ban / warn / none |
| resolved_by | uuid null fk users | |
| resolved_at | timestamptz null | |
Indexes: `(status, created_at)`, `(reported_id, created_at desc)`.

### fraud_scores
`user_id uuid pk, score smallint, band fraud_band_t, signals jsonb, updated_at`.

### fraud_events
`id uuid pk, user_id uuid, signal text, weight smallint, meta jsonb, created_at`.
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
| user_id | uuid fk | |
| delta | int not null | CHECK (delta <> 0) |
| balance_after | int not null | CHECK (balance_after >= 0) |
| reason | ledger_reason_t | |
| ref_type | text null | e.g. `thread`, `payment` |
| ref_id | uuid null | |
| idempotency_key | text not null unique | |
| created_at | timestamptz | |
Index `(user_id, created_at desc)`.
Trigger `ledger_no_update_delete`: raises on UPDATE or DELETE.

### action_prices
`action text pk, credits int not null check (credits >= 0), active boolean default true, updated_at`.
Seed from D-004.

### credit_packs
`id text pk, credits int, price_paise int, bonus_first_pct smallint default 20, active boolean,
sort smallint, variant text default 'A'` (for the beta price test).

### payments
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| pack_id | text fk credit_packs | |
| amount_paise | int | copied from pack at order time |
| credits | int | copied |
| bonus_credits | int default 0 | |
| provider | text default 'razorpay' | |
| provider_order_id | text unique not null | |
| provider_payment_id | text unique null | **idempotency anchor** |
| status | payment_status_t default 'created' | |
| paid_at | timestamptz null | |
| raw_webhook | jsonb null | last verified payload |

### refund_requests
`id uuid pk, user_id uuid, payment_id uuid, reason text, status text default 'open', created_at`.

### referrals
`referee_id uuid pk, referrer_id uuid, rewarded_at timestamptz null, created_at`.
Reward (both get credits) only after the referee's first paid purchase or selfie verification.

---

## 7. Notifications

### push_subscriptions
`id uuid pk, user_id uuid, endpoint text unique, p256dh text, auth text, last_ok_at, created_at`.

### notification_prefs  (pk user_id)
`match, message, like, knot, expiry, balance, generic_text` — booleans, defaults true except
`generic_text` false.

### notifications  (in-app list)
`id uuid pk, user_id uuid, kind text, payload jsonb, read_at timestamptz null, created_at`.
Index `(user_id, created_at desc)`.

---

## 8. Ops

### audit_log
`id uuid pk, actor_id uuid, action text, target_type text, target_id uuid, meta jsonb, created_at`.

### app_config  (key/value, cached 60 s)
`key text pk, value jsonb, updated_at`. Seeds: `swipe_daily_limit_men=50`,
`discovery_radius_km=25`, `thread_hours=24`, `mask_first_n_messages=20`, `kudos_min_messages=6`,
`gift_free_daily_limit=3`, `gift_same_recipient_cooldown_h=24`.

### waitlist
`id uuid pk, email citext unique, city text null, created_at`.

---

## 9. Seed data (Sprint 1, `alembic` data migration + `make seed` for dev)

- `interests` — 21 rows
- `gifts` — 6 rows (D-016)
- `action_prices`, `credit_packs`, `app_config` — from D-004 / D-005
- `areas` — ~40 neighbourhoods for the launch city
- **dev only** (`make seed`): the 20 prototype profiles (10 women, 10 men) with photos,
  a moderator account, and a man with 60 credits for testing.
