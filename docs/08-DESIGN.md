# 08 · Design system

The prototype (`docs/prototype/velora-prototype-reference.html`) is the visual reference for every
screen. It predates the rename to Velora, so it uses "Knot" as the app's name — the screens and
flows are the reference, not the name. **Only the brand changed.** Where the prototype names the
app, read Velora (`APP_NAME`). Thread and Knot stay as the product's nouns ("Tie the knot",
"Knots last", the Knots tab) and are never replaced (CLAUDE.md rule 17). Its "credits" are
Velas, the unit of paid balance (D-049). This file turns the prototype into rules so the real
app stays consistent.

**Where this file departs from the prototype on purpose, naming the decision behind it, this file
is the live spec and the prototype is historical for that screen.** The prototype is never edited
to match (P-22). The OTP screen is one such screen: its four boxes and "Any four digits work
here" predate D-066's six-digit codes, and `OtpInput` below is the spec.

**Read this before trusting the prototype for any screen.** Planning T-3.10 to T-3.13, the first
real app screens, found it wrong 13 times on the onboarding and lock screens alone, each overridden
by a decision or a rule. With Sprint 5's four (§5), it is the evidence for P-57's open question:
the app has no visual design, only a prototype that shows which screens exist.
1. **Code:** four boxes and "Any four digits work here". Six digits (D-066, `OtpInput`).
2. **Phone:** "Continue with Google / Apple", which no plan or decision includes. Dropped.
3. **Birthday:** works out the age in the browser, blocks under 18 before the server sees the date,
   and says "This device can't be registered". The server decides, and it bars the number (D-079,
   D-072).
4. **Gender:** "buy credits". Velas (D-049).
5. **Looking for:** one intent, labelled in code. One to three (D-041), labelled from `en.ts` by id
   (P-26).
6. **Username:** "taken" checked against a local list, only a 4-character minimum, and
   `knot.app/@`. The server's check and suggestion, `[a-z0-9._]{4,20}`, the host from `site.ts`.
7. **Interests:** free strings. Catalogue ids (P-26).
8. **Lock screen:** compares the PIN in the browser, has no way out of a forgotten PIN, and says
   "Knot is locked". `/auth/pin/verify` with attempts left, a sign-out (D-069), `APP_NAME` (rule 17).
9. **Progress kept in `localStorage`.** The server's `onboarding_step` is the only state.
10. **"Bengaluru" as the city placeholder.** The launch city is Phagwara (D-013).
11. **Its sizes:** 17 px fields, 26 px code digits, 15.5 px labels. The scale in §2 and §3.
12. **A back arrow on every screen,** including onto answers that can't change (D-080).
13. **No loading, empty or error state anywhere.** Rule 14 needs all three.
14. **"Verified" everywhere a selfie is meant:** "Face matched — verified", "Verified only",
    "verified profiles get noticeably more replies", and a shield beside a name. A selfie is
    compared with the profile's photos and nothing more is claimed (D-262, T-4.5): the badge says
    "Selfie matches photos" with a face (`ScanFace`), and `web/src/i18n/claims.test.ts` refuses the
    prototype's words.
    **Amended 7 October 2026 (D-393):** the founder chose a tick on 7 October 2026, knowing a tick
    reads as "verified" where the words may not say it (D-262). The words still never say it: the
    badge's label and aria-label stay "Selfie matched", and `claims.test.ts` holds them. The tick
    is `--accent`; the shield stays rejected. The item above stands as written, struck where it
    says a face (`ScanFace`). Built by T-4.12.
15. **The selfie's pose and its promise:** "Turn your head slightly left" and "The pose is randomly
    chosen each time, so a saved photo won't pass", and a selfie sent the moment it's taken. No
    pose is asked (T-4.5, D-263), nothing claims a saved photo can't pass (D-260), and the picture
    is checked before it's sent, since each sent selfie is one of five a day (T-4.7). Its sub,
    "This is what keeps fake accounts off the app", promises more than a comparison: P-110.

What it is still trusted for there: the screen order (§5, D-068), the `Step` frame (back arrow,
a segment of progress per screen, its 12 and now the location question's, title, body, footer,
520 px), each screen's composition, the PIN pad's layout
and the lock screen's (black, ✦).

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
| OtpInput | 6 boxes (D-066; the prototype's 4 are historical), paste, auto-advance, backspace-back |
| PinPad | 4 dots, 3 × 4 keys, delete; the lock screen (T-3.10) and the PIN step (T-3.12) |
| Toggle | on · off · disabled |
| Sheet | bottom (mobile) / centred (desktop); title; scroll body; sticky footer |
| Toast | info (ink) · error (accent) · with action (Undo) |
| Avatar | photo · initial fallback · online dot · selfie-matched badge (a face, never a shield or "Verified": D-262; from T-4.12 a tick in `--accent`, the founder's choice, the words unchanged: D-393) |
| Badge | count · status pill (Online, New, Knotted, intents) |
| Skeleton | line · card · avatar |
| Spinner | sizes; announced as a status, pulses instead of spinning under reduced motion |
| Icon | a Lucide icon at stroke 2; decorative (hidden) unless given a label |
| EmptyState / ErrorState | icon, title, body, action |
| Countdown | shared ticker; `4h 59m left` → `12m 30s left` → `Expired` |
| GiftGrid | D-231's four gifts, each with its price in Velas, and the free sends left this week (was six tiles, 3×2) |
| PriceTag | shows Velas for men, "free" for women (reads from `/prices`) |

T-1.19 built Button, Chip, Field, TextArea, Toggle, Sheet, Toast, Avatar, Skeleton, Spinner, Icon,
EmptyState and ErrorState; `/dev/ui` (under `next dev` only) shows each in every state. The rest
arrive with the first task that needs them: PinPad with T-3.10, OtpInput with T-3.11, IconButton and PriceTag with
T-6.5's action row, Badge with T-6.7 and T-6.9, Countdown with T-7.10, GiftGrid with T-8.10.

Feature components live in `src/components/<feature>/` (discover, chat, wallet, profile, admin).

## 5. Screen inventory

Every screen must exist in the prototype first. ✦ = uses the black chrome.

**Marketing:** Landing ✦(header, hero, footer) · Terms · Privacy · Refunds · Contact · Public profile `/@username`.

**Onboarding (13):** Phone · OTP · DOB · Gender · Seeking + intents · Name + places · Location ·
Username · About · Photos · Interests · PIN · Selfie.

**Location has no prototype screen** (T-4.10, D-220), the one exception to "every screen in the
prototype first", made because the plan and D-034 need the question. It is the onboarding frame's
existing parts and nothing new: a pin icon, the reason, "Share my location", and an area picker of
radio rows like Gender's. That is a screen assembled, not designed: one more case of P-57's gap
(the app's screens have no visual design), not a new one.

**App:** Header ✦ · Bottom nav ✦ · Discover (deck, feeds, search, filters sheet) · Match sheet ✦ ·
Liked you grid · Profile (gallery, gifts row + gift sheet, album, ⋯ menu, report sheet, block sheet, share sheet) ·
Chats list (Threads / Knots) · Conversation (knot bar, expired panel) · Wallet (balance card ✦,
prices, history) · Store sheet · Checkout states (processing, failed) · You · Settings sheets
(edit profile, notifications, privacy) · Lock screen ✦ · Notifications list.

**The app's screens have no visual design yet, and the shell is provisional** (3 October 2026,
P-57). The prototype shows each screen exists, but it isn't a design: it was wrong four times in
Sprint 5's plan alone (the refund button, gift's direction, the price list, and "credits" for
Velas). T-5.6 builds the header and bottom nav from it provisionally. They frame every screen in
Sprints 6 and 7, so they're a one-way door. The first task that needs an app screen designed
(T-6.5) stops and asks, rather than inventing it from the prototype.

**The store and the gifts depart from the prototype too** (D-099, D-231; 4 October 2026). The
packs are ₹1,500 → 30, ₹4,500 → 100, ₹6,000 → 250 and ₹10,000 → 450, not its 30, 100, 150 and
250. Its "Most popular" tag stays on the ₹4,500 pack, chosen knowingly though that pack is the
dominated one; whether the words can show before anyone has bought is the founder's to settle
(on T-8.7's Needs line, moved from T-5.2's on 4 October 2026). The gifts are four at 5, 10, 15 and 20 Velas, with fifteen free
sends a week, not its five at 20 to 500. Its price list's re-open (3), direct message (5) and
album request (5) are D-098's and D-231's 2, 8 and 1. The prototype itself isn't edited (P-22).

**The shell as T-5.6 built it** (provisional, 4 October 2026). The header ✦ holds the wordmark,
`APP_NAME` in `title-1`, never the prototype's "Knot". The nav ✦ is Discover, Chats, Wallet and
You, at `/discover`, `/chats`, `/wallet` and `/you`, with no Vibe (D-010). It is one `<nav>`:
along the bottom on mobile, in the header's row from 768 px, as in the prototype. The current
place is `--chrome-accent` with its icon filled: colour alone would fail WCAG 1.4.1, since
`--chrome-mute` against `--chrome-accent` is about 1.4:1. Its sizes are the `--shell-*` tokens in
`tokens.css`, and its shape is `src/components/shell/AppShell.tsx` alone (`look.test.ts` holds
both), so T-6.5's design pass changes values, not structure. Where it departs from the prototype:
labels are `micro` (its 9.5 px), icons 20 px (its 19), and items stack icon over label at every
width (its desktop items sit side by side); the wordmark is the landing's plain one, without the
red letter; the page scrolls, where the prototype scrolls inside a fixed frame. The globe, the
bell and the Chats badge wait for the tasks that build them (Hindi comes after beta); the balance
pill is T-5.5's, below.

**The wallet and the pill as T-5.5 built them** (provisional, 5 October 2026). At the header's
end, a man's balance pill: `--accent` with `--on-accent` text, a filled bolt (`Zap`) and his
balance, read from `GET /wallet` alone, never from `Me` (P-221). It is a button that opens the
store sheet, and so is "Buy Velas" under the wallet's card. Until T-8.7 fills it, the sheet says
plainly that buying hasn't started, with no promise of when. **Why a button now:** the screen's
shape is settled here, so T-8.7 fills the sheet without reopening the header, the card or the
pill's tap area, and a man out of Velas who taps his balance isn't left stuck. At the direction
of the advisor directing T-5.5 (Claude, in a separate chat), relayed by the founder, 5 October
2026. A woman's header says "Free access" in `--chrome-ink` on `--chrome-accent-soft` with a
`--chrome-accent` border, not the prototype's red text: red on its own soft red measures 4.15:1,
under the 4.5:1 its `micro` text needs (13.93:1 as built). The pill's sizes are the
`--shell-pill-*` tokens, and its tap area reaches 8 px past it, to 44 px (§3).

Where the wallet screen departs from the prototype:
- No "Request a refund on unspent credits" and no "Unspent credits refundable within 7 days": the
  cash-out D-050 removed (D-076, D-230). A quiet "Refund policy" link to `/refunds` instead.
- The price list is `/prices`' actions (D-098, D-231), nine today, in the web's own order, then
  "Tie the knot · Free" and "Messaging in a knot · Free". Not Wink, Boost, calls or "Gifts
  20–500": D-231's gifts are 5, 10, 15 and 20 Velas, priced by `GET /gifts`, not here. A price
  reads "5 Velas" or "1 Vela".
- "Credits" are Velas (D-049). The women's screen drops "calls" (after beta); its "and never
  will" says no more than what is published already ("Free for women, always" on the landing
  page; "Women never pay for anything" in the Terms).
- The history lists every entry, a page at a time as it scrolls, where the prototype showed the
  last 12. Each reason is in words from `en.ts`, by the API's enum (P-26), never free text.

**Admin:** Dashboard · Reports queue · User detail · Moderation queue · Audit log (header ✦).

## 6. Copy voice

Short, warm, plain. Say what happens, not what the system is. "Cleared from your chats" not
"Deleted". "This thread disappears in 4h" not "TTL remaining". Prices always in Velas with the
number first: "Open thread · 5 Velas". Never shame or pressure ("Only 2 left!").
**Flagged 4 October 2026, don't copy it:** "This thread disappears in 4h" is wrong twice. Nothing
disappears, since an expired Thread stays readable, and a Thread is an hour (D-097). The 1-hour
task D-097 names rewrites it.

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
