# 08 · Design system

The prototype (`docs/prototype/velora-prototype-reference.html`) is the visual reference for every
screen. It predates the rename to Velora, so it uses "Knot" as the app's name — the screens and
flows are the reference, not the name. **Only the brand changed.** Where the prototype names the
app, read Velora (`APP_NAME`). Thread and Knot stay as the product's nouns ("Tie the knot",
"Knots last", the Knots tab) and are never replaced (CLAUDE.md rule 17). Its "credits" are
Velas, the unit of paid balance (D-049). This file turns the prototype into rules so the real
app stays consistent. **From 7 October 2026 the app's screens have a design of their own, §8
(P-57): for them the prototype says only which screens exist, and §8 is the visual reference.**

**Where this file departs from the prototype on purpose, naming the decision behind it, this file
is the live spec and the prototype is historical for that screen.** The prototype is never edited
to match (P-22). The OTP screen is one such screen: its four boxes and "Any four digits work
here" predate D-066's six-digit codes, and `OtpInput` below is the spec.

**Read this before trusting the prototype for any screen.** Planning T-3.10 to T-3.13, the first
real app screens, found it wrong 13 times on the onboarding and lock screens alone, each overridden
by a decision or a rule. With Sprint 5's four (§5), it is the evidence for P-57's question, open
until 7 October 2026 (§8): the app has no visual design, only a prototype that shows which screens
exist.
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
(the app's screens have no visual design), not a new one. **§8 closed that gap for the app's
screens on 7 October 2026; this one is onboarding's, not among §8's fifteen, and stands as
assembled.**

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
**Amended 7 October 2026 (P-57 answered):** the design exists, in §8 below. The founder approved
fifteen screens on Claude's design canvas on 7 October 2026 ("all the frontend are correct"). The
canvas is the founder's; §8 is the rules made from it, as §1 to §5 were made from the prototype.
From here the prototype says only which screens exist, and the visual reference for the app's
screens is §8. T-6.5 builds from it and no longer stops to ask. The shell stays as T-5.6 built it:
§8 changes its values, never its structure.

**The store and the gifts depart from the prototype too** (D-099, D-231; 4 October 2026). The
packs are ₹1,500 → 30, ₹4,500 → 100, ₹6,000 → 250 and ₹10,000 → 450, not its 30, 100, 150 and
250. Its "Most popular" tag stays on the ₹4,500 pack, chosen knowingly though that pack is the
dominated one; whether the words can show before anyone has bought is the founder's to settle
(on T-8.7's Needs line, moved from T-5.2's on 4 October 2026). The gifts are four at 5, 10, 15 and 20 Velas, with fifteen free
sends a week, not its five at 20 to 500. Its price list's re-open (3), direct message (5) and
album request (5) are D-098's and D-231's 2, 8 and 1. Its "liked you" reveal (`likedMe`, 20) is 1
Vela from 8 October 2026 (the founder; D-004's note). The prototype itself isn't edited (P-22).

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

## 8. The app's visual design (7 October 2026)

Designed by Claude on its design canvas and approved by the founder on 7 October 2026, fifteen
screens, in his words: "all the frontend are correct". The canvas is the founder's and isn't in the
repo; this section is the rules made from it, by token name (§1) and type token (§2), never a
colour value, as §1 to §5 were made from the prototype. For these screens it is the visual
reference, and the prototype says only that they exist. Two of the canvas's strings were changed
on 8 October 2026 to match D-393, noted where they appear; the canvas now says the same.

**What it covers, and what it doesn't.** Discover (the card, the action row, the feed row, the
match sheet, the empty state), the profile, Liked you, Filters, Search, the chats list, a Thread
(his, hers, and his expired), Knot tied, a Knot, and the shell. Drawn for a man wherever a price or
an hour shows; her Thread is drawn on its own (D-097), her chats list isn't. The wallet and the
balance pill stay as T-5.5 built them (§5), the lock screen and onboarding as T-3.10 to T-3.13 and
T-4.10 built them. You, Settings, Notifications, the store sheet, Checkout and admin have no
design yet: the prototype shows they exist, no more, and the task that builds one asks before
designing it, as T-6.5 was to (P-57).

**One concept, the thread.** A thin red line, `--accent`, 2 to 3 px, is the one thread through the
whole app: on the card, between the photo and the text; on the match sheet, joining the two
people, with a small ring at its middle; in a Thread, a bar under the header whose width is the
part of the hour that is left; at the moment of the knot, the ring fills; in a Knot, the bar is
full and never shrinks. Red is a thread, never a flood: no red background, no red scrim. Text
never sits on a photo: no `--photo-scrim` on the card (§1 lists the token for cards; from here no
card uses it).

**Words.** §6's voice. A price in words is "· 5 Velas", the number first; for a woman, "· Free". A
price badge on a button is the number alone: Super's "5", "Extend 24h · 10". Nowhere "verified"
(D-262): the badge says "Selfie matched", and `web/src/i18n/claims.test.ts` holds every string.
**Every hour on these screens is D-097's** ("41m left", "Threads last an hour", "The hour ran
out"), decided and not built: `app_config.thread_hours` is 24 until the 1-hour task (P-150) lands.
A screen built before then says what runs, as the landing does (copy follows the setting, P-14),
and takes these words when the task lands.

**The card (T-6.5).** `--corner-swipe`. The photo on top, 336 of the card's 560 px, on a
`--surface-2` placeholder while it loads; the thread; the text below. Name and age in `title-1`.
Beside the name, the red tick (D-393) where its rule holds: a 20 px `--accent` circle with an
`--on-accent` check, aria-label "Selfie matched" (D-393's words, held by `claims.test.ts`; the
canvas said "Selfie matched her photos" until 8 October 2026, which overclaims where a shown photo
didn't match, D-393's rule 3). "Phagwara · 3 km" in `small` `--mute`. "Online now" is a `micro`
pill, `--accent` on `--accent-soft`. Intent chips in `ui` on `--surface-2`. The bio in `body`, two
lines. A "New" pill at the photo's top left, `--chrome-ink` on `--ink`. **Without a photo**
(D-392): her initial inside a `--line-strong` silhouette, a round head and shoulders, and "Prefers
not to show photos yet" in `small` `--mute`. No badge there (D-393: no shown face, no badge).

**The action row and the feed row (T-6.5).** Three `IconButton`s (§4): Pass, 46 px, `--ink`;
Super, 46 px, `--accent`, with its price badge, "5", for a man; Like, 56 px, filled `--accent` with
`--shadow-1`. Under them, for a man only, the swipes left today ("12 swipes left today") in `small`
`--mute` (the cap is `swipe_daily_limit_men`, T-6.4). The feed row: For you, New and Online as
pills, the active one filled `--ink` with `--chrome-ink` text; Search and Filters as 40 px icon
buttons at the row's end, Filters carrying the count of active filters as an `--accent` badge.

**The match sheet ✦ (T-6.5).** `--chrome` under `--chrome-glow`. Two initials in 96 px
`--chrome-line` circles; the one whose like was already there (the match forms on the second like,
T-6.4) has a `--chrome-accent` border. The thread between them, with its 14 px ring. "You and Priya
liked each other" in `title-1`. "Open thread · 5 Velas" for a man, "Open thread · Free" for a
woman, filled `--accent` (§1: filled buttons stay `--accent` inside chrome). "Keep swiping" as a
ghost button with a `--chrome-line` border. The footer in `micro` `--chrome-mute`: "Threads last
an hour. Knots last."

**The profile (T-6.8).** The gallery on top, 390 px, with dots; the thread; name, tick and "Online
now"; a pin icon with "Phagwara · 3 km · from Jalandhar" (city, distance, hometown); a small tick
with "Her selfie matched a photo you see here" in `small` `--mute` (true under D-393 wherever the
tick shows; the canvas said "the photos you see here" until 8 October 2026). LOOKING FOR, ABOUT and
INTERESTS as `micro` uppercase labels, their chips 32 px. The kudos row and the album row ("Ask to
view") as `--surface` cards, `--corner-card`. A sticky bar at the bottom: "Open thread · 5 Velas"
and Like.

**Liked you (T-6.7).** A two-column grid of 204 px tiles, `--corner-card`. Revealed: the photo, the
thread, name and distance, and a star badge at the top left for a Super Like. Unrevealed: the
server's blur (T-6.7, never CSS), and under it a "Reveal · 1 Vela" pill, `--surface` with
`--shadow-2` and a lock icon. The number is read from `/prices`, never written into the code (it
was "Reveal · 20 Velas" until 8 October 2026, the founder, P-370). A woman's tiles are all
revealed (`/likes` is free for her). The count in the header is a `--chrome-accent` badge.

**Filters (T-6.9).** A bottom sheet, `--corner-sheet`, over `--scrim`. Intent chips 38 px; pressed,
they fill `--accent-soft` with an `--accent` border and `--accent` text. Two toggles, "Selfie
matched" and "Online now", each with a one-line explanation (the first's words are D-262's and its
meaning D-393's, as T-6.9 says). "Clear" and "Show people" at the bottom. The count of active
filters is a pill in the sheet's header.

**Search (T-6.6).** A field inline in the chrome header, filled `--chrome-line`, `input` (16 px). In
@ mode, a "@ username" badge in `--ink`; an exact username match carries an "Exact" badge on
`--accent-soft`. Result rows 64 px, their avatars 44 px.

**Empty states.** A dashed `--line-strong` outline, `--corner-swipe`; the icon sitting on the
thread; a `title-2`; `body` in `--mute`; one `--accent` action (`EmptyState`, §4).

**The chats list (T-7.10).** Tabs, Threads and Knots, underlined, the active one `--accent`, each
with a count badge. Rows: a 48 px avatar with an `--accent` online dot, the name, the preview, and
a countdown pill (`Countdown`, §4): `--accent-soft` "41m left"; `--surface-2` "22h left" for an
Extended Thread; filled `--accent` "8m left" under ten minutes; `--surface-2` with `--mute` text
"Ran out" (§4's example ends "Expired" and starts at "4h 59m", the 24-hour Thread's; this pill
reads "Ran out"). The footer in `small` `--mute`: "A Thread lasts an hour from her last message.
Knots last."

**His Thread (T-7.11).** The header: her name, then "41m left · her reply restarts the hour", the
time in `--chrome-accent` and the rest in `--chrome-mute`, and an "Extend 24h · 10" pill with a
`--chrome-accent` border. Under the header, the thread's bar: 3 px `--chrome-accent` over
`--chrome-line`, its width the part of the hour left. The knot bar, `--surface`: a half-red thread
glyph, "Tie the knot and this never runs out. Free, if she ties it too.", and "Tie the knot" as an
`--accent` outline button. Bubbles (`--corner-bubble`, the small corner toward the sender): hers
`--surface` with a `--line` border, radius 16 / 16 / 16 / 4; his `--ink` with `--chrome-ink` text,
16 / 16 / 4 / 16. A voice note: a 32 px `--accent` play button, waveform bars (`--ink` played,
`--line-strong` the rest), the duration in `micro`. Under his last message, "Seen 7:49 PM" with a
double tick, `micro` `--mute`. Typing: a bubble of three dots and "Priya is typing". The composer:
the input at 16 px (`input`) with `--corner-input`, a 44 px send button, filled `--accent` with
`--shadow-1`, and a 44 px outlined mic. **The mic is drawn in his composer; T-7.11 gives it to
women** (voice notes are hers, and he pays to hear them): the plan decides, not the drawing.

**Her Thread (T-7.11; D-097).** No countdown, no price, no locked state, anywhere. The header: his
name, "Online now", and the "Free access" pill (T-5.5's, §5). The bar is `--chrome-line` alone:
there is nothing to count down. The knot bar is the same, with her words: "Tie the knot and this
stays, always. He has to tie it too." Under her last message, "Not seen yet" with a single tick.
The composer is the same.

**His expired Thread (T-7.6, T-7.11).** The header: "The hour ran out · 7:52 PM" in
`--chrome-mute`. The bar `--chrome-line`. The whole history stays readable (D-097). A divider where
the hour ran out: "The hour ran out". Her new message has an `--accent` border and "New · 9:14 PM"
in `--accent`. A sheet at the bottom, `--corner-sheet` with `--shadow-2`: `title-2` "She wrote
back. The hour had run out."; `small` `--mute` "You can read everything. To reply, open the Thread
again."; "Re-open · 2 Velas", filled `--accent`; "Re-open and keep it for 24h · 10 Velas",
outlined (D-253: ten in all, never twelve); and in `micro`, "Re-open restarts the hour from her
message. Extend holds it for a day, as many times as you like." A woman never sees this screen.

**Knot tied ✦ (T-7.7).** The match sheet again, but both initials have the `--chrome-accent`
border, and the ring is filled: 28 px `--chrome-accent` with `--shadow-1`, a `--chrome` ring inside
it. "You and Priya tied the knot" in `title-1`. "No hour. No Velas. This one stays, because you
both chose it." "Keep talking", filled `--accent`. The footer as the match sheet's.

**The Knot (T-7.11).** The header's avatar has a `--chrome-accent` border; the name with a 14 px
knot glyph; "Knotted 3 days ago · Online now". The bar is full `--chrome-accent`, and never
shrinks. A divider, "YOU TIED THE KNOT · 4 October", between red lines. No knot bar. His composer
gains the gift button (T-8.10's sheet; gifts go to a woman).

**The shell (T-5.6).** As built: the `--shell-*` tokens unchanged, nav items icon over label, the
current place a `--chrome-accent` filled icon (§5). No structural change: the design confirms the
shell as it stands, and T-6.5's design pass changes values only, as §5 says.
