# 04 · API contract

All routes under `/v1`. 🔓 = public, 🔐 = logged in, ✅ = logged in **and** onboarding done,
🛡 = moderator/admin. The **Task** column says which plan task builds it.
Request/response bodies are Pydantic schemas in each module's `schemas.py`; the OpenAPI output is
the source for `web/src/types/api.ts`.

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
| PUT | /me/location | 🔐 | `{lat, lng}` or `{area_id}` → 204 | T-4.10 |
| PATCH | /me/settings | ✅ | `{is_hidden?, hide_age?, hide_distance?, show_kudos?}` → `Me` | T-9.6 |
| POST | /me/pause | ✅ | → 204 | T-9.6 |
| POST | /me/export | ✅ | → 202 (emailed/downloadable later) | T-9.6 |
| DELETE | /me | ✅ | → 202, 30-day window | T-9.6 |
| GET | /interests | 🔓 | → `Interest[]` | T-3.8 |
| GET | /intents | 🔐 | → `Intent[]` | T-3.6 |
| GET | /areas?city= | 🔓 | → `Area[]` | T-4.10 |

Onboarding endpoints work at their step and after it, never before (D-068).

`Me` (T-3.5): `id`, `role`, `status`, `onboarding_step`, `gender`, `age`, `is_verified`,
`has_pin`, `referral_code`, `balance`, and `profile`: `first_name`, `username`, `about`,
`hometown`, `city`, `seeking`, `intent_ids`, `interest_ids`, `is_hidden`, `hide_age`,
`hide_distance`, `show_kudos`, `show_gifts`. The age, never the date of birth, and no phone
number: no screen shows either, so neither leaves the server (D-067's discipline).

## Photos & verification
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /photos/upload-url | 🔐 | `{kind, position?, content_type}` → `{photo_id, put_url, headers}`. `content_type` is `image/jpeg`, `image/png` or `image/webp`, signed into the PUT, so send `headers` with it; a hint, never what decides (D-089). Public: `position` 0–5, one per place; private: up to 6; selfie: one waiting. Each at its step or after (D-068). 30 an hour per user | T-4.2 |
| POST | /photos/{id}/complete | 🔐 | → `Photo` (pending). The object's bytes decide: a JPEG, PNG or WebP is queued for moderation (a selfie waits for T-4.5); anything else is `UNSUPPORTED_IMAGE`, over 8 MB `IMAGE_TOO_LARGE`, each rejecting the photo and removing its file. Saying it twice is harmless | T-4.2 |
| GET | /me/photos | 🔐 | → `Photo[]`: the owner's live public photos by place, then private; never selfies, rejected photos or anyone else's | T-4.3 |
| PATCH | /me/photos/order | 🔐 | `{photo_ids[]}`, exactly the live public photos, each once, the first the main one → `Photo[]`, places 0 onwards | T-4.3 |
| DELETE | /photos/{id} | 🔐 | → 204 (soft): rejected as `user_deleted`, its public copy removed; twice is once. A selfie, or the last public photo once past the `photos` step, is `NOT_ALLOWED` | T-4.3 |
| POST | /verification/challenge | 🔐 | → `{verification_id, pose}` | T-4.5 |
| POST | /verification/{id}/submit | 🔐 | `{photo_id}` → `Verification` (pending) | T-4.5 |
| GET | /verification/latest | 🔐 | → `Verification` | T-4.5 |

`Photo` (T-4.2, T-4.3): `id`, `kind`, `position`, `status`, `reject_reason`, and `url`: an approved
public photo at `PUBLIC_CDN_URL`, any other live one by a 10-minute signed link to its private copy,
`null` for a rejected one. A pending public photo completes the `photos` step (T-4.3).

## Discovery
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /discover | ✅ | `?feed=foryou|new|online&intent_ids=&verified=&cursor=` → `Page<Card>` (`intent_ids`: any overlap, D-041) | T-6.2 |
| POST | /swipes | ✅ | `{target_id, dir}` → `{matched, match_id?, swipes_left}` | T-6.4 |
| GET | /users/{id} | ✅ | → `PublicProfile` | T-6.3 |
| GET | /users/by-username/{u} | ✅ | → `PublicProfile` | T-6.6 |
| GET | /search | ✅ | `?q=` → `Page<CardLite>` (`@` prefix = username lookup) | T-6.6 |
| GET | /likes | ✅ | → `Page<LikeCard>` (blurred unless revealed; free for women) | T-6.7 |
| POST | /likes/{user_id}/reveal | ✅ | → `PublicProfile` (20 Velas) | T-6.7 |

## Threads & messages
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| GET | /threads | ✅ | `?tier=threads|knots&filter=all|unread|recent&q=&cursor=` → `Page<ThreadRow>` | T-7.2 |
| POST | /threads | ✅ | `{match_id}` or `{user_id, first_message}` → `Thread` (5 Velas) | T-7.1 |
| GET | /threads/{id} | ✅ | → `Thread` | T-7.2 |
| GET | /threads/{id}/messages | ✅ | `?cursor=` → `Page<Message>` | T-7.3 |
| POST | /threads/{id}/messages | ✅ | `{client_msg_id, kind, body?, media_key?, duration_s?}` → `Message` | T-7.3 |
| POST | /threads/{id}/read | ✅ | `{up_to_message_id}` → 204 | T-7.5 |
| POST | /threads/{id}/reopen | ✅ | → `Thread` (3 Velas) | T-7.6 |
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
| POST | /album-requests | ✅ | `{owner_id}` → `AlbumRequest` (5 Velas) | T-8.4 |
| GET | /album-requests/incoming | ✅ | → `AlbumRequest[]` | T-8.4 |
| POST | /album-requests/{id}/decide | ✅ | `{grant: bool}` → `AlbumRequest` (decline → refund) | T-8.4 |
| POST | /album-requests/{id}/revoke | ✅ | → 204 | T-8.4 |
| GET | /users/{id}/album | ✅ | → `{photos: [{url}]}` watermarked, only if granted | T-8.4 |
| GET | /gifts | ✅ | → `Gift[]` (id, label, asset, credits) | T-8.9 |
| POST | /gifts/send | ✅ | `{recipient_id, gift_id}` + Idempotency-Key → `GiftSend` | T-8.9 |
| GET | /me/gifts | ✅ | `?cursor=` → `Page<GiftSend>` received, with sender card | T-8.9 |
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
| GET | /wallet | ✅ | → `{balance}` | T-5.3 |
| GET | /wallet/ledger | ✅ | `?cursor=` → `Page<LedgerEntry>` | T-5.3 |
| GET | /prices | 🔓 | → `{action: credits}` | T-5.2 |
| GET | /packs | ✅ | → `Pack[]` (variant-aware) | T-8.1 |
| POST | /payments/orders | ✅ | `{pack_id}` + Idempotency-Key → `{payment_id, order_id, key_id, amount_paise}` | T-8.1 |
| POST | /payments/webhook | 🔓 signature | Razorpay events → 200 | T-8.2 |
| GET | /payments/{id} | ✅ | → `{status, credits, bonus_credits}` | T-8.2 |
| POST | /refund-requests | ✅ | `{payment_id, reason}` → 201 | T-8.3 |
| GET | /referrals/me | ✅ | → `{code, invited, rewarded}` | T-8.6 |
| POST | /referrals/apply | 🔐 | `{code}` → 204 (only during onboarding) | T-8.6 |

## Notifications
| Method | Path | Auth | Body → Response | Task |
|---|---|---|---|---|
| POST | /push/subscriptions | ✅ | `{endpoint, keys:{p256dh, auth}}` → 201 | T-9.4 |
| DELETE | /push/subscriptions | ✅ | `{endpoint}` → 204 | T-9.4 |
| GET | /notification-prefs | ✅ | → `Prefs` | T-9.4 |
| PATCH | /notification-prefs | ✅ | `Partial<Prefs>` → `Prefs` | T-9.4 |
| GET | /notifications | ✅ | `?cursor=` → `Page<Notification>` | T-9.4 |
| POST | /notifications/read | ✅ | → 204 | T-9.4 |

## Admin 🛡
| Method | Path | Body → Response | Task |
|---|---|---|---|
| GET | /admin/metrics | → counts, revenue, reports open | T-9.5 |
| GET | /admin/users | `?q=` → `Page<AdminUser>` | T-9.5 |
| GET | /admin/users/{id} | → full detail incl. fraud, reports, ledger | T-9.5 |
| POST | /admin/users/{id}/status | `{status, reason}` → 204 (freeze/ban/unban) | T-9.5 |
| POST | /admin/users/{id}/credits | `{delta, reason}` → 204 | T-9.5 |
| GET | /admin/reports | `?status=open` → `Page<Report>` | T-9.5 |
| POST | /admin/reports/{id}/resolve | `{action, note}` → 204 | T-9.5 |
| GET | /admin/moderation | → `Page<Photo>` pending/flagged | T-9.5 |
| POST | /admin/photos/{id}/decide | `{approve, reason?}` → 204 | T-9.5 |
| GET | /admin/threads/{id}/messages | → includes `body_raw` + cleared (audited) | T-9.5 |
| GET | /admin/audit | `?cursor=` → `Page<AuditEntry>` | T-9.5 |

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

Served only where `ENV` is `local` and `SMS_PROVIDER` is `fake` (an allowlist, rule 16); a 404
everywhere else. Kept out of the OpenAPI schema, so `make types` is the same everywhere and the web
can't call it. The number is in the body, never the path or query, which the request logger and
uvicorn's access log record (rule 15). It reads the fake's outbox, not the stored code: a number the
API sent nothing to (D-073) gets `null`, as its phone would. The E2E is its only caller (06-TESTING).

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
| `VERIFICATION_REQUIRED` | 403 | woman without approved selfie |
| `NOT_FOUND` | 404 | also used when a blocked user is looked up |
| `USERNAME_TAKEN` | 409 | |
| `ALREADY_EXISTS` | 409 | duplicate swipe/report/etc. |
| `THREAD_EXPIRED` | 410 | send on an expired thread |
| `UNDERAGE` | 422 | the account is deleted, only the number's hash kept (D-072) |
| `IMMUTABLE_FIELD` | 422 | gender/dob change; a username after onboarding (D-068) |
| `MESSAGE_REJECTED` | 422 | abuse or payment-solicitation filter; `details.rule` |
| `NOT_ALLOWED` | 422 | man sending voice note, kudos too early, woman sending a gift, verifying a PIN when none is set (D-069) |
| `GIFT_LIMIT_REACHED` | 429 | free gifts used up today; `details.resets_at` |
| `GIFT_COOLDOWN` | 429 | same gift to same person too soon; `details.retry_after_s` |
| `SWIPE_LIMIT_REACHED` | 429 | daily cap |
| `RATE_LIMITED` | 429 | `details.retry_after_s` |
| `OTP_INVALID` / `OTP_EXPIRED` / `OTP_TOO_MANY` | 400/400/429 | `OTP_INVALID`: `details.attempts_left`. `OTP_TOO_MANY`: 5 wrong for one code, or 10 for one phone in 24 h (D-066) |
| `FIREBASE_TOKEN_INVALID` | 401 | bad signature, an unknown key, expired, wrong audience or issuer, not a phone sign-in, a sign-in over 5 minutes old, or already used: one answer for all (D-085) |
| `PHONE_NOT_SUPPORTED` | 422 | non-`+91` number |
| `PIN_INVALID` | 401 | `details.attempts_left`; `details.reset_required` when the stored PIN can't be checked (D-069) |
| `INTERNAL` | 500 | unexpected server error; the message never contains internals |
| `PROVIDER_UNAVAILABLE` | 503 | SMS/payment provider down; Google's Firebase keys unreachable (D-085); the daily SMS cap reached (D-066); locally, a number not in `SMS_LOCAL_ALLOWED_TO` (D-064) |
| `NOT_READY` | 503 | a dependency of ours is not ready (`/readyz` only); `details` = `{"database": "ok"\|"fail", "redis": "ok"\|"fail"}` |
