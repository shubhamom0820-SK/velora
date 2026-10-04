# 09 · Market research — complaints, and which gaps Velora closes

Desk research, September 2026: analyses of 1–3 star reviews across the major apps, burnout surveys,
India-specific coverage, and reporting on algorithm behaviour. This is secondary research. It does
not replace the 15 first-hand interviews in P-0.10 — those are still the most valuable input we
will get, because everything below is about other markets or the whole of India, not our city.

---

## 1. What people actually complain about

### C1 · Paywalls — the single most repeated complaint
Not being able to see who liked you without a subscription is the most repeated complaint across
Tinder, Bumble and Badoo. Around 42% of Tinder's negative reviews mention pricing. Other recurring
items: daily like limits, message filters locked behind premium, rewind needing a subscription, and
boost mechanics that feel compulsory. Hinge is repeatedly named as the app that handles this best,
because core messaging stays free.

### C2 · Bots, scams and fake profiles
Bot accounts that immediately push the conversation to WhatsApp or Telegram are a standard pattern.
A 2025–26 escalation: AI-generated and composite photos that pass photo verification. Hinge draws
fewer romance-scam complaints, partly because its prompt-based profiles are harder to generate
convincingly and volume messaging isn't rewarded.

### C3 · Burnout
A Forbes Health / OnePoll survey of 1,000 users found 78% felt emotionally, mentally or physically
exhausted by dating apps at least sometimes (80% of women, 74% of men). A 2026 four-wave study of
active users found exhaustion and a sense of inefficacy climbing steadily over 12 weeks rather than
plateauing. Mobile analytics put dating-app deletion within a month of install at 69% in 2025, up
from 65%. Dating-app market revenue fell for the first time on record in 2025.

The structural point that keeps recurring in the analysis: apps monetise engagement, and a user who
finds a partner is churn. That tension is worth designing against deliberately.

### C4 · Ghosting and dead matches
In one survey of 3,000 people, 82% had been ghosted at least once on a dating app and 52% had met
catfishing. People report investing effort into a conversation and having the other person simply
disappear. Competitors have shipped responses: nudges after 48 hours of no reply, "your turn"
reminders, explicit end-conversation flows with a reason, and closure messages.

### C5 · India-specific
- Supply: reporting on Indian dating data cites splits as extreme as 93 men to 7 women, and notes
  plainly that this is not a problem better algorithms fix — it reflects how unevenly social freedom
  and safety are distributed. TrulyMadly reported women at roughly 20% of its users.
- No verification on the biggest app, so fake accounts take minutes to create.
- Unsolicited messages are the default; women describe the inbox as a swarm.
- Reports act slowly — accounts stay live for weeks after being reported.
- Social overlap: in smaller cities a profile is seen by colleagues, neighbours and family.

### C6 · Opaque visibility and dark patterns
Users widely believe apps hide them. Hinge has confirmed it sometimes stops others from finding,
seeing or receiving messages from bad actors. Neither Tinder nor Bumble confirms shadowbanning, but
community reports are consistent: near-zero matches, a frozen likes queue, boosts that do nothing.
Commentary also accuses apps of throttling reach to sell boosts. The trust damage is real whether
or not each specific accusation is.

### C7 · Basic quality
Swipe lag and accidental swipes, overloaded settings, unclear buttons, weak accessibility. In one
UX study, honest information was a significant driver of the experience, alongside nicely presented
profiles and intuitive navigation.

---

## 2. Gap map — where Velora stands

### Closed by design ✅

| Complaint | What we do | Where |
|---|---|---|
| C5 inbox flood | A man pays Velas to open any conversation — spam is not economically possible | D-002, D-004 |
| C4 dead matches | Threads expire in 24 h; only a mutual knot persists | D-003 |
| C2 fake profiles | Mandatory selfie liveness + face match for women; every photo moderated before it is visible | D-008, T-4.4, T-4.5 |
| C2 push to WhatsApp | Contact details masked server-side for the first 20 messages; solicitation patterns rejected | D-030, T-7.3 |
| C5 slow reports | 24 h SLA, 3 independent reports in 24 h auto-freezes, fraud scoring runs continuously | T-9.1, T-9.2 |
| C5 social overlap | Hide profile, exclude phonebook contacts, hide age, hide distance, rounded distances only | T-9.6 |
| C1 paid core messaging | Messaging inside a knot is free for both, forever | D-003 |
| C1 paywalled safety | Reporting, blocking, clearing — never paid | D-010 |
| Evidence destruction | Clearing is one-sided; the server keeps everything for moderation | D-006 |
| Public shaming | No ratings or reviews of people; only positive kudos the recipient controls | D-007 |
| C7 quality | Loading/empty/error states required per screen, 60 fps target on a ₹10k phone, a11y pass | T-9.10, T-9.11 |

### Partly closed 🟡

| Complaint | Gap that remains |
|---|---|
| C2 AI photos | Our face match compares a live selfie to the profile photos. A fully synthetic but internally consistent set still passes. Mitigation to consider: liveness challenge variety, device signals, and flagging accounts whose photos have no camera metadata after re-encode. |
| C3 burnout | Threads expiring reduces dead weight, but the swipe deck itself is the format people describe as exhausting. Only men have a daily cap. |
| C4 ghosting | Threads solve silence before a knot. **Inside a knot there is nothing** — it is permanent and can go quiet forever. |
| C6 visibility | Our fraud model has a `shadow` band that hides people without telling them. That is a shadowban. Defensible for fraud, indefensible if it ever widens. Keep it strictly fraud-only and write that down. |

### Not addressed ❌

| Gap | Note |
|---|---|
| C5 supply | 93:7 is an acquisition and trust problem, not a feature. Nothing in the product fixes it; the women-first launch plan does the work. |
| C1 price perception | See §3 — this is the sharpest risk we carry. |
| Date safety | No check-in, no share-my-plans, no emergency contact. Competitors have versions of this and it matters most in our market. |
| Profile depth | We have one "about" field. Hinge-style prompts are credited with fewer bots and better openers. |
| Closure | No end-conversation flow, no reply nudge. |

---

## 3. The three risks worth naming

**R1 · Our business model is the #1 complaint, sharpened.**
Paywalls are the most hated thing in the category, and we charge per conversation. At the entry
pack a man pays ₹250 to open one Thread (D-099); Tinder India sells roughly a month of unlimited
messaging for less. We are defensible on *why* (it is what keeps the inbox clean for women), but the
first-run experience has to prove value before it asks for money. Candidate fix: the first thread
free, once per account. Decide before beta, measure in T-10.4.

**R2 · Permanence has no exit.**
We invented a permanent tier and gave it no closure mechanic. If knots go silent, we have recreated
the dead-match problem in the place users were told is the good place.

**R3 · We inherit the trust problem even if we behave.**
Users assume they are being throttled to sell boosts. Since we sell visibility products in the
backlog (boost), we should publish how ranking works in plain words and never throttle reach as a
sales tactic. Cheap to do, and it is a genuine differentiator in a category with no credibility left.

---

## 4. What this research changed

Added to the backlog as B-16…B-19, and R1 flagged into T-10.4. See `05-PLAN.md`.
