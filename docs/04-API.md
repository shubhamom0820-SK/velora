# 04 · API contract

All routes under `/v1`. 🔓 = public, 🔐 = logged in, ✅ = logged in **and** onboarding done,
🛡 = moderator/admin. The **Task** column says which plan task builds it.
Request/response bodies are Pydantic schemas in each module's `schemas.py`; the OpenAPI output is
the source for `web/src/types/api.ts`.

**Lists (D-270, 02-ARCHITECTURE §3).** Every route returning `Page<T>` takes `cursor` and `limit`
beside its own parameters, and the rows below write both. `Page<T>` is `{items: T[], next_cursor}`,
`next_cursor` null on the last page and sent back as `cursor` for the next; each list's schema is
named `<T>Page` (`LedgerEntryPage`). `limit` is 1 to 50, 20 when absent; outside that, and any
`cursor` the API didn't give, is `VALIDATION_ERROR`, never clamped or ignored.

## Auth & session
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /auth/firebase | 🔓 | `{id_token}` → `{access_token, user: Me}` + refresh and CSRF cookies. Path A; served only where `AUTH_PHONE_PROVIDER` is `firebase`, else 404. Used once; a sign-in under 5 minutes old; 10 / IP and 5 / phone an hour (D-085) | T-3.14 |
| POST | /auth/otp/send | 🔓 | `{phone}` → `{resend_after_s}`. Path B, MSG91; served only where `AUTH_PHONE_PROVIDER` is `msg91` or `fake`, else 404 (D-066) | T-3.2 |
| POST | /auth/otp/verify | 🔓 | `{phone, otp}` (6 digits, D-066) → `{access_token, user: Me}` + refresh and CSRF cookies | T-3.3 |
| POST | /auth/refresh | 🔓 cookie + X-CSRF | → `{access_token}` + rotated cookies | T-3.4 |
| POST | /auth/logout | 🔓 cookie + X-CSRF | → 204, revokes the session's family and clears both cookies; works after the access token expires (D-067) | T-3.4 |
| POST | /auth/pin/set | 🔐 | `{pin, current_pin?}` → 204. `current_pin` is needed to change a PIN, except within 10 minutes of a fresh sign-in (D-069) | T-3.9 |
| POST | /auth/pin/verify | 🔐 | `{pin}` → 204 or `PIN_INVALID` (5 → every session revoked; D-069 says what that doesn't protect) | T-3.9 |
| POST | /ws/ticket | ✅ | → `{ticket}` | T-7.4 |

## Me & onboarding
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /me | 🔐 | → `Me` (below) | T-3.5 |
| POST | /me/dob | 🔐 | `{dob}` → `Me`, or `UNDERAGE`: the account is deleted and only the number's hash kept (D-072) | T-3.6 |
| POST | /me/gender | 🔐 | `{gender}` → `Me` (once) | T-3.6 |
| POST | /me/seeking | 🔐 | `{seeking, intent_ids[1–3]}` → `Me` | T-3.6 |
| PATCH | /me/profile | 🔐 | `{first_name?, hometown?, city?, about?}` → `Me` | T-3.7 |
| GET | /usernames/{u}/available | 🔐 | → `{available, suggestion?}` | T-3.7 |
| PUT | /me/username | 🔐 | `{username}` → `Me` or `USERNAME_TAKEN` | T-3.7 |
| PUT | /me/interests | 🔐 | `{interest_ids[5]}` → `Me` | T-3.8 |
| POST | /me/pin/skip | 🔐 | → `Me`, moving `pin` → `selfie` (D-069) | T-3.9 |
| POST | /me/onboarding/complete | 🔐 | → `Me`, moving `selfie` → `done` (D-310). Every requirement met, or `PROFILE_INCOMPLETE` naming each one missing; a matched selfie for anyone but a man, or `VERIFICATION_REQUIRED`. Before `selfie`, `ONBOARDING_INCOMPLETE`; once `done`, `Me` unchanged. Sets `completeness`. As a man reaches `done`, `app_config.welcome_velas` (5) credited as `welcome`, once per phone number, ever, so `Me.balance` says it; never a woman, and nothing about it ever refuses the request (D-470, D-530) | T-4.8, T-8.11 |
| PUT | /me/location | 🔐 | `{lat, lng}`, inside India's box, or `{area_id}`, stored at its centroid → `Me` (D-220). Either is stored as its point of the 0.01° grid, never exactly (D-490). A position takes the nearest area within 2 km of the exact position, or none. From the `username` step on, never moving it; before, `ONBOARDING_INCOMPLETE`. Outside the box, or an area that isn't one: `VALIDATION_ERROR`. 10 an hour per user | T-4.10 |
| PATCH | /me/settings | ✅ | `{is_hidden?, hide_age?, hide_distance?, show_kudos?, show_gifts?, public_link?}` (`public_link`: T-6.8, D-544), each `true` or `false` only → `Me`. A field it doesn't know, or nothing to set, is `VALIDATION_ERROR`: a typo in a privacy switch never looks like it worked | T-9.6 |
| POST | /me/pause | ✅ | → 204: `paused`, hidden from everyone and sent no notifications (T-9.4) until resumed. Twice is once | T-9.6 |
| DELETE | /me/pause | ✅ | → 204: back to `active`. Twice is once | T-9.6 |
| POST | /me/export | ✅ | → 202 `DataExport` (below): a new one queued for the worker, or the one being made, or a ready one, rather than a second (D-502). 5 a day per user | T-9.6 |
| GET | /me/export | ✅ | → `DataExport`, the newest, its `url` signed until `expires_at` while `ready`; none asked for: `NOT_FOUND` | T-9.6 |
| DELETE | /me | ✅ | → 202 `{erase_by}`: `deleted` at once, every session revoked. Signing in again before the erasure restores it; erased on day 29 or 30, within `erase_by` (D-500). A ban or freeze landing meanwhile still refuses it (`ACCOUNT_BANNED` / `ACCOUNT_FROZEN`) | T-9.6 |
| GET | /interests | 🔓 | → `Interest[]` | T-3.8 |
| GET | /intents | 🔐 | → `Intent[]` | T-3.6 |
| GET | /areas?city= | 🔓 | → `Area[]`: `{id, city, name}`, never a centroid, by city then name; every city's, or `city`'s in any case (D-220) | T-4.10 |

Onboarding endpoints work at their step and after it, never before (D-068).

`DataExport` (T-9.6, D-502): `id`, `status` (`pending`, `ready`, `failed`, `expired`),
`requested_at`, `expires_at` (24 hours after it was ready), and `url`, a link to the JSON signed
until `expires_at` and never past it, while `ready`; otherwise `null`. A ready one past its
expiry reads `expired`, whether or not its file's deletion has run yet. The JSON holds the
user's own data and nobody else's (D-502 lists it).

`Me` (T-3.5): `id`, `role`, `status`, `onboarding_step`, `gender`, `age`, `is_verified`,
`has_pin`, `referral_code`, `balance`, and `profile`: `first_name`, `username`, `about`,
`hometown`, `city`, `seeking`, `intent_ids`, `interest_ids`, `is_hidden`, `hide_age`,
`hide_distance`, `show_kudos`, `show_gifts`, `public_link` (T-6.8, D-544: whether `/@username` shows anything to someone not signed in; off until they turn it on), and `location` (T-4.10): `none`, `fresh`, or `stale`
once over 6 hours old by the server's clock (D-220), never where it is. The age, never the date of
birth, and no phone number: no screen shows either, so neither leaves the server (D-067's
discipline).

## Photos & verification
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /photos/upload-url | 🔐 | `{kind, position?, content_type}` → `{photo_id, put_url, headers}`. `content_type` is `image/jpeg`, `image/png` or `image/webp`, signed into the PUT, so send `headers` with it; a hint, never what decides (D-089). Public: `position` 0–5, one per place; private: up to 6; selfie: one being compared, and one never sent to a verification is replaced, as `replaced`, its file deleted (D-263); `verification`, the face photo (D-391, T-4.12): one live per person, a new one replacing the old as `replaced`, `NOT_ALLOWED` once the selfie matched or while one is being compared. Each at its step or after (D-068). 30 an hour per user | T-4.2 |
| POST | /photos/{id}/complete | 🔐 | → `Photo` (pending). The object's bytes decide: a JPEG, PNG or WebP is queued for moderation (a selfie waits for its verification's submit, T-4.5); anything else is `UNSUPPORTED_IMAGE`, over 8 MB `IMAGE_TOO_LARGE`, each rejecting the photo and removing its file. Saying it twice is harmless. No photo moves the `photos` step on (T-4.12): `/me/photos/done` does | T-4.2 |
| GET | /me/photos | 🔐 | → `Photo[]`: the owner's live public photos by place, then private, then the face photo (T-4.12); never selfies, rejected photos or anyone else's | T-4.3 |
| PATCH | /me/photos/order | 🔐 | `{photo_ids[]}`, exactly the live public photos, each once, the first the main one → `Photo[]`, places 0 onwards | T-4.3 |
| POST | /me/photos/done | 🔐 | → `Me`, moving `photos` → `interests`: the step's exit, with or without a public photo (D-392). Anyone but a man needs a face photo, pending or approved (D-391, an allowlist), or `FACE_PHOTO_REQUIRED`. Before `photos`, `ONBOARDING_INCOMPLETE`; once past, `Me` unchanged (D-068) | T-4.12 |
| DELETE | /photos/{id} | 🔐 | → 204 (soft): rejected as `user_deleted`, its public copy removed; twice is once. The last public photo may go, past the `photos` step too (D-392, T-4.12). A selfie is `NOT_ALLOWED`; the face photo too once the selfie matched or while one is being compared | T-4.3 |
| GET | /photos/{id} | 🔐 | → `Photo`: one of the owner's public, private or face photos, in any status, rejected included, so the photos step can say why one left `/me/photos` (D-096). Someone else's, a selfie, or none: the same `NOT_FOUND` | T-4.6 |
| POST | /photos/{id}/show | 🔐 | → `Photo`: also show the face photo on the profile (D-391, T-4.12). An ordinary public photo made from its private copy, in the first free place, pending and queued through moderation as any upload is, carrying `from_photo_id`; twice is the same copy. Hiding it again is `DELETE /photos/{copy}`. The face photo not approved, or no free place (`details.max`): `NOT_ALLOWED`; someone else's, a public photo, or none: `NOT_FOUND`. 30 an hour per user | T-4.12 |
| POST | /verification/start | 🔐 | → `Verification`, waiting for its selfie: the one already open, or a new one. No pose (D-263). At the `selfie` step or after (D-068). Once matched, or while one is being compared, `NOT_ALLOWED`; 5 selfies sent in a rolling 24 hours, `RATE_LIMITED` with `retry_after_s`. 20 an hour per user | T-4.5 |
| POST | /verification/{id}/submit | 🔐 | `{photo_id}`, a selfie uploaded through `/photos/upload-url` → `Verification` (pending, `submitted`), its comparison queued, then the worker woken (D-261). Someone else's verification or selfie, or none: `NOT_FOUND`; a selfie decided, held by another verification or never uploaded, or another selfie for one already sent: `NOT_ALLOWED`; the day's five: `RATE_LIMITED`. The same selfie twice is once. 20 an hour per user | T-4.5 |
| GET | /verification/latest | 🔐 | → `Verification`, the newest; none: `NOT_FOUND` | T-4.5 |

`Photo` (T-4.2, T-4.3, T-4.12): `id`, `kind`, `position`, `status`, `reject_reason`, `url`: an
approved public photo at `PUBLIC_CDN_URL`, any other live one by a 10-minute signed link to its
private copy, `null` for a rejected one; and `from_photo_id`, the face photo a public copy was made
from by `/photos/{id}/show`, `null` for every other photo. No photo completes the `photos` step
(T-4.12; until then a pending public one did, T-4.3). `reject_reason` names only `abandoned`,
`too_large`, `unsupported_format`, `user_deleted`, `replaced`, `nudity`, `no_face` (the face photo
only, D-392) and `text_overlay`; any other reason, a possible minor's included, reads `other`
(D-096, D-093).

`Verification` (T-4.5, D-263): `id`, `status` (`pending`, `approved`, `rejected`), `submitted`
(a selfie is attached: pending and submitted means being compared), `reject_reason` and
`attempts_left` (selfies that may still be sent in the next 24 hours). Never a similarity, a link or
the selfie. `reject_reason` names only `no_face`, `many_faces`, `no_match`, `no_photos` (no approved face
photo, or no face found in it), `unreadable` and `unavailable`; anything else reads `other`.
`approved` means the selfie's face matched the face photo's at SFace's published threshold (D-260,
D-391), and nothing more: no published word calls it verification (D-262). The badge (D-393) is a
further rule, computed from the shown photos' records, never `is_verified` alone (02-ARCHITECTURE
§8).

## Discovery
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /discover | ✅ | `?feed=foryou|new|online&intent_ids=&verified=&online=&cursor=&limit=` → `Page<Card>` with `swipes_left` (T-6.5; `intent_ids`: any overlap, D-041, 1 to 10 known ids, repeated as `intent_ids=1&intent_ids=2`; `verified=true`: the badge, D-393; `online=true`: active in the last 5 minutes, in any feed, D-660, T-6.9) | T-6.2 |
| POST | /swipes | ✅ | `{target_id, dir, shown_price?}` (`like`, `pass`, `super`) → `{matched, match_id, swipes_left}` (`swipes_left` null for anyone uncapped, a woman). Once per pair: `ALREADY_EXISTS`. Only someone the feed could show you, the radius aside: else `NOT_FOUND` (D-492). A man's like and pass count toward `swipe_daily_limit_men` by the IST day, a Super Like doesn't: `SWIPE_LIMIT_REACHED`. A Super Like is 5 Velas for a man (402 if he can't), free for a woman; `PRICE_CHANGED` unless `shown_price` is its price (D-600). 120 a minute | T-6.4 |
| GET | /users/{id} | ✅ | → `PublicProfile`; `NOT_FOUND` for nobody and every refusal alike (D-493). `can_gift`: whether `POST /gifts/send` takes a gift from you to them, a man to a woman he can reach (D-653, D-780); never on your own (T-8.10) | T-6.3 |
| GET | /users/by-username/{u} | ✅ | → `PublicProfile`, in any case, by exactly `GET /users/{id}`'s rule (D-493); a name nobody holds, an erased one's included (D-505), the same `NOT_FOUND` | T-6.6 |
| GET | /search | ✅ | `?q=&cursor=&limit=` → `Page<SearchResult>` (D-540). `@` and 1 to 20 of `[A-Za-z0-9._]`: usernames starting with it, the exact one first, across India and past seeking, never a hidden profile. Otherwise 2 to 50 characters: within the radius, mutual, by name or username (trigram or prefix), city (prefix), or an intent or interest label. Swiped or not; active accounts only. Anything else `VALIDATION_ERROR` on `q`. 60 a minute | T-6.6 |
| GET | /public-profiles/{username} | 🔓 | → `SharedProfile` (T-6.8, D-544): what `/@username` shows someone not signed in, in any case, only when its owner turned `public_link` on and it is active, done, not hidden, in neither the `freeze` nor the `shadow` band; every other case, a name nobody holds among them, the one `NOT_FOUND`. No view recorded. 60 a minute per address | T-6.8 |
| GET | /likes | ✅ | `?cursor=&limit=` → `Page<LikeCard>` (D-542): everyone whose like or Super Like of you waits on your swipe, from someone you could swipe back, newest first; a man's unrevealed ones blurred, never named; a woman's all shown | T-6.7 |
| GET | /likes/count | ✅ | → `{count}`: how many `/likes` lists (D-542) | T-6.7 |
| POST | /likes/{handle}/reveal | ✅ | `{shown_price}` (P-56, D-600: the price the screen showed, compared, never charged; absent is 0) → `PublicProfile` (D-542): `liked_you_reveal`'s price (1 Vela from 8 October 2026, P-370) for a man, nothing for a woman, once per pair; a second is free. 402 / `NOT_ALLOWED` / `PRICE_CHANGED` (409, `details.price`) write nothing; a handle naming no like still waiting on you, `NOT_FOUND`. Was `/likes/{user_id}/reveal` until T-6.7 | T-6.7 |

The feed's page is `Page<Card>` with one more field, `swipes_left`: a man's swipes left today,
the same number `POST /swipes` answers with, null for anyone uncapped (a woman), so the deck can
say it before his first swipe (T-6.5, the founder, 8 October 2026).

`Card` (T-6.2, D-494): `id`, `first_name`, `age` (null if hidden), `username`, `city`, `hometown`,
`distance_km` (whole km between grid points, at least 1, D-034 and D-490; null if hidden),
`intent_ids`, `bio_line` (the first 90 characters of `about`), `main_photo_url` (the approved
public photo at the lowest place, P-75, or null, D-392), `shows_badge` (D-393's rule, never raw
`is_verified`), `is_online` (active within 5 minutes), `is_new` (joined within 7 days). Never a
date of birth, a position, a phone number or `is_verified`. The feed: everyone 02-ARCHITECTURE §8
leaves out stays out, ranked by D-491's score, best first, then by id; its cursor carries the
instant the scroll began, so time passing between pages can't repeat or skip a card (D-491).

`SearchResult` (T-6.6, D-540): a search row. `id`, `first_name`, `age` (null if hidden), `username`,
`city`, `main_photo_url` and `shows_badge` (each the `Card`'s), `is_online`, and `exact` (`@`
search only: the username is exactly what was asked). No distance, date of birth, position or
`is_verified`.

`LikeCard` (T-6.7, D-542): `handle` (opaque, 32 hex: what a reveal names; never the person's
id), `is_super`, `card` (the person's `Card`: a woman's always, a man's once revealed, else null),
and `blurred_photo_url` (unrevealed only: the server's blur of their main photo, D-543, or null
with none yet). Nothing in an unrevealed one, nor in the list's cursor, names the person.

`SharedProfile` (T-6.8, D-544): `username`, `first_name`, `age` (null if hidden), `city`, `main_photo_url`
(the `Card`'s, or null). Never an id, a badge, a distance, the about or another photo.

`PublicProfile` (T-6.3, D-493): a `Card`, and `about` (whole), `photo_urls` (every approved public
photo in place order; the first is `main_photo_url`), `interest_ids`, `kudos` (`{great_conversation,
genuinely_funny, easy_to_talk_to, really_thoughtful}`, each a count; null when `show_kudos` is
off), `album_photo_count` (approved private photos, a number, never one of them), `match_id` and
`thread` (`{id, status, expires_at, kudos}`), what is already between the viewer and them, or null.
`kudos` says whether the viewer may give them kudos (T-8.8, D-790): `given` once they have,
`too_early` until both have written and it has `kudos_min_messages` messages (D-680), else
`can_give`.
Shown to anyone `visible_to` allows without seeking or the radius (a link reaches past both); a
hidden profile only to someone it shares a match or a Thread with; your own always. Every refusal
is `NOT_FOUND`, the same body as an id nobody holds. A view is recorded, one row per pair,
counted, never for your own profile or a refusal.

## Threads & messages
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /threads | ✅ | `?tier=threads|knots&filter=all|unread|recent&q=&cursor=&limit=` → `Page<ThreadRow>`: `threads` is active and expired, `knots` knotted; `unread`, something of theirs unread; `recent`, a message in the last 3 days; `q` (1–50), their first name or username, anywhere in it. Newest first by the last message, or the opening before any. Never one I cleared with nothing newer (D-006), never one with a block either way | T-7.2 |
| POST | /threads | ✅ | `{match_id}` or `{user_id, first_message}` (1–500), each with `shown_price?` → `Thread` (5 Velas from a match; 8 for a private message, D-231; `PRICE_CHANGED` unless `shown_price` is the price, D-600). One per pair: an existing one is returned, nothing charged; an expired one is `THREAD_EXPIRED` for him and returned to her (D-097). Every refusal of whom is `NOT_FOUND` (D-550). A woman past her daily limits: `RATE_LIMITED` (D-553). 20 a minute | T-7.1 |
| GET | /threads/{id} | ✅ | → `ThreadView`: the `Thread`, the other person as the list shows them (`other`, a `CardLite`; no profile view counted, D-493), `send_price`, what my next text message costs now (D-870), and `can_gift` and `kudos` (D-880); `NOT_FOUND` unless it is yours, and across a block | T-7.2, T-7.11, T-7.12 |
| GET | /threads/{id}/messages | ✅ | `?cursor=&limit=` → `Page<Message>`: newest first, after my clearing only (D-006); `NOT_FOUND` unless it is yours, and across a block | T-7.3 |
| POST | /threads/{id}/messages | ✅ | `{client_msg_id, kind, body?, media_key?, duration_s?, shown_price?}` → `Message`. Text 1–2000, not blank. A voice note: hers alone (`NOT_ALLOWED` for anyone else), `media_key` from its upload URL and no body; judged by its bytes and its length measured, never `duration_s` (1–60, unstored): `VALIDATION_ERROR` on `media_key` for a key that URL didn't give this Thread or nothing uploaded, `AUDIO_TOO_LARGE`, `UNSUPPORTED_AUDIO`, `AUDIO_TOO_LONG`; one upload is one message, `ALREADY_EXISTS` again (D-620). The same `client_msg_id` again returns its message, nothing charged; used in another Thread, `ALREADY_EXISTS`. His send on an expired Thread, by the clock, is `THREAD_EXPIRED`, hers delivered (D-097, D-560). What he pays: D-551; a paid send is `PRICE_CHANGED` unless `shown_price` is its price (D-600). `MESSAGE_REJECTED` (D-552), `ACCOUNT_DELETED` (D-555), `RATE_LIMITED` for her daily limits (D-553). 30 a minute | T-7.3 |
| POST | /threads/{id}/read | ✅ | `{up_to_message_id}` → 204: their messages not yet read, up to and including that one and after my clearing, read now; a `read_at` once set never moves. `message.read` to them alone, only when something was marked (D-670). `NOT_FOUND` unless the Thread is yours, across a block, and for a message from another Thread or before my clearing | T-7.5 |
| POST | /threads/{id}/reopen | ✅ | `{shown_price?}` + `Idempotency-Key` (8 to 64 of `A-Za-z0-9_-`) → `Thread`: an expired one (by the clock, D-560) for 2 Velas (D-098) and a fresh hour from now; a live one returned as it is, nothing charged (D-642). The same key again returns the Thread, nothing charged or moved (D-077). A woman, a Knot or a private message: `NOT_ALLOWED`, nothing written (D-642). `PRICE_CHANGED` unless `shown_price` is the price (D-600). 20 a minute, with Extend | T-7.6 |
| POST | /threads/{id}/extend | ✅ | `{shown_price?}` + `Idempotency-Key` → `Thread`: 10 Velas, adding `thread_extend_hours` (24) to what is left, as often as he likes (D-250); from expired the same 10 re-opens it, one `thread_extend` debit (D-253). The same key, a woman, a Knot, a private message and the price as re-open. After either, his first message in a Thread she opened costs nothing more (D-641) | T-7.6 |
| POST | /threads/{id}/knot | ✅ | → `Thread`: your tap, free (D-003), on a live or an expired Thread; the second of the two makes it a Knot (`knotted`, `knotted_at`, no `expires_at`), `knot.accepted` to both and a `knot_accepted` notification to the first; one tap alone, `knot.requested` and a `knot_requested` notification to the other. Your tap already there, or a Knot: returned as it is, nobody told again (D-770). With a deleted account: `ACCOUNT_DELETED`, nothing written (D-770). `NOT_FOUND` unless it is yours, and across a block. 30 a minute, with untie | T-7.7 |
| DELETE | /threads/{id}/knot | ✅ | → `Thread`: either of the two unties a Knot: `active`, both taps cleared, a fresh `thread_hours` from now for a Thread from a match and none for a private message (D-550, D-560); `knot.untied` to the other, no notification. Not a Knot: returned as it is, a pending tap kept, nobody told (D-770). `NOT_FOUND` as tie | T-7.7 |
| POST | /threads/{id}/clear | ✅ | → 204: hidden from my chats alone, through its newest message (D-006, D-610); new messages bring it back. The other person, the messages and the Thread unchanged, nobody told. Again, 204. `NOT_FOUND` unless it is yours, and across a block. 60 a minute, shared with the two below | T-7.8 |
| POST | /threads/clear | ✅ | `{thread_ids}` (1–100) or `{expired: true}`, one of them → `{cleared}`: of the ids, those that are yours and no block stands across, the rest skipped; of `expired`, those in my list expired by the clock (D-560, D-611). Anything else `VALIDATION_ERROR` | T-7.8 |
| DELETE | /threads/{id}/clear | ✅ | → 204: the clearing gone, the whole history back (D-611); never cleared, 204. `NOT_FOUND` unless it is yours, and across a block | T-7.8 |
| GET | /threads/cleared | ✅ | `?cursor=&limit=` → `Page<ThreadRow>` (`ClearedThreadRowPage`): the chats I cleared that nothing newer has brought back, Threads and Knots alike, newest clearing first by `(cleared_at, id)`; never another person's clearing, never one across a block either way. Each is restored by `DELETE /threads/{id}/clear` (P-510, D-912) | T-9.8 |
| POST | /media/voice-upload-url | ✅ | `{thread_id, content_type}` (`audio/webm`, `audio/ogg` or `audio/mp4`) → `{message_id, media_key, put_url, headers}`: PUT the recording there with exactly those headers within 5 minutes, then send it. A woman's alone: anyone else `NOT_ALLOWED`; another type `UNSUPPORTED_AUDIO`; not her Thread, or across a block, `NOT_FOUND`; an expired one takes hers (D-097, D-620). 60 an hour | T-7.9 |
| POST | /messages/{id}/unlock | ✅ | `{shown_price?}` → `{url}`, signed for 10 minutes. 5 Velas for a man, once: unlocked again, or never locked (its sender, a woman), the link and nothing charged; `PRICE_CHANGED` unless `shown_price` is its price (D-600); `INSUFFICIENT_CREDITS`; either writes nothing. An expired Thread is no bar. Not a voice note in a Thread of yours, or across a block, `NOT_FOUND` (D-621). 30 a minute | T-7.9 |
| GET | /messages/{id}/media | ✅ | → `{url}` (signed, 10 min) for anyone it isn't locked for; locked, `NOT_ALLOWED`; otherwise as the unlock, `NOT_FOUND` (D-621). 60 a minute | T-7.9 |

`Thread` (T-7.1): `id`, `origin` (`match`, `dm`), `status`, `other_user_id`, `expires_at` (a
man's alone, D-554: null for a woman, once knotted, and for a private message, which never
expires, D-550), `knotted_at`, `i_tied`, `last_message_at`, `created_at`.

`ThreadView` (T-7.11, D-870): a `Thread`, with `other` (a `CardLite`, as `ThreadRow`'s) and
`send_price`, the Velas my next text message would cost now, by the send's own rules (D-551,
D-641): 2 or 5 for his answer in a Thread she opened, until he has written or paid a re-open or an
Extend there; 2 for each of his private messages until it is knotted; 0 otherwise, and always 0 for
her (D-098). The conversation screen shows it and sends it back as `shown_price` (P-56, D-600). An
expired Thread refuses his send whatever it says (D-097). `can_gift` is whether a gift to them is taken
(D-780's rule, the profile's own) and `kudos` whether kudos can be given (`too_early`, `can_give`,
`given`, the profile's `thread.kudos`, D-790): his gift button and the kudos prompt (D-880).

`ThreadRow` (T-7.2): `id`, `origin`, `status`, `expires_at` (a man's alone, D-554), `knotted_at`,
`i_tied`, `unread` (their messages I haven't read, after my clearing), `last_message`
(`{kind, text, mine, at}`: `text` a text's first 100 characters as shown; a voice note has none,
and the web names it), `last_message_at`, and `other`, a `CardLite`.

`CardLite` (T-7.2): `id`, `first_name`, `username`, `main_photo_url`, `shows_badge` (D-393),
`is_online`, `deleted`. A deleted account (D-051, D-500) is `deleted: true` and nothing else: no
name, username, photo, badge or presence, from the moment they delete; its Thread stays, as the
messages do, and `q` never finds it.

`Message` (T-7.1, T-7.3): `id`, `thread_id`, `kind`, `body` (the text shown, masked where it had
to be; never the original, D-030), `masked`, `duration_s`, `mine`, `from_deleted_account`
(D-051), `locked` (a voice note a man hasn't unlocked; the file is never here, T-7.9),
`read_at`, `created_at`, and `client_msg_id` on your own messages only.

## Real time
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /ws/ticket | ✅ | → `{ticket}`: opens one socket, once, within 30 s (D-557). 30 a minute | T-7.4 |
| WS | /ws?ticket= (at the root, never in OpenAPI) | ticket | §6's envelope; only from the web's exact origins | T-7.4 |

## Album, kudos, safety
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /album-requests | ✅ | `{owner_id, shown_price?}` → `AlbumRequest` `{id, requester: CardLite, owner_id, status, created_at, decided_at}`, never what he paid (D-732). Someone he can't reach as a private message can (D-550), himself, or across a block: `NOT_FOUND`. A pending or granted request to her already: that one, nothing charged. Within `album_reask_days` (30) of her declining or revoking his last: `NOT_ALLOWED`, `details.why` `recently_declined` (D-731). No private photo with a scored copy (D-700): `NOT_ALLOWED`, `empty_album`. Then the `album_request` row's price, 1 Vela for a man, nothing for a woman (D-231, D-098), debited with the request; `PRICE_CHANGED` unless `shown_price` is that price (D-600); 402 if he can't. Every refusal before anything is charged or written. 20 a minute | T-8.4 |
| GET | /album-requests/incoming | ✅ | `?cursor=&limit=` → `Page<AlbumRequest>` (`AlbumRequestPage`): her pending and granted requests, newest first by `(created_at, id)`, none from across a block (D-732) | T-8.4 |
| POST | /album-requests/{id}/decide | ✅ | `{grant: bool}` → `AlbumRequest`. Hers and pending, else `NOT_FOUND`; the same answer again changes nothing, the other once answered `NOT_ALLOWED` (`already_decided`). A grant queues `watermark_album`; a decline returns nothing (D-230). He gets `album.decided`. 60 a minute | T-8.4 |
| POST | /album-requests/{id}/revoke | ✅ | → 204. Hers, else `NOT_FOUND`; only a granted one, else `NOT_ALLOWED` (`not_granted`); twice is once. Its copies are deleted (D-730). 60 a minute, with decide | T-8.4 |
| GET | /users/{id}/album | ✅ | → `Album {status, photos: [{url}]}` (D-732): `status` his latest request to her (null if none); `photos` his own watermarked copies, each signed for 10 minutes (D-027), only while it is granted, else empty. `NOT_FOUND` unless he can open her profile (D-493), and for your own id. A photo approved before D-700 has no scored copy and is never shown | T-8.4 |
| GET | /gifts | ✅ | → `GiftCatalogue {gifts: Gift[] (id, label, asset, credits), free_sends_left, free_sends_reset_at}` (D-652): the active gifts by `sort`, held 60 s per app; a man's free sends left this week and the next Monday 00:00 IST (D-650), read fresh; both null for anyone else | T-8.9 |
| POST | /gifts/send | ✅ | `{recipient_id, gift_id, shown_price?}` + `Idempotency-Key` (8 to 64 of `A-Za-z0-9_-`) → `GiftSend {id, gift_id, recipient_id, credits_charged, thread_id, created_at}`. A man only, else `NOT_ALLOWED`; to a woman he could send a private message to: anyone else `NOT_FOUND`, a block never revealed, and someone he can reach who isn't a woman `NOT_ALLOWED` (D-653). A gift not on sale: `NOT_FOUND`. The same gift to her inside `gift_same_recipient_cooldown_h`: `GIFT_COOLDOWN`. Free while this week's `gift_free_weekly_limit` lasts, then the gift row's price, debited with the send (402 if he can't); `PRICE_CHANGED` unless `shown_price` is that price, 0 for a free send (D-231, D-600, D-650). The same key again: that send, nothing new; with another gift or woman, `ALREADY_EXISTS`. Links a live or knotted Thread, never opens one; she gets `gift.received` and a `gift` notification. 20 a minute | T-8.9 |
| GET | /me/gifts | ✅ | `?cursor=&limit=` → `Page<ReceivedGift>` `{id, gift_id, sender: CardLite, created_at}`: received, newest first by `(created_at, id)`, never what he paid, none from across a block (D-652) | T-8.9 |
| GET | /users/{id}/gifts | ✅ | → `{counts:[{gift_id,count}]}` in the catalogue's order, never from whom. `NOT_FOUND` unless you can open the profile (D-493); with `show_gifts` off, empty to everyone but her | T-8.9 |
| POST | /kudos | ✅ | `{to_id, kind}` → 201 `{to_id, kind, created_at}`: once ever to each person, only after both have written in your Thread and it has `kudos_min_messages` messages (D-680). 10 a minute | T-8.5 |
| GET | /me/kudos | ✅ | → `Kudos[]`: `[{kind, count}]`, the kinds you were given, each with how many gave it, in the kinds' order, none at 0; never who nor when, and shown to you whatever `show_kudos` says (D-680) | T-8.5 |
| POST | /reports | ✅ | `{reported_id, reason, details?, thread_id?, also_block}` → 201 `{id, created_at}`. Anyone with an account, a block standing either way or not; yourself `NOT_ALLOWED` (`why: yourself`), an id nobody holds `NOT_FOUND`. `details` 1 to 500; `also_block` `true` or `false`, always said, and blocks in the same transaction; `thread_id` the pair's own Thread, whatever block stands, else `NOT_FOUND`. The same person again is a new report. Every refusal before anything is written; the reported person is never told. 10 a day (D-863) | T-9.1 |
| GET | /reports | ✅ | `?cursor=&limit=` → `Page<FiledReport>` `{id, reason, created_at, reported: CardLite}`: the reports I filed, newest first by `(created_at, id)`; never one about me, and **no status**, whatever moderation did. Across a block either way, `reported` has its name and username alone, no photo, badge or presence, the same whoever blocked; an erased person is `deleted` (D-911) | T-9.8 |
| POST | /blocks | ✅ | `{user_id}` → 201 `BlockedUser` `{user: CardLite, blocked_at}`. Anyone with an account, in any status; yourself `NOT_ALLOWED`, an id nobody holds `NOT_FOUND`. Twice is once. Every album grant between them, either way, revoked (D-863). From then on everything between them is `NOT_FOUND`, never `BLOCKED` (D-862), and a new account on the blocked person's number is blocked too (D-861). Nobody is told. 60 a minute, with unblocking | T-9.1 |
| DELETE | /blocks/{user_id} | ✅ | → 204: the block lifted and kept (D-860); twice, or never blocked, 204 | T-9.1 |
| GET | /blocks | ✅ | `?cursor=&limit=` → `Page<BlockedUser>` (`BlockedUserPage`): whom you block now, newest first by `(created_at, blocked_id)`; a deleted account as `deleted`; never who blocks you (D-863) | T-9.1 |

## Wallet & payments
Users see Velas (D-049). The contract keeps the neutral name `credits` in fields, paths and error
codes (`credits`, `bonus_credits`, `/admin/users/{id}/credits`, `INSUFFICIENT_CREDITS`); the web
turns them into copy.

| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /wallet | ✅ | → `Wallet`: `{balance}`. A woman's is 0, never a refusal (D-076). No rate limit of its own (02-ARCHITECTURE §12) | T-5.3 |
| GET | /wallet/ledger | ✅ | `?cursor=&limit=` → `Page<LedgerEntry>`, newest first by `(created_at, id)`. A woman's is empty, never a refusal. No rate limit of its own | T-5.3 |
| GET | /prices | 🔓 | → `{action: credits}`: every active action's price for a man; a woman pays 0 for each (D-098). Never gifts (`GET /gifts`), never an inactive action. No rate limit (02-ARCHITECTURE §12) | T-5.2 |
| GET | /packs | ✅ | → `Pack[]`: `{id, credits, price_paise, bonus_credits}`, the man's store by his price-test variant, B shown A's packs until T-10.4, in order, never empty (a store with no active pack is a 500, D-480). `bonus_credits` is the first-purchase bonus he would get buying it now, or 0. A woman: `NOT_ALLOWED` (D-076). No rate limit of its own | T-8.1 |
| POST | /payments/orders | ✅ | `{pack_id}` (nothing else: a body naming an amount or Velas is `VALIDATION_ERROR`, rule 6) + `Idempotency-Key` (8 to 64 of `A-Za-z0-9_-`) → `{payment_id, order_id, key_id, amount_paise}`, priced from the pack's row. A woman: `NOT_ALLOWED`, before any gateway is asked (D-076). A pack not active in his store: `NOT_FOUND`. The same key again: the same order; with another pack, `ALREADY_EXISTS` (D-481). Gateway down or unconfigured: `PROVIDER_UNAVAILABLE`, nothing written. 20 an hour per user | T-8.1 |
| POST | /payments/webhook | 🔓 signature | Razorpay's event, the raw body, `X-Razorpay-Signature` → `{}`. Bad or missing signature, or `RAZORPAY_WEBHOOK_SECRET` unset: `400 VALIDATION_ERROR`, nothing read. Signed but unreadable: `500`, so Razorpay retries. Anything else, applied or not: `200` (below). No rate limit (02-ARCHITECTURE §12) | T-8.2 |
| GET | /payments/{id} | ✅ | → `PaymentStatusView`: `{status, credits, bonus_credits}`, the caller's own payment; anyone else's, or none, `NOT_FOUND`, the same answer. No GST (D-482). No rate limit of its own | T-8.2 |
| POST | /refund-requests | ✅ | `{payment_id, reason}` (nothing else) → 201 `RefundRequest`: `{id, payment_id, reason, status, created_at}`. A broken payment's claim (D-580): `reason` is `missing_velas` or `duplicate_charge`, never a change of mind. The caller's own payment; anyone else's, or none, `NOT_FOUND`, the same answer. `missing_velas` on a `paid` or `refunded` payment: `NOT_ALLOWED`, `details.why` `velas_granted`. A second open claim on one payment: `ALREADY_EXISTS`. 10 a day per user | T-8.3 |
| GET | /referrals/me | ✅ | → `ReferralsMe`: `{code, invited, rewarded}`, the caller's own code, how many applied it and how many of those were rewarded; a woman's counted the same, though she is never paid (D-690). No rate limit of its own | T-8.6 |
| POST | /referrals/apply | 🔐 | `{code}` (1 to 32 characters, trimmed, nothing else) → 204. Paused (D-840): while `referral_reward_velas` isn't above 0, a missing row included, `NOT_ALLOWED`, `details.why` `referrals_paused`, before any other check, so no number's one slot is spent. Looked up as typed, case ignored, never checked for format (T-3.3). Before `done` only, the dob step included (D-078 deletes it with a minor's account), else `NOT_ALLOWED`, `details.why` `onboarding_done`; the caller's own code, `NOT_ALLOWED`, `own_code`; this number already a referee, on this account or any it had before, `ALREADY_EXISTS` (D-691); a code nobody has, or whose owner isn't `done` and `active` or `paused`, `NOT_FOUND`, the same answer (D-693). Rewarded later, when the referee's selfie matches or first purchase is captured: `referral_reward_velas` to each man on it, never a woman, the referrer up to `referral_rewards_max` (D-692). 10 an hour per user | T-8.6 |

**No GST in anything a user is shown about a payment while Velora is unregistered** (D-450,
D-482): not a field, not a word, in any case, in the order's response, `GET /packs`, `GET
/payments/{id}` or anything after them. P-350 adds the GST line, rate and GSTIN on registration.

**The webhook (T-8.2, D-520 to D-524)** handles `payment.captured` (credits the row's `credits`
and, if no other payment of his has moved money, its `bonus_credits`, once: a repeat, a second
payment on one order, an amount or currency not the row's, or an owner who isn't a man credits
nothing), `payment.failed` (a `created` row becomes `failed`, never anchored), `refund.created` and
`payment.dispute.created` (the Velas taken back, down to 0), `refund.failed` and
`payment.dispute.won` (exactly what was taken, given back), and `refund.processed` and
`payment.dispute.lost` (`refunded`). Every other event, and an order nobody made, is `200` and
logged. The Velas always come from the `payments` row, never the webhook (rule 6). A capture
that credits also rewards the payer's referral, if it is due, in the same transaction (T-8.6).

**Claims (T-8.3, D-580 to D-582)** are resolved by an admin, from what the gateway says about the
order, never the claim's kind or the admin's word: a **grant** is the webhook's own capture
(`purchase` and `purchase_bonus` under its key, never `admin_grant`), a **refund** returns a
captured payment no Velas can ever stand against, recorded on the claim (the credited payment's
row is never touched), and a **reject** says why. The webhook records each refund and dispute it
handles once, by its Razorpay id, whatever it took (`payment_reversals`, D-581), so a
redelivery never takes Velas bought since.

`LedgerEntry` (T-5.3): `id`, `delta`, `balance_after`, `reason` (`LedgerReason`, every value, with
`purchase_reversal` and `purchase_restored` since T-8.2, `welcome` since T-8.11, `admin_correction`
since T-9.5) and
`created_at`. Never its ref or its key. The web turns `reason` into words from `en.ts` (D-033,
P-26); the API sends the enum only. Entries from one transaction share `created_at`, so among them
the order is by `id`: stable, though not the order they were written. Whatever the cursor, the
list is the caller's own (D-270).

## Notifications
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /push/key | ✅ | → `{public_key}`, the VAPID public key, base64url. `NOT_FOUND` where push isn't on: local and CI (the fake), and `PUSH_PROVIDER=off`, staging's and production's until D-857 (D-856) | T-9.4 |
| POST | /push/subscriptions | ✅ | `{endpoint, keys:{p256dh, auth}}` → 201 `{endpoint}`. The endpoint must be `https`, no port, on a known push service, else `VALIDATION_ERROR` (D-855); the keys a P-256 point and a 16-byte secret, never returned. One row per endpoint: a browser signed in to another account moves to it; a person keeps their newest 10. 10 a minute | T-9.4 |
| DELETE | /push/subscriptions | ✅ | `{endpoint}` → 204: your own at that endpoint; anyone else's, or none, untouched, the same answer | T-9.4 |
| GET | /notification-prefs | ✅ | → `Prefs` | T-9.4 |
| PATCH | /notification-prefs | ✅ | `Partial<Prefs>` → `Prefs`. An unknown field, or none sent, `VALIDATION_ERROR` | T-9.4 |
| GET | /notifications | ✅ | `?cursor=&limit=` → `NotificationPage`, your own, newest first by `(created_at, id)`, none about someone either of you has blocked (P-760, D-858) | T-9.4 |
| POST | /notifications/read | ✅ | → 204: every unread one of yours, read now | T-9.4 |

`Prefs` (T-9.4, D-851): `{match, message, like, knot, expiry, balance, gift, album, generic_text}`,
each a boolean. Each kind's setting governs its push only; the in-app row is written either way.
`generic_text` sends no name in a push.

`Notification`: `{id, kind, data, read_at, created_at}`. `kind` is one of `match`, `thread`,
`gift`, `album_request`, `album_decided`, `knot_requested`, `knot_accepted`, `thread_expiring` (a
man's only) or `low_balance` (a man's only); `message` and `like` are pushes only (D-852). `data`
is the kind's ids and flags (`user_id`, `thread_id`, `match_id`, `gift_send_id`, `gift_id`,
`album_request_id`, `granted`, `balance`, `expires_at` for his `thread_expiring`). The web turns
`kind` into words (D-033). A push carries `{kind, …}` with only `rules.PUSHED_FIELDS`' ids and
flags, and `name`, the other person's first name, unless `generic_text`: never an expiry, a price,
a balance or a message's text (P-460).

## Admin 🛡
**Every route declares its own `require_role`** (P-30): the web's `/admin` gate is UX, never
protection (D-024). 🛡 is a moderator or an admin unless a row says admin only. **Every call writes
`audit_log`**, a read included, in the transaction that read or changed what it names; a refused call
changes nothing and writes nothing (D-920). Reasons and notes are 10 to 500 characters.

| Method | Path | Body → Response | Task |
|---|---|---|---|
| GET | /admin/metrics | → `AdminMetrics`: `{users_by_status, signups_24h, signups_7d, reports_open, oldest_open_report_at, photos_pending, frozen, claims_open, revenue}`; `revenue` `{last_7_days_paise, last_30_days_paise, financial_year, financial_year_paise}`, paid payments as D-483 counts them, **null for a moderator** (D-926) | T-9.5 |
| GET | /admin/turnover | `?year=` (the financial year's first, 2026 for 2026-27; this one if absent) → `Turnover`: `{financial_year, starts_at, ends_at, turnover_paise, paid_payments, alert_at_paise, threshold_paise}`, paid payments in the year, 1 April to 31 March in IST. **Admin only**, never a moderator; each call writes `audit_log` (D-483) | T-8.1 |
| GET | /admin/refund-requests | `?status=&cursor=&limit=` → `Page<AdminRefundRequest>`: the claims in `status` (`open` if absent), oldest first by `(created_at, id)`, each `{id, user_id, payment_id, order_id, payment_status, reason, status, note, provider_payment_id, provider_refund_id, created_at, resolved_at}`. **Admin only**, never a moderator; each call writes `audit_log` (D-582) | T-8.3 |
| POST | /admin/refund-requests/{id}/resolve | `{action, note?}` → `AdminRefundRequest`. `action`: `grant`, `refund` or `reject` (`note` required, `VALIDATION_ERROR` otherwise). The gateway's payments on the order decide (D-580): a grant needs no credit yet and a captured payment for the order's amount, else `NOT_ALLOWED`, `details.why` `credited` or `nothing_to_grant`; a refund needs a captured, untouched payment that isn't the credited one nor one a grant could credit, else `nothing_to_refund`; a claim not `open`, `resolved`. Gateway down: `PROVIDER_UNAVAILABLE`, nothing changed. None: `NOT_FOUND`. **Admin only**; each resolution writes `audit_log` | T-8.3 |
| GET | /admin/users | `?q=&cursor=&limit=` → `Page<AdminUser>`, newest first by `(created_at, id)`, never the system user. `q`: a whole Indian number, normalised and hashed and matched exactly, every account it had, an erased one too (D-061, D-500); an account's id; or 2 to 50 characters, a username's or first name's start (`@` optional, `_` and `%` as characters); absent, the newest. A number one digit short, or any `q` out of shape, `VALIDATION_ERROR`. The audit row says how, never what was typed (D-927) | T-9.5 |
| GET | /admin/users/{id} | → `AdminUserDetail`: `{user: AdminUser, phone, phone_masked, is_verified, balance, ban, photos, fraud, reports_about, reports_by, ledger, threads}`, each list its newest 50; `phone` whole for an admin, the view audited `phone_shown`, masked for a moderator, null once erased (D-927); `photos` public and private only, never a selfie or the face photo (D-925); `ledger` with each entry's ref. None, or the system user, `NOT_FOUND` | T-9.5 |
| POST | /admin/users/{id}/status | `{status, reason}` → 204. `frozen` (moderator or admin) for an `active` or `paused` account; `banned` (admin) for any not banned, an erased one by its number alone; `active` (admin) lifts a freeze through D-906's path or a ban in place, to `deleted` if it had asked to go (D-922). A freeze or ban revokes every session and closes every socket (D-557). A moderator's ban or lift `FORBIDDEN`; any other move `NOT_ALLOWED` with `details.why` (`already_frozen`, `already_banned`, `not_banned`, `not_frozen`, or the status); `reason` 10 to 500 | T-9.5 |
| POST | /admin/users/{id}/credits | `{delta, reason}` + `Idempotency-Key` (8 to 64 of `A-Za-z0-9_-`) → 204. **Admin only.** `delta` an integer, 1 to 1,000 either way, never 0: positive an `admin_grant`, negative an `admin_correction`, each naming its call's `audit_log` row (D-923). A man's only, else `NOT_ALLOWED` `why: not_a_man` (D-076); a correction beyond the balance `NOT_ALLOWED` `why: balance` with `details.balance`, never `INSUFFICIENT_CREDITS`. The same key again for the same change: 204, nothing written; for another, `ALREADY_EXISTS` | T-9.5 |
| GET | /admin/reports | `?status=open&cursor=&limit=` → `Page<AdminReport>`: oldest first by `(created_at, id)`, each with its two people (`AdminUserRef`), `thread_id` and `due_at`, 24 hours from `created_at` (D-921) | T-9.5 |
| POST | /admin/reports/{id}/resolve | `{action, note}` → 204: `none` dismisses; `warn` (recorded only), `freeze` and `ban` action, the last two as `/status` would, someone already frozen or banned left so; `ban` an admin's (`FORBIDDEN`). The note, 10 to 500, kept in `audit_log.meta`. Resolved already, `NOT_ALLOWED` `why: resolved` (D-921) | T-9.5 |
| GET | /admin/moderation | `?cursor=&limit=` → `Page<AdminPhoto>`: pending public and private photos, oldest first, never a selfie or the face photo (D-925); each with `minor_score` (D-101) and a 10-minute signed link | T-9.5 |
| POST | /admin/photos/{id}/decide | `{approve, reason?, note?}` → 204. Approve a pending photo, published as the worker would; or take down a pending or approved one, `reason` `nudity`, `text_overlay` or `other` and a `note` 10 to 500, its public copies deleted and the private one kept; an approval takes neither (`VALIDATION_ERROR`). Completeness follows (P-210). Rejected already `NOT_ALLOWED` `why: rejected`; approved already `why: approved`; a selfie, the face photo or none, `NOT_FOUND`; storage down, `PROVIDER_UNAVAILABLE` (D-925) | T-9.5 |
| GET | /admin/threads/{id}/messages | `?reason=&cursor=&limit=` → `Page<AdminMessage>`: every message, oldest first, what either person cleared included (T-7.8, D-006); `body` as written (`body_raw` where masked), `masked`, a voice note's 10-minute `audio_url`. `reason` 10 to 500 once trimmed, else `VALIDATION_ERROR`; each page read audited with it (D-924). None, `NOT_FOUND` | T-9.5 |
| GET | /admin/audit | `?action=&cursor=&limit=` → `Page<AuditEntry>` `{id, actor_id, actor_is_system, action, target_type, target_id, meta, created_at}`, newest first, `action` filtering to one (D-920, D-905) | T-9.5 |
| GET | /admin/freezes | `?cursor=&limit=` → `Page<AdminFreeze>` `{user: AdminUser, frozen_at, automatic, rule, score}`: the accounts frozen now, the newest freeze first, the system user's marked `automatic` with its rule and score (P-800, D-928) | T-9.5 |

## Misc
| Method | Path | Auth | Task |
|---|---|---|---|
| POST | /waitlist | 🔓 | T-2.3 |
| GET | /healthz · /readyz | 🔓 | T-1.4 |

`POST /waitlist`: `{email, city?}` → `201 {}`, the same for an email already on the list (D-057).
Five tries a minute per client IP, invalid ones included → `RATE_LIMITED` (D-056).

## Local only (never in OpenAPI)
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /test/sms/last-code | 🔓 | `{phone}` → `{code}`, the code the fake SMS last sent the number, or `null` | T-3.13 |
| POST | /test/payments/webhook | 🔓 | `{payment_id, outcome: captured\|failed, amount_paise?}` → `{delivered_status}`: the fake gateway's signed webhook for that payment, delivered in process to `POST /v1/payments/webhook`, and the status it answered (200 since T-8.2 built the route). `amount_paise` fakes a mismatch | T-8.1 |

Each is kept out of the OpenAPI schema, so `make types` is the same everywhere and the web can't
call it, and each is a 404 everywhere but where its allowlists say (rule 16).

`/test/sms/last-code` is served only where `ENV` is `local` and `SMS_PROVIDER` is `fake`. The
number is in the body, never the path or query, which the request logger and uvicorn's access log
record (rule 15). It reads the fake's outbox, not the stored code: a number the
API sent nothing to (D-073) gets `null`, as its phone would. The E2E is its only caller (06-TESTING).

`/test/payments/webhook` is served only where `ENV` is `local` and `PAYMENTS_PROVIDER` is `fake`:
anywhere else it would pay for Velas with nothing. It builds the webhook from the `payments` row,
so it works for an order made before the API restarted, and signs it with the fake's secret, so
T-8.2's route verifies it with the same code as Razorpay's. It stands in for Razorpay locally: a
fake order is paid by calling it, for T-8.2's tests and T-8.7's local checkout.

---

## Error codes

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | body failed schema |
| `UNSUPPORTED_IMAGE` | 422 | not a JPEG, PNG or WebP, by its bytes; `details.accepted`. The message says what to do (D-089) |
| `IMAGE_TOO_LARGE` | 422 | over 8 MB; `details.max_bytes` |
| `UNSUPPORTED_AUDIO` | 422 | a voice note that isn't WebM, Ogg Opus or MP4 audio by its bytes, or the type its URL was signed for, or whose length can't be told; `details.accepted` (D-620) |
| `AUDIO_TOO_LARGE` | 422 | a voice note over 2 MB; `details.max_bytes` (D-620) |
| `AUDIO_TOO_LONG` | 422 | a voice note over 60 seconds, measured; `details.max_seconds` (D-620) |
| `AUTH_REQUIRED` / `TOKEN_EXPIRED` / `SESSION_REVOKED` | 401 | `SESSION_REVOKED` also for a `deleted` account's access token or refresh (D-500): signing in again restores it |
| `INSUFFICIENT_CREDITS` | 402 | `details.required`, `details.balance` |
| `PRICE_CHANGED` | 409 | a paid action whose `shown_price` (0 when absent) isn't its price now; nothing charged or written; `details.price`, the price now (P-56, D-600) |
| `FORBIDDEN` | 403 | wrong role; a status no one has allowed to sign in (D-067's allowlist) |
| `ACCOUNT_FROZEN` / `ACCOUNT_BANNED` | 403 | |
| `BLOCKED` | 403 | never sent: across a block everything is `NOT_FOUND` (D-862) |
| `ONBOARDING_INCOMPLETE` | 403 | `details.step`, the user's current step (D-068) |
| `PROFILE_INCOMPLETE` | 403 | finishing onboarding with something missing; `details.missing`, every one, in onboarding's order: `seeking`, `intents`, `first_name`, `hometown`, `city`, `location`, `username`, `about`, `interests` (D-310; no photo since T-4.12, D-392) |
| `FACE_PHOTO_REQUIRED` | 403 | leaving the `photos` step with no face photo, pending or approved, by anyone but a man (D-391, T-4.12) |
| `VERIFICATION_REQUIRED` | 403 | anyone but a man without a matched selfie: a woman, or someone with no gender (D-310) |
| `NOT_FOUND` | 404 | also used when a blocked user is looked up |
| `USERNAME_TAKEN` | 409 | |
| `ALREADY_EXISTS` | 409 | duplicate swipe/report/etc.; a second kudos to the same person, whatever its kind (D-680); an order's `Idempotency-Key` sent again for another pack (D-481); a gift's for another gift or woman (D-653); a second open claim on one payment (D-580) |
| `THREAD_EXPIRED` | 410 | his send on an expired Thread; hers is delivered (D-097). Expired by the clock, though the cron hasn't caught its status up (D-560) |
| `ACCOUNT_DELETED` | 410 | a message, kudos or a knot tap to someone who deleted their account (D-500, D-555, D-680, D-770) |
| `UNDERAGE` | 422 | the account is deleted, only the number's hash kept (D-072) |
| `IMMUTABLE_FIELD` | 422 | gender/dob change; a username after onboarding (D-068) |
| `MESSAGE_REJECTED` | 422 | abuse or payment-solicitation filter; `details.rule` |
| `NOT_ALLOWED` | 422 | a referral code applied while referrals are paused, `details.why` `referrals_paused` (D-840); a voice note sent, or its upload URL asked for, by anyone but a woman; a locked voice note's file (D-621), kudos too early (`details.why` `too_early`: fewer than `kudos_min_messages`, or one of the two hasn't written, D-680), woman sending a gift, a woman's re-open or Extend, or either on a Knot or a private message (D-642), verifying a PIN when none is set (D-069), a woman's store or order (D-076); a claim's `missing_velas` on a payment that granted them, or a resolution the gateway's record doesn't allow, `details.why` (D-580); an album request, `details.why`: `recently_declined` (D-731), `empty_album`, `already_decided`, `not_granted` (D-732) |
| ~~`GIFT_LIMIT_REACHED`~~ | — | **Retired by D-650 (T-8.9):** no case. D-231 charges the sixteenth send a week rather than refusing it, and D-016 caps no paid gift. Never sent; never reused for anything else |
| `GIFT_COOLDOWN` | 429 | same gift to same person too soon; `details.retry_after_s` |
| `SWIPE_LIMIT_REACHED` | 429 | a man's daily cap (D-492); `details.limit`, `details.resets_at` (the next IST midnight) |
| `RATE_LIMITED` | 429 | `details.retry_after_s` |
| `OTP_INVALID` / `OTP_EXPIRED` / `OTP_TOO_MANY` | 400/400/429 | `OTP_INVALID`: `details.attempts_left`. `OTP_TOO_MANY`: 5 wrong for one code, or 10 for one phone in 24 h (D-066) |
| `FIREBASE_TOKEN_INVALID` | 401 | bad signature, an unknown key, expired, wrong audience or issuer, not a phone sign-in, a sign-in over 5 minutes old, or already used: one answer for all (D-085) |
| `PHONE_NOT_SUPPORTED` | 422 | non-`+91` number |
| `PIN_INVALID` | 401 | `details.attempts_left`; `details.reset_required` when the stored PIN can't be checked (D-069) |
| `INTERNAL` | 500 | unexpected server error; the message never contains internals |
| `PROVIDER_UNAVAILABLE` | 503 | SMS/payment provider down, or Razorpay's keys not set (P-382); Google's Firebase keys unreachable (D-085); the daily SMS cap reached (D-066); locally, a number not in `SMS_LOCAL_ALLOWED_TO` (D-064) |
| `NOT_READY` | 503 | a dependency of ours is not ready (`/readyz` only); `details` = `{"database": "ok"\|"fail", "redis": "ok"\|"fail"}` |
