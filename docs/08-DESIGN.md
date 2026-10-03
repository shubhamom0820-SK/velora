# 08 · Design system

The prototype (`docs/prototype/velora-prototype-reference.html`) is the visual reference for every
screen. It predates the rename to Velora, so it uses "Knot" as the app's name — the screens and
flows are the reference, not the name. **Only the brand changed.** Where the prototype names the
app, read Velora (`APP_NAME`). Thread and Knot stay as the product's nouns ("Tie the knot",
"Knots last", the Knots tab) and are never replaced (CLAUDE.md rule 17). Its "credits" are
Velas, the unit of paid balance (D-049). This file turns the prototype into rules so the real
app stays consistent.

## 1. Tokens — the only place colours live

`web/src/styles/tokens.css`. Components use **semantic** names only (`--surface`, never `#FFFFFF`).
One theme: the black · white · red blend (D-014, Locked). These values match the prototype's.

```css
:root {
  /* content (soft white) */
  --page:#E7E4E3; --bg:#F6F4F3; --surface:#FFFFFF; --surface-2:#ECE8E7; --line:#E2DDDC;
  --line-strong:#D3CDCC; /* toggle track when off */
  --ink:#1A1517; --mute:#6E6668;
  --accent:#CF2A40; --accent-soft:rgba(207,42,64,.09); --on-accent:#FFFFFF;
  /* chrome (black): header, bottom nav, hero, match sheet, wallet card, lock screen */
  --chrome:#141113; --chrome-ink:#F3EFEE; --chrome-mute:#A29A9C; --chrome-line:#2B2528;
  --chrome-accent:#E8475A; --chrome-accent-soft:rgba(232,71,90,.16);
  --chrome-glow:radial-gradient(circle at 50% 0%, rgba(207,42,64,.22) 0%, transparent 60%); /* landing hero */
  /* on-photo text (cards, call screen) */
  --on-photo:#FFFFFF; --photo-scrim:linear-gradient(to top, rgba(6,3,6,.94), rgba(6,3,6,.55) 52%, transparent);
  --shadow-1:0 4px 14px rgba(207,42,64,.24); --shadow-2:0 10px 26px rgba(20,12,15,.14);
  --shadow-knob:0 1px 3px rgba(40,10,20,.3); /* toggle knob */
  --scrim:rgba(10,8,9,.45);
}
```

Rules:
- Text on `--accent` is `--on-accent`. Text on photos is `--on-photo` over `--photo-scrim`.
- Anything inside a chrome area uses the `--chrome-*` set, except filled buttons, which stay
  `--accent` with `--on-accent` text, as in the prototype. White on `--chrome-accent` is about
  3.8:1, under the 4.5:1 button text needs; on `--accent` it is about 5.2:1.
- Contrast: body text ≥ 4.5:1, large text ≥ 3:1 (checked in T-9.11).
- `<meta name="theme-color">` = `--chrome`. A meta tag can't read a CSS variable, so this is the
  one colour literal outside `tokens.css`: `web/src/styles/theme-color.ts`, which must equal
  `--chrome` (`theme-color.test.ts` fails if it doesn't — P-28). The pre-commit hook exempts only
  these two files.

## 2. Type

System font stack (no web font download): `-apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif`.
Devanagari falls back to Noto Sans Devanagari on Android.

| Token | Size / line / weight | Use |
|---|---|---|
| `display` | 42 / 1.05 / 700, tracking −2 | landing hero |
| `title-1` | 24 / 1.2 / 700 | screen titles, onboarding questions |
| `title-2` | 18 / 1.3 / 700 | sheet titles |
| `body` | 14.5 / 1.6 / 400 | paragraphs, about |
| `ui` | 14 / 1.4 / 500–600 | buttons, list rows, chips, toggles |
| `input` | 16 / 1.4 / 400 | text typed into fields — below 16 px, iOS Safari zooms the page on focus |
| `small` | 12.5 / 1.5 / 400 | helper text |
| `micro` | 11 / 1.3 / 600 | badges, timestamps |

The prototype uses 31 font sizes, including 12, 12.5, 13 and 13.5, which differ by half a pixel.
The scale collapses them. Each element takes the token that the Use column gives its role, even
where that moves the prototype's size by a pixel or two: its 15 px buttons and 13 px chips are
`ui` (14), its 12 px field labels are `small` (12.5), and its 16 px empty-state titles are
`title-2` (18).

## 3. Space, shape, motion

Checked value by value against the prototype in T-1.19, and corrected where the two disagreed.

- Spacing scale (px): 2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 20 · 24 · 32 · 40 · 56. The half-steps
  2 · 6 · 10 · 14 are padding inside controls (buttons 14 and 10, fields 14 × 16, chips 8 × 14),
  as in the prototype. The prototype's rarer values (18, 22, 26, 28, 36, 48, 64) are rounded to the
  nearest step when their screens are built; P-29 adds a hook that rejects anything off the scale.
  Screen padding 20–24 mobile, 24 desktop.
- Radius: 12 inputs and buttons (both sizes) · 14 cards · 16 chat bubbles · 24 sheets · 26 swipe
  card · 999 pills. The prototype's few 10 px buttons (admin actions, the waitlist form) become 12
  when their screens use `Button`, and so does the landing header's pill-shaped "Get started"
  (T-2.1).
- Content max-width: 520 px for app screens (centred on desktop) · 720 legal pages · 760 admin ·
  900 landing.
- Motion: 150 ms for press/hover, 250–300 ms for sheets, spring for the deck. Respect
  `prefers-reduced-motion` (no rotation, fade instead).
- Tap targets ≥ 44 × 44 px. That is the tap area, which may reach past the visible control: chips
  and small buttons are drawn 38–42 px tall, as in the prototype, and stretch their tap area with
  an invisible `::before`.

## 4. Components (`src/components/ui/`)

| Component | Variants / states |
|---|---|
| Button | primary · ghost · danger · chrome; sm · md; loading · disabled |
| IconButton | round, sizes 40/46/56, optional price tag badge |
| Chip | default · active · removable |
| Field / TextArea | label, helper, error, counter |
| OtpInput | 6 boxes (D-066; the prototype shows 4), paste, auto-advance, backspace-back |
| Toggle | on · off · disabled |
| Sheet | bottom (mobile) / centred (desktop); title; scroll body; sticky footer |
| Toast | info (ink) · error (accent) · with action (Undo) |
| Avatar | photo · initial fallback · online dot · verified badge |
| Badge | count · status pill (Online, New, Knotted, intents) |
| Skeleton | line · card · avatar |
| Spinner | sizes; announced as a status, pulses instead of spinning under reduced motion |
| Icon | a Lucide icon at stroke 2; decorative (hidden) unless given a label |
| EmptyState / ErrorState | icon, title, body, action |
| Countdown | shared ticker; `4h 59m left` → `12m 30s left` → `Expired` |
| GiftGrid | 6 tiles, 3×2; free tiles show remaining count, paid show Velas |
| PriceTag | shows Velas for men, "free" for women (reads from `/prices`) |

T-1.19 built Button, Chip, Field, TextArea, Toggle, Sheet, Toast, Avatar, Skeleton, Spinner, Icon,
EmptyState and ErrorState; `/dev/ui` (under `next dev` only) shows each in every state. The rest
arrive with the first task that needs them: OtpInput with T-3.11, IconButton and PriceTag with
T-6.5's action row, Badge with T-6.7 and T-6.9, Countdown with T-7.10, GiftGrid with T-8.10.

Feature components live in `src/components/<feature>/` (discover, chat, wallet, profile, admin).

## 5. Screen inventory

Every screen must exist in the prototype first. ✦ = uses the black chrome.

**Marketing:** Landing ✦(header, hero, footer) · Terms · Privacy · Refunds · Contact · Public profile `/@username`.

**Onboarding (12):** Phone · OTP · DOB · Gender · Seeking + intents · Name + places · Username ·
About · Photos · Interests · PIN · Selfie.

**App:** Header ✦ · Bottom nav ✦ · Discover (deck, feeds, search, filters sheet) · Match sheet ✦ ·
Liked you grid · Profile (gallery, gifts row + gift sheet, album, ⋯ menu, report sheet, block sheet, share sheet) ·
Chats list (Threads / Knots) · Conversation (knot bar, expired panel) · Wallet (balance card ✦,
prices, history) · Store sheet · Checkout states (processing, failed) · You · Settings sheets
(edit profile, notifications, privacy) · Lock screen ✦ · Notifications list.

**Admin:** Dashboard · Reports queue · User detail · Moderation queue · Audit log (header ✦).

## 6. Copy voice

Short, warm, plain. Say what happens, not what the system is. "Cleared from your chats" not
"Deleted". "This thread disappears in 4h" not "TTL remaining". Prices always in Velas with the
number first: "Open thread · 5 Velas". Never shame or pressure ("Only 2 left!").

## 7. Brand images

The share preview and the icons, beside the root layout in `web/src/app/` (T-2.4). Made by Claude
on 2 October 2026 from `tokens.css` itself, rendered with headless Chrome in the system font stack
(§2) as it draws on macOS, so every colour is a token. They're committed as images, never as code
holding a hex value.

| File | What it shows |
|---|---|
| `opengraph-image.jpg` | 1200 × 630, every page's link preview: the landing hero. `--chrome` under `--chrome-glow`, "Threads last a day. Knots last." in `--chrome-ink` at display weight, the wordmark top left, `veloraapp.co.in` in `--chrome-mute` along the bottom. JPEG at quality 90, because the glow is a gradient and PNG compresses it poorly (152 KB against 43 KB). |
| `opengraph-image.alt.txt` | Its alt text: exactly the home page's title, the brand and the headline. |
| `apple-icon.png` | 180 × 180: a V in `--chrome-ink` on `--chrome`, with margins, since iOS crops it to a rounded square. |
| `favicon.ico` | The same V at 16, 32 and 48 px, filling more of its tile. White, not red: at 16 px red on black muddies, and white stays legible (the founder). Its PNGs are RGBA, which Next requires. |

**Regenerate them** when the name changes (the wordmark and the V; rule 17), when the landing
headline changes (it promises `thread_hours`, 03-SCHEMA §8; a test fails until the alt text
matches it), when the theme changes (D-014), or when the domain does.

**Known, and accepted for now** (the founder, 2 October 2026): the red glow barely shows at full
size, and WhatsApp's own re-encode will likely remove what's left, so the image reads as black
with type and the accent does no work there. The domain line isn't readable at phone preview
size. The type and the wordmark carry the image. Weigh both the next time it's made.
