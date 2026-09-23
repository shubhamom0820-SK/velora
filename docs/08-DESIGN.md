# 08 · Design system

The prototype is the visual reference for every screen. This file turns it into rules so the
real app stays consistent.

## 1. Tokens — the only place colours live

`web/src/styles/tokens.css`. Components use **semantic** names only (`--surface`, never `#FFFFFF`).
Theme is chosen by `data-theme` on `<html>`; default is `blend` (D-014).

```css
:root, [data-theme="blend"] {
  /* content (soft white) */
  --page:#E7E4E3; --bg:#F6F4F3; --surface:#FFFFFF; --surface-2:#ECE8E7; --line:#E2DDDC;
  --ink:#1A1517; --mute:#6E6668;
  --accent:#CF2A40; --accent-soft:rgba(207,42,64,.09); --on-accent:#FFFFFF;
  /* chrome (black): header, bottom nav, hero, match sheet, wallet card, lock screen */
  --chrome:#141113; --chrome-ink:#F3EFEE; --chrome-mute:#A29A9C; --chrome-line:#2B2528;
  --chrome-accent:#E8475A; --chrome-accent-soft:rgba(232,71,90,.16);
  /* on-photo text (cards, call screen) */
  --on-photo:#FFFFFF; --photo-scrim:linear-gradient(to top, rgba(6,3,6,.94), rgba(6,3,6,.55) 52%, transparent);
  --shadow-1:0 4px 14px rgba(207,42,64,.24); --shadow-2:0 10px 26px rgba(20,12,15,.14);
  --scrim:rgba(10,8,9,.45);
}
[data-theme="dark"] {
  --page:#080508; --bg:#120C0F; --surface:#1C1418; --surface-2:#261C21; --line:#33262C;
  --ink:#F5EDEE; --mute:#9B8B90; --accent:#E62945; --accent-soft:rgba(230,41,69,.13);
  --chrome:#120C0F; --chrome-ink:#F5EDEE; --chrome-mute:#9B8B90; --chrome-line:#33262C;
  --chrome-accent:#E62945; --chrome-accent-soft:rgba(230,41,69,.13);
  --shadow-1:0 6px 22px rgba(230,41,69,.32); --shadow-2:0 18px 44px rgba(0,0,0,.55);
  --scrim:rgba(4,2,4,.72);
}
[data-theme="soft"] {
  --page:#E6DEDA; --bg:#F2ECE8; --surface:#F9F5F2; --surface-2:#E7DDD8; --line:#DDD1CC;
  --ink:#2E2428; --mute:#7C6F73; --accent:#BF3A4D; --accent-soft:rgba(191,58,77,.10);
  --chrome:#F2ECE8; --chrome-ink:#2E2428; --chrome-mute:#7C6F73; --chrome-line:#DDD1CC;
  --chrome-accent:#BF3A4D; --chrome-accent-soft:rgba(191,58,77,.10);
  --shadow-1:0 4px 12px rgba(191,58,77,.20); --shadow-2:0 10px 26px rgba(70,40,45,.12);
  --scrim:rgba(40,16,24,.36);
}
```

Rules:
- Text on `--accent` is `--on-accent`. Text on photos is `--on-photo` over `--photo-scrim`.
- Anything inside a chrome area uses the `--chrome-*` set.
- Contrast: body text ≥ 4.5:1, large text ≥ 3:1 in all three themes (checked in T-9.11).
- `<meta name="theme-color">` = `--chrome`.

## 2. Type

System font stack (no web font download): `-apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif`.
Devanagari falls back to Noto Sans Devanagari on Android.

| Token | Size / line / weight | Use |
|---|---|---|
| `display` | 42 / 1.05 / 700, tracking −2 | landing hero |
| `title-1` | 24 / 1.2 / 700 | screen titles, onboarding questions |
| `title-2` | 18 / 1.3 / 700 | sheet titles |
| `body` | 14.5 / 1.6 / 400 | paragraphs, about |
| `ui` | 14 / 1.4 / 500–600 | buttons, list rows |
| `small` | 12.5 / 1.5 / 400 | helper text |
| `micro` | 11 / 1.3 / 600 | badges, timestamps |

## 3. Space, shape, motion

- Spacing scale (px): 4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56. Screen padding 16–20 mobile, 24 desktop.
- Radius: 10 inputs/small buttons · 12 buttons · 14 cards · 16 chat bubbles · 24 sheets · 26 swipe card · 999 pills.
- Content max-width: 520 px for app screens (centred on desktop), 900–1100 px for marketing/admin.
- Motion: 150 ms for press/hover, 250–300 ms for sheets, spring for the deck. Respect
  `prefers-reduced-motion` (no rotation, fade instead).
- Tap targets ≥ 44 × 44 px.

## 4. Components (`src/components/ui/`)

| Component | Variants / states |
|---|---|
| Button | primary · ghost · danger · chrome; sm · md; loading · disabled |
| IconButton | round, sizes 40/46/56, optional price tag badge |
| Chip | default · active · removable |
| Field / TextArea | label, helper, error, counter |
| OtpInput | 4 boxes, paste, auto-advance, backspace-back |
| Toggle | on · off · disabled |
| Sheet | bottom (mobile) / centred (desktop); title; scroll body; sticky footer |
| Toast | info (ink) · error (accent) · with action (Undo) |
| Avatar | photo · initial fallback · online dot · verified badge |
| Badge | count · status pill (Online, New, Knotted, intent) |
| Skeleton | line · card · avatar |
| EmptyState / ErrorState | icon, title, body, action |
| Countdown | shared ticker; `4h 59m left` → `12m 30s left` → `Expired` |
| GiftGrid | 6 tiles, 3×2; free tiles show remaining count, paid show credits |
| PriceTag | shows credits for men, "free" for women (reads from `/prices`) |

Feature components live in `src/components/<feature>/` (discover, chat, wallet, profile, admin).

## 5. Screen inventory

Every screen must exist in the prototype first. ✦ = uses chrome in the blend theme.

**Marketing:** Landing ✦(header, hero, footer) · Terms · Privacy · Refunds · Contact · Public profile `/@username`.

**Onboarding (12):** Phone · OTP · DOB · Gender · Seeking + intent · Name + places · Username ·
About · Photos · Interests · PIN · Selfie.

**App:** Header ✦ · Bottom nav ✦ · Discover (deck, feeds, search, filters sheet) · Match sheet ✦ ·
Liked you grid · Profile (gallery, gifts row + gift sheet, album, ⋯ menu, report sheet, block sheet, share sheet) ·
Chats list (Threads / Knots) · Conversation (knot bar, expired panel) · Wallet (balance card ✦,
prices, history) · Store sheet · Checkout states (processing, failed) · You · Settings sheets
(edit profile, notifications, privacy) · Lock screen ✦ · Notifications list.

**Admin:** Dashboard · Reports queue · User detail · Moderation queue · Audit log (header ✦).

## 6. Copy voice

Short, warm, plain. Say what happens, not what the system is. "Cleared from your chats" not
"Deleted". "This thread disappears in 4h" not "TTL remaining". Prices always in credits with the
number first: "Open thread · 5 credits". Never shame or pressure ("Only 2 left!").
