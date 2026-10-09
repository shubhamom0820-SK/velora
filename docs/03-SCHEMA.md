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
`ledger_entries`, `audit_log` and `payment_reversals` (T-8.3), no DELETE on `payments`, `messages` or `reports` (rule 12). New
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
photo_kind_t      ('public','private','selfie','verification')   -- verification: the face photo (D-391, T-4.12)
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
                   'thread_extend','dm_message',   -- T-5.2's (D-251)
                   'purchase_reversal','purchase_restored',   -- T-8.2's (D-521)
                   'welcome')   -- T-8.11's (D-470)
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
| phone_hash | text not null | HMAC-SHA256 of E.164, keyed by `PHONE_PEPPER` (D-061). Unique among accounts not erased (`uq_users_phone_hash_live`); an erased row keeps it (D-051, D-500), and `ix_users_phone_hash` finds every row a number ever had |
| phone_enc | bytea null | E.164, Fernet-encrypted in the API, never by the database (D-061). Null exactly when erased (`ck_users_phone_enc_until_anonymised`) |
| gender | gender_t null | immutable after set (trigger); kept by the erasure (D-501) |
| dob | date null | immutable after set (trigger), but for the erasure's own update, which clears it (D-501) |
| role | role_t not null default 'user' | |
| status | user_status_t not null default 'active' | |
| onboarding_step | onboarding_t not null default 'dob' | moves to `done` only for a man or `is_verified` (trigger `users_done_needs_a_match`, D-310) |
| is_verified | boolean not null default false | the selfie matched the face photo (T-4.5, D-391); never "verified" in copy (D-262). Not the badge: that is D-393's rule as D-910 amends it (the main photo matched), computed from `photos` (02-ARCHITECTURE §8) |
| pin_hash | text null | argon2id over a pepper kept off the database (D-062) |
| pin_failed | smallint not null default 0 | |
| referral_code | citext unique not null | generated at creation |
| last_active_at | timestamptz null | updated at most once per minute |
| deleted_requested_at | timestamptz null | when `DELETE /me` was asked; signing in again clears it (D-500) |
| anonymised_at | timestamptz null | when the account was erased, on day 29 or 30 (T-9.6, D-500); never changes once set (trigger `users_anonymised_for_good`) |

Indexes: `(status, last_active_at desc)`, `(phone_hash)`, and unique `(phone_hash) where
anonymised_at is null`. Checks (T-9.6): `ck_users_anonymised_is_deleted` (only a `deleted` row is
anonymised, so an erased account never comes back), `ck_users_phone_enc_until_anonymised`, and
`ck_users_anonymised_is_empty` (no dob or PIN on an anonymised row: the immutability trigger's
first-set rule would otherwise let a date back in, D-501). What else an erasure takes and keeps is
D-503's, column by column, in `api/app/modules/account/erasure.py`.

### sessions
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users on delete cascade | |
| family_id | uuid not null | rotation family |
| token_hash | text not null unique | SHA-256 of refresh token |
| user_agent | text | stays empty: nothing reads it, and `/privacy` doesn't list it (D-067) |
| ip | inet | stays empty, likewise (D-067). T-9.2 counts sign-ins instead of devices (D-903) |
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

### welcome_grants  (T-8.11, D-470, P-371)
| column | type | notes |
|---|---|---|
| phone_hash | text pk | the number's HMAC, as `users.phone_hash` holds it (D-061) |
| user_id | uuid fk users, unique | the account that received the grant |
| created_at | timestamptz | |

One row per number that received welcome Velas, so it gets them once, ever. The grant claims the
number here (`INSERT ... ON CONFLICT DO NOTHING`) before it credits, in `onboarding.complete()`'s
transaction; a later account on the number, once T-9.6 has erased the first, finds it claimed and
gets nothing. Append-only: triggers `welcome_grants_no_update_delete` and
`welcome_grants_no_truncate` reuse T-1.12's `refuse_change()`, and the app role has no UPDATE or
DELETE. The erasure keeps it (D-503); an under-18 refusal can't meet a row, since the grant comes
after `dob` (D-078). Its downgrade refuses while it holds a row.

### data_exports  (T-9.6, D-502)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users | |
| status | text not null default 'pending' | check: `pending`, `ready`, `failed`, `expired` |
| file_key | text null | the private bucket's key while a file may exist; recorded before the file is written |
| ready_at | timestamptz null | |
| expires_at | timestamptz null | 24 hours after `ready_at`: the link is signed until then, never past it, and the file is deleted then |
Check: `ready` has a file, `ready_at` and `expires_at`. Index `(user_id, created_at desc)`. An
under-18 refusal (D-078) and the erasure (D-503) delete its rows, files first.

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
| location | geography(Point,4326) null | a point of the 0.01° grid, never the exact position: CHECK `ck_profiles_location_on_grid` (D-490) |
| location_updated_at | timestamptz | |
| seeking | seeking_t | |
| is_hidden | boolean default false | privacy: hide profile |
| hide_age | boolean default false | |
| hide_distance | boolean default false | |
| show_kudos | boolean default true | |
| show_gifts | boolean default true | received gifts on profile |
| public_link | boolean default false | `/@username` shows first name, age, city and main photo to someone not signed in only when on; off for everyone, those already here included, until they turn it on (T-6.8, D-544). The in-app profile doesn't read it |
| completeness | smallint default 0 | 0–100, computed by service: 50, and 10 for each approved public photo after the first, set when onboarding finishes (T-4.8, D-310); after that, recomputed by every write that approves or removes a public photo (P-210) |

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
| kind | photo_kind_t | `verification` is the face photo (D-391, T-4.12): one live per person, private unless a public copy is made from it by `POST /photos/{id}/show`; it can't change once the selfie matched or while one is compared |
| position | smallint | 0–5 for public; the lowest approved place is the main one, 0 or not: the server never closes a gap (P-75, D-494) |
| raw_key | text | private bucket key |
| public_key | text null | set when approved (public kind only) |
| scored_key | text null | set when approved (private kind only): the bytes moderation scored, in the private bucket at `scored/{user_id}/{photo_id}.jpg`, where no upload URL reaches; all a private photo is ever shown from (P-79, D-700) |
| blur_key | text null | its blurred copy in the public bucket, for Liked you (T-6.7, D-543): `b/<a fresh random id>.jpg`, never from the photo's id; set by the worker after approval; deleted with the photo, at the underage deletion and the erasure |
| status | review_status_t default 'pending' | |
| reject_reason | text null | |
| moderation | jsonb | every score the decision read (T-4.4): provider, models, `minor` (the highest face's, kept below the threshold too, so D-101's is revisited from real scores), `explicit`, `faces`, `artificial_faces`, `text_artificial`; never the image or the request. A selfie's (T-4.5, D-263): `threshold`, `decided_by` (`wake`, `queue`, or `seed`), `provider`, `faces`, `best`, and `compared` (the face photo's id and cosine similarity, exactly; D-391); later `review` (the founder's `same`/`different`, D-264). A public photo's, from T-4.12: `from_photo_id` when it was made from the face photo, and `selfie_match` (D-393: `verification_id`, `provider`, `similarity`, `threshold`, `matched`, `decided_by`, `at`; the seed's says only `matched` and `decided_by: seed`), which the badge reads and never a rejection |
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
permanent. Check `status <> 'active' OR expires_at IS NOT NULL OR origin = 'dm'` — an active
thread from a match always expires; every way into `active` (open, reopen, untie) sets a fresh
expiry of `app_config.thread_hours` (seeded 24; 1 since T-7.6, D-097) — read the setting, never
hardcode the number (T-1.10). Her message and Extend can also move `expires_at` later, and his
never does (D-560, T-7.6); every move clears `expiry_warned_at`, so each expiry is warned once. A private message (origin `dm`) never expires (D-231), so an active
one carries none (T-7.1's `ddf84381ef6c`, D-550).
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
it reappears showing only messages newer than `cleared_at`. `cleared_at` is the Thread's newest
message's `created_at` when the clearing ran (its opening, before any), read under the Thread's
row lock, never the time of the tap (D-610, T-7.8). Clearing again moves it on; restoring deletes
the row (D-611): a clearing is a view, not a moderation record, and never touches `messages`.

---

## 5. Album, kudos, safety

### album_requests
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| requester_id | uuid fk users | |
| owner_id | uuid fk users | |
| status | album_req_t default 'pending' | |
| credits_charged | int not null default 0 | what he paid; spent, never returned on a decline or revoke (D-230); check `>= 0` |
| decided_at | timestamptz null | her last answer: the grant, the decline, or the revoke (D-731) |
Unique `(requester_id, owner_id) where status in ('pending','granted')`. Check `requester_id <> owner_id`.
A decline or revoke frees the pair, but the same man can't ask her again for `album_reask_days`
(30, `app_config`) after its `decided_at` (D-731, T-8.4).

### album_copies  (T-8.4, D-730)
`id uuid pk, request_id uuid fk album_requests, photo_id uuid fk photos, owner_id uuid fk users,
viewer_id uuid fk users, file_key text not null unique, created_at`. Unique `(request_id, photo_id)`;
indexes on `owner_id` and `viewer_id`. One private photo watermarked for one granted request's
viewer, at `album/{request_id}/{photo_id}.jpg` in the private bucket, rendered from the photo's
`scored_key`, never `raw_key` (D-700). The row is written only once its file is, and deleted only
once its file is gone, read back: so a revoke, the erasure (D-503) and an under-18 refusal (D-078)
find every copy by its `file_key`, both people's. The downgrade refuses while any row exists.

### kudos
`id uuid pk, from_id uuid fk users, to_id uuid fk users, kind kudos_t, thread_id uuid fk threads, created_at`.
Unique `(from_id, to_id)`. Check `from_id <> to_id` — self-kudos would manufacture social proof. Only allowed once the thread has `kudos_min_messages` (6) messages and both people have written one (D-680, enforced in the service).

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
| idempotency_key | text not null | the sender's `Idempotency-Key`; unique per sender, `uq_gift_sends_sender_id_idempotency_key` (T-8.9, D-653). A send from before it got its own id |
| created_at | timestamptz | the clock's now at send, which the cooldown and the week (D-650) read |
Indexes: `(recipient_id, created_at desc)`, `(sender_id, created_at desc)`,
`(sender_id, recipient_id, gift_id, created_at desc)` for the cooldown check.
Check `sender_id <> recipient_id`. No check pins prices to particular values — prices are data (D-016).

### blocks
`id uuid pk, blocker_id uuid fk users, blocked_id uuid fk users, created_at, unblocked_at
timestamptz null`. Unique `(blocker_id, blocked_id) where unblocked_at is null`
(`uq_blocks_active`): one standing block per pair. Index `(blocked_id)`. Check `blocker_id <>
blocked_id`. **Unblocking sets `unblocked_at` and keeps the row; blocking again is a new one**
(T-9.1, D-860, migration `4889c586aa2c`, whose downgrade refuses while a lifted block exists). A
standing block holds against the blocked account's number, matched through `users.phone_hash`, so
a later account on it is blocked too (D-861).

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
Indexes: `(status, created_at)`, `(reported_id, created_at desc)`, `(reporter_id, created_at desc)` (a person's own reports, `GET /reports`, T-9.8).
Check `reporter_id <> reported_id` — a self-report could probe the auto-freeze rule (D-031).

### fraud_scores
`user_id uuid pk fk users, score smallint not null default 0, band fraud_band_t not null default 'normal', signals jsonb, counted_from timestamptz null, updated_at`.
Check `score between 0 and 100` (D-031). Bands are policy, so no check ties them to the score.
Written by `safety.scoring.recompute` (T-9.2, D-900): `signals` is each signal's share of the
score, `{signal: points}`. `counted_from` is set when the founder lifts a freeze
(`app.tools.unfreeze`, D-906): only signals and reports from then on count; null, everything does.

### fraud_events
`id uuid pk, user_id uuid fk users, signal text not null, weight smallint not null, meta jsonb, created_at`.
Index `(user_id, created_at desc)`.
A signal, never a verdict. `weight` is what it was worth when written (T-9.2, D-900), so a later
change of weight applies to new events only. `possible_minor_photo_score` (T-4.4, D-093): a model's
score that one photo may show a minor, 10, capped under the monitor band; `meta` is `{what, model,
score}`, and never the image or which photo. `chargeback_shortfall` (T-8.2, D-520): a dispute took
back money whose Velas were already spent; 30, `meta` `{what, payment_id, shortfall}`, our
payment's id and the Velas the reversal couldn't take. `message_rejected` (T-7.1, D-552): `meta`
`{rule}`, 10 for `abuse`, 15 for `solicitation`. T-9.2's own, never a message, a place or a number:
`report_received` (`{report_id, reason}`, the report names its reporter), `contact_masked` (no
`meta`), and the threshold signals, each written at most once in 24 hours: `many_new_threads`
(`{threads}`), `identical_first_message` (`{people}`), `many_sign_ins` (`{sign_ins}`, D-903),
`location_jump` (`{km}`). The weights and caps are D-900's, in `app/modules/safety/fraud.py`.

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
| `purchase_reversal` | debit | `payment` | named by the caller: the refund's or dispute's own Razorpay id, one per refund or dispute (T-8.2, D-521) |
| `purchase_restored` | credit | `payment` | named by the caller: the same id as the reversal it gives back (D-520) |
| `welcome` | credit | `user` | the man himself: one per account, ever, inside the per-event index; one per number by `welcome_grants` (T-8.11, D-470) |

- `ck_ledger_entries_reason_direction`: credits positive, debits negative. Both lists are
  allowlists, so a reason added to `ledger_reason_t` can't be written until a migration names it.
- `ck_ledger_entries_ref_required`: every reason but `admin_grant` names its ref.
- `ck_ledger_entries_reason_ref_type`: the pinned `ref_type` or none, so a credit naming a payment
  can only be `purchase`, `purchase_bonus` or `purchase_restored`.
- `uq_ledger_entries_one_per_event`: partial unique index on `(user_id, reason, ref_type, ref_id)`
  where the reason is not `admin_grant`, `thread_reopen`, `thread_extend`, `purchase_reversal` or
  `purchase_restored`, the five that repeat for one ref (the third since T-5.2's a1d7de534ef7, the
  last two since T-8.2's fb0a7ce8dd16): one entry per event, even if a key is built wrong.
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
**`liked_you_reveal` is 1 from 8 October 2026 (the founder),** a value change (D-004's note).
P-370's data migration `e4e517f62ce3` moved the row from 20 to 1 the same day, before T-6.7
charges it; its downgrade puts D-004's 20 back.

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
was ₹40 a Vela, below the ladder's ₹50 (D-250), so variant B has no active pack. **Since T-8.1**
(D-480), B is shown A's packs until T-10.4: a man's variant is a hash of his id, and an allowlist
in `payments/rules.py` (`SHOWN_AS`) maps B to A. No man is ever shown an empty store.

### payments
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users | |
| pack_id | text fk credit_packs | |
| amount_paise | int not null | copied from pack at order time; check `> 0` |
| credits | int not null | copied; check `> 0` |
| bonus_credits | int not null default 0 | check `>= 0` |
| gst_paise | int not null default 0 | the government's part of the GST-inclusive `amount_paise` (D-099, D-450): 0 while unregistered, until P-350. Check `gst_paise >= 0 AND gst_paise < amount_paise` (`ck_payments_gst_within_amount`): registration splits the amount, never adds to it (T-8.1, D-482) |
| idempotency_key | text not null | the client's `Idempotency-Key` for the order; unique per user, `uq_payments_user_id_idempotency_key` (T-8.1, D-481) |
| provider | text not null default 'razorpay' | |
| provider_order_id | text unique not null | |
| provider_payment_id | text unique null | **idempotency anchor** |
| status | payment_status_t not null default 'created' | |
| paid_at | timestamptz null | |
| raw_webhook | jsonb null | the last verified event applied to the row (a repeated capture or a failure after payment leaves it), its allowlisted fields only, flattened (T-8.2, D-524): `{event, created_at, payment: {id, order_id, amount, currency, status, method, error_code, created_at}, refund: {id, payment_id, amount, currency, status, created_at}, dispute: {…the refund's keys}}`, each entity present only if the event carries it. Never the payer's email, phone (`contact`), UPI ID (`vpa`), card, bank, wallet, `acquirer_data`, `notes` or `description`, nor any field Razorpay adds later |

Check `status NOT IN ('paid','refunded') OR (provider_payment_id IS NOT NULL AND paid_at IS NOT NULL)` —
once money has moved the idempotency anchor exists, or a payment could be credited twice.
**Set by the webhook (T-8.2, D-523):** `paid`, the anchor and `paid_at` (our clock) only by a
capture; a failed attempt makes a `created` row `failed` and never sets the anchor, so a later
capture on the same order still credits; `refunded` only once the money has gone
(`refund.processed`, `payment.dispute.lost`, D-520). `bonus_credits` becomes 0 when the capture
finds an earlier purchase of his (D-522).
Triggers `payments_no_delete` and `payments_no_truncate`: payments are never hard-deleted
(rule 12); status updates are allowed. Both raise `restrict_violation` (23001) (T-1.12).

### refund_requests
A broken payment's claim (T-8.3, D-580): never a change of mind (D-050, D-230).
`id uuid pk, user_id uuid fk users, payment_id uuid fk payments, reason text not null, status text not null default 'open', note text null, provider_payment_id text null, provider_refund_id text unique null, resolved_at timestamptz null, created_at, updated_at`.
- `reason`: `missing_velas` (the money went through, no Velas came) or `duplicate_charge`
  (charged twice for one purchase), `ck_refund_requests_reason_known`.
- `status`: `open`, `granted`, `refunded` or `rejected`, `ck_refund_requests_status_known`.
  Checks: `(status = 'open') = (resolved_at IS NULL)`; `refunded` names the gateway's payment and
  refund (`ck_refund_requests_refund_names_its_ids`); `rejected` has a `note`, the admin's
  (`ck_refund_requests_rejection_has_note`). `provider_payment_id` is also set on a grant: the
  gateway's payment credited.
- One open claim per payment: `uq_refund_requests_open_per_payment`, unique on `payment_id`
  where `status = 'open'`.
- **A refund is recorded here, never on `payments`:** the payment refunded has no row of its own,
  and the credited payment's row is never touched, so turnover (D-483) stays right (D-580).

### payment_reversals  (append-only)
Every refund and dispute the webhook handled, once, whatever it took (T-8.3, P-420, D-581).
`id uuid pk, payment_id uuid fk payments, provider_ref text unique not null, kind text not null, taken int not null, shortfall int not null, created_at`.
`provider_ref` is the refund's or dispute's own Razorpay id (`rfnd_…`, `disp_…`); `kind` is
`refund` or `dispute`; `taken` and `shortfall` are what its reversal took and couldn't, each
`>= 0`, both 0 when nothing was outstanding. The webhook's repeat check: a reversal that took 0
wrote no ledger entry, so without it a redelivery took from Velas bought since. Keyed to
`payments` only, never `users`. Triggers `payment_reversals_no_update_delete` and
`payment_reversals_no_truncate` reuse T-1.12's `refuse_change()`; the app role has no UPDATE or
DELETE on it.

### referrals
`referee_id uuid pk fk users, referrer_id uuid fk users, rewarded_at timestamptz null, created_at`.
Check `referee_id <> referrer_id` — a self-referral would farm Velas on both sides of one account.
Rewarded once, when the referee's selfie matches or their first purchase is captured, whichever
comes first (T-8.6): `referral_reward_velas` to each **man** on it who still stands, never a
woman (D-076, D-690, D-693), the referrer only up to `referral_rewards_max` paid referrals, ever
(D-692); `rewarded_at` set either way. One referee per phone number, ever (D-691): apply reads the
referrals of every account the number had, through `users.phone_hash`, which the erasure keeps, as
it keeps these rows (D-503). An under-18 refusal deletes them, as referee or referrer (D-078).

---

## 7. Notifications

### push_subscriptions
`id uuid pk, user_id uuid fk users, endpoint text not null unique, p256dh text not null,
auth text not null, last_ok_at timestamptz null, created_at`.
One subscription per endpoint, across accounts. `p256dh` and `auth` are the subscription's keys:
never logged, never returned (rule 15).

### notification_prefs  (pk user_id)
`user_id uuid pk fk users`; `match, message, likes, knot, expiry, balance, gift, album,
generic_text` — booleans, not null, defaults true except `generic_text` false; `updated_at`.
The column is `likes` because `like` is a reserved word in Postgres. The model attribute and the
API field of `Prefs` (04-API) stay `like` (T-1.13). `gift` and `album` since T-9.4 (D-851). Each
governs its kinds' pushes only (`notifications.rules.PREF_FOR`), never the in-app row.

### notifications  (in-app list)
`id uuid pk, user_id uuid fk users, kind text not null, payload jsonb null, read_at timestamptz null,
created_at`. Index `(user_id, created_at desc)`. Written only through `notifications.service.notify()`
(T-9.4), for an active account only. `message` and `like` have no row (D-852).

### push_outbox  (T-9.4, D-850)
`id uuid pk, user_id uuid fk users, kind text not null, payload jsonb not null, attempts smallint
not null default 0 (check ≥ 0), claimed_at timestamptz null, created_at`. Indexes `(created_at)`,
`(user_id)`. A push waiting to be sent, written in the transaction that makes it true, deleted once
sent, skipped or given up on (3 attempts), so a row lives seconds. It is not a record (rule 12):
the erasure and an under-18 refusal delete a user's rows.

---

## 8. Ops

### audit_log  (append-only)
`id uuid pk, actor_id uuid not null fk users, action text not null, target_type text null,
target_id uuid null, meta jsonb null, created_at`.
`target_id` is polymorphic, so no fk. Check `(target_type IS NULL) = (target_id IS NULL)`, as on
`ledger_entries.ref_*`. `actor_id` is never null — null could not tell "the system did it" from
"a bug forgot to set it"; automated actions use a dedicated system user, created by T-9.2's
migration `4800f0e8d5a9` (D-905): `00000000-0000-4000-8000-000000000001`, a row shaped like an
erased account, so it never signs in or appears where people are listed. Its actions are
`fraud.band` and `fraud.freeze`; the founder's unfreeze writes `fraud.unfreeze` as himself (D-906).
Triggers `audit_log_no_update_delete` and `audit_log_no_truncate` (statement-level) reuse T-1.12's
`refuse_change()` and raise `restrict_violation` (23001): the person with a reason to erase the
trace is exactly the person with admin access (T-1.13).

### app_config  (key/value, cached 60 s per app, P-47; OTP send's daily cap reads it fresh)
`key text pk, value jsonb not null, updated_at`. Seeds: `swipe_daily_limit_men=50`,
`discovery_radius_km=25`, `thread_hours=24` (1 by T-7.6's data migration `7ee6438868ed`, which
adds `thread_extend_hours=24`, what one Extend adds, and `thread_warn_minutes=10`, when he is
warned; D-097, D-560), `mask_first_n_messages=20`, `kudos_min_messages=6`,
`gift_free_daily_limit=3` (replaced by T-5.2's data migration with `gift_free_weekly_limit=15`,
fifteen free sends a week, D-231),
`gift_same_recipient_cooldown_h=24`; and, by its own data migration
(T-3.2), `otp_sms_daily_cap=500`: the most Path B sign-in codes sent in one IST day across every
number, ₹100 a day at D-035's unconfirmed ₹0.20 an SMS (D-066); and, by T-8.1's,
`gst_rate_bps=1800`: 18% in basis points, read by nothing while Velora is unregistered (P-350,
D-482).
And by T-7.1's (D-553): `women_new_men_daily_limit=30` and `women_private_messages_daily_limit=30`,
a woman's two daily limits (D-098), by the IST day: limits, never prices.
And by T-8.11's: `welcome_velas=5`, every new man's Velas at `done`, once per number, 0 turning
the grant off; a missing row skips it with a warning, never failing a sign-up (D-470, D-530).
And by T-8.6's (D-692): `referral_reward_velas=5`, each man's Velas when a referral is rewarded, 0
rewarding it with nothing and a missing row skipping it with a warning, never failing its trigger;
and `referral_rewards_max=10`, how many referrals one referrer is paid for, ever, a missing row
paying no referrer. Since P-740 (D-840), `referral_reward_velas=0`: referrals are paused, and
`POST /referrals/apply` is refused while the reward isn't above 0, a missing row included.
And by T-8.4's: `album_reask_days=30`, the days after she declines or revokes his album request
before he may ask her again, read fresh at each request (D-731).
Two settings are also promised in copy, in `web/src/i18n/en.ts`, written out because copy is a
promise, not a computation. Change the copy with the setting:
- `thread_hours`: the landing page ("Threads last an hour", "1-hour", T-2.1), `/terms` ("lasts
  an hour", T-2.2), the match sheet's footer (T-6.5), and the share image, whose pixels say
  "Threads last an hour" (`web/src/app/opengraph-image.jpg`, T-2.4): the easiest one to forget.
  08-DESIGN §7 says how to regenerate it. T-7.6 changed them all with the setting, from a day.
- `thread_extend_hours`: `/terms` ("extended by a day", T-7.6) and the wallet's history
  ("Extend a thread by a day", T-5.5).
- `mask_first_n_messages`: `/terms` and `/privacy` ("first 20 messages", T-2.2).

### waitlist
`id uuid pk, email citext not null unique, city text null, created_at`.
Unique ignores case (citext). No format check in the database: T-2.3 validates in the API.

---

## 9. Seed data (Sprint 1, `alembic` data migration + `make seed` for dev)

- `interests` — 24 rows
- `intents` — 10 rows (P-25, D-041)
- `gifts` — 6 rows (D-016); four active since T-5.2 (D-252)
- `action_prices`, `credit_packs`, `app_config` — from D-004 / D-005 / §8
- `areas` — 40 neighbourhoods for the launch city
- **dev only** (`make seed`, T-1.15): the 20 prototype profiles (10 women, 10 men), a test man,
  a test woman and a moderator, written only to the local stack's database (D-064). Their photos
  arrive with T-4.4, verification rows with T-4.5, and the test man's 60 Velas with T-5.1.

The reference data is two data migrations — T-1.14's, and P-25's for intents — with every insert
`ON CONFLICT DO NOTHING`: re-running them changes nothing and never resets a value tuned since.
