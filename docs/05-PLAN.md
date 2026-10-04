# 05 · Build plan

The only list of what gets built, in the order it gets built. Nothing is built that isn't here.

## How to use this with Claude Code

1. Pick the **first unticked task** whose "Needs" are all ticked.
2. In Claude Code run: `/task T-3.2` (see `.claude/commands/task.md`).
3. Claude restates the task and lists files. **Read it. Approve or correct.** Then it builds.
4. Run `/review` — it checks the work against the task and `07-CHECKLISTS.md`.
5. Run `/done T-3.2` — ticks the box, commits with the task ID.
6. One task per session is ideal. Start a fresh session for the next one.

If Claude discovers work that isn't planned, it goes under **Proposed tasks** at the bottom —
never done silently.

**Task format:** Needs → Steps → Done when → Commit.
**Legend:** `[ ]` todo · `[x]` done · `[~]` in progress · `[-]` dropped (say why).

---

# Phase 0 — Founder tasks (no code, run in parallel)

- [ ] **P-0.1** Trademark search for the name on the IP India public search. Record result in D-015.
  **Partly done:** the founder searched the public web on 1 October 2026 (findings in D-015).
  **Classes 9, 42 and 45 searched on 3 October 2026, but not on the registry** (founder; findings
  in D-015). IP India's public search returned an empty page, so the search ran on mirror
  databases: no mark in those classes, and the only registered VELORA in India is in class 21,
  kitchen utensils. A mirror is only as current as its last copy of the registry, so that can't
  tick this box. US marks turned up too; they matter only at a US store listing or in US
  marketing (D-015, B-15).
  **Still owed:** the same search, Nice classes 45, 9 and 42 as Claude mapped them, on IP India's
  own public search once it answers. D-015 was closed and the domain bought (P-0.3) before it, so
  a conflict found there means a new name and a new domain.
- [ ] **P-0.2** Register company (OPC recommended) → PAN, GST, current account. Then fill the missing facts in `web/src/lib/legal.ts` (D-053), and change Terms' "Who we are" to name the company directly instead of pointing to the contact page: Terms should name the entity it binds.
  **The four legal facts are in** (the founder, 2 October 2026; D-058): a sole proprietorship,
  not the OPC recommended above, named "Shubham Kumar, sole proprietor", word for word as the
  PAN and bank account have it; the registered office in Hajipur; the courts at Hajipur; Shubham
  Kumar as Grievance Officer. They're in `legal.ts`, and Terms now names the proprietor directly.
  **Still open, for the founder to confirm separately:** PAN, GST and the current account. T-2.6
  stays blocked on P-0.3's two mailboxes: four of the six legal facts.
  **3 October 2026:** the mailboxes are in (P-0.3), so all six legal facts are known and a
  production build lets the legal pages through (D-053).
- [x] **P-0.3** Buy the domain (D-015 says why this one). Move its nameservers to Cloudflare. Then set up the support and Grievance Officer mailboxes: their addresses are the `supportEmail` and `grievanceOfficerEmail` facts in `web/src/lib/legal.ts`, and production can't build without them (D-053). Put each address there once it has received and sent a test message, and in the same change add Zoho to `/privacy` (`web/src/i18n/en.ts`) in both places: the list of who handles user data, since from then on it holds every support and grievance email, and "Where your data is", which lists what stays in India (D-048): that mail does, in Zoho's India data centre.
  **The domain is done:** `veloraapp.co.in`, registered 2 October 2026 with Hostinger, expiring
  2 October 2027. Claude read both dates and the registrar from the public WHOIS the same day.
  WHOIS privacy and auto-renewal are on and the registrant email is verified, per the founder.
  Web at the apex, API at `api.veloraapp.co.in` (T-2.6).
  **DNS goes to Cloudflare** (founder, 2 October 2026): T-4.1's R2 custom domain needs the zone
  there, and P-33's staging records go there too.
  **The mailboxes are on Zoho Mail** (founder, 2 October 2026): `support@veloraapp.co.in` and
  `grievance@veloraapp.co.in`. Planned on the free tier (five users, one domain), set up as two
  aliases on one paid user. Zoho sends as well as receives, so grievance acknowledgements go out
  from the grievance address. **Sign up on Zoho's India data centre (`zoho.in`):** it is chosen
  once and hard to move. The MX records point at Zoho; add its SPF and DKIM records and a DMARC
  record too, or those replies land in spam.
  **Rejected: Cloudflare Email Routing.** It's free but only forwards, so replies would go out from
  a personal Gmail address, which undercuts the Grievance Officer section (D-052).
  **Order:** nameservers first, then the mailboxes, then P-33.
  **Nameservers moved, 2 October 2026:** the `.in` registry delegated the domain to Cloudflare
  (`aaron` and `lilyana.ns.cloudflare.com`) by 14:58 IST, read from the registry by Claude. Both
  answered for the zone, with Hostinger's parking A and MX records gone; there was no DNSSEC to
  switch off. P-33 started from there.
  **The mailboxes, 3 October 2026:** both addresses are aliases on one paid Zoho Mail user in
  Zoho's India data centre, so support and grievance mail stays in India (D-048). They're in
  `legal.ts`, and `/privacy` names Zoho in both places this task asks for.
  **Proved by the mail, not a status page** (founder): a message from an outside account reached
  `grievance@` and a reply came back. Gmail's own `Authentication-Results` line on the reply read
  `dkim=pass` with `header.s=zmail` and `spf=pass` with `smtp.mailfrom=grievance@veloraapp.co.in`:
  Google checking the signature against the key in our DNS, not a checker reporting that a
  record exists.
  **That test's `dmarc=pass` wasn't Gmail's verdict.** Claude first put it down to Hostinger's
  stale zone (below); the founder found it was worse, and wrote it down in these words: "Gmail's
  own Authentication-Results line carried only dkim=pass and spf=pass. The dmarc=pass sat inside
  arc=pass(...), which is Gmail relaying what Zoho's own ARC seal asserted. So I quoted a
  vendor's self-report as the receiving server's verdict." It's a sharper version of the same
  trap: not only "which DNS answered" but "whose assertion am I reading". Our zone had no DMARC
  record then: Claude read its absence at both of our nameservers.
  **DMARC is `v=DMARC1; p=quarantine`** (founder, 3 October 2026), for two reasons, the second
  deciding. Only Zoho sends as this domain, so mail claiming to come from it that Zoho didn't
  send goes to spam, including mail posing as `support@` or `grievance@`. And the value tells the
  zones apart: a verdict showing `p=QUARANTINE` can only have come from ours, since Hostinger's
  stale record says `p=none`. Claude read it the same day from both of our nameservers, as
  authoritative answers, along with the MX records (`mx`, `mx2` and `mx3.zoho.in`), SPF
  (`v=spf1 include:zoho.in ~all`), the `zmail` DKIM key and Zoho's verification record.
  **Then Gmail's own verdict, for each address** (founder, 3 October 2026): each alias received a
  message from an outside account and replied, `grievance@` at 02:52 IST and `support@` at 03:11.
  On both replies Gmail's own line read `dkim=pass` with `header.i=@veloraapp.co.in` and
  `header.s=zmail`; `spf=pass` with that alias as `smtp.mailfrom`, so each line belongs to its own
  address, not both to one mailbox; and, as its own clause outside `arc=pass(...)`,
  `dmarc=pass (p=QUARANTINE sp=QUARANTINE dis=NONE) header.from=veloraapp.co.in`. Both went out
  from `103.117.158.11`, Zoho's India sender `sender-op-o11.zoho.in`: Claude read the name both
  ways, reverse and forward.
  **Zoho's own "verify all records" page showed MX and DKIM failing** while both were live, as
  the founder confirmed against a public resolver: Zoho's resolver had cached their earlier
  absence. A vendor's status indicator is a claim; the behaviour is the proof.
  **Not added, on purpose: two ZeptoMail records Zoho offered.** ZeptoMail, Zoho's service for
  sending transactional mail, is off. Don't "fix" the gap: the records come with whatever task
  turns ZeptoMail on.
  **Hostinger's old zone: emptied, not removed** (founder, 3 October 2026). After the move, its
  nameservers kept serving their own MX records (`mx1` and `mx2.hostinger.com`) and a `p=none`
  DMARC record. A resolver still holding the old delegation would deliver mail for `grievance@`,
  the address the legal pages publish, to Hostinger, where no mailbox exists. Hostinger's panel
  deletes only record by record, with no way to delete the zone, so the founder deleted all 11,
  both MX records, the SPF and the DMARC among them. **That's the state we ended up in, not the
  one we aimed for:** Hostinger's nameservers still answer for the domain, with authority, for an
  empty zone. A removed zone would answer `REFUSED`, as they do for a domain they don't host, so
  a resolver still holding the old delegation would fail for a while and retry until it found
  ours. An empty zone tells it there's nowhere to deliver, and a sender can bounce. That window
  closes as those resolvers' copies of the old delegation expire: 24 hours after the move, for
  most.
  **The deletion took time to reach every answer** (read by Claude): at 03:30 IST, Hostinger's
  IPv4 addresses already served the empty zone, at a new serial (`2026100205`), while its IPv6
  addresses still served the deleted MX and `p=none`, at full TTLs that didn't count down: a copy
  that hadn't caught up. This network's own resolver (Jio's) still returned Hostinger's MX in one
  of three tries at 03:32. For the next hour the IPv6 answers flipped between old and new. From
  04:34 all four addresses served the empty zone, three checks in a row five minutes apart, and a
  burst of 80 queries at 04:45 found no old answer, with serial `2026100205` everywhere. By then
  Jio's resolver returned only Zoho's MX.
  **D-053's gate, both ways:** on `main`, a production build (`APP_ENV=production`) refused and
  named the Grievance Officer's email and the support email (P-0.3); with the two addresses in,
  it builds, and the built `/contact` shows both. T-2.6 no longer waits on the mailboxes.
- [ ] **P-0.4** DLT (needed only to move off Firebase later — start it anyway, it is slow): entity → header → OTP template `{#var#} is your Velora verification code. Valid for 5 minutes. Do not share it.`
- [ ] **P-0.5** MSG91 account; link DLT IDs; send one test SMS to yourself.
  **When this is done (D-066):** revisit the OTP send limits, the global daily cap and the ₹0.20
  price behind D-066's figures before Path B is switched on, and build P-46, the MSG91 client.
- [ ] **P-0.12** Firebase: project, Phone provider on, App Check + reCAPTCHA Enterprise enforced (now P-68, proved by its effect), authorised domains, billing alert. Confirm the **real per-SMS price for IN** in the billing console and write it into D-035.
  **Never add a test phone number to a project production uses (D-065):** its fixed code signs anyone in as that number wherever the project's tokens are accepted, production included, and in India the number may be a real person's (D-064).
  **There is no daily SMS cap to set** (4 October 2026, at the founder's direction; the first text asked for one). Google documents no such field. While `velora-ic` stays on plain Firebase Authentication, which it is (P-0.18), Firebase's fixed 3,000 SMS a day per project is a ceiling inherited, not configured. What bounds a flood is App Check (P-68), with the region policy and those fixed limits (P-0.18).
- [x] **P-0.13** Create the Google Cloud billing account and complete India's identity verification. **Owner: the founder, Shubham Kumar. Start: 3 October 2026. Due: 30 days after the account is created, when Google suspends an unverified Indian account; by 2 November 2026 if it's created on the start date.** Blocks T-3.14 (Firebase's Blaze plan bills to this account) and P-49's move (the Compute Engine VM does too). Started late, the 30-day clock is what stalls T-3.14.
  **How:** an Indian billing address means Google's mandatory identity verification. As an individual: PAN or e-Aadhaar through DigiLocker, and proof of address. As a business: a GST or Udyam certificate. **GST:** the advisor directing T-3.2 to T-3.10 says Velora has none, deliberately, below the threshold; P-0.2 still lists GST as unconfirmed, so the founder confirms it there. Without GST or a Udyam registration, it goes through as an individual.
  **If the payment method is refused** (AWS's was, P-0.6), write down exactly what Google said, as P-36 did for Fly, before trying anything else.
  **Closed 3 October 2026 (the founder):** Blaze is active, not just linked: the project shows "Blaze via Google Cloud free-of-charge trial", with ₹28,796.63 of credit valid until 2 January 2027. The ₹1,000 one-off payment is made, and India's tax info is submitted as an unregistered individual with PAN. The 30-day suspension clock is moot. **It leaves a worse-shaped risk in its place, dated: P-0.18,** the trial's end.
- [ ] **P-0.18** Convert the Google Cloud billing account from its free trial to a paid billing account, **after App Check is enforced and proved by its effect (P-68), and before launch.** **Owner: the founder, Shubham Kumar. Due: before launch (REL-1 if its tag includes T-3.14, T-9.15 at the latest), and in any case before 2 January 2027, or before the trial's ₹28,796.63 of credit runs out if that comes first.** Recorded 3 October 2026, when P-0.13 closed; rewritten 4 October 2026, when the daily SMS cap turned out not to be a setting.
  **Why** (the founder): on that date the trial ends, and unless the account has been converted by then, Firebase Auth stops and nobody can sign in, staging or production (they share `velora-ic`, D-065), with nothing wrong in the code and no deploy to blame. "This is exactly the kind of thing that is obvious in January and invisible in October." And the API must not move onto this account while it is a trial (P-49), since the trial's end would then stop the whole API, not just sign-in.
  **In this order** (the founder, 3 and 4 October 2026). On the trial an SMS flood ends the trial: an outage, no bill. Converted, a flood costs money. Neither is acceptable on its own, so something must bound a flood before converting to paid, and no console field does (below):
  1. **App Check enforced on Authentication and proved by its effect, first** (P-68). It is a prerequisite of the conversion, not a sibling: it makes a flood need our web app rather than a script, the strongest lever left. Until then, converting hands one person's card a bill bounded only by Firebase's own limits, and staying on the trial lets a stranger take sign-in down for everyone.
  2. **Then convert, before launch, not at the deadline:** after launch, the trial's end is an outage with no warning and no deploy to blame.
  **What bounds an SMS flood on this path, and what doesn't** (4 October 2026). Google documents no daily SMS cap an owner can set (read by Claude on 3 October 2026), so none of these is a number we chose:
  - **Who can ask:** App Check (P-68), not set up yet.
  - **Where to:** the SMS region policy, India only (set by the founder, T-3.14).
  - **How many:** Firebase's fixed limits for plain Firebase Authentication: 3,000 verification SMS a day and 900 a minute per project; 50 a minute and 500 an hour per IP (Firebase's limits page). **A ceiling we inherit, not one we chose, and only while `velora-ic` stays on plain Firebase Authentication:** Identity Platform's quotas page lists "No SMS/day limit" for a project with a billing instrument. At D-035's $0.01 to $0.07 an SMS (the IN price still unconfirmed, P-0.12), 3,000 a day is $30 to $210 a day.
  - **Not our server's limits:** the browser asks Google for the SMS (D-035). D-066's limits sit on Path B's send route, which staging and production don't serve (D-066's first rule), and T-3.14's throttle on `/v1/auth/firebase` counts token exchanges after the code is entered. Neither stands in front of a Firebase SMS.
  - **Not a budget:** budgets alert; they never cap (Google's budgets page). A budget also counts cost after credits unless told otherwise, so on the trial it sees ₹0 (T-3.14's budget alert counts cost before credits).
  **`velora-ic` is on plain Firebase Authentication** (established 4 October 2026). Its console offers SMS multi-factor authentication behind "Upgrade to enable", the Identity Platform upgrade, which the founder deliberately didn't take; and Firebase offers SMS MFA only after that upgrade: "If you've upgraded to Firebase Authentication with Identity Platform, you can add SMS multi-factor authentication". Read from the console and Google's docs, not from an API: this machine has no Google Cloud credentials. **If the project is ever upgraded, the picture changes** (the founder): the 3,000 a day goes, so this item's bound is re-derived before any upgrade, not after. P-68 may force that question, and says how.
  **Google's terms** (its Free Trial page, read by Claude on 3 October 2026): the trial account closes when 90 days pass or the credit is spent, whichever is first; "All resources you created during the trial are stopped"; and without an upgrade within a 30-day grace period they "are permanently deleted". Upgrading early keeps the remaining credit, usable within the original 90 days, and ends the trial's guarantee: "You will not be billed for any Google Cloud usage during your Free Trial."
  **Where it is read:** dated, in 07-CHECKLISTS §F; on REL-1's Needs line if REL-1's tag includes T-3.14 or falls on or after 2 December 2026; on T-9.15's Needs line; on P-49, which may not land on this account while it is a trial; and P-68 is its first step.
- [ ] **P-0.14** Decide where the registered office is, before `v0.1.0`, production's first release (REL-1). **Blocks that release, not the build:** on REL-1's Needs line, since a registered office is a judgement no check can make. `/contact` publishes D-058's registered office, the founder's home in Hajipur, and from `v0.1.0` it is public, crawled and archived: once Google and archive.org hold the address, no later change removes it.
  **Why it's a decision** (the founder, 3 October 2026): a sole proprietorship must publish a registered address, but it needn't be where the founder sleeps. A virtual-office or registered-address service in India, roughly ₹1,000 to ₹2,000 a month, meets the same requirement with a commercial address. For a dating app, where some users will be angry at whoever banned them, the difference matters.
  **If it changes:** a new decision supersedes D-058's office, `REGISTERED_OFFICE` in `web/src/lib/legal.ts` changes (its guard test names D-058), and the court follows the office (D-058), so a new city means a new court line too.
- [ ] **P-0.15** Move the Vercel team `knot11` to Pro before `v0.1.0` (REL-1). **Blocks that release, not the build,** and the release gate refuses while the team is on Hobby (D-075). Vercel's own terms: "Hobby teams are restricted to non-commercial personal use only", with "advertising the sale of a product or service" among their examples of commercial use (its fair use guidelines, updated 14 September 2026). A public dating app is plainly commercial. Until the release, staging is `noindex` with no traffic, so the risk is close to zero and it waits (the founder, 3 October 2026). Pro is $20 a month with one deploying seat, covering both projects.
  **The trial doesn't fit** (Vercel's own page, read 3 October 2026): 14 days or until its usage limits, whichever comes first; one per user account; started only by creating a new team, not by upgrading `knot11`; without a payment method it falls back to Hobby. So it is worth at most one month's $20, and only if started the day `v0.1.0` goes public, in a new team production would then live in. Upgrade `knot11` itself on release day.
  **The Hobby plan's upload cap already stops staging deploys** (found building T-3.14, 4 October 2026). Vercel refuses a deployment's upload past 5,000 files a day: `Error: Too many requests - try again in 24 hours (more than 5000, code: "api-upload-free")`, at `deploy.yml`'s `web — Vercel` job (`vercel deploy --prebuilt --prod`). Two staging deploys of green code hit it: `1d6eb44` (run 37146785444, 3 October, 19:10 UTC; its log also repeats `Error: Upload aborted`) and `94e3934` (run 37152600833, 20:46 UTC). `6d621f6` uploaded between them (run 37152210707, aliased at 20:40). Each time, gate, migrate and the Fly API had already deployed, so staging's API ran ahead of its web. **To recognise it in a minute:** the `web — Vercel` job red, every job before it green, and `api-upload-free` in its log. It's the plan's limit, not the code: there's nothing to debug. **Pro raises the cap, it doesn't remove it:** Vercel's limits page (read 4 October 2026) gives `api-upload-free` 5,000 a day and Pro's `api-upload-paid` 40,000. Vercel's own hint, `--archive=tgz`, would upload one archive instead of every file.
- [ ] **P-0.16** Move `velora-prod`'s Supabase organisation to Pro before `v0.1.0` (REL-1). **Blocks that release, not the build,** and the release gate refuses while it is on Free (D-075). The Free plan keeps no automatic backups, and the first real sign-up is the first thing worth losing (the founder, 3 October 2026). Pro is $25 a month per organisation with 7 days of daily backups; its $10 of included compute covers one project, which is why `velora-prod` has an organisation of its own (`infra/PRODUCTION.md`). Point-in-time recovery, a further add-on, is T-9.14's.
- [x] **P-0.6** Create accounts: GitHub, Supabase (Mumbai), Upstash, Cloudflare (R2 on), Fly.io (paid plan for `bom`), Vercel, Sentry, Sightengine.
  **Ticked with two still to set up then**, none needed before Sprint 4, each on its task's
  **Needs** line, which `/task` checks before planning: Sightengine (T-4.4; created by the founder
  on 4 October 2026, free plan, its keys in the Keychain) and Sentry (T-9.12). **The face-match
  vendor's account is dropped** (D-087, 4 October 2026): face matching runs on our own worker
  (D-088), and that account's unfinished payment verification is abandoned.
- [ ] **P-0.7** Review our own legal text before real users arrive — no lawyer at this stage (the founder's call, 1 October 2026). Check Terms, Privacy, Refunds and Contact (T-2.2) against the decisions they cite and against what the product actually does at go-live; against the IT Rules 2021 (Grievance Officer, timelines) and the DPDP Act (notice, consent, rights — section 16 and Rule 15 take effect on 13 May 2027; check for any restricted-country notification); and gender-based pricing. Start with the law-and-courts text (D-052), the weakest part we wrote ourselves. Look closely, not in passing, at the under-18 section: it keeps a hashed phone number of someone just identified as a minor (D-009). The mechanism and saying so openly are right, but minors plus retention is the most scrutinised combination there is. Privacy has no section yet on what happens to people's data if the app shuts down or is sold; add one when there is something honest to say. Gates T-9.15, not the production build (D-053). Terms' consumer-rights line (D-058) was written without a lawyer, by the founder and Claude: if the terms are ever reviewed properly, show it to one.
  **The face-match model's training data** (D-088, 4 October 2026), as written there, and never softened (the founder): the code and the weights permit commercial use (MIT, Apache-2.0). The weights' training data is a separate question: OpenCV Zoo doesn't say which set trained the shipped SFace model, and the SFace paper's experiments used CASIA-WebFace, VGGFace2 and MS-Celeb-1M, collections of faces of people who weren't asked. That is a question about the model's origins, not a restriction on using it.
  **No lawyer is engaged: an open item, and its owner is the founder, Shubham Kumar** (recorded 3
  October 2026). This review is his own, with Claude; no lawyer has read the legal pages. D-048
  calls this item "the DPDP session" and P-36 "the DPDP lawyer session", but none is booked. A
  dating app holding women's photos and phone numbers, with Terms, Privacy and Refunds written
  in-house, needs a lawyer's review before launch (the advisor directing T-3.2 to T-3.10, Claude in
  a separate chat). When one is booked, record who and when here.
  **Velas if Velora shuts down or is sold** (3 October 2026, D-076): paid Velas never expire and
  are never refunded, so `/terms` needs a line on what happens to an unspent balance then. It goes
  beside Privacy's missing section above, and is written when there is something honest to say.
  D-076 is Claude's reading of RBI's text, not legal advice: show it to the lawyer too.
- [ ] **P-0.17** A chartered accountant confirms how prepaid Velas are treated, **before the first real sale. Owner: the founder, Shubham Kumar. Trigger: Sprint 8, not launch:** it is on T-8.1's Needs line, so `/task` stops there. Recorded 3 October 2026, at the direction of the advisor directing Sprint 5 (Claude, in a separate chat).
  **What the CA confirms:**
  - **Revenue recognition:** unspent paid Velas are a liability until spent. They never expire and
    are never refunded (D-050, D-076).
  - **GST timing:** whether GST is due when Velas are sold or when they are spent.
  - **Registration:** whether Velora must register for GST at all. The advisor directing T-3.2 to
    T-3.10 says Velora has no GST registration, deliberately, below the threshold; P-0.2 still
    lists GST as unconfirmed. Google's tax form (P-0.13) went in as an unregistered individual with
    PAN (the founder, 3 October 2026): today's status, not whether registration is required.

  **No CA is engaged today.** Neither Claude nor the advisor has read the GST law, and neither
  makes any claim about it. Getting it wrong accrues quietly from the first sale and is expensive
  to unwind. When one is engaged, record who and when here, beside P-0.7's lawyer.
- [ ] **P-0.8** After T-2.2 is live: apply to Razorpay and Cashfree. Before applying, confirm each gateway's exact refund and cancellation-policy requirement against `/refunds` (D-050).
  **A gateway's refund-policy requirement is answered by D-076's rule 3** (3 October 2026): money
  goes back only for a payment with no Velas still standing against it. Never "refund unspent
  Velas": that would be the cash withdrawal ¶2.1 of RBI's PPI Directions forbids.
- [ ] **P-0.9** Buy a ₹10–12k Android phone for testing.
- [ ] **P-0.10** 15 conversations with women aged 22–28 in the launch city about why they left their last dating app. Write findings in `docs/research.md`.
- [ ] **P-0.11** Decide D-013 (city), D-014 (theme), confirm D-005 (packs).

---

# Sprint 1 — Foundation (weeks 1–2)

### T-1.1 · Monorepo skeleton
- [x] **Needs:** —
- [x] Create folders exactly as in `CLAUDE.md` "Repo layout". Empty folders get a `.gitkeep`.
- [x] Root files: `.gitignore` (Python, Node, `.env*` except `.env.example`, `.DS_Store`), `.editorconfig`, `README.md` (one paragraph + `make dev`), `Makefile` with the targets from `CLAUDE.md` (stubs that `echo "not yet"` are fine).
- [x] Copy `CLAUDE.md`, `docs/`, `.claude/commands/` into the repo.
- [x] **Done when:** `git status` shows the tree; `make` lists targets.
- [x] **Commit:** `chore(repo): monorepo skeleton [T-1.1]`

### T-1.2 · Local infrastructure
- [x] **Needs:** T-1.1
- [x] `infra/docker-compose.yml`: `postgis/postgis:16-3.4` (db `velora`, plus `velora_test` via init script), `redis:7-alpine`, `minio/minio` (S3-compatible stand-in for R2, buckets `velora-public`, `velora-private` created by an init container).
- [x] Healthchecks on all three; named volumes; ports 5432, 6379, 9000/9001.
- [x] `make infra-up` / `make infra-down`.
- [x] **Done when:** `make infra-up` → all healthy; `psql` connects; MinIO console shows both buckets.
- [x] **Commit:** `chore(infra): docker compose for postgres, redis, minio [T-1.2]`

### T-1.3 · API skeleton
- [x] **Needs:** T-1.2
- [x] `uv init api`; add runtime deps from `02-ARCHITECTURE.md` stack; dev deps pytest, pytest-asyncio, httpx, polyfactory, faker, ruff, mypy.
- [x] `app/core/config.py` — `Settings` with every var in `02-ARCHITECTURE.md §11`; fail fast on missing required vars; `.env.example`.
- [x] `app/main.py` — app factory `create_app()`; CORS from settings; request-id middleware (header `X-Request-ID`, generated if missing); structlog JSON logging with request id; orjson responses.
- [x] `app/core/clock.py` — `now()` returning timezone-aware UTC; the **only** way app code reads the time (tests freeze/advance it). `today_ist()` helper.
- [x] `app/core/errors.py` — `AppError(code, message, status, details)`; handlers for `AppError`, `RequestValidationError` (→ `VALIDATION_ERROR`), and unhandled (→ 500 `INTERNAL`, logged, Sentry).
- [x] **Done when:** `uvicorn app.main:app` starts; unknown route returns the error envelope.
- [x] **Commit:** `feat(api): app factory, config, logging, error envelope [T-1.3]`

### T-1.4 · Health endpoints
- [x] **Needs:** T-1.3
- [x] `app/core/db.py` async engine + `get_session` dependency; `app/core/redis.py` client.
- [x] `GET /healthz` → 200 always. `GET /readyz` → checks `SELECT 1` and Redis `PING`, 503 if either fails.
- [x] **Done when:** `/readyz` is 200 with infra up and 503 with Redis stopped.
- [x] **Commit:** `feat(api): health and readiness [T-1.4]`

### T-1.5 · Test harness
- [x] **Needs:** T-1.4
- [x] `pytest.ini`/`pyproject` config: asyncio mode auto, test DB `velora_test`, `@pytest.mark.critical` registered.
- [x] Fixtures in `tests/conftest.py`: per-test transaction rolled back; `client` (httpx AsyncClient on the app, sharing the test's transaction); `clock` (freeze/advance, always unfrozen). Moved to the tasks that build what they need: migrating once per session → T-1.7, `fake_providers` → T-1.21, `make_user` → T-3.1.
- [x] One sample test for `/healthz`.
- [x] **Done when:** `make test` runs green in < 10 s.
- [x] **Commit:** `test(api): pytest harness and fixtures [T-1.5]`

### T-1.6 · Lint, types, hooks
- [x] **Needs:** T-1.3
- [x] ruff (lint + format) config; mypy with `strict = true` for `app/` (allow untyped for alembic).
- [x] `.pre-commit-config.yaml`: ruff, ruff-format, mypy, gitleaks, end-of-file-fixer, prettier + eslint for `web/`.
- [x] **Done when:** `make lint` passes; a fake secret in a file is blocked by gitleaks.
- [x] **Commit:** `chore: ruff, mypy, pre-commit, gitleaks [T-1.6]`

### T-1.7 · Alembic
- [x] **Needs:** T-1.4
- [x] `alembic init -t async`; `env.py` reads `DATABASE_URL`; `target_metadata` from a shared `Base` with naming convention (`pk_`, `fk_`, `uq_`, `ix_`, `ck_`).
- [x] `make migrate`, `make migration m="…"`, `make migrate-down`.
- [x] Test harness: `test_engine` in `tests/conftest.py` migrates `velora_test` to head once per session (moved from T-1.5).
- [x] mypy: `api/alembic/` added to `[tool.mypy] files` and kept **strict** — the async `env.py` and generated revisions are already typed. A hand-written migration that genuinely needs loosening uses a per-file `# mypy: disallow-untyped-defs=False`.
- [x] **Done when:** an empty revision upgrades and downgrades cleanly.
- [x] **Commit:** `chore(db): alembic async setup [T-1.7]`

### T-1.8 → T-1.13 · Schema migrations
One migration per task, each with a working `downgrade()`. Build exactly `03-SCHEMA.md`.
- [x] **T-1.8** Extensions, all enums, `set_updated_at()` trigger function. — `feat(db): extensions and enums [T-1.8]`
- [x] **T-1.9** Identity + profile: `users`, `sessions`, `banned_identities`, `profiles`, `areas`, `interests`, `profile_interests`, `photos`, `verifications`, plus trigger making `users.gender`/`users.dob` immutable once non-null. — `[T-1.9]`
- [x] **T-1.10** Discovery + conversations: `swipes`, `profile_views`, `liked_you_reveals`, `matches`, `threads`, `messages`, `message_unlocks`, `thread_clears`. — `[T-1.10]`
- [x] **T-1.11** Album, kudos, safety: `album_requests`, `kudos`, `gifts`, `gift_sends`, `blocks`, `reports`, `fraud_scores`, `fraud_events`. — `[T-1.11]`
- [x] **T-1.12** Money: `wallets`, `ledger_entries` (+ no-update/delete trigger), `action_prices`, `credit_packs`, `payments`, `refund_requests`, `referrals`. — `[T-1.12]`
- [x] **T-1.13** Notifications + ops: `push_subscriptions`, `notification_prefs`, `notifications`, `audit_log`, `app_config`, `waitlist`. — `[T-1.13]`
- **For T-1.10 → T-1.13 (from T-1.9):** autogenerate drops `create_type=False` on every enum column,
  and the line wrapping varies, so **parse the migration file to verify it — never eyeball it.**
- [x] **Done when (each):** `make migrate && make migrate-down && make migrate` succeeds; SQLAlchemy models match.

### T-1.14 · Reference data migration
- [x] **Needs:** T-1.13
- [x] Data migration inserting `interests` (24), `gifts` (6, D-016), `action_prices` (D-004), `credit_packs` (D-005: 25/₹1,500 · 50/₹2,500 · 75/₹3,375 · 100/₹4,000, variant A; variant B entry pack ₹999/25 for the beta test), `app_config` seeds, `areas` for the launch city.
- [x] **Done when:** counts match; re-running is a no-op (`ON CONFLICT DO NOTHING`).
- [x] **Commit:** `feat(db): reference data [T-1.14]`

### T-1.15 · Dev seed
- [x] **Needs:** T-1.14, T-3.1
- **Why T-3.1:** every number goes through its `normalize_phone`, `hash_phone` and `encrypt_phone`, and the test woman's PIN through `hash_pin`, with the keys the local API reads, so login finds the seeded accounts. Parts that need later code live in those tasks: placeholder photos in T-4.4, verification rows in T-4.5, the test man's 60 Velas in T-5.1 (rule 5).
- [x] `make seed` runs `api/seed/`, which writes only when three independent facts hold, each an allowlist (rule 16, D-064): `ENV` is `local`; `DATABASE_URL`'s host is loopback; and the database itself carries the marker `make infra-up` stamps on it (`infra/postgres/stamp-local.sql`). The first two are checked before connecting; the marker is the connection's first read. A tunnel makes staging's database answer on `localhost`, and only the marker catches that. The seed lives outside `app/`: `.dockerignore` keeps it out of the image, and CI checks the image has none.
- [x] The 20 prototype profiles (`docs/prototype/`, the `P` array), each with the four rows `make_user` writes (users, profiles, wallets at 0, notification_prefs), a location scattered inside its neighbourhood, never on the centroid, so nobody is 0 m from anyone (`area_id`; within 750 m, derived from the username so every run is the same, and nearer its own centroid than any other area's; `city` Bengaluru until P-38, `hometown` from `from`), `users.created_at` from `joined`; women seek men, men seek women. Onboarding done, except Ishita, Riya and Pooja (the prototype's unverified women), who stop at the selfie step, unverified, so T-4.5 has women to verify; every onboarded woman is verified (D-008), and the men where the prototype has `v` (7). The profile flags (`show_kudos` from `showKudos`; `hide_age`, `hide_distance`, `show_gifts`, `is_hidden`) each take both values across the 20.
- [x] Swipes, never a like both ways, so no match: Ananya (a super-like, free for women), Meera and Tanvi like the test man (Tanvi's was Riya's in the prototype); Arjun and Rohan like the test woman. The test man passes on Diya and Nandini, and the test woman on Kabir, so their decks show that a profile already swiped doesn't come back.
- [x] A test man (`+91 90000 00001`, `test_man`, seeking women) and a test woman (`+91 90000 00002`, `test_woman`, seeking men, verified, a PIN), both onboarded at Koramangala; a moderator (`+91 90000 00003`, onboarding not started, so not in discovery). The 20 profiles take `+91 90000 00101`–`00120`. India reserves no fictional range, so these may be real people's numbers: T-3.2 and T-3.14 keep any OTP to them on the machine (D-064, D-065).
- [x] Interests: each profile keeps its 3 prototype tags plus 2 drafted by Claude from its `about` text; Kavya's "Carnatic" (not in the catalogue) is replaced. Intents: the prototype's value mapped — `serious` → Something serious, `longterm` → Long term, `short` → Casual dating, `chat` → Go with the flow — then roughly a third get a 2nd intent and a few a 3rd, fitting their `about`, so D-041's 1–3 and any-overlap filter run on real data. Show the founder all 20 (interests, the intent spread and the profile flags) before `/done`. The data file's note says the additions were drafted by Claude from the prototype's about text and reviewed by the founder.
- [x] The data is checked against the rules before anything is written: age 18 or over in IST, 5 distinct catalogue interests, 1–3 distinct intents, an about with no URL or phone number, every onboarded woman verified, swipes only between onboarded people, each pair once, and never a like both ways.
- [x] Running it again changes nothing: people are found by phone hash and never updated, in one transaction. Start over with `make infra-reset`, then `make infra-up migrate seed`; never a targeted delete, which the ledger refuses from T-5.1.
- [x] The seed's output never contains a phone number (rule 15).
- [x] **Done when:** `make seed` twice doesn't duplicate; `ENV` staging and production, a remote host and a loopback address to an unstamped database are each refused before a row is written (tests, 🔒); the test man's number, typed as people type it, finds him through `normalize_phone` and `hash_phone`.
- [x] **Commit:** `chore(dev): seed script [T-1.15]`

### T-1.16 · Schema tests
- [-] **Needs:** T-1.13, T-1.5
- [-] Tests that prove: `wallets.balance` can't go negative *(covered in T-1.12)*; ledger UPDATE/DELETE raises *(covered in T-1.12, TRUNCATE too)*; `threads` rejects `user_low >= user_high` *(covered in T-1.10)*; `users.gender` can't change once set *(covered in T-1.9, `tests/test_schema.py`)*; username regex enforced *(covered in T-1.9)*; unique `(sender_id, client_msg_id)` *(covered in T-1.10)*.
- [-] **Commit:** `test(db): constraint tests [T-1.16]`
- **Dropped:** every constraint above is tested in `tests/test_schema.py` by the task that built it
  (T-1.9 through T-1.12); nothing is left to add. Closed during T-1.14.

### T-1.17 · Web skeleton
- [x] **Needs:** T-1.1
- [x] `pnpm create next-app web` — TypeScript, App Router, Tailwind, ESLint, `src/` dir.
- [x] `tsconfig` strict + `noUncheckedIndexedAccess`; path alias `@/`.
- [x] Route groups: `(marketing)`, `(auth)`, `(app)`, `admin` with placeholder pages.
- [x] `src/styles/tokens.css` from `08-DESIGN.md`; Tailwind theme reads the CSS variables.
- [x] `src/i18n/en.ts` string dictionary + `t()` helper.
- [x] Verify the prettier and eslint pre-commit hooks from T-1.6 run on `web/` files; prettier must be a `web/` devDependency (create-next-app adds ESLint, not Prettier).
- [x] **Done when:** `pnpm dev` shows placeholders; `pnpm lint && pnpm tsc --noEmit` clean.
- [x] **Commit:** `feat(web): next.js skeleton with tokens [T-1.17]`

### T-1.18 · Web data layer
- [x] **Needs:** T-1.17, T-1.3
- [x] `make types` → `openapi-typescript $API/openapi.json -o web/src/types/api.ts`.
- [x] `src/lib/api.ts` — typed fetch wrapper: base URL, JSON, attaches access token, parses the error envelope into `ApiError {code, message, details, status}`.
- [x] `QueryClientProvider` in root layout; `src/lib/queries/keys.ts` (query key factory).
- [x] Zustand `src/store/session.ts` (access token in memory, user id).
- [x] ESLint enforces rule 14's "no `fetch` inside components": `fetch` is banned in `web/src`
  except `src/lib/`, so server data only reaches components through the api client and query
  hooks. Deferred from T-1.17 to here, where `src/lib/` is created — a rule goes in when the thing
  it protects exists.
- [x] **Done when:** a dev page calls `/healthz` via a query hook and renders the result.
- [x] **Commit:** `feat(web): api client, query setup, type generation [T-1.18]`

### T-1.19 · UI primitives
- [x] **Needs:** T-1.17
- [x] From the prototype, in `src/components/ui/`: `Button` (primary/ghost/danger, sm/md, loading), `Chip`, `Sheet` (bottom on mobile, centred on desktop, focus trap, Esc closes), `Field`, `TextArea` (counter), `Toast` + `useToast`, `Icon` (lucide-react), `Avatar`, `Spinner`, `EmptyState`, `ErrorState`, `Toggle`, `Skeleton`.
- [x] `/dev/ui` page (dev only) showing every primitive in every state.
- [x] Vitest + Testing Library; one test per primitive (renders, interaction, a11y role).
- [x] **Commit:** `feat(web): ui primitives [T-1.19]`

### T-1.20 · CI
- [x] **Needs:** T-1.5, T-1.6, T-1.19
- [x] GitHub Actions `ci.yml`: job `api` (postgis + redis services, `uv sync`, migrate, ruff, mypy, pytest); job `web` (pnpm install, lint, tsc, vitest, `next build`). Runs on every push, to any branch. Nothing is marked "required": there are no pull requests to attach required checks to. CI is binding anyway, through `/done` (next step, D-044).
- [x] Secrets scan in CI (from P-09): a `gitleaks git` step in the `api` job. The pre-commit hook
  only protects clones that ran `make hooks`, and `git commit --no-verify` skips it — without this,
  nothing server-side enforces checklist E's "no secrets in repo".
- [x] Hooks work from GUI git clients (from P-10): the ruff and mypy hooks resolve `uv`, and the
  prettier and eslint hooks `pnpm` (live since T-1.17), without relying on the shell's `PATH` (an
  absolute path, or a wrapper that locates it). VS Code's Source Control panel runs hooks without
  the shell profile, so either may be missing and every commit fails. Test a commit from VS Code.
- [x] Types are fresh (from T-1.18, rule 10): CI runs `make types` and fails if
  `web/src/types/api.ts` changes. `make types` works offline (D-043), so this needs no running
  API. Without it, a response schema can change with stale web types and only a reviewer notices.
- [x] `/done` gate (D-044): `/done` pushes the branch, runs `scripts/ci-gate`, and fast-forwards
  `main` only when CI passed for that exact commit. The gate finds the run by the commit's SHA,
  never "the latest run on the branch", and fails closed: no run within 3 minutes, no finish
  within 20, a cancelled or failed run, or GitHub not answering all stop `/done` with a message.
  `done.md` documents a manual path for GitHub being unreachable (exit 4) — never for a red run
  or an error GitHub answered (exit 5). `scripts/ci-gate-test` proves each case against a fake
  `gh`, and runs in CI.
- [x] **Commit:** `ci: api and web pipelines [T-1.20]`

### T-1.21 · Provider adapters
- [x] **Needs:** T-1.3
- [x] `app/core/providers/`: `SmsProvider`, `PaymentsProvider`, `ModerationProvider`, `FaceMatchProvider`, `PushProvider`, `StorageProvider` as `Protocol`s. Each has `Fake…` (in-memory, records calls; fake SMS logs the OTP to console in local only) and a real implementation stub raising `NotImplementedError`. Selection by env var.
- [x] `fake_providers` fixture in `tests/conftest.py` overriding every provider with its fake (moved from T-1.5).
- [x] **Done when:** tests can assert "an SMS was sent to X" via the fake.
- [x] **Commit:** `feat(api): provider interfaces with fakes [T-1.21]`

### T-1.22 · Staging deploy
- [x] **Needs:** T-1.4, T-1.17, P-0.6
- [x] `api/.dockerignore` excluding `.env*`, before the first image is built (from P-32). A `.env`
  in the image is a secrets leak: it bakes the JWT secret, the database password and every
  provider key into an image pushed to Fly's registry, and Docker keeps deleted files in earlier
  layers, so once pushed every one of them must be rotated. It would also set `ENV=local` and
  switch off D-045. CI checks that the built image has no `.env` in any layer.
- [x] `api/Dockerfile` (multi-stage, uv, non-root, base images pinned by digest). uvicorn with 2
  workers, not gunicorn: uvicorn restarts dead workers itself, and the image checks settings once
  before any worker starts, so a configuration error stops the container instead of crash-looping.
  `infra/fly.api.toml`, region `sin` (D-048: Fly retired `bom`), health check `/readyz`. No release command: migrations run
  from CI as the owner (D-046). The worker's Fly app moved to T-4.4, which builds the worker.
- [ ] Supabase staging project (enable PostGIS, pg_trgm, citext); Upstash staging DB; R2 staging buckets.
  All by hand, from `infra/STAGING.md`. **Open, for R2 alone (1 October 2026):** Supabase (Mumbai,
  migrated to head) and Upstash (Mumbai) are serving staging (deploy run 36845884410). R2 isn't
  enabled on the Cloudflare account yet, which only its dashboard can do, so there are no buckets.
  **Moved:** R2 is now on T-4.1's Needs line, the first task that uses the buckets — tick this with
  T-4.1.
- [x] Supabase's Data API off, and the app-role migration strips `anon` and `authenticated` of every
  privilege on our tables. Left on, it serves every table in `public` over REST to anyone with the
  project's anon key. The runbook ends with a SQL check that those roles hold nothing.
  Checked 1 October 2026: that query returned no rows, and every row of the app-role check was
  true. The Data API was never enabled, per the founder at setup.
- [x] Database pool sized for 2 workers (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`): each worker opens its
  own pool, so staging's budget is 2 × (5 + 2) = 14 connections, recorded in `infra/STAGING.md`.
- [x] Note: Supabase manages extensions from its dashboard. T-1.8's migration uses `create extension if not exists`, so upgrade is a no-op there — but its `downgrade()` drops them, so never downgrade a Supabase database to base.
- [x] Least-privilege database role (from P-18): the API and worker connect as a role that doesn't
  own the tables and can't `ALTER` them or set `session_replication_role`; migrations run as the
  owner, from CI (D-046), so the owner's credentials are never on Fly beside the app. The guards on `ledger_entries`, `payments` and `audit_log` are
  triggers — they stop application bugs, but an owner or superuser connection bypasses them with
  `SET session_replication_role = replica` or `ALTER TABLE … DISABLE TRIGGER`.
- [x] Tests, connected as that role: the writes each guard refuses are refused — UPDATE, DELETE and
  TRUNCATE on `ledger_entries` and `audit_log`; DELETE and TRUNCATE on `payments`, whose UPDATE
  stays allowed because a payment's status moves — and both bypasses are denied.
- [x] A separate Vercel project `velora-staging`, with no Git connection, deployed with `--prod` from
  `deploy.yml`: one stable URL, which the API's `CORS_ORIGINS` names. Its URL is
  `https://velora-staging-black.vercel.app`: `velora-staging.vercel.app` is another company's site
  (D-015, `infra/STAGING.md`). Deployed by run 36845884410; no Git connection, checked through
  Vercel's API on 1 October 2026.
- [x] Serve `/openapi.json` and `/docs` only when `ENV == "local"` (from P-31). `create_app()`
  serves them everywhere but production — a blacklist — so public staging would publish the full
  schema of the wallet, payment and admin routes. Nothing needs them outside local: `make types`
  reads the schema offline (D-043). Test staging and production: 404, and no schema in the body.
- [x] `/admin` returns 404 outside `next dev` (from P-30), with the same allowlist as `/dev/ui`
  and a test; check the staging 404's body, not just its status. Until T-9.5 there is no admin
  page to protect, only a placeholder that shouldn't be public.
- [x] GitHub Actions `deploy.yml`: on push to `main` → deploy staging API + worker, but only a commit whose CI passed — a second check after `/done`'s gate (D-044). Vercel deploys web itself from Git, which ignores CI by default: make its web deploys wait for CI too (e.g. deploy from `deploy.yml` with the Vercel CLI), or record why not.
  Also runnable by hand for any commit whose CI passed. GitHub runs `workflow_run` and
  `workflow_dispatch` workflows only from the default branch, so the first deploy follows the merge.
- [x] After every deploy, `scripts/staging-smoke` checks staging from the outside, bodies included.
- [x] **Done when:** staging web loads and staging `/readyz` is 200. **Proved by deploy run
  36845884410** (commit `c57634f`), whose smoke job passed every check against
  `https://velora-staging-black.vercel.app`, including that the web is our build calling this API.
  Run 36843892361 also went green but proves nothing: its smoke job checked another company's site.
- [x] **Commit:** `ci: staging deploy [T-1.22]`

---

# Sprint 2 — Public site (week 3)

### T-2.1 · Landing page
- [x] **Needs:** T-1.19
- [x] `(marketing)/page.tsx` from the prototype: header, hero, three feature cards, footer links. Server-rendered, with no page-level client JS. The waitlist box moved to T-2.3, with its form.
- [x] **Checklist A exception, on purpose:** the landing copy writes `app_config.thread_hours` out
  ("Threads last a day", and "24-hour" twice) instead of reading the setting. 03-SCHEMA's
  never-hardcode rule is about behaviour: the API must never hardcode the number when it computes
  expiry. Landing copy is a promise, not a computation, and making the page dynamic to render one
  number would cost the static prerender the Lighthouse target rests on. Comments in
  `web/src/i18n/en.ts`, 03-SCHEMA §8 and the seed test (`api/tests/test_reference_data.py`) say to
  change the copy with the setting. The seed migration is merged, so it can't carry one (rule 11).
- [x] **Done when:** Lighthouse mobile ≥ 90 performance, 100 accessibility on staging.
  **Measured 1 October 2026 by Claude**, on `https://velora-staging-black.vercel.app/` serving
  `c10e589` (deploy run 36892558024, smoke passed): Lighthouse 13.5.0, mobile, simulated
  throttling, three runs. Performance 98, 99 and 100; accessibility 100 in all three, with every
  weighted audit passing. The LCP element was the hero's paragraph, so it measured this page. Run
  locally with Chrome, because PageSpeed Insights' shared keyless quota was spent (HTTP 429).
- [x] **Commit:** `feat(web): landing page [T-2.1]`

### T-2.2 · Legal pages
- [x] **Needs:** T-2.1
- [x] `/terms`, `/privacy`, `/refunds`, `/contact` as TSX pages, written in plain language from our own decisions — no lawyer, no copied policy. Contact shows the company name, registered office, support email and **Grievance Officer name + email** (IT Rules). A fact we don't have yet shows as "To be confirmed", and production can't build while any is missing (D-053).
- [x] Footer links on every marketing page; the footer's city is Phagwara (D-013).
- [x] **Checklist A exception, on purpose:** the pages write out two `app_config` values in words — `thread_hours` ("lasts a day") and `mask_first_n_messages` ("first 20 messages") — for T-2.1's reason: copy is a promise, not a computation. Comments in `en.ts`, 03-SCHEMA §8 and the seed test say to change the copy with the setting.
- [x] **Done when:** all four reachable, linked, and printable. **Proved on staging, 1 October 2026,**
  by deploy run 36903641112 (commit `1d52ee5`, attempt 2): its smoke job passed every check,
  each legal page returning 200 with its title. Every marketing page's footer links all four
  (checked on `/`, `/terms`, `/privacy`, `/refunds` and `/contact`). Each page, printed from
  staging to PDF, prints the policy alone, on white, sections whole, footer and back link dropped.
  Attempt 1 failed closed: `APP_ENV` had been stored as a Vercel Secret, which `vercel pull`
  writes as `[SENSITIVE]`, and the gate refused it (D-053). It is now Config (`infra/STAGING.md`).
- [x] **Commit:** `feat(web): legal pages [T-2.2]`

### T-2.3 · Waitlist
- [x] **Needs:** T-1.13, T-2.1, and **P-33** (slotted before it, so the form is built once, against staging's final addresses)
- [x] API `POST /v1/waitlist {email, city?}` — validate email, citext unique (duplicate → 201 anyway), rate limit 5/min/IP.
- [x] The landing page's waitlist box, from the prototype (moved from T-2.1): heading, text, form
  and success state arrive together, so nothing on the page asks for an email it can't keep. The
  form is the landing page's one client component: add it to `CLIENT_COMPONENTS_ALLOWED` in
  `(marketing)/page.test.tsx`. The prototype's 48 px below the box is off the spacing scale; round
  it per 08-DESIGN §3.
- [x] **Done when, on staging:** joining from `https://staging.veloraapp.co.in` shows "You're on
  the list"; a sixth try within a minute gets `429 RATE_LIMITED` even when every try forges a
  different `Fly-Client-IP` and `X-Forwarded-For`, which proves Fly's proxy overwrites the header
  its docs don't promise to (D-056); and Lighthouse mobile on `/` stays at ≥ 90 performance and
  100 accessibility with the form on the page.
  **Proved on staging, 2 October 2026, by Claude,** on deploy run 37001771137 (commit `1b259d3`,
  smoke passed). Every test row's email is at `example.com`, so ours are told apart from people's.
  - **Joining:** headless Chrome joined from `https://staging.veloraapp.co.in` as
    `t-2.3-done-when-ui@example.com`. `POST /v1/waitlist` answered 201, "You're on the list"
    appeared inside the live region, and the form went away.
  - **The forged header:** six tries over IPv4, each forging a different `Fly-Client-IP`
    (198.51.100.1–6) and `X-Forwarded-For` (203.0.113.1–6), got five 201s, then `429
    RATE_LIMITED`. An unforged try was refused too, so the forged ones had counted against this
    machine's real address. An IPv6 try from the same machine 20 s later was allowed, so clients
    don't share one bucket either. Fly's proxy overwrites a forged `Fly-Client-IP` (D-056).
  - **Lighthouse** 13.5.0, mobile, simulated throttling, local Chrome: performance 90, 100, 100,
    100, and accessibility 100 in all four, with no weighted accessibility audit failing. The 90
    was the first run, with the same 158 KiB of script and the same server response as the rest:
    a cold first measurement, not the form. A fifth run hit a Chrome error page from this
    network's flaky DNS and isn't counted.
- [x] **Commit:** `feat: waitlist [T-2.3]`

### T-2.4 · SEO and sharing
- [x] **Needs:** T-2.1
- [x] Metadata API titles/descriptions, OG image (static), `sitemap.xml`, `robots.txt`, favicon + icons.
- [x] **Kept out of search with `noindex`, never a robots.txt disallow.** Every page outside
  production says `noindex` (an allowlist on `APP_ENV`), and so do the `(app)` and `(auth)` groups
  in every environment, which covers the routes added to them later. robots.txt disallows
  nothing. A disallow stops Google reading a page's `noindex`, so the page can still surface from
  links elsewhere while we believe it's hidden, and listing a path advertises it (P-30). The
  obvious-looking fix, "just disallow it", is the wrong one (the founder, 2 October 2026).
- [x] **Done when, on staging:** Lighthouse mobile on `/` stays at ≥ 90 performance and 100
  accessibility over several runs, all reported (its SEO score is under 100 there by design:
  staging is `noindex`); `robots.txt` disallows nothing and names no sitemap; `/` and `/discover`
  say `noindex`; `og:image` is an absolute URL on the staging address; and the share image, the
  favicon and the apple icon each answer 200 with their type.
  **Proved on staging, 2 October 2026, by Claude,** on deploy run 37006559216 (commit `629d66e`,
  smoke passed). Fetched the way crawlers fetch, with no JavaScript and no cookies:
  - **Pages:** `/` as WhatsApp, Facebook, X and Google, and `/terms`, `/privacy`, `/refunds`,
    `/contact`, `/discover` and `/login` as Facebook. Each answered 200 with its own title,
    `noindex, nofollow`, and `og:image` absolute on `https://staging.veloraapp.co.in/`.
  - **The share image itself:** the URL the tag points to, fetched as WhatsApp, Facebook and X,
    answered 200 `image/jpeg`, 1200 × 630, 42,679 bytes: the committed file byte for byte
    (SHA-256). This is the check that would have caught T-2.4's first build, whose previews were
    blank while every tag looked right.
  - **The rest:** `robots.txt` is `Allow: /`, with no disallow and no sitemap; the sitemap is
    empty; the favicon (`image/x-icon`) and the apple icon (`image/png`) answer 200.
  - **Lighthouse** 13.5.0, mobile, simulated throttling, local Chrome, five runs fixed in advance
    and all reported: performance 98, 100, 99, 100, 99; accessibility 100 in all five; SEO 66 in
    all five, failing only `is-crawlable`, which is the `noindex` working. Same 158 KiB of script
    as T-2.3's runs (90, 100, 100, 100).
- [x] **Commit:** `feat(web): seo basics [T-2.4]`

### T-2.5 · Security headers
- [x] **Needs:** T-1.17
- [x] `next.config` headers (02-ARCHITECTURE §12, D-059), from `web/src/lib/security-headers.ts`: an enforced CSP exactly as strict as today's pages allow; framing forbidden by `frame-ancestors 'none'` and `X-Frame-Options: DENY`; `nosniff`; Referrer-Policy; and a Permissions-Policy denying the camera, the microphone and location. Each later task widens it deliberately, and the module's comment and each task's line name them. Not report-only: with no collector it protects nothing (T-9.12 wires reporting). HSTS stays Vercel's; preload is T-2.6's decision.
- [x] **Done when, on staging:** securityheaders.com grade A; the five headers as served, HSTS
  without `preload`, and no `X-Powered-By`; headless Chrome shows no CSP violation on the seven
  pages, client-side navigation works, and the waitlist form hydrates and joins for real (201, an
  `example.com` address); and Lighthouse mobile on `/`, five runs fixed in advance and all reported,
  keeps ≥ 90 performance and 100 accessibility.
  **Proved on staging, 2 October 2026,** on deploy run 37037751830 (commit `8b4604f`, smoke
  passed):
  - **Served headers, read by Claude:** all ten URLs checked (the seven pages, a script, the
    share image and robots.txt) carry exactly the five headers; HSTS is `max-age=63072000` with
    no `preload`; there's no `X-Powered-By`; the CSP names staging's API.
  - **The browser, by Claude in headless Chrome:** no CSP violation on the seven pages; a real
    join through the form answered 201 (`t-2.5-done-when-browser@example.com`); client-side
    navigation works; and framed from another origin, Chrome refused: "Framing
    'https://staging.veloraapp.co.in/' violates the following Content Security Policy
    directive: "frame-ancestors 'none'". The request has been blocked."
  - **securityheaders.com, read by the founder** in their own browser (Cloudflare refuses curl
    and headless Chrome), 17:09:50 UTC, results hidden: **grade A**. Six headers detected (CSP,
    Permissions-Policy, Referrer-Policy, HSTS, X-Content-Type-Options, X-Frame-Options), and one
    warning, the predicted one, capping it at A: "This policy contains 'unsafe-inline' which is
    dangerous in the script-src directive." It also found what our checks couldn't:
    `access-control-allow-origin: *` on the page, Vercel's default (P-43, D-059's amendment).
  - **Lighthouse** 13.5.0, mobile, five runs fixed in advance and all reported: performance 100,
    100, 99, 100, 100; accessibility 100 in all five; SEO 66, failing only `is-crawlable`
    (staging's `noindex`).
- [x] **Commit:** `feat(web): security headers [T-2.5]`

### T-2.6 · Production domains
**Re-scoped by the founder, 3 October 2026: Sprint 2 closes on the build.** "The production
environment exists and is proved" is an engineering boundary, and it is met. "We told the
public" is a business act that waits on a home-address decision and two paid plans. So the three
production-live Done-whens, the `v0.1.0` tag and the setup that's left moved to REL-1, and T-2.6
is ticked on what it proved: the environment built, the gate working, staging green.
- [x] **Needs:** P-0.3, T-1.22, and the **legal facts final** (P-0.2, P-0.3) — production can't build the legal pages while any is missing (D-053)
  **Ticked 3 October 2026 by what each Need protects,** as the approved plan proposed: all six legal
  facts are known and a production build passes (P-0.3); P-0.2 stays open only for PAN, GST and the
  current account, none of which a page shows; T-1.22's one open box, the R2 staging buckets, moved
  to T-4.1.
- [x] **Production's pieces, set up on each platform and read back by Claude, 3 October 2026**
  (T-2.6's share of the box now on REL-1):
  - the GitHub environment `production`, whose only allowed source is the tag rule `v*`;
  - the Fly app `velora-api`, with no machine yet, its free addresses, and a certificate for
    `api.veloraapp.co.in` waiting on the DNS record;
  - the Vercel project `velora-production`, with `APP_ENV` = `production` and the API's URL, both
    `encrypted` (Config), and its domains: the apex, `www` → apex (308), and its own
    `velora-production-one.vercel.app` → apex (308);
  - in the `production` environment: both Vercel IDs, a deploy token for `velora-api` only, and
    both URL variables.
  **R2's production buckets are T-4.1's,** as staging's are: R2 isn't enabled on the account.
  **The Fly half is temporary:** P-49 moves the API to Mumbai before Sprint 4 and redoes it
  (`infra/PRODUCTION.md` lists what).
- [x] **Releases from a tag, and only what staging proved (D-075):** `deploy-production.yml` runs
  on a `v*` tag; `scripts/release-gate` refuses unless the commit is on `main`, CI passed for it,
  and staging deployed it, matched by the run's name, which `deploy.yml` now sets; it reads the
  Vercel token's expiry and warns within 30 days; `scripts/release-gate-test` runs it against fakes
  in CI. The `production` environment deploys only from `v*` tags.
  **Proved live, 3 October 2026, by Claude:**
  - **The gate refuses a commit that isn't on `main`:** a throwaway tag, `v0.0.0-gate-check`, on
    `c639832` (T-2.6's commit before it merged) ran the real workflow, run 37114027309. The gate
    said "Not releasing c639832. It isn't on main: production takes only commits that merged
    (D-075)", and every other job was skipped. The tag was deleted.
  - **No branch can use the environment:** a temporary branch whose workflow targeted `production`
    was stopped by GitHub before any step ran: "Branch "probe-production-env" is not allowed to
    deploy to production due to environment protection rules." (run 37114072837). The branch was
    deleted.
  - **Staging names each run for its commit:** run 37114304214 is "Deploy staging 9667bbf…", and
    passed, its web deployed with the token read from the environment and its smoke check's
    canonical line passing.
  - **The gate's tests:** 30 checks, passing in CI (run 37114146650). Four bugs planted in copies
    of the gate each failed them: matching staging by its recorded commit, the token as an
    argument, the 30-day boundary off by one, and no check for `main`.
  **Extended the same day (the founder):** it refuses while the Vercel team is on Hobby (P-0.15)
  or velora-prod's Supabase organisation, read through the project, is on Free (P-0.16), with a
  scoped, read-only Supabase token (D-075's amendment). `release-gate-test` grew to 49 checks;
  three more planted bugs each failed them: Hobby let through, a missing Supabase plan let
  through, and the token as an argument.
- [x] **Every build says which environment it's for (D-053's amendment):** `next build` refuses an
  `APP_ENV` outside local, ci, staging and production, and the smoke check compares the home page's
  canonical address with the site it checks. Proved 3 October 2026, before and after: with
  `APP_ENV` unset the build had passed and served `noindex` and `127.0.0.1` addresses, and now
  refuses; a build for staging, smoked as another site, fails the canonical check by name.
- [x] **HSTS, decided here with its own record (D-059).** Vercel sends `max-age=63072000` today. Whether to add `includeSubDomains` (every subdomain, staging included, HTTPS-only for two years) and whether to submit to the preload list is this task's decision, written down. Preload is close to irreversible: browsers hardcode it, and removal takes months. Never set in passing.
  **Decided: D-074.** `max-age=63072000; includeSubDomains`, set in `security-headers.ts`; never
  preloaded before launch, because preload is effectively irreversible. **Served on staging**
  (deploy run 37114304214, read by Claude on 3 October 2026): exactly one such header on every
  response checked (three pages, a 404 under the scripts' path, the share image and `robots.txt`),
  with no second one from Vercel; the home page's security headers are exactly the six, plus
  P-43's known wildcard.
- [x] **Commit:** `chore(infra): production domains [T-2.6]`


---

# Release — production goes public (not a sprint)

Production was built and proved in Sprint 2 (T-2.6). Telling the public is a business act that
waits on the founder's decisions, so it is a task of its own, outside the sprints (the founder,
3 October 2026). Not `T-2.7`: inside Sprint 2 it would hold the sprint open.

### REL-1 · First public release, `v0.1.0`
- [ ] **Needs:** T-2.6; **P-0.14**, the registered office, a judgement no check can make; and
  **P-0.15** (Vercel Pro) and **P-0.16** (Supabase Pro), which the release gate also refuses
  without (D-075). From the tag on, the site is public, crawled and takes real sign-ups.
  **And three found building T-3.14, each with no condition** (at the direction of the advisor
  directing T-3.14, Claude in a separate chat, relayed by the founder, 4 October 2026: "before
  REL-1" written only on an item, and not here, is a prerequisite nobody reads, as P-65's and
  P-66's were):
  - **P-70:** the phone screen says it takes Indian mobile numbers only, before anything is typed.
    It protects a person who isn't our user: today a foreign number's own ten digits, behind the
    fixed +91, send a code to a stranger in India, every time its owner tries.
  - **P-71:** `/privacy` names reCAPTCHA, which `/login` loads as it opens. The page is published,
    and inaccurate from the moment `/login` ships.
  - **P-69:** `velora-ic`'s browser API key restricted to our two sites and the APIs the web calls,
    after T-3.14's staging check.
  **And three that block only under their condition** (the founder, 3 and 4 October 2026), each
  condition written beside it so nobody reads it as unconditional and blocks a release that
  doesn't need it:
  - **P-66, if REL-1's tag includes T-3.14.** That tag opens sign-in, into the Firebase user pool
    staging shares (T-3.14), which is acceptable only while there are no real users: REL-1 is what
    makes real users possible, not T-9.15. A tag without T-3.14 opens no sign-in and doesn't wait.
  - **P-0.18, if REL-1's tag includes T-3.14, or falls on or after 2 December 2026.** The
    trial's end on 2 January 2027 stops Firebase Auth unless the billing account is paid, and
    after launch that is an outage with no warning (the founder, 3 October 2026): a tag with
    T-3.14 is launch in that sense, as for P-66. The date covers the rest: a month or less before
    the trial ends ("a month" is Claude's reading of the founder's "anywhere near it", approved).
  - **T-4.11, if REL-1's tag includes T-3.14.** Liveness before the first real user (the founder,
    4 October 2026): D-008 makes it mandatory for women, and T-4.5 ships without it.
  - **P-68, if REL-1's tag includes T-3.14.** App Check enforced on Authentication, proved by its
    effect, before the site is public for sign-in (the founder, 4 October 2026): it is what makes
    an SMS flood need our web app rather than a script. A backstop only: P-68 is the very next
    task after T-3.14, since the exposure opens at T-3.14's first staging deploy.
- [ ] `veloraapp.co.in` → Vercel prod; `api.veloraapp.co.in` → Fly prod app; SSL issued. Prod DB/Redis/R2 created but empty.
  **Moved from T-2.6** (the founder's re-scope, 3 October 2026). T-2.6 set up the GitHub
  environment, the Fly app and the Vercel project and its domains; what's left is the founder's,
  from `infra/PRODUCTION.md`: Supabase `velora-prod` in its own organisation, with its two
  connection strings and a scoped, read-only token for the gate; Upstash `velora-prod`; the
  one-year Vercel token; the `api` record at Cloudflare, which issues its certificate; and, on
  release day, the apex and `www` records.
- [ ] The prod app's four keys (`JWT_SECRET`, `PHONE_PEPPER`, `PHONE_ENC_KEY`, `CODE_PEPPER`) freshly generated, never staging's: startup refuses the repo's test keys (D-060) but can't know a copy of staging's. Read their shapes on the machine, lengths only, and compare each with its stored copy by SHA-256 prefix, as T-3.1 did for staging.
- [ ] **Rotate the `velora-prod` R2 token before the first production deploy** (the founder, 4
  October 2026): an Account API token, Object Read & Write, scoped to `velora-prod-public` and
  `velora-prod-private`, TTL Forever, both values in the login Keychain under `velora-prod`. The
  rotated token is the one that becomes the Fly secrets below.
- [ ] **R2's token for production's pair as Fly secrets on `velora-api`** (T-4.1): `R2_ACCESS_KEY_ID`
  and `R2_SECRET_ACCESS_KEY`, which the founder holds (`infra/PRODUCTION.md` §3). Without them
  production's API refuses to start. Prove the token's scope by its effect before the tag: refused
  on staging's buckets, beside a 404 on its own.
- [x] **And the only copy of production's keys must not be one Mac's Keychain** (the founder, 3 October 2026). Losing `PHONE_ENC_KEY` makes every stored phone number unreadable; losing `CODE_PEPPER` makes every PIN unverifiable; losing `PHONE_PEPPER` silently unbans every banned number, and login can't find any account until every number is re-hashed from its encrypted copy (D-061, D-062). Today that costs nothing, since no data depends on them. Decide here, where production's keys are born, where the second copy lives.
  **Decided (the founder, 3 October 2026): a password manager that syncs,** so the copy survives
  the machine; never only the Mac's Keychain, where `CODE_PEPPER` already sits, one laptop away
  from every production key being unrecoverable. The founder names which; nobody asks for or reads
  its contents. `infra/PRODUCTION.md` ("The keys") lists what each key protects and what losing
  it costs: consequences, never values.
  **Named, closing this (the founder, 3 October 2026): Apple Passwords, synced through iCloud,**
  with iCloud sync confirmed on in System Settings. Recorded beside the keys table in
  `infra/PRODUCTION.md`. The keys themselves are still the box above.
- [ ] **Tag `v0.1.0`** on a commit of `main` that staging deployed: `git tag v0.1.0 <commit> &&
  git push origin v0.1.0` (`infra/PRODUCTION.md`). The gate checks the rest.
  **"Staging deployed" means its deploy succeeded, smoke check included, not just that it ran,**
  and that stays true after Pro (P-0.15): a deploy can fail for reasons no plan tier touches, and
  tagging a commit nobody ever deployed is how a release ships something nobody ever saw running.
  `scripts/release-gate` already enforces it (its step 3, D-075). Read on 4 October 2026: for
  `94e3934`, "Not releasing 94e3934. Staging's deploy of it concluded 'failure' (run 37152600833):
  production only gets what staging proved (D-075)."; for `6d621f6`, "ok staging deployed 6d621f6
  and its smoke check passed (run 37152210707)." So a commit whose web upload was refused can't be
  tagged, even when its code matches a green commit's: tag the commit staging did deploy, or
  re-run its deploy until it succeeds.
- [ ] **Done when:** `https://veloraapp.co.in` shows the landing page; `https://api.veloraapp.co.in/healthz` is 200. → **Unblocks P-0.8.**
- [ ] **Done when, T-2.4's production side, which only production can prove:** `robots.txt` names
  `https://veloraapp.co.in/sitemap.xml`; the sitemap lists the five public pages on that address;
  `/` has no `noindex` while `/discover` and `/login` still do; `og:image` is on `veloraapp.co.in`;
  and Lighthouse SEO on `/` is 100. Unit tests cover it until then; this is the real check.
- [ ] **Done when, the first release's own checks,** each reported and nothing re-run: the gate
  passed on `v0.1.0`; production's security headers are exactly the six expected (the CSP naming
  `api.veloraapp.co.in`, and HSTS once, with D-074's value), with no `X-Powered-By`, nothing else
  but P-43's known wildcard, and Chrome refusing a frame; the founder's securityheaders.com grade;
  `www` and the project's `vercel.app` address answering 308 to the apex; MX, SPF, DKIM and DMARC
  unchanged at our nameservers after the apex record; Supabase's SQL checks all true, with no seed
  data; Lighthouse performance and accessibility from the SEO runs; and the gate refusing, live, a
  throwaway tag on a commit that isn't on `main`. That last one is done already, on 3 October 2026
  (run 37114027309, in T-2.6).
- [ ] **Commit:** `docs: first public release, v0.1.0 [REL-1]`

---

# Sprint 3 — Auth and onboarding (weeks 4–5)

### T-3.1 · Security primitives
- [x] **Needs:** T-1.21
- [x] `core/security.py`, every primitive from a vetted library (D-060; PyJWT, argon2-cffi, cryptography and phonenumberslite added): `normalize_phone()` (India only, E.164: `PHONE_NOT_SUPPORTED` for another country's number, `VALIDATION_ERROR` on `phone` for anything else), `hash_phone()` (HMAC-SHA256 keyed by `PHONE_PEPPER`), `encrypt_phone()`/`decrypt_phone()` (Fernet through MultiFernet, in the API, not pgcrypto: D-061), `make_access_token(user_id, role)` (15 min, `aud` = `ENV`), `decode_access_token()` (`AUTH_REQUIRED`, or `TOKEN_EXPIRED` only after a valid signature; expiry by `core.clock`), `new_refresh_token()` (32 random bytes, urlsafe), `hash_token()`, `hash_pin()`/`verify_pin()` (async: argon2id at D-062's exact parameters over a `CODE_PEPPER` key, at most two at once per process), `new_csrf()` and `csrf_matches()` (constant time; empty never matches).
- [x] Keys checked for shape at startup, everywhere; the repo's public test keys refused unless `ENV` is local (D-060). `CODE_PEPPER` added (D-062), which also keys T-3.2's OTP codes (D-063).
- [x] Unit tests for each, written so a deliberately weakened primitive fails: 31 weakened versions (a fixed salt, unchecked parameters, `==` for CSRF, the wall clock for expiry, no pepper and the rest), each turned at least one test red.
- [x] `make_user(gender="male", onboarded=True, credits=0, verified=None)` factory in `tests/conftest.py` returning `(user, access_token)` (moved from T-1.5; needs `users` from T-1.9). `verified` follows D-008 unless given; `credits` other than 0 raises until T-5.1 (rule 5).
- [x] **Staging made ready before `main` moved:** on 3 October 2026 Claude read staging's keys on the machine, lengths and hex only: `JWT_SECRET` at 128 lowercase hex characters, `PHONE_PEPPER` and `PHONE_ENC_KEY` at 64 each, matching `infra/STAGING.md`'s claim. `CODE_PEPPER` was generated into the Keychain and staged the same day (Fly lists it as `Staged`), so the deploy that needs it can start. There is no production Fly app yet. 20 hashes were timed on staging's machine: a median of 18.4 ms (D-062).
- [x] **Done when, on staging:** rebased onto `main`, which moved during the build, and gated on the rebased commit, not the one built, with P-0.3's lines in `05-PLAN.md` kept beside these (the founder, 3 October 2026); the deploy comes up on the new `Settings`; and `CODE_PEPPER`'s SHA-256 computed on the machine matches the Keychain copy's computed locally, first 8 hex characters. A shape check passes any 64 hex characters, so only a match proves the transfer landed intact. A mismatch costs nothing until the day Fly's copy is lost and restored from the Keychain: then every stored PIN becomes unverifiable at once.
  **Proved on staging, 3 October 2026,** on deploy run 37079492855 (commit `bcc3773`, smoke
  passed):
  - **Rebased and gated:** onto `72ef3a2` (P-0.3), whose plan lines stand beside these. The first
    commit's CI run, 37078451050, failed: GitHub's YAML read the unquoted, all-digit test keys as
    numbers (`PHONE_PEPPER` arrived as `7.07070707070707E+63`), and the new key checks refused them
    on their first real run, before anything deployed. `bcc3773` quotes them and makes the guard
    parse `ci.yml`. Its run, 37079193472, was green in 1 m 36 s: the `api` job took 63 s, against
    55 s before T-3.1.
  - **The deploy came up:** release v27, the machine started with its health check passing, and its
    image has `app/core/security.py`. Startup checks all four keys' shapes, so it couldn't have
    started on a malformed one.
  - **The match, read by Claude:** SHA-256 of each key computed on the machine and of its Keychain
    copy computed locally, first 8 hex characters, the values never leaving either place.
    `CODE_PEPPER`: `fd4ae0b5` on both. The other three, carried the same way in T-1.22 and never
    confirmed until now, match too: `JWT_SECRET` `f5fbdd09`, `PHONE_PEPPER` `f7d127c0`,
    `PHONE_ENC_KEY` `9d5de66c`.
- [x] **Commit:** `feat(auth): security primitives [T-3.1]`

### T-3.2 · OTP send
- [x] **Needs:** T-3.1
- [x] This is Path B (MSG91, used after DLT approval); the launch path is T-3.14. `/v1/auth/otp/send` and `/v1/auth/otp/verify` are served only where `AUTH_PHONE_PROVIDER` is `msg91` or `fake`, an allowlist (rule 16); everywhere else they 404, so staging and production, on `firebase`, can't send a Path B SMS at all (D-066).
- [x] `POST /v1/auth/otp/send {phone}` → `{resend_after_s}`. Normalise the phone; if its hash is in `banned_identities`, answer exactly as for any other number and send nothing. Generate a **6-digit** code (D-066), store `otp:{phone_hash}` = keyed HMAC of the code under `CODE_PEPPER`'s `otp/v1` key, not argon2 (D-063), + attempts 0, TTL 300 s; resend lock 45 s. Send via `SmsProvider`.
  **Built:** a banned number's code is stored too, never sent, so a wrong guess at verify gets the
  same `OTP_INVALID` as anyone's and the ban stays invisible to whoever doesn't hold the number.
  The 300 s and the resend lock run on `core.clock` (the stored expiry, a one-place window), so
  tests move them; Redis's TTL only clears the key.
- [x] `hash_otp` and its constant-time check join `core/security.py` beside the PIN's, under the `otp/v1` label T-3.1 reserved: HMAC over the number's hash and the code (D-063).
- [x] Limits (D-066, 02-ARCHITECTURE §12): 5 sends per phone an hour, 20 per IP an hour, 100 an hour per IPv6 /48, 10 per phone a day, and a global daily cap, `app_config.otp_sms_daily_cap`, a new key seeded at 500 by a new data migration (rule 11; list it in 03-SCHEMA §8). At the cap: `503 PROVIDER_UNAVAILABLE`, with a warning logged at 50%, which has nowhere to land until T-9.12 (D-066 records the gap). A banned or unknown number counts against every limit exactly as any other, and a phone at D-066's 10 wrong codes in 24 hours gets `RATE_LIMITED` here (T-3.3's verify keeps that count; T-3.2's test sets it directly).
- [x] **The worst case if the limits are wrong** (D-066, at D-035's unconfirmed ₹0.20 an SMS): with only the first two limits, ₹40,000 an hour from 10,000 rented IPs, and ₹2.6 lakh an hour from one cloud IPv6 /48. With the cap, ₹100 a day. Revisit at P-0.5, when MSG91 goes live.
- [x] **D-070: `normalize_phone` refuses a number that isn't a mobile** (landline, toll-free 1800, the 140 series), as `VALIDATION_ERROR` on `phone` ("isn't a mobile number"), which settles P-45. Update T-3.1's tests to the new rule, still asserting the exact error for each case; never loosen them.
  **Built as `MOBILE` or `FIXED_LINE_OR_MOBILE`, nothing else** (D-070): libphonenumber can't place
  a third or more of the 7 and 8 series as landline or mobile, and requiring `MOBILE` would refuse real
  mobiles there. Shared-cost (1860) and premium-rate numbers are refused too.
- [x] **A seeded number never gets a real SMS (T-1.15, D-064).** India reserves no fictional range, so the seed's `+91 90000 00xxx` numbers may be real people's. Where `ENV` is local, a real `SmsProvider` is called only for numbers in `SMS_LOCAL_ALLOWED_TO` (comma-separated, each passing `normalize_phone` at startup, empty by default); any other number gets `503 PROVIDER_UNAVAILABLE` naming the setting, before the provider is called, and its stored code is discarded. Settings refuse the setting outside local, where it would look like protection it isn't. Add it to 02-ARCHITECTURE §11 and `api/.env.example`.
- [x] `Msg91Sms` stays a stub that **raises** when called, never a fake success: a stub that reports success means "code sent" with no SMS, found only when a real user waits at an empty inbox (D-066). A test holds it to raising. The real client is P-46, after P-0.4 and P-0.5.
- [x] Tests: happy path, with a 6-digit code; resend too soon → `RATE_LIMITED`; 6th send in an hour → `RATE_LIMITED`; each of D-066's other limits; the global cap → `503 PROVIDER_UNAVAILABLE`; banned → the same 200 and no SMS; unknown → the same 200; a landline, a toll-free and a 140 number → `VALIDATION_ERROR`; 404 where `AUTH_PHONE_PROVIDER` is `firebase`; locally, with a real provider configured, a seeded number never reaches it (a recording stand-in proves it, since `Msg91Sms` has no HTTP client to watch until P-46); `Msg91Sms` raises.
- [x] **At `/done`:** D-070 becomes Locked; tick P-45.
- [x] **Commit:** `feat(auth): send otp [T-3.2]`

### T-3.3 · OTP verify and signup
- [x] **Needs:** T-3.2, and the **cookie scope settled**, because this task sets the first cookies and its tests would lock in a wrong scope. Settled 2 October 2026: the refresh cookie is host-only on the API (D-054), and both cookies are named for their environment (D-055)
- [x] `POST /v1/auth/otp/verify {phone, otp}`. Wrong code → attempts+1, `OTP_INVALID` with `details.attempts_left`; 5th wrong → delete key, `OTP_TOO_MANY`; no code stored (expired, or never sent) → `OTP_EXPIRED`. Correct → delete key. A phone at 10 wrong codes in 24 hours → `OTP_TOO_MANY` (D-066).
  **Built:** the try that reaches either limit, the code's fifth or the number's tenth that day,
  is the one answered `OTP_TOO_MANY`; `attempts_left` is the nearer of the two, so it never
  promises tries the number's lock would refuse. The right code is used up atomically (it must
  still be the code that was checked), so it signs in once.
- [x] Find user by `phone_hash`, or create in **one transaction**: `users` (+ referral code), `profiles`, `wallets` (0), `notification_prefs`. A referral code is 8 characters of Crockford base32 without 0, O, 1, I or L, in capitals, drawn again on a collision.
- [x] Who may sign in (D-067): `banned` → `ACCOUNT_BANNED`; `frozen` → `ACCOUNT_FROZEN`; `paused` may; `deleted` can't occur before T-9.6 and gets `FORBIDDEN` until T-9.6 decides.
- [x] Create session (family), valid 30 days from each rotation, storing no IP address or user agent (D-067). Set the refresh cookie (`refresh_prod`, `refresh_staging`, `refresh_local`; `HttpOnly; Secure; SameSite=Lax; Path=/v1/auth`, no `Domain`: host-only on the API, D-054), and the readable CSRF cookie (`csrf_prod`, `csrf_staging`, `csrf_local`): `new_csrf()`'s value, `Secure; SameSite=Lax; Path=/`, `Domain` from `COOKIE_DOMAIN` (host-only where that's empty, locally), 30 days. Return `{access_token, user: Me}`. Both names come from `ENV` with no fallback (D-055), and both cookies are `Secure` locally too (D-067).
- [x] **D-071: access tokens gain `auth_time`,** the session family's sign-in time. Update T-3.1's test of the claim set to the new exact set; never loosen it to "at least these".
  **Stored as `sessions.auth_time`** (D-071), a new column T-3.4 copies at each rotation: the
  family's first session is revoked by then, and the only index on `sessions` is partial.
- [x] **P-42, moved here:** a middleware in `create_app()` adds `X-Content-Type-Options: nosniff` to every response and `Cache-Control: no-store` to every `/v1` response, verify's included, since it carries an access token. Tests read both off real responses.
- [x] Set staging's `COOKIE_DOMAIN` to `staging.veloraapp.co.in` in `infra/fly.api.toml` (P-33 leaves it unset).
- [x] Point `make_user` (T-3.1) and `make seed` (T-1.15) at this find-or-create service: both write these four rows by hand until now. The 20 prototype profiles get generated referral codes. The three test accounts keep fixed, readable ones, `TESTMAN`, `TESTWOMAN` and `MODERATOR`: test accounts may be special, and looking up a random code every time is the friction the seed exists to remove (T-8.6 looks codes up and never checks their format).
- [x] CLAUDE.md: say why Safari can't sign in locally. It keeps no `Secure` cookie over plain `http://127.0.0.1`, so local sign-in needs Chrome or Firefox; Safari is tested on staging, which has HTTPS (D-067). Written down, the hour isn't lost later.
- [x] Tests: new user creates all 4 rows; existing user doesn't duplicate; banned → `ACCOUNT_BANNED`; frozen → `ACCOUNT_FROZEN`; `OTP_INVALID` carries `attempts_left`; 10 wrong codes in 24 hours → `OTP_TOO_MANY`; the refresh cookie has no `Domain`; both cookies' names follow `ENV`; both are `Secure`; the referral code's format; the access token carries `auth_time`; P-42's two headers; sessions keep no IP address or user agent.
- [x] **At `/done`:** D-066 and D-071 become Locked; tick P-42.
- [x] **Commit:** `feat(auth): verify otp and create account [T-3.3]`

### T-3.4 · Refresh and logout
- [x] **Needs:** T-3.3, and **P-33** (staging's web and API on one site, or the refresh cookie can't flow there)
- [x] `POST /v1/auth/refresh`: require `X-CSRF` equal to this environment's CSRF cookie (D-055); look up the `token_hash` of this environment's refresh cookie. If it was revoked less than 10 seconds ago → `SESSION_REVOKED`, leaving its family alone: two tabs refreshing at once cause it (D-067). If longer ago → revoke the whole family (reuse attack) → `SESSION_REVOKED`. Else rotate: a new session valid 30 days, old `revoked_at` + `replaced_by`, a new CSRF value, `auth_time` carried unchanged (D-071).
  **Built:** the presented session is read `FOR UPDATE`, so two refreshes at once rotate it once
  and the second lands in the grace; a test on two connections proves it, and failed without the
  lock. A missing or mismatched `X-CSRF`, a missing cookie, another environment's cookie, an unknown
  token or a session past its 30 days is `AUTH_REQUIRED`. An account that can't sign in (D-067)
  can't refresh either: the new token needs the user's role, so the row is read anyway.
- [x] `POST /v1/auth/logout`: authenticated like refresh, by the refresh cookie and `X-CSRF`, not the access token, so it still works once that has expired (D-067). Revokes the session's family and clears both cookies → 204.
- [x] Tests: rotation works; reuse after 10 seconds kills the family (🔒 15); reuse within 10 seconds is refused and doesn't; missing CSRF → 401; logout works with an expired access token and clears both cookies; `auth_time` survives rotation.
- [x] **Commit:** `feat(auth): refresh rotation and logout [T-3.4]`

### T-3.5 · Current user
- [x] **Needs:** T-3.4
- [x] `deps.current_user` (decode JWT, load user, reject frozen → `ACCOUNT_FROZEN`, banned → `ACCOUNT_BANNED`, deleted → `FORBIDDEN`), `deps.onboarded_user` (also require `done`, else `ONBOARDING_INCOMPLETE` with `details.step`), and `deps.require_role()`, which reads the user row `current_user` loads anyway, never the token's `role`: a demotion takes effect at the next request (D-067).
- [x] 02-ARCHITECTURE §12's default limit, 300 a minute per user, goes in `current_user`, so every authenticated route inherits it.
- [x] **The 15-minute tail (D-067):** a revoked session's access token works until it expires. Bans and freezes are immediate anyway, since `current_user` loads the user; logout, a reuse attack and five wrong PINs (D-069) are not. Accepted, and read with D-069: the PIN lock is a deterrent, not protection.
- [x] `GET /v1/me` → `Me` (04-API): the age, never the date of birth, which no screen shows, and no phone number: data nothing displays isn't sent (D-067's discipline). Throttled `last_active_at` update (Redis key, once per 60 s).
  **Built in `current_user`, not only `/me`:** "last active" has to mean any signed-in request, or
  someone swiping without reloading would look away; the Redis key is a one-place window on
  `core.clock`, so tests move it. `current_user` reads the user in a transaction of its own and
  ends it, so a route's service can open another; a bare read would leave one open and every
  `async with session.begin()` after it would fail. The who-may-sign-in allowlist moved to
  `users.service`, one rule for sign-in, refresh and every request.
- [x] **At `/done`:** D-067 becomes Locked.
- [x] **Commit:** `feat(users): current user and /me [T-3.5]`

### T-3.6 · DOB, gender, seeking
- [x] **Needs:** T-3.5
- [x] `POST /me/dob`: compute age in IST. Under 18 → **D-072**: in one transaction, delete the user and everything attached (the user row with its encrypted number, profile, wallet, notification preferences, sessions), keep only the number's hash in `banned_identities` (`reason` `underage`, D-009), and return `UNDERAGE`. A date in the future, or more than 100 years ago → `VALIDATION_ERROR`. Otherwise advance.
  **Built:** the deletion clears exactly six tables' rows (sessions, notification preferences,
  wallet, profile intents, profile interests, profile) and then the user, and commits before
  `UNDERAGE` is sent. Every other foreign key into `users` is RESTRICT, so a row anywhere else
  stops the deletion whole: a 500, nothing deleted, no hash kept, rather than a moderation or
  money record taken with the account (rule 12); a test holds every key into `users` to that
  split, so a later table that cascades fails it (P-54). A date is only `YYYY-MM-DD`: pydantic
  alone reads a number as a Unix timestamp in UTC, the wrong day in India for part of every day.
  "More than 100 years ago" is before this day 100 years back, so 100 years to the day is accepted.
- [x] `/privacy`'s under-18 paragraph (`web/src/i18n/en.ts`) adds that everything else is deleted at once (D-072); `/terms` already says the number is barred.
- [x] `POST /me/gender`: only if null → set, advance; else `IMMUTABLE_FIELD`.
  **Built:** the same value sent again is `IMMUTABLE_FIELD` too, for gender and dob alike, as
  "only if null" says; a client retrying after a lost answer reads `/me` instead.
- [x] The database also refuses the change (T-1.9's `users_identity_immutable` trigger) with SQLSTATE `23514` `check_violation`, which SQLAlchemy raises as `IntegrityError`. Map it to `IMMUTABLE_FIELD` by that SQLSTATE — never by the message text, which Postgres can reword.
  **Built:** mapped only where `users` is written, which has no CHECK constraint, so 23514 there
  is the trigger's; `profiles`' length CHECKs raise the same SQLSTATE and are never mapped. A test
  switches the service's own check off and gets `IMMUTABLE_FIELD` from the trigger, for both fields.
- [x] `GET /intents`; `POST /me/seeking {seeking, intent_ids}`: seeking women, men or everyone, as the prototype offers; 1 to 3 valid distinct ids (D-041), replace the set in one tx → advance.
- [x] **The step rule (D-068):** each step's endpoint works at its step, advancing it, and after it, as an edit that doesn't advance; before it → `ONBOARDING_INCOMPLETE` with `details.step`, the user's current step. Once set, dob and gender are `IMMUTABLE_FIELD` instead.
  **Built:** `users.service.at_step`, called by every onboarding write after it re-reads the user
  `FOR UPDATE`, so two writes at once take turns. A test on two connections proves it for seeking,
  and failed without the lock: the user ended with both sets of intents.
- [x] Tests for each branch, including "17 years 364 days" and "exactly 18 today"; after `UNDERAGE` nothing survives but one `banned_identities` row: no user, session, profile, wallet or preferences row (🔒 7); a future date and one 101 years ago → `VALIDATION_ERROR`; a step before its turn → `ONBOARDING_INCOMPLETE` with the current step; an edit after it doesn't move the step.
- [x] **At `/done`:** D-072 becomes Locked.
- [x] **Commit:** `feat(onboarding): dob, gender, seeking [T-3.6]`

### T-3.7 · Name, places, username
- [x] **Needs:** T-3.6
- [x] `PATCH /me/profile`: first_name 1–30 characters after trimming, letters in any script (Devanagari, Gurmukhi and the rest), single spaces, and an apostrophe or hyphen inside a name; hometown, city ≤ 40; about 40–300, trimmed, no URLs, no phone numbers. It spans two steps (D-068): `profile` advances once first_name, hometown and city are all set, `about` when about is set at that step; a field of a step not yet reached → `ONBOARDING_INCOMPLETE`.
  **Built** (`profiles/rules.py`, which `make seed` now checks its people against too): text is
  trimmed and put in NFC before it is measured or stored. A letter is any Unicode letter, and the
  marks after it, since no Devanagari or Gurmukhi name is written without vowel signs and viramas;
  digits in any script, zero-width joiners and no-break spaces are refused, and two spaces in a row
  are refused, not collapsed. The apostrophe is `'` or `’`, which a phone's keyboard types.
  Hometown and city refuse control and format characters, where a NUL would have been a 500. A
  null field is "not sent"; every refused field is named at once; and a field of a step not
  reached refuses the whole request, the fields sent beside it too.
- [x] "No URLs, no phone numbers" in about: URLs, `www.` and bare domains; and a phone number is a **run** of 10 or more digits with at most two separators (space, dash or dot) inside it, never digits scattered across a sentence. Ten, because the check exists to catch a reachable Indian mobile number, which is exactly ten digits; below ten it catches dates, and "2010-2015" is a life story, not a contact detail (the advisor directing T-3.2 to T-3.10, approved by the founder, 3 October 2026; seven was a guess). T-7.3's contact masking builds its own, broader check later.
  **Built:** a link is a scheme, `www.`, or a bare domain: a name, a dot and an ending from a list
  people type for links, India's and the shorteners' included (`wa.me`, `t.me`, `bit.ly`). Not
  every ending there is: that would refuse words run together. The ending must be lowercase, so a
  sentence after a missed space ("chai.In the evenings") passes, and the name two characters or
  more, so "B.Com" and "B.Tech" pass, unless a path follows (`x.com/ravi`). Digits in any script
  count toward a phone number. Allowed as the rule is written, and pinned by tests at its edges:
  "98 765 43 210" (three separators) and "98765 - 43210" (three separator characters).
- [x] `GET /usernames/{u}/available` → `{available, suggestion?}`, 30 a minute per user: the regex, then the reserved list (D-068): admin, administrator, mod, moderator, support, help, helpdesk, staff, team, official, root, system, security, api, www, mail, billing, payments, legal, privacy, terms, grievance, knot, knots, thread, threads, vela, velas, me, null, undefined, and the brand from `APP_NAME`, so a rename moves it (rule 17). Matching ignores case, dots and underscores (`ad.min` is admin). The suggestion is the name plus two random digits, checked free.
  **Built:** a name outside the format is `VALIDATION_ERROR`; a reserved or taken one is
  `available: false`, and `PUT` answers `USERNAME_TAKEN` for both. A reserved name gets no
  suggestion: the name with two digits after it is the impersonation the list exists to stop. A
  user's own name is available to them. The suggestion trims the name to 18 characters, so it
  fits 20. `APP_NAME` moved from `app/main.py` to `app/core/config.py`, where a service can read it
  (a service importing `main` would be a cycle).
- [x] `PUT /me/username`: typed in any case, stored in lowercase; handles the unique-violation race → `USERNAME_TAKEN`. Changeable until onboarding is `done`, then `IMMUTABLE_FIELD` until T-9.6 designs changes (D-068). The public page stays D-001's `/@username`: usernames never take a bare top-level path, so the reserved list needn't hold route segments.
  **Built:** the race is proved on two connections, both finding the name free before either
  writes; only the unique index tells them apart, and it is read by SQLSTATE `23505` and the
  constraint's name, `uq_profiles_username`, never the message.
- [x] Tests: each first-name rule both ways; "9876543210", "98765 43210", "+91 98765 43210" and "Call me on 98765 43210" refused; "I lived in Delhi 2010-2015" and "I was born in 1998 and moved here in 2015" allowed; a reserved name, a dotted variant of one, and the brand; `USERNAME_TAKEN` in the race; capitals stored lowercase; a change after `done` → `IMMUTABLE_FIELD`; a field before its step → `ONBOARDING_INCOMPLETE`.
- [x] **At `/done`:** D-068 becomes Locked.
- [x] **Commit:** `feat(onboarding): profile basics and username [T-3.7]`

### T-3.8 · Interests
- [x] **Needs:** T-3.7
- [x] `GET /interests`; `PUT /me/interests` exactly 5 valid distinct ids → replace set in one tx.
  **Built:** like seeking's: the user re-read `FOR UPDATE`, D-068's step rule, all different and all
  in the catalogue, exactly 5 in the request's schema (the web's contract, read back from OpenAPI by
  a test) and again in the service (03-SCHEMA). `GET /interests` is public, as 04-API marks it, with
  no limit of its own: 24 rows of catalogue, nobody's data. A two-connection test proves the lock.
- [x] The interests step comes after photos (D-068), so a real user reaches it only after T-4.3; tests set the step directly.
- [x] **Commit:** `feat(onboarding): interests [T-3.8]`

### T-3.9 · PIN
- [x] **Needs:** T-3.5, and T-3.6's step rule (D-068), which the `pin` step follows
- [x] `POST /auth/pin/set {pin, current_pin?}` → 204: 4 digits (D-012), refusing one digit four times, straight runs either way (0123…, 9876…), alternating pairs (1212) and the 20 most common PINs in DataGenetics' published study → `VALIDATION_ERROR` (D-069). Changing an existing PIN needs `current_pin`, except within 10 minutes of a fresh sign-in, read from `auth_time` (D-071); that is also "forgot PIN": sign out, sign in by OTP, set a new one. At the `pin` onboarding step, setting one advances to `selfie`.
  **Built:** the rule is `auth/pins.py`, which `make seed` checks its PIN against too. It refuses
  exactly 118 of the 10,000 PINs, held so by a test over all of them: 10 one-digit, 14 runs, 90
  alternating pairs, and 1004, 2000, 1122 and 2001, which only the study's list catches. The list is
  the study's table, ranks 1 to 20, read from datagenetics.com on 3 October 2026. No problem's
  wording holds a digit, so no error repeats a PIN, even one refused (rule 15). A change outside the
  window with no `current_pin` is `VALIDATION_ERROR` on `current_pin`, not `PIN_INVALID`: no guess
  was made. "Within 10 minutes" is `now - auth_time` under 10 minutes, so 10:00 is outside. A wrong
  `current_pin` counts as a wrong PIN. Before the `pin` step, setting one is
  `ONBOARDING_INCOMPLETE`; after it, a first PIN is set without advancing. The window is proved
  with real tokens: fresh at 9 minutes, not at 11 though the token still works, not after a refresh
  (it carries `auth_time`), fresh again after a new OTP sign-in. A new dependency,
  `deps.access_claims`, hands a route the token's claims beside `current_user`.
- [x] `POST /me/pin/skip` → `Me`: moves `pin` → `selfie` (D-069).
- [x] `POST /auth/pin/verify {pin}` → 204, or `PIN_INVALID` with `details.attempts_left`. `pin_failed` goes up by one per wrong PIN, in one atomic update; a correct PIN resets it, and so does a fresh sign-in (add that to T-3.3's sign-in service). **At 5, every session of the user is revoked** → `SESSION_REVOKED`; each revoked session's access token still works for up to 15 minutes (D-067).
  **Built:** the try is counted before the hash is checked, by one `UPDATE … WHERE pin_failed < 5
  RETURNING`, committed on its own: tries made at once are each counted, and no more than five are
  ever checked between resets (eight at once on eight connections: five checked, four
  `PIN_INVALID`, four `SESSION_REVOKED`). Past five, nothing is checked, the right PIN included,
  until a fresh sign-in. Verifying with no PIN set is `NOT_ALLOWED`.
- [x] A stored hash `verify_pin` refuses (other parameters, unreadable) doesn't count against `pin_failed`: `PIN_INVALID` with `details.reset_required`, and the way out is the fresh sign-in above (D-069). `hash_pin`/`verify_pin` are T-3.1's (D-062).
  **Built:** `check_pin` joins `core/security.py` and tells a match, a wrong PIN and a refused hash
  apart; `verify_pin` is now `check_pin(...) is MATCH`, so T-3.1's tests hold it unchanged. D-062's
  parameters around a body that won't decode are refused too. A refused hash gives its try back,
  never below zero.
- [x] The PIN endpoints: 10 a minute per user; each check holds 19 MiB for about 18 ms, two at once per process (D-062).
  **Built:** one shared count for setting and verifying; skipping hashes nothing and isn't in it.
- [x] **What the lock doesn't do (D-069, with D-067):** it deters whoever picks up an unlocked phone; it protects nothing. The web keeps a working access token behind the lock screen, so the browser's devtools get past it, and five wrong PINs leave the revoked sessions' tokens working for up to 15 minutes. Never build on it as a security boundary.
  **Built:** a test pins the tail, so nobody mistakes the lock for protection: after five wrong
  PINs the access token still reads `/me` at 14 minutes and is `TOKEN_EXPIRED` at 15.
- [x] The seed's test-woman PIN (`TEST_WOMAN_PIN` in `api/seed/data.py`, T-1.15) must stay valid under these rules; a test here checks it, so the seed doesn't break the day the rules land.
- [x] Tests: each refused shape, and 4829 accepted; a change without `current_pin` refused, and allowed within 10 minutes of sign-in; 5 wrong → every session revoked; a refused hash doesn't count and sets `reset_required`; skip advances; the rate limit.
- [x] **At `/done`:** D-069 becomes Locked.
- [x] **Commit:** `feat(auth): pin lock [T-3.9]`

**T-3.10 to T-3.13 were planned together on 3 October 2026**, the app's first real screens.
Recommended by Claude in a joint plan of 23 decisions, answered by the advisor directing it (Claude,
in a separate chat) and relayed by the founder. Four became D-079 to D-082, one amended D-059, and the
rest are written on the tasks below as "decision N". **T-3.14 isn't in that batch:** it needs
Firebase's Blaze plan, which bills to the Google account P-0.13 creates, and that account didn't
exist yet. The batch is a chain, T-3.10 → T-3.11 → T-3.12 → T-3.13, each needing the last.

### T-3.10 · Web auth client
- [x] **Needs:** T-1.18, T-3.4, T-3.5 (`useMe()` reads `Me`), T-3.9 (the lock reads `has_pin` and calls `/auth/pin/verify`), and **P-55**: until it lands, a local gate run beside another session proves nothing (raised by the advisor, 3 October 2026)
- [x] Access token in Zustand (memory only). On load, in the `(auth)` and `(app)` layouts only, call `/auth/refresh` once to restore a session, sending `X-CSRF` from this environment's CSRF cookie (D-055). Marketing pages never call the API: they stay static (Lighthouse, P-37).
- [x] Cookie names at build time: `next.config` maps `APP_ENV` to the suffix, an allowlist (rule 16): `production` → `prod`, `staging` → `staging`, `local` and `ci` → `local` (T-3.13's E2E runs a production build against an API whose `ENV` is `local`), and `local` under `next dev` with `APP_ENV` unset. No new Vercel variable. The api client sends `credentials: "include"` on `/v1/auth/*` only, the refresh cookie's path. Until now it sends no credentials at all, so no cookie would arrive.
- [x] On any 401 `TOKEN_EXPIRED`: single-flight refresh, then retry the request once. Refreshes are serialised across tabs with the Web Locks API, so two tabs never rotate one token (D-067's 10-second grace covers what's left). Read the CSRF cookie inside the lock, after any refresh ahead of it has set new values.
- [x] `useMe()` query; `<OnboardingGate>` redirects to the user's step at its D-080 URL. This task builds D-080's slug map, with a placeholder page per step until T-3.11 and T-3.12 build the screens. `(app)` routes require `done`.
- [x] **When restoring the session fails** (decision 8): only a 401 sends you to `/login`. A network failure or a 5xx shows an error with Retry, because a phone losing signal mustn't look like being signed out.
- [x] **Who owns the frame** (decision 5; T-3.11 and T-5.6 carry the same line). This task owns what the `(auth)` and `(app)` layouts do: restore the session once per page load, apply the gates, and show the PIN lock. They draw nothing else but a full-screen loading or error state and the lock screen. T-3.11 owns the onboarding frame. T-5.6 adds the header and bottom nav inside the `(app)` layout, never replacing what this task put there. The root layout keeps `QueryProvider`, so P-37's smoke marker is untouched.
- [x] **PIN lock screen:** `PinPad` is a `ui/` primitive with a test and a `/dev/ui` entry (08-DESIGN §4); T-3.12 reuses it. The lock shows on load, and after 5 minutes hidden, if `has_pin`, wherever a session exists: onboarding and the app, never `/login`. A wrong PIN shows `attempts_left`; `SESSION_REVOKED` goes to `/login`; `reset_required` offers the way out below. A deterrent, not protection (D-069).
- [x] **Durations kept in the browser** (decision 9): the 5 minutes, and T-3.11's 400 ms before a username check, are named constants. That's a Checklist A exception, recorded here as T-2.1 recorded its copy: a deterrent the browser runs is not a limit the server enforces, and reading `app_config` would need a new public endpoint.
- [x] **A sign-out before T-9.8** (decision 7): `logout()` in the session layer, and two controls. "Forgot your PIN? Sign out" goes on the lock screen, D-069's way out. A quiet "Sign out" goes in the onboarding frame's top bar, which T-3.11 places. T-3.14's item 5 needs the second: its tester can't reach the PIN step before Sprint 4, because it comes after photos (D-068).
- [x] Local development at `127.0.0.1` only: `localhost:3000` → `127.0.0.1:8000` is cross-site, so the `Lax` refresh cookie silently isn't sent. Remove `localhost` from the local `CORS_ORIGINS` (`api/.env.example`, the test settings), so that mistake fails loudly. In CLAUDE.md's local sign-in paragraph, add that reason, and replace "expected, not yet observed" with what the Done-when below sees, dated.
- [x] **Done when, locally, in Chrome against `make dev`** (decision 10). This task has no phone screen, so sign in from the browser console, with the two requests T-3.11's screens will make. Then observe, on the wire (devtools' network and cookie panes), never inferred from a test:
  - a reload restores the session;
  - both cookies rotate, and the next refresh carries the new values;
  - two tabs reloaded together both stay signed in;
  - `test_woman`'s lock appears, and a wrong PIN shows the attempts left;
  - sign-out clears both cookies;
  - ~~Safari, going through the same steps, loses the session at reload.~~ **Struck, 3 October 2026
    (the founder):** with D-074's HSTS, production is never plain HTTP, so Safari dropping a
    session over plain `http://127.0.0.1` is not a case any user can reach. It isn't carried as
    unverified. Safari's real case is HTTPS: T-3.14's.

  This proves T-3.14's items 4 and 6, and parts of 1, 3 and 5, as mechanism. Nothing comes off T-3.14's list, which only staging can prove.
  **Seen in Chrome 154 on 3 October 2026, all but Safari,** read from Chrome's own DevTools Protocol
  network events, values only as SHA-256 prefixes (the script stays in the session's scratchpad: a
  one-time observation, which T-3.13's E2E makes permanent):
  - `/login` with nobody signed in: refresh 401, no CORS error.
  - Sign-in from the console: verify set `refresh_local` (`HttpOnly; Secure; SameSite=lax;
    Path=/v1/auth`, no `Domain`) and `csrf_local` (`Secure; Path=/`), and Chrome kept both over
    plain `http://127.0.0.1`.
  - A reload of `/discover`: refresh 200, sending exactly those values and `X-CSRF` equal to the
    CSRF cookie; both cookies rotated; `/me` 200; the lock up (`test_woman` has a PIN).
  - The next reload's refresh sent the rotated value, not the first.
  - A wrong PIN: "Wrong PIN. 4 tries left."; the right one, 4829, opened it.
  - Two tabs reloaded together: both refreshes 200, the second carrying the first's rotation (the
    lock queued them), both tabs signed in; a third reload after them, 200.
  - "Forgot your PIN? Sign out": logout 204, both cookies cleared with `Max-Age=0` on their own
    paths, the jar empty, the tab on `/login`; the other tab's next reload, 401 and `/login`.
  - Safari's line is struck (above), and Safari isn't run locally (the founder, 3 October 2026):
    its case is HTTPS, unverified until T-3.14's staging check, which waits on P-0.13, the
    founder's Google Cloud billing account.
  Found on the way: the local dev database was two migrations behind (T-3.2's cap, T-3.3's
  `auth_time`), so OTP send answered 500 until `make migrate`; and that 500 reached Chrome as
  "Failed to fetch", not the API's envelope (P-61).
- [x] **Done when, on staging, after deploy, with nobody signed in:** `/login` at `https://staging.veloraapp.co.in` calls refresh with credentials and gets `401 AUTH_REQUIRED`, not a CORS error. It is the first credentialed request staging has served: the leg T-3.14 would otherwise have to debug at the same time as Firebase.
  **Proved, 3 October 2026,** on deploy run 37129957718 (`feed332`), in headless Chrome 154, read from
  its own network events: `/login` sent the credentialed refresh and got 401, with
  `Access-Control-Allow-Origin: https://staging.veloraapp.co.in` and
  `Access-Control-Allow-Credentials: true`; the same request from the page's console read the body,
  `AUTH_REQUIRED`. The control: a preflight from `https://evil.example` got 400 with no
  `Access-Control-Allow-Origin`, so the 401 isn't CORS letting everyone through.
- [x] **Commit:** `feat(web): auth session, refresh, route gates, pin lock [T-3.10]`

### T-3.11 · Web onboarding 1–7
- [x] **Needs:** T-3.10, T-3.7
- [x] **New dependencies, the first forms to use them, approved** (decision 1): web `react-hook-form` and `zod`, with `@hookform/resolvers` to join them, pinned exactly. Record them in `01-DECISIONS.md` under the next free number at install (rule 4). CLAUDE.md pins them, but nothing has installed them: T-2.3's waitlist form uses plain React state on purpose, because two form libraries for one email field would spend the landing page's performance score (98–100, T-2.1).
- [x] **The CSP's `'unsafe-inline'` stays** (D-059's amendment of 3 October 2026): write its reason in `security-headers.ts`'s comment. Its trigger, a screen first rendering another user's text, is D-059's to watch.
- [x] **Screens**, at D-080's URLs, built only from what 08-DESIGN's list of the prototype's errors leaves trusted:
  - phone and code at `/login`: the code in 6 boxes, from the new `OtpInput` primitive (08-DESIGN §4), with paste, `autocomplete="one-time-code"`, and a resend timer from `resend_after_s`;
  - birthday (D-079): a native date input, a confirm step, no age check in the browser, and a final screen after `UNDERAGE`;
  - gender, with the lock warning;
  - looking-for: seeking plus 1–3 intents, labelled from `en.ts` by id (P-26);
  - name, hometown and city;
  - username: a check 400 ms after typing stops, showing `<site>/@name` with the host from `site.ts`, never a hard-coded domain.
- [x] **The onboarding frame** (decision 5; T-3.10 and T-5.6 carry the same line): `src/components/onboarding/StepFrame`, from the prototype's `Step`: back arrow, 12-segment progress, title, body, footer, 520 px. It's for onboarding only; T-4.6 and T-4.7 reuse it. It holds T-3.10's quiet "Sign out". Back arrows follow D-080.
- [x] **Which path signs in** (D-081): Path B where `APP_ENV` is `local` or `ci`. On a Firebase build, until T-3.14, `/login` says sign-in isn't open yet and links to the waitlist. Remove "web" from `AUTH_PHONE_PROVIDER`'s row in 02-ARCHITECTURE §11.
- [x] **Each screen:**
  - submit is disabled until the input has the schema's shape, and nothing more (D-082);
  - server errors show inline, from `ApiError.code` via `en.ts`;
  - loading and error states (rule 14);
  - `ACCOUNT_BANNED`, `ACCOUNT_FROZEN` and `FORBIDDEN` at sign-in get one neutral line, "This account can't sign in.", with a link to `/contact`, which lists grievance@ (decision 16). P-51 may change it.
- [x] **Copy** (decision 4): every new string is drafted from wording already in `en.ts` (/terms, /privacy) and the decisions, and listed in this task's plan for the founder's approval.
  **Approved by the founder, 3 October 2026, with two changes,** T-3.12's strings included:
  - The PIN step said "You'll enter it each time you open {app}", which the lock doesn't do: it asks
    when a restored session opens and after 5 minutes hidden, never right after a sign-in by code.
    It now says exactly that, with the minutes read from the lock's own constant, so the two can't
    drift.
  - The waitlist box has two headings on D-081's flag (`signInOpen()`, which `/login` reads too):
    "{app} isn't open yet" while nobody can sign in anywhere, "Not in your city yet?" once someone
    can. Two different people; the second heading would tell the first it works elsewhere.
  - **One word departs from the founder's wording:** his subs said "Leave your number"; the
    waitlist form collects an email (T-2.3), so they say "Leave your email".
- [x] **No inline `style=`.** Production's CSP has no `style-src 'unsafe-inline'`, so a progress width or a counter set inline works under `next dev` and is blocked everywhere else (P-41's lesson). Use classes only.
- [x] The consent line naming Google moved to T-3.14 (D-081): on Path B, Google sends nothing.
- [x] **Proved, 3 October 2026:**
  - **Tests:** 31 vitest tests for the screens and 6 for `OtpInput`, and the suites pass in 8 shuffled
    orders (`--sequence.shuffle`).
  - **31 guards broken one at a time, each red, each restored by SHA-256:** a browser age check, a
    browser-computed age, no confirm step, "Change it" sending, the number in a URL (D-079, D-080);
    a Firebase build showing the form, staging signing in by code, any path value believed (D-081);
    a letters rule and a reserved-name list in the browser (D-082); a stale sign-in, `Me` uncached,
    tries left unsaid, no way to a person, under 18 not ending the session, a hard-coded domain, a
    check per keystroke, no lowercasing, an inline style, a back arrow on the birthday, the wrong
    back arrow on the name, +91 unstripped, a code offered at once, paste unspread, Backspace not
    going back, letters kept, the waitlist anchor gone, Send enabled early; and zod not `jitless`,
    its import unrestricted, `Me` stale at once.
  - **Two escaped at first and were fixed:** the number in the URL passed because jsdom keeps one
    URL per file, so an earlier test had already leaked it (each test now starts at `/` and asserts
    the digits are absent); and a paste into an empty box spreads without the paste handler, which
    matters only for a box already holding a digit (now tested).
  - **In Chrome 154 against a production build (`next start`, the strict CSP),** through the real
    screens: a new number signed in by code, then birthday, gender, looking-for, name and username,
    arriving at `/onboarding/about`. No URL held the number; the username's page read
    `127.0.0.1:3000/@…`, the build's own host. **The first run found a CSP violation,
    `script-src eval`: zod 4's `new Function` probe,** reported by the browser though zod catches
    the throw (zod's own comment says so). Fixed by `jitless`, set once in `src/lib/zod.ts`, with
    ESLint refusing `"zod"` anywhere else; the rerun had none, and a planted inline style was
    caught, so the detector is live. The same run showed `/me` fetched again on every step, 7 extra
    round trips (1.8 to 3 s each on staging today, P-49); `useMe` now keeps a written `Me` fresh for
    60 s (`ME_FRESH_FOR_MS`, a Checklist A exception like T-3.10's), and the rerun made none.
  - **D-081 on staging,** deploy run 37131611191 (`7dcd832`), in Chrome: `/login` says "Sign-in
    isn't open yet", with no phone input and no API call but the restore attempt; "Join the
    waitlist" lands on `/#waitlist`; no CSP violation. **Seen there:** the box it lands on is headed
    "Not in your city yet?", written for people outside the launch city, not for someone who can't
    sign in anywhere. Raised with the copy review.
- [x] **Commit:** `feat(web): onboarding steps 1-7 [T-3.11]`

### T-3.12 · Web onboarding 8, 10, 11
- [x] **Needs:** T-3.11, T-3.8, T-3.9
- [x] About (40–300 counter), interests (exactly 5, labelled from `en.ts` by id, P-26), PIN (set + confirm, skip, on T-3.10's `PinPad`). Photos (9) and selfie (12) come in Sprint 4: a placeholder in the onboarding frame that says "coming next", with its "Sign out".
- [x] **The PIN** (D-082): set, confirm, send. A refusal (D-069's weak PINs) returns to "set" with the server's reason; the web holds no copy of D-069's list. `/auth/pin/set` answers 204, so refetch `Me` after it.
- [x] Interests and PIN come after photos in the step order (D-068), so until T-4.3 a real user can't reach these two screens: test them by setting the step. Their URLs are D-080's.
- [x] **Proved, 3 October 2026:**
  - **Tests:** 13 more vitest tests (about, interests, the PIN, the coming-next frames), and the
    no-inline-style check over the new screens.
  - **13 guards broken one at a time, each red, each restored by SHA-256:** an easy-PIN list in the
    browser (D-082), no confirm, a mismatch sent anyway, `Me` not read afresh after the PIN, a sixth
    interest, the database's labels shown, a phone-number rule for about in the browser (D-082),
    about untrimmed, about sent under 40, no way out on the coming-next frames, the wrong back
    arrow, an inline style, a set PIN offered for change without the current one. **One escaped at
    first:** the PIN test began with no `Me` cached, unlike the app, so skipping the fresh read
    changed nothing; it now seeds the cache as the gate does, and goes red.
  - **In Chrome 154 against a production build (`next start`, the strict CSP),** all twelve
    screens: phone to username, then about, the photos frame (coming next, with "Sign out");
    then, with the local test account's step set to `interests` directly in the dev database
    (nobody passes photos before T-4.3), interests and the PIN: 1234 sent and refused by the
    server, shown as "That PIN is too easy to guess", then 4829, arriving at the selfie frame.
    No URL held the number; no CSP violation; a planted inline style was caught, so the detector
    was live.
- [x] **Commit:** `feat(web): onboarding about, interests, pin [T-3.12]`

### T-3.14 · Firebase phone sign-in (launch path)
- [x] **Needs:** T-3.3, T-3.10 (it restores the session on reload, which the Done-when checks), T-3.11 (its phone and OTP screens, which this task's web step puts Firebase on), and **P-0.13** (the Google billing account, verified: Firebase's Blaze plan bills to it)
  **And the two authorised domains, added by the founder** in Firebase's console (Authentication,
  Settings, Authorised domains) for project `velora-ic`: `staging.veloraapp.co.in` and
  `veloraapp.co.in`. Nothing else: no Vercel preview domain, since neither Vercel project is
  connected to Git (T-1.22, `infra/PRODUCTION.md`); not `www`, which 308s to the apex; not
  `127.0.0.1`, since local builds sign in by Path B (D-081). The list held only `localhost` and
  the two `firebaseapp` defaults. **Done, 3 October 2026 (the founder):** both are in.
  **And the web app registered in `velora-ic`, with its config:** the build starts then.
  **Done, 3 October 2026 (the founder):** registered. The founder holds the config and gives it to
  the build session directly (4 October 2026); it goes in the repo's env for the web, public by
  design (Keys, below).
- [x] **Not in T-3.10 to T-3.13's batch** (planned 3 October 2026): P-0.13's account didn't exist yet. When this task starts, switch D-081's Firebase builds from "sign-in isn't open yet" to the Firebase flow: make `signInOpen()` (`web/src/lib/sign-in-path.ts`) true for `firebase`, which moves `/login` and the landing page's waitlist heading together.
- [x] **New dependencies (approved, recorded in D-035):** api `firebase-admin`; web `firebase`.
  **As built (D-085; approved by the advisor directing T-3.14, relayed by the founder, 4 October
  2026):** web `firebase` 12.19.0, pinned
  exactly; api `firebase-admin` not added. PyJWT and httpx check the token, as Google documents for
  third-party JWT libraries, with no new API dependency.
- [x] **Keys (the founder, 3 October 2026):** "the Firebase web config is public by design and
  belongs in the repo's env for the web. Any service account JSON is a secret and goes in the
  password manager and the host's secrets, never in the repo. Say which of the two you need and
  I'll handle it; don't ask me to paste either into chat." This task expects to need no service
  account: verifying an ID token takes only the project ID and Google's public keys, and it is
  P-39's deletes that would need admin rights. `FIREBASE_SERVICE_ACCOUNT_JSON` ("token
  verification") came out of 02-ARCHITECTURE §11, `api/.env.example` and `config.py` on 3 October
  2026, at the founder's direction: a document that says a secret is needed when it isn't gets the
  secret created and stored, and then a key that never had to exist is guarded. If this task finds
  one is needed after all, it says why before asking.
- [x] Firebase console: project created, Phone provider enabled, authorised domains =
  `veloraapp.co.in` + `staging.veloraapp.co.in` (the Done-when signs in there; on the Needs line),
  billing alert set at a fixed rupee amount. **App Check is P-68, the very next task after this
  one** (the founder, 4 October 2026): this task's first staging deploy puts the web config in a
  public bundle, on a hostname in public certificate logs, and P-68 closes what that opens.
  **Done by the founder, 3 October 2026:** project `velora-ic` (no Google Analytics, no Gemini in
  Firebase); Phone sign-in enabled; SMS region policy "Allow", India (IN) only; Blaze linked to a
  billing account; later the same day, the two authorised domains.
  **Read in the console by the founder, 4 October 2026** (the clicks and the readings his): plain
  Firebase Authentication, not Identity Platform; no Google Analytics and no Gemini in Firebase;
  Phone sign-in enabled; no test phone numbers; SMS region policy "Allow", India (IN) only; Blaze
  active through the Google Cloud trial, ₹28,796 of credit until 2 January 2027; web app
  `velora-web` registered; the budget alert set (its Done-when, below). The authorised domains,
  exactly as they stand: `localhost`, `velora-ic.firebaseapp.com`, `velora-ic.web.app`,
  `staging.veloraapp.co.in` and `veloraapp.co.in`. `localhost` is Firebase's default and can't
  host phone sign-in ("localhost is not allowed as a hosted domain for the purposes of phone
  auth", Firebase's web phone-auth page, read 4 October 2026); `127.0.0.1`, where local builds
  run, isn't listed. **The recommendation behind them was the advisor's** (Claude, in a separate
  chat): no test numbers, India only, Analytics and Gemini off, and both Savings boxes cleared.
  The first plan text also listed a Vercel preview and `localhost`: neither is needed (Needs
  line), and a daily SMS quota cap, which isn't a setting at all (below).
  **No console field caps SMS** (4 October 2026, at the founder's direction; the first text
  assumed one). What bounds an SMS flood here (P-0.18 has the detail): App Check (P-68, not yet);
  the region policy, India only; and Firebase's fixed limits for plain Firebase Authentication,
  3,000 SMS a day and 900 a minute per project and 500 an hour per IP, **a ceiling inherited, not
  one we chose, that holds only while `velora-ic` stays on plain Firebase Authentication,** as it
  is. Our server's limits don't: the browser asks Google for the SMS (D-035), and this task's
  throttle on `/v1/auth/firebase` counts token exchanges, not sends. **The founder deliberately
  didn't take the Identity Platform upgrade, and this task doesn't either,** even where the
  console offers a feature behind it: the upgrade removes the daily ceiling (P-0.18).
- [x] **A number outside India is refused by Firebase itself,** under that region policy, before any
  of our code runs. What the person sees then is a case this task handles and tests, not an
  accident. (The phone screen fixes +91, so it takes a pasted or edited number to get there.)
  **What Firebase answers** (4 October 2026, Claude, one REST call for the fictional
  `+1 650-555-0100`, approved in the advisor's review, relayed by the founder): `400`, "OPERATION_NOT_ALLOWED : SMS unable to be
  sent until this region enabled by the app developer.", before any reCAPTCHA check, so no SMS
  could go. The SDK turns it into `auth/operation-not-allowed` (its default mapping, firebase
  12.19.0), and the screen says "Only Indian mobile numbers can sign in for now." (`errorCopy.ts`,
  tested): the number, not them. The same code would come back if phone sign-in were switched off
  in the console, and that line would then be wrong. P-70 is what someone with a foreign number
  actually meets on the screen, which this refusal never reaches.
- [x] **One project, `velora-ic`, for staging and production, and never a Firebase test number in
  it** (D-065, decided by the founder on 3 October 2026): "Not one, not temporarily." A test
  number is a fixed phone and a fixed code that sign in without an SMS. In a project production
  uses, that is a permanent sign-in bypass for anyone who learns the pair. It has the shape of
  T-3.13's `/v1/test/sms/last-code`, proved gated in code; a test number would rebuild it by hand
  in the console, with no gate. So the Done-when signs in with the founder's own phone. A Firebase
  project of staging's own, with its own test numbers, is P-66.
- [x] **Staging sign-ins land in the same Firebase user pool as production** (the founder,
  3 October 2026). That's acceptable while there are no real users, and it is not acceptable
  after launch. Sharing one project means: a real person can sign in to staging with their own
  number, since staging texts whoever production texts, and their number then sits in staging's
  database; a token minted on either site's page is accepted by both APIs, each checking reuse
  only in its own Redis; and staging's sign-ins draw on the same SMS credit and project limits
  that real people's sign-ins need. P-66 ends it. It is on REL-1's Needs line if REL-1's tag
  includes this task, since that tag is what makes real users possible, and on T-9.15's
  regardless.
- [x] `POST /v1/auth/firebase {id_token}`: verify signature and `aud`/`iss`/`exp` against Google's
  public keys (cached); require `phone_number` and `firebase.sign_in_provider == "phone"`;
  reject non-`+91` → `PHONE_NOT_SUPPORTED`; reject a reused `jti` (Redis until expiry) →
  `FIREBASE_TOKEN_INVALID`; throttle 10/IP/hour and 5/phone/hour.
  **As built (D-085):** a Firebase ID token has no `jti` (Google's list of its claims), so used
  once keys on the token's SHA-256; and a sign-in over 5 minutes old is refused too.
- [x] Then reuse the exact same service as T-3.3: banned check → find-or-create user + profile +
  wallet + prefs → session + cookies → `{access_token, user}`.
- [x] The phone screen shows a consent line naming Google before `signInWithPhoneNumber` runs:
  Google's Firebase sends the code, processes the number in the United States and keeps it for abuse
  prevention (D-048, `/privacy`). Firebase asks apps to get this consent. It moved here from T-3.11
  (D-081): on Path B it would be false. Deleting the Firebase user after sign-in is P-39, not this
  task.
- [x] Web: Firebase JS SDK on the phone screen (invisible reCAPTCHA), `signInWithPhoneNumber`,
  6-digit code box (Path B's codes are 6 digits too since D-066, so the OTP screen is the same
  on both paths), resend cooldown, friendly copy for `auth/too-many-requests`,
  `auth/invalid-phone-number`, `auth/code-expired`.
- [x] Sign the user out of Firebase immediately after the exchange — we keep our own session.
- [x] **Widen the CSP here, deliberately (D-059).** T-2.5's policy allows no outside script, connect or frame host, so Firebase's SDK and its reCAPTCHA check fail at sign-in until this task adds exactly the Google hosts Firebase documents (`script-src`, `connect-src`, `frame-src`), each with its reason in `web/src/lib/security-headers.ts`. A CSP error at sign-in is this line, not a Firebase bug.
  **As built (D-085):** Firebase publishes no CSP for Auth, so the hosts are reCAPTCHA's own list
  (its FAQ) and the SDK's two API hosts, on Firebase builds only. **Checked before deploy, locally**
  (4 October 2026, Claude): a production build with `APP_ENV=staging` served the policy
  `security-headers.ts` builds for it, and `/login` in Playwright's Chromium 153 and Firefox 155
  rendered reCAPTCHA (its badge placed and styled) with no `securitypolicyviolation` event, while a
  deliberate one, an image from example.com, was caught, so the listener was live. No SMS could
  go: `127.0.0.1` isn't an authorised domain. The SDK (131 KB) loaded on `/login` only, not on `/`
  or `/privacy`. Those scripts ran from Claude's scratchpad and aren't committed; staging's
  sign-ins below are the proof of record.
- [x] **Seeded numbers and test numbers (D-064, D-065).** Firebase sends its code from the
  browser, so no server guard can stop a text to a seeded number (`+91 90000 00xxx`, T-1.15)
  when the local web runs on Firebase. Locally, seeded users sign in on
  `AUTH_PHONE_PROVIDER=fake`; this task decides how the local web keeps a seeded number from
  reaching Firebase. A Firebase test number signs anyone in as that number wherever its project's
  tokens are accepted, so it never goes in a project production uses.
  **Decided (D-085; approved by the advisor, relayed by the founder, 4 October 2026):** local and
  ci builds get no Firebase
  config at all (`web/src/lib/firebase-config.ts`, by `APP_ENV`) and sign in by Path B (D-081), so
  nothing built on a dev machine reaches Firebase, "structural rather than a rule someone has to
  remember" (the advisor, relayed by the founder). Behind that, Firebase's own: `127.0.0.1` isn't an authorised domain, and
  `localhost`, which is, can't host phone sign-in (its docs; not proved by effect, which would mean
  trying a real send).
- [x] Tests: forged token rejected; expired rejected; reused token rejected; non-Indian number
  rejected; banned phone rejected; a valid token creates exactly one user.
- [x] **Done when, before any real SMS path ships: a budget alert is set** on the billing account
  Blaze bills to, at a fixed rupee amount (the founder, 3 October 2026). No real SMS path ships
  without one: an SMS sent from the browser is outside our server's limits (D-035). **Set it on
  cost before credits** (clear the budget's Promotions box): by default a budget subtracts
  promotional credits, so while the account is on its free trial (P-0.13, P-0.18) it sees ₹0 and
  can never fire (Google's budgets page, read 3 October 2026). A budget only alerts; it never caps.
  **Set by the founder, 4 October 2026,** read in the console: ₹500 a month, alerts at 50, 90 and
  100% of actual cost, email to billing admins, both Savings boxes cleared so it tracks cost before
  credits. Claude can't read it back: this machine has no Google Cloud credentials.
- [ ] **Done when:** on staging, sign in at `https://staging.veloraapp.co.in` with the founder's
  own phone, by real SMS (D-065: no test number, as decided on 3 October 2026), once the budget
  alert above is set. Then reload, and the session is still there, restored by `/auth/refresh`.
  This is the first real sign-in staging can do (D-045 allows only real providers there), so it is
  the first proof that P-33's subdomains carry the refresh cookie. Until it passes, P-33 is
  believed, not proven. **One sign-in per browser:** item 3 below needs Chrome, Firefox and
  Safari, so the check sends three real SMS to one phone, inside this task's own limit of 5 an
  hour per phone. Log out last in each browser, so no step needs another sign-in.
- [ ] **This is the first time any of Sprint 3's session machinery runs outside a test process.**
  T-3.3's cookies, T-3.4's rotation and logout, T-3.5's `current_user` and P-42's headers have been
  proved only in-process against the local stack: staging runs `firebase`, so Path B answers 404
  there, and nothing has signed in on it. So T-3.14 is not just Firebase sign-in, and its Done-when
  must prove each of these in a real browser against staging, observed on the wire (devtools'
  network and cookie panes), never inferred from a green test:
  1. **The refresh cookie crosses P-33's subdomains.** Set by `api.staging.veloraapp.co.in` as
     `refresh_staging` with no `Domain` (host-only, D-054), kept by the browser, and sent back on
     `/v1/auth/refresh` when the page at `staging.veloraapp.co.in` calls it with
     `credentials: "include"`: a reload restores the session.
  2. **The CSRF cookie's `Domain` works.** `csrf_staging`, scoped to `staging.veloraapp.co.in`
     (D-055), is readable by the page there and sent back as `X-CSRF`, and refresh accepts it.
  3. **`Secure` cookies are kept by real browsers over HTTPS**: Chrome, Firefox and Safari. Safari
     can't be tested locally (D-067, CLAUDE.md), so staging is its only proof.
     **Safari over HTTPS is unverified until this check runs** (the founder, 3 October 2026).
     "Staging covers Safari" is a promise until then, not coverage. With a PWA first, every iPhone
     user is a Safari user.
  4. **Rotation in the browser:** a refresh replaces both cookies, and the next refresh uses the
     new values, not the old ones.
  5. **Logout clears both cookies in the browser** (the clearing cookies must match each cookie's
     path and domain, or the browser keeps the originals), and a reload lands on `/login`.
  6. **Two tabs reloaded together both stay signed in** (T-3.10's Web Locks, D-067's 10-second
     grace), and neither signs the other out.
  7. **P-42's headers on a signed-in response:** `Cache-Control: no-store` and
     `X-Content-Type-Options: nosniff` on `/v1/me`.
  And expect it slow while the API is in Singapore: about 4 s for a first sign-in, about 3 s per
  `/me`, measured as round trips (P-49, P-50). Slow is not failed; record the times beside the
  result.
  **Already proved locally, as mechanism:** T-3.10 and T-3.13 prove items 4 and 6, and parts of 1,
  3 and 5, against the local stack. That takes nothing off this list, whose proof is staging's, but
  if staging fails, the platform is the suspect, not the code.
- [x] ~~**One Playwright run against staging** with the test number, T-3.13's journeys on the real
  path. It moved here from T-3.13 (decision 18 of T-3.10 to T-3.13's plan): it needs this task.~~
  **Moved out, 3 October 2026, to P-67, whose Needs line carries P-66:** it needs a test number,
  and none goes in `velora-ic` (D-065, as the founder decided).
- [x] **Commit:** `feat(auth): firebase phone sign-in [T-3.14]`

### T-3.13 · E2E signup
- [x] **Needs:** T-3.12. **Not T-3.14:** the one run on staging's Firebase path moved there (decision 18), so this task closes without P-0.13.
- [x] **New dependency, approved** (decision 1): web `@playwright/test`, a devDependency pinned exactly, with Playwright's Chromium. Record it in `01-DECISIONS.md` under the next free number at install.
- [x] **Journeys,** Chromium at 390 × 844 and 1280 × 800 (06-TESTING), against the local stack with `AUTH_PHONE_PROVIDER=fake`:
  - a new man reaches the photos step;
  - under 18 is refused, and the same number tried again gets a normal answer and no code (D-072, D-073: on Path B a ban is silent);
  - T-3.10's mechanism, so it runs on every push: a reload restores the session, a refresh rotates both cookies, two pages reloaded together both stay signed in, and sign-out clears both cookies.
- [x] **Where it runs** (decision 19):
  - its own database and Redis database, taken as a P-55 slot, so an E2E run and any number of pytest runs never meet (the plan first said a `velora_e2e` made by `make infra-up`; the slot does the same and frees itself);
  - a production build (`next build && next start`, `APP_ENV=local`), so the strict CSP is the one tested;
  - ports apart from `make dev`'s;
  - any CSP violation in the browser console fails the run.
- [x] **The test-only OTP endpoint** (decision 20) answers with the last code the fake SMS provider sent to a number, which is what the phone would have received. It is:
  - served only where `ENV` is `local` and `AUTH_PHONE_PROVIDER` is `fake`, an allowlist;
  - a POST with the number in the body, because the request logger binds the path and uvicorn logs path and query;
  - `include_in_schema=False`, so `make types` is the same everywhere;
  - listed in 04-API under a local-only heading;
  - covered by a rule-15 test through `captured_logs`.
- [x] **CI** (decision 21): a new job on every push. `/done`'s gate (D-044) and the release gate (D-075) then wait on it.
- [x] **Nothing kept from CI** (decision 22): no traces, videos or screenshots. A trace records request and response bodies (numbers, codes, access tokens), and a screenshot of the phone screen shows the number. Failures report through their assertion messages.
- [x] **The shuffle plugin** (decision 23): commit P-48's seeded shuffle option to `api/tests/conftest.py`, opt-in, with no new dependency, unless T-5.1 already has. Run the whole API suite in 8 seeded orders before `/done`, with the seeds in this task's record. CI stays in file order. A fix whose mechanism isn't in the repo is not a fix (CLAUDE.md).
- [x] **Firefox** (decision 2): run T-3.10's local browser checks once in Playwright's Firefox, locally, not in CI, and put what it shows into CLAUDE.md's local sign-in paragraph, dated.
- [x] **06-TESTING's E2E section** says what runs: every push, not "every PR touching `web/`" (D-044 has no pull requests); the nightly staging run waits for T-3.14; J1's "→ discover" is T-4.9's, since photos is as far as this task gets.
- [x] **The shuffle plugin** came from T-5.1, which committed it first (`--shuffle-seed N` in
  `api/tests/conftest.py`), as both tasks' lines allowed; this task used it.
- [x] **Proved, 3 October 2026:**
  - **E2E:** 10 journeys (J1, J3 and T-3.10's reload, rotation, two tabs and sign-out, at 390 × 844
    and 1280 × 800) pass in 1.8 minutes, the production build included; and the same five in
    Playwright's own Firefox 155 build, by hand.
  - **Two of the E2E's own checks were wrong at first, and fixed:** Playwright's `cookies(url)`
    withholds `Secure` cookies from an `http://` URL, so the cookie read was always empty and the
    sign-out test's "both cookies gone" could never fail (it now reads the whole jar); and J3's
    alert matched Next's route announcer and the toast region too.
  - **Six breaks of what the E2E guards, each red:** an inline style, zod's eval probe, the number
    in a URL, no cookies sent to `/v1/auth`, a sign-out the API never hears, and the under-18
    ending gone. **Five of the test-only endpoint's:** served in any `ENV`, served beside a real
    SMS provider, in the OpenAPI schema, the code logged, the number not normalised. Each restored
    by SHA-256. **Then, at the founder's question:** the gate broken into two blacklists. "Not
    staging or production" (today's names) passed staging's and production's cases and went red
    only on `preview` and `env-nobody-has-named-2031`, a name listed nowhere; "not production" also
    failed staging's. The allowlist refuses all three.
  - **The API suite in 8 shuffled orders** (seeds 11 to 18): 1,192 passed each, the new rule-15
    test among them; a seed's order differs from file order (seen, not assumed).
  - **CI's `e2e` job** runs after `api` and `web`, uploads nothing, and is proved by its first run
    on this commit, the only place it can be.
- [x] **Commit:** `test(e2e): signup flow [T-3.13]`

---

# Sprint 4 — Photos and verification (weeks 6–7)

### T-4.1 · Storage provider
- [x] **Needs:** T-1.21, T-1.2, and **R2 enabled on the Cloudflare account, with the staging buckets
  `velora-staging-public` and `velora-staging-private`** (`infra/STAGING.md` §3) — not enabled yet
  (T-1.22); and **P-49**: the API moves to Mumbai before Sprint 4, so T-4.4's worker is built once,
  on the new host (directed by the advisor on 3 October 2026; the founder decides). With R2
  enabled, also create **production's buckets, `velora-prod-public` and `velora-prod-private`**
  (`infra/PRODUCTION.md` §3, moved from T-2.6).
  **R2 is in, set up by the founder on 4 October 2026:** the four buckets, the two custom domains,
  a token per environment scoped to its own pair, and staging's two Fly secrets (`infra/STAGING.md`
  §3, `infra/PRODUCTION.md` §3). **P-49 is waived for this task:** the go-ahead in the founder's
  message of 4 October 2026 came with P-49 unticked. Its reason is T-4.4's worker, and nothing here
  is tied to where the API runs; whether it moves to T-4.4's deploy step is still open (D2 of
  Sprint 4's plan).
- [x] Real `StorageProvider` on aioboto3 (works for R2 and the local S3, SeaweedFS since D-086): `presign_put(bucket, key, content_type, max_bytes, ttl=300)`, `presign_get(bucket, key, ttl=600)`, `get_bytes`, `put_bytes`, `copy`, `delete`.
  Plus `head()`, size and type: a presigned PUT can't cap its own size, so T-4.2 checks the upload
  after it arrives. The Content-Type is signed into the PUT. One client per app, closed with it.
- [x] Key helpers: `raw/{user_id}/{photo_id}`, `p/{photo_id}.jpg`, `voice/{thread_id}/{message_id}.webm`, `album/{photo_id}/{viewer_id}.jpg`.
  Built from UUIDs only, checked at runtime too, so nothing a user types shapes a key
  (`app/core/storage_keys.py`).
- [x] **Storage goes to R2's own endpoint everywhere but local.** `R2_ENDPOINT_URL` (the local S3) is
  refused anywhere `ENV` isn't local, an allowlist (rule 16), in `Settings` and again where the
  endpoint is chosen; with `s3`, every R2 setting is required and named at startup, and
  `PUBLIC_CDN_URL` is `https://` outside local.
- [x] **The custom domains' minimum TLS is 1.2: a decision, not a default** (set by the founder, 4
  October 2026, for this reason): 1.0 is broken, and these serve users' photos; 1.3 would have
  excluded older Android phones that only speak 1.2. Someone could undo it without realising, so it
  is written here and in both runbooks' §3. Read from outside by Claude the same day, by the
  server's own answer: on `cdn.staging.veloraapp.co.in` and `cdn.veloraapp.co.in`, TLS 1.0 and 1.1
  refused with a protocol-version alert, 1.2 and 1.3 accepted.
- [x] **Done when, on staging** (D14 of Sprint 4's plan): `app/tools/storage_probe`, run inside
  staging's machine with its own keys, passes every step, the scope refusals on production's
  buckets included; quoted in the docs commit after `/done`, with the deploy run it ran on.
  **Passed, 4 October 2026,** on `dd30b29` after deploy run 37198554076 (every job green, smoke
  included), by `flyctl ssh console -a velora-api-staging` running
  `python -m app.tools.storage_probe --refused-bucket velora-prod-public --refused-bucket
  velora-prod-private`, exit 0, every line `ok`: for each bucket, a presigned PUT stores the object,
  the same PUT with another Content-Type is refused, `head()` reads its size and type, a presigned
  GET and `get_bytes()` return the bytes; `put_bytes()` stores in the private bucket; `copy()`
  from private to public, and the copy served at `PUBLIC_CDN_URL`; a private object's key not
  served there; an absent key a 404 in these buckets, and these keys refused on
  `velora-prod-public` and `velora-prod-private`; every probe object deleted. **The Fly secrets
  are the Keychain's values:** each compared by SHA-256, first 8 hex characters, computed on the
  machine and from the Keychain, never moved: `R2_ACCESS_KEY_ID` `ac6d5e3f` and
  `R2_SECRET_ACCESS_KEY` `1188b869` in both places.
- [x] **Commit:** `feat(storage): r2 presigned urls [T-4.1]`

### T-4.2 · Upload URL and complete
- [x] **Needs:** T-4.1, T-3.5, and **P-54's row half** (D-078: an under-18 refusal deletes every
  table the app may delete from; this task adds the files)
- [x] `POST /photos/upload-url {kind, position?, content_type}` — public max 6 (positions 0–5), private max 6, selfie 1 active. Creates `photos` row `pending`, returns presigned PUT (image/jpeg|png|webp, ≤ 8 MB; no HEIC, D-089).
- [x] `POST /photos/{id}/complete` — object exists and size ok → enqueue `moderate_photo` (public/private) or leave for `verify_selfie` (selfie).
- [x] **The bytes decide, not the declared type (D-089).** `complete` reads the object's first bytes:
  a JPEG, PNG or WebP goes on, as what its bytes say; anything else is rejected, its object deleted,
  and the error says what to do: "JPEG, PNG or WebP". The declared `content_type` is signed into the
  PUT and used for a clearer message, never to decide. Proved by a test that fails if the code
  trusts the header: bytes of a PNG declared `image/jpeg` handled as a PNG, and bytes of something
  else declared `image/jpeg` refused.
- [x] **D-078 (P-54's file half, built here), in D-090's order:** an under-18 refusal deletes `photos`
  rows and the files behind them. The keys are read in the deleting transaction before the rows go;
  the deletion job is queued **before** the commit (D-090 supersedes D-078's "after"), 60 seconds
  out, and deletes only once the user is gone, checking again at 5 minutes. The object goes; the
  refusal's record, `banned_identities`, stays (rule 12 applies to the record, not the image). Each
  deletion is verified by reading the object back as gone, a check tested to fail against an object
  that still exists. The log line names the `banned_identities` row's id, never a number, a key or a
  signed URL (rule 15); a final failure logs at error level. Until T-4.4's worker runs, the job
  waits in Redis; T-4.4 registers it. Any file this task stores behind a user row joins the list,
  with a test. The upload URL still waits for its step (D-068).
- [x] **Commit:** `feat(photos): upload url and completion [T-4.2]`

### T-4.3 · Manage photos
- [ ] **Needs:** T-4.2
- [ ] `GET /me/photos`, `PATCH /me/photos/order`, `DELETE /photos/{id}` (soft: status `rejected` + reason `user_deleted`, object removed from public bucket).
- [ ] Onboarding `photos` step completes when ≥ 1 public photo is `approved` **or** `pending` (pending ones stay invisible to others until approved).
- [ ] **Commit:** `feat(photos): list, reorder, delete [T-4.3]`

### T-4.4 · Moderation worker
- [ ] **Needs:** T-4.2, T-1.15, and a **Sightengine account with API keys** — created by the founder on 4 October 2026, free plan, its keys in the Keychain (P-0.6)
- [ ] ARQ worker bootstrap (`workers/main.py`) + `make worker`.
- [ ] **The worker polls every 10 seconds** (D-091), a setting: on Upstash's Free plan that is
  260,640 commands a month idle, 52% of the 500K, where ARQ's default 0.5 seconds would be over
  five million.
- [ ] Deploy the worker to Fly staging (moved from T-1.22): `infra/fly.worker.toml` beside
  `fly.api.toml`, the same image and least-privilege role, deployed by `deploy.yml` after the API.
  Add its pool to the connection budget in `infra/STAGING.md`. It shares `Settings`, so it needs
  the API's four keys as secrets, the same values (from the Keychain, `infra/STAGING.md`):
  otherwise it can't read the numbers or hashes the API wrote, or doesn't start (D-060, D-061).
- [ ] `moderate_photo(photo_id)`: fetch raw → Pillow open (reject if not an image) → `ImageOps.exif_transpose` → resize longest side 1600 → save JPEG q85 **without EXIF** → `ModerationProvider.check()` → approve (write public copy for `public` kind) or reject with reason (`nudity`, `minor_suspected`, `no_face`, `text_overlay`, `other`). `minor_suspected` also opens an internal report.
- [ ] Idempotent: re-running on an approved photo does nothing.
- [ ] **Sightengine keeps nothing by default, and this task stays on that default.** There is no
  setting to turn on: deleting is Sightengine's default, which `/privacy`'s "deleted there after the
  check" (D-048) rests on. Its FAQ, "What happens to our images, videos and audio files after
  processing?", at https://sightengine.com/faq/data-retention-after-processing, read by Claude on
  4 October 2026 from the page itself, word for word:

  > By default, images, videos and audios are deleted after processing. You can request a change
  > to this default policy to suit your needs.
  > We only keep a file when you use a feature that stores it:
  > - you send it for human review (hybrid moderation workflow)
  > - you submit it to the Feedback API
  > - you add it to a near-duplicate list\* or upload it with the Upload API (deleted after 14 days)
  > - you redact a video: the redacted video is kept so you can download it (deleted after 3 months)
  >
  > \* Lists can be set to keep only fingerprints. The original files are then deleted, but the
  > list can't be upgraded to newer fingerprint versions.

  **The constraint: we use the plain image moderation API only,** none of those four features.
  **Turning on hybrid review or the Feedback API makes /privacy inaccurate the same day, so either
  is a decision that changes a published page, not a tuning knob someone enables for better
  accuracy.** The same holds for the Upload API and near-duplicate lists. And the retention policy
  is configurable on request, so "default" is a state we must not drift out of, not a guarantee:
  no one asks Sightengine to change it without the same decision. Found by the advisor (Claude, in
  a separate chat), relayed by the founder, 4 October 2026, answering D13 of Sprint 4's plan; the
  quote checked against the page by Claude the same day. P-71 carries the same constraint, beside
  `/privacy`'s other processors.
- [ ] Tests with the fake provider for approve and each reject path; test that output has no EXIF.
- [ ] Extend `make seed` (T-1.15): an approved public photo at position 0 for every seeded user past the photos step (everyone but the moderator, including the three women at the selfie step) — a placeholder from the prototype's `c1`/`c2` gradient, re-encoded like any upload and stored through `StorageProvider`. Re-running creates no duplicates.
- [ ] **Commit:** `feat(worker): photo moderation pipeline [T-4.4]`

### T-4.5 · Selfie verification
- [ ] **Needs:** T-4.4; D-088 (approved by the founder, 4 October 2026: the model and
  `opencv-python-headless`); **the measurement set** (below), which the founder gathers; and **the
  founder's answer on how `verify_selfie` avoids D-091's 10-second pickup**, since a woman waits on
  its result: this task proposes. No third party matches faces (D-087). Liveness isn't here: it is
  T-4.11.
- [ ] **No pose** (the founder, 4 October 2026: liveness is T-4.11's, and the pose challenge is
  rejected). `POST /verification/challenge` and the `challenge` column (`text not null`, "the random
  pose asked for", 03-SCHEMA) were for a pose: this task's plan says what they become, without a
  migration if it can, and 04-API changes with it. `POST /verification/{id}/submit {photo_id}` →
  enqueue `verify_selfie`.
- [ ] `verify_selfie`: re-encode; `FaceMatchProvider.compare(selfie, approved_public_photos)` on the
  worker (D-088): YuNet finds exactly one face, SFace's cosine similarity against each approved
  public photo, the best one counted; at or above the threshold (below) → `approved`,
  `users.is_verified = true`; else `rejected` with reason. Max 5 attempts / day. (The plan's first
  "similarity ≥ 85" was the dropped vendor's 0–100 scale; SFace has none, and the number comes from the
  measurement below.)
- [ ] **T-4.5 ships without liveness, and claims nothing it doesn't do** (the founder, 4 October
  2026; liveness is T-4.11). Face matching is a real check: it proves the selfie matches the profile
  photos. It does not prove a live person was in front of the camera, and we must not claim it does.
  **The hard constraint:** nothing in `/privacy`, the UI copy or any badge may say or imply that we
  confirm a real person, a live person, or that someone "is who they say they are". Describe exactly
  what we do: the selfie is compared with the profile photos. A word that promises more than face
  matching delivers is wrong, the way the Sightengine retention wording would have been.
  **Already in `web/src/i18n/en.ts` (read 4 October 2026), each rewritten here or shown to the
  founder before this task ships:** `/privacy`'s "Your selfie, to check that you're really you.";
  the landing page's "Verified, moderated" and "Selfie verification, photo checks, and reports that
  actually remove people."; the badge, `verified: "Verified"`; and `/terms`' "Women verify with a
  selfie before their profile goes live". (The code screen's "Verify" is the sign-in code's, not
  this.)
- [ ] **Measure the worker's peak memory on the actual Fly machine** (D-088's first condition), with
  face matching loaded, beside this Mac's 290 to 330 MB; the 1 GB size is locked on that number.
- [ ] **Accuracy is ours: how it's measured** (D-088; at the founder's direction, 4 October 2026:
  "there is no longer a vendor to blame when it is wrong").
  - **A right match:** the same person, accepted. **A wrong match:** a different person accepted,
    a false accept: someone verified behind a face that isn't theirs, which is what a catfish
    needs, so it is the error that matters most. **A wrong refusal:** the same person refused, a
    false reject: friction for anyone, and for a woman a profile that can't go live.
  - **The measurement set, never users' data:** people who agree in writing, the founder and
    volunteers, each giving profile-style photos and selfies taken the way T-4.7 takes them,
    across phones, light and angles. At least 50 people with 5 selfies each, spread across the
    people the app is for (women and men, skin tones, glasses, beards, a dupatta or a turban),
    since the model learned mostly from other faces. Every pair of two different people is an
    impostor pair. Stored privately, used for nothing else, deleted when the founder says.
  - **Measured as `verify_selfie` decides:** each selfie against all of one person's photos, the
    best match counted, so the threshold is calibrated for the decision actually made, not for
    single pairs.
  - **The threshold it starts at:** OpenCV's published 0.363 cosine, calibrated on LFW
    (celebrities' photos), only while building on the fake and the set. **This task's real step
    replaces it:** the lowest threshold at which at most 1 in 1,000 impostor pairs is accepted,
    reported with the false-reject rate there. If that rate is above 5%, stop and tell the founder
    before anything ships.
  - **After launch:** every verification records its similarity and outcome, numbers only, never
    an image (rule 15). A refused woman passing on a retry is the false-reject signal; a report of
    a fake profile among verified users the false-accept one. Reviewed monthly until T-9.5's
    moderators can look at disputed pairs.
- [ ] Selfies are never public and never shown to other users.
- [ ] Extend `make seed` (T-1.15): an approved verification row, with a placeholder selfie in the private bucket, for every seeded user marked verified — 15: the test woman, and the prototype's 14 `v` profiles (7 women, 7 men). Ishita, Riya and Pooja stop at the selfie step, unverified, with no row: they're who this task verifies against (the advisor directing T-1.15, Claude in a separate chat, 3 October 2026).
- [ ] **D-078 (P-54):** an under-18 refusal deletes `verifications` rows and the selfies behind them,
  keys read in the deleting transaction before the rows go. Any file this task stores behind a user
  row joins that list, with a test. The challenge still waits for the selfie step (D-068).
- [ ] **Commit:** `feat(verification): selfie challenge and face match [T-4.5]`

### T-4.6 · Web photos step
- [ ] **Needs:** T-4.3, T-3.12
- [ ] 6-slot grid; tap empty slot → file picker (`accept="image/*"`, `capture` not forced); client resize to ≤ 2000 px before upload (canvas) to save data; PUT to presigned URL with progress; states per slot: uploading %, checking, approved, rejected (with reason + retry). Drag to reorder (or up/down buttons on mobile).
- [ ] Women see the private-album note.
- [ ] Built in T-3.11's `StepFrame`, at D-080's `/onboarding/photos`, replacing T-3.12's placeholder.
- [ ] **Widen the CSP here (D-059):** `connect-src` for R2's upload endpoint (the presigned PUT), and `img-src` for `PUBLIC_CDN_URL` and `blob:` previews. Uploads and previews fail with a CSP error until then.
- [ ] **Done when, on a real iPhone, on this control (D-089):** iOS Safari's upload sends JPEG, not
  HEIC, read from what the API received (its bytes), never reasoned about. If it sends HEIC, "no
  HEIC" breaks every iPhone sign-up: stop and tell the founder before anything ships. D-089 is
  Locked when this passes.
- [ ] **Commit:** `feat(web): photo upload step [T-4.6]`

### T-4.7 · Web selfie step
- [ ] **Needs:** T-4.5, T-4.6
- [ ] Start the verification (no pose: T-4.5) → `getUserMedia({video:{facingMode:"user"}})` → live mirrored preview → capture to canvas → upload as `kind=selfie` → submit → poll `GET /verification/latest` every 2 s (max 60 s) → result. Handles permission denied with instructions per browser.
- [ ] Men: "Skip for now". Women: cannot skip.
- [ ] **The copy claims face matching only** (T-4.5's hard constraint): the screen says the selfie
  is compared with the profile photos, never that it confirms a real or live person.
- [ ] Built in T-3.11's `StepFrame`, at D-080's `/onboarding/selfie`, replacing T-3.12's placeholder.
- [ ] **Allow the camera here (D-059):** T-2.5's Permissions-Policy has `camera=()`, so `getUserMedia` is refused until this task makes it `camera=(self)`; add `blob:` wherever the captured frame shows. T-4.9's fake-camera E2E fails until then.
- [ ] **Commit:** `feat(web): selfie verification step [T-4.7]`

### T-4.8 · Finish onboarding
- [ ] **Needs:** T-4.5, T-4.10
- [ ] Service `onboarding.complete()`: requires profile fields, username, 5 interests, ≥ 1 public photo, location (T-4.10), and for women an `approved` verification → step `done`, compute `completeness`.
- [ ] **Commit:** `feat(onboarding): completion rules [T-4.8]`

### T-4.9 · E2E onboarding
- [ ] **Needs:** T-4.7, T-4.8, T-4.10
- [ ] Playwright with fake camera flags: man completes without selfie; woman is blocked until selfie approved.
- [ ] **Commit:** `test(e2e): full onboarding [T-4.9]`


### T-4.10 · Location
- [ ] **Needs:** T-3.5, and **P-38** (the seeded areas are still Bengaluru's; D-013 is Phagwara), and **P-65** before P-38: P-38's data migration is the next migration in the plan, and its deploy must read back the database's own head and D-076/D-077's guards
- [ ] `PUT /me/location` accepts `{lat,lng}` (must be inside India bounding box) or `{area_id}` (uses centroid). `GET /areas?city=`.
- [ ] Web: onboarding asks permission once with a clear reason; on deny → area picker. Location refreshed on app open if > 6 h old. The question has no `onboarding_t` step: give it a slug in D-080's map and a place in the flow, in T-3.11's `StepFrame`.
- [ ] The seed (T-1.15) gives each profile both its `area_id` and a location scattered near that area's centroid, as if it had shared its position. If `{lat,lng}` here leaves `area_id` empty, or sets it some other way, make the seed match.
- [ ] **Allow location here (D-059):** T-2.5's Permissions-Policy has `geolocation=()`, so the browser refuses the position without ever asking until this task makes it `geolocation=(self)`. Until then everyone silently lands on the area picker.
- [ ] **Commit:** `feat(profiles): location [T-4.10]`


### T-4.11 · Liveness
- [ ] **Needs:** T-4.5; the research below naming a model; and the founder's decision on it.
  **Before the first real user:** on REL-1's Needs line if REL-1's tag includes T-3.14, and on
  T-9.15's. Split out of T-4.5 by the founder, 4 October 2026, so T-4.5 ships face matching
  without it. D-008 (Locked) makes liveness mandatory for women before their profile goes live:
  this is the task that makes that true.
- [ ] **What is known, so the research starts from it** (read by Claude, 4 October 2026):
  Sightengine's `liveness` model is passive, one photo, no head turns: a score from 0 to 1 and a
  rejection reason (`no_face`, `too_many_faces`, `inanimate_face`, `invalid_face`, `spoof`,
  `deepfake`, `ai_generated`), on the same `check.json` endpoint as T-4.4's moderation. It isn't on
  the free plan: one call with our keys, on Sightengine's own example image, was refused with
  "Access to the Liveness Detection API is restricted. Feature not available on the free plan.
  Switch to a paid plan" (0 operations charged). Its pricing page lists it under Pro, $99 a month,
  and its documented example consumed 10 operations a check. **Not bought** (the founder): about
  ₹8,300 a month, roughly ₹1 lakh a year, before the product has a single paying user.
- [ ] **The research, first:** passive liveness, or presentation-attack detection, models whose
  licence permits commercial use. D-088's standard: the actual licence text read, and anything
  research-only rejected the way InsightFace was; memory measured and accuracy measured, on attacks
  we make ourselves (prints, screens, replays) against the measurement set's consenting people,
  never a paper's claims. Reported to the founder, who decides.
- [ ] **The pose challenge stays rejected** until that research exists (the founder, 4 October
  2026): Claude called it weak and so did he, and "a weak check that looks like a strong one is
  worse than no check".
- [ ] **Commit:** `feat(verification): liveness [T-4.11]`

---

# Sprint 5 — Velas core (week 8)

Built before discovery and chat because swipes, threads and unlocks all spend Velas.

**Decisions:** D-076 (Velas stay a closed-system instrument: only men hold them) and D-077 (a ledger
entry happens once), planned on 3 October 2026 with the advisor directing Sprint 5 (Claude, in a
separate chat) and approved by the founder.

**Order:** T-5.1 → T-5.4 → T-5.2 → T-5.3 → T-5.6 → T-5.5. T-5.4 proves T-5.1, so it follows
straight after. T-5.1 to T-5.4 need only Sprint 1 and can run alongside Sprints 3 and 4. If two
sessions both write a migration, the second to merge points its `down_revision` at the first's
before merging (rule 11 untouched).

**From T-5.1, `make infra-reset` is the only reset.** The first ledger row makes its user
permanent: the ledger refuses DELETE and TRUNCATE, and foreign keys into `users` are RESTRICT.
Starting over means `make infra-reset` (every volume: `velora`, every test run's, the local S3, Redis), then
`make infra-up migrate seed`. That stack serves every worktree on the machine (`CLAUDE.md`). No
migration ever writes a ledger row (rule 5), so no downgrade needs to delete one. Per-test rollback
still works, since a rollback isn't a DELETE. Tests that commit rows follow 06-TESTING's rules for
committed rows.

### T-5.1 · Wallet service
- [x] **Needs:** T-1.12, T-1.5, T-1.15
- [x] Settles P-19: tick it at `/done`.
- [x] Two migrations, one change each (rule 11), with models to match:
  1. **The ledger's shape (D-077).** Each reason has one direction: `(delta > 0) = (reason is a
     credit)`, with `gift` a debit. Every reason except `admin_grant` needs a ref. Each reason has
     exactly one `ref_type` (`admin_grant`'s ref is optional). A partial unique index on
     `(user_id, reason, ref_type, ref_id)` covers every reason except `admin_grant` and
     `thread_reopen`.
  2. **Only men hold Velas (D-076).** One trigger function and two triggers refuse any
     `ledger_entries` row, and any `wallets.balance` other than 0, for a user whose gender isn't
     `male`. That is an allowlist, so a user with no gender is refused too.
- [x] `wallet/rules.py`: each reason's direction and `ref_type`. Bare `refund` is refused, in the
  service only (D-077 says why the level differs from D-076's). The key is
  `{user_id}:{reason}:{event}`, built here and never by callers. The event is the ref id, or an
  event the caller names for `admin_grant` and `thread_reopen`.
- [x] `wallet.service.debit(...)` and `credit(...)`, in this order:
  - refuse anything outside a transaction;
  - the amount must be an `int`, not a `bool`, above 0;
  - the reason must be used in its direction, and the ref must match the reason;
  - `SELECT … FOR UPDATE` the wallet with the user's gender, and refuse anyone but a man;
  - a repeat key with the same details returns the existing entry with `applied=False`; with
    different details it raises;
  - a debit needs `balance >= amount`, or raises `INSUFFICIENT_CREDITS {required, balance}` (402)
    with a message naming no unit (rule 17);
  - update the balance, and insert the entry with `balance_after`.

  Both return `LedgerResult(entry, applied)`. They never catch a unique violation and carry on, and
  nothing external runs under the lock.
- [x] `core/events.py`: events are queued on the session, kept on commit and dropped on rollback.
  When the request ends, `get_session` publishes the request's committed events to Redis `user:{id}`
  in 02-ARCHITECTURE §6's envelope. The publish is awaited, never fire-and-forget: a publish that
  outlives its request fails where nobody is looking. A failed publish is logged and never fails the
  request. The event here is `wallet.updated {balance}`. Callers outside a request (the seed)
  publish nothing. T-7.4 builds the socket side.
- [x] **Seed (T-1.15):** credit the test man 60 through `credit(reason='admin_grant')` with a named
  event, even if he already exists. That is the one exception to insert-only, written in the seed's
  docstring and summary. A re-run changes nothing.
- [x] **`make_user(credits=N)` (T-3.1)** credits men through `credit(reason='admin_grant')`; anyone
  else with credits raises. Rule 5: nothing writes a balance directly.
- [x] **Changes the guards force on existing tests:**
  - `tests/test_schema.py`'s T-1.12 ledger tests get men and refs, and every CHECK test asserts its
    constraint name, not just SQLSTATE 23514. Otherwise a new guard could make one pass for the
    wrong reason (P-48's lesson, caught before it bit).
  - `tests/seed/test_seed.py`'s ledger count, which counts every row in the database, is scoped to
    the seeded people.
  - `tests/test_harness.py`'s credits test.
- [x] **Tests:**
  - **The gender guard both ways:** every `Gender` value and no gender, so only `male` may have rows
    or a non-zero balance. Includes the case that motivated the allowlist: a user with no gender is
    refused a credit, then chooses female, and holds nothing.
  - **Directions:** every reason × both signs against the rules, "only these"; and the debit reasons
    are exactly the priced actions plus `gift`.
  - **Refs and keys:** the per-event index refuses one payment under two keys; `thread_reopen` and
    `admin_grant` may repeat; two users with the same event both apply (P-19); a repeat gives
    `applied=False`; the same key with different details raises; bare `refund` is refused.
  - **`INSUFFICIENT_CREDITS`** writes nothing.
  - **A two-connection race** (two debits of 5 on a balance of 5; two same-key credits), asserting
    each waited alone at the lock (`f543b0d`).
  - **Events:** published on commit only, nothing after a rollback, a failed publish logged.
  - **The app role:** debit and credit as `velora_app`.
  - **The seed and `make_user`.**
  - **Rule 15:** no key, hash, PIN, token or phone number in a log or response, with the log tests
    also run in shuffled order. P-48's shuffle plugin isn't in the repo (found planning T-3.10 to
    T-3.13): commit it here, an opt-in option in `api/tests/conftest.py` with no new dependency,
    unless T-3.13 already has. Never a throwaway copy: a fix whose mechanism isn't in the repo is
    not a fix (CLAUDE.md).
- [x] **Break every guard once, on a database of the task's own.** That is `velora_t51_test`, made
  with `createdb` in the shared Postgres (never `infra-reset`), with `TEST_DATABASE_URL` pointed at
  it. Breaking a constraint in the shared `velora_test` would hit every session using it, however
  well its assertions are scoped. Break:
  - each of D-077's six layers;
  - each of D-076's two triggers, removed and also turned into a blacklist;
  - the service checks;
  - publish-before-commit;
  - the seed's key.

  Restore each byte for byte, proved by SHA-256. The report lists every weakening and its result.
  **Since P-55** every run has a database of its own, created empty when it starts, so
  `TEST_DATABASE_URL` is optional here. It still works, and the run still takes a slot for its Redis
  database. The full `make test` runs on its own slot's database.
- [x] **Done when:** the docs commit after `/done` names the staging deploy run that applied both
  migrations. **Deploy run 37131243030** (commit `1938709`): its migrate job, as the owner against
  Supabase, logged `Running upgrade 684b79a19e8b -> 97ddae55f597` and `97ddae55f597 ->
  190d7bebf133` (3 October 2026, 14:53 UTC), so the D-076 migration's count found nothing held
  by anyone but a man on staging; smoke passed. Read from alembic's own log, not the database's
  `alembic_version`, which this session can't reach.
- [x] **Commit:** `feat(wallet): row-locked debit and credit [T-5.1]`

### T-5.4 · The concurrency test 🔒
- [ ] **Needs:** T-5.1
- [ ] Settles P-07: tick it at `/done`.
- [ ] **Committed rows, never deleted** (the ledger refuses DELETE and TRUNCATE):
  - fresh men each run, never onboarded, on numbers `make_user` never generates (T-5.1's helper);
  - every assertion scoped to their ids;
  - each run's database is its own, recreated when its slot is next taken (P-55); CI starts empty;
  - never the owner's trigger bypass.
- **Moved out of this list, 4 October 2026: its first two items,** a counter for `fresh_man`'s
  numbers and P-64's tripwire. They are harness, not wallet, and Sprint 4's tests use the same
  helper, so they landed before Sprint 4 instead of waiting here, in `test(harness): fresh men by
  a counter; P-64's tripwire [T-5.4]` (at the direction of the advisor, Claude in a separate chat,
  relayed by the founder). What this task inherits: `fresh_man` numbers men one past the highest
  `+9197` number the database holds, under an advisory lock, so fifty made at once never share
  one and a run on a database `TEST_DATABASE_URL` keeps never restarts into an earlier run's; and
  listening on Redis through the `client` fixture raises, naming P-64.
- [ ] **A dedicated 50-connection engine,** asserting 50 distinct backends. If Postgres runs out of
  connections, fail loudly; never skip.
- [ ] **Prove the overlap by what the lock decides** (`f543b0d`): all 50 are inside open transactions
  before any takes the lock (asserted). After the read, each waits up to 20 ms and records whether
  it waited alone; with the lock, all 50 do.
- [ ] **Debits:** credit a man 10, then fire 50 concurrent debits of 5. Exactly 2 succeed, 48 get
  `INSUFFICIENT_CREDITS`, the balance is 0, there are 3 ledger rows (the credit and 2 debits), and
  `sum(delta) == balance`.
- [ ] **Keys:**
  - the same key 50× concurrently, for debits and for credits: exactly 1 entry each;
  - one payment credited under two different keys: the second is refused by D-077's index;
  - two users with the same client key: both apply.
- [ ] **Breaking runs:** `FOR UPDATE`, the repeat check, the unique key and the per-event index, one
  at a time, each red, on the task's own database as in T-5.1.
- [ ] This test must never be skipped or marked flaky. If it fails, stop everything.
- [ ] **Commit:** `test(wallet): concurrency and idempotency [T-5.4]`

### T-5.2 · Prices
- [ ] **Needs:** T-5.1
- [ ] `pricing.service.price_for(user, action)`:
  - women 0; men the `action_prices` value;
  - no gender raises; an inactive row gives `NOT_ALLOWED`; a missing row is a 500; never 0 by
    default;
  - read fresh inside the debit's transaction, with no cache. P-47 puts any cache on the app, and
    P-50 adds one only where something is measured slow.
- [ ] `pricing.service.charge(...)` reads the price and debits only when it is above 0, since a
  debit of 0 raises. A test allows `wallet.service.debit` to be called only from `charge` and from
  gift sending (T-8.9, priced from `gifts`), so no literal price can reach it.
- [ ] `GET /prices` (public): list prices for active actions only. Gifts aren't in it (`GET /gifts`).
- [ ] **Commit:** `feat(pricing): server-side prices [T-5.2]`

### T-5.3 · Wallet endpoints
- [ ] **Needs:** T-5.1
- [ ] `GET /wallet` → `{balance}`. `GET /wallet/ledger?cursor=` → `Page<LedgerEntry>`: `id`,
  `delta`, `balance_after`, `reason`, `created_at`; never refs or the key. The web turns `reason`
  into words from `en.ts` (D-033, P-26); the API doesn't.
- [ ] Newest first by `(created_at, id)`. Entries from one transaction share `created_at`, so their
  order is stable but arbitrary. The opaque cursor and the page type live in `core`, since this is
  the first paginated endpoint.
- [ ] Women get a balance of 0 and an empty list, not a refusal. No rate limit on these reads.
- [ ] **Commit:** `feat(wallet): balance and history [T-5.3]`

### T-5.6 · App shell
- [ ] **Needs:** T-3.10
- [ ] The `(app)` layout's header and bottom nav: Discover, Chats, Wallet and You, each a placeholder
  route until its task. No Vibe (after beta, D-010). The wordmark comes from `APP_NAME`, never the
  prototype's "Knot" (rule 17).
- [ ] **Who owns the frame** (decided planning T-3.10 to T-3.13; T-3.10 and T-3.11 carry the same
  line). T-3.10's `(app)` layout restores the session, gates on `done` and shows the PIN lock. This
  task adds the header and nav inside that layout, in `src/components/shell/`, never replacing what
  T-3.10 put there, and never on `(auth)` routes. Onboarding has its own frame, T-3.11's
  `StepFrame`, with no header or nav, as in the prototype.
- [ ] **Provisional (08-DESIGN):** no visual design exists for the app's screens, and the prototype
  was wrong four times in Sprint 5's plan alone: the refund button, gift's direction, the price list
  and "credits" for Velas. Build only what this task names; anything more waits on P-57.
- [ ] **The shell's look lives in two places only:** colour, type scale and spacing as tokens in
  `src/styles/tokens.css`, and the header's and nav's shape in one layout component in
  `src/components/shell/`, never spread through the components inside. **Why:** this shell is
  what every later screen sits inside, built before any visual design exists (P-57). When T-6.5's
  design pass comes, it should change values, not structure. Reopening the shell's structure after
  five screens sit on it would be the most expensive rework in the sprint; this is the cheapest
  insurance against it. At the direction of the advisor directing Sprint 5, 3 October 2026.
- [ ] **Commit:** `feat(web): app shell [T-5.6]`

### T-5.5 · Web wallet
- [ ] **Needs:** T-5.2, T-5.3, T-3.10, T-5.6
- [ ] **The balance pill** (men), or "Free access" (women), sits in T-5.6's header.
- [ ] **The wallet screen** has a black balance card, a price list from `/prices` and the ledger
  history (infinite scroll). It follows the prototype with these departures, written into 08-DESIGN:
  - no "Request a refund on unspent credits" and no "Unspent credits refundable within 7 days" (the
    cash-out D-050 removed; D-076), just a quiet link to `/refunds`;
  - the price list is `/prices`' seven actions plus "Tie the knot · Free" and "Messaging in a knot ·
    Free". Not Wink, Boost, calls or "Gifts 20–500" (D-016's prices are 0, 2 and 4);
  - "credits" becomes Velas (D-049), and the women's screen drops "calls" (after beta).
- [ ] The pill reads one wallet query, refreshed after anything that spends or credits and when the
  window regains focus. No polling; the socket arrives with T-7.12.
- [ ] Global handler: any `INSUFFICIENT_CREDITS` from a mutation (the query client's mutation error
  hook; queries never) opens the store sheet, a "coming soon" placeholder until T-8.7, with its open
  state in Zustand.
- [ ] Words for all 15 ledger reasons in `en.ts`, in a map typed from the generated enum, so a new
  reason without words fails `tsc`.
- [ ] **Commit:** `feat(web): wallet screen and balance pill [T-5.5]`

---

# Sprint 6 — Discovery (weeks 9–10)

> Location lives in Sprint 4 as T-4.10, because onboarding needs it first. Discovery starts at T-6.2.

### T-6.2 · Discovery query
- [ ] **Needs:** T-4.10, T-4.8
- [ ] Repository implements the query in `02-ARCHITECTURE.md §8` with feeds: `foryou` (ranked), `new` (joined ≤ 7 days first), `online` (active ≤ 5 min). Filters: `intent_ids` (any overlap, D-041), verified.
- [ ] Excludes: self, swiped, blocked either way, hidden, not `done`, status ≠ active, fraud band `freeze`; `shadow` band users only shown to others in `shadow`.
- [ ] Response `Card`: id, first_name, age (null if hide_age), username, city, hometown, distance_km (null if hide_distance, else ≥ 1), intent_ids, bio line (first 90 chars of about), main photo URL, is_verified, is_online, is_new.
- [ ] Cursor = (score, user_id).
- [ ] Performance test: seed 50k profiles, assert p95 < 80 ms with `EXPLAIN ANALYZE` showing the GIST index.
- [ ] **Commit:** `feat(discovery): ranked nearby feed [T-6.2]`

### T-6.3 · Public profile
- [ ] **Needs:** T-6.2
- [ ] `GET /users/{id}` → `PublicProfile`: card fields + full about, all approved public photos, interests, kudos (if `show_kudos`), album photo count, existing thread/knot state with me. Blocked either way → 404 `NOT_FOUND`. Records a profile view (for later "viewed you").
- [ ] **Commit:** `feat(profiles): public profile [T-6.3]`

### T-6.4 · Swipes and matching
- [ ] **Needs:** T-6.3, T-5.1
- [ ] `POST /swipes {target_id, dir}`: men's daily cap from `app_config` (IST day, Redis counter) → `SWIPE_LIMIT_REACHED`; `super` debits price (women free) via wallet; duplicate swipe → `ALREADY_EXISTS`.
- [ ] If `like`/`super` and the target already liked me → create `matches` row (ordered pair), publish `match.created` to both, notification.
- [ ] **Commit:** `feat(swipes): swipe, daily cap, super like, match [T-6.4]`


### T-6.5 · Web discover deck
- [ ] **Needs:** T-6.2, T-6.4, and P-57: the app's screens have no visual design, so this task stops and asks before designing one rather than inventing it from the prototype
- [ ] `useDiscover(feed, filters)` infinite query; keep 3 cards rendered; prefetch next page at 5 left.
- [ ] Card with `@use-gesture/react` + `@react-spring/web`: drag with rotation, LIKE/PASS overlays by drag distance, fling threshold 100 px or velocity, up = super. Tap = open profile. Keyboard ← → ↑ on desktop.
- [ ] Optimistic swipe: advance immediately, rollback + toast on error.
- [ ] Action row: pass, super (price tag for men), like. Swipes-left counter for men.
- [ ] Match celebration sheet → "Open thread · 5 Velas" / "Keep swiping".
- [ ] Empty states: no one nearby / filters too narrow (clear button).
- [ ] 60 fps on the test phone (check Chrome performance panel).
- [ ] **Re-examine the CSP's `'unsafe-inline'` here (D-059's trigger, amended 3 October 2026):** the first screen planned to render another user's text, their names and about. If any screen gets there sooner, the re-examination moves to it. T-3.11 kept the allowance for the user's own text; here the threat is someone else's input on your page. Nonces scoped to the signed-in routes by Next's proxy leave the marketing pages static (the amendment).
- [ ] **Commit:** `feat(web): discover deck [T-6.5]`

### T-6.6 · Search and @username
- [ ] **Needs:** T-6.3
- [ ] `GET /search?q=`: `@` prefix → exact-then-prefix username match (ignores distance/filters, still respects blocks/hidden); otherwise trigram on first_name/username + city, intent and interest matches within radius. `GET /users/by-username/{u}`.
- [ ] Web search bar with debounce; @-mode list results.
- [ ] **Commit:** `feat(search): search and username lookup [T-6.6]`

### T-6.7 · Liked you
- [ ] **Needs:** T-6.4, T-5.1
- [ ] `GET /likes`: people who liked/super-liked me and whom I haven't swiped; for men, unrevealed entries return only a blurred thumbnail URL (server-generated blur, not CSS) and no name. `POST /likes/{id}/reveal` debits 20 and records `liked_you_reveals`.
- [ ] Web "Liked you" tab: grid, count badge, reveal flow.
- [ ] **Commit:** `feat(discovery): liked you with paid reveal [T-6.7]`

### T-6.8 · Profile pages
- [ ] **Needs:** T-6.3
- [ ] In-app profile screen from the prototype (gallery, chips, kudos, message button, album section, ⋯ menu).
- [ ] Public shareable page `veloraapp.co.in/@username` (SSR): logged-out visitors see first name, age, city, main photo, and "Join Velora to message"; logged-in users are redirected to the in-app profile.
- [ ] `/@username` is D-001's link, and the `@` keeps usernames out of the routes' namespace: no route segment may begin with `@` (D-068). Next.js reads an `@folder` as a parallel-route slot, so serve `/@username` through a rewrite to an internal route.
- [ ] **Commit:** `feat(web): profile screens and share page [T-6.8]`

### T-6.9 · Filters
- [ ] **Needs:** T-6.5
- [ ] Filter sheet: intent multi-select, verified only, online now; active count badge; stored in URL search params.
- [ ] **Commit:** `feat(web): discovery filters [T-6.9]`

---

# Sprint 7 — Threads, knots, chat (weeks 11–12)

### T-7.1 · Open a thread
- [ ] **Needs:** T-6.4, T-5.5-ready wallet (T-5.1)
- [ ] `POST /threads` from `{match_id}` (origin `match`) or `{user_id, first_message}` (origin `dm`, first message required, 1–500 chars).
- [ ] Rules: not blocked; both onboarded; if a thread already exists for the pair → `active`/`knotted` returns it (no charge), `expired` → `THREAD_EXPIRED` (client offers re-open).
- [ ] In one transaction: debit (men only, `thread_open` or `dm_open`), insert thread (`expires_at = now + thread_hours`), link match, insert first message if dm. Notify the other person.
- [ ] Tests: man pays once; woman pays nothing; double-tap race creates one thread and one charge.
- [ ] **Commit:** `feat(threads): open thread [T-7.1]`

### T-7.2 · Thread list
- [ ] **Needs:** T-7.1
- [ ] `GET /threads?tier=threads|knots&filter=&q=`: excludes cleared (unless newer message), blocked; each row has other person's card-lite, last message preview (voice → "Voice note"), unread count, status, `expires_at`, whether I've tapped tie.
- [ ] **Commit:** `feat(threads): list [T-7.2]`

### T-7.3 · Messages
- [ ] **Needs:** T-7.2
- [ ] `GET /threads/{id}/messages?cursor=` (newest first, respects my `cleared_at`; voice notes locked for men without unlock → no media URL).
- [ ] `POST /threads/{id}/messages`: participant only; thread `expired` → `THREAD_EXPIRED`; text 1–2000; abuse/solicitation rules → `MESSAGE_REJECTED` (+ fraud event); masking if `message_count < mask_first_n` (store `body_raw`, set `masked`); dedupe on `client_msg_id` (return existing); update `last_message_at`, `message_count`; publish `message.new`; notify recipient if not connected.
- [ ] Tests for masking patterns (+91 numbers, spaced digits, emails, UPI handles, "insta: x"), rejection, dedupe, expired.
- [ ] **Commit:** `feat(messages): list and send with safety filters [T-7.3]`

### T-7.4 · Real-time server
- [ ] **Needs:** T-7.3, and **P-64**: in tests `session_for_the_app` replaces `get_session`, which is what publishes, so no endpoint test sees an event; and services queue events through `core/events.py` (T-5.1), never a publish of their own
- [ ] `POST /ws/ticket` (Redis, 30 s, single use). `/ws` endpoint: validate ticket, register connection, subscribe `user:{id}`, heartbeat, close on logout/freeze. Publishing helper `realtime.publish(user_id, type, data)` used by services.
- [ ] Load test: 1,000 concurrent sockets on one instance stay under 256 MB.
- [ ] **Commit:** `feat(realtime): websocket gateway [T-7.4]`

### T-7.5 · Read receipts and typing
- [ ] **Needs:** T-7.4
- [ ] `POST /threads/{id}/read` sets `read_at` up to a message, publishes `message.read`. Client `typing` relay throttled.
- [ ] **Commit:** `feat(realtime): read receipts and typing [T-7.5]`

### T-7.6 · Expiry and re-open
- [ ] **Needs:** T-7.4
- [ ] Cron `expire_threads` (every minute, batches of 500, `FOR UPDATE SKIP LOCKED`) → `expired` + event. Cron `warn_expiring` (< 2 h, once) → push + event.
- [ ] `POST /threads/{id}/reopen` (expired only) → debit 3 (men), `active`, `expires_at = now + 24h`, reset warning.
- [ ] Tests using a controllable clock.
- [ ] **Commit:** `feat(threads): expiry, warnings, reopen [T-7.6]`

### T-7.7 · Tie the knot
- [ ] **Needs:** T-7.6
- [ ] `POST /threads/{id}/knot`: set my `*_knot_at`; if both set → `knotted`, `knotted_at`, `expires_at = null`, publish `knot.accepted` to both; else publish `knot.requested` to the other. Works on `expired` threads too (converts directly if both).
- [ ] `DELETE /threads/{id}/knot`: untie → `active`, fresh 24 h, clear both taps, notify.
- [ ] **Commit:** `feat(threads): tie and untie knot [T-7.7]`

### T-7.8 · Clearing
- [ ] **Needs:** T-7.2
- [ ] `POST /threads/{id}/clear`, `POST /threads/clear` (ids or `expired: true`), `DELETE /threads/{id}/clear` (restore). Upsert `thread_clears`. Never touches `messages`.
- [ ] Test: after A clears, B still sees everything; admin still sees everything.
- [ ] **Commit:** `feat(threads): one-sided clearing [T-7.8]`

### T-7.9 · Voice notes
- [ ] **Needs:** T-7.3, T-4.1
- [ ] `POST /media/voice-upload-url` (women only, ≤ 60 s, ≤ 2 MB, audio/webm|ogg|mp4), then send message `kind=voice` with `media_key`, `duration_s`.
- [ ] `POST /messages/{id}/unlock` (men, debit 5, insert `message_unlocks`, idempotent) → signed URL. `GET /messages/{id}/media` for sender or unlocked.
- [ ] **Commit:** `feat(messages): voice notes and unlocks [T-7.9]`

### T-7.10 · Web chat list
- [ ] **Needs:** T-7.2, T-7.8
- [ ] Threads / Knots tabs with counts; live countdown per row (one shared 1 s ticker, not one per row); Knots filters; search; select mode + bulk clear; "Clear expired (n)"; trash per row with 5 s undo toast; unread dots; empty states.
- [ ] **Commit:** `feat(web): chats list [T-7.10]`

### T-7.11 · Web conversation
- [ ] **Needs:** T-7.3, T-7.7, T-7.9
- [ ] Bubbles, day separators, "Sent/Read" on my last message, typing dots, voice player (locked card with price for men), icebreakers when empty, knot bar (tie / waiting), expired panel (re-open · 3 / tie), header with countdown or "Knotted · permanent", ⋯ → profile menu.
- [ ] Composer: text (Enter sends, Shift+Enter newline), mic for women (MediaRecorder, hold or tap-to-record, 60 s cap, preview before send). Optimistic send with `client_msg_id`; failed → retry.
- [ ] Rejected message → inline explanation, text kept in composer.
- [ ] **Allow the microphone here (D-059):** T-2.5's Permissions-Policy has `microphone=()`, so recording is refused until this task makes it `microphone=(self)`; add `media-src` for voice notes' storage origin and `blob:` for the preview.
- [ ] **Commit:** `feat(web): conversation screen [T-7.11]`

### T-7.12 · Web real-time client
- [ ] **Needs:** T-7.4, T-7.11
- [ ] `src/lib/ws.ts`: ticket → connect; exponential backoff 1→30 s with jitter; pause when tab hidden > 5 min; on reconnect refetch open thread + list. Events update TanStack Query caches (append message, bump row, update wallet, knot state).
- [ ] **Widen the CSP here (D-059):** `connect-src` for `wss://` on the API host. The socket fails with a CSP error until then.
- [ ] **Commit:** `feat(web): realtime client [T-7.12]`

### T-7.13 · E2E chat
- [ ] **Needs:** T-7.12
- [ ] Two browser contexts: man + woman. Match → open thread (balance −5) → messages both ways live → woman voice note → man unlocks (−5) → both tie → Knots tab. Expiry via test clock endpoint (local only).
- [ ] **Commit:** `test(e2e): threads and knots [T-7.13]`

---

# Sprint 8 — Payments, album, kudos, referrals (week 13)

### T-8.1 · Packs and orders
- [ ] **Needs:** T-5.1, T-1.21, and P-0.17: a chartered accountant has confirmed how prepaid Velas are treated, before any real sale can happen
- [ ] `GET /packs`: active packs for the user's price-test variant (`users.id` hash → A/B, stable). `POST /payments/orders {pack_id}` + `Idempotency-Key`: copy amount + `credits` from the pack, compute first-purchase bonus, create provider order, insert `payments` (`created`), return checkout params.
- [ ] **A woman can't order Velas** → `NOT_ALLOWED` (D-076). The database would refuse her credit anyway; the route says so first, before she pays for something she could never use.
- [ ] Fake provider: returns a fake order and exposes a local-only endpoint that simulates the webhook.
- [ ] **Commit:** `feat(payments): packs and order creation [T-8.1]`

### T-8.2 · Webhook
- [ ] **Needs:** T-8.1
- [ ] `POST /payments/webhook`: verify `X-Razorpay-Signature` (HMAC SHA-256 of raw body with webhook secret) → else 400 and log. Handle `payment.captured` and `payment.failed` only; others → 200 ignore.
- [ ] Captured: find by order id; if `provider_payment_id` already set → 200 no-op. Else one transaction: set paid + ids + `raw_webhook`, `wallet.credit(purchase)`, `wallet.credit(purchase_bonus)` if any, referral reward check (T-8.6). Always return 200 quickly.
- [ ] Amount mismatch vs row → mark `failed`, alert, no credit.
- [ ] **`raw_webhook` keeps no payer details, whatever city the database is in** (directed 3 October
  2026, from P-49's residency read): it stores an allowlist of the verified payload's fields and
  nothing else, Razorpay's payment and order ids, amount, currency, status, method, error code and
  timestamps. Never the payer's email, phone (`contact`), UPI ID (`vpa`), card or bank details:
  RBI's own list of payment data, and not ours to keep. An allowlist, never a list of fields to
  strip, so a field Razorpay adds later stays out. Test: a payload with every payer field set is
  stored with exactly the allowlisted keys.
- [ ] `GET /payments/{id}` for the client poll.
- [ ] **Refunds and disputes made outside us** (D-076, rule 3): a refund done in Razorpay's dashboard, or a chargeback, must not leave the payment's Velas standing. Handle Razorpay's refund and dispute events by reversing those Velas in the ledger, in the same step. That needs a debit reason for the reversal, an enum addition decided here. If the Velas were spent, decide here what happens, and write it down.
- [ ] Tests: same webhook delivered 5 times concurrently → credited once; bad signature → no credit; amount mismatch → no credit.
- [ ] **Commit:** `feat(payments): verified idempotent webhook [T-8.2]`

### T-8.3 · Refund requests
- [ ] **Needs:** T-8.2
- [ ] `POST /refund-requests` for **broken transactions only** (D-050): a payment that went through without granting Velas, or a duplicate charge for one purchase. A change of mind isn't a claim — purchases are final. In MVP an admin resolves each claim: missing Velas are granted through `wallet.credit()` (idempotent on the payment), and a duplicate charge is refunded to the original payment method in the gateway and recorded (`payments.status = refunded`). This task defines the claim kinds and the `status` values.
- [ ] **Missing Velas are granted with reason `purchase` (and `purchase_bonus`) and the webhook's own key** (D-077), never `admin_grant`: so a webhook arriving after the repair can't credit them a second time. Money goes back only under D-076's rule 3.
- [ ] **Commit:** `feat(payments): refund requests [T-8.3]`

### T-8.4 · Private album
- [ ] **Needs:** T-4.4, T-5.1
- [ ] Requests (debit 5 for men, `credits_charged` stored), incoming list for owner, decide (grant → enqueue `watermark_album`; decline → `wallet.credit(refund_album_declined)`), revoke (delete watermarked copies, status `revoked`).
- [ ] **A decline refunds only when `credits_charged > 0`.** A woman's request is free, `credit()` refuses an amount of 0, and the database refuses any ledger row for her (D-076).
- [ ] `watermark_album`: for each private photo render a copy with the viewer's `@username` tiled diagonally at ~20% opacity.
- [ ] `GET /users/{id}/album` → signed URLs of the viewer's copies only.
- [ ] **Commit:** `feat(album): requests, grants, watermarking [T-8.4]`

### T-8.5 · Kudos
- [ ] **Needs:** T-7.3
- [ ] `POST /kudos` (thread with ≥ `kudos_min_messages`, one per pair ever, fixed kinds only), `GET /me/kudos`, visibility via `show_kudos` setting. Public profile shows distinct kinds received, never who sent them.
- [ ] **Commit:** `feat(kudos): positive-only notes [T-8.5]`

### T-8.9 · Gifts
- [ ] **Needs:** T-5.1, T-6.3
- [ ] `GET /gifts` (active, sorted, cached 60 s).
- [ ] `POST /gifts/send {recipient_id, gift_id}` with `Idempotency-Key`. Rules, each with a test:
  recipient must be a woman with onboarding `done` (else `NOT_ALLOWED`); sender must be a man
  (women sending → `NOT_ALLOWED`); blocked either way → `BLOCKED`; frozen sender → `ACCOUNT_FROZEN`;
  free gifts capped by `gift_free_daily_limit` per IST day → `GIFT_LIMIT_REACHED`;
  same gift to the same person inside `gift_same_recipient_cooldown_h` → `GIFT_COOLDOWN`.
- [ ] Paid gifts: `wallet.debit(reason="gift", ref_type="gift_send")` **in the same transaction**
  as the `gift_sends` insert. Price read from the `gifts` row, never a literal.
- [ ] Links `thread_id` if an active or knotted thread already exists. Never creates a thread.
- [ ] Publishes `gift.received` on the socket and a notification (respects prefs).
- [ ] `GET /me/gifts` (received, paginated, sender card) and `GET /users/{id}/gifts` (counts only,
  hidden when `show_gifts` is false).
- [ ] **Commit:** `feat(gifts): catalogue, sending, limits [T-8.9]`

### T-8.10 · Web gifts
- [ ] **Needs:** T-8.9, T-5.5
- [ ] Gift button on a woman's profile → sheet with the 6 gifts in a 3×2 grid: asset, label, and
  either "Free" or the price in Velas. Free ones show the remaining daily count.
- [ ] Sending: optimistic disable, success toast, balance updates from `wallet.updated`.
  `GIFT_LIMIT_REACHED` / `GIFT_COOLDOWN` → friendly inline copy with when they can send again.
  `INSUFFICIENT_CREDITS` → store sheet.
- [ ] Received gifts row on her own profile and in You tab; toggle `show_gifts` in privacy settings.
- [ ] Notification opens the sender's profile.
- [ ] **Commit:** `feat(web): gifts on profile [T-8.10]`

### T-8.6 · Referrals
- [ ] **Needs:** T-8.2
- [ ] `POST /referrals/apply {code}` only before onboarding `done`, not own code, once. Reward both (Velas from `app_config`) when the referee completes selfie verification or first purchase, whichever first; idempotent. `GET /referrals/me`. Apply looks a code up and never checks its format: the seed's three test accounts carry readable codes outside the generated one (T-3.3).
- [ ] **A woman's referral reward is never Velas** (D-076): the database refuses any ledger row for her, and "Reward both" would otherwise reach every referred woman, since every woman verifies her selfie (D-008). Decide here what she gets instead, if anything, and write it down.
- [ ] **D-078 (P-54):** an under-18 refusal deletes `referrals` rows naming the user, as referrer or
  referee, once P-54's row half has landed; check it has. A reward already paid is a ledger row,
  which rule 12 keeps, and would stop the deletion: none can exist before dob is set.
- [ ] **Commit:** `feat(referrals): codes and rewards [T-8.6]`

### T-8.7 · Web store and checkout
- [ ] **Needs:** T-8.2, T-5.5
- [ ] Store sheet from the prototype (packs, per-Vela and per-thread price, first-purchase banner). Load Razorpay Checkout script on demand. On success callback → poll `/payments/{id}` every 1.5 s (max 60 s) → toast + wallet refresh. Failure/dismiss → "Payment didn't go through" sheet with retry.
- [ ] **Widen the CSP here (D-059):** Razorpay Checkout's script, frame and connect hosts, exactly as Razorpay documents them. The CSP has been enforced since T-2.5, so checkout fails with a CSP error until this lands.
- [ ] **Commit:** `feat(web): store and razorpay checkout [T-8.7]`

### T-8.8 · Web album, kudos, referral UI
- [ ] **Needs:** T-8.4, T-8.5, T-8.6
- [ ] Album section on profile (locked / pending / granted with watermark note); incoming requests list for women with grant/decline; kudos prompt in chat after the threshold; referral code field in onboarding (optional) and share card in You tab.
- [ ] **Commit:** `feat(web): album, kudos, referrals [T-8.8]`

---

# Sprint 9 — Safety, admin, notifications, hardening (weeks 14–15)

### T-9.1 · Reports and blocks
- [ ] **Needs:** T-7.2
- [ ] `POST /reports` (≤ 10/day, details ≤ 500, optional `also_block`), `POST /blocks`, `DELETE /blocks/{id}`, `GET /blocks`.
- [ ] Block effects, each with a test: removed from both discovery feeds, search, likes; profile → 404 both ways; threads hidden for both and sending → `BLOCKED`; realtime events stop; existing album grants revoked.
- [ ] Reported person is never told who reported.
- [ ] **Commit:** `feat(safety): reports and blocks [T-9.1]`

### T-9.2 · Fraud scoring v1
- [ ] **Needs:** T-9.1
- [ ] Signals written as `fraud_events` by services: report received, contact-info masked, message rejected (abuse / solicitation), > 30 new threads in 24 h, identical first message to > 10 people, > 3 devices in 7 days, location jumps > 500 km in 1 h.
- [ ] Sessions store no IP address or user agent (D-067), and "> 3 devices in 7 days" needs one of them. Add what this task needs here, with a line on `/privacy`, which lists neither today.
- [ ] `recompute_fraud` worker: weighted sum with 7-day decay → `fraud_scores` + band. Actions: `shadow` → shown only to other shadowed users; `freeze` → status `frozen`, sessions revoked, admin notified. 3 reports from different users in 24 h → freeze immediately.
- [ ] **D-078 (P-54):** an under-18 refusal deletes `fraud_events` and `fraud_scores` rows, once P-54's
  row half has landed; check it has, since a location jump can come before dob is set.
- [ ] **Commit:** `feat(safety): fraud scoring and auto-freeze [T-9.2]`

### T-9.3 · Refund when a partner is banned
- [ ] **Needs:** T-9.2, T-5.1, and **P-63**: one ban credits several men in one transaction, and nothing yet makes their wallets lock in `user_id` order (D-077)
- [ ] On ban: find Velas other users spent on this person in the last 7 days (threads opened with them, voice unlocks, album requests) → `wallet.credit(refund_banned_partner)` each, idempotent per ref, notify. The 7 days is also stated on `/refunds` (D-050): change both together.
- [ ] **Commit:** `feat(safety): refunds for banned partners [T-9.3]`

### T-9.4 · Notifications
- [ ] **Needs:** T-7.4
- [ ] VAPID keys; `POST/DELETE /push/subscriptions`; `send_push` worker (drop subscriptions on 404/410); notification prefs; in-app `notifications` list. Kinds: match, message (only if not connected), like, knot requested/accepted, thread expiring, album decided, low balance.
- [ ] Web: Serwist service worker (push + notificationclick → open the right route), permission asked **after the first match**, not on load; generic-text option; iOS note when not installed.
- [ ] Update `/privacy` (T-2.2) to say what push notifications carry and who delivers them.
- [ ] **Commit:** `feat(notifications): web push and in-app list [T-9.4]`

### T-9.5 · Admin panel
- [ ] **Needs:** T-9.2
- [ ] API: all `/admin/*` routes in `04-API.md`, `require_role(moderator)`; Vela grants and bans `admin` only; every call writes `audit_log`; viewing messages of a thread logs who looked and why (reason required).
- [ ] **Vela grants (`/admin/users/{id}/credits`):** a grant can't reach a woman, because the database refuses it (D-076). A negative `delta`, an admin correction, has no ledger reason today, since `admin_grant` is a credit (D-077). Add a debit reason for it here, an enum addition. **Make `admin_grant`'s ref required here:** it is optional (T-5.1) only while its callers are the seed and `make_user`; an admin's grant names the `audit_log` row its call writes, or it is a grant nobody can trace. That is a migration on `ck_ledger_entries_ref_required` and a change to `wallet/rules.py`, which the seed and `make_user` must then follow (at the direction of the advisor directing Sprint 5, 3 October 2026).
- [ ] Web `/admin`: metrics tiles, report queue with SLA timer (24 h), user search + detail (photos, reports, fraud signals, ledger, threads), moderation queue (approve/reject), actions with confirmation dialogs, audit log.
- [ ] Web `/admin` renders only for `role in (moderator, admin)`, read through `useMe()`; anyone else
  gets the 404 page — replacing T-1.22's `next dev`-only gate (from P-30). **This gate is UX, not
  protection:** anyone can download the page's JavaScript, and the Next.js server never sees a
  session there (D-024). Every `/admin/*` endpoint must carry its own `require_role(...)`; the
  API's role check is the only thing guarding admin data.
- [ ] **User search finds a phone number only in full, never by prefix or part** (D-061). Numbers are
  stored as a keyed hash and an encrypted copy, so search normalises and hashes the number typed and
  matches it exactly. "Whose number ends in 4321?" has no answer, by design: support asks for the
  whole number.
- [ ] **Commit:** `feat(admin): moderation panel [T-9.5]`

### T-9.6 · Settings and data rights
- [ ] **Needs:** T-3.5
- [ ] Hide profile, hide age, hide distance, show kudos; pause (hidden + no notifications); export (JSON of own data, generated by worker, signed link valid 24 h); delete (status `deleted`, profile hidden immediately, anonymised after 30 days by cron; payments and ledger kept, detached from identity). What's erased and kept follows D-051, which `/privacy` states: messages stay in the other person's chat as from "Deleted account" and as moderation records, and a hashed phone number is kept so deletion can't escape a ban. Change the page with the code.
- [ ] Two things T-3.3 and T-3.7 left here: what a `deleted` account gets at sign-in (`FORBIDDEN` until now, D-067), and whether and how a username can change after onboarding (locked until now, D-068; D-001's `/@username` links depend on it).
- [ ] **Commit:** `feat(settings): privacy and data rights [T-9.6]`

### T-9.7 · PWA
- [ ] **Needs:** T-9.4
- [ ] Web manifest (name, icons 192/512/maskable, theme colour from tokens, `display: standalone`), install prompt banner (Android `beforeinstallprompt`; iOS instructions), offline shell page.
- [ ] **Commit:** `feat(web): installable pwa [T-9.7]`

### T-9.8 · You tab complete
- [ ] **Needs:** T-9.6, T-8.8
- [ ] Profile summary + edit, verification status, kudos, knots list with untie, blocked list with unblock, reports filed, cleared chats with restore, settings rows, lock now, log out.
- [ ] **Commit:** `feat(web): you tab [T-9.8]`

### T-9.9 · Ledger audit
- [ ] **Needs:** everything above
- [ ] One test per paid action (thread open, dm, re-open, voice unlock, album, super like, liked-you reveal): man → exactly one ledger entry with the right reason and amount; woman → zero entries; insufficient → nothing created.
- [ ] Reconciliation test: for every user, `wallets.balance == sum(ledger.delta)`. Also as a daily cron that alerts on mismatch.
- [ ] **Commit:** `test(wallet): paid action audit and reconciliation [T-9.9]`

### T-9.10 · Performance pass
- [ ] **Needs:** T-9.8
- [ ] On the ₹10k test phone over throttled 4G: first load of `/discover` < 3 s, swipe at 60 fps, JS bundle for `(app)` < 250 KB gzipped, images served at the right size. Fix the top 3 offenders.
- [ ] **Commit:** `perf(web): mobile performance pass [T-9.10]`

### T-9.11 · Accessibility pass
- [ ] **Needs:** T-9.8
- [ ] Keyboard reachable everything, visible focus, labels on icon buttons, colour contrast AA from tokens, reduced-motion respected by the deck, screen-reader names for swipe actions.
- [ ] **Commit:** `a11y(web): accessibility pass [T-9.11]`

### T-9.12 · Observability
- [ ] **Needs:** T-1.22, and a **Sentry account** — not created yet (P-0.6)
- [ ] Sentry in api, worker, web (release = git sha). Alerts: 5xx > 1% for 5 min, webhook signature failures, any job failing 3×, ledger reconciliation mismatch, queue depth > 1,000. Uptime check on `/readyz`.
- [ ] Route D-066's OTP warning, logged at half of `otp_sms_daily_cap`, to the alert channel: until this task it lands only in Fly's logs, which nobody reads.
- [ ] Route D-090's final failure to the alert channel: a minor's files that couldn't be deleted after three tries, logged at error level with the `banned_identities` id. Until this task that log line is all there is, which D-078 says is not enough.
- [ ] **Widen the CSP here, and wire its reporting (D-059):** `connect-src` for Sentry's ingest host, and the CSP's reports (`report-to`, with `report-uri` as the fallback) sent to Sentry's security endpoint. Until then the enforced policy is silent: a violation in production stays invisible until a user complains.
- [ ] **Commit:** `chore(ops): error tracking and alerts [T-9.12]`

### T-9.13 · Security review
- [ ] **Needs:** T-9.9
- [ ] Walk the security checklist in `07-CHECKLISTS.md` line by line; fix findings; run Claude Code `/security-review` on the branch; commission the external review of auth + wallet + payments (budget line in cost doc).
- [ ] **Commit:** `fix(security): review findings [T-9.13]`

### T-9.14 · Backups and restore drill
- [ ] **Needs:** REL-1, which creates production's database (moved from T-2.6 on 3 October 2026)
- [ ] Confirm Supabase PITR on production; restore last night's backup into a scratch project and run the reconciliation query against it. Document the steps in `docs/runbook.md`.
- [ ] **Commit:** `docs(ops): backup and restore runbook [T-9.14]`

### T-9.15 · Go live
- [ ] **Needs:** T-9.13, T-9.14, P-0.5, P-0.7, P-0.8; **T-4.11**: liveness before the first real user (the founder, 4 October 2026); **P-66**: until staging has a Firebase project of its own, its sign-ins land in production's user pool, which is not acceptable after launch (the founder, 3 October 2026, on T-3.14); **P-0.18**: the billing account converted from its free trial, after App Check (P-68), since after launch the trial's end is an outage with no warning (the founder, 3 October 2026); and **P-68**: App Check enforced on Authentication and proved by its effect, before the site is public for sign-in (the founder, 4 October 2026)
- [ ] Production env: real SMS, real Razorpay live keys + webhook URL, real moderation and face match, VAPID keys. Run the pre-launch checklist in `07-CHECKLISTS.md`. Do one real ₹ purchase yourself and refund it, under D-076's rule 3: the refund reverses that purchase's Velas in the ledger in the same step (T-8.2), so money never goes back while its Velas stand.
- [ ] **Write to the waitlist** (T-2.3): its copy promises to tell people when Velora opens near them. Nothing can send bulk email yet, so choose how before launch day, or the list is one we can't write to. A sending service is a new dependency and another processor `/privacy` must name, and its From address needs SPF and DKIM, like the mailboxes (P-0.3). B-14, a second city, writes to it again, by city.
  **DKIM before the first send, or the launch email goes to spam:** our DMARC record says
  `p=quarantine` (P-0.3), so mail that isn't authenticated as `veloraapp.co.in` is sent to spam.
  Set up the service's DKIM for our domain, and prove it with a test send: the receiving server's
  own `Authentication-Results` line must show `dkim=pass` for our domain and `dmarc=pass`, not a
  result relayed inside `arc=pass(...)` (P-0.3 says why).
  **A certificate before any click-tracking subdomain (D-074):** HSTS covers every
  `*.veloraapp.co.in` for two years after a visit, so if the sending service rewrites links through
  a subdomain of ours, that subdomain must serve HTTPS before the first send. Otherwise every link
  in the launch email fails for anyone who has visited the site.
- [ ] **Commit:** `chore(release): v1.0.0 [T-9.15]`

---

# Sprint 10 — Closed beta operations (weeks 16–19)

- [ ] **T-10.1** Invite codes: signup requires a code during beta (`app_config.beta_invite_only`); women's codes unlimited, men's limited per code.
- [ ] **T-10.2** Product analytics (PostHog, EU/India region if available): events `signup_step_completed`, `swipe`, `match`, `thread_opened`, `message_sent`, `knot_tied`, `thread_expired_unanswered`, `purchase_started`, `purchase_paid`, `report_filed`. No message content, no phone numbers. Update `/privacy` (T-2.2) to say what it collects and where it goes. Widen the CSP here for the provider's script and connect hosts, deliberately (D-059).
- [ ] **T-10.3** Metrics queries for the weekly review: D1/D7 retention, thread → knot rate, % threads expiring with zero replies, paying conversion (men), revenue per paying user, reports per 100 users, active gender ratio.
- [ ] **T-10.4** Price test: variant A (₹1,500 / 25 Velas) vs B (₹999 / 25) assigned 50/50; compare revenue per paying man after 3 weeks.
- [ ] **T-10.7** First-thread-free test (risk R1 in `09-RESEARCH.md`): half of new men get their first thread free. Measure paying conversion, threads per man, and revenue per man — not just the free-thread take-up.
- [ ] **T-10.5** Moderator runbook: report handling per reason, SLA, escalation (minor suspected → immediate ban + preserve evidence), canned replies.
- [ ] **T-10.6** Feedback loop: in-app "Send feedback" → `feedback` table; weekly triage into Proposed tasks.

---

# Backlog — after beta (Sprint 11+)

Each becomes a full task with steps when it's pulled in.

| ID | Feature | Notes |
|---|---|---|
| B-1 | Voice calls (knots only, 4 Velas/min, first 60 s free) | Agora Web SDK, server-minted tokens |
| B-2 | Video calls (10 Velas/min) + live frame moderation | biggest cost line — check unit economics first |
| B-3 | Vibe Room (3-min anonymous text, mutual reveal → thread) | needs strong moderation |
| B-4 | Boost (30 Velas / 30 min) | ranking multiplier |
| B-5 | Who viewed you (15 Velas reveal) | `profile_views` already recorded in T-6.3 |
| B-6 | Wink (2 Velas) | |
| B-7 | Paid incognito | |
| B-8 | Daily streaks | |
| B-9 | Rewarded ads | needs an ad network that supports web rewarded |
| B-10 | Auto top-up | needs saved payment mandate |
| B-11 | View-once photos | |
| B-13 | Hindi UI | `hi.ts` alongside `en.ts` |
| B-14 | Second city | |
| B-15 | Native Android (React Native + Expo) | only if beta gates are met. **Before listing:** Velora Studios LLC holds VELORA as a US mark for software and polices it, so a listing in the US store could draw a complaint (P-0.1, D-015) |
| B-16 | **Closure kit for knots** — "End chat" with a reason, closure message to the other person, and a gentle nudge after 48 h of no reply | answers C4/R2 in `09-RESEARCH.md`; cheap and hits the most emotional complaint |
| B-17 | **Date safety kit** — share plans with a friend, check-in timer, emergency contact | strongest women-side differentiator for India (C5) |
| B-18 | **Profile prompts** — 3 of ~20 short questions instead of one about field | fewer bots, better openers (C2/C7) |
| B-19 | **Visibility transparency** — a plain-words page on how ranking works; never throttle reach to sell boost | answers R3; keep the fraud `shadow` band fraud-only |

---

# Timeline

15 weeks full-time to go-live (Sprints 1–9), then 4 weeks of beta. At 2–3 hours a day, expect
roughly double. Re-estimate after Sprint 2 using your real pace.

---

# Proposed tasks

Claude Code adds items here instead of doing unplanned work. Format:
`- [ ] P?-NN · short title — why it's needed — found during T-x.y`

- [ ] P-01 · Decide the Postgres image for Apple Silicon — `postgis/postgis:16-3.4` publishes no
  arm64 manifest, so it runs under emulation on the dev Mac. It works, but it is slow, and T-1.5
  targets `make test` green in under 10 s. Either accept the cost, switch to an arm64 PostGIS
  image, or build one — needs a D-entry either way — found during T-1.2
- [x] P-02 · Record the MinIO registry and pinning in `01-DECISIONS.md` — `minio/minio` on Docker
  Hub is no longer publicly pullable, so the stack pulls from `quay.io/minio/*` at pinned RELEASE
  tags. The tag also matters because newer MinIO community builds drop the web console that T-1.2's
  acceptance depends on — found during T-1.2
  **Settled by D-086, 4 October 2026 (T-4.1):** MinIO is archived and quay.io withdrew its images
  too, so the local S3 is now SeaweedFS, pinned by version and index digest; D-086 records the
  registry, the pinning and why.
- [x] P-03 · Decide the response-class strategy — FastAPI 0.141 deprecates `ORJSONResponse`
  ("FastAPI now serializes data directly to JSON bytes via Pydantic"), but T-1.3 specifies orjson
  responses, so every error response currently emits a `FastAPIDeprecationWarning`. Either keep it
  and silence the warning, or drop `default_response_class` and keep orjson only where we serialise
  by hand. Worth settling before T-1.20 turns warnings into CI noise — found during T-1.3
  **Resolved in T-1.6:** moved off `ORJSONResponse` (handlers use `JSONResponse`; routes serialise
  natively via Pydantic), orjson removed, D-038 amended. 21 warnings → 0.
- [ ] P-04 · Exception logging may leak values — tracebacks currently log exception messages
  verbatim, which can carry row values or tokens once real data exists. Violates CLAUDE.md rule 15.
  Found during T-1.3.
- [x] P-05 · `create_app(settings)` does not reach the database or Redis — the lifespan calls
  `get_engine()` / `get_redis()`, which read the global `get_settings()`, so settings passed to
  `create_app` drive CORS, logging and docs but not the connections. Verified: `create_app` given
  `velora_test` connected to `velora`. A T-1.5 harness passing test settings would silently run
  against the dev database. Fix with a test, and add the missing test for `get_session`.
  **Fix before or at the start of T-1.5.** Found in review of T-1.4.
- [ ] P-06 · Harden the public `/readyz` — it is unauthenticated and unthrottled, and each call
  checks out a pooled Postgres connection and hits Redis, so a flood during a slow-database incident
  can hold connections up to 2 s each and starve real requests. It also tells anyone which
  dependency is down. Rate-limit it with the rate-limit work, and decide whether production should
  hide per-dependency details before T-1.22 exposes `api.velora.app`. Found in review of T-1.4.
- [ ] P-07 · Harness mode for concurrency tests — the `db` fixture is one session inside one
  rolled-back transaction, so concurrent requests through it fail (measured: 5 concurrent requests →
  `[200, 500, 500, 500, 500]`, `InvalidRequestError`), and row locks inside a single transaction never
  contend anyway. The 🔒 tests #1–#3 in `06-TESTING.md` (wallet concurrency and idempotency, T-5.4;
  webhook idempotency, T-8.2) need genuinely committed transactions on separate connections, with
  the tables truncated afterwards. **Needed before T-5.4.** Found in review of T-1.5.
  **Note from T-1.12:** truncation won't work — `ledger_entries` refuses UPDATE, DELETE *and*
  TRUNCATE, and `payments` refuses DELETE and TRUNCATE. Decide the cleanup in T-5.4, where the
  constraint is felt: a throwaway database per run, or fresh user ids per run (production never
  deletes from the ledger either).
  **Folded into T-5.4, 3 October 2026; tick it there:** fresh men per run, never deleted, every
  assertion scoped to them (06-TESTING). A database per run is P-55's.
- [ ] P-08 · `TEST_REDIS_URL` override — `TEST_DATABASE_URL` can be overridden but the test Redis
  is fixed at `127.0.0.1:6379/1`. If T-1.20's CI runs Redis anywhere else, the harness reports the
  stack unreachable and CI hard-fails by design. Add the override alongside T-1.20. Found in review
  of T-1.5.
  **Narrower since P-55:** each run's Redis database is its slot's, 2 to 15, so runs no longer share
  one; the host is still fixed at `127.0.0.1:6379`, which is where CI runs Redis.
- [ ] P-09 · Run gitleaks in CI — the pre-commit hook only protects clones that ran `make hooks`,
  and `git commit --no-verify` skips it. T-1.20's CI steps list ruff, mypy and pytest but not
  gitleaks, so nothing server-side enforces checklist E's "no secrets in repo". Add a
  `gitleaks git` step to T-1.20's `api` job. Found in review of T-1.6.
  **Moved:** now a step in T-1.20 — tick this with T-1.20.
- [ ] P-10 · Hooks must work from GUI git clients — the ruff and mypy hooks call `uv` by name. VS
  Code's Source Control panel (which the user commits from) and other GUI clients run hooks
  without the shell profile, so `uv` may not be on `PATH` and every commit fails. Resolve `uv`
  robustly (absolute path or a wrapper that locates it) and test a commit from VS Code. Found in
  review of T-1.6.
  **Moved:** now a step in T-1.20 — tick this with T-1.20.
- [x] P-11 · Test DB stamped at a revision the checkout doesn't have — every task works on its own
  branch, and from T-1.8 each adds migrations. Run the tests on a branch with a new migration, switch
  to one without it, and `velora_test` still records that revision: every database test then errors
  with `ResolutionError: No such revision`. Happened for real during T-1.7. `velora_test` is
  disposable, so the harness should detect an unknown stamp and rebuild the schema (drop and
  recreate `public`, migrate to head) rather than fail. Until then, recover with
  `make infra-reset`. Found during T-1.7.
  **Settled by P-55, 3 October 2026:** a run's database is dropped and created empty whenever the run
  takes its slot, then migrated from nothing, so no stamp outlives the run that wrote it. P-55's
  `test_a_slot_starts_empty_whatever_its_last_run_left` proves a previous run's committed table is
  gone, and goes red when the drop is removed.
- [x] P-12 · Drop `typing.Union` from the revision template — `api/alembic/script.py.mako` imports
  `Union`, the post-write ruff hook rewrites the annotations to `X | Y`, and T-1.7's F401 exemption
  for `alembic/versions/*` then keeps the now-unused import in every new revision. Write the
  template with `|` and no `Union` import. Found during T-1.8 (removed by hand there).
  **Done:** template now imports `Sequence` from `collections.abc` and writes `str | Sequence[str] | None`;
  a generated revision has no `Union` and passes strict mypy and ruff.
- [x] P-13 · Public photos must have a position — `ck_photos_public_position_range` is
  `kind <> 'public' OR position BETWEEN 0 AND 5`; with `position` NULL, `BETWEEN` is unknown and
  Postgres passes a CHECK on unknown, and the partial unique index treats NULLs as distinct. So any
  number of slot-less public photos can be inserted, though 03-SCHEMA.md ("0–5 for public; 0 =
  main") implies every public photo holds a slot. Needs a **new** migration now that T-1.9 is
  merged (rule 11): `… OR (position IS NOT NULL AND position BETWEEN 0 AND 5)`, plus a test.
  **Before T-4.x (photo upload).** Found in review of T-1.9.
  **Done:** migration `36af56c36916` recreates the check with `position IS NOT NULL AND …`;
  a public photo with no position is now refused (`23514`), other kinds still need none.
- [x] P-14 · Say `thread_hours`, not "24h" — T-1.10's note in 03-SCHEMA.md (threads) and the
  `threads` model docstring say every way into `active` sets "a fresh 24h", but the lifetime is
  `app_config.thread_hours` (seeded 24). Reword both so T-7.x reads the config instead of copying
  a literal (checklist A). The CHECKs don't depend on the value. **Before T-7.x.** Found in review
  of T-1.10.
  **Done:** both now name `app_config.thread_hours` (seeded 24).
- [ ] P-15 · Bound `messages.body_raw` and `duration_s` (optional) — `body` is capped at 2000
  characters but `body_raw` is unbounded, and `duration_s` accepts 0 or negative seconds. API input
  validation (T-7.x) is the primary bound; matching CHECKs would be defence in depth. Needs a new
  migration now that T-1.10 is merged (rule 11). Found in review of T-1.10.
- [ ] P-16 · Decide whether unblocking keeps history — `blocks` is one row per pair with no
  history, so unless T-9.1 designs otherwise, unblock is a `DELETE` and the fact that A blocked B is
  gone. Rule 12's explicit list doesn't name blocks, but its principle does ("nothing is hard-deleted
  that moderation may need"), and "blocked by many people" is a fraud and moderation signal. Options:
  soft-unblock (`unblocked_at`, primary key replaced by a partial unique index) or accept the loss.
  Needs a new migration (T-1.11 is merged). **Before T-9.1.** Found in review of T-1.11.
- [ ] P-17 · Refuse DELETE and TRUNCATE on `messages` and `reports` — rule 12 names messages,
  reports, ledger and payments as never hard-deleted. T-1.12 enforces it in the database for the
  ledger and payments (`refuse_change()`, `restrict_violation` 23001); `messages` and `reports`
  were merged earlier without it. Reuse `refuse_change()` in a new migration (rule 11). Clearing a
  chat stays one-sided (`thread_clears`), so no legitimate path deletes messages. Found during T-1.12.
- [x] P-18 · App connects as a least-privilege database role — T-1.12's guards (append-only ledger,
  never-deleted payments) and T-1.13's (append-only `audit_log`) are triggers: they stop application
  bugs, not a privileged role. Proven on the ledger, and again on `audit_log` in review of T-1.13:
  as table owner or superuser, `SET session_replication_role = replica` or `ALTER TABLE … DISABLE
  TRIGGER` lets a `DELETE` straight through. If the API connects to Supabase as the owning role, an
  injection or stray script has those bypasses. The API must use a role that doesn't own the tables
  and can't `ALTER` them or set `session_replication_role`; migrations run as the owner. Its tests
  cover every guarded table. **Before T-1.22.** Found in review of T-1.12.
  **Moved:** now two steps in T-1.22 — tick this with T-1.22.
- [x] P-19 · Namespace ledger idempotency keys per user — `ledger_entries.idempotency_key` is unique
  across all users, and money routes accept a client `Idempotency-Key` header (02-ARCHITECTURE §3).
  Stored raw, two users sending the same key collide: the second user's genuine debit is refused —
  or, if the service reads a unique violation as "already applied", reported as paid when it wasn't.
  `wallet.service` must store a namespaced key, e.g. `{user_id}:{operation}:{client key}`.
  **Design into T-5.x.** Found in review of T-1.12.
  **Folded into T-5.1, 3 October 2026; tick it there:** the key is `{user_id}:{reason}:{event}`,
  built by the wallet module (D-077).
  **Settled by T-5.1, 3 October 2026:** `wallet/rules.py`'s `key_for()`; two men with one event both
  apply (`test_two_people_with_one_event_both_apply`), red when the key drops the user.
- [ ] P-20 · Audit automated actions as a system user — ruled in T-1.13: `audit_log.actor_id` is
  NOT NULL, because null could not tell "the system did it" from "a bug forgot to set it", and the
  system user is created when auto-freeze first needs it, by T-9.2. T-9.2's text says neither that
  auto-freeze writes `audit_log` nor that the user must exist; the ruling lives only in 03-SCHEMA §8
  and the `AuditLogEntry` docstring. T-9.2 adds a data migration creating the user — it must never
  log in or appear anywhere users are listed — and writes each automated freeze to `audit_log` as
  it. **Fold into T-9.2.** Found in review of T-1.13.
- [ ] P-21 · Correct two comments — the `PushSubscription` docstring calls `p256dh` and `auth`
  "secrets": `auth` is a shared secret, but `p256dh` is the browser's public key. The comment above
  `test_updated_at_triggers_are_on_exactly_the_mutable_tables` says "five mutable tables"; it has
  been wrong since T-1.10 and the set is now 17. Comments only. Found in review of T-1.13.
- [x] P-22 · Commit the prototype to the repo — it is "the visual reference for every screen"
  (08-DESIGN) and the source for T-1.15's 20 dev profiles, T-1.19's UI primitives, T-2.1's landing
  page, T-3.11's onboarding screens and T-8.7's store sheet, but it has never been in the repo or its
  history. T-1.14 had to ask for the interests list for the same reason. Suggested home:
  `docs/prototype/`. **Before T-1.15.** Found during T-1.14.
  **Done:** committed as `docs/prototype/velora-prototype-reference.html`. It predates the Velora
  rename, so it says "Knot": the screens and flows are the reference, not the name.
- [ ] P-23 · Define what a variant-B man sees in `GET /packs` (T-8.1) — T-1.14 seeds variant B as
  one row, `entry-25` (25 Velas, ₹999). Read literally, "active packs for the user's price-test
  variant" gives a B user a one-pack store. What D-005 describes is A's ladder with the entry pack
  in place of `pack-25`. Decide in T-8.1, with a test that B sees four packs. Found during T-1.14.
- [ ] P-24 · Make the catalogue columns NOT NULL — `areas.city`, `areas.name`, `areas.centroid`,
  `interests.slug` and `interests.label` are nullable (T-1.9). A catalogue row with no name means
  nothing, and nullable unique keys (`(city, name)`, `slug`) don't stop duplicate NULLs, so a
  re-run could duplicate such a row. The T-1.14 seed sets them all. New migration (rule 11).
  Found during T-1.14.
- [x] P-25 · Intent becomes a multi-select catalogue, the same shape as interests — interests are
  who you are; intents are what you're looking for. **Do right after T-1.14.** Its own migration,
  because T-1.8 and T-1.9 are merged (rule 11).
  - Drop `profiles.intent` (and its index `ix_profiles_intent`) and the `intent_t` enum.
  - Add `intents` (`id smallint pk, slug text unique, label text`) and `profile_intents`
    (`user_id, intent_id, pk(user_id, intent_id)`).
  - Seed 10, in sentence case like interests (both show as chips on the same profile): Something
    serious, Long term, Situationship, Casual dating, Just one night, No strings attached, Open
    relationship, Discreet, Friendship, Go with the flow.
  - Users pick 1 to 3, enforced in the service.
  - Update 03-SCHEMA, 04-API (`POST /me/seeking` takes a list), and the T-3.6 and T-6.2 steps,
    since discovery filters on intent.
  - Also touches (found while filing): 04-API `GET /discover`'s `intent=` param and T-6.2's `Card`
    (one `intent` today); T-6.6 search ("city/intent/interest matches"); T-6.9's filter sheet;
    T-3.11's "seeking + intent" screen; 08-DESIGN's intent badge; 02-ARCHITECTURE §8's query
    sketch; and in code `Intent` / `PG_ENUMS` in `app/core/enums.py`, whose test expects 20 enums.
  **Done:** migrations `edf91547331e` (schema) and `c4193b88d395` (the 10 intents); decision
  recorded as D-041, with `GET /intents` (🔐, T-3.6) added to 04-API.
- [ ] P-26 · Catalogue labels on screen come from `en.ts`, keyed by id — D-033 puts every
  user-facing string in `web/src/i18n/en.ts`, but 03-SCHEMA calls `gifts.label` "shown in UI", and
  `GET /gifts` returns `label` (04-API), and `GET /interests` will. **Resolved:** the database
  label is the admin-facing name and the fallback; the UI reads `en.ts` keyed by id. That is what
  lets Hindi work later without a data migration. Applies to `gifts.label`, `interests.label` and,
  after P-25, `intents.label`. Reword 03-SCHEMA's notes on those columns to match; the tasks that
  show them — T-3.12's interests picker, T-6.8's profile chips, T-8.10's gift sheet, and P-25's
  intent screens — add the `en.ts` entries and read them. Found during T-1.14.
- [ ] P-27 · Consider Indian classical music in the interests catalogue — the 24 have Indie music
  and Old Hindi cinema but nothing classical, and a prototype profile needed it: Kavya's about
  opens "Trained in Carnatic vocal since I was six", and T-1.15 has to replace her "Carnatic" tag.
  Adding it is a data migration; existing ids stay fixed, so it would take id 25. Found while
  planning T-1.15.
  **Reconsider the catalogue with the city, not before it** (the advisor directing T-1.15,
  Claude in a separate chat): once P-38 moves
  the launch city to Phagwara, Carnatic stops fitting anyway, and Punjabi music is the gap that
  matters there. Until then, the seed's Kavya carries Indie music in its place.
- [x] P-28 · Test that `theme-color` equals `--chrome` — `<meta name="theme-color">` can't read a
  CSS variable, so `web/src/styles/theme-color.ts` holds the literal `#141113`: the one documented
  exception to rule 14 (08-DESIGN §1). The day `--chrome` changes in `tokens.css`, that copy drifts
  and nobody notices. **After T-1.19** (vitest): a test that reads `tokens.css` and asserts
  `THEME_COLOR` equals `--chrome`. Found in T-1.17.
  **Done in T-1.19:** `web/src/styles/theme-color.test.ts`. Proven both ways: it fails when the
  copy is one digit off, and passes once it's restored.
- [ ] P-29 · Reject spacing values that aren't on the scale. 08-DESIGN §3's spacing scale was
  settled in T-1.19: 2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 20 · 24 · 32 · 40 · 56 px. The prototype's
  32 one-off values (18, 22, 26, 28, 36, 48, 64) are to be rounded when their screens are built,
  but nothing enforces that — the same gap P-28 closed for theme-color. Extend the
  `colours-only-in-tokens` pre-commit hook (same hook, same `pygrep` pattern, same `^web/src/`
  scope) to also reject Tailwind padding, margin, gap and space utilities, in every axis and side
  form, whose value is off the scale. That covers both arbitrary values (`p-[18px]`) and off-scale
  steps (`mt-7` is 28 px, `gap-4.5` is 18 px, `p-9` is 36 px). Prove it both ways: it flags
  those, and passes `p-3.5`, `gap-2.5` and `px-0.5`. Found in T-1.19.
- [ ] P-30 · Keep `/admin` off the public internet until it is gated. **Due before T-1.22.**

  **The web gate on `/admin` is UX, not protection.** Anyone can download the page's JavaScript,
  and the Next.js server never sees a session there: D-024 keeps the access token in browser
  memory, and checklist E scopes the refresh cookie to `/v1/auth`. The only thing guarding admin
  data is the API's role check. Every `/admin/*` endpoint must carry its own
  `require_role(...)`; never ship one on the strength of the page gate.

  Why now: `web/src/app/admin/page.tsx` is a placeholder that returns 200 from the production
  build, and T-1.22 puts that build on a public staging URL. The plan gates the admin API (T-9.5),
  but nothing gates the web route. T-3.10's gate covers `(app)` only, and T-2.4's `robots.txt`
  disallow only asks crawlers to stay away — it also advertises the path. Two parts:
  - **Before T-1.22:** `/admin` returns 404 outside `next dev`, using the allowlist `/dev/ui` uses
    (`notFound()` unless `NODE_ENV === "development"`), with a test. Check the staging 404's
    *body*, not just its status: in T-1.19 a 404 still carried the page's `metadata` title.
  - **In T-9.5, replacing the gate above:** the web `/admin` renders only for
    `role in (moderator, admin)`, read through `useMe()`, and anyone else gets the 404 page. It can
    only be a client-side check (see above), so it is there for the user, not for security.

  Found while closing T-1.19.
  **Moved:** the 404 is now a step in T-1.22, and the role gate a step in T-9.5 — tick this with
  T-9.5.
- [x] P-31 · Stop serving the API schema and docs outside local. **Due before T-1.22.**
  `create_app()` serves `/openapi.json` and `/docs` unless `ENV` is `production` — a blacklist,
  so staging serves both, with the full schema. Checked in T-1.18: `local` and `staging` return
  200 with every path; `production` returns 404 with no schema in the body. T-1.22 makes staging
  public, and a public schema of the wallet, payment and admin routes is free reconnaissance.
  Since T-1.18 nothing needs the endpoint: `make types` reads the schema offline (D-043). Make it
  an allowlist, served only when `ENV == "local"`, and test both `staging` and `production`:
  `/openapi.json` and `/docs` return 404, and the bodies contain no schema. Found in T-1.18.
  **Moved:** now a step in T-1.22 — tick this with T-1.22.
- [x] P-32 · Keep `api/.env` out of every image — a secrets leak, not a config problem.
  **Due with T-1.22's Dockerfile.** Docker's build context ignores `.gitignore`, so building from
  `api/` copies a developer's `api/.env` into the image unless it's excluded. That bakes the JWT
  secret, the database password and every provider key into an image pushed to Fly's registry.
  Docker keeps deleted files in earlier layers, so removing the file later doesn't remove the
  secrets: once pushed, every one of them must be rotated. It also sets `ENV=local` inside the
  image, which switches D-045's check off and allows fake payments and fake sign-in. Add
  `api/.dockerignore` excluding `.env*` before the first image is built, and a CI check that the
  built image contains no `.env` in any layer. Found in T-1.21.
  **Moved:** now a step in T-1.22 — tick this with T-1.22.
- [x] P-33 · Put staging's web and API on one site, or sign-in can't keep a session there. **Due
  before T-2.3**, where the founder slotted it on 2 October 2026: built between tasks while nothing
  is in flight, so T-2.3 is built once, against staging's final addresses. On T-2.3's and T-3.4's
  Needs lines. **Needs:** the nameservers on Cloudflare (P-0.3).
  Staging's web is `*.vercel.app` and its API `*.fly.dev`: different sites, so D-024's
  `SameSite=Lax` refresh cookie never flows between them. Refresh and logout (T-3.4) could then
  only be tested locally.
  **The fix, approved 2 October 2026:** web at `staging.veloraapp.co.in`, API at
  `api.staging.veloraapp.co.in`, both DNS records DNS-only. The API nests under the web's name so
  staging's CSRF cookie, scoped to `staging.veloraapp.co.in`, never reaches production (D-055).
  The old address, `velora-staging-black.vercel.app`, redirects to the new one: left serving, it
  would be a live URL that looks like our product while CORS quietly refuses its API calls, and
  it's in old docs. Staging's `COOKIE_DOMAIN` stays unset until T-3.3 sets it.
  **Unblocked 2 October 2026:** the domain is bought (P-0.3, D-015), ahead of the trademark search
  (P-0.1), so a rename forced by that search would mean buying again.
  **Cookie scope settled:** staging's subdomains are the same site as production's, so a site-wide
  production cookie would reach staging. The refresh cookie is host-only on each API host
  (D-054), so neither environment's reaches the other; both cookies are named for their
  environment (D-055), so production's and staging's never collide.
  **Its own check can't prove a cookie flows:** nothing sets one before T-3.3. T-3.14's Done-when
  is that proof, a session surviving a reload on staging. Found planning T-1.22.
  **Done, proved by deploy run 36995339160** (commit `017f71a`, 2 October 2026): its smoke job,
  pointed at `https://api.staging.veloraapp.co.in` and `https://staging.veloraapp.co.in`, passed
  every check, including that the web is our build calling the new API and that CORS allows the
  new origin. Both certificates are Let's Encrypt's and verify; both records are DNS-only CNAMEs.
  Run by hand by Claude the same day, the check passes on that pair and fails on both old
  addresses: the old web address, which now 308-redirects to the new one (9 failures, CORS among
  them), and the old API address, which the new build doesn't call (1 failure). That the cookie
  flows is still T-3.14's to prove.
- [ ] P-34 · Move local and CI to Postgres 17, closing the gap with Supabase (D-047). Staging runs
  Postgres 17.11 with PostGIS 3.3.7; local and CI run 16 with PostGIS 3.4. Switch
  `infra/docker-compose.yml`, and with it CI (which starts the same compose services), to a pinned
  `postgis/postgis:17-*` image, run the full suite, and update CLAUDE.md's stack row. **This closes
  the gap, not eliminates it:** the `postgis:17` images ship PostGIS 3.5, not Supabase's 3.3, so
  PostGIS behaviour is only ever verified on staging. Consider matching Supabase's layout too — the
  extensions in an `extensions` schema rather than `public` — since that difference hid the bug
  `67e81c6c203d` fixed. Best done before discovery leans on PostGIS (T-6.2). Found setting up
  staging in T-1.22.
- [x] P-36 · Decide where the API and worker run, now that Fly won't provision in Mumbai. **Blocks
  T-1.22's Done-when. The decision is open, and the founder makes it fresh, not against a deadline.**
  - **What Fly said** (deploy run 36793830288, 2026-10-01 00:01 UTC, request ID
    `01M3TC93PM16F2PE40187YC8D7-iad`): "Region bom is deprecated and cannot have new resources
    provisioned. Please consider using an alternate region such as sin". `fly platform regions`
    (flyctl 0.4.110) no longer lists `bom`.
  - **Temporary or permanent is not confirmed.** The wording isn't Fly's capacity error, which reads
    "could not find a good candidate…", so waiting a day probably won't help. But Fly hasn't
    announced it: its region-consolidation post lists Mumbai as an active region, not among the
    retired ones. And in September 2025 a different `bom` refusal ("…organization is on a legacy or
    non-paid plan") turned out to be a Fly bug, fixed after a community post. **Next step: ask Fly
    support whether `bom` is retired for good or refused for this account, quoting the request ID.**
  - **Constraint:** Indian users' data (photos, phone numbers) stays in India until the DPDP lawyer
    session (P-0.7) says otherwise. Moving to Singapore is a legal and positioning question, not a
    latency tradeoff, and it's off the table for now. If `bom` is gone for good, the founder leans
    towards another host in Mumbai for the API and worker (for example AWS `ap-south-1` or Google
    Cloud Run `asia-south1`). That gets decided properly, with WebSocket support (D-025) checked,
    and recorded as a decision superseding D-023's region.
  - **Staging as it stood when this was filed** (it has deployed since; see T-1.22):
    - Supabase (Mumbai) is migrated to head.
    - Fly app `velora-api-staging` has five staged secrets, a shared IPv4 and a dedicated IPv6, and
      no machines.
    - Vercel project `velora-staging` exists but hasn't been deployed.
    - R2 isn't enabled.

    Until this is settled, every push to `main` runs `deploy.yml`, which migrates and then fails at
    its `api` job. That's harmless, but expect the red run.

  Found during T-1.22's first deploy.
  **Decided (D-048):** the API and worker run on Fly in Singapore; Postgres and Redis stay in Mumbai.
- [ ] P-37 · Give the staging smoke check a new identity marker before the web's providers move
  off marketing pages. **Due in whichever task moves them.** Worst case: every deploy's smoke
  check fails with a misleading cause ("another site at that URL, or NEXT_PUBLIC_API_URL unset"),
  and the quick fix is to weaken the check, which reopens the hole where another company's site
  passed for our staging (T-1.22). The check passes because `/`'s scripts contain the API's URL,
  and they do only because the root layout mounts `QueryProvider`, which imports `src/lib/api.ts`.
  A task that moves the providers to the `(app)` and `(auth)` layouts, for example to make the
  landing page lighter, must replace the marker in the same commit with one that only our build
  carries, and prove it both ways: it fails against another site and passes against ours. The
  coupling is also written above the check in `scripts/staging-smoke`.

  Found while planning T-2.1.
- [ ] P-38 · Seed Phagwara's areas, replacing Bengaluru's. **Due before T-4.10** (on its Needs
  line). **Needs P-65 first:** this is the next migration in the plan, and its deploy reads back
  what it did. Worst case: someone in Phagwara who denies location access is offered a list of
  Bengaluru neighbourhoods, so their area, and every distance shown to them, is wrong. D-013 is
  now Phagwara, but the reference-data migration seeded 40 Bengaluru neighbourhoods as the
  decision's old default, and `make seed`'s profiles sit in Bengaluru localities. A new data
  migration replaces the areas (never an edit of the merged one, rule 11), and the dev seed's
  localities follow. Label the centroids with who drafted and who reviewed them, as T-1.14's were.

  The registered office is in Hajipur, and that's deliberate (D-058): these areas stay
  Phagwara's, the launch city. Don't make the two agree; a test in `legal.test.ts` says why.

  **The migration must fail with a message, not a bare foreign-key error (from T-1.15).** On a
  seeded dev database, 22 profiles point at Bengaluru areas (`area_id`, `on delete restrict`),
  so removing those areas raises a restrict violation that says nothing about why. Before it
  removes anything, the migration counts profiles whose area it would remove and, if there are
  any, stops with a message naming the fix: on a dev database that's the seed, so `make
  infra-reset`, then `make infra-up migrate seed` once `api/seed/data.py` has moved. Anywhere
  else it's real users, whose areas need moving, not deleting. Move the seed in the same task:
  its 14 localities, `AREA_CITY` in `api/seed/run.py`, and the about texts that name Bengaluru
  or places near it (Ananya's, Sanya's, Siddharth's), for the founder to review.
  `SCATTER_RADIUS_M` (750 m) is under half the gap between Bengaluru's two closest centroids; a
  test fails if any profile lands nearer another area's centroid, so check it against Phagwara's.
  Reconsider the interests catalogue in the same task (P-27): Punjabi music is the gap there.

  Found while planning T-2.2.
- [ ] P-39 · Delete the Firebase user right after sign-in. **After T-3.14 works plainly.** Worst
  case without it: every user's phone number sits in Firebase's records in the United States for
  as long as the account exists, and up to 180 days after we delete it. Deleting the Firebase user
  straight after the token exchange shrinks that to the sign-in itself. Google's abuse-prevention
  copy stays either way (D-048), so this shrinks the footprint, not the disclosure on `/privacy`.
  Kept out of T-3.14 on purpose: auth is where cleverness causes outages, so sign-in works plainly
  first.

  Found while planning T-2.2.
- [ ] P-40 · Stop uvicorn trusting every proxy's `X-Forwarded-For`. **Before anything reads
  `request.client`.** Worst case: code that reads `request.client.host` gets an address the client
  chose, so a limit, a ban or an audit-log entry built on it can be forged. The image runs uvicorn
  with `--proxy-headers --forwarded-allow-ips '*'`, which fills `request.client` from the leftmost
  `X-Forwarded-For` entry, and the client writes that entry. Nothing reads it today: per-IP limits
  read `Fly-Client-IP` (D-056). Drop `--proxy-headers`, or trust only Fly's proxy, and test that a
  forged header doesn't change `request.client`. Still true after T-3.3: sessions store no address
  (D-067).

  Found in T-2.3.
- [ ] P-41 · Give `Avatar` size classes instead of an inline style. **Before any production page
  renders it.** Worst case: the first page that does shows avatars at the wrong size, because the
  CSP (D-059) blocks the server-rendered `style="width:…;height:…"`; the size never recovers after
  hydration, and the tempting fix, `style-src 'unsafe-inline'`, loosens every page. Today `Avatar`
  appears only on `/dev/ui`, where `next dev`'s allowances cover it. Map its sizes to classes on
  the spacing scale (08-DESIGN §3), and check the page shows no CSP violation.

  Found in T-2.5.
- [x] P-42 · Security headers on the API's responses. **Before T-3.5's `/me`, the first
  authenticated response a browser can cache.** Worst case: a browser or shared cache keeps one
  person's `/me`, threads or messages and shows them later (a shared phone, the back button), or a
  browser sniffs a JSON body as HTML. The web's headers (D-059) cover only the web; the API on Fly
  sends none. Two matter: `X-Content-Type-Options: nosniff` on every response, and
  `Cache-Control: no-store` on every authenticated one. A Starlette middleware in `create_app()`,
  with tests that read both off real responses, a public one and an authenticated one. Low urgency
  until then.
  **Moved:** now a step in T-3.3, since its verify is the first response to carry an access token,
  earlier than `/me` — tick this with T-3.3. **Done in T-3.3.**

  Found in T-2.5.
- [ ] P-43 · Decide `Access-Control-Allow-Origin` on the web's own responses. **Before any
  authenticated content renders.** Worst case: Vercel's blanket `access-control-allow-origin: *`
  reaches production on authenticated responses, telling every site it may read them. Browsers
  refuse credentialed requests against a wildcard, so today it's near enough harmless (the pages
  are public and no cookies are involved), but nobody chose it and it has no place on an
  authenticated surface. securityheaders.com flagged it in the founder's scan (T-2.5): "This is a
  very lax CORS policy. Such a policy should only be used on a public CDN." Claude's HEAD of `/`
  showed it too, before T-2.5. **First establish where it appears:** every response, or only
  prerendered ones. Then set what we want in `web/src/lib/security-headers.ts`, beside the other
  headers, and make the check "exactly these headers, and nothing else" (D-059's amendment): an
  inclusion check can never find a header we didn't want.

  Found in T-2.5's Done-when.
- [x] P-45 · Decide whether `normalize_phone` accepts only mobile numbers. **Decide in T-3.2.**
  Worst case: T-3.2 pays for an SMS, and spends the sender's rate-limit slots, on a number that
  can't receive one. `normalize_phone` (T-3.1) checks that a number is valid, not what type it
  is, so it accepts landlines (`+91 22 2222 2222`), toll-free 1800 numbers and the 140 series
  (libphonenumber 9.0.40 types them `FIXED_LINE`, `TOLL_FREE` and `UAN`; checked by Claude, 3
  October 2026). Sign-in needs an SMS-capable number. Requiring `PhoneNumberType.MOBILE` would
  refuse them up front, with a test each way; Firebase's path (T-3.14) may already refuse them,
  which is worth checking before duplicating it.
  **Decided:** D-070, mobiles only, built in T-3.2 — tick this with T-3.2. **Done in T-3.2.**

  P-44 is skipped on purpose: the advisor directing T-1.15 (Claude, in a separate chat) recalls
  it as T-3.1's PIN pepper, closed there, though no file or commit in the repo names it. Never
  give the number to anything else.

  Found while planning T-1.15.
- [ ] P-46 · Build the MSG91 client. **Needs P-0.4 and P-0.5**: the DLT template and the account.
  Worst case without it: Path B can't send a single code, because T-3.2's `Msg91Sms` raises by
  design (D-066), so switching `AUTH_PHONE_PROVIDER` to `msg91` breaks sign-in outright. Build it
  on httpx against MSG91's own documentation, with the DLT template, tested against a mocked
  transport, then prove it with one real SMS to the founder's own phone. D-064's local guard wraps
  it unchanged. Revisit D-066's limits and cap in the same task (P-0.5).
  **And prove D-066's limits on the real provider, not only the fake** (the founder, 4 October
  2026). They are the only SMS limits that are ours, and they bind only Path B: a Firebase SMS
  never passes through our server (D-035, P-0.18). So far every one is proved against the fake
  alone. The method is Claude's: with `Msg91Sms` wired, show each (5 per phone an hour, 20 per IP
  an hour, 100 an hour per IPv6 /48, 10 per phone a day, the global daily cap) stopping the send
  before MSG91 is called, by counting the requests MSG91's mocked transport receives; then once
  for real, by MSG91's own delivery log: five codes reach the founder's phone in an hour, and the
  sixth is refused before MSG91 is asked.
  **And make a banned number take as long as any other** (T-3.2): send answers a banned number
  exactly as any other but skips the SMS. With the fake, that costs nothing; with a real HTTP call
  to MSG91, a banned number would answer a few hundred milliseconds sooner, and a stopwatch would
  tell whoever asks whether a number is banned. Send the SMS off the request (an ARQ job, or a
  background task) so every number's answer takes the same time, or pad to it; and keep T-3.2's
  `503` for D-064's local refusal, which happens before anything is sent.
  **And keep httpx from logging the number** (found in P-48): httpx logs every request's URL at
  INFO through the stdlib, which reaches Fly's logs. If MSG91's API takes the mobile number in the
  query string, each send would log a phone number (rule 15). Send it in the body, or lower httpx's
  logger, and test it with `captured_logs`.

  Found while planning T-3.2 to T-3.10.
- [ ] P-47 · Give `app_config` its 60-second cache. **With T-6.4**, the first hot path to read a
  setting (the men's daily swipe limit, on every swipe). Worst case without it: a database read
  per request for a value that changes a few times a year. T-3.2's reader
  (`admin.service.config_int`) reads fresh, on purpose for now: its one caller, OTP send's daily
  cap, is rate-limited, and fresh means a lowered cap applies at once. A cache must be per app
  (`app.state`), not per process, or tests that tune a setting would read another test's value.
  Found in T-3.2.
- [x] P-48 · Make `structlog.testing.capture_logs` see every log line in tests. Worst case: a test
  that nothing secret is logged (rule 15) passes having captured nothing. structlog caches a
  logger at first use against the processor list configured then, and every `create_app()` calls
  `configure_logging()`, which installs a new list; `capture_logs` edits only the current one, so
  a logger first used in an earlier test escapes it. T-3.2's tests swap in a fresh logger and
  assert they saw the event they expect; T-3.1's PIN-hash log test relies on test order. Fix at
  the root: configure logging once per process, or keep one processor list and change it in place.
  Found in T-3.2.
  **Done, 3 October 2026:** `configure_logging()` keeps one processor list and changes it in place,
  so every logger, cached or not, reaches `capture_logs`. Proved by shuffling the whole suite (a
  seeded plugin, no new dependency): before the fix, T-3.1's PIN-hash log test failed in 8 of 8
  orders; with T-3.2's fresh-logger workaround switched off, its two log tests and T-3.3's failed
  in 8 of 8 too, loudly only because each asserts an event it expects. After the fix, with the
  workaround removed, all 749 pass in file order and in 8 of 8 shuffled orders. Two tests could never
  fail, asserting only absence on paths that log nothing (T-1.21's OTP check, T-2.3's waitlist
  email check via `capfd`, which can miss a logger bound to an earlier stream); both now use a new
  `captured_logs` fixture whose probes, through structlog and the stdlib, must arrive, and each goes
  red when a leak is planted.
  **Its shuffle plugin was never committed** (found planning T-3.10 to T-3.13, 3 October 2026). So
  "proved by shuffling" above, and "survives a shuffled order" in every report since, can't be
  re-checked from the repo. The fix itself, `configure_logging()`'s one processor list, is in. T-3.13
  commits the plugin, or T-5.1 if it gets there first.
- [ ] P-49 · Colocate the API and the database, and decide which city. **Before Sprint 6**, whose
  discovery pays the split below several times per request. Worst case if it stays: every
  authenticated request costs seconds before any work, in an app whose complaint driver is lag
  (09-RESEARCH C7). The user's own hop is one round trip; the API's to the database are a dozen or
  more per request. Putting the two in one city fixes that whichever city it is.
  - **Why the API is in Singapore (D-048, P-36):** Fly retired Mumbai (`bom`) on 25 September 2026
    and refused new machines there. **Still true:** on 3 October 2026 Fly's own region list (flyctl
    0.4.110) has 17 regions and none in India.
  - **Measured from the staging machine, 3 October 2026,** through the app's own engine and Redis
    client: 165.6 ms per Postgres round trip (D-048 had 165), 165 ms per Redis command, 2,865 ms to
    open a connection, and 993 ms, six round trips, for a pooled request that runs one select
    (checkout, BEGIN, the select, COMMIT). **The per-checkout liveness ping is three of those round
    trips, not one:** asyncpg's ping runs BEGIN, `;` and ROLLBACK, about 495 ms on staging. D-048
    priced it at 165 ms, and it's Locked, so the correction lives here. Cross-checked on staging
    itself: `/readyz` (one pooled checkout and select, and a Redis ping) answers 1.1 s after
    `/healthz`, 6.6 round trips' worth.
  - **Round trips per endpoint,** counted locally by a proxy that delays every packet, and matched
    against each endpoint's statement log: OTP send about 14, verify for a new account about 25,
    refresh about 9, `GET /me` about 17. At 165 ms that is 2.3 s, 4.1 s, 1.5 s and 2.8 s of server
    time. `current_user` alone is about 8 round trips, 1.3 s. P-52 and P-53 take `/me` to about 11
    round trips, still about 1.8 s split as it is.
  - **Unexplained, measured after P-53 deployed (3 October 2026):** from the staging machine,
    staging's own Redis host now answers a TCP connect in 55.5 ms over IPv4 (its PING took 56 ms,
    against 165 that morning), while its Postgres host still takes 164.6 ms over IPv6. Mumbai to
    Singapore can cost about 56 ms; our Postgres path costs three times that, over both of
    Supabase's paths (D-048). Worth one traceroute or a question to Supabase before deciding: at
    56 ms a round trip, the split would cost about 0.6 s per `/me`, not 1.8 s, still far above
    either colocation.
  - **The same city, measured:** from the staging machine in Singapore, a TCP connect to Supabase's
    Singapore endpoint takes 6.9 ms (AWS Singapore 4.0 ms); to its Mumbai endpoint, the control, 171
    ms, which matches the query round trip above. **The user's hop,** from the founder's machine:
    Singapore 92 ms (153 ms an hour earlier, through curl: the routes vary), Mumbai 54 to 58 ms.
  - **Option A, both in Mumbai.** A round trip of about a millisecond (an estimate: no machine there
    to measure from), so `/me` costs about 70 ms in all. It means leaving Fly for the API. **Google
    Cloud Run `asia-south1`** is the realistic one: it rides the Google billing account Firebase
    needs anyway (P-0.12, not done yet). It needs WebSockets checked (D-025), `deploy.yml` and `infra/STAGING.md` rewritten, secrets moved,
    the smoke check repointed, and `/privacy`'s "handled by our servers in Singapore" changed.
  - **Option B, both in Singapore.** Keeps Fly: a new Supabase project in `ap-southeast-1` and Upstash
    in Singapore, by dump and restore. A round trip of about 5 to 7 ms, so `/me` costs about 150 to
    230 ms in all, one user hop slower than A, a hop paid once per request rather than per query.
    **It is the cheapest it will ever be:** staging's database holds the schema, the reference data
    and test waitlist rows, and no users (the seed runs only locally, D-064); nothing is live. Every
    sprint makes it dearer.
  - **What decides whether B is on the table: residency.** Claude's reading of the primary texts
    on 3 October 2026, not legal advice:
    - **D-048's reason was our promise, not the law.** In its words: "Postgres (Supabase) and Redis
      (Upstash) stay in **Mumbai**, so Indian users' data stays in India. Moving it out would take a
      new decision, after the DPDP session (P-0.7)." Its amendment: "'Data stays in India' was our
      own promise, not a legal requirement." And: "Moving the database after launch, with live user
      data, is not [cheap]. Keeping it in Mumbai is what keeps the India option open."
    - **DPDP requires no localisation of ordinary personal data.** Section 16(1) lets the Central
      Government "by notification, restrict the transfer of personal data ... to such country or
      territory outside India as may be so notified": a blacklist, and none has been notified as
      far as Claude found (the repo's last check was September 2026; P-0.7 re-checks). Section 16(2)
      keeps any stricter sectoral law. Rule 15 of the DPDP Rules, 2025 allows transfers, subject to
      requirements the Government may set about making data available to a foreign State. Both
      take effect on 13 May 2027. **The one localisation lever is Rule 13, for Significant Data
      Fiduciaries,** who can be made to keep specified data in India. Velora isn't one; designation
      weighs volume and sensitivity, and a dating app's data is sensitive, so at scale it could be.
      Then data in Singapore might have to come home, at that day's price.
    - **RBI's payment-data storage directive doesn't reach us as a merchant.** The circular of 6
      April 2018, per RBI's own FAQ (questions 1 and 2), binds payment system providers RBI
      authorises and the "service providers, intermediaries, payment gateways, third party vendors
      and other entities" they engage for payment services: Razorpay, not its merchants.
    - **The Vela ledger isn't payment system data.** Velas buy only Velora's own services, have no
      cash value and can't be transferred (D-050), and a gift moves no Velas to its recipient
      (D-016): a closed-system prepaid instrument, which RBI's PPI FAQ (question 7, 22 November
      2022) says is "not classified as a payment system requiring approval / authorisation by RBI
      and are, therefore, not regulated or supervised by RBI". **D-076 (3 October 2026)** tests the
      design against each condition of that exemption, and records what keeps Velas inside it.
    - **The closest call is `payments.raw_webhook`** (T-8.2), which keeps Razorpay's verified payload:
      it can carry the payer's email, phone and UPI ID, all in RBI's own list of payment data. As
      written, the directive binds Razorpay, not us; storing less (ids, amount, status) removes the
      question. A design point for T-8.2 whichever city is chosen.
    - **The binding constraint is our own published page.** `/privacy` says the profile, messages,
      Velas, payment records and our encrypted copy of each number are "stored in Mumbai, India",
      and waitlist emails too. Option B changes that page in the same task, before any data moves.
    - **No lawyer is scheduled.** P-0.7 is the founder's own review ("no lawyer at this stage", 1
      October 2026), though D-048 calls it "the DPDP session" and P-36 "the DPDP lawyer session". So
      B is the founder's call on our own promise, unless he books a lawyer first.
  - **Directed, 3 October 2026: both in Mumbai, before Sprint 4** (the advisor directing T-3.2 to
    T-3.10, Claude in a separate chat; the founder decides, and it stays open until he does). Why
    Mumbai, though Singapore is cheaper today: the latency a person feels includes their own hop, so
    Singapore is two to three times Mumbai end to end, not the few tens of milliseconds the server
    side suggests (from the founder's machine, `/me` would be about 160 to 220 ms against 70 to 90);
    `/privacy`'s "stored in Mumbai, India" is something a woman deciding whether to upload her
    photos can check, a trust asset worth more than the latency; and Rule 13 is the tail risk, so
    moving out now and back later is worse than not moving. Why before Sprint 4: T-4.4 makes the
    worker a second Fly app, so moving now migrates one thing, and after Sprint 4 two, with every
    sprint adding Fly-specific secrets, checks, CI and `infra/STAGING.md` to rewrite. It is on
    T-4.1's Needs line, so `/task` stops there until it's done or decided otherwise.
  - **The three checks the direction asked for, done 3 October 2026:**
    1. **Cloud Run cold starts and cost.** One instance kept warm (`min-instances` 1) has no cold
       start; only instances added for a burst start cold. Our part of a start, the imports and
       `create_app()`, takes about 330 ms on the founder's Mac; Cloud Run adds pulling the image and
       starting the container on one vCPU, unmeasured without an account. Mumbai (`asia-south1`) has
       been on Cloud Run's cheaper Tier 1 since 15 November 2024. For one instance of 1 vCPU and 512
       MiB over a 30-day month, at list prices: **kept warm but idle, about $10** (request-based
       billing's idle rates); **busy all month, about $49** (instance-based billing) **to $65**
       (request-based). An open WebSocket counts as busy, so T-7.4's chat keeps instances busy
       whenever anyone is connected, and T-4.4's worker, which polls Redis all the time, needs an
       always-on instance of its own: about $49 more. So production with chat live is roughly $100
       to $115 a month on Cloud Run, against Fly's roughly $3 to $4 per small machine (published
       rates; flyctl's size list shows no prices), $7 to $8 for an API and a worker. **A Compute
       Engine VM in Mumbai** under the same Google billing account, `e2-small` at $14.69 a month on
       demand (`e2-micro` $7.34), runs the API, the worker and WebSockets flat, with no cold starts,
       at the cost of looking after a VM (OS updates, TLS, the deploy). **What this changes:** the
       warm instance is cheap; WebSockets and the worker are what make Cloud Run the dearest of the
       three. Mumbai stands; the host is the founder's choice between Cloud Run's management and a
       VM's flat price.
    2. **The Postgres-versus-Redis gap is not the pooler.** The API reaches Postgres over Supabase's
       direct connection, IPv6, not its pooler (`infra/STAGING.md`), and the pooler measured 171 ms
       anyway. Both hosts are Amazon's, in Mumbai: from the founder's machine in India, Upstash's four
       addresses answer in 61 to 68 ms, like AWS Mumbai's own 66, so no nearer edge fronts them. The
       gap is Fly's routing from Singapore, which differs by destination and changed during the day:
       165 to 171 ms to every AWS Mumbai address tried (Supabase direct and pooler, AWS's EC2 API),
       while Upstash's fell from 165 that morning to 56. So nothing in our configuration is free to
       recover, and inside Mumbai the detour doesn't exist, so the Mumbai estimate stands. A route
       that moves threefold in a day is one more reason not to depend on it.
    3. **Whether Google can be paid: not confirmed, and only the founder can confirm it.** This
       machine has no Google Cloud CLI to ask with. Google's own page says an Indian billing account
       must complete mandatory identity verification within 30 days or be suspended: an individual
       by PAN or e-Aadhaar through DigiLocker and proof of address, a business by a GST or Udyam
       certificate (P-0.2's PAN and GST are still unconfirmed). Firebase's Blaze plan (P-0.12) needs
       the same billing account, so it is owed anyway. Until a billing account exists and is
       verified, no plan should rest on Google either.
       **Answered 3 October 2026 (P-0.13, closed by the founder):** the account is active, on
       Google Cloud's free trial until 2 January 2027. **So the API must not move onto this
       billing account while it is a trial** (the founder): the trial's end would stop the whole
       API, not just sign-in. On Google, P-49 lands only after P-0.18 converts the account.
  - **Host, directed 3 October 2026: a Compute Engine VM in Mumbai, not Cloud Run** (the advisor
    directing T-3.2 to T-3.10, Claude in a separate chat; the founder decides). Threads and Knots
    are the product, so "busy whenever anyone is connected" is close to always: Cloud Run's roughly
    $100 to $115 a month against the VM's roughly $15 is a different budget, pre-revenue, not a
    trade-off (about ₹1 lakh a year against ₹15,000, the advisor's figures).
    **What the VM costs, accepted, not overlooked:**
    - OS updates, TLS renewal, deploys and restarts become ours. Caddy terminates TLS and renews
      its certificates itself; Docker Compose runs the API, the worker and Caddy, as Compose already
      runs the stack locally.
    - One VM is one point of failure, and a deploy is a restart unless built around: open WebSockets
      drop and clients reconnect (T-7.12). At launch, in one city, with no users yet, survivable.
    - **Revisit when** revenue exists, or when a restart during a live Thread becomes a real
      complaint.
    **Considered and not chosen: DigitalOcean in Bangalore.** Droplets from $6 a month and App
    Platform from $5 a container, with workers, both in Bangalore: managed deploys and TLS would cut
    the ops above. But Bangalore isn't Mumbai, so it is another split: an estimated 15 to 20 ms per
    round trip to Supabase and Upstash (unmeasured: no machine there), paid about 13 times per `/me`
    (11 round trips to Postgres, 2 to Redis), so about 200 to 260 ms of server time, where a VM in
    Mumbai pays about 15 to 25 ms. It doesn't beat Compute Engine clearly, and one Google account
    for hosting and Firebase is worth something on its own. Colocating in Bangalore would mean
    leaving Supabase for DigitalOcean's own Postgres: a bigger move, not this one.
  - **Not decided here.** The founder decides the city and the host; this is the measurement, the
    reading and the advisor's direction. The move is a task of its own and writes the decision
    superseding D-048 (and D-023's region); no D- number is taken before then.
  - **What the move inherits from T-2.6 and must redo** (the founder, 3 October 2026). T-2.6 built
    production's API half on Fly knowing this move would replace it: closing Sprint 2 was worth the
    rework, and `api.veloraapp.co.in` carries no traffic in between, so the DNS change costs
    nothing. The move redoes, for production:
    - the Fly app `velora-api` and its machine, and `infra/fly.api.production.toml`;
    - its secrets, moved with the **same values**: new keys would make every stored phone number
      and PIN unreadable (D-061, D-062);
    - the `api` record at Cloudflare;
    - the `api` and `migrate` jobs in `.github/workflows/deploy-production.yml`, with
      `infra/PRODUCTION.md`'s Fly section and its Fly cost line.

    The web, the release gate, the smoke check and the domains stay.

  Found reviewing T-3.2 to T-3.5, at the direction of the advisor directing them (Claude, in a
  separate chat), who added option B and the residency question.
- [ ] P-50 · Cut the round trips every request pays. **Before Sprint 6 adds routes on
  `current_user`; worth doing wherever the API runs.** Worst case without it: the fixed cost in P-49
  multiplies with every route that inherits it. Measured on 3 October 2026 (P-49's method):
  - `pool_pre_ping` costs three round trips per checkout. Recycle connections by age instead
    (`pool_recycle` below Supabase's and Fly's idle timeouts) and retry a request once on a dropped
    connection: about 495 ms a checkout on staging.
  - **T-3.5 doubled the checkouts:** `current_user` reads the user in a transaction of its own (so a
    service's `async with session.begin()` can follow), and a committed `AsyncSession` hands its
    connection back, so the service checks out again and pays the ping again. One checkout per
    request (bind the request's session to one connection) keeps T-3.5's reason and drops the second.
  - `Me` is four selects after the user row (profile, balance, intents, interests); one query does it.
  - The rate limit and the activity throttle are two Redis scripts per request; one script does both.
  - Sign-up: one query for the ban and the user lookup, the referral code drawn by insert-and-retry
    instead of a check first, the four rows in one statement, no reads back after insert, and the
    code's peek, read and use as one Redis script: about 25 round trips to about 9.
  Each with a test that counts round trips (the delay proxy, or statement and command counts), so a
  change that adds one goes red.

  Found reviewing T-3.2 to T-3.5.
  **Split, 3 October 2026:** the first two items are our own waste, worth fixing whatever P-49
  decides, so they are P-52 (the second checkout) and P-53 (the ping), done now. The rest waits for
  P-49's answer.
  **P-49's answer, as directed (3 October 2026): both in Mumbai.** There a round trip costs about a
  millisecond, so what's left here saves tens of milliseconds a request, not seconds: `/me` is about
  11 round trips after P-52 and P-53. So the rest waits for the move, and after it is done only where
  a route proves slow, measured with `tests/roundtrips.py`. If the founder keeps the split instead,
  it is worth doing at once: at 165 ms a round trip it is most of `/me`'s remaining 1.8 s.
- [ ] P-51 · Decide what a banned number is told. **In T-9.5, where bans are written, or T-9.6.**
  Worst case: a person barred by mistake, or a minor's family, has no way to learn why sign-in stopped
  working, or that grievance@ exists, which the IT Rules' grievance obligations (D-052) assume.
  D-073 records what happens today: on Path B, a number in `banned_identities` is answered like any
  other and its codes simply stop arriving, with no message. On Path A, Firebase's own SMS still
  arrives and the exchange answers `ACCOUNT_BANNED`, which the web can turn into copy naming
  grievance@. Whether Path B's silence is acceptable is this task's question.

  Found reviewing T-3.2 to T-3.5, at the direction of the advisor directing them.
- [x] P-52 · One connection per request: stop the second checkout T-3.5 added. **Now, before
  T-3.6.** Worst case left: every authenticated request checks out twice and pays the liveness ping
  twice, about 990 ms on staging, in every environment, colocated or not. `current_user` reads the
  user in a transaction of its own and ends it, so the route's service can begin another (T-3.5),
  and a session bound to the engine hands its connection back at every commit, so the service
  checks out again. The fix: the request's session checks out one connection at its first query and
  keeps it until the request ends, so later transactions reuse it; a request that never reaches the
  database, a bad token say, still checks out nothing. Proved on the real `get_session` by counting
  pool checkouts, failing with the old session.
  **Done, 3 October 2026:** `core/db.py`'s `RequestSession` opens its connection inside `get_bind`
  at the first query and hands it back from `close`, `reset` and `invalidate`. On the real
  `get_session`: two transactions in a request take one checkout, as do `current_user` and `/me`'s
  route together; a bad token takes none. Every way a session ends returns the connection, between
  transactions too, where only the session knows it holds one (the first version of that test,
  mid-transaction only, missed a leak from `invalidate`). Six weakenings, each red. Measured by the
  delay proxy: `/me` from about 17 round trips to about 14, one liveness ping fewer, about 495 ms on
  staging; single-transaction endpoints unchanged.

  Split from P-50, at the direction of the advisor directing T-3.2 to T-3.10.
- [x] P-53 · Make the liveness ping cheap. **Now, before T-3.6.** Worst case left: `pool_pre_ping`
  costs three round trips on every checkout, about 495 ms on staging (D-048 priced it at 165):
  asyncpg's ping wraps `;` in BEGIN and ROLLBACK for PgBouncer's transaction mode, which we don't
  use (staging connects direct, `infra/STAGING.md`). The fix: no ping for a connection used in the
  last 30 seconds; one idle longer is pinged, and if dead, replaced before the request sees it; and
  the pool hands out its newest connection first, so a quiet pool keeps reusing a warm one. Proved
  by counting the round trips a request makes, and by killing an idle connection's backend and
  seeing the next request succeed.
  **Done, 3 October 2026:** `build_engine` drops `pool_pre_ping`, checks a connection only after
  `CHECK_IF_IDLE_FOR` (30 s) idle, never a new one, and hands out the newest first. A new test
  helper, `tests/roundtrips.py`, counts round trips at the wire, deterministically (a client send
  after the server's answer is one): a warm connection's request is three (BEGIN, the select,
  COMMIT), where `pool_pre_ping` made six; after 30 s idle, seven the first time (asyncpg also
  prepares `;`) and six after. A killed idle connection is replaced before the request sees it; one
  killed within 30 s of use fails one request, then is replaced, pinned by a test as the price.
  Eight weakenings, each red. Found on the way: the kill helper's wait read Postgres's
  `pg_stat_activity`, which keeps one snapshot per transaction, so it sometimes waited on a stale
  answer until it timed out; a fresh transaction per poll fixed it (fifteen runs clean).
  **Measured with P-52, by the delay proxy:** OTP send about 14 round trips to about 11, verify for a
  new account about 25 to about 12, refresh about 9 to about 6, `/me` about 17 to about 11. Most of
  verify's drop is LIFO, not the check: with only LIFO off it is about 21, because a pool handing
  out its oldest connection first kept moving verify to connections that hadn't prepared its
  statements yet. That part is a cold-pool effect; in a long-warm pool the gap closes.
  **Proved on staging, 3 October 2026,** after deploy run 37109881416 (commit `c228739`), read on
  the machine and from outside: a pooled request with one select fell from 993 ms to 497 ms, six
  round trips to three, as the wire count predicted; `/readyz` now answers 535 ms after `/healthz`,
  against 1,097 ms that morning.

  Split from P-50, at the direction of the advisor directing T-3.2 to T-3.10.
- [x] P-54 · Keep D-072's deletion possible once T-8.6 lets a referral code be applied during
  onboarding. **Decided as D-078. The row half before T-4.2, on its Needs line; the file half in
  T-4.2.** Worst case: someone under 18 applies a code before the dob step, then
  gives their date; the referral's row, RESTRICT to `users`, stops the deletion, they get a 500, and
  their account, encrypted number included, stays: the data D-072 exists not to hold. T-3.6 made
  it fail closed (nothing deleted, no hash kept), and a test fails if any key into `users`
  cascades. T-8.6 either refuses `/referrals/apply` until dob is set, or adds its table to
  `UNDERAGE_DELETES` (`api/app/modules/users/repository.py`) with a test. The same goes for any 🔐
  route that writes a row before dob: D-068's step rule already keeps photos (T-4.2) and the selfie
  (T-4.5) behind their steps. Found in T-3.6.
  **A test, not a note** (3 October 2026, at the advisor's direction): every table with a key to
  `users` is now in exactly one of two lists in `users/repository.py`, `UNDERAGE_DELETES` or
  `UNDERAGE_KEEPS`, each kept table with why a user at the dob step can't have a row there and
  whose task writes it. A table added later fails CI, naming D-072, until it is classified; a
  probe table proves it, and a kept table that cascades fails too.
  **What the test can't catch, so this stays open.** Every table already exists: Sprint 1 created
  the whole schema. So the risk is not a new table but a new writer to a kept one before dob is
  set. Four tasks do that unless they're careful: T-4.2 (`photos`; its upload URL has no step
  gate in its text), T-4.5 (`verifications`), T-8.6 (`referrals`, applied "before onboarding
  done") and T-9.2 (`fraud_events` and `fraud_scores`). Each now carries a line saying so.
  **Covering every table literally isn't possible:** `messages`, `reports`, `ledger_entries`,
  `payments` and `audit_log` are never hard-deleted (rule 12), and the app role can't delete from
  them (T-1.22).
  **Decided, 3 October 2026: D-078, the deletion takes everything the app may delete, files
  included** (the advisor, relayed by the founder; a database guard refusing rows before dob was
  rejected). What this task builds:
  - **The row half,** which can land at once: every table the app role may delete from moves from
    `UNDERAGE_KEEPS` to the deletions, under every column that names the user, in an order the
    keys between those tables allow. `UNDERAGE_KEEPS` is then exactly rule 12's five, and the test
    holds it so. The deletion is proved as `velora_app`, as T-3.6's is.
  - **The file half,** D-078's sequence: the storage keys behind the rows read in the deleting
    transaction, before the rows go; the files' deletion enqueued with them after the commit; a
    final failure raised where someone sees it. It lands in T-4.2, the first task to store a file
    behind a user row, since the keys are T-4.2's to define; T-4.5 adds its selfies. The job queue
    arrives with T-4.4, after T-4.2, so T-4.2 decides how the deletion runs until then.
  - The lines on T-4.2, T-4.5, T-8.6 and T-9.2 say what each inherits.
  **Row half done, 3 October 2026:** the deletion takes the user's rows in all 25 tables the app
  role may delete from, under every column that names them, and every row on their threads (another
  user's clear of one), in the order of the keys between those tables; it keeps only rule 12's five.
  Tests hold it to the database, not to a list: every table keyed to `users` is deleted or kept;
  each deleted table's listed columns are exactly its keys to `users`; every one keyed to `threads`
  deletes by thread; the order follows the keys; and the kept set is exactly what `velora_app` has
  no DELETE on, read from its grants. A 🔒 test puts a row naming the minor in every table that can
  hold one (all but `message_unlocks` and `refund_requests`, whose rows stand behind a message or a
  payment, which rule 12 keeps) and finds none afterwards, the other user untouched. Nine
  weakenings, each red. With no file stored anywhere yet, this is the whole protection today. The
  file half is T-4.2's own line, where the first file behind a user row is stored.
  **The count, read from the database on 3 October 2026:** 43 keys into `users`, from 30 tables:
  25 deleted, 5 kept. (A chat report that day said 37 tables; it was wrong, and is corrected here.)
- [x] P-55 · Let two checkouts' test suites run at once. **Next: raised by the advisor on 3
  October 2026, on T-3.10's Needs line, the next task in the plan.** **Until it lands, a green local
  `make lint test` while another session is running is not evidence: only the CI run on the exact
  commit counts (D-044).** CI starts every run on its own services, and that is the only thing that
  kept `main` safe on 3 October. Worst case: a session sees tests fail that nothing in its change broke, and spends
  an hour on them or "fixes" them. Seen on 3 October 2026: T-3.7's username rate-limit test and
  four of T-2.6's OTP rate-limit tests failed in the same minute, because both suites use
  `velora_test` and Redis db 1, and `test_redis` clears every `ratelimit:*` key, so each run wiped
  the other's windows; alone, each passed. The database is shared too: two runs' uncommitted rows
  with the same unique values (`make_user`'s serial phone numbers) wait on each other. Give each run
  its own Redis database or key prefix and its own test database (by worktree, or by a run id),
  with a test that two runs can't see each other's keys. Found in T-3.7.
  **From T-5.1, two more reasons** (3 October 2026):
  - Committed ledger rows can't be deleted: the ledger refuses DELETE and TRUNCATE, and foreign
    keys into `users` are RESTRICT. So a shared `velora_test` collects them until
    `make infra-reset`, and a database per run would end that.
  - A task that breaks a constraint to prove a test catches it hits every session using the
    database, however well its assertions are scoped. T-5.1 and T-5.4 avoid this with a database
    of their own (`createdb`, pointed at by `TEST_DATABASE_URL`). Redis database 1 can't be
    redirected the same way (P-08), so a full run still clears another session's rate-limit keys.

  Found planning Sprint 5.
  **Done, 3 October 2026** (ahead of T-3.10, at the direction of the advisor directing T-3.10 to
  T-3.13, Claude in a separate chat): `tests/infra.py` gives each run a slot, 2 to 15, held for the
  process's life by a Postgres advisory lock on a connection it keeps open, so a crashed or killed
  run frees its slot when the connection closes. The slot is a database, `velora_slot<n>_test`, and
  Redis database `<n>`, dropped, created empty and flushed when a run takes it. `TEST_DATABASE_URL`
  still overrides the database. pytest's header names the slot (06-TESTING).
  - **Before, on `main` at `d9e3c5d`:** one full run passed all 1,089 in 24.9 s; two started
    together failed 45 and 42 (plus 3 errors), T-3.6's rule-15 log test among them. One of those
    runs also failed a peer session's gate run that minute; it ran again, green, after.
  - **After:** two full runs started together passed all 1,093 each; three passed all 1,093 each, on
    slots 3, 4 and 2. One alone: 24.5 s, so no measurable cost.
  - **`tests/test_run_slots.py`, four tests:** this run is on its own slot's database and Redis; a
    second run taken beside it gets another slot and neither sees the other's keys or rows; a slot
    starts empty whatever its last run left; a run killed by SIGKILL frees its slot.
  - **Seven weakenings, each red on its intended assertion:** no lock (always the first slot), one
    database for every slot, one Redis database for every slot, the database not recreated, Redis
    not flushed, the lock released at once (a transaction lock), and the lock's connection closed
    after taking it. Each ran with no bytecode on slots 13 to 15, so a broken harness couldn't
    touch a peer's run; restored and checked by SHA-256. Settles P-11.
  **So the caveat at the top of this entry has expired:** a local run no longer depends on what
  else is running, and is evidence again; the CI run on the exact commit is still the gate (D-044).
  Until it landed, three sessions building that day (T-2.6, T-3.6 to T-3.9, and this one) worked
  around its absence: two saw rate-limit tests fail for one another's runs, and gates were run
  only in quiet windows agreed between sessions by message.
- [ ] P-56 · Refuse a charge whose price changed after it was shown. **For T-7.1,** the first paid
  action a person taps. Worst case: a man sees "Open thread · 5 Velas" and is charged 6, because
  the price changed in between. The server still decides the price (rule 6), and `/terms` says
  prices can change. But charging more than the screen said is the kind of surprise that ends
  trust in a paid product. The client sends the price it showed, and the server refuses with
  `PRICE_CHANGED` if it differs: the value is compared, never used. Deferred from T-5.2, which reads
  prices fresh with no cache. Found planning Sprint 5 (decision 22, with the advisor directing it).
- [ ] P-57 · The app's screens have no visual design. **Before T-6.5,** on its Needs line. Worst
  case: every screen in Sprints 6 and 7 is framed by a shell and built from a prototype that was
  wrong four times in Sprint 5's plan alone, and a one-way door gets designed by accident: the
  refund button, gift's direction, the price list and "credits" for Velas. T-5.6 builds the shell
  provisionally (08-DESIGN). The first task that needs a screen designed stops and asks, rather
  than inventing it from the prototype. Found planning Sprint 5, at the direction of the advisor
  directing it.
- [ ] P-58 · Prove the T-3.x race tests' overlap by what the lock decides. **Before the next task
  that leans on one of these locks.** Worst case: a lock removed by mistake and every test still
  green, because the current tests are timing-based. Each waits up to a second for the other to
  arrive and goes on alone if it doesn't. On a slow machine, code without the lock can pass:
  a false green, worse than no test, since it buys confidence nobody earned. Bring them to T-5.4's
  standard (`f543b0d`): every call inside an open transaction before any takes the lock,
  asserted, then each records whether it waited alone, with no wait that a slow machine can run
  out. Which ones: T-3.4's two refreshes at once, T-3.6's seeking, and T-3.8's interests (the same
  pattern, mine). T-3.9's eight PIN tries prove the cap of five but not the overlap: a counter read
  and written in two statements would pass it whenever the eight happen not to overlap. T-3.7's
  username race isn't timing-based: it fails loudly if the two don't meet. At the direction of the
  advisor, 3 October 2026; found in T-3.6 and T-3.9.
  **The standard's limit, found in T-5.1** (3 October 2026): with the lock in place, "waited alone"
  is decided by the lock, so a green is the lock's word. A red is not as firm. Without the lock, the
  test goes red only if the second call reaches its locked read inside the first's wait (1 s in
  T-5.1's race); and with the forced overlap removed, T-5.1's race went red 4 of 4 times, but that
  red depends on the scheduler: usually the first call reaches the lock before the second's
  transaction is open, not always. So these tests are strong evidence, not proof, and a report
  says "red in N of N" rather than "red". Making a lock race deterministic needs a fault-injection
  point inside the lock, which the advisor judged not worth building today.
- [ ] P-59 · Look-alike letters in first names, and the about field's link rule. **With T-9.5**,
  where moderation is built, or T-7.3 for the link rule. Worst case: impersonation by display
  name. First names take every script (T-3.7, D-068's answers), so "Ravi" spelt with U+0430, the Cyrillic
  a, reads exactly as another user's "Ravi" on a card or in a chat list. First names aren't
  unique, so this is impersonation by look, not by key. What stops it reaching the name people
  share as a link: usernames are ASCII only (`^[a-z0-9._]{4,20}$`). **That rule is load-bearing,
  not incidental**, said beside the regex and in 03-SCHEMA, with a test refusing look-alike
  usernames; widening usernames to Unicode would reopen it. Options for first names: refuse mixed
  scripts within a word, or flag them to moderation. In the same note, T-3.7's link heuristic in
  about, Claude's rather than decided: it refuses ordinary prose run together with a lowercase
  ending ("goa.in summer"), and misses "ravi dot com" and endings off its list. At the direction
  of the advisor, 3 October 2026; found in T-3.7.
- [ ] P-60 · Make `scripts/ci-gate` refuse a commit that is already on `main`. **Before the next
  `/done`.** Worst case: a session's commit step is skipped or fails, the gate runs anyway on
  HEAD, a commit already on `main` with a green run, and prints "CI is green". The session reports
  its work landed and removes its worktree, and the change it never committed is lost, or sits
  unpushed while everyone believes it is on `main`. Seen on 3 October 2026, in P-54: Claude's shell
  chain joined the gate with `;` rather than `&&`, so after the fast-forward check refused (`main`
  had moved) and nothing was committed, the gate checked the untouched HEAD, `c47feca`, and printed
  its earlier green run. The gate named the commit it checked, but nothing compared that with the
  commit meant, and the green line is the one people read. `/done` runs its steps in order and
  stops on a failure; an improvised chain doesn't, which is why the gate must refuse rather than
  trust its caller. Fix: with no argument, `/done`'s use, refuse when HEAD is already contained in
  `origin/main`, with an exit code of its own and a message saying nothing new was committed; an
  explicit ref (`scripts/ci-gate main`, the manual path's step 4) is checked as now. Print the
  commit's subject beside its SHA. In `scripts/ci-gate-test`: an already-merged HEAD exits with the
  new code and says why; an explicit `main` still checks. At the direction of the advisor directing
  T-3.2 to T-3.10, 3 October 2026; found in P-54.
- [ ] P-61 · Give the API's 500s their CORS headers. **Before T-9.12,** or sooner if a screen needs to
  tell a crash from no signal. Worst case: a browser can't read the API's `INTERNAL` envelope at all,
  so every 500 looks to the web exactly like a lost connection ("Failed to fetch"), and a bug in
  production hides behind "check your connection". Starlette builds a 500 outside every middleware,
  CORS's included; `errors.py` adds `nosniff` and `no-store` there (P-42) but not
  `Access-Control-Allow-Origin`. Seen in T-3.10's Chrome check, when the dev database's missing
  `otp_sms_daily_cap` made OTP send fail. The web copes today (a failed restore offers a retry, never
  `/login`), so this is about seeing errors, not losing sessions. Add the CORS headers to the 500
  for an allowed origin only, with a test that a disallowed origin still gets none. Found in T-3.10.
- [ ] P-62 · Give T-1.9's identity trigger a constraint name. **Before the next migration that
  touches `users`; needs P-65 first,** since this fix is a migration itself. Worst case: a refusal reported as the wrong one. `users_identity_immutable()`
  raises `check_violation` (23514) and names no constraint, so its tests can only match its message,
  and T-3.6's `_flush_identity` maps any 23514 at that flush to `IMMUTABLE_FIELD`. Its comment says
  only that trigger can raise it, since `users` has no CHECK. From T-5.1, D-076's two triggers raise
  23514 too (on `ledger_entries` and `wallets`), so a flush there that carried a wallet write a
  trigger refused would answer "This can't be changed once it's set." Fix: a migration replacing
  the function to raise `using constraint = tg_name`, T-3.6 mapping by that name, and the
  `test_schema.py` tests asserting it. Not in T-5.1, at the advisor's direction. Found in T-5.1,
  which made every other CHECK test in `test_schema.py` name its constraint.
- [ ] P-63 · Make the wallet refuse locking several wallets out of `user_id` order. **Before
  T-9.3,** on its Needs line, the first task that locks more than one. Worst case: two
  transactions each holding one man's wallet and waiting for the other's, a deadlock Postgres
  breaks by failing one, so a ban's refunds fail at random under load. D-077 says a transaction
  locks one wallet, or several in `user_id` order, but nothing enforces it: `debit()` and
  `credit()` lock whatever they're given. Fix: the wallet module records on the session which
  wallets it holds, and refuses (`WalletMisuse`) a lock below the highest held; or a
  `lock_wallets(ids)` that sorts them first. Test it with two transactions crediting the same two
  men in opposite orders. Found in T-5.1.
- [ ] P-64 · Let endpoint tests see the events a request publishes. **Before T-7.4,** on its Needs
  line. Worst case: T-7.4 ships with every socket event untested end to end, or a service publishes
  on its own to make one visible, which would publish before commit and under a lock. In tests the
  `app` fixture replaces `get_session` with `session_for_the_app` (the test's rolled-back session),
  and `get_session` is what publishes a request's committed events (`core/events.py`, T-5.1). So
  through `client` no event is ever published; only `tests/core/test_events.py`'s app, built
  without the override and committing for real, sees one. Fix: `session_for_the_app` takes the
  session's committed events when the request ends and publishes them as `get_session` does, or
  hands them to a fixture to read. Also: T-7.4's "publishing helper `realtime.publish()` used by
  services" predates `core/events.py`; services queue events, and T-7.4 builds only the socket
  side (T-5.1's text). Found in T-5.1, at the direction of the advisor directing Sprint 5.
  **The tripwire is in** (4 October 2026, moved out of T-5.4 ahead of Sprint 4): while the `app`
  fixture is up, listening on Redis raises, naming this item and pointing at the real
  `get_session`, on a new subscription and on one made before the app was (`LISTENING` in
  `tests/conftest.py`), so the gap fails loudly until T-7.4 closes it. Proved both ways in
  `tests/test_harness.py`, and red with the tripwire removed and with it on `pubsub()` alone.
  This item's fix removes it, and turns that test into one that sees the events.
- [ ] P-65 · Make the deploy read `alembic_version` back after migrating. **Before P-38 or P-62,
  whichever lands first:** the plan's next migrations (P-38's areas, due before T-4.10, on whose
  Needs line this sits; P-62's trigger fix). No task from T-3.12 to T-6.4 carries one: checked
  task by task on 3 October 2026 (discovery's GIST index already exists, T-1.9). A task that
  later grows a migration before these takes P-65 onto its own Needs line. Worst
  case: a deploy reports a migration applied when the database is somewhere else, and the next
  task builds on a schema staging doesn't have. Today the only witness is Alembic's own log in the
  migrate job ("Running upgrade …"): the migrator reporting on itself. T-5.1's Done-when rested
  on exactly that (deploy run 37131243030). Fix: `scripts/migrate-with-url`, which both deploys
  run, reads `select version_num from alembic_version` on the same connection after the upgrade,
  prints it, and fails unless it is the repo's single head (`alembic heads`). Then, with the head
  matching, it checks three objects by name in the script: the triggers `ledger_entries_only_men`
  and `wallets_only_men` (D-076), each present and enabled (`pg_trigger.tgenabled`, since a
  disabled trigger exists and refuses nothing), and the index `uq_ledger_entries_one_per_event`
  (D-077), present, unique and valid. **Why these three and no others:** Alembic's schema
  comparison never sees a trigger or a function, nor a partial index's condition, so these are
  what a matching head can't vouch for; and they carry the regulatory position (D-076) and one
  entry per event (D-077). A head that matches while `ledger_entries_only_men` is missing is the
  false green at its most expensive. Every migration's objects listed by hand would rot; a later
  guard of the same weight is added here by the task that builds it. Test it in the script's own
  test: a wrong database refused, and a database at head with each of the three dropped, then
  disabled, refused, naming the object. At the direction of the advisor directing Sprint 5,
  3 October 2026, after T-5.1; the three objects added at the advisor's direction the same day.
- [ ] P-66 · Give staging a Firebase project of its own, with its own test numbers, its own
  authorised domains and its own region policy. **Before the first staging check that signs in
  and runs unattended** (an E2E against staging, or anything in CI that signs in): that is P-67,
  whose Needs line carries P-66. **And before real users are possible:** on REL-1's Needs line if
  REL-1's tag includes T-3.14, and on T-9.15's regardless. `scripts/staging-smoke` already runs
  unattended after every deploy but signs nobody in (it reads `/healthz`, `/readyz` and the home
  page), so it isn't the trigger. Worst case: launch with staging still signing in through
  production's project, where a real person can sign in to staging, each site's tokens are
  accepted by both APIs, and staging draws on the SMS credit and limits real sign-ins need
  (T-3.14). **Why the first unattended check is the trigger** (the founder, 3 October 2026):
  until then the founder's own phone is enough; after it, it isn't, because a check that needs a
  human holding a phone is a check that stops being run. **Its first use has a name, not just a
  condition** (the founder):
  P-67, the Playwright run moved out of T-3.14, with 06-TESTING's nightly run. A later task that
  wants a signed-in staging run unattended takes P-66 onto its own Needs line too.
  Test numbers go in this project and nowhere else, never in `velora-ic`, which production uses
  (D-065: "Not one, not temporarily."). Staging's API takes this project's ID as
  `FIREBASE_PROJECT_ID`, so production's API refuses staging's tokens as an audience; staging's
  build takes this project's web config; and `staging.veloraapp.co.in` comes off `velora-ic`'s
  authorised domains. At the founder's direction, 3 October 2026, after T-3.13.
- [ ] P-67 · Run T-3.13's journeys against staging, unattended: once, then nightly. **Needs:**
  P-66, staging's own Firebase project, which holds the test number this run signs in with: never
  `velora-ic` (D-065). The number and its code go in CI's secrets, never the repo (rule 13). Worst
  case without it: a release ships with sign-in broken, because staging's smoke check signs nobody
  in, and a check that needs a human holding a phone stops being run (the founder, P-66). The one
  run moved here from T-3.14, which had it from T-3.13 (decision 18 of T-3.10 to T-3.13's plan):
  T-3.13's journeys on the real path, Firebase sign-in included. Then the same journeys nightly,
  as 06-TESTING describes. **Both runs stay in this one item** (the founder, 3 October 2026): they
  need the same thing, an unattended staging sign-in, so splitting them would make two items with
  one dependency and no separate decision between them. Nothing is kept from a run, as in T-3.13:
  no traces, videos or screenshots. At the founder's direction, 3 October 2026, so that P-66's
  first use "has a name, not just a condition".
- [ ] P-68 · Enforce App Check on Firebase Authentication, and prove it by its effect. **The very
  next task after T-3.14** (the founder, 4 October 2026), **for this reason, so nobody reorders it
  as housekeeping:** the exposure opens at T-3.14's first staging deploy, not at REL-1. From that
  deploy, staging's bundle carries the web config, the same project production uses, and
  staging's hostname is in public certificate logs; waiting for REL-1 would leave it open for
  however long REL-1 takes. (The logs, checked 4 October 2026: the certificates for
  `staging.veloraapp.co.in` and `api.staging.veloraapp.co.in`, Let's Encrypt, 2 October 2026,
  each carry the logs' signed timestamps, which a self-signed control doesn't.) It also gates REL-1 (if REL-1's tag includes T-3.14) and T-9.15 on
  their Needs lines, and it is the first step of P-0.18's order.
  **Needs:** T-3.14, and the founder's console work, done right before this task starts and not
  earlier, so a registration made now can't drift before anything uses it (the founder,
  4 October 2026; the steps from Firebase's reCAPTCHA Enterprise provider page, read by Claude on
  4 October 2026):
  1. Google Cloud console, project `velora-ic`: enable the reCAPTCHA Enterprise API, and create a
     **Web** key for `veloraapp.co.in` and `staging.veloraapp.co.in`, with "Use checkbox
     challenge" left unselected.
  2. Firebase console, Security, App Check: register the web app with the reCAPTCHA Enterprise
     provider and that key. The token lifetime (30 minutes to 7 days) and the risk threshold
     (0.5) can stay at their defaults.
  3. **Enforcement stays off** until this task's code is live and the metrics show our own
     traffic passing. Authentication stays unenforced, which still collects metrics; then the
     founder enforces it. Enforced before the web sends tokens, it refuses every sign-in.
  The key is public by design, and joins the web config committed in
  `web/src/lib/firebase-config.ts` by `APP_ENV` (D-085), not a variable. Assessments above
  a no-cost quota are charged.
  Worst case without it: the web config, public by design, ships in the bundle from T-3.14 on,
  and with it anyone can ask Firebase to send SMS from a script, needing only a solved reCAPTCHA
  per send. A flood then spends the trial's credit, which ends the trial and stops sign-in
  everywhere; once paid, it bills one person's card up to Firebase's fixed 3,000 a day (P-0.18).
  App Check makes a flood need our web app, the strongest lever left (the founder), since no
  console field caps SMS and our server's limits never see a Firebase send (D-035).
  **The code, this item's:** `initializeAppCheck` with `ReCaptchaEnterpriseProvider` and
  `isTokenAutoRefreshEnabled: true` (the SDK doesn't refresh tokens by default), before the phone
  screen asks for a code. It widens the CSP for App Check's hosts the way T-3.14 does for
  Firebase's, each with its reason (D-059).
  Local and CI builds sign in by Path B (D-081), so they never meet App Check.
  **Done when, by its effect, not the console's switch:** with enforcement on, a request to
  Firebase Authentication's send-code endpoint without an App Check token is refused, and the
  refusal's body names App Check, not a missing reCAPTCHA token; and sign-in from our own site
  still works. The switch alone proves nothing. Google's own API description says some services
  "require certain conditions to be met before they will work with App Check, such as requiring
  you to upgrade to a specific service tier", and until then enforcement "will have no effect".
  Google's pages don't say whether Authentication is one of them; the test decides.
  **If enforcement turns out to need the Identity Platform upgrade, don't take the upgrade: stop
  and tell the founder** (the founder's hard instruction, 4 October 2026). The upgrade removes the
  3,000-a-day ceiling, the only "how many" bound there is (P-0.18), and trading a known ceiling
  for an unproven guard would leave us worse off than today. That decision has a cost on both
  sides, so it is the founder's. At the founder's direction, 4 October 2026.
- [ ] P-69 · Restrict `velora-ic`'s browser API key. **After T-3.14's staging check, beside P-68,
  and before REL-1** (on its Needs line), by the founder in the Google Cloud console. Worst case without it: the key, which every page of
  staging and production ships, works from any website and any script. One call from this machine
  on 4 October 2026, with no referrer at all, got Firebase's own answer (T-3.14's region refusal).
  Firebase's page on API keys, read that day: "Although API keys for Firebase services are safe to
  include in code, you should review and apply appropriate restrictions and limits to them."
  Restrict it to the referrers `https://veloraapp.co.in/*` and `https://staging.veloraapp.co.in/*`
  and to the APIs the web calls (Identity Toolkit and the Token Service; reCAPTCHA Enterprise from
  P-68). A referrer is a header a script can write, so this stops other websites, not scripts:
  App Check (P-68) is the lever against scripts. Prove it by its effect: the same call without a
  referrer is refused, naming the restriction, and staging still signs in. Not before T-3.14's
  staging check: a restriction set wrong refuses every sign-in, and that check has 5 SMS an hour.
  At the direction of the advisor directing T-3.14 (Claude, in a separate chat), relayed by the
  founder, 4 October 2026.

  Found building T-3.14.
- [ ] P-70 · Stop a number from outside India being texted as an Indian one. **Before REL-1** (on
  its Needs line). **It protects a person who isn't our user.** Worst case, and it can happen today:
  someone with a foreign number, in Dubai or living in Phagwara, types their own ten digits; the
  screen puts +91 in front, and the code lands as an SMS on the phone of a stranger in India who
  never asked for it, at 2 a.m. if that's when it's sent, for an app they've never heard of, and
  again every time that person tries. The person trying waits for a code that went to someone
  else. Firebase's region policy can't stop it: the stranger's number is Indian, so it's allowed.
  **The fix is before the typing, not after the send:** +91 fixed and unremovable beside the
  input (it is today, from T-3.11, outside the field; keep it so), and under it a line saying
  Velora works with Indian mobile numbers only, in Phagwara to start, so nobody reaches the point
  of sending a code to a stranger. T-3.14's copy for a number Firebase refuses stays as the
  backstop, not the fix: the screen never sends a number that isn't +91, so only devtools reaches
  it. At the direction of the advisor directing T-3.14 (Claude, in a separate chat), relayed by the
  founder, 4 October 2026.

  Found building T-3.14.
- [ ] P-71 · Name reCAPTCHA on `/privacy`. **Before REL-1** (on its Needs line). Worst case:
  `/privacy` is published, and is inaccurate from the moment `/login` ships on a Firebase build:
  `/login` loads Google's reCAPTCHA as it opens (T-3.14 renders it then, so the first tap is quick),
  and reCAPTCHA reads browser and device signals for Google before a number is typed, while
  `/privacy` names Google only for sending the code and handling the number. A published page that
  says less than the product does is the same failure as switching on Google Analytics would have
  been. One line in its section on Google; its list of processors already names Google. It goes in
  P-0.7's review too, and to a lawyer when there is one (none is engaged, P-0.7). At the direction
  of the advisor directing T-3.14 (Claude, in a separate chat), relayed by the founder, 4 October
  2026.

  Found building T-3.14.
  **And the constraint that keeps `/privacy`'s Sightengine line true** (4 October 2026). `/privacy`
  says photos are checked by Sightengine "and deleted there after the check". That holds only while
  T-4.4 uses Sightengine's plain image moderation API, on its default retention, which deletes
  after processing; T-4.4 quotes Sightengine's FAQ and the four features that keep files (human
  review, the Feedback API, the Upload API and near-duplicate lists, redacted videos). **Turning on
  hybrid review or the Feedback API makes /privacy inaccurate the same day, so either is a decision
  that changes a published page, not a tuning knob someone enables for better accuracy.** Sightengine
  changes its retention on request, so "default" is a state we must not drift out of, not a
  guarantee. At the direction of the advisor (Claude, in a separate chat), relayed by the founder.
