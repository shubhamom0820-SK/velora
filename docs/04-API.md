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
| POST | /me/onboarding/complete | 🔐 | → `Me`, moving `selfie` → `done` (D-310). Every requirement met, or `PROFILE_INCOMPLETE` naming each one missing; a matched selfie for anyone but a man, or `VERIFICATION_REQUIRED`. Before `selfie`, `ONBOARDING_INCOMPLETE`; once `done`, `Me` unchanged. Sets `completeness` | T-4.8 |
| PUT | /me/location | 🔐 | `{lat, lng}`, inside India's box, or `{area_id}`, stored at its centroid → `Me` (D-220). Either is stored as its point of the 0.01° grid, never exactly (D-490). A position takes the nearest area within 2 km of the exact position, or none. From the `username` step on, never moving it; before, `ONBOARDING_INCOMPLETE`. Outside the box, or an area that isn't one: `VALIDATION_ERROR`. 10 an hour per user | T-4.10 |
| PATCH | /me/settings | ✅ | `{is_hidden?, hide_age?, hide_distance?, show_kudos?}` → `Me` | T-9.6 |
| POST | /me/pause | ✅ | → 204 | T-9.6 |
| POST | /me/export | ✅ | → 202 (emailed/downloadable later) | T-9.6 |
| DELETE | /me | ✅ | → 202, 30-day window | T-9.6 |
| GET | /interests | 🔓 | → `Interest[]` | T-3.8 |
| GET | /intents | 🔐 | → `Intent[]` | T-3.6 |
| GET | /areas?city= | 🔓 | → `Area[]`: `{id, city, name}`, never a centroid, by city then name; every city's, or `city`'s in any case (D-220) | T-4.10 |

Onboarding endpoints work at their step and after it, never before (D-068).

`Me` (T-3.5): `id`, `role`, `status`, `onboarding_step`, `gender`, `age`, `is_verified`,
`has_pin`, `referral_code`, `balance`, and `profile`: `first_name`, `username`, `about`,
`hometown`, `city`, `seeking`, `intent_ids`, `interest_ids`, `is_hidden`, `hide_age`,
`hide_distance`, `show_kudos`, `show_gifts`, and `location` (T-4.10): `none`, `fresh`, or `stale`
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
| GET | /discover | ✅ | `?feed=foryou|new|online&intent_ids=&verified=&cursor=&limit=` → `Page<Card>` (`intent_ids`: any overlap, D-041, 1 to 10 known ids, repeated as `intent_ids=1&intent_ids=2`; `verified=true`: the badge, D-393) | T-6.2 |
| POST | /swipes | ✅ | `{target_id, dir}` → `{matched, match_id?, swipes_left}` | T-6.4 |
| GET | /users/{id} | ✅ | → `PublicProfile`; `NOT_FOUND` for nobody and every refusal alike (D-493) | T-6.3 |
| GET | /users/by-username/{u} | ✅ | → `PublicProfile` | T-6.6 |
| GET | /search | ✅ | `?q=&cursor=&limit=` → `Page<CardLite>` (`@` prefix = username lookup) | T-6.6 |
| GET | /likes | ✅ | `?cursor=&limit=` → `Page<LikeCard>` (blurred unless revealed; free for women) | T-6.7 |
| POST | /likes/{user_id}/reveal | ✅ | → `PublicProfile` (`liked_you_reveal`'s price: 1 Vela from 8 October 2026, the founder; 20 before; P-370 moves the row) | T-6.7 |

`Card` (T-6.2, D-494): `id`, `first_name`, `age` (null if hidden), `username`, `city`, `hometown`,
`distance_km` (whole km between grid points, at least 1, D-034 and D-490; null if hidden),
`intent_ids`, `bio_line` (the first 90 characters of `about`), `main_photo_url` (the approved
public photo at the lowest place, P-75, or null, D-392), `shows_badge` (D-393's rule, never raw
`is_verified`), `is_online` (active within 5 minutes), `is_new` (joined within 7 days). Never a
date of birth, a position, a phone number or `is_verified`. The feed: everyone 02-ARCHITECTURE §8
leaves out stays out, ranked by D-491's score, best first, then by id; its cursor carries the
instant the scroll began, so time passing between pages can't repeat or skip a card (D-491).

`PublicProfile` (T-6.3, D-493): a `Card`, and `about` (whole), `photo_urls` (every approved public
photo in place order; the first is `main_photo_url`), `interest_ids`, `kudos` (`{great_conversation,
genuinely_funny, easy_to_talk_to, really_thoughtful}`, each a count; null when `show_kudos` is
off), `album_photo_count` (approved private photos, a number, never one of them), `match_id` and
`thread` (`{id, status, expires_at}`), what is already between the viewer and them, or null.
Shown to anyone `visible_to` allows without seeking or the radius (a link reaches past both); a
hidden profile only to someone it shares a match or a Thread with; your own always. Every refusal
is `NOT_FOUND`, the same body as an id nobody holds. A view is recorded, one row per pair,
counted, never for your own profile or a refusal.

## Threads & messages
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /threads | ✅ | `?tier=threads|knots&filter=all|unread|recent&q=&cursor=&limit=` → `Page<ThreadRow>` | T-7.2 |
| POST | /threads | ✅ | `{match_id}` or `{user_id, first_message}` → `Thread` (5 Velas from a match; 8 for a private message, D-231) | T-7.1 |
| GET | /threads/{id} | ✅ | → `Thread` | T-7.2 |
| GET | /threads/{id}/messages | ✅ | `?cursor=&limit=` → `Page<Message>` | T-7.3 |
| POST | /threads/{id}/messages | ✅ | `{client_msg_id, kind, body?, media_key?, duration_s?}` → `Message` | T-7.3 |
| POST | /threads/{id}/read | ✅ | `{up_to_message_id}` → 204 | T-7.5 |
| POST | /threads/{id}/reopen | ✅ | → `Thread` (2 Velas, D-098) | T-7.6 |
| POST | /threads/{id}/knot | ✅ | → `Thread` (sets your tap; converts when both) | T-7.7 |
| DELETE | /threads/{id}/knot | ✅ | → `Thread` (untie → active, fresh 24h) | T-7.7 |
| POST | /threads/{id}/clear | ✅ | → 204 (one-sided) | T-7.8 |
| POST | /threads/clear | ✅ | `{thread_ids[]}` or `{expired: true}` → `{cleared}` | T-7.8 |
| DELETE | /threads/{id}/clear | ✅ | → 204 (undo / restore) | T-7.8 |
| POST | /media/voice-upload-url | ✅ | `{thread_id}` → `{media_key, put_url}` (women only) | T-7.9 |
| POST | /messages/{id}/unlock | ✅ | → `{url}` (5 Velas, men) | T-7.9 |
| GET | /messages/{id}/media | ✅ | → `{url}` (signed, 10 min, only if unlocked or sender) | T-7.9 |

## Album, kudos, safety
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /album-requests | ✅ | `{owner_id}` → `AlbumRequest` (1 Vela, D-231) | T-8.4 |
| GET | /album-requests/incoming | ✅ | → `AlbumRequest[]` | T-8.4 |
| POST | /album-requests/{id}/decide | ✅ | `{grant: bool}` → `AlbumRequest` (a decline returns nothing, D-230) | T-8.4 |
| POST | /album-requests/{id}/revoke | ✅ | → 204 | T-8.4 |
| GET | /users/{id}/album | ✅ | → `{photos: [{url}]}` watermarked, only if granted | T-8.4 |
| GET | /gifts | ✅ | → `Gift[]` (id, label, asset, credits) | T-8.9 |
| POST | /gifts/send | ✅ | `{recipient_id, gift_id}` + Idempotency-Key → `GiftSend` | T-8.9 |
| GET | /me/gifts | ✅ | `?cursor=&limit=` → `Page<GiftSend>` received, with sender card | T-8.9 |
| GET | /users/{id}/gifts | ✅ | → `{counts:[{gift_id,count}]}` if `show_gifts` | T-8.9 |
| POST | /kudos | ✅ | `{to_id, kind}` → 201 | T-8.5 |
| GET | /me/kudos | ✅ | → `Kudos[]` | T-8.5 |
| POST | /reports | ✅ | `{reported_id, reason, details?, thread_id?, also_block}` → 201 | T-9.1 |
| POST | /blocks | ✅ | `{user_id}` → 201 | T-9.1 |
| DELETE | /blocks/{user_id} | ✅ | → 204 | T-9.1 |
| GET | /blocks | ✅ | → `BlockedUser[]` | T-9.1 |

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
| POST | /payments/webhook | 🔓 signature | Razorpay events → 200 | T-8.2 |
| GET | /payments/{id} | ✅ | → `{status, credits, bonus_credits}` | T-8.2 |
| POST | /refund-requests | ✅ | `{payment_id, reason}` → 201 | T-8.3 |
| GET | /referrals/me | ✅ | → `{code, invited, rewarded}` | T-8.6 |
| POST | /referrals/apply | 🔐 | `{code}` → 204 (only during onboarding) | T-8.6 |

**No GST in anything a user is shown about a payment while Velora is unregistered** (D-450,
D-482): not a field, not a word, in any case, in the order's response, `GET /packs`, `GET
/payments/{id}` or anything after them. P-350 adds the GST line, rate and GSTIN on registration.

`LedgerEntry` (T-5.3): `id`, `delta`, `balance_after`, `reason` (`LedgerReason`, every value) and
`created_at`. Never its ref or its key. The web turns `reason` into words from `en.ts` (D-033,
P-26); the API sends the enum only. Entries from one transaction share `created_at`, so among them
the order is by `id`: stable, though not the order they were written. Whatever the cursor, the
list is the caller's own (D-270).

## Notifications
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /push/subscriptions | ✅ | `{endpoint, keys:{p256dh, auth}}` → 201 | T-9.4 |
| DELETE | /push/subscriptions | ✅ | `{endpoint}` → 204 | T-9.4 |
| GET | /notification-prefs | ✅ | → `Prefs` | T-9.4 |
| PATCH | /notification-prefs | ✅ | `Partial<Prefs>` → `Prefs` | T-9.4 |
| GET | /notifications | ✅ | `?cursor=&limit=` → `Page<Notification>` | T-9.4 |
| POST | /notifications/read | ✅ | → 204 | T-9.4 |

## Admin 🛡
| Method | Path | Body → Response | Task |
|---|---|---|---|
| GET | /admin/metrics | → counts, revenue, reports open | T-9.5 |
| GET | /admin/turnover | `?year=` (the financial year's first, 2026 for 2026-27; this one if absent) → `Turnover`: `{financial_year, starts_at, ends_at, turnover_paise, paid_payments, alert_at_paise, threshold_paise}`, paid payments in the year, 1 April to 31 March in IST. **Admin only**, never a moderator; each call writes `audit_log` (D-483) | T-8.1 |
| GET | /admin/users | `?q=&cursor=&limit=` → `Page<AdminUser>` | T-9.5 |
| GET | /admin/users/{id} | → full detail incl. fraud, reports, ledger | T-9.5 |
| POST | /admin/users/{id}/status | `{status, reason}` → 204 (freeze/ban/unban) | T-9.5 |
| POST | /admin/users/{id}/credits | `{delta, reason}` → 204 | T-9.5 |
| GET | /admin/reports | `?status=open&cursor=&limit=` → `Page<Report>` | T-9.5 |
| POST | /admin/reports/{id}/resolve | `{action, note}` → 204 | T-9.5 |
| GET | /admin/moderation | `?cursor=&limit=` → `Page<Photo>` pending/flagged | T-9.5 |
| POST | /admin/photos/{id}/decide | `{approve, reason?}` → 204 | T-9.5 |
| GET | /admin/threads/{id}/messages | → includes `body_raw` + cleared (audited) | T-9.5 |
| GET | /admin/audit | `?cursor=&limit=` → `Page<AuditEntry>` | T-9.5 |

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
| POST | /test/payments/webhook | 🔓 | `{payment_id, outcome: captured\|failed, amount_paise?}` → `{delivered_status}`: the fake gateway's signed webhook for that payment, delivered in process to `POST /v1/payments/webhook`, and the status it answered (404 until T-8.2 builds the route). `amount_paise` fakes a mismatch | T-8.1 |

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
| `AUTH_REQUIRED` / `TOKEN_EXPIRED` / `SESSION_REVOKED` | 401 | |
| `INSUFFICIENT_CREDITS` | 402 | `details.required`, `details.balance` |
| `FORBIDDEN` | 403 | wrong role; a `deleted` account until T-9.6 (D-067) |
| `ACCOUNT_FROZEN` / `ACCOUNT_BANNED` | 403 | |
| `BLOCKED` | 403 | either side blocked |
| `ONBOARDING_INCOMPLETE` | 403 | `details.step`, the user's current step (D-068) |
| `PROFILE_INCOMPLETE` | 403 | finishing onboarding with something missing; `details.missing`, every one, in onboarding's order: `seeking`, `intents`, `first_name`, `hometown`, `city`, `location`, `username`, `about`, `interests` (D-310; no photo since T-4.12, D-392) |
| `FACE_PHOTO_REQUIRED` | 403 | leaving the `photos` step with no face photo, pending or approved, by anyone but a man (D-391, T-4.12) |
| `VERIFICATION_REQUIRED` | 403 | anyone but a man without a matched selfie: a woman, or someone with no gender (D-310) |
| `NOT_FOUND` | 404 | also used when a blocked user is looked up |
| `USERNAME_TAKEN` | 409 | |
| `ALREADY_EXISTS` | 409 | duplicate swipe/report/etc.; an order's `Idempotency-Key` sent again for another pack (D-481) |
| `THREAD_EXPIRED` | 410 | his send on an expired Thread; hers is delivered (D-097) |
| `UNDERAGE` | 422 | the account is deleted, only the number's hash kept (D-072) |
| `IMMUTABLE_FIELD` | 422 | gender/dob change; a username after onboarding (D-068) |
| `MESSAGE_REJECTED` | 422 | abuse or payment-solicitation filter; `details.rule` |
| `NOT_ALLOWED` | 422 | man sending voice note, kudos too early, woman sending a gift, verifying a PIN when none is set (D-069), a woman's store or order (D-076) |
| `GIFT_LIMIT_REACHED` | 429 | free gifts used up today; `details.resets_at`. D-231 charges the sixteenth send a week rather than refusing it, so T-8.9 says whether this keeps a case |
| `GIFT_COOLDOWN` | 429 | same gift to same person too soon; `details.retry_after_s` |
| `SWIPE_LIMIT_REACHED` | 429 | daily cap |
| `RATE_LIMITED` | 429 | `details.retry_after_s` |
| `OTP_INVALID` / `OTP_EXPIRED` / `OTP_TOO_MANY` | 400/400/429 | `OTP_INVALID`: `details.attempts_left`. `OTP_TOO_MANY`: 5 wrong for one code, or 10 for one phone in 24 h (D-066) |
| `FIREBASE_TOKEN_INVALID` | 401 | bad signature, an unknown key, expired, wrong audience or issuer, not a phone sign-in, a sign-in over 5 minutes old, or already used: one answer for all (D-085) |
| `PHONE_NOT_SUPPORTED` | 422 | non-`+91` number |
| `PIN_INVALID` | 401 | `details.attempts_left`; `details.reset_required` when the stored PIN can't be checked (D-069) |
| `INTERNAL` | 500 | unexpected server error; the message never contains internals |
| `PROVIDER_UNAVAILABLE` | 503 | SMS/payment provider down, or Razorpay's keys not set (P-382); Google's Firebase keys unreachable (D-085); the daily SMS cap reached (D-066); locally, a number not in `SMS_LOCAL_ALLOWED_TO` (D-064) |
| `NOT_READY` | 503 | a dependency of ours is not ready (`/readyz` only); `details` = `{"database": "ok"\|"fail", "redis": "ok"\|"fail"}` |
