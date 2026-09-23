# 06 · Testing

## The rule

A task isn't done until its tests pass. Tests are written in the same task as the code — not
"later". A bug fix starts with a failing test that reproduces it.

## Layers

| Layer | Tool | What | Speed target |
|---|---|---|---|
| Unit (api) | pytest | pure functions: security, masking regexes, pricing, ranking score, fraud weights | < 5 s total |
| Service (api) | pytest + real Postgres + fake providers | business rules through the service layer | < 60 s total |
| API (api) | pytest + httpx AsyncClient | status codes, error codes, auth, schemas | inside the above |
| Unit (web) | vitest + Testing Library | primitives, hooks, formatters, countdown | < 20 s |
| E2E | Playwright (Chromium, mobile viewport 390×844 + desktop 1280×800) | the user journeys below | < 5 min |

No mocking of the database — tests use a real Postgres (`velora_test`). External services always
use the **fake** providers from `app/core/providers/`.

## Fixtures (api)

- `db` — session inside a transaction rolled back after each test.
- `client` — AsyncClient on the app with dependency overrides for providers.
- `make_user(gender="male", onboarded=True, credits=0, verified=False)` → `(user, token)`.
- `make_thread(a, b, status="active", messages=0)`.
- `clock` — freezes/advances "now" for expiry tests (the app reads time only through
  `core.clock.now()` — never `datetime.now()` directly).
- `fake_sms.last_code(phone)`, `fake_payments.capture(order_id)`, `fake_moderation.next = "reject:nudity"`.

## Tests that must never be skipped 🔒

If any of these fails, nothing ships.

1. **Wallet concurrency** (T-5.4): 50 parallel debits on 10 credits → exactly 2 succeed.
2. **Wallet idempotency** (T-5.4): same key 50× concurrently → one entry.
3. **Webhook idempotency** (T-8.2): same capture 5× concurrently → credited once.
4. **Webhook signature** (T-8.2): bad signature → no credit.
5. **Ledger reconciliation** (T-9.9): `balance == sum(delta)` for every wallet.
6. **Women never pay** (T-9.9): every paid action by a woman → zero ledger entries.
6b. **Free gifts stay free** (T-8.9): a free gift creates a `gift_sends` row and **zero** ledger
    entries; a paid gift creates exactly one with the price from the `gifts` table.
7. **Age gate** (T-3.6): 17y364d refused and banned; exactly 18 today accepted.
8. **Gender immutable** (T-1.16, T-3.6): second set → `IMMUTABLE_FIELD`; DB trigger also blocks.
9. **Blocks are total** (T-9.1): after a block, neither side appears to the other anywhere.
10. **Clearing is one-sided** (T-7.8): A clears → B still sees every message.
11. **Contact masking** (T-7.3): numbers, spaced digits, emails, UPI IDs, social handles masked in
    the first 20 messages; `body_raw` never returned by any user-facing endpoint.
12. **Expired thread** (T-7.6): sending → `THREAD_EXPIRED`; re-open charges exactly 3.
13. **Velora is mutual** (T-7.7): one tap never converts; two taps always do.
14. **Private data** (T-4.4, T-4.5): processed images contain no EXIF; selfies never appear in
    any public response.
15. **Refresh reuse** (T-3.4): replaying a rotated refresh token revokes the family.
16. **Firebase token** (T-3.14): forged, expired, wrong-audience and already-used ID tokens are all
    rejected; a non-`+91` number never creates a user.

A test in this list is marked `@pytest.mark.critical`; CI runs them first and fails fast.

## E2E journeys

| # | Journey | Task |
|---|---|---|
| J1 | New man: phone → OTP → all onboarding → discover | T-3.13, T-4.9 |
| J2 | New woman: blocked until selfie approved | T-4.9 |
| J3 | Under-18 refused, same number can't retry | T-3.13 |
| J4 | Swipe → match → open thread (−5) → chat both ways live | T-7.13 |
| J5 | Voice note from woman → man unlocks (−5) → plays | T-7.13 |
| J6 | Both tie the knot → Knots tab, no countdown | T-7.13 |
| J7 | Thread expires → read-only → re-open (−3) | T-7.13 |
| J8 | Buy credits (fake gateway) → balance updates | T-8.7 |
| J9 | Payment fails → retry sheet → success | T-8.7 |
| J10 | Report with also-block → confirmation shown → person gone everywhere | T-9.1 |
| J11 | Moderator resolves a report and freezes the account | T-9.5 |
| J12 | Clear chat → undo → restore from You tab | T-7.10 |

Run E2E on every PR touching `web/` and nightly against staging.

## What not to test

Third-party SDK internals, Tailwind classes, exact copy text (test by role/label instead),
and anything already enforced by the type checker.

## CI order

1. ruff + mypy + eslint + tsc (fail fast, ~1 min)
2. `pytest -m critical`
3. rest of pytest + vitest (parallel jobs)
4. `next build`
5. Playwright (only if 1–4 pass)
