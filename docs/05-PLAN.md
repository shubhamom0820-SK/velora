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
- [x] **P-0.18** Convert the Google Cloud billing account from its free trial to a paid billing account, **after App Check is enforced and proved by its effect (P-68), and before launch.** **Owner: the founder, Shubham Kumar. Due: before launch (REL-1 if its tag includes T-3.14, T-9.15 at the latest), and in any case before 2 January 2027, or before the trial's ₹28,796.63 of credit runs out if that comes first.** Recorded 3 October 2026, when P-0.13 closed; rewritten 4 October 2026, when the daily SMS cap turned out not to be a setting.
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
  **Done 17 October 2026, out of order (the founder):** the billing account `01C4E8-84A5D8-4255F2`
  was upgraded from its trial, **before P-68**, so the order above didn't hold; the trial's leftover
  credit still offsets costs. P-49's two projects bill to it (D-1020). **What that leaves, until
  P-68:** an SMS flood now costs money rather than ending the trial, bounded only by Firebase's
  fixed limits above (3,000 verification SMS a day per project) and the India-only region policy.
  P-68 stays the next step, not a sibling. Recorded by Claude building P-49, 18 October 2026.
- [ ] **P-0.14** Decide where the registered office is, before `v0.1.0`, production's first release (REL-1). **Blocks that release, not the build:** on REL-1's Needs line, since a registered office is a judgement no check can make. `/contact` publishes D-058's registered office, the founder's home in Hajipur, and from `v0.1.0` it is public, crawled and archived: once Google and archive.org hold the address, no later change removes it.
  **Why it's a decision** (the founder, 3 October 2026): a sole proprietorship must publish a registered address, but it needn't be where the founder sleeps. A virtual-office or registered-address service in India, roughly ₹1,000 to ₹2,000 a month, meets the same requirement with a commercial address. For a dating app, where some users will be angry at whoever banned them, the difference matters.
  **If it changes:** a new decision supersedes D-058's office, `REGISTERED_OFFICE` in `web/src/lib/legal.ts` changes (its guard test names D-058), and the court follows the office (D-058), so a new city means a new court line too.
- [ ] **P-0.15** Move the Vercel team `knot11` to Pro before `v0.1.0` (REL-1). **Blocks that release, not the build,** and the release gate refuses while the team is on Hobby (D-075). Vercel's own terms: "Hobby teams are restricted to non-commercial personal use only", with "advertising the sale of a product or service" among their examples of commercial use (its fair use guidelines, updated 14 September 2026). A public dating app is plainly commercial. Until the release, staging is `noindex` with no traffic, so the risk is close to zero and it waits (the founder, 3 October 2026). Pro is $20 a month with one deploying seat, covering both projects.
  **The trial doesn't fit** (Vercel's own page, read 3 October 2026): 14 days or until its usage limits, whichever comes first; one per user account; started only by creating a new team, not by upgrading `knot11`; without a payment method it falls back to Hobby. So it is worth at most one month's $20, and only if started the day `v0.1.0` goes public, in a new team production would then live in. Upgrade `knot11` itself on release day.
  **The Hobby plan's upload cap already stops staging deploys** (found building T-3.14, 4 October 2026). Vercel refuses a deployment's upload past 5,000 files a day: `Error: Too many requests - try again in 24 hours (more than 5000, code: "api-upload-free")`, at `deploy.yml`'s `web — Vercel` job (`vercel deploy --prebuilt --prod`). Two staging deploys of green code hit it: `1d6eb44` (run 37146785444, 3 October, 19:10 UTC; its log also repeats `Error: Upload aborted`) and `94e3934` (run 37152600833, 20:46 UTC). `6d621f6` uploaded between them (run 37152210707, aliased at 20:40). Each time, gate, migrate and the Fly API had already deployed, so staging's API ran ahead of its web. **To recognise it in a minute:** the `web — Vercel` job red, every job before it green, and `api-upload-free` in its log. It's the plan's limit, not the code: there's nothing to debug. **Pro raises the cap, it doesn't remove it:** Vercel's limits page (read 4 October 2026) gives `api-upload-free` 5,000 a day and Pro's `api-upload-paid` 40,000. Vercel's own hint, `--archive=tgz`, would upload one archive instead of every file.
  **The cap again, 4 October 2026, and `--archive=tgz` landed** (at the direction of the advisor
  directing Sprint 5, relayed by the founder, instead of Pro: Pro raises a ceiling that every
  session's landing climbs back into). Staging's deploy of `dc914d9` (run 37214991123) was refused
  at 16:00:26 UTC with `Too many requests - try again in 24 hours (more than 5000, code:
  "api-upload-free")`; the API had deployed. Vercel's limits page (read 4 October 2026): 5,000 per
  86,400 s, reset "after the Duration has expired", fixed or rolling not said. This item's own
  record above, an upload at 20:40 UTC between two refusals, points to rolling. Both deploy
  workflows now run `vercel deploy --prebuilt --prod --archive=tgz`, so staging proves what
  production runs (D-075). Vercel's deploy page says `--archive` packs the output into "one or
  more files", and split archives are now its default, so a deploy should upload a few parts,
  against the ~761 files of a deploy without it. **Not yet proved:** the first staging deploy
  that goes through must show that count; if the CLI's output doesn't show it, the record says so
  rather than assuming the flag took effect. Pro stays unbought until that is read.
  **Proved, 4 October 2026:** the first staging deploy through after the window cleared
  (`aba62e5`, run 37222076586) printed bytes only (`Uploading … (1.8MB/1.8MB)`), then
  `Concatenating deployment archive files... Extracted 762 deployment files...`, where a deploy
  without the flag says `Downloading 761 deployment files...`. That shows the archive was used,
  not how many uploads it took, so the count came from one `--debug` deploy (approved once, run
  37222405686, from a throwaway branch, deploying `main`'s head `f083c61`): Vercel's client said
  `1 files are required to upload`, made one `POST /v2/files`, and uploaded
  `web/.vercel/source.tgz.part1` (1.78 MB). **One upload per deploy, measured.** A bigger build
  may split into more parts; this one didn't. Pro remains unbought.
- [ ] **P-0.16** Move `velora-prod`'s Supabase organisation to Pro before `v0.1.0` (REL-1). **Blocks that release, not the build,** and the release gate refuses while it is on Free (D-075). The Free plan keeps no automatic backups, and the first real sign-up is the first thing worth losing (the founder, 3 October 2026). Pro is $25 a month per organisation with 7 days of daily backups; its $10 of included compute covers one project, which is why `velora-prod` has an organisation of its own (`infra/PRODUCTION.md`). Point-in-time recovery, a further add-on, is T-9.14's.
- [x] **P-0.6** Create accounts: GitHub, Supabase (Mumbai), Upstash, Cloudflare (R2 on), Fly.io (paid plan for `bom`), Vercel, Sentry, Sightengine.
  **Ticked with two still to set up then**, none needed before Sprint 4, each on its task's
  **Needs** line, which `/task` checks before planning: Sightengine (T-4.4; created by the founder
  on 4 October 2026, free plan, its keys in the Keychain) and Sentry (T-9.12). **The face-match
  vendor's account is dropped** (D-087, 4 October 2026): face matching runs on our own worker
  (D-088), and that account's unfinished payment verification is abandoned.
- [ ] **P-0.7** Review our own legal text before real users arrive — no lawyer at this stage (the founder's call, 1 October 2026). Check Terms, Privacy, Refunds and Contact (T-2.2) against the decisions they cite and against what the product actually does at go-live; against the IT Rules 2021 (Grievance Officer, timelines) and the DPDP Act (notice, consent, rights — section 16 and Rule 15 take effect on 13 May 2027; check for any restricted-country notification); and gender-based pricing. Start with the law-and-courts text (D-052), the weakest part we wrote ourselves. Look closely, not in passing, at the under-18 section: it keeps a hashed phone number of someone just identified as a minor (D-009). The mechanism and saying so openly are right, but minors plus retention is the most scrutinised combination there is. Privacy has no section yet on what happens to people's data if the app shuts down or is sold; add one when there is something honest to say. Gates T-9.15, not the production build (D-053). Terms' consumer-rights line (D-058) was written without a lawyer, by the founder and Claude: if the terms are ever reviewed properly, show it to one.
  **The face-match model's training data** (D-088, 4 October 2026), as written there, and never softened (the founder): the code and the weights permit commercial use (MIT, Apache-2.0). The weights' training data is a separate question: OpenCV Zoo doesn't say which set trained the shipped SFace model, and the SFace paper's experiments used CASIA-WebFace, VGGFace2 and MS-Celeb-1M, collections of faces of people who weren't asked. That is a question about the model's origins, not a restriction on using it.
  **The liveness model's training data, the same question** (D-380's fourth decision, the founder, 7 October 2026: beside SFace's, and never softened). MiniFASNet, the model T-4.11's research named (minivision's Silent-Face-Anti-Spoofing, Apache-2.0, "Copyright 2020 Minivision"), was trained on data minivision keeps private. Its own member, asked (read by Claude, 5 October 2026, in the repository's issues): "We did not use any open source datasets" and "about 5 million images in each class" (issue #25, 21 August 2020); and, asked to release it, that the data involves legal and privacy matters, so it isn't open-sourced (issue #29, 26 August 2020, in Chinese). Whose faces, and whether anyone was asked, is unknown. As with SFace, a question about the model's origins, not a restriction on using it.
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
  **The exception: P-81 is answered before the first real user, not with the rest** (the founder,
  4 October 2026). Whether deleting a photo that scores as both a possible minor and sexual
  (D-093) conflicts with a duty under Indian law to preserve or report it is the one legal
  question that can't wait for this review: getting it wrong is not a commercial mistake. It is
  on REL-1's Needs line for that reason.
- [x] **P-0.17** A chartered accountant confirms how prepaid Velas are treated, **before the first real sale. Owner: the founder, Shubham Kumar. Trigger: Sprint 8, not launch:** it is on T-8.1's Needs line, so `/task` stops there. Recorded 3 October 2026, at the direction of the advisor directing Sprint 5 (Claude, in a separate chat).
  **Answered 8 October 2026** (the founder, Shubham Kumar, after a phone call with a chartered
  accountant; the CA's name is the founder's to add here when given). Recorded as D-450, Open
  until that name is in. The five points, as the founder relayed them:
  1. **No GST registration now.** The threshold for services is ₹20 lakh aggregate turnover in a
     financial year, Section 22 of the CGST Act as the CA put it: the law's number, not the
     founder's choice. Below it Velora stays unregistered and charges no user GST.
  2. **Prices are GST-inclusive.** A user pays ₹1,500 for the entry pack, today and after
     registration. Registration doesn't move the price: Velora's share becomes ₹1,271 and ₹229
     is the government's (18%, digital services).
  3. **Unregistered, a receipt says nothing about GST:** no "incl. GST", no rate, no GSTIN. The
     total alone. Showing or collecting GST without a GSTIN is against the law.
  4. **Unspent paid Velas are a liability** (deferred revenue), revenue when spent. An accounting
     rule, separate from GST; the first bullet below stands as written.
  5. **The voucher-timing question** (GST at sale or at spend) is asked of the CA on the day
     Velora registers, not before: while unregistered it doesn't arise.
  **What follows:** T-8.1's Needs line reads this as answered, and two boxes there carry what the
  answer needs built: a `gst_paise` that stays 0 and a receipt in which the word GST appears
  nowhere, and the aggregate turnover counter with its ₹15 lakh alert. **P-350** is the
  registration itself, within 30 days of crossing ₹20 lakh. D-099 notes that its prices are
  inclusive.
  **What the CA confirms:**
  - **Revenue recognition:** unspent paid Velas are a liability until spent. They never expire and
    are never refunded (D-050, D-076).
  - **GST timing:** whether GST is due when Velas are sold or when they are spent.
  - **Registration:** whether Velora must register for GST at all. The advisor directing T-3.2 to
    T-3.10 says Velora has no GST registration, deliberately, below the threshold; P-0.2 still
    lists GST as unconfirmed. Google's tax form (P-0.13) went in as an unregistered individual with
    PAN (the founder, 3 October 2026): today's status, not whether registration is required.

  **Of the three, on 8 October 2026:** revenue recognition is **answered**, point 4, as written.
  Registration is **answered**, point 1: not required below ₹20 lakh aggregate turnover in a
  financial year, and not done; the advisor's "below the threshold" was right, and this names
  the threshold. P-0.2's GST line is answered by the same point, and P-0.2 stays open for PAN
  and the current account. GST timing is **deferred to registration day**, point 5, on P-350:
  it is the CA's question then, and doesn't arise before.

  **A chartered accountant was consulted, by phone, on 8 October 2026** (the founder); the name
  goes here when the founder gives it, beside P-0.7's lawyer, and D-450 Locks on it. Until 8
  October 2026 this paragraph read "No CA is engaged today." Neither Claude nor the advisor
  has read the GST law, and neither makes any claim about it: the five points above are the
  CA's, as the founder relayed them. Getting it wrong accrues quietly from the first sale and is
  expensive to unwind, which is why P-350 leads with the threshold crossed unnoticed.
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
- [x] Supabase staging project (enable PostGIS, pg_trgm, citext); Upstash staging DB; R2 staging buckets.
  All by hand, from `infra/STAGING.md`. **Open, for R2 alone (1 October 2026):** Supabase (Mumbai,
  migrated to head) and Upstash (Mumbai) are serving staging (deploy run 36845884410). R2 isn't
  enabled on the Cloudflare account yet, which only its dashboard can do, so there are no buckets.
  **Moved:** R2 is now on T-4.1's Needs line, the first task that uses the buckets — tick this with
  T-4.1.
  **Ticked 8 October 2026 (the audit, P-490):** T-4.1 landed (`6814f46`, 4 October 2026) with its
  Needs line's R2 box ticked: the four buckets, set up by the founder that day.
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
  - **P-880:** `/login` shows reCAPTCHA's badge, or, where it is hidden, Google's required notice
    near "Send code". Filed 18 October 2026, at the founder's direction.
  - **P-69:** `velora-ic`'s browser API key restricted to our two sites and the APIs the web calls,
    after T-3.14's staging check.
  **And P-130, with no condition** (D-230, 4 October 2026): `/refunds` rewritten to say there is no
  product refund. As published it promises Velas back on a ban and on a declined album request,
  which the product will never return.
  **And P-165, with no condition** (the founder, 5 October 2026): one upload from Safari on an
  iPhone, its format recorded from the bytes as they arrive. T-4.6's box closed on "not HEIC", and
  which format an iPhone sends, and from which browser, was never seen.
  **And one found building T-4.6, with no condition:** production's private bucket's CORS rule
  (`infra/PRODUCTION.md` §3), set by the founder and checked by a preflight from
  `https://veloraapp.co.in`. Without it no browser can upload a photo, so nobody gets past the
  photos step.
  **And P-180, with no condition:** CI required at GitHub before `main` moves (D-280). The landing
  guard protects only the clones that installed it; this protects every clone.
  **And P-940, with no condition** (the founder, 19 October 2026): the app installed from staging
  on a real Android phone in Chrome and on an iPhone, alongside P-930's test-phone check. Until
  then the banner, the install and the offline page are seen only in tests and desktop Chromium.
  **And six that block only under their condition** (the founder, 3 and 4 October 2026), each
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
  - **T-4.11 left this list on 7 October 2026:** liveness waits until after launch (the founder,
    D-380); D-008 is amended, and the selfie's face match (T-4.5) is what stays mandatory.
  - **T-4.12, if REL-1's tag includes T-4.6: the advisor's recommendation (Claude, in a separate
    chat, 7 October 2026), for the founder to confirm, not his decision.** A tag with T-4.6 is the
    first that asks women for photos, and asking the first cohort to show a face is the opposite
    of the redesign (D-392); and T-4.12 changes what `/privacy` says the selfie is compared with.
  - **P-72, if REL-1's tag includes T-4.4.** A human for repeated possible-minor flags (D-093), so
    a model's probability never becomes an automatic action against a real woman.
  - **P-81, if REL-1's tag includes T-4.4.** The lawyer's answer on a photo that scores as both a
    possible minor and sexual, which D-093 deletes: the one legal question the founder put before
    the first real user, since getting it wrong is not a commercial mistake (4 October 2026).
  - **P-162 and P-163, if REL-1's tag includes T-4.5.** Whether one matching photo may carry a
    profile of someone else's photos (P-162), and an undo for a selfie decision the founder's
    review finds wrong (P-163): both reach real women once a selfie can be decided for one.
  - **P-68, if REL-1's tag includes T-3.14.** App Check enforced on Authentication, proved by its
    effect, before the site is public for sign-in (the founder, 4 October 2026): it is what makes
    an SMS flood need our web app rather than a script. A backstop only: P-68 is the very next
    task after T-3.14, since the exposure opens at T-3.14's first staging deploy.
- [ ] **Production's Fly deploy tokens get a shorter expiry than Fly's default of 20 years**, chosen
  then, and the worker's too once production has one (the founder, 4 October 2026): in production
  the consequence is real. Staging's keep the default on purpose: low consequence, and a renewal
  date nobody remembers is its own risk.
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
  **Open, 4 October 2026, so T-3.14 lands partly complete:** staging's `sessions` rows (read
  read-only by Claude, 12:43 UTC) show one real Firebase sign-in, at 20:53 UTC on 3 October,
  refreshed twice in a browser they don't name, and two more accounts from numbers whose owner is
  unknown. It closes when the founder signs in by SMS in Chrome, Firefox and Safari, naming each
  browser as he does (the rows never record browsers), with each reload visible in the rows. The
  37-step procedure is in `out/t-3.14-staging-check.md`, on the founder's Mac, where Firefox isn't
  installed yet.
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
  **Open, 4 October 2026:** the rows show only part of items 1, 2 and 4, in a browser they don't
  name: the refresh cookie and `X-CSRF` accepted twice, the second time with the token the first
  rotation issued. It closes when all seven items are seen in each of the three browsers: the
  cookies' attributes and `/v1/me`'s headers in devtools, and the rotation, the two tabs and the
  sign-out also in the `sessions` rows.
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
  is tied to where the API runs. **Decided 4 October 2026 (D-095):** the worker deploys to Fly
  staging in T-4.4, and moves with the API when P-49 lands.
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
**Changed by T-4.12 (D-392, filed 7 October 2026):** the step is left without a public photo,
and the last one may be removed; these boxes record what T-4.3 built and proved.
- [x] **Needs:** T-4.2
- [x] `GET /me/photos`, `PATCH /me/photos/order`, `DELETE /photos/{id}` (soft: status `rejected` + reason `user_deleted`, object removed from public bucket).
- [x] Onboarding `photos` step completes when ≥ 1 public photo is `approved` **or** `pending` (pending ones stay invisible to others until approved).
- [x] **Commit:** `feat(photos): list, reorder, delete [T-4.3]`

### T-4.4 · Moderation worker
**Changed by T-4.12 (D-391, D-392, filed 7 October 2026):** `no_face` applies to the face photo
and never to a public photo (D-101 amended); these boxes record what T-4.4 built and proved.
- [x] **Needs:** T-4.2, T-1.15, and a **Sightengine account with API keys** — created by the founder on 4 October 2026, free plan, its keys in the Keychain (P-0.6)
- [x] ARQ worker bootstrap (`workers/main.py`) + `make worker`.
  `python -m app.workers` (`make worker`; `make dev` starts it too): `moderate_photo` and
  `delete_files`, the API's `Settings`, its own engine (query values hidden from errors, rule 15),
  ARQ's line naming a job's arguments replaced by its name (`delete_files` carries storage keys).
  It refuses to start without Sightengine's keys, naming them; `--check` says so and exits 2.
  Proved end to end by `test_a_photo_the_api_completes_is_moderated_by_the_worker_through_arq`:
  the API's own `complete` queues the job on this run's Redis, a real ARQ worker built as the
  real one is runs it, and the photo ends approved and published.
- [x] **The worker polls every 10 seconds** (D-091), a setting: on Upstash's Free plan that is
  260,640 commands a month idle, 52% of the 500K, where ARQ's default 0.5 seconds would be over
  five million. `WORKER_POLL_DELAY_S`, default 10; the health key hourly; abort and cron off.
  `test_it_polls_every_10_seconds_which_is_d091s_sum` builds the worker as `run_worker` does and
  recomputes D-091's 260,640 from its own numbers.
- [x] **On Fly now (D-095, the founder, 4 October 2026):** not after P-49's move.
  Deploy the worker to Fly staging (moved from T-1.22): a 1 GB machine (D-088), with Sightengine's
  and R2's keys among its secrets; `infra/fly.worker.toml` beside
  `fly.api.toml`, the same image and least-privilege role, deployed by `deploy.yml` after the API.
  Add its pool to the connection budget in `infra/STAGING.md`. It shares `Settings`, so it needs
  the API's four keys as secrets, the same values (from the Keychain, `infra/STAGING.md`):
  otherwise it can't read the numbers or hashes the API wrote, or doesn't start (D-060, D-061).
  **Done, 4 October 2026, by Claude:** the app `velora-worker-staging` (organisation `personal`,
  `sin`), its ten secrets staged through stdin, never printed (the four keys, R2's pair and
  Sightengine's pair from the Keychain; `DATABASE_URL` and `REDIS_URL` piped from the API's
  machine), and its own deploy token in GitHub's `staging` environment as `FLY_WORKER_API_TOKEN`
  (scoped to this app; Fly's default expiry, 2046). Deployed by deploy run 37218077335 on
  `94dcee6`: its release command (`python -m app.workers --check`) passed on a one-off machine,
  then one `worker` machine, shared-cpu-1x, 1,024 MB. Budget: 14 + 3 = 17 of `velora_api`'s 20.
- [x] `moderate_photo(photo_id)`: fetch raw → Pillow open (reject if not an image) → `ImageOps.exif_transpose` → resize longest side 1600 → save JPEG q85 **without EXIF** → `ModerationProvider.check()` → approve (write public copy for `public` kind) or reject with reason (`nudity`, `minor_suspected`, `no_face`, `text_overlay`, `other`). `minor_suspected` is D-093's: rejected without an accusation ("We couldn't verify this photo — try a different one"), the image deleted, a `fraud_events` signal kept; the internal report waits for T-9.2's system user.
  **As built** (`photos.service.moderate`): at most 8 MB read and the bytes judged again (the PUT
  URL outlives `complete`, D-089); the re-encoded JPEG written over the upload before Sightengine
  is asked, so no original is kept even when it fails; approved public photos published from the
  bytes scored, never copied from the upload; `no_face` for public photos only; an upload it can't
  read, `other` (or `too_large`), its file deleted; the decision written with the user's row
  locked, so it and a reorder take turns (`test_the_decision_and_a_reorder_take_turns`, the
  overlap observed in `pg_stat_activity`). The thresholds are Claude's, the founder's to change:
  **D-101,** decided by the founder (a possible minor from 0.35). What the owner reads of a rejection is T-4.6's (D-093's first condition at the
  API: no reason that names a possible minor); the `fraud_events` row is
  `possible_minor_photo_score`, weight 0, `meta`
  `{what, model, score}`, never the image or which photo; every copy deleted and read back, and a
  copy still there tried again. Three failures leave it pending, logged at error level.
- [x] Idempotent: re-running on an approved photo does nothing.
- [x] **Pillow under D-092's three conditions:** a full decode and re-encode, proved with a photo
  that genuinely carries GPS EXIF (the test fails if any location survives); the pixel limit set
  explicitly and tested with an actual bomb file; the version pinned exactly, and updated when CVEs
  land. **Met:** (1) `tests/fixtures/located/` holds a JPEG, a PNG and a WebP carrying a location
  in every place each format allows (EXIF GPS, XMP, a comment, a text chunk, bytes after the
  image), made by Claude with Pillow and **confirmed by two readers that aren't Pillow** on 4
  October 2026: Apple's ImageIO (12.9716 N, 77.5946 E, 920 m, orientation 6, in all three) and
  exifread 3.0.0 (the same, as rationals 444/25 and 1014/25). A test re-checks those bytes before
  trusting them; `test_no_location_survives_the_reencode` (critical) reads the output's segments
  by hand, exactly SOI, JFIF, tables, frame, scan, EOI and nothing after;
  `test_a_located_photo_is_stored_with_no_location_anywhere` (critical) checks every stored copy
  and what Sightengine is sent. (2) `MAX_PIXELS` 40 million, set on Pillow and checked before
  decoding: an 8,000 × 8,000 PNG bomb of under 20 KB (above ours, under Pillow's 89 million
  default) and 2.5- and 3.6-gigapixel bombs under 400 KB are refused with no decode. (3)
  `pillow==12.3.0` (PyPI listed no vulnerability for it, 4 October 2026); a test fails on `>=`.
- [x] **Sightengine under D-094:** built on a fake shaped like its documented responses; the last
  step one real call whose response's shape (field names, nesting, types) is compared with the
  fake's, and the date and the shape seen recorded here.
  **The check, by Claude, 4 October 2026, from this Mac with the Keychain's keys:**
  `app/tools/sightengine_shape.py` sends Sightengine's two documentation examples (`example7.jpg`,
  a face; `text1-1200.jpg`, embedded text), each re-encoded as the worker sends a photo, through
  the provider `build_providers` makes, and compares each answer's shape with the fake's.
  **The first run found the fake wrong in two places, both the documentation's:** with no text in
  the image, `text.boxes` is absent, not `[]` (the reader, requiring it, refused every ordinary
  photo: every upload would have stayed pending); and each box carries a `prob` number the
  documentation doesn't show. The fake and the reader now follow the real answers
  (`CHECKED_ANSWER`). **The recorded run, at 15:42 UTC on the provider code this commit lands:
  0 differences for both, exit 0.** The shape seen: `status` string; `request {id string, timestamp number, operations
  number}`; `nudity {sexual_activity, sexual_display, erotica, very_suggestive, suggestive,
  mildly_suggestive, none: number; suggestive_classes {bikini, cleavage, lingerie, male_chest,
  male_underwear, miniskirt, minishort, nudity_art, other, schematic, sextoy, suggestive_focus,
  suggestive_pose, swimwear_male, swimwear_one_piece, visibly_undressed: number;
  cleavage_categories {very_revealing, revealing, none: number}; male_chest_categories
  {very_revealing, revealing, slightly_revealing, none: number}}; context {sea_lake_pool,
  outdoor_other, indoor_other: number}}`; `faces [{x1, y1, x2, y2: number; attributes {age
  {minor: number}}}]`; `artificial_faces []` (no element seen); `text {has_artificial,
  has_natural: number; boxes [{x1, y1, x2, y2, prob: number; label: string}], absent when there
  is no text}`; `media {id, uri: string}`. Three runs in all, 15 operations of the free plan's.
- [x] **Sightengine keeps nothing by default, and this task stays on that default.** There is no
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
  **Held by a test:** `test_every_request_stays_on_the_plain_image_api`: every request goes to
  `/1.0/check.json` with nothing in its URL and exactly four form fields (`models`, `api_user`,
  `api_secret`, `media`); a workflow field, or `check-workflow.json`, fails it.
  **Closed, 7 October 2026, by Claude, on the test read and broken, not on this plan's word.**
  `test_every_request_stays_on_the_plain_image_api`, `api/tests/core/test_moderation.py:180`,
  read that day: three checks through `httpx.MockTransport`, once per outcome the fake gives,
  and every request held to host `api.sightengine.com`, path `/1.0/check.json`, an empty query,
  a form of exactly `models`, `api_user`, `api_secret` and `media`, and the three models. Broken
  that day on `c9a5aaf`: `uv run python -m tests.break_guards t44`, 37 of 37 red, every file
  restored by SHA-256, exit 0 (the log in `out/t-4.4-breaks/`, local); the three cases on this
  box, `t44-15` (a `workflow` field in the request), `t44-16` (`check-workflow.json` as the
  endpoint) and `t44-19` (the keys in the URL), each failed all five of the test's
  parametrisations. So this box rests on no promise to take care: a test in the repo goes red the
  day a workflow, or anything else, joins the check request. **What it doesn't see:** a second
  call to another Sightengine endpoint, the Feedback API's `feedback.json` or the Upload API's,
  added as a method of its own, never passes through it, and nothing else in the repo holds the
  module to one endpoint (grepped that day). That gap is P-260.
- [x] Tests with the fake provider for approve and each reject path; test that output has no EXIF.
  `tests/modules/photos/test_moderate.py`, `tests/core/test_moderation.py`,
  `tests/core/test_reencode.py`, `tests/workers/`. **Every guard broken once, all 32 red,**
  every file restored by SHA-256: `uv run python -m tests.break_guards t44` (its cases, committed,
  kept applicable by `tests/test_break_guards.py`).
- [x] Extend `make seed` (T-1.15): an approved public photo at position 0 for every seeded user past the photos step (everyone but the moderator, including the three women at the selfie step) — a placeholder from the prototype's `c1`/`c2` gradient, re-encoded like any upload and stored through `StorageProvider`. Re-running creates no duplicates.
  22 people (the moderator excepted), 900 × 1200, both buckets; someone seeded before T-4.4 gets
  theirs on the next run, once; a place 0 already holding a live photo gets none.
- [x] **Done when, on staging:** the worker deploys by `deploy.yml`; its secrets match their
  sources by SHA-256 prefix, computed on each machine and from the Keychain; a job queued on
  staging's Redis is run by it; `sightengine_shape` passes inside its machine; its memory measured
  there. Recorded in the docs commit after `/done`, with the deploy run.
  **Passed, 4 October 2026, by Claude, after deploy run 37218077335 (`94dcee6`):**
  - **Started:** its log, `Starting worker for 2 functions: moderate_photo, delete_files`,
    Upstash's `redis_version=8.4.0`, and `worker.started` with `poll_delay_s` 10.0, `env` staging.
  - **Secrets:** SHA-256, first 8 hex characters, computed on each machine and from the Keychain,
    never moved: `DATABASE_URL` `c15a8086` and `REDIS_URL` `55506d9f` on both machines;
    `JWT_SECRET` `f5fbdd09`, `PHONE_PEPPER` `f7d127c0`, `PHONE_ENC_KEY` `9d5de66c`, `CODE_PEPPER`
    `fd4ae0b5`, `R2_ACCESS_KEY_ID` `ac6d5e3f`, `R2_SECRET_ACCESS_KEY` `1188b869` on both and in the
    Keychain (R2's as T-4.1 recorded); `SIGHTENGINE_API_USER` `98317d78` and
    `SIGHTENGINE_API_SECRET` `54c71686` on the worker and in the Keychain, and on the API, none.
  - **A job through staging's Redis:** two `moderate_photo` jobs queued from inside the worker's
    machine for photo ids that exist nowhere (no row read, none written), each answered
    "no such photo": picked up 10.20 s and 7.93 s after queuing (the 10-second poll), run in
    1.85 s (a cold connection to Mumbai) and 0.18 s. ARQ's line read `moderate_photo(…)`: no
    argument logged.
  - **Sightengine where it runs:** `python -m app.tools.sightengine_shape` inside the machine:
    0 differences for both examples, exit 0.
  - **R2 where it runs:** T-4.1's `storage_probe` inside the worker's machine, with the
    `velora-prod-*` refusals: every step `ok`, exit 0.
  - **Memory, measured on this machine** (962 MB usable of the 1,024): the running worker, after
    those jobs, 113 MB resident, its peak 113 MB. Decoding there, in a separate process: a
    typical 12-megapixel JPEG of 5.65 MB peaks at 181 MB, the worst the 40-megapixel limit lets
    through (an RGBA PNG) at 447 MB, from a 104 MB start; so a worker decoding the worst photo
    sits near 460 MB. The same figures as this Mac's arm64 image (182 and 447 MB). D-088's 290
    to 330 MB is face matching's, measured by T-4.5.
  - **Not proved here: a real photo from upload to approved.** It needs T-4.6's upload screen on
    staging, signed in by SMS. That chain is T-4.6's staging check, and the demo.
- [x] **Commit:** `feat(worker): photo moderation pipeline [T-4.4]`

### T-4.5 · Selfie verification
**Changed by T-4.12 (D-391, D-393, filed 7 October 2026):** the selfie is compared with the face
photo alone, and each shown photo with a face is compared with the selfie for the badge; these
boxes record what T-4.5 built and proved.
- [x] **Needs:** T-4.4; D-088 (approved by the founder, 4 October 2026: the model and
  `opencv-python-headless`). No third party matches faces (D-087). Liveness isn't here: it is
  T-4.11. **The measurement set this line once named is dropped, and isn't happening before
  launch** (D-260, Locked on the founder's words, 4 October 2026: "test kiye bina aage badho").
  **The 10-second pickup is answered** by D-261's wake (Open).
- [x] **No pose** (the founder, 4 October 2026: liveness is T-4.11's, and the pose challenge is
  rejected). **Built as D-263, no migration:** `POST /verification/challenge` became
  `POST /verification/start`, returning `Verification`; the `challenge` column holds `none`, and
  `liveness_ok` stays null until T-4.11. `POST /verification/{id}/submit {photo_id}` attaches the
  uploaded selfie, queues `verify_selfie` and, after the commit, wakes the worker (D-261). 04-API
  changed with it.
- [x] `verify_selfie`: the selfie re-encoded (D-092) and written back over itself, then compared
  on the worker (D-088): YuNet finds the faces, and the selfie must hold exactly one; SFace's
  cosine similarity against each approved public photo's public copy (the bytes moderation scored,
  never an upload a second PUT could have replaced, P-79), by each photo's largest face; the best
  counted. At or above 0.363 (D-260) → `approved`, `users.is_verified = true`; else `rejected`
  with a reason from D-263's list. Max 5 a rolling 24 hours, at start and at submit. Pillow decodes
  every image and OpenCV gets only pixels, so OpenCV's image decoders never see an upload; the API
  never imports OpenCV (tested). The numbers, exactly, go in the selfie's `moderation` record;
  `verifications.similarity` stays empty (D-263, P-164). (The plan's first "similarity ≥ 85" was
  the dropped vendor's 0–100 scale.)
- [x] **T-4.5 ships without liveness, and claims nothing it doesn't do** (the founder, 4 October
  2026; liveness is T-4.11). Face matching compares the selfie with the profile's photos. It does
  not prove a live person was in front of the camera, and **it does not stop a man holding a
  woman's photos and one real selfie of her: that selfie matches her photos closely, nowhere near
  the threshold** (D-260). Only T-4.11 or a person looking stops that **(a passive liveness check
  doesn't, T-4.11's research found: D-260's amendment of 7 October 2026, D-380)**; until one
  exists, the person isn't optional (D-264). **The hard constraint:** nothing in `/privacy`, the UI copy or any badge
  may say or imply that we confirm a real person, a live person, or that someone "is who they say
  they are". **Done as D-262:** the four strings found on 4 October 2026 rewritten (`/privacy`'s
  selfie line, which now says our team may look at it; the landing page's "Verified, moderated" and
  its body, whose "reports that actually remove people" is cut, since reporting isn't built; the
  badge, now "Selfie matches photos" with a face, not a shield; `/terms`' selfie sentence), and
  `web/src/i18n/claims.test.ts` fails on a fifth.
- [x] **No woman sits watching a spinner** (the founder, 4 October 2026, on D-091's 10-second
  pickup). **Done as D-261:** the wake decides a selfie the moment its submit commits; the queued
  job stays the path sure to run, so a lost wake costs 10 seconds, never the selfie. Proved end to
  end on this run's Redis (`test_a_submitted_selfie_is_decided_by_the_wake_and_the_job_finds_it_done`).
  What she sees while she waits is T-4.7's (its line says how).
- [x] **Measure the worker's peak memory on the actual Fly machine** (D-088's first condition), with
  face matching loaded, beside this Mac's 290 to 330 MB; the 1 GB size is locked on that number.
  **Measured on the Fly machine, by Claude, 5 October 2026, after deploy run 37233775780
  (`3ed0f6d`, every job green, the worker's release-command `--check` passing with the models):**
  `velora-worker-staging`, shared-cpu-1x, 962 MB usable. The running worker, models loaded at
  startup: **207 MB resident, 268 MB its peak since start**. One comparison in a separate process
  in that machine, a 1,600-pixel selfie against two 1,600-pixel photos (the committed fixtures,
  sent in with the probe and enlarged there; Wikimedia refused Fly's address): **405 MB peak**,
  from 123 MB before the models load. **That is above D-088's 290 to 330 MB estimate** (macOS,
  without the image's baseline), and matches this Mac's arm64 container (403 MB). With T-4.4's
  worst photo decode (447 MB from a 104 MB start), the worker's worst moment is one or the other,
  never both, since both run synchronously on its one event loop: about 207 + 343 = 550 MB of 962.
  1 GB holds it with room; locking the size on this number is the founder's (D-088). The models
  behave alike on amd64: the same similarities as on the Mac (0.9099, 0.1353).
  **The wake on staging (D-261):** the worker logs `wake.listening` on `wake:verify_selfie` at
  start, so Upstash's Free plan takes the subscription. Three wakes published from inside the
  worker's machine for verification ids that exist nowhere (nothing read or written) were heard in
  547, 536 and 454 ms, each including the probe's own new TLS connection to Mumbai. **Not measured:**
  what a wake costs in Upstash's command count (its pages don't say whether deliveries count);
  its console's daily chart, before and after a few test selfies, answers it.
- [x] **Accuracy: there is no measurement, and the record says so** (D-260). The threshold is
  SFace's published 0.363 on LFW, the model's authors' number on their data, not ours on ours; our
  false-accept rate is unknown. **What stands in for it:** the words (D-262), and the founder
  looking at every decision with `app.tools.selfie_review` (D-264), whose `same`/`different`
  verdicts, written into each selfie's record, are the measurement P-160 needs, built from real
  decisions as they happen. **Before any published word claims verification, P-160 measures it**
  (on 07-CHECKLISTS §F, the release checklist). Every decision records its numbers, never an image
  (rule 15).
- [x] Selfies are never public and never shown to other users. **Critical #14:**
  `test_a_matched_selfie_is_never_public_and_never_shown` (no public copy or key, not in `/me/photos`,
  `GET /photos/{id}` 404, no link, key or number in `GET /verification/latest`) and
  `test_a_located_selfie_is_stored_with_no_location`. Staff see them only through D-264's tool.
- [x] Extend `make seed` (T-1.15): an approved verification row, with a placeholder selfie in the private bucket, for every seeded user marked verified — 15: the test woman, and the prototype's 14 `v` profiles (7 women, 7 men). Ishita, Riya and Pooja stop at the selfie step, unverified, with no row: they're who this task verifies against (the advisor directing T-1.15, Claude in a separate chat, 3 October 2026).
  **Built:** each selfie the profile's gradient turned round, private only; its record says
  `{"decided_by": "seed"}`, never a comparison; a re-run adds none, and someone seeded before
  T-4.5 gets theirs once.
- [x] **D-078 (P-54):** an under-18 refusal deletes `verifications` rows and the selfies behind them,
  keys read in the deleting transaction before the rows go. Any file this task stores behind a user
  row joins that list, with a test. The challenge still waits for the selfie step (D-068).
  **Held:** a selfie is a photo, so `UNDERAGE_FILES` already reads its key, and T-4.5 stores no
  other file (the re-encoded selfie is written back over its own key);
  `test_a_refusals_selfie_and_its_verification_go_with_it` (critical). A selfie uploaded and never
  sent is replaced by the next and its file deleted (D-263); one compared after its user was
  refused is removed by the run that wrote it back.
- [x] **Tests, and every guard broken once:** `tests/modules/verification/`, `tests/core/test_facematch.py`
  (the real models on NASA's public-domain portraits in `tests/fixtures/faces/`, which prove the
  mechanism, never accuracy), `tests/core/test_queue.py`, `tests/workers/test_verify_selfie.py`,
  `tests/workers/test_wake.py`, `tests/workers/test_worker.py`, `tests/tools/test_selfie_review.py`,
  `tests/seed/test_seed.py`, and the web's `src/i18n/claims.test.ts` and `Avatar.test.tsx`.
  **All 32 API cases red and 4 web cases red,** each file restored by SHA-256, 5 October 2026:
  `uv run python -m tests.break_guards t45-` and `node scripts/break-guards.mts t45-`, kept
  applicable by `tests/test_break_guards.py` and `src/lib/break-guards.test.ts`. **Two breaks
  stayed green at first, each now a finding fixed:** counting every selfie ever sent, not the last
  24 hours' (no test sent only old selfies: `test_selfies_sent_over_24_hours_ago_no_longer_count`
  added); and the wake sent inside the submit's transaction, which the end-to-end test can't see
  (the commit lands microseconds after the publish, long before the listener reads), so only the
  in-transaction check proves the order, and t45-14 names that one. Nothing held the badge's icon
  either: `marks a matched selfie with a face, never a shield` added.
- [x] **Commit:** `feat(verification): selfie face match [T-4.5]`

### T-4.6 · Web photos step
**Changed by T-4.12 (D-391, D-392, filed 7 October 2026):** a slot of its own for the face photo
and its toggle, and the step left without a public photo; these boxes record what T-4.6 built
and proved.
- [x] **Needs:** T-4.3, T-3.12
- [x] 6-slot grid; tap empty slot → file picker (`accept="image/*"`, `capture` not forced); client resize to ≤ 2000 px before upload (canvas) to save data; PUT to presigned URL with progress; states per slot: uploading %, checking, approved, rejected (with reason + retry). Drag to reorder (or up/down buttons on mobile).
  **Built** (`PhotosStep`, `PhotoSlot`, `usePhotoSlots`; hooks in `src/lib/queries/photos.ts`):
  every photo the browser can read goes up as a JPEG drawn on a canvas, at most 2000 px
  (`src/lib/resize-image.ts`); one it can't read goes up as it is, and the API's answer says what
  it is (D-089, D-082). The PUT is `src/lib/upload.ts`, an XMLHttpRequest for its progress, the
  web's only one: ESLint now bans `XMLHttpRequest` outside `src/lib` as it bans `fetch`. A photo
  goes in the first free place, and removing or clearing one closes the gap, as the prototype's
  grid does, so place 0 stays the main photo. Up and down buttons sit beside every photo, always
  shown on a touch screen.
- [x] Women see the private-album note.
- [x] **A rejection's reason on screen:** `GET /me/photos` lists only live photos (T-4.3), so a photo
  moderation rejects drops out of it. This task decides how its reason (D-093's wording for a
  possible minor) reaches the slot that showed it, before building the "rejected" state.
  **Decided as D-096 (Open, for the founder's approval):** `GET /photos/{id}` reads that one photo,
  and the API names a reason only from a list, so `minor_suspected` reaches the person as `other`,
  in D-093's words.
- [x] Built in T-3.11's `StepFrame`, at D-080's `/onboarding/photos`, replacing T-3.12's placeholder.
- [x] **Widen the CSP here (D-059):** `connect-src` for R2's upload endpoint (the presigned PUT), and `img-src` for `PUBLIC_CDN_URL` and `blob:` previews. Uploads and previews fail with a CSP error until then.
  **And `img-src` for R2's own endpoint too** (found 4 October 2026): `GET /me/photos` gives a
  pending or private photo as a signed link to the private bucket, on R2's endpoint
  (`https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`, path-style, T-4.1), not the CDN. Without it a
  photo shows only once approved.
  **Done** (`src/lib/storage-origins.ts`, by `APP_ENV`): each bucket by its path, never the whole
  endpoint, which staging and production share. **Proved locally by its effect, 4 October 2026,** in
  Playwright's Chromium against a production build (`APP_ENV=local`): the upload, its preview and
  the signed link all loaded, and the browser refused the rest in its own words, e.g. "Connecting
  to 'http://127.0.0.1:9000/velora-public/probe' violates the following Content Security Policy
  directive: "connect-src 'self' http://127.0.0.1:8001 http://127.0.0.1:9000/velora-private/". The
  action has been blocked.", and "Loading the image 'http://127.0.0.1:9000/other-bucket/x.jpg'
  violates the following Content Security Policy directive: "img-src 'self' blob:
  http://127.0.0.1:9000/velora-private/ http://127.0.0.1:9000/velora-public/"".
  **And on staging, the same day,** after `aba62e5`'s deploy (run 37222076586, every job green,
  smoke included), in Chromium on `https://staging.veloraapp.co.in`: staging's own private bucket
  admitted (below), and refused, each in the browser's words, production's private bucket on the
  same endpoint ("Connecting to 'https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com/velora-prod-private/probe'
  violates the following Content Security Policy directive: "connect-src 'self'
  https://api.staging.veloraapp.co.in https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com/velora-staging-private/
  …". The action has been blocked."), staging's public bucket for a PUT, an image from production's
  private bucket, and one from production's CDN; an absent key on staging's CDN failed as a 404
  with no violation.
- [x] **CORS on the private bucket, or no browser can upload at all** (found 4 October 2026). The
  presigned PUT goes from the web's origin to R2's endpoint: cross-origin, with a `Content-Type`
  header, so the browser asks first, and R2 refuses without a CORS rule. Our tokens are Object Read
  & Write and can't set one, so the founder sets it in Cloudflare (R2 → `velora-staging-private` →
  Settings → CORS policy), exactly this, and production's the same with `https://veloraapp.co.in`
  before REL-1:
  `[{"AllowedOrigins": ["https://staging.veloraapp.co.in"], "AllowedMethods": ["PUT"], "AllowedHeaders": ["Content-Type"], "MaxAgeSeconds": 3600}]`.
  Signed links shown in `<img>` need no CORS. Locally the web (`127.0.0.1:3000`) and the S3
  (`127.0.0.1:9000`) are different origins too, so the local S3 (D-086) needs the same rule for the
  local web: proved by a real upload from the browser, not assumed.
  **Local: done.** SeaweedFS answers every origin unless a bucket has a rule of its own, so
  `s3-init` sets `infra/s3/private-cors.xml` on `velora-private` at every `make infra-up` and in
  CI, and `api/tests/test_local_s3_cors.py` holds the bucket to it by preflight. Proved on 4 October
  2026 by a real upload in Playwright's Chromium from `http://127.0.0.1:3000`: the PUT went with
  `Content-Type: image/jpeg` and nothing else, and the API received a 2000 × 1500 JPEG; Chrome
  refused DELETE ("Method DELETE is not allowed by Access-Control-Allow-Methods in preflight
  response") and another origin ("No 'Access-Control-Allow-Origin' header is present on the
  requested resource"). **Staging: set by the founder the same day, with `GET` as well as `PUT`,
  and checked from outside at 15:48 UTC** (`infra/STAGING.md` §3): the staging origin's PUT
  preflight passes, every other origin, method and header gets R2's 403. **Then by a real
  browser's upload, the same day:** a PUT signed inside staging's API machine with its own keys,
  under `probe/` as T-4.1's probe writes, sent by Chromium from `https://staging.veloraapp.co.in`
  with exactly the signed `Content-Type`: R2 answered 200 with `Access-Control-Allow-Origin:
  https://staging.veloraapp.co.in`, upload progress reached the page, and what arrived, read back in
  the machine, was 10 bytes of `image/jpeg` beginning `ffd8ffe0`; then deleted, and read back as
  gone. (R2 answers an unsigned request with 400 before CORS applies, so only a signed one shows
  both legs.) **Then through the photos step itself,** signed in, on 5 October 2026 (below).
  **And narrowed to `PUT` only** the same night, `GET` removed by the founder: checked at 19:12
  UTC, the staging origin's `PUT` preflight names `PUT` alone, and a `GET` preflight gets R2's 403.
- [x] **Done when, on a real iPhone, on this control (D-089):** iOS Safari's upload sends JPEG, not
  HEIC, read from what the API received (its bytes), never reasoned about. If it sends HEIC, "no
  HEIC" breaks every iPhone sign-up: stop and tell the founder before anything ships. D-089 is
  Locked when this passes.
  **Where it stands, 5 October 2026 (unticked):** a fresh sign-up on staging at 01:06 IST went
  through the photos step and uploaded two photos, at 01:08:06 and 01:08:34 (the API's request
  log). `complete` read each one's bytes on arrival and accepted both, and it refuses HEIC there,
  so **neither arrived as HEIC.** One was approved by T-4.4's worker on staging; the other was
  rejected `no_face`, and the page read its reason back by `GET /photos/{id}` (D-096).
  **The limit, exactly:** not HEIC, which is not the same as JPEG. Whether they were JPEG rather
  than PNG or WebP is unknown: the worker writes its re-encode over the upload within seconds
  (`moderate_photo`, D-101), so the bytes as received were gone before anything else read them.
  The advisor's ruling (Claude, in a separate chat, relayed by the founder, 5 October 2026): that
  excludes D-089's risk, a HEIC refused breaking every iPhone sign-up, by direct evidence, and the
  format question stays open at no cost; no further watcher for it.
  **What it rests on, open for the founder:** which device made the 01:06 sign-up. The evidence is
  the iPhone's only if it was the iPhone, in Safari; until he says, this box stays unticked and
  D-089 stays Open.
  **Closed by the founder, 5 October 2026, in his own words (given in Hinglish, recorded here in
  English), on exactly this basis:** on staging at 01:08 IST two photos arrived; `complete` read
  each one's bytes and accepted both, and the same place refuses HEIC, so no HEIC arrived. That
  excludes D-089's real risk, a HEIC refused breaking every iPhone sign-up. **The device that made
  that sign-up wasn't recorded, so "iOS Safari" was not separately confirmed, and that is this
  box's one gap.** D-089 stays Open, not Locked as this box's first lines once said, because the
  format (JPEG, or PNG or WebP) and the device are both still open; P-165 records an iPhone's
  upload before REL-1. **The rows, read by Claude the same day** (read-only, on staging's API
  machine): two public photos created at 19:38:04 and 19:38:33 UTC (01:08 IST), both scored by
  moderation, which only a photo `complete` accepted reaches (a refused upload is rejected there
  and never scored); one approved, one rejected `no_face`.
  **To settle first, 5 October 2026 (the founder):** whether the photo completed at 00:44:59 IST
  (the desktop one, most likely: the only upload then) and the 01:08 photo that was refused both
  had a clear face. If they did, D-101's `no_face`
  refused real faces two times out of three, and it needs tuning before real users. Not a finding
  yet: two photos nobody here has seen.
- [x] **Commit:** `feat(web): photo upload step [T-4.6]`

### T-4.7 · Web selfie step
**Changed by T-4.12 (D-391, filed 7 October 2026):** the copy says the selfie is compared with
the face photo, not "your photos"; these boxes record what T-4.7 built and proved.
- [x] **Needs:** T-4.5, T-4.6
- [x] Start the verification (no pose: T-4.5) → `getUserMedia({video:{facingMode:"user"}})` → live mirrored preview → capture to canvas → upload as `kind=selfie` → submit → poll `GET /verification/latest` every 2 s (max 60 s) → result. Handles permission denied with instructions per browser.
  **Built** (`SelfieStep`, `SelfieCamera`, `useSelfie`, `selfieCopy`; `src/lib/camera.ts`; hooks
  in `src/lib/queries/verification.ts`): the front camera asked for 1280 × 720 at best (most
  browsers give 640 × 480 otherwise, small for comparing faces), the preview mirrored and the
  picture taken not, a canvas JPEG with no EXIF. **The picture is checked before it's sent**
  ("Use this selfie" / "Retake", right after capture and before any upload: each sent selfie is
  one of five a day, and a woman can't skip; T-4.7's plan, question 2, answered in the text the
  founder relayed, 5 October 2026). Asked every 2 s while compared, for a minute a round; then
  "Check again" starts another. **Permission denied, per browser,** from each one's own help
  pages, read 5 October 2026: Chrome on Android and on a computer, Firefox on a computer, Safari
  on a Mac (Apple's Safari guide). The iPhone's steps are Safari's own menus (aA, Website
  Settings) as help pages beyond Apple's describe them: Apple's iPhone guide didn't show them when
  read. Edge, Samsung Internet, Opera and Firefox on Android get the general line, since their
  menus differ. **None of the instructions has been seen on a real phone.**
- [x] Men: "Skip for now". Women: cannot skip.
  **Built:** "Skip for now" for `gender == "male"` only, an allowlist. It and a match's
  "Continue" lead to a panel in place, "That's everything for now. The rest of sign-up opens
  next.", never to `/discover`, whose gate sends anyone not `done` straight back to this step
  (T-4.7's plan, question 1, answered in the text the founder relayed, 5 October 2026). T-4.8
  wires both to its completion endpoint; the server's rule, not this screen, is what stops a woman.
- [x] **The copy claims face matching only** (T-4.5's hard constraint): the screen says the selfie
  is compared with the profile photos, never that it confirms a real or live person.
- [x] **No spinner to watch** (D-261, the founder's constraint on T-4.5): the result usually comes
  in seconds, by the wake. While she waits, the screen says what is happening ("comparing your
  selfie with your photos"); if nothing has come after about 15 seconds, it says plainly that it
  can take a minute and she can leave, and the result is there when she is back (the queued job
  decides it within D-091's 10 seconds, or tries again). Never a bare spinner. A rejection's reason
  comes from D-263's list, in words that say what to change, never an accusation; `attempts_left`
  says how many tries remain today. The prototype's "Face matched — verified" is overridden
  (D-262); `web/src/i18n/claims.test.ts` fails on it.
  **Built:** the selfie shown in its circle with "Comparing your selfie with your photos…", the
  can-leave line from 15 seconds, "Still comparing" and "Check again" at a minute. Each D-263
  reason says what to change (`no_photos` links back to the photos step); anything unlisted reads
  `other`; `RATE_LIMITED`'s `retry_after_s` becomes "about N minutes" or "about N hours". The step
  repeats `/privacy`'s "Our team may look at it to check a comparison" where the selfie is taken,
  and `claims.test.ts` holds that line and the prototype's selfie-screen words.
- [x] Built in T-3.11's `StepFrame`, at D-080's `/onboarding/selfie`, replacing T-3.12's placeholder.
  **Done:** `ComingNextStep` and its string are gone.
- [x] **Allow the camera here (D-059):** T-2.5's Permissions-Policy has `camera=()`, so `getUserMedia` is refused until this task makes it `camera=(self)`; add `blob:` wherever the captured frame shows. T-4.9's fake-camera E2E fails until then.
  **Done:** `camera=(self)` on every page, not only this one: a page reached by Next's client-side
  navigation keeps the policy of the document first loaded, so a policy on one path would refuse
  anyone arriving from the PIN step. `blob:` was already there: T-4.6's `img-src` has it on every
  build with photo storage, and a build without storage can't upload a selfie either.
  **Proved by its effect, 5 October 2026, by Claude,** in Playwright's Chromium against a
  production build (`APP_ENV=local`), the API and the worker with the real face models (D-088) on
  a database of their own (dropped after), a fake camera playing the committed NASA portraits:
  - Served with T-2.5's `camera=()` (a loopback proxy rewriting only that header), the browser
    refused in its own words, "Permissions policy violation: camera is not allowed in this
    document.", and the step said the camera was blocked, with Chrome's way to allow it.
  - Served as built, `camera=(self)`: the camera opened at 1280 × 720, the preview mirrored
    (`scale: -1 1`), the picture checked as a `blob:` image, no CSP violation anywhere. A fresh
    woman whose one public photo is `chari_2021`, signed in through the screens and never offered
    "Skip for now", sent four selfies: Chrome's own test pattern → `no_face` (0 faces); three
    people → `many_faces` (3); Williams → `no_match` (best 0.098); Chari's 2017 portrait → matched
    (0.867, threshold 0.363). Tries read 4, 3, 2. **Each result showed about 2.4 seconds after
    "Use this selfie"**, all four decided by the wake (`decided_by: wake`).
  - With the worker stopped before the selfie was sent, so its wake was lost: the can-leave line
    at 15.5 s, "Still comparing" at 60.2 s with no more asking, the worker started again, and
    "Check again" showed the match at 85.5 s, decided by the queue (`decided_by: queue`): D-261's
    other path, seen through the screen.
  The run's script and fake-camera videos stay in that session's scratchpad: the evidence is this
  record, and T-4.9's fake-camera E2E is the standing check. The run was on the branch before it
  was rebased onto T-4.10, whose only overlap is the same header's `geolocation=(self)` and one
  more progress segment (the selfie is now 13 of 13); `make lint test` and CI ran on the rebased
  commit.
- [x] **Tests, and every guard broken once:** `SelfieStep.test.tsx`, `camera.test.ts`,
  `queries/verification.test.tsx`, `security-headers.test.ts`, `claims.test.ts`. **All 20 web
  cases red,** each file restored by SHA-256, 5 October 2026 (`node scripts/break-guards.mts
  t47-`). **One stayed green at first, a finding fixed:** asking every 10 seconds instead of 2
  (`t47-poll-02`), because the hook's test advanced time by the constant itself, so a slower poll
  slowed the test with it; it now waits the plan's own 6 seconds.
- [x] **Commit:** `feat(web): selfie verification step [T-4.7]`

### T-4.8 · Finish onboarding
**Changed by T-4.12 (D-392, filed 7 October 2026):** `photo` leaves what `done` needs,
completeness unchanged; these boxes record what T-4.8 built and proved.
- [x] **Needs:** T-4.5, T-4.10
- [x] Service `onboarding.complete()`: requires profile fields, username, 5 interests, ≥ 1 public photo, location (T-4.10), and for women an `approved` verification → step `done`, compute `completeness`.
  **Built** (`app/modules/onboarding/`, D-310): `POST /me/onboarding/complete` answers `Me`. Each
  requirement missing is named in `PROFILE_INCOMPLETE`'s `details.missing`, all at once, in
  onboarding's order (seeking and 1 to 3 intents among them; a photo means an approved public
  one). Anyone but a man without `is_verified`, T-4.5's own record of the match, gets
  `VERIFICATION_REQUIRED`: an allowlist. Completeness is 50, and 10 for each approved public
  photo after the first. **And in the database:** `users_done_needs_a_match` refuses any write
  moving anyone else to `done` unmatched, read back by the deploy beside D-076's triggers. The
  seed's finished profiles get their completeness by the same rule (all 50). The five answers
  that shaped it are D-310's, by the advisor directing T-4.8 (Claude, in a separate chat), relayed
  by the founder, 5 October 2026.
- [x] **Wire the selfie step's two ways on** (T-4.7): a man's "Skip for now" and a match's
  "Continue" (`useSelfie`'s `finish()`) show an in-place panel until this task, since nothing
  moves `selfie` to `done`. This task points both at its completion endpoint and its answer, and
  drops the panel's string, `onboarding.selfie.next`.
  **Built:** both call `useCompleteOnboarding()` and go where the `Me` it returns says
  (`/discover`). A refusal names the first thing missing, with "Take me there" to its screen, or
  says the selfie hasn't matched and reads `Me` and the latest verification afresh. The panel and
  its string are gone.
- [x] **Tests, and every guard broken once:** `tests/modules/onboarding/` (each requirement,
  each refusal, the step rule, the trigger and its migration, a forced race with moderation),
  `tests/seed/test_seed.py`, `tests/test_migrate_with_url.py`, `tests/test_app_role.py`, and
  `SelfieStep.test.tsx`. **All 8 web cases red** (`node scripts/break-guards.mts t48-`), each
  file restored by SHA-256, 5 October 2026. **All 27 API cases red** (`uv run python -m
  tests.break_guards t48-`), the same day. The race test was changed after that full run, to put
  its committed man back as `fresh_man` leaves one (its intents had stopped
  `test_migrations_round_trip`'s downgrade); the two cases resting on it were run again, red.
  **One stayed green at first, a finding fixed:** counting a photo whatever its status
  (`t48-a-removed-photo-counted`). The test's rejected photo had no `public_key`, but `DELETE
  /photos/{id}` keeps it (T-4.3), so the test hid the case the status check exists for. The test
  now holds a removed photo as T-4.3 leaves it, and the case is red.
- [x] **Commit:** `feat(onboarding): completion rules [T-4.8]`

### T-4.9 · E2E onboarding
**Changed by T-4.12 (filed 7 October 2026):** J1 and J2 follow the redesign; these boxes record
what T-4.9 built and proved.
- [x] **Needs:** T-4.7, T-4.8, T-4.10
  **Uploads need two things the E2E doesn't have yet** (found building T-4.6): the local S3's CORS
  rule (`infra/s3/private-cors.xml`) admits only `make dev`'s web, `http://127.0.0.1:3000`, and
  the E2E's is on 3100; and CI's e2e job starts Postgres and Redis but no S3, and its API
  (`api/tests/e2e_server.py`) stores to the fake. Each upload fails until both change.
  **Done, and a third found:** the rule has a second `CORSRule` for `http://127.0.0.1:3100`, PUT
  and Content-Type only, held by `api/tests/test_local_s3_cors.py` for both origins (its 3100 case
  was red before `make infra-up` applied the rule, green after); CI's `e2e` job starts the S3 and
  runs `s3-init` as the `api` job does, and the launcher stores to it (`STORAGE_PROVIDER=s3`,
  refusing to start when it isn't reachable). **The third: the E2E had no worker.** The launcher
  ran uvicorn alone, so no photo was ever approved, T-4.8's completion refused `PROFILE_INCOMPLETE`
  with `photo` missing, and no selfie was ever compared: both journeys stopped without one. The
  launcher now runs `python -m app.workers` as a child on the same slot (D-330), its settings in
  its environment and never from `api/.env` (its working directory is `tests/`, which has none;
  `PYTHONPATH` names `api/`, since `app` isn't installed into the venv), polling every 0.5 s with
  the reason written where it is set, and stopped from the signal handler uvicorn puts back after
  its own shutdown: a plain `finally` never ran, and the first by-hand stop left the worker
  running (seen, then fixed, 5 October 2026). The models are checked before anything starts, with
  the worker's own refusal, so a missing model stops the run at once with D-088's message.
- [x] Playwright with fake camera flags: man completes without selfie; woman is blocked until selfie approved.
  **Built** (`web/e2e/signup.spec.ts`, `web/playwright.config.ts`): J1 now runs to Discover and
  J2 is new, both at 390 × 844 and 1280 × 800, through the screens alone. The photo is chosen
  through the slot's own picker (the file chooser answered), uploaded by the presigned PUT to the
  local S3, checked by the worker (the fake moderation) and read back as "Approved" before
  Continue, since finishing needs the approved public copy (D-310); five interests; J1 sets and
  confirms a PIN (`4719`, one D-069 allows), J2 skips it. At the selfie: J1 sees "Skip for now"
  and J2 doesn't; each visits `/discover` and is sent back by the gate. J1's "Skip for now"
  finishes sign-up (T-4.8) and lands in Discover inside the shell's four-link nav; J2 opens the
  camera (`camera=(self)`, T-4.7), waits for a presented frame, takes the shot, checks it, sends
  it, reads "Comparing your selfie with your photos…", then "Your selfie matches your photos.",
  the real models' verdict (D-088) on the browser's selfie against her photo, and "Continue"
  finishes. Both reload once in the app. No URL carries the number (D-080); any CSP violation
  fails them (T-3.13's fixture).
  **The camera** is Chromium's fake one, playing NASA's 2017 portrait of Raja Chari
  (`api/tests/fixtures/faces`) as a one-frame MJPEG copied at config load, never committed; her
  profile photo is his 2021 portrait, so the match is between two photos of one person. His photo
  is Sunita Williams', since a man's selfie is never compared. The names are the test's.
  **Found on the way, 5 October 2026:**
  - **Playwright's headless shell has no media capture:** `getUserMedia` there is
    "NotSupportedError: Not supported" (probed before the spec was written). The journeys run on
    the full Chromium in its new headless mode (`channel: "chromium"`), which `playwright install
    chromium` already installs beside the shell. T-4.7's hand run was on that build.
  - **The first frame isn't drawable the instant the shutter enables** (`loadeddata`): a frame
    drawn then was black in the probe, a real one 1.5 s later. A person looks at the preview before
    tapping; the spec waits for `requestVideoFrameCallback` to say a frame was presented. Not a
    product bug: the review screen shows the shot before it's sent, and a black one would be retaken.
  - **A restored session with a PIN is locked on an onboarding step too** (T-3.10, by design): J1's
    visit to `/discover` is a full load, the gate sends him back to the selfie, and the lock sits
    over it until his PIN; the first run's "Skip for now" waited two minutes under the dialog. J1
    now unlocks there and again after its reload in the app, so the lock after a restore is in the
    E2E as well.
  - `getByRole("button", { name: "Men" })` also matches "Women": the name is a case-insensitive
    substring unless `exact`.
  **Recorded:** D-330 (Open, extending D-084, which is Locked and not edited); 06-TESTING's E2E
  section and J1/J2 rows; CLAUDE.md's and the Makefile's `make e2e` lines (`make models` is now
  a prerequisite).
  **Proved, 5 October 2026, by Claude:** `make e2e`, all 14 journeys green in 2.5 minutes, the
  build included (J1 9.1 s and 8.5 s, J2 11.3 s and 10.7 s, phone and desktop). **Read back from
  the run's own database** (slot 2, before the next run dropped it): both men `done`, not
  verified, completeness 50, one approved public photo each; both women `done` and `is_verified`;
  both selfies approved, **decided by the wake** (D-261), best similarity 0.856 against the 0.363
  threshold, 480 × 600 after re-encode; four public photos moderated. The first full run's two
  failures were the spec's own, above (the lock over "Skip for now", "Men" in "Women"), and were
  the only ones.
  **Six breaks of what the journeys guard, each on the phone project, each file restored and
  checked by SHA-256** (the script stays in that session's scratchpad: it weakens one file as a
  careless change would, runs the journey, and puts the file back; the spec is the standing
  check):
  - the 3100 rule taken out of `private-cors.xml` (and `make infra-up` run): J1 red at the
    "Approved" wait, the slot reading "This photo didn't upload — check your connection and try
    again", the browser's refusal of the PUT's preflight;
  - the worker not started (a sleeping child in its place): J1 red at the same wait, the slot
    reading "Checking…" for 30 seconds;
  - the fake camera's device flag removed from `playwright.config.ts`: J2 red, the camera's
    ready line never shown;
  - `MAY_SKIP` widened to women in `SelfieStep.tsx`: J2 red, one "Skip for now" where none may be;
  - the gate's redirect for an unfinished sign-up replaced by none in `AppGate.tsx`: J1 and J2
    both red, `/discover` served instead of the selfie step (a first weakening, `&& false`, didn't
    build, so it proved nothing and was replaced);
  - her profile photo swapped for Sunita Williams' in the spec, the camera still playing Chari:
    J2 red, "Your selfie matches your photos." never shown in 30 seconds. **This is the one the
    fake face match could never fail,** and why the E2E runs the real one (D-330).
- [x] **Commit:** `test(e2e): full onboarding [T-4.9]`


### T-4.10 · Location
- [x] **Needs:** T-3.5, and **P-38** (the seeded areas are still Bengaluru's; D-013 is Phagwara), and **P-65** before P-38: P-38's data migration is the next migration in the plan, and its deploy must read back the database's own head and D-076/D-077's guards
- [x] `PUT /me/location` accepts `{lat,lng}` (must be inside India bounding box) or `{area_id}` (uses centroid). `GET /areas?city=`.
- [x] Web: onboarding asks permission once with a clear reason; on deny → area picker. Location refreshed on app open if > 6 h old. The question has no `onboarding_t` step: give it a slug in D-080's map and a place in the flow, in T-3.11's `StepFrame`.
- [x] The seed (T-1.15) gives each profile both its `area_id` and a location scattered near that area's centroid, as if it had shared its position. If `{lat,lng}` here leaves `area_id` empty, or sets it some other way, make the seed match.
- [x] **Allow location here (D-059):** T-2.5's Permissions-Policy has `geolocation=()`, so the browser refuses the position without ever asking until this task makes it `geolocation=(self)`. Until then everyone silently lands on the area picker.
- [x] **Commit:** `feat(profiles): location [T-4.10]`


### T-4.11 · Liveness — deferred past launch (D-380)
- [x] **Needs:** T-4.5 (built, `3ed0f6d`); the research below naming a model (done, Claude, 5
  October 2026); and the founder's decision on it: **made, 7 October 2026, on six questions the
  advisor (Claude, in a separate chat) put to him from the research, taken on the advisor's advice
  (D-380). Liveness waits until after launch, with real users.** That day this task left REL-1's
  conditional list and T-9.15's Needs line, and D-008 was amended: the selfie and its face match
  (T-4.5) stay mandatory for women, and passive liveness is not D-008's "liveness verification"
  (D-380's second decision). Split out of T-4.5 by the founder, 4 October 2026, so T-4.5 ships face
  matching without it. **Its scope (D-380's first decision):** a print, a screen or a replay held in
  front of the camera. A selfie that already exists, uploaded as a file, isn't this task's to stop:
  that takes a freshness mechanism, a separate decision, not yet made.
- [x] **What is known, so the research starts from it** (read by Claude, 4 October 2026):
  Sightengine's `liveness` model is passive, one photo, no head turns: a score from 0 to 1 and a
  rejection reason (`no_face`, `too_many_faces`, `inanimate_face`, `invalid_face`, `spoof`,
  `deepfake`, `ai_generated`), on the same `check.json` endpoint as T-4.4's moderation. It isn't on
  the free plan: one call with our keys, on Sightengine's own example image, was refused with
  "Access to the Liveness Detection API is restricted. Feature not available on the free plan.
  Switch to a paid plan" (0 operations charged). Its pricing page lists it under Pro, $99 a month,
  and its documented example consumed 10 operations a check. **Not bought** (the founder): about
  ₹8,300 a month, roughly ₹1 lakh a year, before the product has a single paying user. **Still so on
  7 October 2026** (Claude, both pages read again that day): the pricing page lists "Liveness
  Detection" under Pro, $99 a month, and not under Starter ($29) or the Free tier; the docs' example
  response still shows `"operations": 10`, and the seven rejection reasons above are still the
  documented ones. **The refused call of 4 October was not run again.** Sightengine is the baseline
  the research compared against, not an option (the founder): it judges "a single static photo or
  frame" too (its docs' words), and the word "injection" is nowhere on its page.
- [x] **The research, first: the licences read, memory measured, a model named** (Claude, 5 October
  2026, reported to the founder; the advisor put six questions to him from it, answered 7 October
  2026, D-380). **Every number below can be run again:** the probe is `api/bench/liveness/` (D-381),
  its package docstring says how; every run's raw readings are in `out/t-4.11-probe/` on the machine
  that ran them (git-ignored); the plan holds ranges and modes.
- **The research named MiniFASNet** (Claude's recommendation; the founder chose no model, he
    deferred the task): minivision's Silent-Face-Anti-Spoofing, MiniFASNetV2 at crop scale 2.7 and
    MiniFASNetV1SE at 4.0, the pair its authors ship, 0.43M parameters each, about 3.5 MB of ONNX in
    all. **Its licence, read:** the repository's `LICENSE` (commit `b6d5f04`, 5 August 2020) is the
    Apache License 2.0, "Copyright 2020 Minivision", and the weights sit in that repository under it
    (`resources/anti_spoof_models/`, 1,849,453 and 1,856,130 bytes, SHA-256 `a5eb02e1…` and
    `84ee1d37…`); neither README adds a research-only term. **Its weights, verified:** the two ONNX
    exports the probe runs (yakhyo/face-anti-spoofing's release, Apache-2.0) and a third
    (garciafido's on Hugging Face, which states the upstream `.pth`'s SHA-256, matching minivision's
    file) were run through OpenCV's DNN beside minivision's own `.pth` through its own network code:
    over 506 inputs (500 random patches and the 6 faces YuNet finds in the four NASA fixtures, at
    both crop scales) the largest softmax difference is 2.38e-07 (V2, both exports) and 3.58e-07
    (V1SE) (`same_weights.py`; the same on 7 October 2026). **Its training data:** private, by
    minivision's own words (P-0.7 carries the flag, D-380's fourth decision). **One caution:**
    minivision's repository also ships InsightFace's RetinaFace detector
    (`Widerface-RetinaFace.caffemodel`), which D-088's rejection covers; it is never fetched or
    shipped, and the crop takes YuNet's box, the worker's own detector. MiniFASNet was trained on
    RetinaFace's boxes, and what YuNet's do to its accuracy only P-280's set can show.
- **Memory, measured** (this Mac's arm64 Docker, one CPU, 1 GB, no swap: not Fly, where 962 MB is
    usable; the API image built from the repository; the worker's own `SFaceFaceMatch.compare` on a
    1,600-pixel selfie against two 1,600-pixel photos, as T-4.5's probe on Fly did, then the route's
    liveness score, 22 times; peak is the process's VmHWM). **Baseline, face matching alone: 392 to
    406 MB, mostly 403 to 404 (the committed probe, 20 runs on 7 October 2026; 5 October's probe,
    not committed, read 392 to 404, mostly 404, over the same 20 interleaved runs).** T-4.5 measured
    the same comparison at 403 MB here and 405 MB on Fly, so the method agrees with the machine.
    **MiniFASNet through OpenCV's DNN, the image's own, no new dependency: 409 to 410 MB, mostly 410
    (20 runs on 7 October 2026, and the same from 5 October's probe).** The same two files through
    onnxruntime 1.30.0: 441 MB (441/441/442 on 5 October, 441 three times on 7 October), and a 20 MB
    dependency. minivision's `.pth` through PyTorch 2.14.1 (CPU): 628 to 630 MB, a 152 MB wheel, and
    a `.pth` is a pickle (D-381). On Fly, adding each route's cost to T-4.5's worst moment (207 MB
    resident plus 343 MB for the worst photo decode, about 550 of 962): about 556, 570 and 742 MB, a
    projection, not a measurement.
- **A finding about the probe itself, so the next measurer doesn't trust n = 3:** 5 October's three
    identical readings (404/404/404) were taken as deterministic. Eight runs on 7 October showed
    they were not (392 to 407), and in 20 interleaved runs the original went to 392 five times.
    Three identical draws are not proof of determinism. **So: the probe's baseline varies 392 to 406
    MB run to run with no code change (5 October's, 392 to 407), and a difference under about 15 MB
    between two routes is not something this probe can tell apart. MiniFASNet's +6 MB is inside
    that; the decision rests on single-digit MB against about 400, not on the 6.** **And the
    committed probe against 5 October's:** the probe is a port of that day's `bench.py` (kept
    outside the repository, its DAMO routes dropped); run 20 times each, interleaved, in the same
    image with the same flags, the original read 392 to 404 MB, mostly 404, and the port 392 to 406,
    mostly 403 to 404; on MiniFASNet both read 409 to 410, mostly 410. The record here is the
    port's, since it is what can be run again; the raw readings of all 60 runs are in
    `out/t-4.11-probe/interleaved/` and `interleaved-2/` on the machine that ran them.
- **Four comparisons at once don't fit, with or without liveness:** about 1,060 MB (1,062 to 1,064
    observed, swap allowed, face matching alone or with MiniFASNet loaded), and with swap off, as
    Fly runs the worker, the process is killed, exit 137. The worker never does that today, by the
    comment at `app/workers/main.py:64-66`, not by a check: P-281.
- **DAMO's two models (ModelScope, `damo/cv_manual_face-liveness_flrgb` and `_flxc`): no licence**
    (D-380's fifth decision). Each repository holds `.gitattributes`, `configuration.json`,
    `model.onnx`, `README.md` and an image, and no LICENSE file (listed 5 October, and again 7
    October 2026); the model card's front matter says `license: MIT License` and nothing more, with
    no copyright line, while MIT's own text requires that "the above copyright notice and this
    permission notice shall be included". A tag isn't a licence text, so D-088's standard isn't met;
    not research-only, so not InsightFace's rejection either. Their training data is private
    ("在私有数据集上", the cards). **The probe's two DAMO routes, and their memory readings, were dropped
    together on 7 October 2026** (the founder): a rejected model's numbers decide nothing later, and
    numbers nobody can re-run are worse than none; if the licence is ever settled, measuring again
    is cheap. (modelscope.cn reset the connection three times on 5 October.)
- **Rejected on their licences, each read:** facenox/face-antispoof-onnx, and
    kprokofi/light-weight-face-anti-spoofing with Intel's OMZ `anti-spoof-mn3`, all trained on
    CelebA-Spoof, whose agreement says it "is available for **non-commercial research purposes**
    only" and "You agree **not to** … exploit for any commercial purposes, any portion of the images
    and any portion of derived data" (a trained weight is derived data: rejected as InsightFace
    was); the Hugging Face ViT and DINOv2 fine-tunes (nguyenkhoa's, Molkaatb's and others), each "on
    an unknown dataset"; biometric-ai-lab/Antispoofing (its tag says apache-2.0, its badge MIT);
    KBY-AI ("requires a license for each machine or instance"); uniface (no model of its own: it
    downloads yakhyo's files, and needs onnxruntime); InsightFace (D-088, unchanged).
- **The finding that shaped D-380: passive single-photo liveness, ours or Sightengine's, doesn't
    stop D-260's attack.** The selfie reaches the server as bytes, by a presigned PUT
    (`photos/service.py`, `storage.presign_put`); the server can't tell a camera from a file, so a
    man with one real selfie of her uploads it as it is, a photo of a live face, which such a model
    is built to call real. Shown by its effect: a NASA portrait, never in front of our camera,
    scored 0.8949 "real" through the real pipeline (5 October, and again 7 October 2026). One image,
    not a rate. What stops that is freshness, something in the selfie that couldn't exist before the
    request, chosen by the server; the pose challenge stays rejected; so until such a thing exists,
    D-264's human is the only thing in that attack's way (D-260's amendment).
- **Retries:** an attacker gets 5 tries a day (D-263). At 1% a try he is through within a week 29.7%
    of the time; at 5%, 83.4%. Passive liveness slows a stubborn attacker; it doesn't stop him. And
    no measurement of 30 people can show "nobody can be impersonated": 0 breached of 30 bounds it at
    9.5%, no lower (P-280).
- [ ] **The research, second: accuracy measured, on attacks we make ourselves against consenting
  people, never a paper's claims** (D-088's standard, as this task's research line put it on 4
  October 2026). **Open, on P-280:** 30 consenting people, 1,350 captures, on the real capture path,
  after launch (D-380's third decision). No README's accuracy number stands in for it, and this box
  doesn't tick without it. That is the founder's standard, held on his word, not a mechanism: D-260
  shows he has shipped face matching unmeasured.
- [x] **The pose challenge stays rejected.** Its condition, "until that research exists", is met:
  the research exists (above). The founder's rejection of 4 October 2026 stands, unchanged on 7
  October (D-380's first decision): Claude called it weak and so did he, and "a weak check that
  looks like a strong one is worse than no check". The research didn't evaluate a pose; what a
  freshness mechanism would be is a separate decision, not made.
- [ ] **Commit:** `feat(verification): liveness [T-4.11]`, after launch, with real users (D-380).

### T-4.12 · Photos and verification redesign: a face photo for the check, public photos as she likes, nobody needs one (D-390 to D-393)
**Filed 7 October 2026, docs only; nothing is built yet.** The founder's decision of that day, in
five parts, written by the advisor (Claude, in a separate chat) and relayed by the founder; the
badge's rule (D-393) in his own words. **Why one new task and not six boxes reopened** (the
founder, 7 October 2026, on the advisor's advice and Claude's): rule 11 wants a new migration
whatever happens; T-4.3 to T-4.9's Done-whens quote staging runs and break-guard runs on named
commits, and reopening them would make those records claim things about code that no longer
exists; and one task is one commit series and one break-guard sweep. Each task this changes keeps
its box and carries one pointer line to here. **Where it sits:** on T-6.2's Needs line, since the
`Card`'s badge and its photo-less fallback are this task's rules; and on REL-1's conditional list,
"if the tag includes T-4.6", as the advisor's recommendation for the founder to confirm.
- [x] **Needs:** T-4.5, T-4.8, T-4.9 (all built); D-390 to D-393 (filed, below); and this task's
  own plan, answering its four open points (below) before any code.
- [x] **What changes, in one place:**
  1. **Gender isn't verified, and now that is deliberate (D-390).** Nothing is built for it; D-264's
     human review is what stands against a man who picks "Woman" and matches his own face.
  2. **A face photo for the selfie check (D-391).** `PhotoKind` gains `verification` (the
     identifier only: in copy the photo is never called that, since `claims.test.ts` refuses
     `/verif/i`; "face photo" is the advisor's recommendation). One migration: the type rebuilt as
     `4a7e20790605` rebuilt `ledger_reason_t`, never `ALTER TYPE … ADD VALUE` (a value added that
     way can't be removed, nor used in the transaction that added it), and the partial unique
     index and `ck_photos_public_position_range` on `photos`, which name `kind`, re-created from
     the database's own definitions; `tests/core/test_enums.py` holds Python to the database. One
     live per person, as the selfie (`_check_room`); uploaded at the `photos` step or after
     (`_STEP_OF`, D-068); moderated by all four of D-101's checks, `no_face` among them, since she
     may choose to show it; private bucket only, no public copy unless she chooses; listed to its
     owner by `GET /me/photos` and read by `GET /photos/{id}` (today both see public and private
     only: `photos/repository.py`, D-096); `verify_selfie` compares the selfie with it alone
     (`approved_public_photos` and `public_photos_waiting` read it instead, and `no_photos` comes
     to mean "no face photo yet", its words with it); D-078's deletion takes it with an under-18
     refusal, with a test, as T-4.5 wrote one for the selfie.
  3. **Public photos need no face (D-392).** `moderation.verdict`'s `no_face` reads the new kind
     and never `public`; `test_no_face_only_for_public_photos` turns into its opposite. Hair over
     the face, a mask, a crop, a photo from behind, an emoji over the face: all pass. Nudity, a
     possible minor and text over the photo are refused as before.
  4. **Nobody needs a public photo (D-392), men included.** `photo` leaves `rules.missing` and
     `PROFILE_INCOMPLETE`'s `details.missing` (04-API); the photos step gains a way to be left
     without one (today only a public photo's `complete` moves the step on, `photos/service.py`;
     the way is this task's plan's: an endpoint of the step's own, or the face photo's `complete`);
     T-4.3's "the last public photo can't be removed past the step" goes (`DELETE /photos/{id}`).
     Completeness is unchanged (D-310 amended): zero photos is 50, the bottom of discovery's
     ranking (D-032), on purpose.
  5. **The badge and the card (D-393).** Each approved public photo whose moderation record says a
     face (`moderation.faces >= 1`, which T-4.4 already records) is compared with the kept selfie,
     when it is approved (a selfie already decided) or when the selfie is decided (photos already
     there), one comparison at a time (P-281), the result in that photo's `moderation` record,
     never a rejection. The badge is `is_verified` **and** at least one such photo matched; its
     icon a tick in `--accent`; its label and aria-label "Selfie matched" (D-262's rule on words
     unchanged, `claims.test.ts` as strict). T-6.2's `Card` carries the badge as this computes it,
     never raw `is_verified`, and a null main photo when there is none, which the web shows as a
     grey silhouette with the name. This task gives T-6.2 the rule and the query; the `Card`
     itself stays T-6.2's.
- [x] **Web:** the photos step gets a slot of its own for the face photo ("this is only for the
  check; nobody sees it") and the toggle that also shows it on the profile; the step's "At least
  one to be visible" and "Add at least one photo" go; the selfie step's lines that say "your
  photos" (`subWoman`, `subMan`, `comparing`, `matched`, `finish.needsMatch`, `finish.missing.photos`,
  `reasons.no_match`, `reasons.no_photos`) say the face photo instead; `/privacy`
  (`collect.selfie`, `where.faceMatch`, and a new line: a photo of her face is kept for the check
  and never shown unless she chooses, and why: so the photos others see need not show her face),
  `/terms`' `profile.body` and the landing's `safety.body` ("Selfies compared with profile
  photos") rewritten inside D-262's rule; `Avatar`'s badge a red tick; every new string under
  `claims.test.ts`.
- [x] **Seed:** a face-photo row (a placeholder, private) for every seeded user marked verified,
  and for the three women at the selfie step, who verify against it from then on; seeded public
  photos get a `moderation` record with `faces`, or carry none and show no badge, decided in the
  plan. A re-run adds nothing twice.
- [x] **E2E (T-4.9):** J2 uploads the portrait as her face photo and finishes with no public
  photo; J1 finishes with none; 06-TESTING's J1/J2 rows follow.
- [x] **Contracts, changed with the code and not before:** 03-SCHEMA (`photo_kind_t`, `photos`,
  the note on `users.is_verified`), 04-API (`/photos/upload-url`'s kinds, `/me/photos`,
  `/photos/{id}`, `DELETE`, `PROFILE_INCOMPLETE`, `Verification`'s description, the step's exit),
  02-ARCHITECTURE §8 (the `Card`'s badge, an EXISTS on `photos`), 06-TESTING #14 (the face photo
  joins what is never public unless chosen) and J1/J2, 08-DESIGN §4's Avatar row; `make types`
  (`PhotoKind` changes).
- [x] **Four points this task's plan decides, Claude's recommendation beside each, none decided
  today** (the founder, 7 October 2026). **Decided 8 October 2026 (D-400):** each as recommended,
  the step's exit `POST /me/photos/done`; the toggle's copy goes through moderation rather than
  approved at once, Claude's change for the founder to confirm (D-400).
  1. **The toggle's mechanism.** A separate `public` row made from the face photo's scored bytes,
     with a place of its own, so every reader of "public photo" (discovery, completeness, T-6.3,
     the badge's comparison) stays as it is, and turning it off is `user_deleted` on that row; or
     the face photo's own row given a place and a public copy, which touches every reader.
     Recommended: the separate row.
  2. **Whether a woman may leave the photos step without a face photo.** Recommended: no, by an
     allowlist like `MAY_FINISH_UNMATCHED` (men may), in place of today's "one public photo,
     pending or approved"; the server's rule, not the screen's.
  3. **The photo's name in copy.** "face photo" (the advisor's recommendation: no claim, just what
     it is) or "selfie-check photo"; never a word matching `/verif/i`.
  4. **Replacing the face photo after a match** (found filing): refused while a verification is
     approved, as a selfie's removal is refused today, so the match can't be left pointing at a
     photo that is gone; a change then goes through P-163's path. Recommended: refused.
- [x] **Tests, and every guard broken once,** as T-4.5 to T-4.9 did (`tests.break_guards`,
  `scripts/break-guards.mts`, each file restored by SHA-256, the log kept): `tests/modules/photos/`
  (the kind, its one-at-a-time rule, `no_face` on the face photo and never on a public one, the
  last public photo removable), `tests/modules/verification/` (the selfie against the face photo
  alone; a public photo's comparison on approval and on the selfie's decision; a non-match that
  doesn't reject), `tests/modules/onboarding/` (`done` with zero photos, for a man and a woman;
  completeness 50 at zero), `tests/seed/`, the enum and migration tests, and the web's
  `PhotosStep.test.tsx`, `SelfieStep.test.tsx`, `Avatar.test.tsx`, `claims.test.ts`,
  `e2e/signup.spec.ts`. A photo with no face approved as public and refused as a face photo,
  each at D-101's edge.
  **Done, 8 October 2026:** `tests.break_guards t412-`, 22 cases, 22 of 22 red, every file
  restored by SHA-256, the tree byte for byte as before; the web's
  `scripts/break-guards.mts`, T-4.12's 8 cases and the 7 whose anchors this task moved, 15 of 15
  red. Logs in `out/t-4.12/` (git-ignored). Two older cases left with their guards: `t45-04` (the
  selfie no longer reads a public copy) and T-4.8's `photo` requirement.
- [x] **Done when, on a per-run database (P-55):** a fresh woman finishes with zero public photos,
  her selfie matched against her face photo alone, `is_verified` true and **no badge**; she adds a
  public photo with a face that matches, and the badge appears; a public photo of hers with no
  face is approved; her face photo appears in no public response and in nobody else's (06-TESTING
  #14, extended); a man finishes with no photo and no selfie; `claims.test.ts` is green with every
  new string; `make lint test`, then CI, on the commit that lands.
  **Seen, 8 October 2026, each on a per-run database:** zero photos to `done` for a man and a
  matched woman at completeness 50 (`test_zero_photos_finishes_at_completeness_50`); the selfie
  against the face photo alone (`test_the_selfie_is_compared_with_the_face_photo_alone`); no badge
  with `is_verified` alone, the badge once a shown face matched
  (`test_the_query_needs_is_verified_and_a_shown_face_that_matched`,
  `test_shown_the_copy_is_compared_for_the_badge_once_approved`); a public photo with no face
  approved (`test_a_public_or_private_photo_needs_no_face`); the face photo in nobody else's
  response (`test_the_face_photo_is_its_owners_alone`); J1 and J2 through the browser, 14 of 14;
  `claims.test.ts` green. `make lint test` on the commit that lands, then CI, are /done's.
- [x] **The trade-off, weighed, and written down so nobody later thinks it was missed** (the
  founder, 7 October 2026): on a dating app a card with no face gets far fewer swipes. The woman
  this change is for may arrive, show nothing, receive nothing, and conclude the app doesn't work.
  The founder weighed that and chose to let her in rather than stop her at the door.
- [x] **Commit:** `feat(photos): face photo for the selfie check; public photos need no face; nobody needs one [T-4.12]`

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
- [x] **Needs:** T-5.1
- [x] Settles P-07: tick it at `/done`.
- [x] **Committed rows, never deleted** (the ledger refuses DELETE and TRUNCATE):
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
- [x] **A dedicated 50-connection engine,** asserting 50 distinct backends. If Postgres runs out of
  connections, fail loudly; never skip.
- [x] **Prove the overlap by what the lock decides** (`f543b0d`): all 50 are inside open transactions
  before any takes the lock (asserted). After the read, each waits up to 20 ms and records whether
  it waited alone; with the lock, all 50 do.
- [x] **Debits:** credit a man 10, then fire 50 concurrent debits of 5. Exactly 2 succeed, 48 get
  `INSUFFICIENT_CREDITS`, the balance is 0, there are 3 ledger rows (the credit and 2 debits), and
  `sum(delta) == balance`.
- [x] **Keys:**
  - the same key 50× concurrently, for debits and for credits: exactly 1 entry each;
  - one payment credited under two different keys: the second is refused by D-077's index;
  - two users with the same client key: both apply.
- [x] **Breaking runs:** `FOR UPDATE`, the repeat check, the unique key and the per-event index, one
  at a time, each red, on the task's own database as in T-5.1.
  **Done, 4 October 2026,** with the script committed this time (`api/tests/break_guards.py`,
  `uv run python -m tests.break_guards t54- --repeat 3`): `FOR UPDATE` removed, the repeat check
  moved before the lock, the repeat check removed, the unique key removed, the per-event index
  made non-unique, and the harness's forced overlap removed, **each red in 3 of 3**, every file
  restored by SHA-256, none differing after. T-5.1's cases re-run from the same script, **all 35
  red in 1 of 1**: T-5.1's report and commit said 34, a miscount; there were always 35. The
  unique-key test makes the repeat check blind on purpose, the only way to see the key go red:
  it proves the key holds as the last line of defence, **not** that the production path is right
  (there the lock and the repeat check stand in front of it, proved by the other tests). Its
  patch is scoped to that test and checked restored by identity before any assertion runs. The
  whole API suite in 8 shuffled orders: T-5.4's tests passed in all 8; seeds 3, 4 and 7 each
  failed once, on T-4.2's photo test (P-84), which fails race-first with no T-5.4 code involved.
- [x] This test must never be skipped or marked flaky. If it fails, stop everything.
- [x] **Commit:** `test(wallet): concurrency and idempotency [T-5.4]`

### T-5.2 · Prices
**Not held** (the founder, 4 October 2026). It was held earlier that day until the wallet had a
screen, behind T-4.4 and T-4.6; that order was the sprint's sequence, not a dependency, since
prices don't depend on the web photos step, and the hold is lifted.
- [x] **Needs:** T-5.1, and the founder's answer to each question below. Claude found all ten on 4
  October 2026 while writing D-097 to D-100; the founder answered them the same day (D-097's note,
  D-230, D-231, D-250), and moved the parts that touch no file of this task's to the tasks they
  touch. Answered ones keep their numbers, so references to them hold.
  1. **Answered: an expired Thread stays readable** (D-097, which records it). Asked as: can an
     expired Thread still be read, which `/terms` answers today? "Unavailable" means he can't send,
     not that he can't read: the history he paid for stays visible to both of them. **Why:** he
     bought that conversation, and hiding it would be both harsher than intended and a change to a
     live page for no gain. So `/terms` ("kept, read-only") stands as published, and so do D-003,
     06-TESTING's J7 and the prototype. What it settles:
     - **T-7.11's expired panel** must show her no prompt, and no sign that money stands between
       her message and his reply: readable, and otherwise silent on her side.
     - **08-DESIGN §6's example copy, "This thread disappears in 4h", is wrong twice:** the word,
       since nothing disappears, and the number, since a Thread is an hour. Flagged, not
       rewritten: the 1-hour task D-097 names rewrites it.
     - **An expired Thread refuses his sends and accepts hers** (D-097). This follows from D-097's
       step 4 rather than from the answer: Claude wrote it down here, and the advisor confirmed it.
       It is beside each place that raises or tests `THREAD_EXPIRED`: 04-API, T-7.1, T-7.3 and
       06-TESTING's case 12.
     - The first two are noted beside T-7.11 and 08-DESIGN §6 too, where that work happens.
  2. **Answered, and it changes `/refunds`, a published page: no product refunds** (D-230).
     Nothing is returned on a ban or on a declined album request, so T-9.3 is dropped and T-8.4's
     decline returns nothing; `refund_album_declined` and `refund_banned_partner` stay unused, never
     repurposed. A chargeback reversal (T-8.2) and a duplicate charge (T-8.3) aren't product refunds
     and stay. `/refunds` is wrong as published: **P-130** rewrites it, before REL-1 and T-8.1.
     And the album request is viewing private pictures, at 1 Vela (D-231).
  3. **Answered: D-004's other prices** (D-231). The direct message is the private message (item
     4). A voice-note unlock (5), a Super Like (5) and a "liked you" reveal (20) stay at D-004's
     prices **by default, not by decision**: the founder had no preference. **Answered: a Super
     Like is not swiping** (D-250). Free swiping is an ordinary left or right swipe; a Super Like is
     its own action and keeps D-004's 5, which survived by default and was never decided.
     **The reveal is 1 Vela from 8 October 2026 (the founder),** a value change (D-004's note);
     P-370 moves the row.
  4. **Answered: a private message is sent from a profile directly, with no swipe and no match**
     (D-231): 8 Velas for the first, 2 for each after, and it never expires. It is D-004's direct
     message (`dm_open`, the `dm` origin), whose 5 is dead. How it is kept beside 03-SCHEMA's rule
     that an active Thread always expires is T-7.1's to propose (noted there).
  5. **Answered: four gifts, at 5, 10, 15 and 20 Velas** (D-231). The old six and the cap of three
     free a day are gone. Fifteen sends a week are free, as sends, not a grant of Velas; the
     sixteenth costs its price.
  6. **Answered: the 20% first-purchase bonus stays,** on D-099's packs (D-231). On a first
     purchase it makes opening a Thread about ₹208 at the entry pack and ₹93 at the largest.
  7. **Answered: the prototype's packs are stale** (D-231; 08-DESIGN §5 records the departure).
     **Answered: `entry-25` is retired, not repriced** (D-250). T-10.4's test, ₹1,500 against ₹999
     for 25 Velas, matched no pack once D-099's replaced D-005's. ₹999 for 25 is ₹40 a Vela and the
     new entry pack is ₹50 a Vela, so keeping it would have left the cheapest pack sitting below the
     ladder. T-10.4 can propose a fresh test against the new packs when there are users to test on.
  8. **Answered: "Most popular" stays on the ₹4,500 pack, chosen knowingly** (D-231), with the
     arithmetic that makes it the dominated pack in front of us. **Moved to T-8.7, which owns the
     screen** (the founder, 4 October 2026): at launch nobody has bought anything, so the words
     aren't true on day one, a separate problem from the value question and still open. No file of
     this task's holds the tag: `credit_packs` has no column for it.
  9. **Answered: 09-RESEARCH's "about ₹300" was stale,** not a decision, and now says ₹250.
  10. **Four things about how a Thread lives** (D-097), none answered by its five steps. **(b)
      answered (D-250); (a) and (d) moved** to P-150, the 1-hour task D-097 names, with a pointer
      at T-7.6 (the founder, 4 October 2026): they touch no file of this task's. **(c) answered,
      in two parts:** D-250, the founder's, and D-253, the advisor's rule, Open until the
      founder's word.
      - (a) **Moved, open: does his own message restart the hour?** Step 2 says hers does and is
        silent on his. If his did, he could keep a Thread open alone, free, by writing every 59
        minutes, and would never re-open one.
      - (b) **Answered: when she sends the first message, he pays to answer,** and that is the
        2-Vela re-open, `thread_reopen`: a priced action with a ledger reason of its own.
      - (c) **Answered: can he Extend a Thread that has already expired, and if so do the 10
        Velas include the 2 to re-open it?** Yes, and yes, by the advisor's rule (D-253, Open
        until the founder's word): Extend is 10 at any time, and
        from expired the 10 both re-opens and extends, never 2 then 10. **And** (D-250) Extend can
        be bought more than once for one Thread, 10 Velas for another 24 hours each time, so its
        reason repeats for one ref. Claude's summary to the founder had put (c) as that second
        question, so the first answer didn't reach (c)'s two as written; Claude moved them to
        P-150 on 4 October 2026, and they were answered instead on 5 October, never moved.
      - (d) **Moved, open: when Extend's 24 hours end, does the hour start then, or run from her
        last message,** which could expire the Thread the moment Extend ends?
- **Estimate, 4 October 2026: about 5½ hours of working time** (4½ to 7), Claude's, made before
  seeing any other. Slowest, it said: making the new ledger reasons reversible. Postgres can add a
  value to `ledger_reason_t` and never remove one, so going down means rebuilding the type under
  the ledger's three reason checks, its per-event index and its append-only triggers, and refusing
  once any row uses a new reason, since no row can be deleted. **It stands over the advisor's 2½ to
  3½ hours** (Claude, in a separate chat), which was wrong because it didn't account for the
  enum's one-way nature (the founder).
  **Measured: about 1 hour of working time to the code commit, and about 1½ hours to landing,** from
  the answers arriving (about 22:57, 4 October), less about 12 minutes spent waiting for the gifts
  to be confirmed: the commit's author time is 00:07, and `main`'s CI run for it started at 00:42
  (run 37227352463). The half hour between is three rebase-and-gate cycles, each because `main`
  moved. **Both estimates were high,** and both included the gate and the rebases: Claude's 5½ hours
  by about three and a half times, the advisor's 2½ to 3½ by about two. The slowest part was the one
  named: the enum held the task's one real bug (D-251's note), but it cost about twenty minutes, not
  hours. Claude's estimate priced the work at a person's pace and the gate cycles one after another,
  when tests and CI ran beside the work. So the line above is half right: the advisor's estimate did
  leave out the enum, and it was still the nearer number (Claude, correcting its own estimate, 5
  October 2026). **Corrected the same day:** this record first said "about 1¼ hours" to the commit,
  rounded toward the estimate; the commit's author time gives 58 minutes.
- [x] **The prices are D-097 to D-099's and D-231's** (the founder, 4 October 2026). Velas, for men;
  0 for a woman, for every action:
  - open a Thread 5 · re-open an expired Thread 2, every time · Extend, 24 hours, 10 · first
    private message 8 · each private message after it 2 · view private pictures 1 · unlock a voice
    note 5 · Super Like 5 · reveal one "liked you" 20 (these three by default, D-231; the reveal
    is 1 from 8 October 2026, the founder, and P-370 moves the row) · a gift 5,
    10, 15 or 20, and fifteen free sends a week · swiping free · tying the knot, and a Knot's
    messages, free. Private messages never expire.
  - packs: ₹1,500 → 30 · ₹4,500 → 100 · ₹6,000 → 250 · ₹10,000 → 450, with the 20% first-purchase
    bonus. The ₹4,500 pack is dominated on purpose (D-099): don't "fix" it.
  - re-open (2) and Extend (10) change together or not at all (D-098).
- [x] **Written by data migrations of this task's own,** one change each (rule 11), never by editing
  T-1.14's: `thread_reopen` from 3 to 2, `dm_open` from 5 to 8, `album_request` from 5 to 1; the
  `gifts` rows become D-231's four; `gift_free_daily_limit` gives way to fifteen free sends a week;
  **the packs become D-099's four and `entry-25` is retired** (D-250: this task replaces the packs,
  as 03-SCHEMA said). 03-SCHEMA's seed lines and `tests/test_reference_data.py` change with them.
  The new priced actions, Extend (`thread_extend`) and each private message after the first
  (`dm_message`), are debit reasons of their own (D-251): an addition to `ledger_reason_t` with
  D-077's direction and `ref_type`, and T-5.1's test that the debit reasons are exactly the priced
  actions plus `gift` grows to match. **Extend can be bought more than once for one Thread**
  (D-250), so it repeats for one ref, as `thread_reopen` does, and D-077's per-event index leaves
  it out.
- [x] **Not this task's:** the 1-hour Thread (D-097): `thread_hours` stays 24 until its own task.
  Women's limits (D-098: 30 men and 30 private messages a day) are rate limits for the tasks that
  send messages, not prices. No charging path for women is built, enabled or disabled (D-098).
  Refunds aren't this task's either: there are none for a product (D-230), and a chargeback
  reversal and a duplicate charge stay with T-8.2 and T-8.3.
- [x] `pricing.service.price_for(user, action)`:
  - women 0; men the `action_prices` value;
  - no gender raises; an inactive row gives `NOT_ALLOWED`; a missing row is a 500; never 0 by
    default;
  - read fresh inside the debit's transaction, with no cache. P-47 puts any cache on the app, and
    P-50 adds one only where something is measured slow.
- [x] `pricing.service.charge(...)` reads the price and debits only when it is above 0, since a
  debit of 0 raises. A test allows `wallet.service.debit` to be called only from `charge` and from
  gift sending (T-8.9, priced from `gifts`), so no literal price can reach it.
- [x] `GET /prices` (public): list prices for active actions only. Gifts aren't in it (`GET /gifts`).
- **Broken once each, 4 October 2026,** with the script committed (`uv run python -m
  tests.break_guards t52- t51-L3 t51-L-direction t54-per-event-index`): T-5.2's 22 cases and the
  five of T-5.1's and T-5.4's that its migrations took over, **each red in 1 of 1**, every file
  restored and none differing by SHA-256 after, no bytecode in the tree. Read from each red:
  - **The gender check made a blacklist** (`is None`) went red on the gender nobody has named
    only; the no-gender case stayed green, as it must. That case is what tells the allowlist apart.
  - **The downgrade's refusal removed** went red, but the database still refuses, by its cast of
    `thread_extend` into the older type: the guard adds the reason, not the only stop.
  - **The enum's downgrade made a no-op** went red in 28: the next upgrade then refuses ("already
    has"), stranding the run's database below head, which is what such a migration does.
  - **The debit's allowlist:** a stray `wallet_service.debit` in pricing's own module went red;
    the scan made blind to attributes went red on the attribute-shaped callers and on the live
    allowlist (`charge` vanished), the name-shaped callers staying green as they should; and the
    allowlist made per-file went red.
  - **T-5.1's direction, ref-type and per-event cases now weaken a1d7de534ef7,** which re-creates
    those three: weakened in 97ddae55f597 they would never reach the head. Its `ref_required` case
    still weakens 97ddae55f597 and still went red, carried across by the enum's rebuild.
- [x] **Commit:** `feat(pricing): server-side prices [T-5.2]`

### T-5.3 · Wallet endpoints
- [x] **Needs:** T-5.1
- [x] `GET /wallet` → `{balance}`. `GET /wallet/ledger?cursor=&limit=` → `Page<LedgerEntry>`: `id`,
  `delta`, `balance_after`, `reason`, `created_at`; never refs or the key. The web turns `reason`
  into words from `en.ts` (D-033, P-26); the API doesn't.
- [x] Newest first by `(created_at, id)`. Entries from one transaction share `created_at`, so their
  order is stable but arbitrary. The opaque cursor and the page type live in `core`, since this is
  the first paginated endpoint.
- [x] Women get a balance of 0 and an empty list, not a refusal. No rate limit on these reads.
- [x] **Commit:** `feat(wallet): balance and history [T-5.3]`

### T-5.6 · App shell
- [x] **Needs:** T-3.10
- [x] The `(app)` layout's header and bottom nav: Discover, Chats, Wallet and You, each a placeholder
  route until its task. No Vibe (after beta, D-010). The wordmark comes from `APP_NAME`, never the
  prototype's "Knot" (rule 17).
- [x] **Who owns the frame** (decided planning T-3.10 to T-3.13; T-3.10 and T-3.11 carry the same
  line). T-3.10's `(app)` layout restores the session, gates on `done` and shows the PIN lock. This
  task adds the header and nav inside that layout, in `src/components/shell/`, never replacing what
  T-3.10 put there, and never on `(auth)` routes. Onboarding has its own frame, T-3.11's
  `StepFrame`, with no header or nav, as in the prototype.
- [x] **Provisional (08-DESIGN):** no visual design exists for the app's screens, and the prototype
  was wrong four times in Sprint 5's plan alone: the refund button, gift's direction, the price list
  and "credits" for Velas. Build only what this task names; anything more waits on P-57.
- [x] **The shell's look lives in two places only:** colour, type scale and spacing as tokens in
  `src/styles/tokens.css`, and the header's and nav's shape in one layout component in
  `src/components/shell/`, never spread through the components inside. **Why:** this shell is
  what every later screen sits inside, built before any visual design exists (P-57). When T-6.5's
  design pass comes, it should change values, not structure. Reopening the shell's structure after
  five screens sit on it would be the most expensive rework in the sprint; this is the cheapest
  insurance against it. At the direction of the advisor directing Sprint 5, 3 October 2026.
- [x] **Commit:** `feat(web): app shell [T-5.6]`

### T-5.5 · Web wallet
- [x] **Needs:** T-5.2, T-5.3, T-3.10, T-5.6
- [x] **The balance pill** (men), or "Free access" (women), sits in T-5.6's header.
- [x] **The shell's look guard is still a blacklist** (P-83, which waits for T-6.5): whatever this
  task adds to `AppShell.tsx` keeps its look values in `tokens.css` by its own discipline, never
  by trusting `look.test.ts` to catch one. At the direction of the advisor directing T-5.6 (Claude,
  in a separate chat), relayed by the founder, 4 October 2026.
- [x] **The wallet screen** has a black balance card, a price list from `/prices` and the ledger
  history (infinite scroll). It follows the prototype with these departures, written into 08-DESIGN:
  - no "Request a refund on unspent credits" and no "Unspent credits refundable within 7 days" (the
    cash-out D-050 removed; D-076), just a quiet link to `/refunds`;
  - the price list is `/prices`' nine actions (D-098, D-231) plus "Tie the knot · Free" and
    "Messaging in a knot · Free". Not Wink, Boost, calls or "Gifts 20–500" (D-231's gifts are 5,
    10, 15 and 20);
  - "credits" becomes Velas (D-049), and the women's screen drops "calls" (after beta).
- [x] The pill reads one wallet query, refreshed after anything that spends or credits and when the
  window regains focus. No polling; the socket arrives with T-7.12.
- [x] Global handler: any `INSUFFICIENT_CREDITS` from a mutation (the query client's mutation error
  hook; queries never) opens the store sheet, a "coming soon" placeholder until T-8.7, with its open
  state in Zustand.
- [x] Words for all 17 ledger reasons in `en.ts`, in a map typed from the generated enum, so a new
  reason without words fails `tsc`.
- [x] **Commit:** `feat(web): wallet screen and balance pill [T-5.5]`

---

# Sprint 6 — Discovery (weeks 9–10)

> Location lives in Sprint 4 as T-4.10, because onboarding needs it first. Discovery starts at T-6.2.

### T-6.2 · Discovery query
- [x] **Needs:** T-4.10, T-4.8; **P-75**: public photo places kept 0 onwards by the server, or
  "main" defined as the lowest place, before a `Card` carries a main photo (found building T-4.6)
  **P-161**: a public photo added after a verification compared with the selfie, or the badge
  cleared, before a `Card` carries `is_verified` to anyone (found building T-4.5): **resolved in
  shape by D-393 and built by T-4.12**, which is on this line for it
  **T-4.12**: the face photo, the badge's rule and the card with no photo (D-391 to D-393), before
  a `Card` carries a badge or a main photo
  **P-120**: distances snapped so they can't be trilaterated, before a `Card` carries
  `distance_km` to anyone (found building T-4.10)
  **P-210**: `profiles.completeness` kept current after onboarding finishes, before the ranking
  reads it (found building T-4.8)
- [x] Repository implements the query in `02-ARCHITECTURE.md §8` with feeds: `foryou` (ranked), `new` (joined ≤ 7 days first), `online` (active ≤ 5 min). Filters: `intent_ids` (any overlap, D-041), verified.
- [x] Excludes: self, swiped, blocked either way, hidden, not `done`, status ≠ active, fraud band `freeze`; `shadow` band users only shown to others in `shadow`.
- [x] Response `Card`: id, first_name, age (null if hide_age), username, city, hometown, distance_km (null if hide_distance, else ≥ 1), intent_ids, bio line (first 90 chars of about), main photo URL, is_verified, is_online, is_new.
  **From 7 October 2026 (D-392, D-393, T-4.12):** the main photo URL is null when there is no
  approved public photo, and the web shows a grey silhouette with the name; the badge field is
  D-393's rule (a selfie matched the face photo **and** at least one approved public photo's face
  matched the selfie), computed by the query, never raw `is_verified`, and its name is this task's
  (`is_verified` stays in `Me`, for the owner). Whether the ranking's `is_verified` term stays is
  P-290.
- [x] Cursor = (score, user_id). **Built as `(as_of, score, user_id)` (D-491):** the score at the
  scroll's first instant, so time passing between pages can't repeat or skip a card.
- [x] Performance test: seed 50k profiles, assert p95 < 80 ms with `EXPLAIN ANALYZE` showing the GIST index.
  **Split by the founder (8 October 2026, Q7):** `make test` holds the deterministic half,
  `tests/modules/discovery/test_plan.py` (a 6,000-profile crowd spread across India, EXPLAIN shows
  `ix_profiles_location`); the timing is `api/bench/discovery`, run by hand. **Measured 8 October
  2026, 50,000 profiles, 10 interleaved rounds of 100 timed requests each (the feed and its cards,
  first pages and a page 200 deep), on the founder's Mac against the local Postgres 16:**
  spread across India, **p95 24.2 to 34.8 ms** (p50 20.6 to 21.9): the target met. The launch
  shape, all 50,000 inside Phagwara's 25 km, **p95 197.1 to 209.0 ms** (p50 165.8 to 188.9):
  accepted above 80 ms, far beyond beta scale (D-495), its fix P-391. **Caveat: not an idle
  machine.** Other sessions' tests ran through the whole run (5 of their test processes in every
  one of 45 samples, load average 2.79 mean), so these may read high. Before it: without JIT off and
  with the viewer's point behind a subquery, launch 191.0 to 246.1 ms; a nearest-2,000 window
  (D-495, removed) 173.0 to 274.7 ms over 5 rounds. Staging's own numbers are P-390's.
- [x] **Commit:** `feat(discovery): ranked nearby feed [T-6.2]`

### T-6.3 · Public profile
- [x] **Needs:** T-6.2
- [x] `GET /users/{id}` → `PublicProfile`: card fields + full about, all approved public photos, interests, kudos (if `show_kudos`), album photo count, existing thread/knot state with me. Blocked either way → 404 `NOT_FOUND`. Records a profile view (for later "viewed you").
  **Who may open one is D-493:** `visible_to` without seeking or the radius, a hidden profile only
  to someone it shares a match or Thread with, your own always, every refusal the same
  `NOT_FOUND`. `tests/modules/discovery/test_public_profile.py` holds it; breaking runs `t63-01`
  to `t63-08` each red.
- [x] **Commit:** `feat(profiles): public profile [T-6.3]`

### T-6.4 · Swipes and matching
- [x] **Needs:** T-6.3, T-5.1
- [x] `POST /swipes {target_id, dir}`: men's daily cap from `app_config` (IST day, Redis counter) → `SWIPE_LIMIT_REACHED`; `super` debits price (women free) via wallet; duplicate swipe → `ALREADY_EXISTS`.
- [x] If `like`/`super` and the target already liked me → create `matches` row (ordered pair), publish `match.created` to both, notification.
  **Built as D-492:** only someone the feed could show you, the radius aside; a man's like and
  pass count, a Super Like doesn't; the place given back when nothing is written; the pair locked,
  so two likes at once make one match (`test_race.py` forces it). Breaking runs `t64-01` to
  `t64-14` each red, `t64-06` (the lock) red in 3 of 3. P-47's cache came with it.
- [x] **Commit:** `feat(swipes): swipe, daily cap, super like, match [T-6.4]`


### T-6.5 · Web discover deck
- [x] **Needs:** T-6.2, T-6.4, and P-57, answered 7 October 2026 (08-DESIGN §8): the app's visual design, which this task builds from, never the prototype; and P-82 and P-83: its design pass changes the shell's values, so first the shell is checked where a browser draws it, and its look guard fails anything not on an allowed list; and P-220: its match sheet is the app's first sheet after T-5.5's store sheet, so a sheet left open behind the PIN lock stops being reachable first; and **P-56, built by T-6.5 as its first commit** (the founder, 8 October 2026): the API refuses a charge whose price changed after it was shown, on every paid endpoint on `main`, and then this task's web sends the price it showed
- [x] `useDiscover(feed, filters)` infinite query; keep 3 cards rendered; prefetch next page at 5 left.
  **Built:** the filters are read from the URL (`intent_ids`, `verified`), where T-6.9's sheet will
  write them. The feed is never asked again on focus: a refetch would re-rank the scroll mid-swipe.
  **The feed's page carries `swipes_left`** (a man's number, null for a woman), so the counter shows
  before his first swipe: the founder's answer, 8 October 2026, instead of a new endpoint.
- [x] Card with `@use-gesture/react` + `@react-spring/web`: drag with rotation, LIKE/PASS overlays by drag distance, fling threshold 100 px or velocity, up = super. Tap = open profile. Keyboard ← → ↑ on desktop.
- [x] Optimistic swipe: advance immediately, rollback + toast on error.
  **Built:** `ALREADY_EXISTS` and `NOT_FOUND` leave the card gone (it is gone anyway);
  `INSUFFICIENT_CREDITS` puts it back and opens the store sheet; `PRICE_CHANGED` puts it back, says
  the new price and asks `/prices` again; `SWIPE_LIMIT_REACHED` puts it back and holds the counter
  at 0. **Tap opens `/people/{id}`**, the one route a profile has, agreed with T-6.8's session
  (a placeholder page until T-6.8), and a nonce route (`NONCE_ROUTES`).
- [x] Action row: pass, super (price tag for men), like. Swipes-left counter for men.
  **The price shown is the price sent (P-56, D-600):** Super's number and the match sheet's are
  read from `/prices` and sent as `shown_price`; a woman sees no price and sends 0 (D-002).
- [x] Match celebration sheet → "Open thread · 5 Velas" / "Keep swiping".
- [x] Empty states: no one nearby / filters too narrow (clear button).
  **Broken once each, 8 October 2026:** web `node scripts/break-guards.mts t65-` (17 cases) and
  API `uv run python -m tests.break_guards t65-` (2 cases), every one red in 1 of 1, every file
  restored. **One stayed green at first and was a finding:** `t65-10` (the next page asked for at
  6 left) passed, because the test built its page from the `PREFETCH_AT` constant and moved with
  it; the test now says 5 itself, and the case went red.
- [ ] 60 fps on the test phone (check Chrome performance panel).
  **Open for the founder's reading on the test phone (P-500).** The desktop stand-in, measured 8
  October 2026 (`web/bench/deck-fps.spec.ts`, run by hand: a production build, a 412 × 915
  screen at 2.625×, DevTools' CPU throttling, ten runs at each rate, interleaved; each run a
  200 px drag and the fly-off, its swipe request and the card's movement required):
  **4×:** the drag never dropped a frame (longest 16.8 ms in all ten runs); the flight
  **57.7 to 60 fps**; 5 of 1,089 frames over 25 ms. **6×:** the flight **55.4 to 57.7 fps**; the
  drag's longest frame 16.7 to 33.3 ms; 14 of 1,080 frames over 25 ms. The dip is one long frame
  as the flight starts, when the next card mounts. **Caveat: not an idle machine** (load average
  4.5 to 5.8, other sessions' tests running), and not a phone's GPU. A first draft of the bench
  counted every frame the page painted, which an idle page also paints at 60; it was discarded.
- [x] **Re-examine the CSP's `'unsafe-inline'` here (D-059's trigger, amended 3 October 2026):** the first screen planned to render another user's text, their names and about. If any screen gets there sooner, the re-examination moves to it. T-3.11 kept the allowance for the user's own text; here the threat is someone else's input on your page. Nonces scoped to the signed-in routes by Next's proxy leave the marketing pages static (the amendment).
  **Moved to T-6.6 and done there (D-541, 8 October 2026):** its search rows got there first. The
  deck's routes are already nonce routes (`/discover` and beneath); a new place this task adds
  outside them joins `NONCE_ROUTES` in `web/src/lib/security-headers.ts`.
- [x] **The feed row's Search button links to `/discover/search`** (T-6.6) and a Liked you entry
  to `/discover/likes` (T-6.7): P-443.
  **Search is built; Liked you's entry moved to T-6.7, on its line:** its screen and count didn't
  exist yet, and a link to a 404 is worse than none.
- [x] **Commit:** `feat(web): discover deck [T-6.5]`

### T-6.6 · Search and @username
- [x] **Needs:** T-6.3
- [x] `GET /search?q=`: `@` prefix → exact-then-prefix username match (ignores distance/filters, still respects blocks/hidden); otherwise trigram on first_name/username + city, intent and interest matches within radius. `GET /users/by-username/{u}`.
- [x] **Search and `/users/by-username/{u}` find `active` accounts only** (T-9.6, D-500): a
  deleted or paused one is `NOT_FOUND`. An erased account's username is free for anyone to take
  (D-505).
- [x] Web search bar with debounce; @-mode list results.
  **Built as D-540:** `@` and a username's start across India and past seeking, the exact one
  first, never a hidden profile; text within the radius, mutual, by name, username, city, intent
  or interest; swiped people included; a `SearchResult` per row; 60 a minute. The screen is
  `/discover/search`, its field on a chrome bar under the header; T-6.5's feed row links to it
  (P-443). Breaking runs `t66-01` to `t66-11` (API) and `t66-search-*` (web) each red.
- [x] **The CSP's re-examination came here (D-059's trigger; D-541):** the search rows are the
  first screen with another person's text. The sign-in and app routes carry a nonce per response
  and `'strict-dynamic'`, never `'unsafe-inline'`, and render per request; the marketing pages
  stay static. `web/e2e/csp.spec.ts` proves it by effect; breaking runs `t66-csp-*` each red.
- [x] **Commit:** `feat(search): search and username lookup [T-6.6]`

### T-6.7 · Liked you
- [x] **Needs:** T-6.4, T-5.1 (P-370, the `liked_you_reveal` row at 1, not 20, came off this line
  when it landed, 8 October 2026)
- [x] `GET /likes`: people who liked/super-liked me and whom I haven't swiped; for men, unrevealed entries return only a blurred thumbnail URL (server-generated blur, not CSS) and no name. `POST /likes/{id}/reveal` debits the `liked_you_reveal` row's price, through `pricing.service`, never a literal (1 Vela from 8 October 2026, the founder; this line said "debits 20" until then), and records `liked_you_reveals`.
  **Built as D-542:** a man's unrevealed like carries an opaque `handle`, never the liker's id
  (which would open their profile free), and the reveal is `POST /likes/{handle}/reveal`; the
  reveal's row is written first and only the request that wrote it pays, so two at once pay once
  (`test_race.py` forces it). `GET /likes/count` for the badge. Listed: likes waiting on your swipe
  from someone you could swipe back. A woman sees everyone, free.
- [x] **The blur is the server's (D-543):** 24 pixels, under a fresh key in the public bucket
  (`photos.blur_key`), made by the `blur_photo` job on approval, or when `/likes` first needs one
  for a photo approved before; deleted with the photo and at the erasure. YuNet finds the face in
  each NASA portrait and none in its blur. Breaking runs `t67-01` to `t67-13` (API, but `t67-04`)
  and `t67-likes-*` (web) each red. `t67-04`, the reveal charged whether its row was written or
  not, stayed green: the wallet's key for the debit (D-077) holds the charge to once by itself, so
  the case was dropped, never weakened to pass (D-542).
- [x] Web "Liked you" tab: grid, count badge, reveal flow.
  **Built as** `/discover/likes`, a two-column grid, the count in its chrome header; the price is
  `/prices`' and a 402 opens the store sheet. T-6.5's deck links to it (P-443).
- [x] **The price shown (P-56, D-600):** `POST /likes/{id}/reveal` takes `shown_price` and passes it to `pricing.service.charge(..., shown=)`, which compares it, never charges it (the check came with T-6.5's first commit, before this task was on main). Test `PRICE_CHANGED` with nothing charged or written, and its web sends the price it displayed, from `/prices`.
  **Built** with the opaque handle (D-542): `POST /likes/{handle}/reveal` takes `{shown_price}`;
  shown 0, stale or absent is `PRICE_CHANGED` with the reveal unwritten and nothing charged. The
  web sends the price it showed, hers 0, and says the new one. Breaking runs `t67-14` and
  `t67-likes-04` each red.
- [x] **Liked you's entry on the deck (P-443):** T-6.5's feed row holds Search; this task adds
  Liked you, with its count from `GET /likes/count`, in `web/src/components/discover/FeedRow.tsx`,
  linking to `/discover/likes`. A revealed tile links to the profile at `/people/{id}` (T-6.8).
  **Built:** a heart in `FeedRow.tsx` beside Search, its count a badge when anyone is waiting;
  a revealed tile links to `/people/{id}`.
- [x] **Commit:** `feat(discovery): liked you with paid reveal [T-6.7]`

### T-6.8 · Profile pages
- [x] **Needs:** T-6.3
- [x] In-app profile screen from the prototype (gallery, chips, kudos, message button, album section, ⋯ menu).
  **Built as D-545,** at `/people/[id]`, the one route a profile has (agreed with T-6.5's session;
  the plan's `/u/[username]` dropped): 08-DESIGN §8's screen, from `GET /users/{id}`. Like is
  there; "Open thread" (P-440), "Ask to view" (P-441) and Report and Block (P-442) wait for their
  tasks, and the ⋯ menu shares the `/@username` link. Search's rows link to it.
- [x] Public shareable page `veloraapp.co.in/@username` (SSR): logged-out visitors see first name, age, city, main photo, and "Join Velora to message"; logged-in users are redirected to the in-app profile.
  **Built as D-544:** only when its owner turned `public_link` on, a sixth privacy switch, false
  for everyone (the founder's addition, 8 October 2026); `GET /public-profiles/{username}`, public,
  60 a minute per address. Never indexed; a nonce route (D-541); someone signed in goes to
  `/people/[id]` by `GET /users/by-username`. `test_a_fresh_account_is_not_found_until_she_turns_the_link_on`
  holds the founder's rule.
- [x] `/@username` is D-001's link, and the `@` keeps usernames out of the routes' namespace: no route segment may begin with `@` (D-068). Next.js reads an `@folder` as a parallel-route slot, so serve `/@username` through a rewrite to an internal route.
  **Built as** next.config's rewrite to `/share/[username]`, a username only after the `@`
  (`USERNAME_IN_PATH`); `src/app/routes.test.ts` holds that no segment begins with `@`, and
  `web/e2e/share.spec.ts` the page in a browser. Breaking runs `t68-01` to `t68-06` (API) and
  `t68-*` (web) each red.
- [x] **Commit:** `feat(web): profile screens and share page [T-6.8]`

### T-6.9 · Filters
- [x] **Needs:** T-6.5
- [x] Filter sheet: intent multi-select, verified only, online now; active count badge; stored in URL search params.
  **The "verified only" chip's words follow D-262** (T-4.5), and its meaning D-393 (T-4.12, 7
  October 2026): it filters on the badge, a selfie matched to the face photo and a shown face
  that matched the selfie, never on `is_verified` alone, so it says that ("Selfie matched", or the
  founder's choice), never "Verified only", which the prototype says and
  `web/src/i18n/claims.test.ts` refuses.
  **Built as D-660 (the founder, 8 October 2026):** "Online now" is a filter, `online=true` on
  `GET /discover`, in any feed, not the Online feed's pill; all three filters are free for
  everyone. The URL (`intent_ids`, `verified`, `online`) is read and written only by
  `web/src/components/discover/filterParams.ts`, so the sheet's "Show people" and the empty deck's
  "Clear filters" write the same way. The sheet holds a draft until "Show people"; the count is
  each intent plus each toggle, on the Filters button and in the sheet's header. **Broken once
  each, 8 October 2026:** web `node scripts/break-guards.mts t69-` (11 cases) and API
  `uv run python -m tests.break_guards t69-` (2 cases), every one red in 1 of 1, every file
  restored; T-6.2's `t62-20` re-anchored on the new line and red again.
- [x] **Commit:** `feat(web): discovery filters [T-6.9]`

---

# Sprint 7 — Threads, knots, chat (weeks 11–12)

### T-7.1 · Open a thread
- [x] **Needs:** T-6.4, T-5.5-ready wallet (T-5.1)
- [x] `POST /threads` from `{match_id}` (origin `match`) or `{user_id, first_message}` (origin `dm`, first message required, 1–500 chars).
- [x] Rules: not blocked; both onboarded; if a thread already exists for the pair → `active`/`knotted` returns it (no charge), `expired` → `THREAD_EXPIRED` (client offers re-open). That refusal is his alone: an expired Thread accepts her sends (D-097).
- [x] In one transaction: debit (men only, `thread_open` or `dm_open`), insert thread (`expires_at = now + thread_hours`), link match, insert first message if dm. Notify the other person.
- [x] **The `dm` origin is a private message (D-231):** sent from a profile with no swipe and no match, 8 Velas for the first and 2 for each after, and it never expires. This task proposes how that lives beside 03-SCHEMA's rule that an active Thread always expires, and where each later message's 2 Velas are charged.
- [x] Tests: man pays once; woman pays nothing; double-tap race creates one thread and one charge.
  **Built as D-550 to D-554** (the founder's answers, 8 October 2026): a private message is a
  Thread of origin `dm` that never expires (`ddf84381ef6c` changes the CHECK; its downgrade
  refuses while one is active); whom you may reach is the public profile's rule, and for a private
  message each wanting the other's gender, every refusal `NOT_FOUND`; `expires_at` is a man's
  alone; the hours are `thread_hours`, read when the Thread opens, never a number in the code; a
  woman's two daily limits are `app_config` values (`386bbc188276`); the first message passes
  `messages/filters.py`, the prototype's lists with three corrections (D-552), and a refusal keeps
  a `message_rejected` signal. The double tap is forced in `test_race.py`: both opens inside
  their transactions before either locks the pair, each waiting alone with the lock.
  **Broken once each, 8 October 2026** (`uv run python -m tests.break_guards t71- t63-04`):
  T-7.1's twenty cases, each red in 1 of 1, every file restored and none differing by SHA-256
  after. **One stayed green at first and was a finding:** `t71-20` (the bare word "transfer"
  refused) passed, because the test's sentence said "transferring", which `\btransfer\b` never
  matches; a sentence with the bare word was added and the case went red. T-6.3's `t63-04`
  anchored on `mutual=False`, which this task made a parameter; it now weakens the parameter's
  default, and went red.
- [x] **Commit:** `feat(threads): open thread [T-7.1]`
  Added 8 October 2026 (the audit, P-490): T-7.1 landed as `8b6c542` without this line.

### T-7.2 · Thread list
- [x] **Needs:** T-7.1
- [x] `GET /threads?tier=threads|knots&filter=&q=`: excludes cleared (unless newer message), blocked; each row has other person's card-lite, last message preview (voice → "Voice note"), unread count, status, `expires_at`, whether I've tapped tie.
- [x] **The other person deleted their account** (T-9.6, D-051, D-500): their row's card-lite is
  "Deleted account", no name or photo, from the moment they delete; once erased they have no
  profile row at all. The thread stays, as the messages do.
  **Built 8 October 2026:** `recent` is a message in the last three days, the prototype's Knots
  filter; a voice note's preview carries no text and the web names it, so no copy lives in the
  API; `q` matches anywhere in the first name or username, `%` and `_` taken literally; a deleted
  account is `deleted: true` with no name, photo, badge or presence, and `q` never finds it; her
  rows carry no `expires_at` (D-554). `GET /threads/{id}` is the participants' alone, and a block
  hides it as it hides the row. **Broken once each** (`uv run python -m tests.break_guards
  t72-`): fourteen cases, each red in 1 of 1, every file restored and none differing by SHA-256.
  **Two stayed green at first, and were findings in the tests:** `t72-05` (my own messages
  counted unread) and `t72-06` (messages before my clearing counted) passed, because the message
  each guard leaves out was already marked read in its test, so the count never leaned on the
  guard. Both messages were made unread, and both cases went red.
- [x] **Commit:** `feat(threads): list [T-7.2]`

### T-7.3 · Messages
- [x] **Needs:** T-7.2
- [x] `GET /threads/{id}/messages?cursor=&limit=` (newest first, respects my `cleared_at`; voice notes locked for men without unlock → no media URL).
- [x] **Messages from a deleted or erased account** show as from "Deleted account" (D-051), and
  stay; sending to one is refused, with the code this task chooses (T-9.6, D-500).
- [x] `POST /threads/{id}/messages`: participant only; thread `expired` → `THREAD_EXPIRED` for his send, while hers is delivered (D-097: an expired Thread refuses his sends and accepts hers); text 1–2000; abuse/solicitation rules → `MESSAGE_REJECTED` (+ fraud event); masking if `message_count < mask_first_n` (store `body_raw`, set `masked`); dedupe on `client_msg_id` (return existing); update `last_message_at`, `message_count`; publish `message.new`; notify recipient if not connected.
- [x] **When she wrote first, he pays to answer: the 2-Vela re-open, `thread_reopen`** (D-250,
  the founder, 4 October 2026; T-5.2's item 10(b)). Charged through `pricing.service.charge`
  (T-5.2), never a literal price.
- [x] Tests for masking patterns (+91 numbers, spaced digits, emails, UPI handles, "insta: x"), rejection, dedupe, expired.
  **Built as D-551 and D-555** (the founder's answers, 8 October 2026): sending to a deleted
  account is `ACCOUNT_DELETED`; what he pays is D-551 (the opener writes free; answering her is
  the 2-Vela re-open once, writing first where she opened is 5; each private message 2); her
  message moves a live Thread's hour on to D-560's rule and his never does, and expiry is read
  from the clock, in sending and in T-7.1's open path (the founder's Q7: built here, T-7.6 finds
  it done); her daily limits (D-553) count a man when she writes first in a Thread, and every
  private message of hers. Two sends at once hold the Thread's row in turn (`test_race.py`, the
  overlap forced). A voice note is `NOT_ALLOWED` until T-7.9, whose media URL is never in a
  `Message`. **"Notify recipient if not connected" is T-9.4's:** its kinds already list "message
  (only if not connected)", and only T-7.4 can tell who is connected; this task queues
  `message.new` to both. **A block** makes the Thread `NOT_FOUND` here, as in T-7.2's list and
  `GET /threads/{id}`; T-9.1 decides whether sending says `BLOCKED` instead.
  **Broken once each** (`uv run python -m tests.break_guards t73-`): twenty-six cases, each red
  in 1 of 1, every file restored and none differing by SHA-256 after.
- [x] **Commit:** `feat(messages): list and send with safety filters [T-7.3]`

### T-7.4 · Real-time server
- [x] **Needs:** T-7.3, and **P-64**: in tests `session_for_the_app` replaces `get_session`, which is what publishes, so no endpoint test sees an event; and services queue events through `core/events.py` (T-5.1), never a publish of their own
- [x] `POST /ws/ticket` (Redis, 30 s, single use). `/ws` endpoint: validate ticket, register connection, subscribe `user:{id}`, heartbeat, close on logout/freeze. ~~Publishing helper `realtime.publish(user_id, type, data)` used by services.~~ **Services queue events through `core/events.py`, published after commit (T-5.1); this task builds the socket side only** (P-64's note, struck 8 October 2026 as P-64 landed).
- [x] Load test: 1,000 concurrent sockets on one instance stay under 256 MB.
  **Built as D-557, 8 October 2026:** the ticket kept by its hash and taken once; the socket
  only from the web's exact origins; one Redis subscription an instance; `ping`/`pong` and 60 s
  of silence; `socket.close` queued wherever sessions are revoked (sign-out, a replayed refresh,
  five wrong PINs, a deleted account), proved through each of those flows. The tests drive the
  app as ASGI in process (`tests/ws.py`), so a request's events reach a socket as in the app
  (P-64). **The load test** (`uv run python -m bench.realtime.sockets`, by hand, D-556): eleven
  runs on the founder's Mac, every socket open and every event delivered each time, the API at
  137 to 210 MB with 1,000 sockets open and 170 to 198 MB after the events: under 256 MB in all
  eleven, the worst by about 46. A local measure, never Fly's. **Fly needed nothing** (the plan's
  Q10 was wrong: Fly has no default hard limit, D-557). **Broken once each** (`uv run python -m
  tests.break_guards t74-`): eighteen cases, each red in 1 of 1, every file restored and none
  differing by SHA-256 after.
- [x] **Commit:** `feat(realtime): websocket gateway [T-7.4]`

### T-7.5 · Read receipts and typing
- [x] **Needs:** T-7.4
- [x] `POST /threads/{id}/read` sets `read_at` up to a message, publishes `message.read`. Client `typing` relay throttled.
  **Built as D-670, 8 October 2026** (the founder, on the advisor's recommendation, relayed):
  a read marks the other person's messages not yet read, up to and including the one named and
  after the reader's clearing; a `read_at` once set never moves; `message.read`
  (`{thread_id, up_to_message_id, read_at}`) goes to them alone, only when something was marked,
  and neither event carries an expiry or a price (D-554), so her "Not seen yet" (08-DESIGN §8)
  is her message's `read_at` still null. `NOT_FOUND` for anyone else's Thread, a block either
  way, another Thread's message and one before the clearing. **Typing** reaches the other person
  as `{thread_id}` alone, never the typist's own sockets: one a Thread every 3 s and 40 a minute
  in all, both in Redis, before one short session (`core/db.py`'s `session_opener`) asks
  whether they are its two with no block; anything else is dropped quietly, the socket left
  open. This amends D-557's "the gateway reads no database". **Broken once each** (`uv run
  python -m tests.break_guards t75-`): twenty cases, each red in 1 of 1, every file restored
  and none differing by SHA-256 after. Three older cases anchored on code this task moved
  (`t73-20`, `p64-01`, `t74-06`) were re-anchored and each went red again.
- [x] **Commit:** `feat(realtime): read receipts and typing [T-7.5]`

### T-7.6 · The 1-hour Thread: expiry, re-open, Extend
- [x] **Needs:** T-7.4 (and through it T-7.3, whose send path this task changes)
- **This is the 1-hour task D-097 names** (written by P-150, 8 October 2026). Until it lands, 24
  hours is what runs. What it builds is decided: D-097's five steps and its amendment (his message
  never restarts the hour; when Extend ends, the hour runs from her last message), D-098's prices,
  D-250 (Extend again and again), D-253 (Extend from expired is 10 in all), and the five answers
  below. How it is kept is D-560.
- **Decided 8 October 2026** (the founder, on the advisor's recommendation, Claude in a separate
  chat, relayed by the founder; P-150's five questions):
  1. **After a re-open, the hour starts now.** He paid 2 for an hour. From her last message, a
     message over an hour old would have had him pay 2 and expire on the spot.
  2. **One warning, 10 minutes before expiry, to him only;** the cron runs every minute. The old
     "< 2 h" never fires on a 1-hour Thread.
  3. **`thread_hours` keeps its name and is set to 1 here;** beside it, `thread_extend_hours = 24`
     and `thread_warn_minutes = 10`. T-7.1 already reads `thread_hours`, so no code is renamed.
  4. **A second Extend adds 24 hours to what is left,** never 24 from now: extending with 4 hours
     left gives 28, so no paid hour is lost.
  5. **The setting and the copy change together, in this task;** `/terms`' new sentence is shown
     to the founder before this task lands.
- [x] **The hour lives in `expires_at` alone (D-560),** every move of it in the transaction that
  causes it, with the Thread row locked:
  - open: `now + thread_hours` (T-7.1, as built);
  - **her** message on a live Thread: `max(expires_at, sent_at + thread_hours)`, so a message in
    an Extend's last hour carries the Thread past it and one earlier changes nothing (D-097's
    amendment, d). **His message never moves it** (a): a test has him write every 59 minutes and
    the Thread expire an hour after her last message;
  - Extend: `max(expires_at, now) + thread_extend_hours` (answer 4; from expired, `now` wins);
  - re-open: `now + thread_hours` (answer 1);
  - untie (T-7.7): `now + thread_hours`.
  Every move later clears `expiry_warned_at`, so each expiry gets its one warning.
- [x] **Expired is the clock, not the status column.** A Thread whose `expires_at` has passed is
  expired for every check, though the cron hasn't caught its status up: his send is refused with
  `THREAD_EXPIRED`, and her message is delivered and moves nothing (D-097 step 4: it stays expired
  until he re-opens). Without this, the minute between crons lets him send in a Thread that ran
  out, and lets her message revive one. T-7.3's send changes here to read it.
  **Built in T-7.3** (the founder's Q7, 8 October 2026; D-551): her message's `max` and the
  warning it clears, his message moving nothing, and expiry read from the clock in the send and
  in T-7.1's open path (`threads/rules.py`'s `has_expired`). This task's tests of them stand.
- [x] Cron `expire_threads` (every minute, batches of 500, `FOR UPDATE SKIP LOCKED`): active
  Threads past `expires_at` → `expired`, `thread.expired` to him. Cron `warn_expiring` (every
  minute): active Threads with `thread_warn_minutes` or less left and no `expiry_warned_at` →
  set it, push + `thread.expiring` to him. **Neither reaches her** (D-097: her side shows only
  that her message hasn't been seen; T-7.2 sends her `expires_at` as null).
- [x] **`POST /threads/{id}/extend`** + `Idempotency-Key` → `Thread`: Extend is sold here (D-253:
  no other task sells it). 10 Velas through `pricing.service.charge`, one `thread_extend` debit
  (D-251), the key naming the event the wallet keys a repeating reason on (D-077), so a double tap
  charges once. An active or an expired Thread; from expired the same 10 re-opens it, `active`,
  never a `thread_reopen` beside it (D-253). A Knot, or a woman (D-097: she is never charged and
  never shown it), → `NOT_ALLOWED`, and no ledger row.
- [x] `POST /threads/{id}/reopen` + `Idempotency-Key` (expired only) → debit 2 (men; D-098,
  `thread_reopen`), `active`, `expires_at = now + thread_hours`, warning cleared.
- [x] **The setting and every promise of it, in one commit** (answer 5). A data migration sets
  `thread_hours` to 1 and adds `thread_extend_hours` (24) and `thread_warn_minutes` (10),
  reversibly; with it, everything that says a Thread lasts a day (P-150's sweep, 8 October 2026):
  - `web/src/i18n/en.ts`: `landing.headlineThreads` ("Threads last a day."), `landing.intro` ("a
    24-hour thread"), `landing.features.threads.title` ("24-hour threads"), and `/terms`'
    `conversations.body` ("which lasts a day"), each with its comment. **`/terms` is a published
    page: its new sentence goes to the founder before this lands.**
  - `web/src/app/opengraph-image.jpg`, whose pixels say "Threads last a day", and
    `opengraph-image.alt.txt`, regenerated as 08-DESIGN §7 says.
  - the comments that say 24: `web/src/app/(marketing)/page.tsx`, `web/src/lib/site.ts`,
    `api/app/modules/threads/models.py`'s docstring, `api/tests/test_reference_data.py`'s seed
    test, `api/tests/test_schema.py`'s "24-hour promise".
  Untouched, and right: the seed migration's `thread_hours: 24` (history; the new migration
  moves it), and `api/tests/modules/pricing/test_service.py`'s "another 24 hours", which is
  Extend's.
- [x] Tests using a controllable clock: her message restarts the hour and his never does; Extend
  stacks (answer 4); an extended Thread expires the instant Extend ends when her last message is
  over an hour old (d), and doesn't when she wrote in its last hour; Extend from expired is one
  debit of 10; re-open is 2 and an hour from now; a woman's Extend writes nothing; past
  `expires_at` before the cron, his send is refused and her message revives nothing; her message
  racing the cron, the overlap forced, never leaves an active Thread with an expiry in the past;
  one warning per expiry, never to her.
- [x] **The price shown (P-56, D-600):** re-open and Extend take `shown_price` and pass it to `charge(..., shown=)`; Extend from expired compares its 10, never 2 + 10. Test `PRICE_CHANGED` with nothing charged or written, and its web sends the price it displayed, from `/prices`.
- [x] **The match sheet's footer too** (T-6.5): `discover.match.footer` in `en.ts` says "Threads
  last a day. Knots last." while `thread_hours` is 24; with this task it takes 08-DESIGN §8's
  "Threads last an hour. Knots last." in the same commit.
  **Built 8 October 2026, with the founder's answers to its plan (D-640 to D-642):** the two
  sweeps run once a minute in the worker's own loop, not as ARQ crons, which would cost Upstash
  Free more than it has (D-640, `app/workers/minutely.py`); a re-open or an Extend he paid for is
  his answer too, so he never pays to re-open and then again to reply (D-641); a woman's re-open,
  and either on a Knot or a private message, is `NOT_ALLOWED`, and a re-open of a live Thread
  returns it, nothing charged (D-642). Re-open and Extend take `{shown_price?}` and an
  `Idempotency-Key`, the wallet's event `reopen|extend:{thread}:{key}`; `useReopenThread` and
  `useExtendThread` (`web/src/lib/queries/threads.ts`) send both, for T-7.11's buttons. The
  migration is `7ee6438868ed`. The share image was regenerated as 08-DESIGN §7 now records. The
  `/terms` sentence and the landing, match-sheet and share lines were shown to the founder and
  approved before landing. The races are forced on committed rows with no ledger row committed
  (`test_clock_race.py`): two Extends at once each add their day, and the sweep skips a Thread a
  send holds and takes it the next minute. **Broken once each** (`uv run python -m
  tests.break_guards t76-`): twenty-eight cases, each red in 1 of 1, and the five older cases
  whose anchors this task moved (t71-04, t71-06, t71-07, t72-04, t72-13) red again, every file
  restored and none differing by SHA-256 after (t72-04's anchor moved again on rebasing over
  T-7.8, whose t78-02 needed a longer one beside it: both red again); the hooks' four guards and the share image's alt
  text broken by hand, each red, each file restored by its hash. Found writing the plan: P-540.
- [x] **Commit:** `feat(threads): the 1-hour Thread, expiry, re-open and Extend [T-7.6]`

### T-7.7 · Tie the knot
- [x] **Needs:** T-7.6
- [x] `POST /threads/{id}/knot`: set my `*_knot_at`; if both set → `knotted`, `knotted_at`, `expires_at = null`, publish `knot.accepted` to both; else publish `knot.requested` to the other. Works on `expired` threads too (converts directly if both).
- [x] `DELETE /threads/{id}/knot`: untie → `active`, a fresh hour (`now + thread_hours`, T-7.6), clear both taps, notify.
  **A private message's Knot untied never expires again** (D-550, T-7.1): `expires_at` stays
  null, as the CHECK allows only for origin `dm`; a match's gets a fresh `thread_hours`.
  **Built 9 October 2026 as D-770** (the founder's answers to its plan, on the advisor's
  recommendation, relayed): untying a Thread that isn't a Knot returns it unchanged, so tap,
  untie, tap asks her once; a tap with a deleted account is `ACCOUNT_DELETED`, nothing written;
  `knot_requested` and `knot_accepted` notifications, an untie the event alone; the "Knot tied"
  sheet and the web's hooks go to T-7.11 (P-670). Tapping and untying hold the Thread's row,
  30 a minute between them. The races are forced on committed rows (`test_knot_race.py`): two
  taps at once make one Knot, and the minute's sweep, in either order with the last tap, never
  expires it. **Broken once each** (`uv run python -m tests.break_guards t77-`): sixteen cases,
  each red in 1 of 1, every file restored and none differing by SHA-256 after. T-7.6's `t76-09`
  and `t76-10` anchored on lines untying repeats; both were re-anchored on `_buy_time`'s own
  `until` and went red again.
- [x] **Commit:** `feat(threads): tie and untie knot [T-7.7]`

### T-7.8 · Clearing
- [x] **Needs:** T-7.2
- [x] `POST /threads/{id}/clear`, `POST /threads/clear` (ids or `expired: true`), `DELETE /threads/{id}/clear` (restore). Upsert `thread_clears`. Never touches `messages`.
- [x] Test: after A clears, B still sees everything; admin still sees everything.
  **Built as D-610 and D-611** (the founder's answers, 8 October 2026): a clearing holds the
  Thread's row as a send does and is stamped with the newest message's `created_at` (the opening
  before any), never the tap's time, so a message written after it always shows; restoring
  deletes the row and the whole history comes back; a bulk clear skips ids that aren't yours or
  are across a block, and `expired: true` takes the Threads in your list expired by the clock.
  After A clears, B's list, unread count, Thread and messages page are equal to the byte, every
  message row and the Thread row are unchanged (`to_jsonb`), nothing is published or notified,
  and a read with no clearing applied (how T-9.1 and T-9.5 must read, noted on both) finds every
  message, `body_raw` included. `test_clear_race.py` forces the three ways a clearing and a send
  meet, each wait seen by Postgres (`pg_blocking_pids`). **Broken once each** (`uv run python -m
  tests.break_guards t78-`): fifteen cases, each red in 1 of 1, every file restored and none
  differing by SHA-256 after. P-510 (`GET /threads/cleared`, for T-9.8) and P-511 (the
  prototype's 7-day auto-clear, after beta) filed.
- [x] **Commit:** `feat(threads): one-sided clearing [T-7.8]`

### T-7.9 · Voice notes
- [x] **Needs:** T-7.3, T-4.1
- [x] `POST /media/voice-upload-url` (women only, ≤ 60 s, ≤ 2 MB, audio/webm|ogg|mp4), then send message `kind=voice` with `media_key`, `duration_s`.
- [x] `POST /messages/{id}/unlock` (men, debit 5, insert `message_unlocks`, idempotent) → signed URL. `GET /messages/{id}/media` for sender or unlocked.
- [x] **The price shown (P-56, D-600):** `POST /messages/{id}/unlock` takes `shown_price` and passes it to `charge(..., shown=)`. Test `PRICE_CHANGED` with nothing charged or written, and its web sends the price it displayed, from `/prices`.
  **Built as D-620 and D-621** (the founder's answers, 8 October 2026): the server measures the
  length from the bytes (`core/audio.py`, written by hand: Ogg Opus, WebM, MP4 with its
  fragments; the longer of two stated lengths; unreadable refused), the client's `duration_s`
  only checked (P-15's API bound, 1 to 60) and never stored. **Found building it:** the upload
  URL outlives the check, so the browser PUTs to `voice-uploads/…` and the send writes the bytes
  it measured to `voice/{thread}/{file_id}`, new each time, which no client can write: nothing
  can be swapped in after he pays. Three new error codes: `UNSUPPORTED_AUDIO`, `AUDIO_TOO_LARGE`
  and `AUDIO_TOO_LONG`. The unlock records first and charges
  only a new row; an expired Thread is no bar (the founder's Q2). The price box's web half, the
  locked card sending the price it showed, is T-7.11's (P-56 is on its Needs line). `message.new` now reaches a man
  with a voice note locked: T-7.3's `announce` told both it was unlocked. A double unlock is
  forced in `test_race.py`, both inside their transactions before either records it, each
  waiting alone. T-7.3's "a voice note isn't sendable yet" test and its case `t73-15` retired
  with this task; `t73-24` and `t73-25`'s anchors widened, as `voice_of` repeats their lines.
  `messages.service.send` now takes `storage` and `settings`, so T-7.8's `test_clear_race.py`,
  landed first, passes them as `test_race.py` does.
  **Broken once each, 8 October 2026** (`uv run python -m tests.break_guards t79- t73-24
  t73-25`): T-7.9's thirty-five cases and the two re-anchored, each red in 1 of 1, every file
  restored and none differing by SHA-256 after. **Two guards had no test until written for the
  run:** the bytes read held to 2 MB again (a PUT between the size and the read) and the type
  sniffed (a Matroska file declared WebM parses as one); a test was added for each before the
  run. A third, the round trip in `parse_voice_upload_key`, could never go red under its regex
  and was removed.
- [x] **Commit:** `feat(messages): voice notes and unlocks [T-7.9]`

### T-7.10 · Web chat list
- [x] **Needs:** T-7.2, T-7.8, and **P-460**: her rows draw no countdown and no expired state
- [x] Threads / Knots tabs with counts; live countdown per row (one shared 1 s ticker, not one per row); Knots filters; search; select mode + bulk clear; "Clear expired (n)"; trash per row with 5 s undo toast; unread dots; empty states.
  **Built 9 October 2026** (the founder's answers, on the advisor's recommendation, relayed):
  `src/components/chats/` from 08-DESIGN §8, never the prototype. **Her list says nothing about
  time (P-460):** her rows draw no `Countdown` and no expired state whatever `status` or
  `expires_at` they carry, and she gets no "Clear expired" and no footer; the gate is an
  allowlist (`gender === "male"`), so while `me` loads nobody sees a countdown. Every countdown
  reads one shared clock, `src/lib/ticker.ts` (`useNow`), started by the first reader and
  stopped after the last. `Countdown` (§4) says "41m left" (minutes rounded up), "22h left"
  past the hour (an Extended Thread), fills `--accent` under ten minutes and says "Ran out",
  by the clock (D-560). A tab's count is one page of its tier, 50 (the API's largest), and
  "50+" beyond (Q1). A row opens `/chats/{id}`, T-7.11's screen (Q2). His footer is the
  one-hour line, landed after T-7.6 (Q3). A clear takes the row out at once and offers Undo for
  5 s once the server has it; Undo is `DELETE /threads/{id}/clear` (Q4), which brings back
  history from an earlier clearing too: P-620. Select mode clears up to 100 at once, as the API
  takes. Search is by name only, as `q` is (T-7.2), trimmed, never empty, at most 50.
  **Broken once each, 9 October 2026** (`node scripts/break-guards.mts t710-`, log in the main
  checkout's `out/t-7.10-break-guards.log`): twenty cases, each red in 1 of 1, every file
  restored byte for byte.
- [x] **Commit:** `feat(web): chats list [T-7.10]`

### T-7.11 · Web conversation
- [x] **Needs:** T-7.3, T-7.7, T-7.9, and **P-56**: its paid buttons send the price they showed
  (before the web's paid buttons, the founder, 8 October 2026); and **P-520**: a real recording
  from each browser read by T-7.9's measuring, or every iPhone user's voice note may be refused
- [x] Bubbles, day separators, "Sent/Read" on my last message, typing dots, voice player (locked card with price for men), icebreakers when empty, knot bar (tie / waiting), expired panel (re-open · 2 / tie), header with countdown or "Knotted · permanent", ⋯ → profile menu.
- [x] **P-670: the "Knot tied ✦" sheet** (08-DESIGN §8, headed T-7.7 there) when the second tap
  makes the Knot, and the `useTieKnot` / `useUntieKnot` hooks in `src/lib/queries/threads.ts`
  for `POST` and `DELETE /threads/{id}/knot` (T-7.7, D-770).
- [x] Composer: text (Enter sends, Shift+Enter newline), mic for women (MediaRecorder, hold or tap-to-record, 60 s cap, preview before send). Optimistic send with `client_msg_id`; failed → retry.
- [x] Rejected message → inline explanation, text kept in composer.
- [x] **Her side of an expired Thread (D-097):** readable, and otherwise silent: no prompt, and no sign that money stands between her message and his reply. An expired Thread accepts her sends, so her composer keeps working; the re-open price is his alone.
- [x] **Allow the microphone here (D-059):** T-2.5's Permissions-Policy has `microphone=()`, so recording is refused until this task makes it `microphone=(self)`; add `media-src` for voice notes' storage origin and `blob:` for the preview.
  **Built 9 October 2026, with the founder's answers to its plan (D-870, D-871),** on the
  advisor's recommendation, relayed. **An API change first (D-870):** the web couldn't know what
  his next message costs, so `GET /threads/{id}` answers `ThreadView`, with `send_price` from the
  send's own `_answer` and `other`, a `CardLite` (no profile view counted). Its tests prove the
  price shown is the price charged, by the ledger, in each of D-551's cases. **The screen**
  (`src/components/conversation/`, at `/chats/[id]`): her side draws no countdown, bar, Extend,
  expired panel or price whatever it is sent (an allowlist, `gender === "male"`); his expired
  Thread keeps its history and offers re-open, re-open and keep, and the knot; every paid button
  sends the price it showed (re-open, Extend and an unlock from `/prices`, his message from
  `send_price`); a message shows at once, a refused one returns to the composer with its reason,
  a failed one keeps Retry under the same `client_msg_id`. Typing dots read a cache only T-7.12
  will write. The recorder is `src/lib/voice-recorder.ts`, and `/dev/voice` (`next dev` only) is
  where P-520's recordings are made with it. **Broken once each, 9 October 2026:** the API's six
  cases (`uv run python -m tests.break_guards t711-`) and the web's sixteen (`node
  scripts/break-guards.mts t711-`), each red in 1 of 1, every file restored byte for byte; logs in
  the main checkout's `out/t-7.11-break-guards-api.log` and `out/t-7.11-break-guards-web.log`.
  Two stayed green on their first run, each a weak test: the view's tests checked a send was
  accepted at the shown price, not charged it (now read from the ledger), and the input-method
  test looked for a request not yet made (now it holds the draft). T-4.7's two Permissions-Policy
  cases were re-anchored on the new policy. **P-520's recordings:** iPhone Safari's 5 s and 59 s, measured
  within the second (0.77 s and 0.96 s short), the Mac's browsers left to P-773 and Safari's MP4 to
  P-774 (the founder, 9 October 2026). Found building it: P-770 to P-774. Two items T-8.10
  and T-8.8 added here while it was being built (his gift button, the kudos prompt) moved to
  T-7.12 (the founder, 9 October 2026).
- [x] **Commit:** `feat(web): conversation screen [T-7.11]`

### T-7.12 · Web real-time client
- [x] **Needs:** T-7.4, T-7.11, and **P-460**: the client reads nothing from her null `expires_at`
- [x] `src/lib/ws.ts`: ticket → connect; exponential backoff 1→30 s with jitter; pause when tab hidden > 5 min; on reconnect refetch open thread + list. Events update TanStack Query caches (append message, bump row, update wallet, knot state).
- [x] **Widen the CSP here (D-059):** `connect-src` for `wss://` on the API host. The socket fails with a CSP error until then.
- [x] **His composer's gift button (08-DESIGN §8, "gifts go to a woman"):** T-8.10's `GiftSheet`
  (`src/components/gifts/`), with her id and first name, shown only where her profile's
  `can_gift` is true (`GET /users/{id}`, D-780), never decided from a gender in the browser.
- [x] **The kudos prompt here too (T-8.8, D-790):** T-8.8 built it on the profile, from
  `PublicProfile.thread.kudos`, shown only for `can_give`. The conversation shows the same
  `KudosPrompt` by that state: read the other person's profile, or add `kudos` to `Thread` from
  `kudos.service.state`, never a second rule.
  **Moved here from T-7.11** (the founder, 9 October 2026): T-8.10 and T-8.8 added these two
  to T-7.11 while it was being built, and it landed without them; T-7.12 is the next work on
  the conversation screen (`src/components/conversation/`).
- **As built 9 October 2026 (D-880, D-881; the founder's answers to the plan, on the advisor's
  recommendation, relayed):** P-592 first, its own commit (worker jobs publish their events).
  **The API:** `ThreadView` gains `can_gift` (`discovery.service.can_gift`, the profile's and the
  send's one rule) and `kudos` (`kudos.service.state`); tests hold each to the profile and to the
  endpoint it leads to (`test_view.py`). **The socket** (`src/lib/ws.ts`): ticket, backoff from 1 s
  to 30 s with jitter, its count reset after 10 s open; never again after 4000 or 4403; `ping`
  every 25 s, a new socket without a `pong` in 10 s; closed after 5 minutes hidden; every
  reconnect asks the Threads and the wallet again; `typing` sent from the composer, once a Thread
  every 3 s. **The events** (`src/lib/queries/realtime.ts`) append a message once, mark "Seen",
  show the dots for 6 s and set the balance; a Thread's state is only asked again (P-460). **The
  CSP**: the API's host as a socket in `connect-src`, nonce routes only; `e2e/csp.spec.ts` sees
  the browser allow it there, refuse another host, and refuse it on a static page, signing no one
  in (P-680). **The screen**: his gift button where `can_gift`, the kudos prompt for `can_give`,
  "Knot tied ✦" for both once per Knot made while open (the founder's Q4), and P-764's Report and
  Block. **Broken once each:** the API's (`uv run python -m tests.break_guards t712- t810-
  t711-04`, 6 of 6 red) and the web's (`node scripts/break-guards.mts t712-web t46-lint t711-13`,
  25 of 25 red, after one stayed green on its first run: the Knot sheet's once-only test let the
  refetch land before the sheet closed, and now holds it until then); T-8.10's three and T-7.5's
  two cases re-anchored on the shared rules, T-4.6's two and T-7.11's one on the changed lines;
  logs in the main checkout's `out/t712-break-guards-api.log`, `out/t712-break-guards-web.log`
  (and `-run1.log`). **In the browser:** with the socket's source taken out, Chromium refuses
  the app's own socket on `/login` (`CSP-VIOLATION connect-src ws://127.0.0.1:8100/ws`,
  `out/t712-e2e-csp-broken.log`); restored, the CSP spec passes (`out/t712-e2e-csp.log`), and
  the whole E2E, 30 of 30, each journey now opening the real socket (`out/t712-e2e.log`).
  Found building it: P-780.
- [x] **Commit:** `feat(web): realtime client [T-7.12]`

### T-7.13 · E2E chat
- [x] **Needs:** T-7.12
- [x] Two browser contexts: man + woman. Match → open thread (balance −5) → messages both ways live → woman voice note → man unlocks (−5) → both tie → Knots tab. Expiry via test clock endpoint (local only).
  **Built 18 October 2026, with the founder's answers to its plan (16 October 2026, on the
  advisor's recommendation, relayed):** `web/e2e/threads.spec.ts`, one journey, a `test.step`
  for each of J4 to J7 (Q3), J7 before J6 since a Knot never expires; 06-TESTING has each as
  built. **The expiry is no clock (Q1, D-930):** `POST /v1/test/threads/{id}/expire` sets the
  Thread's `expires_at` to that moment, behind T-3.13's gate (ENV local and the fake SMS), so the
  API, the worker's sweep and the browser each see it by their own clock; a test clock would have
  moved the API's alone. Its first version ended the hour a second early, and the journey's voice
  note, sent 0.85 s before the call, read as hers after the hour ("She wrote back"), so it ends at
  the call. **His Velas:** the 5 he signs up with open the Thread, so his first Unlock opens the
  store and he buys 30 as J8 does: 5, 0, 36, 31, 29. **The deck** is shared by every journey's
  people, so each has a first name of their project's own and passes cards until the other's is
  on top, 25 at most. `signUpWoman` moved to `e2e/fixtures.ts` (Q2, P-663's woman half), with
  the steps J13 shares; `signUpMan` takes a first name. **Broken once each:** the route's five
  cases (`uv run python -m tests.break_guards t713-`, 5 of 5 red, every file restored,
  `out/t713-break-guards-api.log`); and in the browser, with T-7.12's `message.new` handler
  taken out (`addMessage`), J4 went red on both projects at the first message's arrival, then
  restored from its copy, SHA-256 checked (`out/t713-e2e-break-no-live-message.log`). `make e2e`
  passed 42 of 42 (`out/t713-e2e.log`).
- [x] **Commit:** `test(e2e): threads and knots [T-7.13]`

---

# Sprint 8 — Payments, album, kudos, referrals (week 13)

### T-8.1 · Packs and orders
- [x] **Needs:** T-5.1, T-1.21, and P-0.17: a chartered accountant has confirmed how prepaid Velas are treated, before any real sale can happen, **answered 8 October 2026 (below)**; and **P-130**: no Velas are sold while `/refunds` promises returns that don't exist (D-230)
- [x] `GET /packs`: active packs for the user's price-test variant (`users.id` hash → A/B, stable). `POST /payments/orders {pack_id}` + `Idempotency-Key`: copy amount + `credits` from the pack, compute first-purchase bonus, create provider order, insert `payments` (`created`), return checkout params.
- [x] **A woman can't order Velas** → `NOT_ALLOWED` (D-076). The database would refuse her credit anyway; the route says so first, before she pays for something she could never use.
- [x] **Variant B has no active pack** since T-5.2 retired `entry-25` (D-250). Worst case: a man
  hashed into B opens the store and finds nothing to buy. This task decides what B is shown until
  T-10.4 proposes a new test, and tests that no man ever gets an empty list.
- [x] Fake provider: returns a fake order and exposes a local-only endpoint that simulates the webhook.
- [x] **GST, as P-0.17 and D-450 have it (the founder, 8 October 2026):** `gst_paise` on the
  `payments` row, 0 while `GST_REGISTERED` is false, which it is today and stays until P-350;
  and a `gst_rate_bps` config, 1800 once registered. Prices are GST-inclusive (D-099), so
  registration never moves `amount_paise`: it splits it. A receipt, anything the user is shown
  about a payment (the order's response, `GET /payments/{id}`, T-8.7's copy, T-5.5's history),
  carries a GST line only when registered. Unregistered it shows the total alone: no "incl.
  GST", no rate, no GSTIN, since showing or collecting GST without a GSTIN is against the law.
  **Test:** an unregistered payment, serialised as the user sees it, contains the string "GST"
  nowhere. 03-SCHEMA and 04-API take the column and the fields in this task (rule 10).
- [x] **Aggregate turnover counter, P-350's companion:** the sum of paid payments' `amount_paise`
  (`status = 'paid'`, Razorpay's captured) with `paid_at` in the financial year, 1 April to 31
  March, at `GET /admin/turnover` or wherever the admin reads it (T-9.5's `/admin/metrics`
  otherwise), and an **alert at ₹15 lakh**: by whatever alerting exists before T-9.12, at the
  least a line the worker logs once a day with the year's figure, at warning level once ₹15
  lakh is passed. Counted from `payments`, never from the ledger: turnover is money in, and
  bonus Velas aren't. Worst case without it: the ₹20 lakh threshold is crossed and nobody
  knows, and registration is late, with penalty and interest from the first day over (P-350).
  **Test:** payments either side of 1 April fall into the right year, and the alert line
  appears at ₹15 lakh and not below it.
- [x] **Commit:** `feat(payments): packs and order creation [T-8.1]`

### T-8.2 · Webhook
- [x] **Needs:** T-8.1
- [x] `POST /payments/webhook`: verify `X-Razorpay-Signature` (HMAC SHA-256 of raw body with webhook secret) → else 400 and log. Handle `payment.captured` and `payment.failed` only; others → 200 ignore.
- [x] Captured: find by order id; if `provider_payment_id` already set → 200 no-op. Else one transaction: set paid + ids + `raw_webhook`, `wallet.credit(purchase)`, `wallet.credit(purchase_bonus)` if any, referral reward check (T-8.6). Always return 200 quickly.
- [x] Amount mismatch vs row → mark `failed`, alert, no credit.
- [x] **`raw_webhook` keeps no payer details, whatever city the database is in** (directed 3 October
  2026, from P-49's residency read): it stores an allowlist of the verified payload's fields and
  nothing else, Razorpay's payment and order ids, amount, currency, status, method, error code and
  timestamps. Never the payer's email, phone (`contact`), UPI ID (`vpa`), card or bank details:
  RBI's own list of payment data, and not ours to keep. An allowlist, never a list of fields to
  strip, so a field Razorpay adds later stays out. Test: a payload with every payer field set is
  stored with exactly the allowlisted keys.
- [x] `GET /payments/{id}` for the client poll.
- [x] **Refunds and disputes made outside us** (D-076, rule 3): a refund done in Razorpay's dashboard, or a chargeback, must not leave the payment's Velas standing. Handle Razorpay's refund and dispute events by reversing those Velas in the ledger, in the same step. That needs a debit reason for the reversal, an enum addition decided here. If the Velas were spent, decide here what happens, and write it down.
- [x] Tests: same webhook delivered 5 times concurrently → credited once; bad signature → no credit; amount mismatch → no credit.
- [x] **Commit:** `feat(payments): verified idempotent webhook [T-8.2]`

### T-8.3 · Refund requests
- [x] **Needs:** T-8.2
- [x] `POST /refund-requests` for **broken transactions only** (D-050): a payment that went through without granting Velas, or a duplicate charge for one purchase. A change of mind isn't a claim — purchases are final. In MVP an admin resolves each claim: missing Velas are granted through `wallet.credit()` (idempotent on the payment), and a duplicate charge is refunded to the original payment method in the gateway and recorded **on the claim** (`refunded`, with the gateway's payment and refund ids). **Corrected by D-580 (the founder, 8 October 2026):** this line first said "`payments.status = refunded`", but the payment refunded has no row of its own, so marking the row would call the purchase that stands refunded and drop it from turnover (D-483); the credited payment's row is never touched. This task defines the claim kinds and the `status` values.
- [x] **Missing Velas are granted with reason `purchase` (and `purchase_bonus`) and the webhook's own key** (D-077), never `admin_grant`: so a webhook arriving after the repair can't credit them a second time. Money goes back only under D-076's rule 3.
- [x] **Commit:** `feat(payments): refund requests [T-8.3]`

### T-8.4 · Private album
- [x] **Needs:** T-4.4, T-5.1; **P-79**: an approved private photo can't be swapped for an unmoderated one through its upload URL; and **P-301**: a private photo's served copy is the bytes moderation scored
- [x] Requests (debit 1 for men, D-231: viewing private pictures; `credits_charged` stored), incoming list for owner, decide (grant → enqueue `watermark_album`; decline → nothing is returned, D-230), revoke (delete watermarked copies, status `revoked`).
- [x] **A decline returns nothing** (D-230, superseding D-050's refund on a decline). `refund_album_declined` stays unused, never repurposed.
- [x] `watermark_album`: for each private photo render a copy with the viewer's `@username` tiled diagonally at ~20% opacity, **from its `scored_key`, never `raw_key`** (D-700); a photo with none is left out.
- [x] `GET /users/{id}/album` → signed URLs of the viewer's copies only.
- [x] **The price shown (P-56, D-600):** the album request takes `shown_price` and passes it to `charge(..., shown=)`. Test `PRICE_CHANGED` with nothing charged or written, and its web sends the price it displayed, from `/prices`.
- [x] **Built 9 October 2026 (D-730, D-731, D-732, the founder's answers on the advisor's
  recommendation):** `album_copies` rows (`57ab54709630`, its downgrade refusing while one exists),
  keys `album/{request_id}/{photo_id}.jpg`, on the erasure's and D-078's file lists; 30 days before
  asking her again after a decline or revoke (`album_reask_days`, `652c4bad186e`); `{status,
  photos}` for the album, her list paged, no charge for an album with no scored photo, and
  `album_photo_count` counting only those; a removed private photo's copies deleted. Tested in
  `tests/modules/album/` (the price, the cooldown on day 30 and day 31, five-way refusals with
  nothing written, the race forced on two connections, copies from the scored bytes and never the
  upload, a revoke racing the render), `test_images_watermark.py` and `test_watermark_album.py`.
  Broken once each (`uv run python -m tests.break_guards t84-`, log in
  `out/t84-break-guards.log`): 20 of 20 red, and t412-22, re-anchored to the generalised file
  read, still red; no file differing by SHA-256 after.
- [x] **Commit:** `feat(album): requests, grants, watermarking [T-8.4]`

### T-8.5 · Kudos
- [x] **Needs:** T-7.3
- [x] `POST /kudos` (thread with ≥ `kudos_min_messages`, one per pair ever, fixed kinds only), `GET /me/kudos`, visibility via `show_kudos` setting. Public profile shows distinct kinds received, never who sent them.
- [x] **Commit:** `feat(kudos): positive-only notes [T-8.5]`

### T-8.9 · Gifts
- [x] **Needs:** T-5.1, T-6.3
- [x] `GET /gifts` (active, sorted, cached 60 s).
- [x] `POST /gifts/send {recipient_id, gift_id}` with `Idempotency-Key`. Rules, each with a test:
  recipient must be a woman with onboarding `done` (else `NOT_ALLOWED`); sender must be a man
  (women sending → `NOT_ALLOWED`); blocked either way → `BLOCKED`; frozen sender → `ACCOUNT_FROZEN`;
  fifteen free sends a week, then each send costs its gift's price (D-231: the daily cap and
  `gift_free_daily_limit` are gone, so this task says whether `GIFT_LIMIT_REACHED` keeps a case,
  and proposes where the week starts);
  same gift to the same person inside `gift_same_recipient_cooldown_h` → `GIFT_COOLDOWN`.
  **Answered 8 October 2026 (the founder, on the advisor's recommendation):** the week starts
  Monday 00:00 IST and `GIFT_LIMIT_REACHED` is retired, never sent (D-650). Whom: anyone a private
  message could reach (D-550), else `NOT_FOUND`, a block never revealed, in place of `BLOCKED`
  and of `NOT_ALLOWED` for a woman not `done`; reachable but not a woman, `NOT_ALLOWED` (D-653).
  A frozen sender is refused by `deps.current_user` before the route runs (`ACCOUNT_FROZEN`).
- [x] Paid gifts: `wallet.debit(reason="gift", ref_type="gift_send")` **in the same transaction**
  as the `gift_sends` insert. Price read from the `gifts` row, never a literal.
- [x] **Name gift sending in the debit's allowlist:** `ALLOWED` in
  `api/tests/modules/pricing/test_debit_callers.py` (T-5.2). Until it is named, that test fails on
  any call to `wallet.service.debit` outside `pricing.service.charge`, this task's included. The
  free sends' setting is `app_config.gift_free_weekly_limit` (15, T-5.2). **The allowlist reads
  source, so it can't see a name built at run time: P-152,** worth doing here, where it is next
  touched. **Both done:** `("app/modules/gifts/service.py", "_send_in")` is in `ALLOWED`, and
  `debit()` refuses any other caller when it runs (D-651), proved against a name built at run time.
- [x] Links `thread_id` if an active or knotted thread already exists. Never creates a thread.
- [x] Publishes `gift.received` on the socket and a notification (respects prefs).
  **No setting in `notification_prefs` names gifts,** and pushes are T-9.4's: the in-app `gift`
  row is written as Threads' and matches' are, and which setting governs its push is **P-550**, on
  T-9.4's line.
- [x] `GET /me/gifts` (received, paginated, sender card) and `GET /users/{id}/gifts` (counts only,
  hidden when `show_gifts` is false). **And `GET /gifts` carries his free sends left and when they
  come back** (D-652); she never sees what a gift cost. The send keeps its `Idempotency-Key`
  (`gift_sends.idempotency_key`, migration `5978faceb05b`, D-653).
- [x] **The price shown (P-56, D-600):** `POST /gifts/send` takes `shown_price`; a gift debits outside `charge()` (priced from `gifts`), so it compares by hand with `pricing.service.price_changed()`, before the debit. A free send this week is a price of 0. Test `PRICE_CHANGED` with nothing charged or written, and its web sends the price it displayed, from `/prices`.
  **The web half is T-8.10's** (this task has no screen): pointer on its line, which sends the
  price `GET /gifts` showed, since gifts aren't in `/prices`.
- **Broken once each, 8 October 2026** (`uv run python -m tests.break_guards t89- p152-`): T-8.9's
  twenty-nine and P-152's five, each red in 1 of 1, every file restored and none differing by
  SHA-256 after. Among them: the sender's lock removed (both forced races red: two free sends past
  the limit, and the same key breaking on its unique constraint), the week read from the UTC date,
  the price from a literal table, a refused debit leaving its send, and `debit()`'s check removed,
  trusting a function's name in any module, or passing any module named `tests…`.
- [x] **Commit:** `feat(gifts): catalogue, sending, limits [T-8.9]`

### T-8.10 · Web gifts
- [x] **Needs:** T-8.9, T-5.5
- [x] Gift button on a woman's profile → sheet with D-231's four gifts: asset, label and the price
  in Velas, and the free sends left this week. (Was six in a 3×2 grid, with a daily count.)
- [x] Sending: optimistic disable, success toast, balance updates from `wallet.updated`.
  `GIFT_LIMIT_REACHED` / `GIFT_COOLDOWN` → friendly inline copy with when they can send again.
  `INSUFFICIENT_CREDITS` → store sheet.
  **From T-8.9 (D-650, D-652):** `GIFT_LIMIT_REACHED` is retired, never sent: past the week's free
  sends a gift costs its price. The sheet reads `GET /gifts`'s `free_sends_left` and
  `free_sends_reset_at`, and sends `shown_price`, the price it displayed: 0 while a free send is
  left, else the gift's `credits` from `GET /gifts`, never from `/prices` (gifts aren't in it).
  `PRICE_CHANGED` shows the new price again (D-600).
- [x] Received gifts row on her own profile and in You tab; toggle `show_gifts` in privacy settings.
- **Notification opens the sender's profile: moved to T-9.4** (the founder, 9 October 2026, on
  the advisor's recommendation): the web has no notification list or service worker until then,
  so there is nothing to open. Pointer on T-9.4's line.
- [x] **Built 9 October 2026 (D-780, and the founder's answers on the advisor's recommendation):**
  the gift button shows where `GET /users/{id}`'s `can_gift` says a gift is taken (a man, a woman
  he could send a private message to), which `test_can_gift_is_the_sends_own_answer` holds to
  `POST /gifts/send`'s own answer, case by case, and each of its three conditions removed turns
  it red (`uv run python -m tests.break_guards t810-`, 3 of 3, `out/t810-break-guards.log`). The sheet (`src/components/gifts/GiftSheet.tsx`,
  `GiftGrid` in `ui/`) is existing parts only, as T-8.7's store was. "Free" and 0 while a free
  send is left, else each gift's `credits`, and the price `PRICE_CHANGED` gives is shown and sent
  next. A send keeps its `Idempotency-Key` for the same gift at the same price, so trying again
  after no answer is the same send. `GIFT_COOLDOWN` says how long, rounded up to the minute, and
  holds that gift until the sheet reopens. `INSUFFICIENT_CREDITS` opens the store. The balance
  updates through `touchesWallet` until T-7.12's socket, whose line already updates the wallet.
  Her counts are on every profile that shows them, with "Only you can see these" on her own
  while `show_gifts` is off. Her list and the `show_gifts` switch are a women-only Gifts section
  on the You page, built as T-9.8's placeholder still stands (`useUpdateSettings`, for T-9.8's
  settings to reuse). Tested in `GiftSheet.test.tsx`, `ReceivedGifts.test.tsx`,
  `GiftGrid.test.tsx`, `gifts.test.tsx` and `ProfileScreen.test.tsx`; eight of the web's controls
  broken by hand, seven red, and the eighth (clearing the key after a refusal) removed as no
  control at all.
  Its E2E journey (she signs up as J2, he sends a free Coffee from her profile, she finds it in
  the You tab, and her switch hides her counts from him) passed locally on both projects, but
  isn't landed: CI's E2E has no OTP sends to spare (P-680, the founder, 9 October 2026).
  **Landed by P-680** as J13 (06-TESTING), 9 October 2026.
- [x] **Commit:** `feat(web): gifts on profile [T-8.10]`

### T-8.6 · Referrals
- [x] **Needs:** T-8.2; and **P-63, if one transaction credits two men** (the referrer and a
  referee who is a man, or a reward inside T-8.2's webhook transaction): moved here from T-9.3,
  dropped by D-230, 4 October 2026. **It did, so P-63 was built in this task** (the founder's
  brief, 8 October 2026; its line says how).
- [x] `POST /referrals/apply {code}` only before onboarding `done`, not own code, once. Reward both (Velas from `app_config`) when the referee completes selfie verification or first purchase, whichever first; idempotent. `GET /referrals/me`. Apply looks a code up and never checks its format: the seed's three test accounts carry readable codes outside the generated one (T-3.3).
  **Built:** "once" is once per phone number, ever (D-691); `referral_reward_velas` 5 to each man
  on it, the referrer paid for `referral_rewards_max` 10 at most (D-692); only a code whose owner
  is `done` and `active` or `paused` works, and only a man who still stands is paid (D-693). The
  reward runs in the webhook's capture before the purchase, and in the selfie's decision, both
  wallets locked in `user_id` order first (P-63).
- [x] **A woman's referral reward is never Velas** (D-076): the database refuses any ledger row for her, and "Reward both" would otherwise reach every referred woman, since every woman verifies her selfie (D-008). Decide here what she gets instead, if anything, and write it down.
  **Decided: nothing** (D-690, the founder, 8 October 2026); her referrals are counted in `GET
  /referrals/me` only.
- [x] **D-078 (P-54):** an under-18 refusal deletes `referrals` rows naming the user, as referrer or
  referee, once P-54's row half has landed; check it has. A reward already paid is a ledger row,
  which rule 12 keeps, and would stop the deletion: none can exist before dob is set.
  **Checked:** `Attached(Referral, ("referee_id", "referrer_id"))` is in `UNDERAGE_DELETES`, and
  a test applies a code at the dob step, gives an under-18 date, and finds no referral and the
  referrer untouched. Both triggers come after `dob`, so no reward can exist before it.
- [x] **Commit:** `feat(referrals): codes and rewards [T-8.6]`

### T-8.7 · Web store and checkout
- [x] **Needs:** T-8.2, T-5.5, and the founder's answer: **can "Most popular" show when nobody has
  bought anything yet?** At launch the words aren't true of the world. Moved here from T-5.2's
  Needs line (item 8), 4 October 2026 (the founder), since this screen holds the tag:
  `credit_packs` has no column for it. Separate from the value question, which is settled (D-231).
  **Answered 9 October 2026 (the founder): no.** "Best value" on the cheapest Vela at launch
  (D-760); "Most popular" when real purchases make it true (P-660).
- [x] Store sheet from the prototype (packs, per-Vela and per-thread price, first-purchase banner), with D-099's packs, not the prototype's (08-DESIGN §5). **"Most popular" stays on the ₹4,500 pack, the dominated one, chosen knowingly (D-231); whether the words can be shown when nobody has bought anything yet is the founder's to settle (on this task's Needs line).** The 20% first-purchase bonus stays. Load Razorpay Checkout script on demand. On success callback → poll `/payments/{id}` every 1.5 s (max 60 s) → toast + wallet refresh. Failure/dismiss → "Payment didn't go through" sheet with retry.
  **As built (D-760, D-761):** "Best value", worked out from the packs, and no "Most popular".
  The design is existing parts only (08-DESIGN §5, the founder's approval). Packs and the Thread's
  price come from `GET /packs` and `GET /prices`, never the web. A woman never sees it and never
  asks for packs. "Try again" reopens the same order. The order's amount is checked against the
  price shown before any window opens. Only `paid` ends the poll, and at 60 s "still confirming"
  takes over. Local and CI builds pay by a stand-in and the fake gateway (J8, J9, both passing).
- [x] **Widen the CSP here (D-059):** Razorpay Checkout's script, frame and connect hosts, exactly as Razorpay documents them. The CSP has been enforced since T-2.5, so checkout fails with a CSP error until this lands.
  **Razorpay documents none** (its security pages list API and IP whitelisting only, read 9
  October 2026). So the list is what its live Checkout asked of the page in Chrome, under
  production's policy, plus inline styles for its phone layout. It applies on Razorpay builds'
  nonce routes only (D-761), and `web/bench/razorpay-csp.spec.ts` holds each source to a
  violation without it (6 of 6, `out/t-8.7-razorpay-csp.log`). A real payment's steps on staging
  with test keys: P-661.
- [x] **The man's claim form (P-481):** `POST /refund-requests` from a payment that broke, the two
  kinds only (D-580). **On the checkout's "didn't go through" and "still confirming" sheets**,
  where the payment's id is known. From the history, and a claim's outcome: P-662, before beta.
- [x] **Commit:** `feat(web): store and razorpay checkout [T-8.7]`

### T-8.8 · Web album, kudos, referral UI
- [x] **Needs:** T-8.4, T-8.5, T-8.6
- [x] Album section on profile (locked / pending / granted with watermark note); incoming requests list for women with grant/decline; kudos prompt in chat after the threshold; referral code field in onboarding (optional) and share card in You tab.
- [x] **Referrals are paused (D-840, P-740):** while they are, build no referral code field and no
  "invite friends" or share card, nor any copy offering a referral. `POST /referrals/apply`
  refuses every code (`NOT_ALLOWED`, `referrals_paused`). The two referral items above wait for
  the decision that turns referrals back on, and that one needs P-591 done first.
- [x] **The album request sends `shown_price`,** the `album_request` price it displayed from
  `/prices` (P-56, D-600): T-8.4's API refuses anything else with `PRICE_CHANGED`, a man's absent
  field included. Its states are `GET /users/{id}/album`'s `status` (D-732); a refusal's
  `details.why` (`recently_declined`, `empty_album`) is shown in words, never as a code.
- **As built (D-790, the founder's answers to the plan, 9 October 2026):** the album row on
  `/people/[id]` (`AlbumSection`): locked with "Ask to view" and the `album_request` price from
  `/prices` (a woman's "Free", 0), "Asked" while pending, his watermarked copies once granted,
  `declined` and `revoked` read as locked; `recently_declined` in neutral words naming no decline
  and no person (`album-copy.test.ts`). The kudos prompt on the profile too, not in chat (T-7.11
  isn't built; a pointer on its line), from `PublicProfile.thread.kudos` (P-580). Her requests at
  `/you/album-requests`, linked from the You placeholder for everyone. No referral field, card or
  copy: `referrals-paused.test.ts` holds `en.ts` to it. Broken once each (`uv run python -m
  tests.break_guards t85- t88-`, log in `out/t88-break-guards.log`): 13 of 13 red, T-8.5's
  four talk-rule cases re-anchored to the shared `_talked`, no file differing by SHA-256 after.
- [x] **Commit:** `feat(web): album, kudos, referrals [T-8.8]`

### T-8.11 · Welcome Velas
**Filed 8 October 2026 (D-470):** every man gets 5 Velas when he finishes sign-up, once per phone
number, ever. The founder's decision; the shape is the advisor's (Claude, in a separate chat),
relayed by the founder.
**Worst case first: one number, account after account.** What stops it: `users.phone_hash` is
unique, so a number holds one account at a time, and the ledger's one-per-event index gives an
account one grant. D-072's hash does nothing here: it is written only when a date of birth is
refused. What that leaves is P-371, answered by the founder on 8 October 2026:
**re-registering** on the same number once T-9.6 has anonymised the old account would grant again,
and is **closed** here, by a kept hash of every number that received a grant (below); **a fresh
number** per account gets its 5 each, one Thread's worth, and is **accepted**, knowingly (D-470).
- [x] **Needs:** T-5.1, T-4.8
- [x] **Config:** `app_config.welcome_velas`, 5, by a data migration of this task's own (rule
  11), `ON CONFLICT DO NOTHING` like T-1.14's. 03-SCHEMA's `app_config` seeds take it. Tunable
  (D-470): at 0 the service writes nothing and never calls `credit()`, whose `delta <> 0` would
  refuse it.
- [x] **Enum and migration:** `welcome` in `ledger_reason_t`, rebuilt both ways as
  `4a7e20790605` did (D-251), the downgrade refusing once the ledger holds a `welcome` row. A
  credit, `ref_type` `user` (the man himself), inside the one-per-event index (D-470): named in
  the direction and `ref_type` checks, which are allowlists, in `wallet/rules.py`, and in
  `tests/modules/wallet/test_guards.py` and `test_reason_migration.py`. 03-SCHEMA's enum and
  ledger-shape table change with it.
- [x] **Once per number:** a hash of every number that received a grant (the HMAC
  `users.phone_hash` holds, D-061), kept where T-9.6's anonymisation never clears it, as D-072
  keeps one. The grant checks it first, and a later account on that number gets nothing. This
  task names the table and 03-SCHEMA takes it; if it carries a key to `users`, D-078's test makes
  it choose deleted or kept. **`/privacy` says why the hash is kept** ("so that deleting an
  account can't be used to escape a ban or a report", `en.ts`): this task adds the welcome reason
  there, in the same commit (D-051's note).
- [x] **The grant, in `onboarding.complete()`'s transaction,** as the step moves to `done`:
  `wallet.service.credit()` with `welcome`, key `{user_id}:welcome:{user_id}`, for a man only
  (gender `male`, an allowlist the service checks first). A woman is skipped by the service,
  since leaving her to D-076's trigger would abort her sign-up. Never a default balance (rules 5,
  6). Nothing for D-078: the grant comes after `dob`, so no under-18 account can hold one (D-470).
- [x] **Tests, each guard broken once:** a man finishing gets 5 (balance 5, one `welcome` row); a
  woman finishing gets 0 and no row, and her sign-up completes; `done` twice gives one grant, with
  two completions forced to overlap; `welcome_velas` 0 gives no grant and no row; grant, delete
  the account, sign up again on the number after T-9.6's 30 days: no second grant (P-371).
  T-9.6 comes after this task, so until it lands the test stands in for its anonymisation by
  freeing the number from the old account, and T-9.6 runs it through its own (its pointer).
- [x] **T-9.6's erasure already keeps the hash table by name** (D-503): `welcome_grants`, in
  `KEPT_WHEN_BUILT` in `api/app/modules/account/erasure.py`. Name the table that, or rename the
  entry; once the table exists, the check asks for it to move to `KEPT`. T-9.6 came first, so
  this task's test (grant, delete, sign up again after 30 days, no second grant) runs through the
  real erasure, `account.service.erase_due_accounts`, with no stand-in.
- [x] **Types and copy:** `make types`, since `LedgerReason` gains `welcome` (rule 10), and a
  history label for it in `en.ts`, whose `satisfies Record<LedgerReason, string>` fails `tsc`
  without one.
- [x] **For this task's plan, the advisor's recommendation** (Claude, in a separate chat, relayed
  by the founder, 8 October 2026; not decided here): a missing `welcome_velas` row skips the grant
  and logs a warning, and never fails sign-up; no backfill for men already `done`, since before
  launch they are test and seed accounts; and one line telling a new man about his 5 Velas,
  inside D-262's rule (`claims.test.ts`). The worst case of the first, for the plan to weigh: a
  skip is silent, so a lost row grants nobody until someone reads the warning.
- [x] **Commit:** `feat(onboarding): welcome Velas for new men [T-8.11]`

---

# Sprint 9 — Safety, admin, notifications, hardening (weeks 14–15)

### T-9.1 · Reports and blocks
- [x] **Needs:** T-7.2, and **P-400**: a blocked person deletes and signs up again on the same
  number to reach the one who blocked them; and **P-16**: whether unblocking keeps history (a
  migration, if it does)
  **Answered 9 October 2026, the founder:** P-16 soft-unblock (D-860), P-400 by number (D-861).
- [x] `POST /reports` (≤ 10/day, details ≤ 500, optional `also_block`), `POST /blocks`, `DELETE /blocks/{id}`, `GET /blocks`.
  **Built as D-863:** `also_block` is said every time; repeats are new reports; `GET /blocks` is
  a page (`BlockedUserPage`); anyone with an account may be blocked or reported.
- [x] Block effects, each with a test: removed from both discovery feeds, search, likes; profile → 404 both ways; threads hidden for both and sending → `BLOCKED`; realtime events stop; existing album grants revoked.
  **Built as D-862: sending is `NOT_FOUND`, never `BLOCKED`**, which would tell him. Each surface
  is asked of both people, whichever blocked (`test_block_effects.py`); the Thread's clock neither
  warns nor tells of an expiry across a block; grants are revoked either way, and `decide` is
  `NOT_FOUND` across one, a grant and a block at once forced in both orders
  (`test_block_album_race.py`). A new account on a blocked number is blocked too (D-861).
  Notifications from before a block are left out by T-9.4 (P-760, D-858).
- [x] Reported person is never told who reported.
  Nothing is queued or written for them, with `also_block` or without (`test_reports.py`).
- [x] **A report's evidence is the whole Thread, whatever the reporter cleared** (T-7.8, D-006,
  D-610): read the Thread's messages from `messages` by `thread_id`, never through
  `messages.service.list_messages` or anything that applies `thread_clears.cleared_at`, which
  shows a person their own view. Clearing never touches `messages`, so nothing is lost; a test
  clears, then reports, and finds every message. A block hides a Thread separately from a
  clearing: unblocking brings it back with the clearing still in place.
  **Built:** `safety.service.report_evidence`, through `safety.repository.thread_messages`, for
  T-9.5's admin read. **Broken once each** (`uv run python -m tests.break_guards t91-`):
  nineteen cases, each red in 1 of 1, every file restored and none differing by SHA-256 after;
  T-6.2's `t62-03` re-anchored on the new helper, red in 1 of 1.
- [x] **Commit:** `feat(safety): reports and blocks [T-9.1]`
  **J10 held by P-680** (06-TESTING): written and passing locally, it took CI's E2E past the
  20-sends-an-hour cap; it waits on branch `t-9.1-j10`. Report and Block in the conversation's ⋯
  menu: P-764. **Landed by P-680**, 9 October 2026.

### T-9.2 · Fraud scoring v1
- [x] **Needs:** T-9.1
- **A freeze closes the sockets** (T-7.4, D-557): wherever this task sets `frozen` and revokes
  the sessions, `events.close_sockets(session, user_id)` in the same transaction, as sign-out does.
  **Built:** `safety.scoring._freeze` calls `auth.service.sign_out_everywhere`, which does both.
- **The plan, approved by the founder, 9 October 2026** ("t 9.2 ka plan sahi hai"): every
  recommendation of Claude's plan, Q2 option B; Q1, Q2, Q3 and Q7 his decisions (D-900 to D-902),
  Q4 and Q5 approved with it (D-903, D-904). His addition: he lifts any freeze himself, from now
  (D-906, `app.tools.unfreeze`).
- [x] Signals written as `fraud_events` by services: report received, contact-info masked, message rejected (abuse / solicitation), > 30 new threads in 24 h, identical first message to > 10 people, > 3 devices in 7 days, location jumps > 500 km in 1 h.
  **Built (D-900):** `report_received` (`safety.service.report`), `contact_masked` and
  `identical_first_message` (`messages.service.write_text`, a Thread's first message only, case
  and spacing ignored, 7 days), `message_rejected` weighed by its rule, `many_new_threads`
  (`threads.service._open_in`, the ones they opened), `many_sign_ins` (`auth.service.sign_in`),
  `location_jump` (`profiles.service._locate`, kilometres only). A threshold signal once a day.
  Through `safety/signals.py`; `test_fraud_signals.py`, each at its threshold and one below.
- [x] Sessions store no IP address or user agent (D-067), and "> 3 devices in 7 days" needs one of them. Add what this task needs here, with a line on `/privacy`, which lists neither today.
  **Built as D-903: neither.** A device is a sign-in, a session family still signed in that began
  in 7 days, so nothing new is stored; `/privacy`'s new `collect.safety` line says sign-ins are
  counted, and what scoring can do.
- [x] **A possible-minor photo's event is a signal, not proof** (D-093): it weighs in the score, and
  nothing here acts on it alone. Repeated ones go to a human (P-72), never to an automatic ban.
  **Built:** 10 each, capped at 20, under the monitor band, so it never acts alone
  (`test_possible_minor_scores_never_act_on_anyone_alone`). P-72 stays open.
- [x] `recompute_fraud` worker: weighted sum with 7-day decay → `fraud_scores` + band. Actions: `shadow` → shown only to other shadowed users; `freeze` → status `frozen`, sessions revoked, admin notified. 3 reports from different users in 24 h → freeze immediately.
  **Built:** `app/workers/tasks/recompute_fraud.py`, every 10 minutes in the worker's own loop,
  and the person reported scored in the report's transaction, their row locked first, so two
  reports at once count one after the other (`test_report_freeze_race.py`, the overlap forced
  and seen in `pg_blocking_pids`). Three reporting numbers who shared a Thread freeze (D-901);
  strangers' reports shadow at three. "Admin notified" is the system user's `audit_log` row and a
  `fraud.frozen` warning (D-904, P-800). Only `active` and `paused` accounts are frozen, whenever
  the band is freeze (a deleted account restored in the band included), and nothing automatic
  lifts a freeze (D-902). **P-20 folded here:** the system user, migration
  `4800f0e8d5a9` (D-905). **The founder's undo:** `python -m app.tools.unfreeze` (D-906), with
  `fraud_scores.counted_from` (migration `445eefba7f8e`).
- [x] **D-078 (P-54):** an under-18 refusal deletes `fraud_events` and `fraud_scores` rows, once P-54's
  row half has landed; check it has, since a location jump can come before dob is set.
  **Checked:** P-54's row half has landed; both tables are in `UNDERAGE_DELETES`. A location
  can't come before dob (D-068: `PUT /me/location` works from the `username` step), but sign-ins
  can, so `test_an_under_18_refusal_takes_a_signal_written_before_the_dob` holds it.
- [x] **Commit:** `feat(safety): fraud scoring and auto-freeze [T-9.2]`
  **Broken once each** (`uv run python -m tests.break_guards t92-`): twenty-seven cases, each
  red in 1 of 1, every file restored and none differing by SHA-256 after (`out/t-9.2-break-guards-run2.log`,
  and `-run3.log` for `t92-16`). The first run (`out/t-9.2-break-guards.log`) found two cases
  green: `t92-09`, whose guard (freeze on the way in) was redundant and hid a hole, so the rule
  became D-902's "whenever the band is freeze" and `t92-27` holds it; and `t92-16`, whose test
  never signed in after its refreshes, so it never asked for the count it guarded.

### T-9.3 · Refund when a partner is banned
**Dropped, 4 October 2026 (D-230): nothing is returned on a ban.** Kept below as it was planned;
`refund_banned_partner` stays unused, never repurposed.
- [-] **Needs:** T-9.2, T-5.1, and **P-63**: one ban credits several men in one transaction, and nothing yet makes their wallets lock in `user_id` order (D-077)
- [-] On ban: find Velas other users spent on this person in the last 7 days (threads opened with them, voice unlocks, album requests) → `wallet.credit(refund_banned_partner)` each, idempotent per ref, notify. The 7 days is also stated on `/refunds` (D-050): change both together.
- [-] **Commit:** `feat(safety): refunds for banned partners [T-9.3]`

### T-9.4 · Notifications
- [x] **Needs:** T-7.4
- **"Only if not connected" needs presence across instances** (T-7.4, 8 October 2026): each
  instance's hub knows only its own sockets (`Hub.count`), so this task records who is connected,
  for example a Redis key per user refreshed while a socket lives, and reads that.
- [ ] VAPID keys; `POST/DELETE /push/subscriptions`; `send_push` worker (drop subscriptions on 404/410); notification prefs; in-app `notifications` list. Kinds: match, message (only if not connected), like, knot requested/accepted, thread expiring, album decided, low balance.
  **Open: no VAPID keys exist, because push is off until D-857 and P-755.** Everything else on this
  line is built and tested: the subscriptions, the sender, the settings, the list and every kind
  (CI run 37867167873 on `340ce05`). No pair is set and `PUSH_PROVIDER = "off"` in every Fly
  file until the founder gives D-857 in their own words and P-755 sets the pair.
- [x] **A paused account is sent nothing** (T-9.6): no push and no in-app notification while
  `paused`. A deleted one has no push subscriptions left (`DELETE /me` drops them).
- [x] **P-550: gifts.** T-8.9 writes a `gift` notification (`{gift_send_id, gift_id, user_id}`)
  for every gift received, and no setting names gifts: decide which one governs its push, and add
  `gift` to the kinds above.
- [x] **From T-8.10: a `gift` notification opens the sender's profile,** `/people/{user_id}`:
  the payload's `user_id` is the sender's (T-8.9). Moved here from T-8.10's line (the founder, 9
  October 2026), since the in-app list and `notificationclick` are this task's.
  **Built after T-9.4 landed** (it had sent a gift to `/you`, missing this line, which arrived with
  T-8.10 during the build): `ROUTES.gift` is `/people/{user_id}`, held by `push-worker.test.ts`
  and `NotificationsScreen.test.tsx`, and broken once (`t94-web-09`). Across a block the row stays
  hidden, as every row about that person is (P-760, D-858, its test).
- [x] **P-631: album requests.** T-8.4 tells her nothing when someone asks to see her album (D-732):
  add an `album.requested` event and an `album_request` notification, and the setting that
  governs its push.
- [x] Web: Serwist service worker (push + notificationclick → open the right route), permission asked **after the first match**, not on load; generic-text option; iOS note when not installed.
  **Built without Serwist** (D-859), and tested in vitest and by eight web breaks. With push off
  it offers nothing yet (P-755), and no real device has received a push (P-753).
- [x] Update `/privacy` (T-2.2) to say what push notifications carry and who delivers them.
- **Built as D-850 to D-859** (the founder's answers to T-9.4's plan, 9 October 2026, on the
  advisor's recommendation, relayed):
  - **The kinds and their settings:** `notify()` is the one writer, for an active account only.
    Gifts and the album have settings of their own, `gift` and `album` (D-851, closing P-550 and
    P-631, with `album.requested`).
  - **Push-only kinds:** a message and a like write no in-app row (D-852).
  - **Low balance:** `low_balance` fires once per crossing of `low_balance_velas`, 10 (D-853).
  - **Presence:** read as `PUBSUB NUMSUB user:{id}` (D-854), not a key per user.
  - **Sending:** pushes wait in `push_outbox` and go on a wake and in the worker's minute, never
    as ARQ jobs (D-850).
  - **Subscriptions** name a known push service or are refused (D-855).
  - **VAPID:** two Fly secrets plus `GET /push/key` (D-856).
  - **No Serwist:** `/sw.js` comes from a route handler, and `/you/notifications` and
    `/notifications` are built from existing parts (D-859).
  - **Blocks (P-760, from T-9.1's session):** the list and the sender leave out anything about
    someone blocked either way (D-858).
  - **Open (D-857):** pushes leave India through the browser's maker, awaiting the founder's own
    words.
  - **Proved:** the encryption is RFC 8291's example byte for byte. **Broken once each** (`uv run
    python -m tests.break_guards t94-`): thirty-seven cases, and the web's eight.
  - **Landed with push off everywhere** (the founder, 9 October 2026): `PUSH_PROVIDER = "off"` in
    every Fly file, a value added for it (D-856, amended). No keys are needed, no key is served,
    and nothing is sent. In-app notifications work. On again: P-755. No real push service has yet
    accepted one of ours: P-753.
- [x] **Commit:** `feat(notifications): web push and in-app list [T-9.4]` (landed as two: the API's,
  then `feat(web): notifications and the service worker [T-9.4]`: `0e968e2` and `340ce05`, CI run
  37867167873)

### T-9.5 · Admin panel
- [x] **Needs:** T-9.2
- **A ban or a freeze closes the sockets** (T-7.4, D-557): `events.close_sockets(session,
  user_id)` in the transaction that sets it, as sign-out does.
  **Built:** `admin.panel._freeze` and `_ban` call `auth.service.sign_out_everywhere`, which does
  both (`test_staff_freeze_signs_out_closes_sockets_and_audits`, and the ban's).
- **The plan, approved by the founder, 14 and 16 October 2026:** his answers to its ten questions
  in T-9.5's brief (D-920 to D-929), and to its five, on the advisor's recommendation (Claude, in a
  separate chat), relayed: `NOT VALID` for the ref rule, an unbanned account that had asked to go
  back to `deleted`, a ban lifted in place and never deleted, the face photo kept out, and an
  `Idempotency-Key` on grants. Built in four commits: the ledger, the API, the web, the docs.
- [x] API: all `/admin/*` routes in `04-API.md`, `require_role(moderator)`; Vela grants and bans `admin` only; every call writes `audit_log`; viewing messages of a thread logs who looked and why (reason required).
  **Built (D-920 to D-924):** `app/modules/admin/panel.py` behind `router.py`, its own module since
  `admin.service` is imported by scoring and payments; every route declares its own `require_role`
  and writes `audit_log`, reads included, and `test_admin_roles.py` reads the app's OpenAPI so a new
  `/v1/admin` route without one fails. Added beyond 04-API's list: `GET /admin/freezes` (P-800).
- [x] **Vela grants (`/admin/users/{id}/credits`):** a grant can't reach a woman, because the database refuses it (D-076). A negative `delta`, an admin correction, has no ledger reason today, since `admin_grant` is a credit (D-077). Add a debit reason for it here, an enum addition. **Make `admin_grant`'s ref required here:** it is optional (T-5.1) only while its callers are the seed and `make_user`; an admin's grant names the `audit_log` row its call writes, or it is a grant nobody can trace. That is a migration on `ck_ledger_entries_ref_required` and a change to `wallet/rules.py`, which the seed and `make_user` must then follow (at the direction of the advisor directing Sprint 5, 3 October 2026).
  **Built (D-923):** `admin_correction` (migrations `eb2e5b3a5cc8`, `688032b1dc7a`), every reason
  naming its ref, `NOT VALID` (`7a758777affd`); the seed's grant names the system user's
  `seed.grant` row and leaves an earlier one as it is, the tests' through `tests/grants.py`. The
  route takes an `Idempotency-Key`. The correction's ledger audit, as T-9.9 reads one, is
  `test_a_correction_is_exactly_one_admin_correction_and_the_ledger_reconciles` (critical).
- [x] Web `/admin`: metrics tiles, report queue with SLA timer (24 h), user search + detail (photos, reports, fraud signals, ledger, threads), moderation queue (approve/reject), actions with confirmation dialogs, audit log.
  **Built (D-920):** `src/app/admin/` and `src/components/admin/`, from existing parts only, 760 px;
  confirmations are sheets that ask why. `/admin` is one of `NONCE_ROUTES` (D-541, amended).
- [x] **`GET /admin/threads/{id}/messages` shows what either person cleared** (T-7.8, D-006): it
  reads `messages` by `thread_id` with no viewer's `cleared_at`, as 04-API's "includes `body_raw` +
  cleared" says; T-7.8's test reads the same way and finds every message after a clearing.
  **Built (D-924):** `test_every_message_shows_whatever_either_person_cleared`.
- [x] **A moderator's approve or reject changes a profile's completeness (P-210):** call `onboarding.service.refresh_completeness` in the same transaction, under the user's row lock, as `photos.service._record` and `delete_photo` do, or discovery ranks that profile by a stale number (D-032).
  **Built (D-925):** `photos.service.decide_by_staff`, under the owner's row lock;
  `test_approving_a_public_photo_publishes_it_and_lifts_completeness` and the takedown's.
- [x] Web `/admin` renders only for `role in (moderator, admin)`, read through `useMe()`; anyone else
  gets the 404 page — replacing T-1.22's `next dev`-only gate (from P-30). **This gate is UX, not
  protection:** anyone can download the page's JavaScript, and the Next.js server never sees a
  session there (D-024). Every `/admin/*` endpoint must carry its own `require_role(...)`; the
  API's role check is the only thing guarding admin data.
  **Built:** `AdminGate` (`AdminGate.test.tsx`), and P-30's half here.
- [x] **User search finds a phone number only in full, never by prefix or part** (D-061). Numbers are
  stored as a keyed hash and an encrypted copy, so search normalises and hashes the number typed and
  matches it exactly. "Whose number ends in 4321?" has no answer, by design: support asks for the
  whole number.
  **Built (D-927):** `test_part_of_a_number_finds_nobody`.
- [x] **Revisit D-101's possible-minor threshold, 0.35, from real scores** (the founder, 4
  October 2026). It was chosen for an asymmetry, not from data: nobody had seen how
  Sightengine's `face-age` scores real photos. This is where real scores are first seen (the
  photo's `moderation` column keeps every photo's minor score, below the threshold too).
  Report what they show; the founder decides whether 0.35 moves, recorded on D-101.
  **Read 16 October 2026 (on D-101):** staging only, production has no deployment: 3 photos carry
  a score, 0.01, 0.01 and 0.78 (rejected). Too few to move anything; the founder's to decide.
- [x] **An erased account is still found by its number** (T-9.6, D-500): search hashes the number
  typed and matches `users.phone_hash`, which an erased row keeps (`ix_users_phone_hash`), so
  support sees it as erased, with its reports. Its row can't leave `deleted`
  (`ck_users_anonymised_is_deleted`): ban its number through `banned_identities` only. And
  **P-401**: what a ban landing during a deletion's 29 days does to the erasure.
  **Built (D-922, D-929):** an erased account is banned and unbanned by its number alone; a ban
  during the 29 days stops the erasure and keeps the data, and lifting it returns the account to
  `deleted`.
- [x] **The claims screen (P-480):** T-8.3's queue and resolution (`/admin/refund-requests`,
  D-580 to D-582), admin only, each action behind a confirmation.
  **Built:** `ClaimQueue`, `/admin/claims`.
- [x] **Freezes (T-9.2, D-902, D-906):** an unfreeze before the first real user: a screen over
  `safety.scoring.unfreeze`, the tool's own path, which resets the score and its `counted_from`
  (an unfreeze that leaves them would be frozen again at the next sweep). The automatic freezes
  listed, and P-800. **The system user** (D-905, `SYSTEM_USER_ID`) shown as "System" in the audit
  log and left out of user search.
  **Built (D-922, D-928):** an admin's unfreeze is `safety.scoring.unfreeze`; `/admin/freezes`
  marks the automatic ones; the push is filed as P-820. The system user is "System" in the log
  and in no list.
- [x] **Commit:** `feat(admin): moderation panel [T-9.5]`

### T-9.6 · Settings and data rights
- [x] **Needs:** T-3.5
- [x] Hide profile, hide age, hide distance, show kudos; pause (hidden + no notifications); export (JSON of own data, generated by worker, signed link valid 24 h); delete (status `deleted`, profile hidden immediately, anonymised after 30 days by cron; payments and ledger kept, detached from identity). What's erased and kept follows D-051, which `/privacy` states: messages stay in the other person's chat as from "Deleted account" and as moderation records, and a hashed phone number is kept so deletion can't escape a ban. Change the page with the code.
- [x] Two things T-3.3 and T-3.7 left here: what a `deleted` account gets at sign-in (`FORBIDDEN` until now, D-067), and whether and how a username can change after onboarding (locked until now, D-068; D-001's `/@username` links depend on it).
- [x] **The welcome hash survives the anonymisation** (T-8.11, D-470, P-371): a number that
  received welcome Velas never gets them again, on any later account. T-8.11's test (grant,
  delete, sign up again after 30 days, no second grant) stands in for this task's anonymisation
  until it exists; run it through the real one here.
  **Built here as far as it can be before T-8.11 (8 October 2026):** T-8.11's table doesn't exist
  yet, so the erasure keeps it by name, `welcome_grants` in `KEPT_WHEN_BUILT` (D-503), and
  `test_the_welcome_hash_is_kept_by_name_before_it_exists` holds that. The erasure touches only
  the tables `ERASED` lists, and `banned_identities` and the erased row's own `phone_hash` stay
  too. The grant-delete-sign-up test is T-8.11's to run through the real erasure (its pointer).
- [x] **Commit:** `feat(settings): privacy and data rights [T-9.6]`

### T-9.7 · PWA
- [x] **Needs:** T-9.4
- [x] Web manifest (name, icons 192/512/maskable, theme colour from tokens, `display: standalone`), install prompt banner (Android `beforeinstallprompt`; iOS instructions), offline shell page.
- **Built as D-1040 to D-1043** (the founder's answers to T-9.7's plan, 19 October 2026, on the
  advisor's recommendation, relayed). T-9.4's push box is still open (push is off until P-755);
  nothing here needs push, so the founder let this start on it.
  - **One worker, no cache** (D-1040): `/sw.js` stays the only service worker and gains a `fetch`
    handler for this site's page loads alone, network first through navigation preload; only a
    network failure gets the offline page, which the worker builds from `offline-page.ts` (the
    lock screen's layout on `--chrome`, `tokens.css` embedded, no script, a CSP of its own by
    hash). Nothing is ever cached. No Serwist, closing D-859's question.
  - **Registered on every page** (D-1041), the landing page included, by `ServiceWorkerRegistrar`
    in the root layout through `push.register()`. A broken worker can't stick on a phone:
    `/sw.js` is `no-cache` and both registrations pass `updateViaCache: "none"`, each tested.
  - **The banner** (D-1042): the prototype's strip, first on every `(app)` screen, on touch-first
    devices only; Android's held `beforeinstallprompt`, or on an iPhone the Share steps. Closed
    once, closed in that browser.
  - **The manifest** (D-1043): `id` `/`, `start_url` `/discover`, both colours `--chrome`, three
    icons rendered by `web/scripts/render-icons.mts` (08-DESIGN §7); the maskable V is held
    inside the centre 80% pixel by pixel.
  - **Broken once each** (`node scripts/break-guards.mts t97-web`, `out/t97-web-breaks.log`): ten
    cases, 10 of 10 red, the tree byte for byte as it was. `e2e/pwa.spec.ts`: the manifest and
    icons served, the one worker registered with `updateViaCache: "none"`, and the offline page
    shown with the browser offline, with no CSP violation.
  - **Not seen yet:** an install on a real phone (P-940).
- [x] **Commit:** `feat(web): installable pwa [T-9.7]`

### T-9.8 · You tab complete
- [x] **Needs:** T-9.6, T-8.8
- [x] Profile summary + edit, verification status, kudos, knots list with untie, blocked list with unblock, reports filed, cleared chats with restore, settings rows, lock now, log out.
- [x] **The settings screen** (T-9.6's routes): the five switches through `PATCH /me/settings`,
  pause and resume, a copy of your data (`POST`/`GET /me/export`, with the link while it is
  ready, 24 hours), and delete. **The delete confirmation shows his balance in plain words before
  he confirms** (D-504): the number from the API, `Me.balance`, never written into the copy, and
  that Velas left are lost at the erasure unless he signs in again within 29 days. After the
  delete, the web is signed out (`SESSION_REVOKED`).
- **Built as D-910 to D-913** (the founder's answers to T-9.8's plan, 9 October 2026, on the
  advisor's recommendation, relayed; D-910 the founder's own):
  - **Two read endpoints, their own commit:** `GET /threads/cleared` (P-510, D-912), restored one
    at a time, no "Restore all"; and `GET /reports`, the reports you filed, with no status and,
    across a block either way, the name alone (D-911), served by a new index on
    `(reporter_id, created_at desc)` (migration `086fa0402d0d`).
  - **The badge follows the main photo** (D-910, amending D-393): a new main photo, or a reorder,
    carries none until it matches the selfie; the face photo can't be swapped once matched
    (T-4.12's refusal, now tested with the badge). `badge_of` is the one rule.
  - **Found and fixed:** the unread count's clearing subquery took every clearing the viewer
    had, so two clearings and an unread message made `GET /threads` a 500 on `main` (D-912).
  - **The web from existing parts** (D-913): `/you`, `/you/settings` (the five switches, P-447's
    `public_link` among them; pause; a copy of your data; delete with his balance, D-504),
    `/you/edit`, and `/you/photos` (the photos step's grid, moved into `PhotoGrid`). The block
    sheet says "You can undo this from the You tab" (P-762). No invite card (D-840).
  - **Broken once each** (`uv run python -m tests.break_guards t98- t412-17 t412-18 t62-11
    t72-01`, `out/t98-break-guards.log`): eleven new cases and four re-anchored to the new code,
    15 of 15 red, no file differing by SHA-256 after.
    The web's twelve (`node scripts/break-guards.mts t98-web`, `out/t98-web-breaks.log`): 12 of
    12 red, the tree byte for byte as it was.
- [x] **Commit:** `feat(web): you tab [T-9.8]`

### T-9.9 · Ledger audit
- [x] **Needs:** everything above
  **Read 14 October 2026:** of the tasks above, only T-9.5 blocked a paid action's test (its
  `admin_correction`, which the brief added); it landed first (`59ab5e0`), so its row is here and
  P-840 wasn't needed. REL-1, T-3.14's staging check, T-4.11, T-6.5's 60 fps, T-7.13, T-9.4's push
  box and T-9.7 are open and block none of these tests.
- [x] One test per paid action (thread open, dm, re-open, voice unlock, album, super like, liked-you reveal, and D-098's Extend and each private message after the first): man → exactly one ledger entry with the right reason and amount; woman → zero entries; insufficient → nothing created.
  **Built (D-940):** `tests/modules/wallet/test_paid_actions.py`, every debit of Velas: the nine
  above, his first message where she opened the Thread (the open's and the re-open's price, by
  `POST /threads/{id}/messages`), `gift` and `admin_correction` (the founder, 14 and 18 October
  2026), 13 rows × 3 tests, prices as the plan's literals. A guard holds the table to
  `wallet/rules.py`'s debits exactly, `purchase_reversal` exempt by name (D-520).
- [x] Reconciliation test: for every user, `wallets.balance == sum(ledger.delta)`. Also as a daily cron that alerts on mismatch.
  **Built (D-940):** `tests/modules/wallet/test_reconcile.py` (the global check `critical`, and a
  mismatch each way, a balance with no rows, rows with no wallet, inside the rolled-back
  transaction); `reconcile_ledger` at 03:00 UTC (08:30 IST), each mismatch a
  `wallet.ledger_mismatch` line at error level, which T-9.12 forwards to Sentry.
  **Broken once each** (`uv run python -m tests.break_guards t99-`, `out/t99-break-guards.log`):
  nine cases, 9 of 9 red, no file differing by SHA-256 after.
- [x] **Commit:** `test(wallet): paid action audit and reconciliation [T-9.9]`

### T-9.10 · Performance pass
- [x] **Needs:** T-9.8
- [ ] On the ₹10k test phone over throttled 4G: first load of `/discover` < 3 s, swipe at 60 fps, JS bundle for `(app)` < 250 KB gzipped, images served at the right size. Fix the top 3 offenders.
  **Open for the founder's reading on the test phone (P-930), and for right-sized photos
  (P-931), both before launch** (the founder, 19 October 2026, landing T-9.10). No test phone yet (P-0.9), so everything was measured on the desktop stand-in the
  founder chose (14 and 16 October 2026, D-1030): a production build in Chromium, a 412 × 915
  screen at 2.625×, CPU 4×, DevTools' own Fast 4G (the pass/fail) and Slow 4G (the stress
  reading), every byte through a loopback proxy, ten cold runs of each, interleaved. Before is
  `main` at `74c9d46`, after is this branch on it, both 19 October 2026:
  - **First load of `/discover` < 3 s on Fast 4G: met on the stand-in.** The top card's photo
    shown at **1,916 to 2,100 ms** (median 1,970), from 2,908 to 3,000 ms before (median 2,932,
    one run at the line). Slow 4G: **7,216 to 7,340 ms**, from 11,868 to 11,936 ms; over 3 s by
    the HTML, about 250 KB of JS and two preflighted calls at 562 ms a round trip before any
    photo, and recorded, not passed (D-1030). Kinder than the street: the stand-in API answers
    at once and nothing is TLS (`web/bench/first-load.spec.ts`;
    `out/t-9.10-first-load-before.log`, `out/t-9.10-first-load-after.log`).
  - **JS for `(app)` < 250 KB gzipped: met, and held by CI** (`scripts/bundle-budget.mts`, the
    web job, D-1034). Every `(app)` route **194.0 to 237.1 KB** (`/discover` 224.1, `/chats/[id]`
    the largest), from 286.1 to 316.5 KB: all fourteen failed before (`out/t-9.10-budget-before.log`,
    `out/t-9.10-budget-after.log`). 1 KB is 1,000 bytes.
  - **Swipe at 60 fps: no change from T-6.5's** (`web/bench/deck-fps.spec.ts`, four sessions of
    each side interleaved, `out/t-9.10-deck-fps*.log`). The flight 57.7 to 60 fps at 4× and 57.7
    to 57.8 at 6× on both sides. **One finding:** one drag frame of 183.3 ms, in the first run of
    one of this branch's four sessions, never on `main`'s; its other frames over 25 ms per session
    5, 1, 1, 1 against `main`'s 0, 0, 1, 1. Unsettled whether the change causes it: P-932. The
    phone's own reading is still P-500's.
  - **Images at the right size: not met; P-931** (D-1030's 2× rule: a photo's natural width at
    most twice the device pixels it fills). `/discover` 1.31 to 1.42× and `/people/[id]` 1.18×
    pass; `/discover/likes` 2.71× and `/chats` **10.16×** fail: twelve 281 KB photos into 48 × 48
    avatars. Every photo is the one 1,600-pixel copy (D-092); a fix is the server's.
  - **The top three offenders, fixed** (by what they cost the Fast 4G and Slow 4G first load):
    1. **Three photos at once** where one shows: the two cards behind now ask for theirs only
       once the top card's has loaded or failed (D-1031). Photos started before the top one
       arrived: 3, now 1.
    2. **zod with every locale on every `(app)` page**, about 63 KB gzipped, from the socket's
       schemas: `zod/mini` by named imports (`src/lib/zod-mini.ts`, D-1032), and the socket's
       client fetched as the app mounts, not in the first load (D-1035, the founder's answer, 19
       October 2026, when `/discover` was still 250.9 KB).
    3. **The feed waited for `/me`**, two round trips with their preflights: on `/discover` the
       gate starts the deck's first page alongside `/me` (D-1033). The server is the guard: a
       frozen account is refused the feed (`test_a_frozen_account_is_refused_the_feed`, new) as an
       unfinished onboarding is (`ONBOARDING_INCOMPLETE`, tested since T-6.2).
  - **Broken once each:** the web's seventeen (`node scripts/break-guards.mts t910-web`,
    `out/t-9.10-web-breaks.log`), 17 of 17 red, the tree byte for byte as it was; the API's one
    (`uv run python -m tests.break_guards t910-`, `out/t-9.10-api-breaks.log`), red in 1 of 1, no
    file differing after.
- [x] **Commit:** `perf(web): mobile performance pass [T-9.10]`

### T-9.11 · Accessibility pass
- [x] **Needs:** T-9.8
- **The plan, approved by the founder, 16 October 2026,** on the advisor's recommendation
  (Claude, in a separate chat), relayed: axe through Playwright (D-960), `--accent-text` for red
  on a tint (D-961), field borders filed as P-864; and on 18 October, a local-only staff role for
  the admin walk (D-963), on conditions: the test routes' gate, staff roles only, audited,
  nothing in the bundle, and T-9.13's review.
- [x] Keyboard reachable everything, visible focus, labels on icon buttons, colour contrast AA from tokens, reduced-motion respected by the deck, screen-reader names for swipe actions.
  **Built (D-960 to D-963):** `web/e2e/a11y.spec.ts` walks every `(app)` screen as a man and as a
  woman and every admin screen as staff, on both projects: axe's WCAG 2.0 and 2.1 A and AA rules
  find nothing (13 to 25 rules passing a screen), and a Tab walk from the top reaches every
  control a pointer can, each with a ring (5 to 45 stops a screen), the skip link first. Its list
  is held to the page files (`a11y-routes.test.ts`). One ring, `:focus-visible` in `globals.css`;
  a skip link; toasts held while focused; the profile's photos a Tab stop; the swipe buttons
  naming who is on top, the price from `/prices`, and each swipe said. Contrast from the tokens in
  `contrast.test.ts`; the deck under reduced motion by its effect, dragged: it moves, never tilts.
  `make e2e` 44 of 44, the walk 3.6 min a project (`out/t911-make-e2e.log`).
  **Broken once each:** the API's five (`uv run python -m tests.break_guards t911-`,
  `out/t911-break-guards-api.log`), 5 of 5 red; the web's eleven (`node scripts/break-guards.mts
  t911-web`, `out/t911-web-breaks.log`), 11 of 11 red; and three in the browser, rebuilt each
  time, each red at its own check and the file restored by SHA-256: the ring gone (no ring on the
  shell's links), `--accent-text` back to `--accent` (axe's `color-contrast` on his chats), and
  the tilt under reduced motion (3.85° where 0 was expected)
  (`out/t911-e2e-break-*.log`). Not proved: what a real screen reader says (P-860).
- [x] **Commit:** `a11y(web): accessibility pass [T-9.11]`

### T-9.12 · Observability
- [x] **Needs:** T-1.22, and a **Sentry account** — not created yet: P-0.6 was ticked with it left to this task
  **The account exists** (the founder, 16 October 2026): EU region, the free Developer plan (D-1000).
- [ ] Sentry in api, worker, web (release = git sha). Alerts: 5xx > 1% for 5 min, webhook signature failures, any job failing 3×, ledger reconciliation mismatch, queue depth > 1,000. Uptime check on `/readyz`.
  **Built, not yet seen working; unticked until it is.** The SDKs, the release from `GIT_SHA`
  (D-1000, D-1001), every alert line (D-1002, the 5xx as one alert per issue: the free plan has no
  rate alert) and queue depth (D-1004) are code, tested by planting what must never leave
  (`tests/core/test_observability.py`, `web/src/lib/sentry.test.ts`). The alert and the uptime
  monitor on staging's `/readyz`, the Mumbai VM since P-49, exist only once the founder runs
  `scripts/sentry-alerts --apply`, proved so far against a fake of Sentry's API only (D-1005). Tick
  when `--check` exits 0 and `infra/OBSERVABILITY.md` §4's staging check is done: the release in
  both projects, a test error from each component, and its email.
- [x] Route D-066's OTP warning, logged at half of `otp_sms_daily_cap`, to the alert channel: until this task it lands only in Fly's logs, which nobody reads.
  `otp_daily_cap_half_used` is one of the three warnings sent (`ALERTING_WARNINGS`, D-1002), held by `test_each_alerting_warning_is_sent` against the plan's literals.
- [x] Route D-090's final failure to the alert channel: a minor's files that couldn't be deleted after three tries, logged at error level with the `banned_identities` id. Until this task that log line is all there is, which D-078 says is not enough.
  `storage.delete_failed`, at error level, goes to Sentry with the id and nothing else (D-1002, D-1003); `test_each_alerting_error_is_an_issue_of_its_own` holds it.
- [x] **Widen the CSP here, and wire its reporting (D-059):** `connect-src` for Sentry's ingest host, and the CSP's reports (`report-to`, with `report-uri` as the fallback) sent to Sentry's security endpoint. Until then the enforced policy is silent: a violation in production stays invisible until a user complains.
  On builds that report, every page (`security-headers.ts`, exactly these additions, `security-headers.test.ts`). In Chromium against a staging build the SDK's envelope went out unblocked and a planted image raised `img-src` (`out/t9.12-web-bundle-and-browser.log`); the report's arrival at Sentry is the staging check's (`infra/OBSERVABILITY.md` §4), since Chrome sends it outside the page.
- [x] **Commit:** `chore(ops): error tracking and alerts [T-9.12]`

### T-9.13 · Security review
- [ ] **Needs:** T-9.9
- [ ] **Pillow's pinned version against its CVEs** (D-092): an image parser reading hostile input;
  update it if any has landed since it was pinned.
- [ ] **The local-only test routes, D-963's role route first** (T-9.11, at the founder's
  direction, 18 October 2026): `POST /v1/test/users/{id}/role` makes anyone an admin, so confirm
  every `/v1/test` route is still a 404 in the deployed image, from outside, on staging and
  production (not only `test_make_staff.py`'s settings), that none is in OpenAPI, and that nothing
  in the web bundle names one (`no-test-routes.test.ts` reads the source, not the build).
- [ ] Walk the security checklist in `07-CHECKLISTS.md` line by line; fix findings; run Claude Code `/security-review` on the branch; commission the external review of auth + wallet + payments (budget line in cost doc).
- [ ] **Commit:** `fix(security): review findings [T-9.13]`

### T-9.14 · Backups and restore drill
- [ ] **Needs:** REL-1, which creates production's database (moved from T-2.6 on 3 October 2026)
- [ ] Confirm Supabase PITR on production; restore last night's backup into a scratch project and run the reconciliation query against it. Document the steps in `docs/runbook.md`.
- [ ] **Commit:** `docs(ops): backup and restore runbook [T-9.14]`

### T-9.15 · Go live
- [ ] **Needs:** T-9.13, T-9.14, P-0.5, P-0.7, P-0.8; **P-80**: no query value in the API's database errors (rule 15); **P-81**: the lawyer's answer on a possible minor's photo that is also sexual (D-093); **P-73**: who the two unidentified staging accounts are; **P-74** and **P-76**: a photo rejected after the person left the photos step reaches them, and an upload that never arrived stops showing as "Checking…" (found building T-4.6); **P-72**: a human path for repeated possible-minor flags (D-093); **P-66**: until staging has a Firebase project of its own, its sign-ins land in production's user pool, which is not acceptable after launch (the founder, 3 October 2026, on T-3.14); **P-0.18**: the billing account converted from its free trial, after App Check (P-68), since after launch the trial's end is an outage with no warning (the founder, 3 October 2026); and **P-68**: App Check enforced on Authentication and proved by its effect, before the site is public for sign-in (the founder, 4 October 2026); **P-162**: whether one matching photo may carry a whole profile (T-4.5); and **P-163**: the founder able to undo a selfie decision his review finds wrong, since until then a woman he marks "different" stays live with the badge (T-4.5, D-264)
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
- [ ] **T-10.4** Price test: variant A (₹1,500 / 25 Velas) vs B (₹999 / 25) assigned 50/50; compare revenue per paying man after 3 weeks. **Both variants are gone** (D-099, D-250): D-099's packs replaced A, and T-5.2 retired B, `entry-25`, since ₹999 for 25 is ₹40 a Vela, below the new entry pack's ₹50. This task proposes a fresh test against D-099's packs when there are users to test on.
- [ ] **T-10.7** First-thread-free test (risk R1 in `09-RESEARCH.md`): half of new men get their first thread free. Measure paying conversion, threads per man, and revenue per man — not just the free-thread take-up.
  **Changed 8 October 2026 (D-470):** every new man now gets 5 Velas at sign-up, one Thread's
  worth (T-8.11), so this task tests that grant, not a free Thread. What it compares, now that
  every man gets it, is this task's to propose.
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
The number comes from the session's own block, given in its brief, from P-100 up (CLAUDE.md,
"P- and D-numbers: a block per session"); never from scanning branches.

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
  **Deadline passed, 8 October 2026** (the audit, P-490): T-1.22 deployed staging on 1 October 2026.
- [x] P-07 · Harness mode for concurrency tests — the `db` fixture is one session inside one
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
  **Settled by T-5.4, 4 October 2026:** fifty committed transactions on fifty connections
  (`tests/modules/wallet/test_concurrency.py`), on fresh men, never deleted, through the harness
  `tests/modules/wallet/races.py`.
- [ ] P-08 · `TEST_REDIS_URL` override — `TEST_DATABASE_URL` can be overridden but the test Redis
  is fixed at `127.0.0.1:6379/1`. If T-1.20's CI runs Redis anywhere else, the harness reports the
  stack unreachable and CI hard-fails by design. Add the override alongside T-1.20. Found in review
  of T-1.5.
  **Narrower since P-55:** each run's Redis database is its slot's, 2 to 15, so runs no longer share
  one; the host is still fixed at `127.0.0.1:6379`, which is where CI runs Redis.
- [x] P-09 · Run gitleaks in CI — the pre-commit hook only protects clones that ran `make hooks`,
  and `git commit --no-verify` skips it. T-1.20's CI steps list ruff, mypy and pytest but not
  gitleaks, so nothing server-side enforces checklist E's "no secrets in repo". Add a
  `gitleaks git` step to T-1.20's `api` job. Found in review of T-1.6.
  **Moved:** now a step in T-1.20 — tick this with T-1.20.
  **Ticked 8 October 2026 (the audit, P-490):** T-1.20's step from it is ticked, and T-1.20 landed
  (`2d65eba`); `ci.yml`'s `api` job runs gitleaks over the full history.
- [x] P-10 · Hooks must work from GUI git clients — the ruff and mypy hooks call `uv` by name. VS
  Code's Source Control panel (which the user commits from) and other GUI clients run hooks
  without the shell profile, so `uv` may not be on `PATH` and every commit fails. Resolve `uv`
  robustly (absolute path or a wrapper that locates it) and test a commit from VS Code. Found in
  review of T-1.6.
  **Moved:** now a step in T-1.20 — tick this with T-1.20.
  **Ticked 8 October 2026 (the audit, P-490):** T-1.20's step from it is ticked, and T-1.20 landed
  (`2d65eba`); every hook that needs `uv` or `pnpm` starts through `scripts/with-tools`
  (`.pre-commit-config.yaml`).
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
  **T-7.9 (8 October 2026):** `duration_s` is bounded 1 to 60 by the API and tested, and the length
  stored is the server's measure (D-620); `body_raw` and both CHECKs stay open (the founder).
- [x] P-16 · Decide whether unblocking keeps history — `blocks` is one row per pair with no
  history, so unless T-9.1 designs otherwise, unblock is a `DELETE` and the fact that A blocked B is
  gone. Rule 12's explicit list doesn't name blocks, but its principle does ("nothing is hard-deleted
  that moderation may need"), and "blocked by many people" is a fraud and moderation signal. Options:
  soft-unblock (`unblocked_at`, primary key replaced by a partial unique index) or accept the loss.
  Needs a new migration (T-1.11 is merged). **Before T-9.1.** Found in review of T-1.11.
  **Placed 8 October 2026 (the audit, P-490):** on T-9.1's Needs line.
  **Done 9 October 2026 (T-9.1, D-860):** soft-unblock, the founder's answer: `unblocked_at`, the
  pair's key replaced by `uq_blocks_active`, migration `4889c586aa2c`.
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
- [x] P-20 · Audit automated actions as a system user — ruled in T-1.13: `audit_log.actor_id` is
  NOT NULL, because null could not tell "the system did it" from "a bug forgot to set it", and the
  system user is created when auto-freeze first needs it, by T-9.2. T-9.2's text says neither that
  auto-freeze writes `audit_log` nor that the user must exist; the ruling lives only in 03-SCHEMA §8
  and the `AuditLogEntry` docstring. T-9.2 adds a data migration creating the user — it must never
  log in or appear anywhere users are listed — and writes each automated freeze to `audit_log` as
  it. **Fold into T-9.2.** Found in review of T-1.13.
  **Built in T-9.2 (D-905), 9 October 2026:** migration `4800f0e8d5a9`, `admin.service.SYSTEM_USER_ID`;
  every automatic band change and freeze is written as it. Tick with T-9.2's `/done`.
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
- [x] P-23 · Define what a variant-B man sees in `GET /packs` (T-8.1) — T-1.14 seeds variant B as
  one row, `entry-25` (25 Velas, ₹999). Read literally, "active packs for the user's price-test
  variant" gives a B user a one-pack store. What D-005 describes is A's ladder with the entry pack
  in place of `pack-25`. Decide in T-8.1, with a test that B sees four packs. Found during T-1.14.
  **Done (T-8.1, D-480, the founder, 8 October 2026):** B is shown A's four packs until T-10.4,
  by an allowlist (`SHOWN_AS`); `test_each_variant_sees_d099s_four_with_the_first_purchase_bonus[B]`
  is the test, and no man is ever shown an empty store.
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
- [x] P-30 · Keep `/admin` off the public internet until it is gated. **Due before T-1.22.**

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
  **Deadline passed, 8 October 2026** (the audit, P-490): T-6.2 landed on Postgres 16.
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
- [x] P-38 · Seed Phagwara's areas, replacing Bengaluru's. **Due before T-4.10** (on its Needs
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

  **Done, 5 October 2026:** migration `bc589ac265c2` deletes Bengaluru's 40 and inserts 17 Phagwara
  areas; its downgrade puts the 40 back from its own copy. Each direction first counts the profiles
  in the areas it would remove, with the delete's own condition, and stops with a message naming
  the fix (`AreasInUse`). **The 17**, drafted by Claude from OpenStreetMap (Overpass and Nominatim,
  read that day), each point a place inside the locality, not a measured centre:
  - In town, where OSM names a locality in an address or a building: Guru Hargobind Nagar, Model
    Town, Banga Road, Sarai Road, Satnampura, Bhagatpura, Chahal Nagar, Sukhchain Nagar, Hadiabad.
  - Around LPU: Law Gate, LPU, Maheru, Chaheru.
  - Villages: OSM's village and hamlet points within 3 km of its point for the town (the town is
    about 20 km²): Guru Nanak Nagar, Chachoki, Ghauspur, Bhullarai. Phagwara only, Jalandhar not
    (P-190), at the direction of the advisor (Claude, in a separate chat).
  - **Left out:** Urban Estate, Mehli Gate, Thapar Colony, Bazar Sarafan, Prem Nagar and Kotrani,
    which no source could place; Patel Nagar, Subhash Nagar and Green Valley, within a few hundred
    metres of an area already in; Tibbi, whose OSM point is 1.1 km from the bus stand OSM addresses
    as Tibbi; Hoshiarpur Road, a road whose points spread 3 km; villages 3 to 4.5 km out (Thakarki,
    Khothran, Bhanoki, Bazidwal, Mehtan, Mehli, Khalwara, Palahi, Birk).
  - **The founder's review: none of the 17 had been reviewed when this landed,** so every row
    says "not yet reviewed". He lives in Phagwara but can't vouch for twenty localities street by
    street, so whatever he can't confirm stays marked that way (the advisor's direction). His
    review, and any correction, is P-191: a new migration, never an edit of this one (rule 11).

  The seed moved with them: `AREA_CITY` is Phagwara, each prototype neighbourhood maps to one
  Phagwara area, and Ananya moves to Chachoki. `SCATTER_RADIUS_M` drops from 750 m to 250 m: the
  two closest centroids are 510 m apart (Guru Hargobind Nagar and Model Town), and a test reads that
  gap from the database and holds the radius under half of it. At 250 m, four people in one area
  put two of them 89 m apart, under the seed's 100 m; hence Ananya. Four about texts were rewritten
  for Phagwara, drafted by Claude for the founder to review: Ananya's, Sanya's and Siddharth's, and
  Ishita's metro, which Phagwara doesn't have (rewriting hers was the advisor's call).
  **P-27 stays open, undecided:** the advisor kept it out of tonight's task, as forty-five minutes
  T-4.10 doesn't need; the catalogue is the founder's to reconsider. Proven by eleven breaking cases
  (`tests/break_guards.py`, `p38-`), each red for its own reason.
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
- [x] P-47 · Give `app_config` its 60-second cache. **With T-6.4**, the first hot path to read a
  setting (the men's daily swipe limit, on every swipe). Worst case without it: a database read
  per request for a value that changes a few times a year. T-3.2's reader
  (`admin.service.config_int`) reads fresh, on purpose for now: its one caller, OTP send's daily
  cap, is rate-limited, and fresh means a lowered cap applies at once. A cache must be per app
  (`app.state`), not per process, or tests that tune a setting would read another test's value.
  Found in T-3.2.
  **Done, 8 October 2026, on T-6.4's branch:** `admin.service.ConfigCache`, one per app
  (`app.state.config_cache`), read through `config_int(..., cache=)`: the men's daily swipe cap and
  discovery's radius use it; OTP send's daily cap still reads fresh, on purpose. A missing or
  mistyped row is never cached. `tests/modules/admin/test_config_cache.py` holds it; breaking runs
  `p47-01` to `p47-04` each red.
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
- [x] P-49 · Colocate the API and the database, and decide which city. **Before Sprint 6**, whose
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
  - **And staging's worker** (D-095, 4 October 2026): T-4.4 deploys it to Fly now, so the move takes
    two apps, not one: `infra/fly.worker.toml`, its job in `deploy.yml`, its secrets (the same four
    keys, R2's and Sightengine's), and its line in `infra/STAGING.md`'s connection budget.

  Found reviewing T-3.2 to T-3.5, at the direction of the advisor directing them (Claude, in a
  separate chat), who added option B and the residency question.
  **Deadline missed, 8 October 2026 (the audit, P-490):** Sprint 6 is landing with the split in
  place (T-6.2, T-6.3, T-6.4). **Now before REL-1, measured on staging** (the advisor's
  recommendation; the founder to confirm). Nothing above changes.
  **Decided and under way, 16 to 18 October 2026 (D-1020 to D-1023; the founder, on the advisor's
  recommendation, Claude in a separate chat, relayed):** Option A, both environments, on Compute
  Engine in `asia-south1`; Fly and Singapore leave entirely. Built by Claude in session block
  P-920 to P-929, D-1020 to D-1029, in steps the founder set:
  - **Done, by the founder's own commands (blocks 1 to 5, `out/`, each read by the advisor first):**
    projects `velora-ic-staging` and `velora-ic-prod` on billing account `01C4E8-84A5D8-4255F2`;
    each a custom VPC (TCP 80/443 in, 22 from IAP only, the default network and its open rules
    deleted), a static IPv4 (staging `34.47.244.114`, production `34.180.56.204`), two service
    accounts, an Artifact Registry and 16 Secret Manager slots in Mumbai, WIF for GitHub; the VMs
    `velora-api-staging` (e2-small) and `velora-api-prod` (e2-medium), both reporting
    `velora-startup: ready`. Staging's 13 values moved from Fly and the Keychain, all compared equal
    by SHA-256 prefix across Secret Manager, the Keychain, Fly's API and Fly's worker; a fresh VAPID
    pair and the Sentry DSN into Secret Manager. Production's four keys and VAPID pair generated
    fresh, different from staging's; R2's from the Keychain; its database, Redis, Razorpay and
    Sightengine values not set yet (P-921).
  - **This landing:** the VM's files (`infra/gce/`), `Caddy-Client-IP` (D-1021), the deploy jobs
    beside Fly's, `roundtrip_probe`, `check-caddy-client-ip`, `gcp-secrets`. Fly's staging deploy
    is untouched and keeps running from `main` until the founder retires it.
  - **A hand-built image never reached the VM:** pushing from the founder's Mac broke twice in
    Docker Desktop's own proxy (P-924), so the first image the VM runs is CI's, from `main`.
  - **Left, in order:** the VM's first deploy from `main`; the checks from outside (Caddy's
    certificate, `Server: Caddy`, `/readyz`, the API's port closed, IPv6 to Supabase) and the
    round trips, measured with `roundtrip_probe` against this entry's estimates; the forged-header
    check on staging; then, on the founder's word, the worker swap (Fly's to 0 first, D-091) and
    `api.staging`'s DNS; the phone test; then P-920 removes Fly. Production: P-921.
  **Ticks when** staging serves from Mumbai, measured, with Fly's worker at 0; P-920 and P-921
  carry the rest.
  **The VM serves, 18 October 2026** (`main`'s `a761c9e`, deployed by CI: run 39118222247, attempt
  2, after the WIF subject was rebound, D-1022's amendment). Read from outside: Let's Encrypt's
  certificate for `api-mumbai.staging`, `/readyz` with Postgres and Redis ok, `Via: 1.1 Caddy`,
  the schema hidden, CORS for the staging web, HTTP redirected; ports 8000, 22, 5432, 6379 and
  2019 refused, only 80 and 443 answering. On the VM, by the founder's OS Login through IAP:
  Docker 29.9.1, the API healthy with no host port, the secret files root's and mode 600, the
  worker off, and Supabase's host resolving to IPv6 only. Memory 787 of 1,976 MB with the worker
  off (the API 246 MB, Caddy 16 MB). **Round trips, measured by `roundtrip_probe` inside the API's
  container, 3 runs:** Postgres `SELECT 1` on a warm connection, medians 2.3 to 3.1 ms (p95 at most
  3.4); Redis `PING` 3.2 to 3.7 ms (p95 at most 3.9); opening a connection 97 to 109 ms. **Against
  this entry's estimate of about 1 ms a round trip, 2 to 3 times higher**, unmeasured cause, likely
  the hop between Google's Mumbai and Amazon's, where Supabase and Upstash run; against Fly's 165.6
  ms and 2,865 ms to connect, 55 to 70 times lower. From the founder's Mac, 10 requests each, a new
  connection every time: `/readyz` minus `/healthz` is 0 ms on the VM (medians 199 and 199 ms)
  against 502 ms on Fly (824 and 322 ms; P-53 had 535). `/me` itself not timed: it needs a session.
  **The cutover, as the founder approved it (`out/p-49-cutover.md`, read by the advisor first):**
  a commit that makes Caddy serve `api.staging` too, stops deploying Fly's worker (once scaled to
  0, a deploy could launch it again), and adds `socket_probe` (a real WebSocket through the
  public host, its ticket never leaving the API's container); then the worker swap, Fly's to 0
  and the VM's started in one chain, memory read before anything else is tested (stop above 85%
  of 1,976 MB); then `api.staging`'s record, by the founder's hand, and the checks: Caddy's
  certificate, the smoke, a socket's `pong`, then the founder's phone test.
  **Done, 18 October 2026: staging serves from Mumbai, measured, with Fly's worker at 0.**
  - **Step 1:** the cutover commit `5ee3547`, `main`'s staging deploy run 39123650005 green in every
    job (no Fly worker job any more); Fly's worker still 1 machine; the VM's worker off.
  - **Step 2, the worker swap:** the queue empty (0 jobs) at the swap; Fly's process group `worker`
    scaled to 0 at 11:38:52 UTC (the machine destroyed, the app kept), the VM's worker started at
    11:38:59 UTC, so never two and none for 7 seconds. `worker.started` logged once, with
    `thread_clock` and `send_push`; no `Traceback` and no `minutely.failed`. Memory 1,013 MB used of
    1,976 (worker 174 MB, API 246 MB, Caddy 19 MB), under the founder's 85% stop (1,680 MB). The
    first try was refused (`scale count 0` names the default group, `app`; the app's group is
    `worker`), a pipe hid the refusal (CLAUDE.md shell trap 1), and the chain's started-machine count
    stopped it before the VM's worker could start: nothing changed until the corrected command.
  - **Step 3, `api.staging`'s DNS** (the founder, by hand: the CNAME to Fly replaced by `A
    34.47.244.114`, DNS only, TTL 1 min): 1.1.1.1 and 8.8.8.8 answered `34.47.244.114`; Caddy had
    Let's Encrypt's certificate for `api.staging` about 3 minutes later, with no restart; the full
    smoke check with `EXPECT_API_VIA=Caddy` passed every check; `/readyz` from the founder's Mac,
    median 201 ms (`/healthz` 193 ms) against 824 ms on Fly before the switch, 10 requests each.
  - **The founder's phone test, read from the VM's access log and the database, not taken from the
    report:** through `api.staging` in Mumbai, every request the phone made succeeded: discovery,
    threads, the wallet and ledger, a session refresh (the reload), the PIN, two socket tickets (the
    web's own socket, through Caddy) and a Razorpay order (`payments.order_created`). The account was
    `812a6748-97f1-4c56-8970-9d83c27c737b`, its session refreshed, its sign-in from 9 October.
    **`socket_probe` as that account through `api.staging`:** opened in 88 ms, `pong` in 2 ms.
  - **Not proved: a photo through the VM's worker, and a message.** The founder reported a photo
    uploaded and a message sent; neither reached either API (no photo or message request in the VM's
    access log or Fly's, no photo row since 9 October, staging's messages table empty), and after
    12:01:40 UTC no request from the phone reached either API at all (checked again at 12:10:25
    UTC, after the founder reported a photo shown as uploaded), so the later photo attempts never
    reached staging's servers. Not a web bug on this evidence: opening the photo screen makes
    requests of its own, and none came. Moderation on the VM is left to the first real photo, the
    founder's call (P-927, a note, not a blocker).
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
  **Deadline missed, 8 October 2026 (the audit, P-490):** Sprint 6 added routes on `current_user`
  (T-6.2, T-6.3, T-6.4). **Now before REL-1, measured on staging** (the advisor's recommendation;
  the founder to confirm). Nothing above changes.
- [ ] P-51 · Decide what a banned number is told. **In T-9.5, where bans are written, or T-9.6.**
  Worst case: a person barred by mistake, or a minor's family, has no way to learn why sign-in stopped
  working, or that grievance@ exists, which the IT Rules' grievance obligations (D-052) assume.
  D-073 records what happens today: on Path B, a number in `banned_identities` is answered like any
  other and its codes simply stop arriving, with no message. On Path A, Firebase's own SMS still
  arrives and the exchange answers `ACCOUNT_BANNED`, which the web can turn into copy naming
  grievance@. Whether Path B's silence is acceptable is this task's question.
  **Left open by T-9.5** (the founder's answer in its brief): still before real users, its place
  in the plan the founder's to set.

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
- [x] P-56 · Refuse a charge whose price changed after it was shown. **For T-7.1,** the first paid
  action a person taps. Worst case: a man sees "Open thread · 5 Velas" and is charged 6, because
  the price changed in between. The server still decides the price (rule 6), and `/terms` says
  prices can change. But charging more than the screen said is the kind of surprise that ends
  trust in a paid product. The client sends the price it showed, and the server refuses with
  `PRICE_CHANGED` if it differs: the value is compared, never used. Deferred from T-5.2, which reads
  prices fresh with no cache. Found planning Sprint 5 (decision 22, with the advisor directing it).
  **Missed, 8 October 2026 (the audit, P-490):** T-6.4's Super Like, T-7.1's Thread and T-7.3's
  private messages (`8a03628`) landed without it. **T-6.5 builds it as its first commit** (the
  founder, 8 October 2026): the API side, for every paid endpoint on `main`, then T-6.5's web sends
  the shown price. T-6.7's reveal adopts it if it lands after. It comes before the web's paid
  buttons: on T-6.5's and T-7.11's Needs lines.
  **Built 8 October 2026, before T-6.5, the first screen where a man taps a price (D-600):**
  `shown_price` on `POST /swipes`, `POST /threads` and `POST /threads/{id}/messages`, optional and
  0 when absent, so a man's paid action without it is refused (the founder's choice);
  `pricing.service.charge()` takes `shown` as a required argument and refuses with
  `PRICE_CHANGED` (409, `details.price`) before any debit. Only a priced action compares. The
  paid endpoints not yet built carry a line each: T-6.7, T-7.6, T-7.9, T-8.4, T-8.9.
  **Broken once each** (`uv run python -m tests.break_guards p56-`): the comparison removed, an
  absent field let through, and each of the four call sites comparing the price with itself, every
  one red in 1 of 1, no file differing by SHA-256 after.
- [x] P-57 · The app's screens have no visual design. **Before T-6.5,** on its Needs line. Worst
  case: every screen in Sprints 6 and 7 is framed by a shell and built from a prototype that was
  wrong four times in Sprint 5's plan alone, and a one-way door gets designed by accident: the
  refund button, gift's direction, the price list and "credits" for Velas. T-5.6 builds the shell
  provisionally (08-DESIGN). The first task that needs a screen designed stops and asks, rather
  than inventing it from the prototype. Found planning Sprint 5, at the direction of the advisor
  directing it.
  **Answered 7 October 2026 (08-DESIGN §8):** the founder approved fifteen screens on Claude's
  design canvas, "all the frontend are correct"; §8 is the rules made from it, and T-6.5 builds
  from §8, never the prototype. The screens §8 doesn't cover (You, Settings, Notifications, the
  store sheet, Checkout, admin) keep this rule: their tasks ask before designing them.
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
  **Left open by T-9.5** (the founder's answer in its brief): nothing in the panel flags mixed
  scripts yet; staff can read a name in a user's detail and freeze or ban, no more.
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
  **Seen a second time, in other circumstances (4 October 2026):** a rebase stopped on a conflict,
  which leaves HEAD on `main`'s own commit, and the gate, run in the same chained command, printed
  `CI is green for 48a5975 (run 37216216651)`: a commit already on `main`, with nothing of the
  session's in it. The push before it had failed, so nothing went up, and the green was disregarded
  (P-0.15's deploy flag, landed later as `da5172a`). P-54's case was a refused fast-forward; this
  was a stopped rebase. Twice, by two routes, makes it a thing that happens, not a thing that
  happened.
  **Partly closed by P-140:** a stopped rebase leaves HEAD detached, and `ci-gate` with no argument
  now exits 6 there, naming no branch. A HEAD already on `main` while on a branch still passes,
  which is this item's own fix, still open.
  **Deadline passed, 8 October 2026** (the audit, P-490): many `/done`s have run since.
- [x] P-61 · Give the API's 500s their CORS headers. **Before T-9.12,** or sooner if a screen needs to
  tell a crash from no signal. Worst case: a browser can't read the API's `INTERNAL` envelope at all,
  so every 500 looks to the web exactly like a lost connection ("Failed to fetch"), and a bug in
  production hides behind "check your connection". Starlette builds a 500 outside every middleware,
  CORS's included; `errors.py` adds `nosniff` and `no-store` there (P-42) but not
  `Access-Control-Allow-Origin`. Seen in T-3.10's Chrome check, when the dev database's missing
  `otp_sms_daily_cap` made OTP send fail. The web copes today (a failed restore offers a retry, never
  `/login`), so this is about seeing errors, not losing sessions. Add the CORS headers to the 500
  for an allowed origin only, with a test that a disallowed origin still gets none. Found in T-3.10.
  **Closed, 16 October 2026, before T-9.12 (the founder's order):** `_handle_unexpected` adds
  `cors_headers()` (`app/core/headers.py`), for an origin in `CORS_ORIGINS` only, compared exactly;
  it and `main.py`'s CORSMiddleware read one pair of settings, so the 500 can't drift from a 200.
  The tests compare a 500's `Access-Control-*` headers with a 200's for the same origin, and find
  none for another origin, a near miss (`…:30000`) or none at all. Broken once each
  (`uv run python -m tests.break_guards p61-`, `out/p61-break-guards.log`): 2 of 2 red, no file
  differing after.
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
  **Deadline passed, 8 October 2026** (the audit, P-490): T-4.8 and T-9.6 both migrated `users`, and
  T-9.6 (`15c75a4`) replaced this very function, still naming no constraint.
- [x] P-63 · Make the wallet refuse locking several wallets out of `user_id` order. **Before
  T-9.3,** on its Needs line, the first task that locks more than one. Worst case: two
  transactions each holding one man's wallet and waiting for the other's, a deadlock Postgres
  breaks by failing one, so a ban's refunds fail at random under load. D-077 says a transaction
  locks one wallet, or several in `user_id` order, but nothing enforces it: `debit()` and
  `credit()` lock whatever they're given. Fix: the wallet module records on the session which
  wallets it holds, and refuses (`WalletMisuse`) a lock below the highest held; or a
  `lock_wallets(ids)` that sorts them first. Test it with two transactions crediting the same two
  men in opposite orders. Found in T-5.1.
  **Its gate moved on 4 October 2026:** T-9.3 is dropped (D-230). The next task that can lock
  two wallets is T-8.6: its referral reward credits both men, and T-8.2's webhook runs that check
  inside the buyer's own transaction. So P-63 is on T-8.6's Needs line now, under that condition.
  **Done in T-8.6, 8 October 2026** (the founder's brief: inside that task). The wallet records on
  the session which wallets its transaction holds, forgotten when the transaction ends, and
  refuses (`WalletMisuse`) a lock below the highest held; `wallet.lock_wallets(ids)` sorts them
  first. The referral reward locks both wallets that way before either is credited, and before
  the webhook's purchase. `tests/modules/wallet/test_lock_order.py`: the refusals in the rolled-back
  session, and two transactions on two connections locking the same two men in opposite orders,
  each forced to hold one before asking for the other: the reversed one is refused, never a
  Postgres deadlock (`40P01`, which the breaking run shows with the guard gone). `make_user` now
  grants each man's Velas in a transaction of its own, as signup's is.
- [x] P-64 · Let endpoint tests see the events a request publishes. **Before T-7.4,** on its Needs
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
  **Done, 8 October 2026** (its own commit, before T-7.4): `session_for_the_app` now takes the
  request, and when it ends publishes the request's committed events to the app's Redis, as
  `get_session` does, and keeps them for a new fixture, `published`. What the test itself
  committed before the request is the test's, never published, as code outside a request
  publishes nothing. The tripwire is gone, and its test is three: a request's events heard on
  Redis through `client` and kept; a rolled-back request's never; the test's own setup never.
  T-7.1's and T-7.3's tests read `published` now, where they had read the session's committed
  events by hand. **Broken once each** (`uv run python -m tests.break_guards p64-`): three
  cases, the publish, the keeping and the test's own setup, each red in 1 of 1, every file
  restored and none differing by SHA-256 after.
- [x] P-65 · Make the deploy read `alembic_version` back after migrating. **Before P-38 or P-62,
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
  **Done, 4 October 2026,** at the direction of the advisor (Claude, in a separate chat), relayed
  by the founder. `scripts/migrate-with-url` hands Alembic a connection of its own, commits, and
  on that connection reads `alembic_version`: anything but the
  repo's single head (`get_current_head()`, which refuses two) exits 1, naming what the database
  holds. With the head matching, D-076's two triggers must be on their own tables with `tgenabled`
  `O` or `A` (`R` fires only under replica, so it counts as disabled), and D-077's index on
  `ledger_entries`, unique and valid; each refusal names the object. **Proof, both ways**
  (`api/tests/test_migrate_with_url.py`, the real script against scratch databases on the run's
  slot): an empty database migrated, then read back on the test's own connection; one at head
  passes again. Refused: Alembic logging `Running upgrade` for the last migration while a trigger
  on `alembic_version` keeps the old version (the false green this item exists for); a head
  stamped one migration short; each trigger dropped, disabled, replica-only and on the wrong table;
  the index dropped, on the wrong table, not unique and invalid. **Weakenings** (the script
  restored by SHA-256 after each): red with the comparison removed, with Alembic's answer trusted,
  with `R` or any `tgenabled` accepted, with either object matched by name alone, with uniqueness
  or validity unchecked, with a refusal exiting 0, and with a transaction opened before the upgrade
  and the commit removed: there the script printed the head and exited 0 over a database with no
  `alembic_version`, caught only by the test's own readback. **Green, as expected,** with the
  commit removed alone: Alembic commits a transaction it opened itself, and the commit is for the
  case above. **Passing against a real deploy:** staging's deploy of `ff50186` (run 37225065845,
  4 October 2026, 18:36 UTC), its migrate job as the owner against Supabase, printed
  `migrate: alembic_version holds 190d7bebf133.` and `that is the repo's head, 190d7bebf133.`,
  both triggers `present and enabled` and the index `present, unique and valid`; every job green.
  No migration was due, so Alembic logged no `Running upgrade`: these lines are the database's
  answer, not the migrator's. **Failing against a real deploy: not produced.** It would mean
  breaking staging's `alembic_version`, whose owner credentials live only in GitHub; the real
  script against a real Postgres stands in for it, above. **What it doesn't prove:** a trigger
  whose function was rewritten to refuse nothing still passes, since present and enabled is what
  this item asks. **Unexplained:** one run of the weakening set reported two errors on the index
  cases, with no log kept, no Postgres error logged then, and none in 33 runs since; if it
  recurs, keep pytest's output.
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
  **Deadline missed, 8 October 2026 (the audit, P-490):** other tasks have landed since T-3.14.
  **Now next after the current wave, the founder's console steps first.** Nothing above changes.
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
- [x] P-70 · Stop a number from outside India being texted as an Indian one. **Before REL-1** (on
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

  Found building T-3.14. **Done 18 October 2026:** under the number, on both sign-in paths and
  before anything is typed, "{app} takes Indian mobile numbers only. We're starting in Phagwara."
  (the founder's copy), the field's description; +91 stays outside it. `onboarding.test.tsx` and
  `SignIn.firebase.test.tsx` hold it (both red without it).
- [x] P-71 · Name reCAPTCHA on `/privacy`. **Before REL-1** (on its Needs line). Worst case:
  `/privacy` is published, and is inaccurate from the moment `/login` ships on a Firebase build:
  `/login` loads Google's reCAPTCHA as it opens (T-3.14 renders it then, so the first tap is quick),
  and reCAPTCHA reads browser and device signals for Google before a number is typed, while
  `/privacy` names Google only for sending the code and handling the number. A published page that
  says less than the product does is the same failure as switching on Google Analytics would have
  been. One line in its section on Google; its list of processors already names Google. It goes in
  P-0.7's review too, and to a lawyer when there is one (none is engaged, P-0.7). At the direction
  of the advisor directing T-3.14 (Claude, in a separate chat), relayed by the founder, 4 October
  2026.

  Found building T-3.14. **Done 18 October 2026:** a second paragraph in "Your phone number and
  Google": "When you open the sign-in page, Google's reCAPTCHA checks that you're not a bot, before
  you type anything. To do that it reads information about your browser and device and sends it to
  Google." Drafted by Claude, approved by the founder; `legal-pages.test.tsx` pins it, in that
  section. Still for P-0.7's review, and a lawyer's when there is one. Google's own notice on
  `/login` is P-880.
  **And the constraint that keeps `/privacy`'s Sightengine line true** (4 October 2026). `/privacy`
  says photos are checked by Sightengine "and deleted there after the check". That holds only while
  T-4.4 uses Sightengine's plain image moderation API, on its default retention, which deletes
  after processing; T-4.4 quotes Sightengine's FAQ and the four features that keep files (human
  review, the Feedback API, the Upload API and near-duplicate lists, redacted videos). **Turning on
  hybrid review or the Feedback API makes /privacy inaccurate the same day, so either is a decision
  that changes a published page, not a tuning knob someone enables for better accuracy.** Sightengine
  changes its retention on request, so "default" is a state we must not drift out of, not a
  guarantee. At the direction of the advisor (Claude, in a separate chat), relayed by the founder.
- [ ] P-72 · Give repeated possible-minor flags a human to go to. **Before the first real user** (on
  T-9.15's Needs line, and REL-1's if its tag includes T-4.4). Worst case without it: a model's
  probability, which catches young-looking adults, grows into an automatic action against a real
  woman, or into nothing at all. D-093: repeated `minor_suspected` flags on one person never
  auto-ban; they escalate to a human, the founder at this size, and no path for that exists yet
  (T-9.5's admin panel is the eventual one). Decide what "repeated" means, how the founder learns of
  it (with no image: D-093 deletes it), and what he can do. At the founder's direction, 4 October
  2026.

  Found planning T-4.4.
  **Decided (18 October 2026, D-991):** two flags in 30 days; a push to every active admin, and
  the flagged list in `/admin` if the panel carries it cheaply, no SSH tool; leave, freeze or ban
  as underage, each in `audit_log`, none automatic. Not built yet. The plan's answers (18 October:
  a permanent underage ban that keeps the account, the in-app row until P-755) are in D-991 and
  D-994; built next, before P-163.
- [x] P-73 · Find out what the two unidentified accounts on staging hold. **Before real users** (on
  T-9.15's Needs line, and REL-1's if its tag includes T-3.14). Two accounts, from phone numbers the
  founder hasn't identified, signed in to staging at 21:05 and 21:11 UTC on 3 October 2026 and were
  still signed in a day later (the founder's reading). Staging shares Firebase's user pool with
  production (P-66), so if they hold real profile data, real people are already in that pool.
  Worst case: a stranger's profile or photo shown to someone who isn't meant to see it, once any
  screen shows other people (none does on 4 October 2026: discover, chats, wallet and you are all
  placeholders, and no profile page exists, so no demo can show them yet).
  **Not answered yet, and why:** on 4 October 2026 Claude proposed one read-only query inside
  staging's API machine (a read-only transaction printing only, per account, when it was created,
  its onboarding step, which profile fields are set, yes or no, and a row count for every table
  with a key to `users`; never a phone number, a name, a photo, an IP address or a user agent).
  Claude Code's permission system blocked it as personal-data handling, and nothing was read by any
  other route. **Two ways to answer it:** (a) the founder allows it, by approving that query when
  it is proposed or by adding a Bash permission rule for it, and Claude runs it; or (b) the founder
  runs it himself. What to do with the answer is the founder's either way. At the founder's
  direction, 4 October 2026.

  Found preparing T-4.6.
  **Answered (18 October 2026): the founder's own test accounts.** The query ran by way (a), the
  founder approving it (16 October, relayed), on the Mumbai VM's API container over IAP SSH, the
  script fed on stdin (`out/p73_query.py`, SHA-256 `3a3109…8e33`): `transaction_read_only = on`,
  rolled back, labels, times, states, set or empty and counts only. Two accounts in 21:00 to 21:15
  UTC: A, made 21:05:48, stopped at `selfie`, profile fields set, one approved public photo, last
  seen 5 October; B, made 21:11:52, stopped at `seeking`, nothing beyond gender and birth date. Both
  `active`, unverified, signed in. Neither is shown to anyone: every way to find a person needs
  `done` (`discovery.repository.visible_to` for the feed, the profile, both searches, likes and
  swipes; the share page also `public_link`, off for A). The founder: "A and B are my own test
  accounts from my staging sign-in test on the night of 3 October (02:35 and 02:41 IST)", relayed
  18 October 2026; both stay as they are on staging. P-66 still owns the shared user pool.
- [ ] P-74 · Tell a person whose photo was rejected after they left the photos step. **Before the
  first real user.** Worst case: a woman whose only public photo is rejected while she is on the
  next screen is past the photos step with no live photo, so nobody sees her profile, and nothing
  anywhere says why. T-4.6 shows a rejection only in the slot that showed it, while that page is
  open (D-096); a reload, or going on, forgets it. Where it belongs (a notification, the You
  screen, a gate before discovery) is a product decision.
  **7 October 2026 (D-392, T-4.12):** the worst case changes shape, not weight: once nobody needs a
  public photo, she isn't invisible for lack of one, she is a grey silhouette (D-392), and still
  nothing tells her why her photo was refused. The fix is the same.

  Found building T-4.6.
- [x] P-75 · Keep public photo places 0 onwards on the server. **Before T-6.2 serves `Card`s with a main photo URL.**
  Worst case: a profile shown in discovery with no main photo, because its place 0 was rejected by
  moderation or removed by a client other than ours, and nothing moved the next one up. 03-SCHEMA
  says 0 is the main one; the API allows gaps (upload to any free place, delete without closing
  up), and only the web closes them (after a delete, a cleared rejection, and at Continue, T-4.6).
  Either the API closes gaps itself, or "main" becomes the lowest place, decided once.
  **7 October 2026 (D-392, T-4.12):** "main" must also cover there being no public photo at all:
  the `Card`'s main photo URL is null then, and the web shows a grey silhouette with the name.
  Whichever way this is settled, T-6.2 handles none.
  **Answered 8 October 2026** (the founder, on the advisor's recommendation, Claude in a separate
  chat, relayed by the founder): the card's photo is the profile's photo, the owner's approved
  public photo at the lowest place; the server moves no photo, so with a gap the lowest is still
  the main one; with none, null. Built by T-6.2 (`discovery.repository.main_photo_key`, D-494),
  held by `tests/modules/discovery/test_card.py`.

  Found building T-4.6.
- [ ] P-76 · Free an upload that never arrived when the owner's photos are listed, not only at the
  next upload URL. **Before the first real user.** Worst case: someone who closed the tab mid-upload
  comes back to a slot saying "Checking…" over a broken image, for a photo that will never be
  checked, until they remove it or upload another. `GET /me/photos` lists it as pending; only
  `POST /photos/upload-url` marks it `abandoned` (T-4.2).

  Found building T-4.6.
- [x] P-77 · Give CI's fresh SeaweedFS room for both buckets. **Done, 4 October 2026,** at the
  direction of the advisor directing Sprint 5, relayed by the founder. Worst case, as it happened:
  every session's storage tests go red on CI the day its suite grows, with nothing of theirs at
  fault. A fresh SeaweedFS claims 7 volumes per collection at its first write; started with no
  `-volume.max` (documented default 8), the collection written last could find none, and writes
  to `velora-public` failed with `InternalError` once the first one came about 25 s later than
  usual. Found when T-5.4's 50-connection tests lengthened the critical pass by that much (CI run
  37205686329, two attempts). Fix, both halves: `-volume.max=100` with the count in a comment,
  since neither alone is enough; and `s3-init` writes and deletes one object in each bucket
  through the filer, so both claim their volumes before any test runs. **Proved on the commit
  that went red,** `main` plus a test that only sleeps 25 s (`dfff8bf`, red: run 37210123236):
  with the fix, green (`5a7aafc`, run 37213315783); with the fix reverted, a tree identical to
  `dfff8bf`, red again on the same four tests (`b2837cb`, run 37213318457). The cost is written on
  D-086.
- [ ] P-78 · Watch SeaweedFS under load it hasn't met. **Not resolved by P-77, whenever a test
  first puts real concurrency on it.** Worst case: a storage server failing under load it has
  never seen, read as a flake. What P-77 proved is timing, not load: `main` plus a 25 s sleep
  reproduced the failure with no extra connections, and T-5.4's 50 connections are Postgres's,
  in an earlier pytest process. Nothing has put concurrent S3 writes on SeaweedFS yet, so it is
  not proved under load; this failure is the reason to watch it. A storage test that fails on CI
  with `InternalError` and passes on a re-run is this item's evidence, never a flake to re-run
  past. Filed at the direction of the advisor directing Sprint 5.
- [ ] P-180 · Require CI at GitHub before `main` moves: GitHub Pro, and a required status check on
  `main` (D-280). **Before REL-1** (on its Needs line). Worst case without it: a clone without the
  landing guard (a new machine, a reinstalled one, a `make hooks` never run, or `git push
  --no-verify`) puts on `main` a commit CI never passed, and every session rebases onto it. The
  guard (`scripts/push-gate`) protects the clones that installed it; a required check at GitHub
  protects every clone that will ever exist. **What it costs:** GitHub Pro, $4 a month as the
  advisor gave it; GitHub's pricing page as Claude read it on 5 October 2026 listed Free, Team ($4
  per user a month) and Enterprise and showed no price for Pro, so confirm it at purchase. GitHub's
  plans page lists protected branches in private repositories among what Pro adds, and today its
  API refuses them here (403, "Upgrade to GitHub Pro or make this repository public"). **The
  steps, the founder's:** upgrade the account `shubhamom0820-SK` to Pro; then Settings → Branches →
  a rule for `main`: "Require status checks to pass", naming the jobs that run on every branch
  push (`api — secrets, lint, migrate, pytest`, `web — lint, vitest, build`, `image — no .env
  inside, serves, fails fast`, `repo — types, hooks, gate`), **never `e2e — Playwright`, which
  P-282 skips on a docs-only push, so a check on it would hold every docs commit, and never
  `vouch`, which runs on `main` alone (D-410, 8 October 2026)**, and "Do not allow bypassing the
  above settings". **Proved by its effect:** a commit CI never ran on, pushed to `main`, refused by
  GitHub in its own words; then a commit CI passed on its branch, fast-forwarded, accepted. Not
  tonight (the advisor, 5 October 2026): today there is one machine and the guard covers it, and
  $4 a month is not the obstacle; remembering is, which is why it is on REL-1's Needs line.

  Found answering T-4.6's question about the pipe; filed from this session's block (P-180 to
  P-189).
- [x] P-84 · Scope T-4.2's "no photo was made" check to its own user. **Now: the Sprint 4
  session's next commit.** **Done in T-4.4's commit** (`feat(worker): photo moderation
  pipeline`), found there independently: its own committed photos turned the same check red in
  file order, so it is scoped to the test's user, as written below. Worst case: a test that fails by order teaches people to re-run
  instead of investigate, the habit that loses a real bug later. In `test_upload.py`,
  `test_a_declared_type_we_refuse_anyway_is_refused_saying_what_to_do` asserts
  `select(Photo.id)` finds nothing in the whole table, but `test_upload_race.py` commits photos
  for a fresh man, as it must. In file order the check runs first and passes; run race-first, all
  four of its cases fail (`pytest tests/modules/photos/test_upload_race.py
  tests/modules/photos/test_upload.py`). CI runs file order, so it is green there. Seen in 3 of
  8 shuffled orders of the whole suite (seeds 3, 4 and 7) during T-5.4, which touches no photo
  code. Fix: `where(Photo.user_id == user.id)`, 06-TESTING's rule since T-5.1. Found in T-5.4.
- [x] P-82 · Check the app shell where a browser draws it, at a phone's width and a desktop's.
  **Before T-6.5** (on its Needs line). It needs T-4.9, whose journey is the first to reach
  `/discover`. Worst case without it: at one width the nav, the only way between Discover, Chats,
  Wallet and You, is gone, under the page, or over the last thing on every screen, and every test
  stays green. T-5.6's tests run in jsdom, which applies no CSS: they prove the DOM (one nav,
  exactly four links, inside the gate and never on `(auth)`) and that the classes read tokens
  (`look.test.ts`), never where the nav lands. Tailwind drops a class it can't compile without an
  error, so a mistyped token reference removes a style silently. T-5.6's placement claims (fixed
  along the bottom on a phone, in the header's row from 768 px, the frame 900 px and centred,
  every item at least 44 × 44) rest on one Playwright run against `next dev` with a mocked API,
  whose script stayed in that session's scratchpad: not a check anyone can re-run.
  **The fix:** in T-3.13's E2E, on D-084's terms (a production build, Chromium, nothing kept, so
  assertions and no screenshots), once J1 reaches `/discover`. At 390 × 844 and 1280 × 800: the
  four links are visible and each opens its route; on the phone the nav's bottom edge is the
  viewport's and `<main>` keeps clear of it; on the desktop the nav sits inside the header's box.
  The control: `/login` and an onboarding step show no nav at either width. Proved by its effect:
  drop the nav's `md:static`, see the desktop case go red, restore. At the direction of the
  advisor directing T-5.6 (Claude, in a separate chat), relayed by the founder, 4 October 2026.

  Found building T-5.6.
  **Done, 8 October 2026:** in J1 (`e2e/signup.spec.ts`), which already runs in both of the E2E's
  projects, `mobile` at 390 × 844 and `desktop` at 1280 × 800. After the reload into `/discover`
  it opens Chats, Wallet, You and Discover from the nav, and on each: four links visible; on the
  phone the nav out of the header, its bottom edge the viewport's, and `<main>`'s content box
  ending at or above the nav's top; on the desktop the nav inside the header's box. The control:
  no `<nav>` in the page on `/login` or the birthday step, at both widths. Broken once each, run by
  `pnpm exec playwright test -g "J1: a new man"`: without the nav's `md:static` the desktop case
  went red ("the nav inside the header's box"), the phone's stayed green; without `<main>`'s
  `pb-(--shell-nav-height)` the phone case went red (content ending at 844, the nav's top 788),
  the desktop's stayed green. Restored, both green. **Its first CI run after a rebase went red,
  the check's own fault:** scrolled to the end in one call and measured in another, a page read
  1100 against the nav's 788, not at its end when measured (most likely still filling in; which
  page wasn't named, so the message names it now). Scrolling and measuring are one call in the page
  since, with under a pixel allowed for the scroll's rounding (788.05 seen locally, 1 of 3
  phone runs; a lost padding misses by the nav's 56). Then 10 of 10 green (`--repeat-each=5`),
  and both breaks red again in their own project only.
- [x] P-83 · Make the shell's look guard an allowlist. **Before T-6.5** (on its Needs line). Worst
  case: a look value from a family nobody listed lands in `AppShell.tsx`, the guard stays green,
  and T-6.5's design pass meets values written into structure: the rework T-5.6's rule exists to
  prevent, the most expensive in the sprint. `look.test.ts` bans the families T-5.6 thought of
  (Tailwind's spacing, type, radius, line-width, shadow and opacity scales, arbitrary values,
  numbers passed as sizes, inline styles), so `scale-95`, `duration-150`, `blur-sm`,
  `aspect-video` and whatever Tailwind adds next all pass it. That is a blacklist, the shape
  D-084 records: a blacklist passes every test written with today's names. T-5.5, which puts the
  balance pill in the header, edits the shell before T-6.5 does, under the blacklist.
  **The fix:** invert it. In the shell's components a class passes only if it is on an allowed
  list: layout utilities that carry no look (display, flex, position, alignment, `z-*`, zero
  offsets); utilities named after a token, those names read from `tokens.css` and `globals.css`,
  never typed into the test; and `(--name)` references to a token that exists. Anything else
  fails. Its test includes a class nobody has named, as D-084's gate test includes
  `env-nobody-has-named-2031`, and keeps it. At the direction of the advisor directing T-5.6
  (Claude, in a separate chat), relayed by the founder, 4 October 2026.

  Found building T-5.6.
  **Done, 8 October 2026:** `look.test.ts` reads classes only from class props (`className`, or any
  `…ClassName`), each a string or `cx()` of strings behind plain names; any other shape fails as
  classes it can't read, so moving classes into a variable doesn't hide them. A class passes only
  if it is on `LAYOUT` (display, position, flex and alignment, `z-*`, zero, `auto`/`full`/`dvh`
  sizes, `fill-current`), is a utility named after a theme name read from `globals.css`, or reads
  a token in `tokens.css` by `(--name)` or `(type:--name)`. Inverting it failed the shell's three
  bare `border`s, a 1 px from Tailwind's default: the founder chose a token, `--shell-line`, which
  `AppShell.tsx` reads as `border-(length:--shell-line)` and its sides (the built CSS has
  `border-bottom-width:var(--shell-line)` and the rest). `quux-nobody-has-named-2031` stays in
  its test. Broken once each: `duration-150` in `AppShell.tsx` failed the shell's test; the
  can't-read rule off failed its five cases; every class allowed failed 20 of its 21 named classes
  (`text-[13px]` is caught as an arbitrary value first) and the `cx()` case. Restored by file copy, SHA-256 checked, all 43 green.
- [x] P-79 · Stop an approved private photo being swapped for an unmoderated one. **Before T-8.4**
  (on its Needs line), which first shows private photos to anyone but their owner. Worst case: a
  private photo passes moderation, its owner PUTs a nude, or a photo carrying their home's
  location, to the same presigned URL, and T-8.4's album shows it to the people they granted.
  How: the upload URL lasts 5 minutes (D-027) and still works after `complete`; moderation reads
  the upload and writes the re-encoded JPEG back over it (T-4.4), so a PUT inside those 5
  minutes, after moderation, replaces the approved copy. A public photo is safe: its public copy is
  the bytes Sightengine scored, written to its own key, never copied from the upload (T-4.4 tests
  that). Options: keep the moderated copy at a key of its own (a column, so a migration, P-65
  first), or have T-8.4 render albums only from bytes moderation wrote. The founder decides.
  **Decided by the founder, 4 October 2026: the separate key.** Moderation writes the re-encoded
  image to a key the owner's upload URL can't reach, and albums render only from that key. D-092
  already makes those bytes a different artifact, so its own key costs almost nothing and closes
  the hole rather than narrowing it. (Built from the photo's id, as the public copy's key is, it
  may need no column at all; the task that builds it says.)

  Found building T-4.4. **P-79 to P-81 predate the P-number blocks** (CLAUDE.md): they were on
  `main` before that rule, and keep their numbers, since renumbering risks the stale reference the
  rule exists to prevent (the founder, 4 October 2026).
  **Built 8 October 2026, as D-700, with a column** (the founder, on the advisor's
  recommendation): `photos.scored_key` (migration `8243172d0af6`, whose downgrade refuses while a
  row has one), `scored/{user_id}/{photo_id}.jpg` in the private bucket, written from the scored
  bytes when a private photo is approved; the owner's link to an approved private photo is signed
  for it. A column, since the erasure's and D-078's file lists are held by their tests to every
  `*_key` column, so both carry it (both tests now delete one). Tested in `test_moderate.py`: the
  copy is the bytes scored, outside `raw/`, and a PUT while Sightengine is asked and another after
  approval change neither it nor the owner's link; a rejected private photo, a public photo and
  the face photo get none. Broken once each (`tests.break_guards p79-`, log in
  `out/p79-break-guards.log`): the copy never written, written at the upload's key, the key
  helper under `raw/`, every approved kind given one, the owner shown the upload, either file
  list without it, and the downgrade not refusing: 8 of 8 red, every file restored, SHA-256
  checked. Private photos approved before this have no scored copy; T-8.4 shows only rows that do.
- [x] P-80 · Keep query values out of the API's database errors. **Before real users** (on
  T-9.15's Needs line). Worst case: a failed query's error, logged with its parameters, carries a
  phone number's hash, an encrypted number or a storage key into Fly's logs (rule 15). Seen
  building T-4.4: a test's unique-key violation printed `[parameters: (…, 'raw/<user>/<photo>', …)]`.
  SQLAlchemy's `hide_parameters=True` removes them; T-4.4 gave `build_engine` the option and
  turned it on for the worker only, since changing the API's engine was outside the task. Turning
  it on for the API is one argument in `create_app()`, and a test that a failing query's error
  names no value.

  Found building T-4.4.
  **Built (16 October 2026, D-990), wider than filed:** with `hide_parameters` on, four ways still
  quoted a value: a duplicate key's DETAIL (a phone number's hash, by `uq_users_phone_hash_live`), a
  check's failing row, a cast Postgres refused, and an argument asyncpg can't encode, quoted to 40
  characters (a storage key's user id; the worker's test passed only because a whole key is
  longer). `create_app()` sets the flag, and the flag now also installs `_withhold_values`
  (`core/db.py`), which rebuilds every layer of the error from its SQLSTATE and names; Postgres's
  message stays only for class 23 and our triggers' P0. Held by `test_db.py`'s
  `test_the_apis_database_errors_carry_no_values` (each of the four, against SQLAlchemy's option
  alone as the control), the worker's test with a key too short to be cut, and five break cases,
  `p80-1` to `p80-5`, all red (`out/p80-break-run.log`, `p80-4` rerun in `out/p80-4-rerun.log` after
  its claim was narrowed). The flag's name is P-890's.
- [ ] P-81 · Ask the lawyer whether D-093's deletion may need to yield when a photo is also sexual.
  **Before the first real user, and not with the rest** (on REL-1's and T-9.15's Needs lines; the
  one exception on P-0.7). **The one legal question that must be answered before anyone real
  signs up** (the founder, 4 October 2026): the founder has deferred legal work until later, and
  this is the exception, because getting it wrong here is not a commercial mistake. "I'm not going
  to reason my way to an answer": neither of us knows the law, so a lawyer answers it. Worst case: a photo
  Sightengine scores as possibly a minor's and as sexual is deleted, as D-093 requires, when the
  law required it kept and reported. Claude doesn't know what Indian law requires here and claims
  nothing; this is a question, not a finding. The code does what D-093 says: a possible minor's
  photo is deleted first, whatever else it scores (T-4.4, `photos/moderation.py`). If the answer is
  that such a photo must be preserved, D-093 is superseded by a decision, never changed in code
  alone.

  Found building T-4.4.
- [ ] P-85 · Refuse a duplicate Proposed-item number in CI. **Not tonight (the advisor directing
  Sprint 5, 4 October 2026); before the next day with several sessions allocating at once.**
  Worst case: two items under one number, and a relay, a Needs line or a commit that names it
  points at the wrong one. On 4 October five sessions allocated at once: two open branches
  claimed P-74 and P-75 for different items, and T-5.4's item moved from P-73 to P-84 at its
  rebase. The manual rule held (re-read `main` and every open branch at landing), but a rule five
  sessions follow by hand will slip. Fix: a test that parses `05-PLAN.md`'s Proposed list and
  fails on any number used twice, naming both titles, so the second session to merge finds out
  in CI. Found in T-5.4.
- [x] P-130 · Rewrite `/refunds` to D-230: there is no product refund. **Before REL-1 and T-8.1**
  (on both Needs lines). Worst case: the page goes public, and Velas go on sale, promising Velas
  back on a ban and on a declined album request that the product will never return, a published
  promise to paying men that the code doesn't keep.
  **What changes:** the "When Velas come back on their own" section goes, along with the opening
  line's "and when Velas come back on their own". The page says plainly that Velas spent are spent,
  including on someone later banned and on a declined request. "When we fix a payment" stays, since
  a duplicate charge and a chargeback aren't product refunds (D-230). Then
  `legal-pages.test.tsx`, which asserts the section's title, follows the page, and so does the
  comment in `en.ts` tying its 7 days to T-9.3, which is dropped.
  **Files:** `web/src/i18n/en.ts` (`legal.refunds`), `web/src/app/(marketing)/refunds/page.tsx`,
  `web/src/app/(marketing)/legal-pages.test.tsx`. Copy only: nothing else promises a return (read
  4 October 2026). Decided by the founder, 4 October 2026; filed by Claude.
  **Done, 8 October 2026:** the page's three sections are "Purchases are final", "Velas you spend
  are spent" (new: nothing comes back on someone later banned or on a declined request) and "A
  broken payment is ours to fix", unchanged. The test holds the order, the two sentences, and that
  no word on the page says Velas return by themselves, by a regex it proves against the replaced
  copy. Read again the same day: the only other return wording in the web is the wallet history's
  labels for the two unused ledger reasons (`en.ts`, "Returned after a ban", "Returned: request
  declined"), words for enum values the API still has, not a promise on a page; left as they are.

  Found writing D-230.
- [x] P-140 · Make a deploy's gate read `main`'s own CI run, not whichever ran last for the commit.
  **Before the next day with several sessions landing at once.** Worst case: a commit whose CI
  on `main` passed is refused deployment, and the refusal reads as if the commit failed on its
  merits, so someone hunts a bug that isn't there while staging falls behind `main`. **Observed,
  4 October 2026:** staging's deploy of `da5172a` (run 37219111888) stopped at its gate, `CI concluded
  'cancelled' for da5172a (run 37218824878)`. Three CI runs existed for that commit: 37218291859 on
  its own branch (success), 37218706519 on `main` (success) and 37218824878 on another session's
  branch, `docs-pricing-answers` (cancelled, the newest, created 16:59:52 UTC). **Read from the
  code, not tested:** `scripts/ci-gate` (lines 49–55) takes the newest push-event run of the CI
  workflow for the commit, on any branch (`sort_by(.createdAt) | last`), which fits what happened.
  **Not established:** how that branch came to point at `da5172a`, and whether the same rule could
  also let a newer green run on another branch stand in for a red run on `main` (the code allows
  it; nobody has seen it). Fix to decide: the deploy's gate filters to `main`'s run for the
  commit, and `/done`'s to the task branch's. Found landing P-0.15's deploy flag; filed from this
  session's block (P-140 to P-149).
  **Done, 4 October 2026,** at the direction of the advisor directing Sprint 5. **The silent
  direction was real before the fix:** with `main`'s run red and a newer green run for the commit
  on another branch, `scripts/ci-gate` called as `deploy.yml` called it answered `CI is green ...
  (run 12)` and exited 0, and `scripts/release-gate`, production's gate, picked the same run: both
  would have passed a red commit. **Fix:** `ci-gate` reads one branch's run only (`--branch`, else
  the branch its ref names, else the branch HEAD is on; a bare commit or a detached HEAD has no
  branch and exits 6, never guessed), checks the branch again when it reads the run, and
  `deploy.yml` passes `--branch main`; `release-gate` reads `main`'s run only. **Proof, both
  ways:** the new scenarios (`main` red with a newer green elsewhere refused; `main` green with a
  newer cancelled elsewhere passed; a run only on another branch never counts; a run read back
  from another branch refused; HEAD's and a ref's branch found; a bare commit and a detached HEAD
  refused) pass, `ci-gate-test` 20 of 20 and `release-gate-test` 52 of 52. Against the old
  `release-gate`, the hole scenario exited 0. Each check removed alone went red: `ci-gate`'s branch
  filter (4 scenarios), its read-back check (1), `release-gate`'s filter (3); each restored and
  checked by SHA-256.
- [x] P-150 · Write the 1-hour task D-097 names, which moves a Thread from 24 hours to 1 and lists
  every place that says 24 hours. **Needs:** nothing now. The founder's word on D-253, the
  advisor's rule for Extend from an expired Thread, came 8 October 2026 (Locked). The two questions
  moved here from T-5.2's item 10 on 4 October 2026 were **answered 8 October 2026 (the founder, in
  his words; D-097's amendment):**
  - (a) **Does his own message restart the hour? No.** "P-150 ka a ka nahi": only hers does, as
    D-097's step 2 says. The worst case if it had been guessed the other way, a Thread he keeps
    open alone, free, by writing every 59 minutes, never arises.
  - (d) **When Extend's 24 hours end, does the hour start then, or run from her last message? From
    her last message.** "ghanta uske aakhri message se gina jayega": Extend bought 24 hours, not
    25. So a Thread he paid 10 Velas to extend can expire the instant the extension ends, if her
    last message is more than an hour old by then: named here as the worst case if guessed, and
    now decided, not guessed.

  **Also unowned: no task sells Extend yet.** T-5.2 prices it (`thread_extend`, 10 Velas, as many
  times as he likes for one Thread, D-250, and at any time: from expired the 10 re-opens it too,
  D-253, Locked 8 October 2026), but no endpoint charges it; this task is its natural home, the
  founder to confirm.
  T-7.6 points here. Found in T-5.2; filed from this session's block (P-150 to P-159).
  **Still nobody's, 8 October 2026:** the questions are answered, and the work, the 1-hour task
  that sells Extend, is unwritten. This box stays open until it is.
  **Done 8 October 2026: written into T-7.6,** which was not yet built, so rewritten in place
  rather than reopened: the hour in `expires_at` alone (D-560), the expire and warning crons,
  re-open, and `POST /threads/{id}/extend`, Extend's home as this entry proposed (in the plan the
  founder approved, 8 October 2026). Its five questions (re-open's hour, the warning, the settings, a second
  Extend, where the copy changes) were answered the same day and are written there as decided.
  **The sweep** (`git grep -i` for 24 h, 24h, 24-hour, 24 hours, `thread_hours`, "a day", every
  hit classified): docs that gave a Thread 24 hours now say an hour (CLAUDE.md, README, 02, 03,
  04, 06, 08, 09; D-097 points at T-7.6); the code and copy that say it are T-7.6's, listed on its
  setting-and-copy line. Left as they are: D-003 and the other entries' history, the prototype
  (the design reference, whose departures 08-DESIGN records), and every 24 that isn't a Thread's
  (sign-in codes, exports, grievances, the report SLA, the selfie window, discovery's recency, the
  gift cooldown, and Extend's own 24 hours).
- [x] P-141 · Let only `main` deploy to staging. **Before the next session that can push a
  branch.** Worst case: a workflow file edited on any branch runs with staging's secrets, among
  them the database owner's connection used for migrations, and the Vercel and Fly tokens: it can
  deploy anything to staging or read what those secrets reach. **Observed, 4 October 2026:** the
  staging environment has no deployment branch policy (`deployment_branch_policy: null`, no
  protection rules), and a `deploy.yml` changed on a throwaway branch and dispatched from it ran
  every job with staging's secrets (run 37222405686, P-0.15's one `--debug` deploy, approved).
  Production is already closed: its environment allows only tags `v*`. Fix: give `staging` a
  deployment branch policy of `main` only. Every real deploy runs on `main` (a CI run there, or a
  dispatch from it), so nothing legitimate is lost; a one-off like that `--debug` run would then
  need its change on `main`. A repository setting, so the founder's to change. Found running
  that deploy; filed from this session's block (P-140 to P-149).
  **Done, 4 October 2026, by the founder:** the `staging` environment's deployment branches are
  `main` only (GitHub reports one custom policy, branch `main`). **Proved by its effect, not the
  setting:** `deploy.yml` dispatched from a throwaway branch (run 37224641921) was refused at the
  first job that uses the environment: `Branch "ci-staging-policy-probe" is not allowed to deploy
  to staging due to environment protection rules.` `migrate` was rejected and nothing after it
  ran; only the gate job ran, and it holds no environment secret.
- [ ] P-151 · Name tables and types in catalogue queries by `to_regclass()` or a join, never a
  `'name'::regclass` or `'name'::regtype` literal, wherever the object can be dropped and made
  again in one test run. **Before the next task whose tests read the catalogue.** Worst case: a
  check reads an object that no longer exists and finds nothing. Written as "these, exactly", it
  fails loudly in some test orders and someone hunts a bug that isn't there (P-84's cost); written
  as "no row breaks X", it passes having looked at nothing. **Why:** Postgres fixes such a literal
  to an OID when the statement is prepared, and asyncpg keeps prepared statements per connection,
  keyed by their text. After `test_migrations_round_trip` (base and back) on a pooled connection,
  `users` and every other table has a new OID, and a statement that connection prepared before
  still asks about the old one. **Seen in T-5.2,** not in today's tests: migration 4a7e20790605's
  first label query read the dropped type's values, none, on a connection that had rebuilt it
  once, and wrote a type of two values; reproduced, and fixed there with a join by name and
  `to_regclass()`. **Not seen:** `tests/modules/users/test_dob_gender.py`'s three
  `'users'::regclass` reads (D-072's check), which would report every listed table as holding no
  key, a loud false red, if such an order ever happened. Found in T-5.2; filed from this
  session's block (P-150 to P-159).
- [x] P-142 · Let two runs' fifty-connection tests take turns on the shared server. **Done, 4
  October 2026,** at the direction of the advisor directing Sprint 5. Worst case, as it was
  happening: a red on code nobody changed, blocking each session's landing in turn, since the
  landing guard runs `make test` locally first. Every checkout shares one Postgres of 100
  connections, and since T-5.4 every full run opens fifty at once for its concurrency tests: two
  runs together don't fit, and the second failed loudly (`Postgres opened 40 of 50 connections
  … too many clients`), as designed, but on no fault of its own. Seen twice landing P-141.
  **Fix:** the `fifty` fixture first takes the server's one fifty-connection turn, a Postgres
  advisory lock (first key 50) on the server's own `postgres` database, so every run and slot
  sees it, held on a connection of its own, so a run that dies frees it; a second run waits for
  it, up to 600 s, then fails loudly, never skips. Restarting the shared database with a higher
  limit was rejected tonight: it would cut off every session's running tests. **Proved both
  ways:** two runs started together, both 7 of 7 (42.6 s and 53.5 s, against 25 s alone: they
  took turns); with the lock removed, both failed on the collision itself (`Postgres opened 44`
  to `49 of 50`), and the new `test_a_fifty_waits_while_another_run_holds_the_turn` went red
  (`it took the turn while another run held it`); restored by SHA-256. The case is committed:
  `tests.break_guards p142-`, red in 1 of 1. Filed from this session's block (P-140 to P-149).
- [ ] P-200 · Stop the shared local Postgres running out of connections when sessions test at once,
  in what P-142 leaves. **Now** (the founder, 5 October 2026). Worst case: a local run fails,
  passes on a re-run, and people learn to re-run instead of look, the habit the landing guard was
  built that night to stop; with six sessions working at once, the flake meets someone every day it
  stays.
  **What was observed, by Claude, 4 October 2026, on this machine:** every worktree shares one
  Docker Postgres, at the default `max_connections` of 100 (read from Postgres itself; nothing in
  `infra/docker-compose.yml` sets it), and T-5.4's concurrency tests open 50 at once. Twice that
  night `make test` failed with Postgres's own refusal: once in `tests/core/test_events.py`
  (`TooManyConnectionsError: sorry, too many clients already`, answered as a 500), once in
  T-5.4's six concurrency tests (their own message: "Postgres opened 44 of 50 connections",
  then 45). At the second, `pg_stat_activity` showed 60 connections held by other sessions. Each
  time, waiting until fewer than 30 were in use and running again passed, the whole suite.
  **It fits an earlier failure without proving it:** on 4 October 2026 one run failed
  `tests/modules/users/test_me.py::test_me_never_sends_the_number_or_the_date_of_birth`, CI was
  green on the same commit, and it never reproduced (5 runs alone, 2 full suites). Its error text
  was lost: that run's output went through a pipe to `grep`. A probe of the one other cause
  suspected, the birth year appearing in `/me` by chance, found it in 0 of 1,500 bodies.
  **One more that may be the same, unproved:** the same night, one run of
  `python -m tests.break_guards land` reported its first two cases not red; its output wasn't
  kept, and each was red in 4 of 4 runs since. A pytest run that can't start (Postgres refusing
  the run slot's connection, say) reads there as "not red" rather than inconclusive, which would
  explain it; nothing showed that it did.
  **What P-142 settled, and what it leaves** (P-142 landed minutes before this was filed): two
  runs' fifty-connection tests now take turns, which is the second observation's kind if the 60
  held then included another run's fifty. It leaves the first kind: while one run holds its
  fifty, every other session's ordinary tests share the other 50, and a run's own pools, the
  app's included, are refused when they don't fit, as `test_events.py` was.
  **Options, the founder's to choose:** raise `max_connections` in the compose file, sized from
  what every session can open at once (P-55's slots × their pools, plus the 50 of the run holding
  the turn), at a quiet moment, since P-142 rejected restarting the shared server while
  sessions' tests run; or make an ordinary run wait for the turn too when it can't get a
  connection, rather than fail. Whatever is chosen, prove it by its effect: a full suite started
  while another holds the fifty, both green.

  Found building T-4.4's follow-ups. The first number of Claude's block for this session (P-200
  to P-209, D-300 to D-309, given by the founder).
  **Deadline missed, 8 October 2026 (the audit, P-490):** "Now" was 5 October 2026. **Now when no
  session is running tests** (raising `max_connections` restarts the Docker Postgres every worktree
  shares). Nothing above changes.
- [x] P-152 · Make the debit's allowlist hold against a caller it can't see named. **Not tonight**
  (the advisor, 5 October 2026); worth doing where it is next touched, T-8.9, which names gift
  sending in it. Worst case: a caller reaches `wallet.service.debit` through a name built at run
  time (`getattr(module, "de" + "bit")`, an `importlib` lookup, a handler table filled by
  registration) with a literal price, and `test_only_charge_reaches_the_debit` stays green: a man
  is charged a number no `action_prices` row holds, and nothing says so (rules 5 and 6). **The same
  shape as D-084's blacklist:** the guard catches what it can see named, so every case written
  with a name it can see passes. D-084's lesson is the precedent: prove the stronger guard against
  a caller the source scan can't see, a debit reached by a computed name, and keep that case.
  Ways to strengthen it, the strengthener's to choose: a check at run time (`debit` refuses a call
  that didn't come through `charge` or gift sending, for instance by needing a value only they
  can build), or a `debit` no other module can import, with the source scan kept as a second
  layer. Found in T-5.2, whose report named it; the advisor ranked it first of that report's three
  worries. Filed from this session's block (P-150 to P-159).
  **Done in T-8.9, 8 October 2026 (D-651):** `wallet.service.debit()` reads the frame that awaits
  it and refuses with `WalletMisuse`, before any row is read, unless it is `pricing.service.charge`
  or gift sending's `_send_in` (`DEBIT_CALLERS`), or test code, which never ships. Proved in
  `tests/modules/pricing/test_debit_callers.py` against a module built at run time that reaches
  `debit` by `getattr(service, "de" + "bit")`: the scan passes its source, and the run refuses it
  with nothing written. Also refused: a listed name in an unlisted module, an unlisted name in a
  listed one, and a debit started as a task. A test holds the scan's list and `DEBIT_CALLERS` equal.
- [x] P-143 · Refuse `make hooks` anywhere but the clone's main checkout. **Done, 4 October 2026,**
  at the direction of the advisor directing Sprint 5. Worst case, as it happened: git's hooks are
  shared by every checkout of a clone, and `pre-commit install` pins the pre-commit hook to the
  virtualenv of the checkout it runs in; run from a scratchpad worktree later removed (at 23:48),
  every checkout's commits failed with "`pre-commit` not found", and with seven sessions each
  holding a worktree it would happen again. **Fix:** `make hooks` first runs
  `scripts/require-main-checkout`, which refuses a linked worktree and names the command to run
  instead. It tells the two apart by git itself, never a path: in the main checkout the git
  directory is the clone's common one, in a worktree `<common>/worktrees/<name>`. **Proved both
  ways, in a throwaway clone with hooks of its own:** from its main checkout `make hooks` was
  accepted and the hook pointed at that checkout's virtualenv; from its linked worktree it was
  refused (exit 2) with the hooks byte for byte unchanged; with the check disabled, `make hooks`
  from the worktree succeeded, pointed the hook at the worktree, and once the worktree was removed
  a commit in the main checkout failed with "`pre-commit` not found": tonight's breakage,
  reproduced. In the suite: `scripts/require-main-checkout-test` (5 of 5, a real linked worktree)
  through `tests/test_require_main_checkout.py`, which also asks `make -n hooks` that the check is
  the first thing it runs; `tests.break_guards p143-` turns each red (the check disabled, the
  check not run), restored by SHA-256. Filed from this session's block (P-140 to P-149).
  **Whose worktree it was** (added by that session, unprompted): Claude's, in the session doing
  T-4.4's follow-ups. Its `make hooks`, at 23:48 IST, installed the landing guard's pre-push and
  pinned the pre-commit hook to that worktree's virtualenv; it removed the worktree after landing
  `76bda6f`, and reinstalled the hook from the main checkout's virtualenv at 00:34 IST, when its
  own next commit failed. The hook has pointed there since.
- [ ] P-190 · Decide what someone just outside Phagwara picks when they deny location access.
  **For the founder, before REL-1.** Worst case: someone in Jalandhar, 22 km from Phagwara and so
  inside D-013's 25 km discovery radius (`discovery_radius_km`), denies location access and is
  offered only Phagwara's 17 areas (P-38). They pick the nearest, and every distance shown to them,
  and theirs to everyone else, is out by up to 25 km. P-38 kept the areas Phagwara's on purpose:
  the launch city is a decision, not a radius, and the radius reaching another city is a side effect
  of the number, not an intention (the advisor directing P-38, Claude in a separate chat, 5 October
  2026). The choices: leave it, since that user can still share their location; seed Jalandhar's
  areas, which widens the launch and so is D-013's to change; or narrow the radius. Found in P-38;
  filed from this session's block (P-190 to P-199).
- [ ] P-191 · Record the founder's review of Phagwara's 17 area centroids. **Before REL-1.** Worst
  case: a centroid drafted from one shop's address sits in the wrong part of town, so someone who
  denies location access and picks that area is shown distances out by a kilometre or two, and so
  is everyone near them. P-38 landed all 17 marked "not yet reviewed" (migration `bc589ac265c2`,
  each row with its source); its review sheet, with a map link per centroid, was
  `out/p-38-areas-review.md` on the founder's machine. A new data migration records each row as
  confirmed, moved or dropped, by the founder, and leaves "not yet reviewed" on what he can't
  confirm. Moving a centroid can shrink the closest gap: the seed's test reads it from the database
  and fails if `SCATTER_RADIUS_M` (250 m) is no longer under half of it. Found in P-38; filed from
  this session's block (P-190 to P-199).
- [ ] P-160 · Measure the face-match threshold on real data **before the product claims
  verification in any published word** (on 07-CHECKLISTS §F, the release checklist, not a someday
  list). Worst case: a published "verified" resting on a false-accept rate nobody knows, so a man
  holding a woman's photos passes as her under a badge that says we checked. **Not before launch:**
  the founder dropped the 50-person measurement set (D-260), and nothing claims verification until
  this is done (D-262, held by `web/src/i18n/claims.test.ts`). **It completes itself:** every
  `same`/`different` verdict the founder records with `app.tools.selfie_review` (D-264) is a
  labelled pair from a real decision, written into the selfie's record, so the reviews that protect
  people at launch also build the data a set of volunteers would have. **What's still missing, and
  isn't Claude's to decide:** a false-accept rate also needs pairs of *different* people compared,
  which means comparing users' faces with each other for a purpose `/privacy` doesn't name; the
  founder decides, with P-0.7's lawyer, before it is done. Then: the lowest threshold accepting at
  most 1 in 1,000 such pairs, with the false-reject rate there (T-4.5's original standard; above 5%,
  stop and tell the founder). Filed from T-4.5's block (P-160 to P-169), at the direction of the
  advisor directing T-4.5 (Claude, in a separate chat), relayed by the founder, 5 October 2026.
- [x] P-161 · Compare a public photo added after a verification with the selfie, or say the match
  no longer holds. **Before T-6.2's `Card` carries `is_verified` to anyone.** Worst case: a woman's
  badge says "Selfie matches photos" while every photo on her profile was replaced, after the
  check, with someone else's; the comparison ran once, against the photos she had then. Options:
  re-run `verify_selfie` against the kept selfie when a public photo is approved after a
  verification, and clear `is_verified` if it no longer matches; or show the badge only while the
  photos are the ones compared. The founder decides which (a cleared badge on a live woman's
  profile is a product rule, T-4.8's). Found building T-4.5.
  **Resolved in shape, 7 October 2026 (D-393, Locked; built by T-4.12, and ticked when it lands):**
  the redesign widened this from "a photo added after" to every public photo, since the selfie is
  compared with the face photo alone (D-391) and never with a public one. The founder chose the
  first option, in his own words: each approved public photo with a face is compared with the kept
  selfie, when it is approved or when the selfie is decided, and the badge shows only while at
  least one matched; a photo that doesn't match isn't rejected and doesn't count. A cleared
  `is_verified` is rejected; undoing a decision stays P-163's.
- [x] P-162 · Decide whether one matching photo may carry a whole profile. **Before real users**
  (on T-9.15's Needs line, and REL-1's if its tag includes T-4.5). Worst
  case: a man verifies with a selfie of himself against one photo of himself among five of a
  woman's; the profile shows her, and the badge says the selfie matches. T-4.5 counts the best
  photo, as the plan said, and D-264's review marks such approvals `MIXED` meanwhile. Options:
  require the main photo (place 0) to match, or every photo with one face; each is unmeasured
  (D-260), and each turns away real women whose other photos are in sunglasses or in profile. The
  founder decides, ideally with P-160's numbers. Found in T-4.5's plan.
  **7 October 2026 (D-391, D-393, T-4.12):** the selfie now has one reference, the face photo, so
  "the best of five" no longer arises for the selfie's own decision. The question returns on the
  badge's side: a profile of someone else's photos with one of the man's own among them shows the
  badge on that one match, since D-393 counts at least one. D-264's `mixed` flag keeps marking
  such profiles; the founder decides as before.
  **Closed (18 October 2026, D-992): answered by D-910.** Since 9 October the badge follows the
  main photo alone, this item's first option; the other photos stay unchecked, and
  `selfie_review` keeps marking `mixed` profiles for the founder to look at. Nothing to build.
- [ ] P-163 · Let the founder undo a decision his review finds wrong. **Before real users** (on
  T-9.15's Needs line, and REL-1's if its tag includes T-4.5). Worst case: he records "different" for a woman's approved
  selfie, and she stays live with the badge until someone edits production's database by hand.
  T-4.5 records the verdict (D-264) and changes nothing else. Fix: an action that rejects the
  verification, clears `is_verified` and writes `audit_log`, through `selfie_review` or T-9.5's
  panel; what happens to a woman's live profile then is the founder's call (T-4.8). Found in
  T-4.5's plan.
  **Decided (18 October 2026, D-993):** the undo sends the person back to the `selfie` step;
  open Threads while she is back are checked in the plan. Not built yet. The plan's answers (18
  October: Threads as they are, D-995; a man may skip back to `done`; the referral reward stays
  paid) are in D-993; built after P-72.
- [ ] P-164 · Widen `verifications.similarity` to hold a cosine exactly (`numeric(6,5)`), if
  anything ever wants it there. **No deadline.** Worst case if never done: none; the exact numbers
  live in the selfie's `moderation` record (D-263), and the column stays empty. A migration, so P-65
  (landed) applies. Filed so the empty column reads as a decision, not an oversight. Found in
  T-4.5's plan.
- [ ] P-165 · Upload one photo from Safari on an iPhone and record its format from the bytes as
  they arrive. **Before REL-1** (on its Needs line). Worst case: the format an iPhone sends was
  never seen, and a format other than HEIC that gives trouble is found by a real user. T-4.6's box
  closed on two staging uploads that `complete` accepted, so not HEIC (D-089's real risk), but the
  device wasn't recorded and the bytes as received were overwritten by the worker's re-encode
  within seconds. How, the doer's to choose: `complete` already judges each upload's type by its
  first bytes, so recording that judged type (never the key, the user or the bytes) while the
  founder uploads from his iPhone settles it, and which browser he used is his to note beside it.
  At the founder's direction, 5 October 2026, in his own words; filed from T-4.5's session block
  (P-160 to P-169).
  **And the selfie step, from the same iPhone** (T-4.7, added 5 October 2026 in the text the
  founder relayed): its picture is drawn on a canvas and sent as a JPEG, so its format isn't this
  question, but the step itself was seen only in Playwright's Chromium with a fake camera. Taking
  one selfie in that session shows the camera opening on a real phone; its permission is P-123's.
- [ ] P-170 · Read `Me.balance` through `wallet.service.balance()`, not users' own `balance_of`.
  **No deadline:** both read `wallets.balance`, so no risk today, but a change to how a balance is
  read (a cache, a derived balance) would have to be made twice. Filed from T-5.3's block, as its
  plan's answers asked; rule 3 kept it out of T-5.3.
- [ ] P-171 · Make the generated types say what the API sends for a request that fails validation.
  **No deadline.** `web/src/types/api.ts` shows FastAPI's default `422` with `HTTPValidationError`
  on every route that takes a body or parameters (20 operations: T-5.3's ledger and 19 before it;
  T-5.3's report said 22, a line count that took in the schema's own definition), while the API
  answers `400 VALIDATION_ERROR` in our envelope. One gap across the whole API, so its own task.
  Filed from T-5.3's block, as the founder asked, 5 October 2026.
- [x] P-120 · Keep a distance from giving away where someone is. **Before T-6.2's `distance_km`
  reaches anyone** (on T-6.2's Needs line). Worst case: a stalker finds where a woman lives. A
  `Card`'s `distance_km` is whole kilometres, never under 1 (D-034), and anyone can put themselves
  anywhere in India at will with `PUT /me/location` (T-4.10). Read her distance from three places
  and the circles cross where she is: rounding makes each circle a band a kilometre wide, and
  readings from more places narrow where the bands overlap. **The rate limit doesn't stop it:**
  `PUT /me/location`'s 10 an hour (D-220) slows it, but three readings are enough, and a second
  account starts its own hour. The fix is the distance's, not the limit's: T-6.2 decides how, as a
  decision, for example measuring between positions the server has snapped to a grid about a
  kilometre wide, so a move finer than the grid tells nothing. Found building T-4.10; filed from
  its session block (P-120 to P-129).
  **Done, 8 October 2026, on T-6.2's branch (D-490):** the founder chose the 0.01° grid at write,
  the exact point never stored, from T-6.2's plan. Building it found the sharper leak: the radius
  filter's edge, exact to the metre whatever `hide_distance` says; on grid points both end at a
  cell. `ck_profiles_location_on_grid` refuses an exact point, `4c71a9e2b058` moved the stored
  rows (its downgrade can't restore them, and says so), and `tests/modules/profiles/test_grid.py`
  holds it.
- [ ] P-121 · Correct 03-SCHEMA §9's seed list, which still says `areas` is "40 neighbourhoods for
  the launch city". **Whenever 03-SCHEMA is next opened.** Worst case: someone sizes a picker or a
  test on 40 when there are 17. P-38 replaced Bengaluru's 40 with Phagwara's 17, and §2 says so;
  §9's line was missed. Found building T-4.10; filed from its session block (P-120 to P-129).
- [ ] P-122 · Make `tests/tools/test_selfie_review.py` count only its own rows. **Before the next
  task that touches verifications or reorders the suite** (P-48's shuffle among them). Worst case:
  a check whose verdict depends on which tests ran before it, so a reorder turns the suite red for
  no fault, or a real miscount in `selfie_review` hides behind rows another test left. Two of its
  tests (`test_every_decision_is_listed_far_from_the_threshold_too`,
  `test_the_seeds_rows_arent_decisions`) count every verification in the database, and find 2 or
  3 too many when `tests/workers` or `tests/modules/verification` runs first in the same
  invocation: `uv run pytest -m "not critical" tests/workers tests/tools/test_selfie_review.py`
  fails 2, reproduced on a clean `e0f1245`, so not T-4.10's. The full suite's order passes, which
  is why `make test` and CI are green. Found building T-4.10; filed from its session block (P-120
  to P-129).
  **Deadline passed, 8 October 2026** (the audit, P-490): T-4.12 and T-6.2 have touched
  verifications since.
- [ ] P-123 · See the location prompt work in Safari on an iPhone, and on staging over HTTPS. **No
  deadline.** Worst case: on an iPhone the prompt behaves differently, and every woman on one
  lands silently on the area picker, with nobody knowing. T-4.10's prompt, the browser's permission
  and `geolocation=(self)` were seen only in Playwright's Chromium, over plain
  `http://127.0.0.1` (J1 and its refused twin), never in Safari, on a phone, or on staging's
  HTTPS. Seen means read from what the browser did: the API's row holding a position rather than
  an area's centroid, not the screen's word. At the founder's direction, 5 October 2026; filed from
  T-4.10's session block (P-120 to P-129).
  **And the selfie camera, in the same session** (T-4.7, added 5 October 2026 in the text the
  founder relayed): `camera=(self)` and the step's camera were seen only in Playwright's Chromium
  over plain `http://127.0.0.1`. In Safari on the iPhone, over staging's HTTPS: the camera opens
  when allowed, and, refused once, the step's iPhone instructions (aA, Website Settings, Camera)
  match what Safari shows. Those words came from help pages, never a phone (T-4.7's line).
- [ ] P-110 · Guarantee-shaped claims that D-262's word list can't see. Worst case: a line
  promising protection the product doesn't give is published while `claims.test.ts` stays green,
  because the test matches words ("verif", "genuine", "guarantee"…), not promises. One is live:
  the gender screen says "Locked permanently after signup. This is what keeps fake accounts out."
  (`onboarding.gender.lock`); locking a gender doesn't keep fake accounts out. The prototype's
  selfie line, "This is what keeps fake accounts off the app", had the same shape (not used,
  T-4.7). The founder's to choose: rewrite the gender line in words it can keep, and whether the
  test gains patterns for this shape ("keeps fake", "won't pass", "stops") or a person reads every
  new string. Found in T-4.7's plan; filed from T-4.7's session block (P-110 to P-119).
- [ ] P-111 · Keep browser proofs run by hand out of the test runs' Redis databases. **Before the
  next manual proof.** Worst case: another session's `make test` fails for no real reason, a job
  taken by the proof's worker or the proof's queue emptied by the run's start-up flush, and nobody
  can trace it afterwards, since which run held which slot isn't recorded. Test runs take Redis
  databases 2 to 15, one per slot (`api/tests/infra.py`, `SLOTS`), and each empties its own when
  it starts. T-4.7's proof used 13, by mistake, on 5 October 2026 between 15:19 and 15:30 IST.
  The mistake was one session's; the trap is still there for the next. Name a database outside
  that range for proofs, and make the wrong one refuse rather than rely on remembering: a guard
  beats a rule. In the text the founder relayed, 5 October 2026; filed from T-4.7's session block
  (P-110 to P-119).
- [x] P-220 · Keep an open sheet behind the PIN lock out of reach. **Before T-6.5** (on its Needs
  line). Worst case: someone opens a sheet in the app, the lock comes up over it after five
  minutes away, and whoever picks up the phone can still Tab into the sheet, or hear it read by a
  screen reader: a report being written, a profile's ⋯ menu, whatever that sheet holds. The lock
  is a deterrent (D-069), but this is a gap in it. `Sheet` portals to `<body>` (`Sheet.tsx`), and
  the lock makes only the frame's own children `inert` (`SignedInFrame.tsx`); the lock is drawn
  over the sheet (z-50 over z-40), but nothing makes the sheet unreachable. Seen in jsdom in
  T-5.5's session: with the lock up, the page sat under `inert` and an open sheet didn't (a probe,
  not kept). T-5.5's store sheet closes itself when the lock goes up (`StoreSheet.tsx`, with a
  test); every later sheet would have to repeat that. Fix once, the doer's to choose: `Sheet`
  stays shut while `locked`, or the lock makes the portal's content `inert` too, with a test that
  a sheet open when the lock rises can't be reached. Found in T-5.5's plan; filed from its block
  (P-220 to P-229).
  **Done, 8 October 2026:** the founder chose `inert`. `Sheet` reads `useSession`'s `locked` and
  puts `inert` on its portal's root while the lock is up, so every sheet, today's and T-6.5's, sits
  under the lock out of reach and keeps what was being written in it: a sheet shut instead would
  unmount a half-written report. `StoreSheet` still closes itself on lock, with its own test; only
  its comment changed. `Sheet.test.tsx` opens a sheet, types into it, raises the lock: the dialog
  is inside `[inert]`; lowered, it isn't and the text is still there. jsdom only carries the
  attribute (it doesn't act on `inert`), as T-3.10's frame test does. Broken once: without
  `inert={locked}` that test went red; restored by file copy, SHA-256 checked, green.
- [ ] P-221 · Read a balance on the web only from the wallet query, never from `Me`. **Before any
  screen shows a balance read from `Me`.** Worst case: a screen shows `Me.balance` beside the
  header's pill and the two disagree, a money number wrong on screen, silently. `Me` is cached for
  60 s (`ME_FRESH_FOR_MS`); the pill asks `GET /wallet` again on focus and after every spend. No
  risk today: the pill and the wallet's card both read `useWallet()`, and nothing on the web reads
  `Me.balance`. Fix: stop `Me` carrying the balance, or keep it out of the web's `Me` type, so
  reading it fails `tsc`. P-170 is the API's side of the same field. Filed from T-5.5's block, at
  the direction of the advisor directing T-5.5 (Claude, in a separate chat), relayed by the
  founder, 5 October 2026, with this trigger rather than no deadline.
- [x] P-222 · Give `PinPad`'s blank cell a key of its own. **Before REL-1**, where real people
  type PINs. Worst case: React reconciles the pad wrongly on a re-render (the keys disable while
  a PIN is checked) and the 9 goes missing, or shows twice, on the lock screen or the PIN step,
  so someone whose PIN has a 9 can't type it, at the lock or while choosing it. React's own words
  for duplicate keys: children "may be duplicated and/or omitted — the behavior is unsupported".
  `KEYS` puts `""` at index 9 and keys that cell by its index, so it is `9`, the same as the
  digit 9's key (`src/components/ui/PinPad.tsx`). Seen in T-5.5's browser look (Playwright's
  Chromium against `next dev`, 5 October 2026): "Encountered two children with the same key, `9`"
  on the lock screen. Not seen: any misdrawn pad; all ten digits showed and the PIN unlocked.
  Fix: a key no digit can have (`"blank"`), and a test that the pad renders with no React key
  warning. Found in T-5.5's session; filed from its block (P-220 to P-229).
  **Done 18 October 2026:** `key="blank"`; `PinPad.test.tsx` re-renders the pad disabled and back,
  as a PIN check does, and fails on any "same key" warning (three with the index key, seen red).
- [x] P-210 · Keep `profiles.completeness` current after onboarding finishes. **Before T-6.2 ranks
  by it** (on T-6.2's Needs line). Worst case: discovery ranks people by a number that no longer
  describes their profile, and the ranking D-030 promises to explain in plain words doesn't do what
  it says. Someone who adds five photos after finishing stays at 50; someone who removes all but
  one keeps the higher number. T-4.8 computes it once, at `done` (D-310), and asking
  `POST /me/onboarding/complete` again recomputes nothing, by design. What changes it after that:
  a public photo approved later (T-4.4's decision), one removed (`DELETE /photos/{id}`), and
  anything a later task adds to the formula. How, the doer's to choose: recompute it in each of
  those writes with `onboarding.rules.completeness`, under the user's row lock each already takes,
  or have the ranking compute it from the photos as it queries. Found in T-4.8's plan; filed from
  T-4.8's session block (P-210 to P-219), at the direction of the advisor directing T-4.8 (Claude,
  in a separate chat), relayed by the founder, 5 October 2026.
  **Done, 8 October 2026, on T-6.2's branch:** the founder chose the recompute in each write, from
  T-6.2's plan. `onboarding.service.refresh_completeness`, under the user's row lock, runs in
  moderation's approval (`photos.service._record`) and in `delete_photo`, only once onboarding is
  `done`; turning a shown face photo off is `delete_photo` on its copy. Its weakness, a later write
  path that forgets, has a pointer line on T-9.5, whose moderation queue rejects approved photos.
  `tests/modules/photos/test_completeness.py` holds it.
- [ ] P-260 · Hold the moderation provider to one Sightengine endpoint at the source, not only
  per check. **Before any second call to Sightengine is written** (a moderator's override sent to
  the Feedback API is the likely first). Worst case: `/privacy`'s "deleted there after the check"
  (D-048) goes false the day a `feedback()` method lands, every test green. Sightengine keeps a
  file sent to the Feedback API (its FAQ, quoted on T-4.4), and
  `test_every_request_stays_on_the_plain_image_api` sees only the requests `check()` makes: a
  method of its own posting to `feedback.json` never passes through it. `t44-15`, `t44-16` and
  `t44-19` each break the check request; none adds a second call. Nothing else in the repo holds
  `app/core/providers/moderation.py` to one endpoint (grepped 7 October 2026). Fix, the doer's to
  choose: a test that the module names `api.sightengine.com` once and posts once, to `CHECK_URL`;
  or every request routed through one method the test wraps; and a `t44-` case that adds a
  `feedback()` method and must go red. Found closing T-4.4's retention box, 7 October 2026; filed
  from that session's block (P-260 to P-269).
- [x] P-261 · `/done` describes its own landing guard wrongly: step 1's check can never be the
  one the push reads. **Before the next `/done` someone follows to the letter.** Worst case: a
  session does what the document says, the push to `main` is refused, and the refusal is read as
  the guard misbehaving, or answered with `--no-verify` (which CLAUDE.md "Landing" and the
  document's own next sentence forbid). `.claude/commands/done.md`, step 9, line 23, word for
  word, the sentence running onto line 24: "The push itself refuses unless step 1's `make lint
  test` passed on this exact commit's tree and CI passed for it". Step 1 runs `make lint test`
  before step 4 commits, so on a tree with the task's changes uncommitted, by design.
  `scripts/mark-checked`, which writes the mark `push-gate` reads, answers that run, word for
  word: "mark-checked: make lint passed with changes not committed: not marked for landing.
  Commit, then run it again." (and the same line for `test`). So the run step 9 names never
  writes the mark step 9 says it did, and no step of the document runs the checks on the
  committed tree. The script's own header already says so: "a working tree with any change, or
  a tree that moved while the check ran, gets none, and says why". The document contradicts its
  guard. Seen 7 October 2026, landing T-4.4's retention box: step 1's run was answered with
  that line. Fix: move `make lint test` to after the commit, between step 4 and step 7, its exit
  code read on its own (CLAUDE.md "Shell traps" 1), and reword line 23 to name that run; step 1
  may stay as an early stop on a failure, but the document must not say its run is what the push
  reads. `done.md` is outside T-4.4's scope (rule 3), so filed, not fixed. Found closing T-4.4's
  retention box, 7 October 2026; filed from that session's block (P-260 to P-269).
  **Done 8 October 2026 (P-490):** the checks run once, after the commit, as `/done`'s step 4, its
  exit code read on its own; step 1's run is gone, steps 2 to 4 moved up one, and step 9 names step
  4's run. Steps 5 to 10 kept their numbers, so the manual path's "steps 9 and 10" holds. Once, not
  twice, by the founder's choice (8 October 2026): `make test` is the longest step, and two runs
  double every landing's wait.
- [ ] P-280 · The liveness measurement set: 30 consenting people, 1,350 captures, on the real
  capture path. **After launch** (the founder, 7 October 2026, D-380's third decision; it was
  T-4.11's accuracy half, and T-4.11 can't tick that half without it). Worst case while it is
  missing: a liveness check ships on a README's accuracy number, "a weak check that looks like a
  strong one" (the founder, 4 October 2026), because the one standard that stops it, accuracy
  measured on our own attacks against consenting people (T-4.11's research line, D-088's way), is
  a measurement nobody has made; and nothing stops it but the founder's refusal to ship without
  one (D-260 shows he has shipped face matching unmeasured, on his own word, so this is his
  standard, not a mechanism). **The set, as T-4.11's research designed it** (Claude, 5 October
  2026), the founder's to change: 30 people who agree in writing, at least 15 women, spread the
  way T-4.5's dropped set was (skin tones, glasses, beards, a dupatta, a turban, since the model
  learned from other faces), each giving 45 captures, 1,350 in all: 10 real selfies (2 phones,
  their own and a cheap Android, in 5 conditions: window light, a tube light at night, low light,
  outdoors, as they usually look); 10 print attacks (an A4 printout and a glossy print, flat and
  curved, at several distances); 10 screen attacks (their photo on a phone and on a laptop, bright
  and dim); 10 replay attacks (a video of them played on a phone and a laptop); and 5 injections,
  their real selfie sent straight to the API, **which must pass**, so the gap D-380 names is shown
  by its effect, never assumed. One or two people genuinely trying to beat the model, not going
  through the motions. **The capture path is the real one,** T-4.7's screen or exactly its steps
  (`getUserMedia`, a canvas, a JPEG, our q85 re-encode): MiniFASNet reads fine texture and
  frequency, which a JPEG chain erases, so a phone camera app's photos would flatter it. **The
  threshold is chosen on the real selfies only** (the lowest refusing at most 5% of real people,
  T-4.5's rule) and the attacks counted at that threshold; chosen on the attacks it would flatter
  the result. Why these numbers (exact binomial bounds, Claude, 5 October 2026): 30 people, since
  errors cluster by person and a trait 10% of users have (a turban, a dupatta over the hair, a
  dark skin tone under a tube light) appears in 30 people with 95.8% probability and in 20 with
  87.8%; 300 real selfies, since a 5% refusal rate then has a 95% interval of 2.8% to 8.1%, tight
  enough to apply the 5% rule; 300 of each attack, since zero passes bound the per-try rate at
  1.0% and two passes at 2.1% (one-sided 95%), and an attacker gets 5 tries a day (D-263), so at
  5% a try he is through within a week 83.4% of the time and at 1% 29.7%. **Its honest limit:**
  per person, 0 breached of 30 bounds the rate at 9.5%, no lower; "nobody can be impersonated"
  can't be shown at this size, and passive liveness slows a stubborn attacker, never stops him.
  Consent in writing; never a user's data; stored privately, used for nothing else, deleted when
  the founder says; and **never inside the repository:** the probe's faces guard refuses a
  directory inside it or any worktree of it (`api/bench/liveness/run.py`, `faces_dir`, tested),
  so the set lives outside, where no `git add` can take it. Cost: about 7.5 hours of capture (the
  advisor's estimate, unmeasured) plus gathering 30 people. Filed by Claude from T-4.11's research
  (5 October 2026), at the founder's direction, 7 October 2026; its session's block, P-280 to
  P-289.
- [ ] P-281 · Hold the worker to one image at a time by a check, not a comment. **Before anything
  moves decoding or inference off the event loop, and before T-4.11 builds** (a third model in
  the same process). Worst case: the worker is killed by the kernel in the middle of a
  verification; ARQ tries its running jobs again; and, since `restart = always`
  (`infra/fly.worker.toml`), it comes back, takes the same four heavy jobs and is killed again, a
  crash loop that leaves every upload and every selfie pending. The loop isn't measured, only
  possible; the kill is measured. **Today this is a comment, not a check:**
  `app/workers/main.py:64-66` says, with its reasons and citing D-092 and D-088, that decoding is
  synchronous on the event loop, so only one image is ever decoded at a time whatever `MAX_JOBS`
  (line 67, 4) says. True today. A comment can't go red: the day inference or decoding moves to
  `asyncio.to_thread`, `MAX_JOBS = 4` overlaps for real, the comment is false, and no test fails.
  **Measured** (Claude, 5 October 2026, and again on 7 October with the committed probe,
  `api/bench/liveness/run.py baseline --at-once 4`; this Mac's arm64 Docker, one CPU, 1 GB: not
  Fly, where 962 MB is usable): one YuNet + SFace set, 191 to 195 MB resident; four threads, each
  with a set of its own, since OpenCV's model objects can't be shared across threads, 368 MB
  before any comparison; four concurrent face-match comparisons, swap allowed, peak about 1,060 MB (1,062 to 1,064 observed); swap
  off, as Fly runs it, the process is killed, exit 137, with face matching alone. **Two things not
  measured:** the overlap of two decodes (the probe's threads overlap whole comparisons); and two
  calls on one shared model object, which is what `asyncio.to_thread` with a single model set
  would do: there the memory is less than four sets', so the hazard is thread safety, not memory,
  and nothing above speaks to it. **The memory numbers are the probe's, not a property of the
  worker:** its baseline varies 392 to 406 MB from run to run with no code change (T-4.11's
  research line), so read them as about 400 MB a comparison and about 1,060 for four, never as
  exact. **Fix, the doer's choice:** a test that forces the overlap (four jobs whose compare is
  held on an event, then an assertion that at most one is inside the decode or the inference at
  any moment), or an explicit semaphore of one permit around decode and inference that a test can
  hold; a test that doesn't force the overlap stays green with the guard removed, which is to say
  it isn't a check. Filed by Claude from T-4.11's research (5 October 2026), at the founder's
  direction, 7 October 2026; its session's block, P-280 to P-289.
- [x] P-282 · CI minutes: no duplicate run on `main`, e2e only when code changes, and the
  cancel-in-progress that already exists kept off `main`. **Before the next week of several
  sessions landing at once.** Worst case, seen 7 October 2026: GitHub Free's 2,000 Actions
  minutes a month (D-280) ran out mid-week, at 481 runs that week and about 800 billed minutes a
  day (the founder, from the billing page); GitHub then refuses to *start* a job and closes a
  green run as "failure" (run 37641734875 for `6e6392b`: api, web, image and repo green, `e2e`
  never created, "failure" seven seconds after api finished, and HTTP 500 to a re-run), the gate
  reads exit 1 as it must, and every session is blocked at once with nothing to fix on any
  branch, until the founder raises the spending limit, which is what happened. **What a run
  costs, each job rounded up to the minute as GitHub bills it** (read by Claude from the runs
  that day): `main`'s run 37611479267 for `68c3078`, 17 minutes (api 5, e2e 5, web 3, image 2,
  repo 2); the branch run 37641734875, 12 without e2e (api 6, web 2, image 2, repo 2); a docs-only
  commit pays the same 17; and the `timing` endpoint answers 0 ms for every run, so the billing
  page, not the API, is the number to trust. **Three cuts, each with the gate it touches, since
  every one of them reads CI:**
  1. **No second run on `main` for a commit CI already checked.** Landing is a fast-forward to a
     commit whose branch run the gate read (ci-gate, P-140), so `main`'s run repeats 17 minutes
     for nothing. The coupling: the staging deploy fires on `workflow_run` of CI on `main`
     (`deploy.yml:21-24`, `conclusion == 'success' && event == 'push'`) and then runs
     `scripts/ci-gate --branch main "$SHA"`, and `release-gate` reads `main` too (D-075). So
     `main`'s workflow can't be skipped: it must still complete, green, for that SHA. The shape
     that keeps both: on `main`, one short job that asks GitHub for a passed CI run of exactly
     this SHA on a branch of this repository (never the newest run, never another SHA: P-140) and
     succeeds only then, so the deploy still fires and the gates still read a green run of the
     SHA on `main`; with no such run it fails closed and `main`'s full CI runs instead. About 15
     of 17 minutes saved per landing; proved by a landing whose `main` run shows one job, a deploy
     that still fired, and `ci-gate --branch main` reading it as passed; and by the fail-closed
     case, a commit pushed to `main` with no branch run, refused.
  2. **Cancel-in-progress per branch: already there** (`ci.yml:18-20`,
     `concurrency: ci-${{ github.ref }}`, `cancel-in-progress: true`), so a second push to a task
     branch cancels the first's run, and a cancelled run reads as exit 1 in ci-gate, so nothing
     lands on one. **What it gets wrong:** the group is per ref with no exception, so a push to
     `main` while `main`'s run is in flight cancels that run, and the deploy, which fires only on
     `conclusion == 'success'`, never fires for the cancelled commit: the next landing deploys
     both, or nothing deploys until someone notices. Make it `cancel-in-progress:
     ${{ github.ref != 'refs/heads/main' }}`; proved by two pushes to `main` in quick succession
     (on a scratch branch named like it in a test, or once, deliberately), both runs completing.
  3. **e2e only when code changed.** A docs-only commit pays e2e's 5 minutes (and the 12 of the
     rest). Gate e2e on the paths changed since the push's `before` SHA (the merge base with
     `main` when `before` is zeros, a new branch), by an **allowlist of paths that can't reach a
     journey** (`docs/**`, `**/*.md`, `.claude/**`), never a list of what counts as code (rule
     16): anything not on the allowlist runs it. A skipped job leaves the run's conclusion
     `success`, which ci-gate and the deploy both read as today. The coupling: P-180's required
     status checks, once GitHub Pro allows them, must not name `e2e` as required, or a skipped
     e2e blocks every docs commit; name the jobs that always run. Proved by a docs-only push
     whose run shows e2e skipped and the gate passing, and a one-line code change whose run shows
     e2e run.
  Not in it: skipping api and web on docs-only commits too (another 11 minutes): a separate
  question with couplings of its own, and the `repo` job, whose pre-commit pass reads every file,
  docs included, runs either way. Filed by Claude at the founder's direction, 7 October 2026,
  from the day's outage; its session's block, P-280 to P-289.
  **Done, 8 October 2026** (the founder's approval of the plan that morning, on the advisor's
  recommendation, Claude in a separate chat, relayed), as D-410 records it: `scripts/ci-vouch`
  and the `vouch` job, `scripts/ci-e2e-needed` and the `api` job's verdict that gates `e2e`,
  and `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`; each script with its test
  beside it, run by `repo`. `deploy.yml`, `ci-gate`, `release-gate` and `push-gate` are
  untouched. **The one deviation, confirmed by the founder:** on a branch the journeys' diff
  is measured from the merge base with `main`, not the push's `before`, because a code push
  whose run a quick docs push cancelled would leave the branch tip with no e2e run on its
  tree, since the second push's diff is docs only; on `main`, `before`, with zeros or an
  unknown SHA running them. **Each cut broken to show it works**, on two scratch branches
  carrying the landed workflow with `refs/heads/p-282-proof` in place of `main` in its three
  expressions and nothing else different (the diff was read before each push), both deleted
  after:
  - **Cut 1, the vouch (wiring and gate).** `e379c9d`, whose run on the ordinary branch had
    passed with e2e (run 37686012553), pushed to the main-like branch: run 37687698856, the
    `vouch` job alone, six seconds of work (`ci-vouch: run 37686012553 on p-282-proof-src
    passed 'CI' for e379c9d: it vouches`), five jobs skipped, the run `success` ten seconds
    after it was created, and `scripts/ci-gate --branch p-282-proof e379c9d` read it: "CI is
    green for e379c9d (run 37687698856)", exit 0. **Fail closed:** `9e65ed0` and `54a15cd`,
    pushed straight to the main-like branch with no branch run, ran the full CI (runs
    `37687846099`, `37687894968`: `ci-vouch: No completed, passed push run of 'CI' … on a branch
    other than p-282-proof`, `vouched=false`). On real `main`: `22aeab7`, this task's code commit, landed through the push gate on its branch run 37691150742 (full CI, e2e run, since code changed); `main`'s run 37732453666 was the `vouch` job alone (`ci-vouch: run 37691150742 on p-282-ci-minutes passed 'CI' for 22aeab7: it vouches`), the run `success` twelve seconds after it was created; the staging deploy 37732473688 fired on it and passed, smoke check included; `scripts/ci-gate --branch main 22aeab7` read it green, exit 0; and `scripts/release-gate 22aeab7`, run by hand, read both: "CI passed for 22aeab7 (run 37732453666)", "staging deployed 22aeab7 and its smoke check passed (run 37732473688)".
  - **Cut 2, no cancel on `main`.** On the ordinary branch, a push on the heels of another
    cancelled the first's run three times (37684498515 at 20:45:52, one second after the
    next run was created; 37685359884 at 20:52:55; 37685363443 about a minute after the
    third push, GitHub's own lag), so the expression is true off `main`. On the main-like
    branch, `54a15cd` pushed while `9e65ed0`'s jobs were running: its run 37687894968 sat `pending` for five minutes while 37687846099 ran to the end, then ran, both `success`; nothing cancelled.
  - **Cut 3, e2e only off the allowlist.** `9e65ed0`, docs only, straight to the main-like
    branch: run `37687846099`, `api` named `docs/p-282-proof.md` allowlisted, `e2e=false`, the
    `e2e` job skipped, the run `success`. `54a15cd`, one line in the `Makefile`: run
    `37687894968`, `Makefile` outside, `e2e=true`, the journeys ran and passed. On a branch,
    the real case: this tick commit's own branch run skipped e2e on a docs-only diff from `main`.
  - **A trap the first proof run found (37684502234):** GitHub carries a skip down the whole
    needs chain, so `vouch`, skipped on every branch, skipped `e2e` too, however green `api`
    and `web` were and with `e2e=true` printed, because `e2e`'s condition had no status
    function. Fixed before anything landed: every job below `vouch` opts out with
    `!cancelled()` and names the results it needs (D-410, 06-TESTING).
  **What it saved, each job rounded up as GitHub bills:** 7 October's ten CI runs, five
  landings, all docs-only, cost 189 minutes, 36 to 38 a landing; the same day with the three
  cuts would have cost 71. This landing's own: 19 minutes, the branch run 18 (repo 2, api 5, image 2, web 3, e2e 6) and `main`'s run 1, against 36 to 38 the day before; a docs-only landing is about 14 (this tick's own run says). The proof cost 97
  minutes on the scratch branches, against about 50 planned: one run repeated for the
  needs-chain fix, one cancelled by hand a moment after it started and re-run. Also noted on
  the way: CLAUDE.md's shell trap 5, zsh's read-only `status`. Built by Claude, 8 October
  2026; its session's block, P-310 to P-319 and D-410 to D-419, of which D-410 is used.
- [x] P-290 · Decide whether discovery's ranking keeps its `is_verified` boost for a profile whose
  badge is hidden. **Before T-6.2 writes `rank_score`.** Worst case: two rules that look like one.
  D-032 (Locked) ranks by `is_verified`, the selfie's match; D-393 shows the badge only with a
  shown face that matched the selfie. So a woman with a matched selfie and no shown face is
  ranked as verified and shown without a badge, and a reader of the two entries can't tell which
  rule discovery means, or whether the boost is a claim D-262 forbids. **The advisor's opinion
  (Claude, in a separate chat, relayed by the founder, 7 October 2026): leave D-032 alone.**
  Ranking is not a claim; D-262 is about copy. `is_verified` is a real check, the selfie matched,
  and the boost is that check's; the badge is a separate, stricter condition. And a profile with
  no photo sits at the bottom anyway, at completeness 50 (D-310, D-392). The founder decides;
  D-032 is Locked, so a change supersedes it with a new entry. Filed by Claude while filing
  T-4.12, 7 October 2026; its session's block, P-290 to P-299.
  **Answered 8 October 2026** (the founder, on the advisor's recommendation, relayed by the
  founder): D-032 stands as it is. The `is_verified` boost stays whether or not the badge shows;
  ranking is not a claim, and D-262 is about copy. T-6.2's score carries it (D-491), and
  `test_is_verified_ranks_whether_or_not_the_badge_shows` holds it.
- [ ] P-350 · Register for GST within 30 days of aggregate turnover crossing ₹20 lakh in a
  financial year; at that moment, the CA answers the voucher-timing question (GST at sale or at
  spend), and a task flips `GST_REGISTERED`, adds the GST line to receipts, and files the timing
  rule as a decision. **Owner: the founder. Trigger: T-8.1's turnover counter and its alert at
  ₹15 lakh.** Worst case first: the threshold is crossed and nobody notices. Registration is
  then late, and penalty and interest run from the first day over, on sales already made at an
  inclusive price with no tax set aside, and nothing in the product would have said a word.
  That is why T-8.1 builds the counter and the alert alongside the first order: without them
  the threshold can't be known, and this task has no trigger. **What the day looks like:** the
  counter passes ₹20 lakh; the founder registers within 30 days of the crossing (the figure as
  the founder relayed it from the CA, 8 October 2026) and asks the CA the timing question,
  which doesn't arise before (D-450, point 5); then one task flips `GST_REGISTERED` on, sets
  `gst_rate_bps` to 1800, splits each new payment's inclusive `amount_paise` into Velora's share
  and `gst_paise` (₹1,500 into ₹1,271 and ₹229, D-450; the paise rounding is that task's to
  settle), puts the GST line, the rate and the GSTIN on the receipt, and files the timing rule
  as a decision in its own block. The price a user pays doesn't move (D-099, D-450). Filed by
  Claude at the direction of the advisor (Claude, in a separate chat, relayed by the founder),
  8 October 2026; its session's block, P-350 to P-359.
- [x] P-330 · The wake listener says "subscribed" before Redis does, and `test_wake.py`'s first test
  can go red on a commit that never touched it. **Before the next landing that hits it; the fix is
  a line in `app/workers/wake.py` and a test.** Worst case first: a red CI on a docs-only commit,
  and a landing that re-runs until green, which teaches every session to shrug at red (P-140's
  silent direction). Seen 8 October 2026 on a5f650c (run 37685930558), three docs commits:
  `test_it_hears_a_wake_and_hands_on_the_id` got `publish(...) == 0` where it expects 1; 2,085
  passed, and locally the same tree passed twice. **Why:** `WakeListener._listen` sets its
  `subscribed` event right after `await pubsub.subscribe(channel)`, but redis-py's
  `PubSub.execute_command` only sends the command (`connection.send_command`) and reads the
  server's confirmation later, as a message `get_message` then ignores. So the event fires before
  the server holds the subscription, and a PUBLISH from another connection in that window finds
  0 subscribers. On a loaded runner the window is wide enough; on this Mac it wasn't, twice.
  **The product isn't at risk:** the worker's listener runs for the life of the process,
  subscribed long before any wake, and a missed wake is caught by the 10 s poll (D-091, D-261).
  **Fix:** set `subscribed` only after reading the subscribe confirmation
  (`get_message(ignore_subscribe_messages=False)` until a `subscribe` message arrives), and a test
  that publishes the instant the event is set, many times over, and never sees 0. Filed by Claude
  landing P-57, P-150 and D-253, 8 October 2026; its session's block, P-330 to P-339.
  **Seen again, 8 October 2026 (P-490):** 2 failures in 21 runs of `test_wake.py` on `447a045`, a
  docs-only commit, with three other sessions' pytest runs going and the machine at about 330% CPU.
  Once in a full `make test`: `test_what_isnt_an_id_is_ignored_and_it_listens_on` got no
  `wake.not_an_id` log, its first PUBLISH lost in the same window. Once in 20 runs of the file
  alone: the reconnect test, after `client_kill_filter`, timed out waiting to hear its id, which
  fits the window reopening when the listener subscribes again (inferred, not observed). So the
  window hits more than the first test.
  **Seen twice more, 8 October 2026, in T-6.6's local `make test` (only the API half's
  non-critical run; CI green on the same commits, 37778006933 and 37779494195), while other
  sessions' pytest ran on the Mac (load average about 4):**
  `test_a_dropped_connection_is_made_again` timed out at `heard.next()` (10 s) after the
  re-subscribe, on c94033f; and `test_what_isnt_an_id_is_ignored_and_it_listens_on` heard the id
  but never logged `wake.not_an_id`, so the first publish found nobody subscribed, on 12c2534.
  The file passed 5 of 5 run alone (8 tests, about 1 s each). Both fit the cause above.
  Recorded by Claude landing T-6.6, at the founder's direction.
  **Closed (approved by the founder on the advisor's
  recommendation, 8 October 2026):** `_listen` reads messages until Redis's `subscribe`
  confirmation arrives, and only then sets `subscribed`, on every connection, a reconnect's
  included, so all three failures above lose their window. `test_wake.py`'s
  `test_subscribed_means_redis_holds_the_subscription` subscribes through a loopback proxy that
  holds the worker's bytes for 0.2 s, as the road to Upstash does, and publishes the instant the
  event is set, for three listeners, each before and after its connection is killed: the window
  is made wide on purpose, so the test doesn't wait on a loaded machine to show it. On the old
  code it published to 0 subscribers (`assert 0 == 1`), and with the confirmation wait removed
  again, once, the same. `test_wake.py` then ran 30 times on this Mac, its load average 2.8 at
  the start and 4.9 at the end: 30 green, 9 passed each, 7.76 s to 8.79 s.
- [ ] P-300 · Retry, or sweep for, a shown photo's badge comparison that failed its last try.
  **Before REL-1's tag, if it includes T-6.2** (the badge on cards). Worst case: a real woman's
  only shown face is approved while storage hiccups three times in a row (`match_photo`'s three
  tries over 30 seconds), the comparison is never made, and her card carries no badge though her
  selfie matched and her face is shown, until she removes and re-adds the photo. T-4.12 logs the
  last failure at error level and leaves the photo as it is: the badge rests only on comparisons
  that were made. Options: a periodic sweep on the worker for approved public photos with
  `faces >= 1`, a kept selfie and no `selfie_match` for its verification, queued one at a time
  (P-281); or `match_photo` with more tries, spaced wider. Filed by Claude while building T-4.12,
  8 October 2026; its session's block, P-300 to P-309.
- [x] P-301 · Make a private photo's served copy the bytes moderation scored, as a public photo's
  is. **Before T-8.4 serves private photos to anyone.** Worst case: a presigned PUT URL lasts five
  minutes and outlives `complete` (P-79); for a public photo T-4.4 publishes the scored bytes, so
  a second PUT over the raw key changes nothing anyone sees, but a private photo has no second
  copy: its raw key is what T-8.4 would sign a link to, so a PUT after approval, inside the window,
  shows a chosen viewer bytes nobody scored. The face photo met the same window in T-4.12, which
  is why its shown copy goes through moderation rather than being approved from the private copy
  (D-400). Options: the worker writes an approved private photo's scored bytes to a key no PUT
  URL ever covered and the row points there; or `complete` revokes the window by moving the
  object. Found building T-4.12; filed by Claude, 8 October 2026; its session's block, P-300 to
  P-309.
  **Placed 8 October 2026 (the audit, P-490):** on T-8.4's Needs line.
  **Closed 8 October 2026 by P-79's build (D-700):** the first option, the same change; its
  evidence is on P-79.
- [x] P-370 · Move the `liked_you_reveal` row from 20 to 1 Vela, by a data migration. **Before
  T-6.7, on its Needs line.** Worst case first: the founder set the reveal at 1 Vela (8 October
  2026, D-004's note), but the price is a row, and every database holds 20, written by T-1.14's
  `fa16c0908c2c`. Editing the docs changes nothing that is shown or charged: T-5.5's price list
  reads the row (`GET /prices`), so it shows 20 wherever it runs, and T-6.7, built against the row
  as it must be, would charge twenty times the price set, Velas a man can't get back (D-230).
  **The work:** a data migration of its own (rule 11; T-1.14's is never edited),
  `liked_you_reveal` 20 → 1, reversible; `tests/test_reference_data.py` and
  `tests/modules/pricing/test_router.py`, which both hold 20; and 03-SCHEMA's note, which then says
  the row has moved. `web/src/components/wallet/WalletScreen.test.tsx` holds 20 as a stand-in for
  the API's answer; this task says whether it follows. Filed by Claude
  at the direction of the advisor (Claude, in a separate chat, relayed by the founder), 8 October
  2026; its session's block, P-370 to P-379.
  **Done 8 October 2026:** `e4e517f62ce3` moves the row to 1 and its downgrade puts 20 back; a
  test in `test_reference_data.py` holds both, with every other row unchanged. The two tests
  named, and `tests/modules/pricing/test_service.py`, which held 20 too, say 1, so T-5.5's price
  list (`GET /prices`) is held at 1. `WalletScreen.test.tsx` follows, since it stands in for that
  answer, and asserts each row's action and price apart, as a person sees them. Not a bug to
  file: the row's markup, read once in Playwright's Chromium (a one-off reading, not a committed
  check), gives `innerText` "See one person who liked you\n1 Vela" and an accessible text with a
  space between; only jsdom's `textContent` runs them together. 08-DESIGN's "Reveal · 20 Velas"
  pill is now 1, read from `/prices`; D-099 notes that its number to watch falls on a man's second
  Thread (both the founder's, 8 October 2026). `api/seed/` holds no price.
- [x] P-371 · Welcome Velas: can one person collect them again and again? **Answered by the
  founder, 8 October 2026, on the advisor's recommendation (Claude, in a separate chat), relayed;
  recorded in D-470.** The question, found filing T-8.11: one number holds one account at a time
  (`users.phone_hash` is unique) and one account one grant (the ledger's per-event index), and
  D-072's hash is written only when a date of birth is refused, so it stops nothing here. Two ways
  were left open:
  1. **A fresh number per account: accepted.** Each fresh number gets its 5, one Thread's worth,
     a free first message to a woman per number. Velas can't move between accounts (D-076), so
     many numbers make many single Threads, never one balance. The founder chose this knowing
     it, and D-470 says so.
  2. **Re-registering on the same number: closed.** One welcome per phone number, ever: a hash of
     every number that received a grant is kept, as D-072 keeps one, and survives T-9.6's
     anonymisation, so a later account on that number gets no grant. T-8.11 builds it, with a
     test (grant, delete, sign up again after 30 days, no second grant); T-9.6 carries the
     pointer.
  Filed and answered the same day, so T-8.11 isn't blocked on it. Filed by Claude; its session's
  block, P-370 to P-379.
- [x] P-380 · Grant the first-purchase bonus only to a man's first paid payment, decided at
  capture, not only at order. **In T-8.2, which credits it.** Worst case: a man opens two
  checkouts before paying either; T-8.1 computes the bonus at order time, when neither is paid, so
  both rows carry it, and if he pays both he is credited it twice, up to 90 + 90 Velas on two
  ₹10,000 packs, with nothing in the ledger saying it shouldn't be. The fix belongs where Velas
  are granted: T-8.2's capture grants `purchase_bonus` only if no other payment of his is paid or
  refunded, in the same transaction, the wallet row locked (D-077). Found building T-8.1; filed
  by Claude, 8 October 2026; its session's block, P-380 to P-389. **Closed by T-8.2 (D-522):** the
  capture decides it under the wallet's lock, and a race test forces two captures of one man into
  overlap and asserts one bonus.
- [x] P-381 · Route the daily turnover line to the alert channel. **In T-9.12.** Worst case:
  turnover passes ₹20 lakh, `log_turnover` logs an error every morning to Fly's logs, which nobody
  reads and which rotate out in about 25 minutes, and registration is late, with penalty and
  interest from the first day over (P-350). Until T-9.12 the line is the only alarm (D-483), the
  same gap as D-066's OTP warning. The founder can read the figure meanwhile at
  `GET /v1/admin/turnover`. Filed by Claude building T-8.1, 8 October 2026; its session's block,
  P-380 to P-389. **Closed by T-9.12 (D-1002):** `payments.turnover` goes to Sentry at warning from
  ₹15 lakh and at error from ₹20 lakh, two issues so the second alerts though the first is open;
  info below stays in the logs (`test_the_turnovers_warning_and_error_are_two_issues`).
- [ ] P-382 · Require `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and, since T-8.2,
  `RAZORPAY_WEBHOOK_SECRET` at startup where `PAYMENTS_PROVIDER` is `razorpay`. **When P-0.8 gives Velora a Razorpay account, before the
  keys go into Fly.** Worst case: a deploy with a key missing or mistyped starts cleanly, every
  checkout fails with `PROVIDER_UNAVAILABLE`, and the first anyone hears of it is a man who
  couldn't pay. Today the API can't require them: staging and production run Razorpay, and with
  no account there are no keys to set, so T-8.1 refuses each order instead of refusing to start
  (02-ARCHITECTURE §11). The check names each missing key, never a value,
  as the storage check does. Filed by Claude building T-8.1, 8 October 2026; its session's block,
  P-380 to P-389. **Extended by T-8.2 (the founder, 8 October 2026, approving its plan):** without
  the webhook secret every webhook is refused, `400`, with an error log naming the setting, so a
  deploy missing it takes men's money and credits nothing until someone reads that line; the
  startup check names it too.
- [ ] P-390 · Check Supabase's `jit` setting and the feed's real time on staging. **Before REL-1;
  not blocking T-6.2.** Worst case first: production's feed takes several times what the bench
  measured, because the bench ran on the local Postgres 16, not Supabase's 17, and JIT alone moved
  T-6.2's query from about 112 ms to 399 to 575 ms there (psql, 8 October 2026). The feed turns JIT
  off for its own transaction (`SET LOCAL jit = off`, D-495), so this checks that the setting
  takes on Supabase as it does locally (a role or pooler setting can override it), and reads the
  feed's time where it runs: `EXPLAIN (ANALYZE)` of the feed's statement on staging with a
  crowd in a scratch schema or database of its own, never `velora`'s rows, and the API's request
  time for `GET /v1/discover` in its logs. Records the numbers, ranges across runs, beside T-6.2's.
  Filed by Claude at the founder's direction (8 October 2026, on the advisor's recommendation,
  relayed), building T-6.2; its session's block, P-390 to P-399.
- [ ] P-391 · Rank the feed by grid cell first. **Before any city passes 10,000 eligible profiles,
  or when P-390's staging numbers say so, whichever comes first.** Worst case first: one city
  nearing tens of thousands of people makes the deck slow, about 200 ms a page at 50,000 within
  25 km (T-6.2's bench, D-495), and slower as it grows, because the feed scores every eligible
  candidate on every request. The fix: positions are grid points (D-490), about 1,800 distinct in
  a crowded city, so rank cells first, nearest outward, and score only the people in enough of
  them to fill a page and its cursor, keeping D-491's ranking and every exclusion. D-495 records
  what doesn't work, a nearest-N window by the GIST index's order, and why: read it first. The
  trigger needs a count: how many eligible profiles a city has, from a query T-9.5's metrics or
  a check by hand can run. Filed by Claude at the founder's direction (8 October 2026, on the
  advisor's recommendation, relayed), building T-6.2; its session's block, P-390 to P-399.
- [x] P-400 · Stop a blocked person getting around the block by deleting and signing up again.
  **Before T-9.1** (on its Needs line). Worst case: a harasser someone blocked deletes their
  account, waits out T-9.6's 29 days, signs up again on the same number, and reaches the person
  who blocked them as a stranger, in their discovery feed and search. A block names the old
  `user_id`, and the erasure keeps the other person's block of it (D-503), but the new account is a
  new id that no block names. The number's hash survives on the erased row (D-500), so T-9.1 can
  carry a block to a later account on the same number. What T-9.1 decides: whether a block holds
  against the number as well as the account, and how that is told to nobody (a block is silent).
  Filed by Claude building T-9.6; the founder put it on T-9.1's Needs line, 8 October 2026. Its
  session's block, P-400 to P-409.
  **Done 9 October 2026 (T-9.1, D-861):** a block holds against the number, matched through
  `users.phone_hash`, the founder's answer; nobody is told. `test_block_number.py` erases a
  blocked man, signs his number up again, and finds the new account blocked both ways everywhere.
- [x] P-401 · Decide what a ban landing during a deletion's 29 days does to the erasure. **In
  T-9.5, where bans are written.** Worst case: someone deletes their account, a moderator bans it
  the next day, and the erasure never runs, because it erases only `deleted` accounts. Their
  photos, profile and number's encrypted copy are then kept indefinitely, against what `/privacy`
  told them. Or, the other way, the erasure runs on a banned
  account and takes the photos a moderator was about to look at. T-9.6 erases only `deleted`
  accounts, so a ban today keeps everything (`deleted_requested_at` stays set as the record of
  the request). Filed by Claude building T-9.6, 8 October 2026; its session's block, P-400 to
  P-409.
  **Answered in T-9.5 (D-929), the founder's answer in its brief:** a ban stops the erasure and
  keeps the data, today's behaviour, written down; lifting the ban returns the account to
  `deleted`, so the erasure runs then (D-922).
- [x] P-420 · Make a reversal that found nothing to take a repeat too. **In T-8.3, or a task of
  its own: the founder's call.** Worst case: a refund or dispute reaches a man who has spent every
  Vela of that payment, so `wallet.reverse()` takes 0 and, by design, writes nothing (a ledger
  entry can't be 0, `ck_ledger_entries_delta_non_zero`); the shortfall is logged, and on a dispute
  signalled. If Razorpay redelivers that same event after he has bought Velas again, nothing marks
  it as handled, so the redelivery takes from the new Velas, up to the shortfall, and a dispute
  records its signal a second time. Razorpay retries for about a day, so it needs a redelivery
  and a new purchase inside that window. One way: record each refund or dispute id handled, on the
  payment or in a small table, and treat a known id as a repeat. Found building T-8.2 (D-520);
  filed by Claude, 8 October 2026; its session's block, P-420 to P-429. **Closed by T-8.3 (D-581, the
  founder, 8 October 2026):** `payment_reversals` records every refund and dispute handled, once,
  by its Razorpay id, 0 taken included, and the webhook's repeat check reads it.
  `tests/modules/payments/test_reversals.py` buys again between two deliveries of one refund, and
  of one dispute, and finds the new Velas untouched and one signal; `test_reversal_races.py`
  delivers it five times at once and finds one record.
- [x] P-460 · Keep the countdown and the expiry off her screens. **In T-7.10 and T-7.12** (on
  neither's Needs line yet: the founder to place it). Worst case: she sees a Thread's countdown,
  "Ran out" or an expired state, and so learns that time, and money, stands between her message
  and his reply, which D-097 says she is never shown ("Her side shows only that her message hasn't
  been seen"). T-7.10's line asks for "live countdown per row", and T-7.12's events update the
  list's state, neither saying whose rows. 08-DESIGN covers her conversation screen (T-7.11, no
  countdown, no price), not the list. **The API half is closed:** T-7.2's session sends her
  `expires_at` as null (its Q6, approved 8 October 2026), and T-7.6 sends `thread.expiring` and
  `thread.expired` to him only. What is left is the web: her rows draw no countdown pill and no
  expired state, and the client reads nothing from a null. Found writing T-7.6; filed by Claude,
  8 October 2026; its session's block, P-460 to P-469.
  **Placed 8 October 2026 (the audit, P-490):** on T-7.10's and T-7.12's Needs lines.
  **T-7.10's half built 9 October 2026:** her chats list draws no countdown, no expired state,
  no "Clear expired" and no footer, and a test gives her rows an `expires_at` to prove the
  screen's own gate (`t710-01` to `t710-04` red when broken). T-7.12's half, the client reading
  nothing from her null, stays open.
  **T-7.12's half built 9 October 2026 (D-881):** no socket event writes a Thread's state into a
  cache, an expiry least of all; the Thread is asked of the API again, which sends her null. The
  hour's two events are read by a man alone, an allowlist (`realtime.test.ts`: her client handed
  `thread.expired` with an `expires_at` changes and asks nothing; `t712-web-01` red when broken).
- [ ] P-450 · Add Hindi and Hinglish words to the message filters. **Before REL-1,** the first
  time strangers message each other. Worst case: a man writes "paytm kar do", "number do" or a
  Hindi slur, in the language most of our users write in, and it reaches her unmasked and
  unrefused, while `/terms` promises "We refuse messages that are abusive or that ask for money".
  T-7.1's `messages/filters.py` (D-552) holds the prototype's lists: eight abuse words, five of
  them romanised Hindi, and English money phrases. Wanted: Hindi and Hinglish abuse words, and
  solicitation in the forms people use (payment-app asks, "number do", "paise bhejo", "recharge
  kar do", "UPI pe"), in Devanagari and romanised. **The founder supplies or approves the list**
  (8 October 2026): a word list is a product judgment, and a wrong one refuses ordinary sentences.
  Each word goes in with a test, and each with an ordinary sentence it must not catch. Filed by
  Claude in T-7.1 at the founder's direction; its session's block, P-450 to P-459.
- [ ] P-470 · Stop `test_a_fifty_waits_while_another_run_holds_the_turn` failing when other
  sessions test at once. **Before the next session's `make test` meets it** (no deadline beyond
  that: it blocks a landing, it hides no bug). Worst case: a `make test` goes red on a branch that
  touches nothing near it, the push gate refuses the landing, and the next session, told a red
  is never waved through, spends its time on a test that is right about its own code. Seen once,
  8 October 2026, in P-220's run (web files only): `TimeoutError` at
  `asyncio.wait_for(waiting, timeout=10)`, `api/tests/modules/wallet/test_concurrency.py`, while
  three other worktrees' `pytest -m "not critical"` were running (`pgrep`, minutes later). The
  turn is one advisory lock on the shared server (P-142). The test holds it, releases it, and
  gives its own waiter 10 s, but the waiter only polls every 0.2 s, so another run's fifty can
  take the turn in that gap and hold it for its own whole test. **A hypothesis, not established:**
  that interleaving wasn't observed, only the timeout beside the other runs. Fix, the doer's to
  choose: the test's own lock id, so no other run can contend for it; or a waiter that queues
  (`pg_advisory_lock`, blocking) rather than polls. Its proof: hold the turn from a second
  connection in the gap and see today's test go red, the fixed one green. Found in P-220's
  session; filed from its block (P-470 to P-479).
- [x] P-480 · The admin's claims screen. **In T-9.5** (on its line). Worst case without it: a man's
  claim that his money went through and no Velas came sits unread, since the queue exists only
  as an API (`GET /admin/refund-requests`, D-582) and nobody looks at it, and the published
  `/refunds` promise ("we fix it") goes unkept. The screen lists the open claims, oldest first,
  and resolves each with grant, refund or reject (a note required), behind a confirmation, from
  what the API already decides (D-580). Until it exists, nothing tells the founder a claim was
  filed. Found building T-8.3; filed by Claude, 8 October 2026; its session's block, P-480 to
  P-489.
  **Done in T-9.5:** `/admin/claims`, an admin's (`ClaimQueue`).
- [x] P-481 · The man's claim form. **In T-8.7** (on its line). **Done there, on the checkout's
  sheets; the history's half is P-662.** Worst case without it: a man whose
  payment broke has no way in the product to say so, only the support email `/refunds` names,
  and the claim never reaches the queue T-8.3 built. A "Report a problem with this payment" on
  a payment (the checkout's failure sheet and T-5.5's history), with the two kinds and their
  plain words, never a change of mind (D-230). He can't yet see a claim's outcome: the API has
  no list of his own claims, so this task adds `GET /refund-requests` (his own, D-270) if it
  shows one. Found building T-8.3; filed by Claude, 8 October 2026; its session's block, P-480
  to P-489.
- [x] P-443 · Link search and Liked you from the deck. **In T-6.5.** Worst case: both screens
  exist from T-6.6 and T-6.7 at `/discover/search` and `/discover/likes`, and nothing in the app
  leads to either, so nobody finds them but by typing the address. T-6.5's feed row holds a Search
  icon button (08-DESIGN §8) and is the deck's own file, `web/src/app/(app)/discover/page.tsx`,
  which neither task touches while T-6.5 is unbuilt. Liked you's entry, with its count (`GET
  /likes/count`, T-6.7), is T-6.5's to place. Filed by Claude building T-6.6, 8 October 2026; its
  session's block, P-440 to P-449.
  **Done in T-6.5 for Search** (the feed row's Search links to `/discover/search`). **Liked you's
  entry moved to T-6.7, on its line:** neither `/discover/likes` nor `GET /likes/count` existed
  when T-6.5 landed, and a link to a page that 404s is worse than none. T-6.7 places it in
  `web/src/components/discover/FeedRow.tsx`.
- [x] P-490 · File the 8 October 2026 audit's findings. The audit was run by the advisor (Claude, in
  a separate chat) at the founder's request, and approved by the founder on the advisor's
  recommendation. Docs only. It ticked boxes whose work had landed (T-1.22's Supabase, Upstash and
  R2 box; P-09; P-10), added T-7.1's missing Commit line, corrected T-9.12's pointer to P-0.6
  (Sentry is still not created), put P-460, P-301, P-16 and P-56 on the Needs lines of the tasks
  they gate, and dated every missed deadline: P-49, P-50, P-68 and P-200 with a new one, P-06, P-34,
  P-60, P-62 and P-122 as passed. It also fixed `/done` as P-261 asked. Filed from this session's
  block (P-490 to P-499, D-590 to D-599).
- [ ] P-500 · The deck at 60 fps on the test phone, read by the founder. **Before beta.** Worst
  case: the deck drags at 60 fps on a desktop slowed six times and stutters on the phones men in
  Phagwara actually carry, where a GPU, a thermal limit and a real display are what count, and
  the first screen of the paid product feels broken. T-6.5's reading is a desktop stand-in
  (`web/bench/deck-fps.spec.ts`, run by hand: a production build, a phone's screen, DevTools' CPU
  throttling at 4× and 6×, ten runs each); the box on its line waits for this one: Chrome's
  performance panel, remote-debugging the test phone over USB, a card dragged and flung ten
  times, the frame track's range recorded in the tick. Filed by Claude building T-6.5, 8 October
  2026, at the founder's direction; its session's block, P-500 to P-509.
- [ ] P-530 · Give the web tests' first look at the screen room to wait when the machine is busy.
  **Before it costs a landing again; the founder to place it.** Worst case: a landing goes red for
  no fault of its own, re-runs until green, and every session learns to shrug at red (P-140's
  silent direction), the same hazard P-330 was. Seen 8 October 2026, in `/done`'s `make lint test`
  for P-330 (`c3f6b8f`, which touches no web file), with several sessions testing at once:
  `PhotosStep.test.tsx`'s first test, "with no photos: six empty slots and the face slot; a man may
  go on with none (D-392)", failed at `findAllByRole("button", { name: "Add a photo" })` (`Unable
  to find role="button"`), 1 of 1,044 web tests; that file took 9,056 ms. Then run alone five
  times, load average 14.9: 5 green, 33 passed each, 4.09 s to 4.83 s. So the query's wait ran out
  under load; nothing in the component was wrong (inferred from those runs, not observed: no
  timing of the render was taken). Testing Library's `find*` queries wait 1 s by default, and
  `vitest.config.mts` and `vitest.setup.ts` set no `asyncUtilTimeout`, so every web test's first
  `find*` has that one second, however many other sessions' runs share the machine. One way: raise
  `asyncUtilTimeout` once in `vitest.setup.ts`, which costs a passing test nothing, and prove it
  red at today's 1 s under a forced load. Filed by Claude landing P-330, 8 October 2026; its
  session's block, P-530 to P-539.
- [x] P-510 · `GET /threads/cleared`: the chats I cleared, for T-9.8's "cleared chats with
  restore" (the prototype's "Cleared chats (n)" with "Restore all", 08-DESIGN's You tab). Worst
  case: T-9.8 reaches its row and no API lists a cleared chat, so a person who cleared one by
  mistake past the 5-second undo can't find it to restore it; it is kept (D-006) and unreachable.
  T-7.8 built clear, bulk clear and restore (D-611) and no list; this adds `Page<ThreadRow>` of
  Threads I cleared with nothing newer (D-270), and "Restore all" as a loop or a bulk `DELETE`,
  whichever T-9.8 wants. Belongs on T-9.8's Needs line. Filed by Claude building T-7.8, 8 October
  2026, at the founder's direction; its session's block, P-510 to P-519. **Built in T-9.8** (D-912).
- [ ] P-511 · The prototype's auto-clear: an expired Thread more than 7 days past its expiry
  cleared from each person's chats by itself. **After beta, no deadline** (the founder, 8 October
  2026). Worst case without it: a Threads tab fills with long-dead Threads until its owner taps
  "Clear expired". The prototype does it on the client; built, it is a cron writing
  `thread_clears` through T-7.8's `repository.clear` (D-610's stamp), a clearing of each person's
  own (D-006), never a Knot, and a restore (D-611) undoes it. Filed by Claude building T-7.8, 8
  October 2026; its session's block, P-510 to P-519.
- [ ] P-440 · "Open thread" on the profile. **In T-7.10 or T-7.11** (the chats' screens; the
  founder to place it). **Not in T-7.11** (the founder, 9 October 2026): still to be placed. Worst case: a man reads a profile, wants to write, and finds no button,
  only Like; he has to find the person again in a match or the deck. T-7.1 built `POST /threads`
  (from a match, or a private message with its first message); 08-DESIGN §8's sticky bar carries
  "Open thread · 5 Velas", which T-6.8 left out until a screen can take a first message and its
  price (P-56's `shown_price`). Filed by Claude building T-6.8, 8 October 2026; its session's
  block, P-440 to P-449.
- [ ] P-441 · "Ask to view" on the profile's private album. **In T-8.4.** Worst case: the album row
  says how many private photos there are and offers no way to ask, so the count reads as a tease.
  T-6.8 shows the count alone. Filed by Claude building T-6.8, 8 October 2026; its session's block.
- [x] P-442 · Report and Block in the profile's ⋯ menu. **In T-9.1.** Worst case: someone being
  harassed opens the profile to block or report and finds only Share. T-6.8's menu holds Share
  alone until T-9.1 builds both. Filed by Claude building T-6.8, 8 October 2026; its session's block.
  **Done 9 October 2026 (T-9.1, D-863):** both, on someone else's profile only.
- [x] P-445 · Next's own 404 page breaks the CSP on every build. **Before REL-1.** Worst case: every
  404 a person reaches renders with its styles refused (five `style-src` violations, read in
  Playwright's Chromium on 8 October 2026 at `/no-such-page` under the static policy), and once
  T-9.12 reports violations to Sentry, every mistyped link is noise there. Next's built-in
  not-found page sets inline styles, which neither policy allows (`style-src` falls back to
  `default-src 'self'`). Ours, a `not-found.tsx` styled by classes, would fix it; its proof, the
  E2E watch passing on a 404. Found building T-6.8, whose share E2E had to visit one with plain
  `@playwright/test`; filed by Claude, 8 October 2026; its session's block.
  **Done 16 October 2026 (D-980):** ours, class-styled, rendered per request so a nonce route's
  404 carries its nonce; `e2e/not-found.spec.ts` holds a 404 under each policy to no violation and
  to hydrating, and `/@a!b` is now under the watch.
- [ ] P-446 · `/@username`'s limit counts the web's server, not each visitor. **Before
  `/@username` is shared at scale.** Worst case: one link shared widely, read more than 60 times a
  minute in all, and every reader after the 60th sees "isn't public" until the minute passes, and
  a script walking usernames is held to the same 60 as everyone together. The page's server render
  asks `GET /public-profiles/{u}` from the web's server, so the API's per-address limit (D-544)
  sees that server's address. Options: send the visitor's address in a header the API trusts only
  from the web (a shared secret), or let the browser ask the API itself. Found building T-6.8;
  filed by Claude, 8 October 2026; its session's block.
- [x] P-447 · A switch for `public_link` on a screen. **With the settings screens** (You and
  Settings have no design yet, 08-DESIGN §8). Worst case: the switch exists only in the API, so
  nobody can turn on their `/@username` page, and every shared link reads "isn't public" to people
  not signed in. T-6.8 built the setting (D-544) and no screen, as the founder's addition asked.
  Filed by Claude building T-6.8, 8 October 2026; its session's block. **Built in T-9.8** (D-913): a switch in Privacy and account.
- [x] P-580 · Tell T-8.8's kudos prompt whether it can be shown. Worst case: the prompt in chat
  keeps coming back after kudos was given, and each tap on it is an `ALREADY_EXISTS`, so a
  positive note reads as an error; or it shows before D-680 allows it, and each tap is
  `NOT_ALLOWED`. `GET /me/kudos` says only what you were given (D-680), and nothing yet says, for a
  Thread, whether you have given its other person kudos or whether both have written. T-8.8 decides
  where that lives (a field on the Thread as you see it is one way) and builds it with the prompt.
  Filed by Claude building T-8.5, 8 October 2026; its session's block, P-580 to P-589.
  **Done in T-8.8 (D-790):** `PublicProfile.thread.kudos` (`too_early`, `can_give`, `given`),
  from the one rule `POST /kudos` reads; the prompt shows only for `can_give`.
- [x] P-520 · A real voice recording from each browser, read by T-7.9's measuring. **Before
  T-7.11** (on its Needs line). Worst case: Safari's MediaRecorder writes a fragmented MP4 that
  `core/audio.py` can't read, and every iPhone user's voice note is refused as
  `UNSUPPORTED_AUDIO`; or Chrome's WebM or Firefox's Ogg measures wrong and a minute's note is
  refused as too long. T-7.9's readers are tested only on files built by hand to the specs
  (`tests/audio_samples.py`; no ffmpeg here, and no browser recorded one). Record 5 s and 59 s in
  Chrome, Firefox and Safari (macOS and iPhone) with T-7.11's recorder, commit them as fixtures,
  and assert each file's measured length within a second of the recorder's. Filed by Claude
  building T-7.9, 8 October 2026, at the founder's direction; its session's block, P-520 to P-529.
  **Done for iPhone Safari only** (the founder, 9 October 2026: "that was the real risk"). The
  founder recorded 5 s and 59 s on his iPhone in Safari at `/dev/voice` (T-7.11's recorder, over a
  temporary HTTPS tunnel, stopped once they were in) and AirDropped them; both came out as WebM
  Opus written by WebKit, since this Safari records WebM and the recorder asks for it first. Saved
  under the page's default name, `chrome-mac-…`, and committed under their true names, the bytes
  unchanged: `api/tests/fixtures/voice/safari-iphone-5s-5693ms.webm` and `-59s-59919ms.webm`,
  pinned by SHA-256 in `tests/core/test_audio_recordings.py`, which shows each was AirDropped
  (`sharingd`) and WebKit-written. **Measured:** 4.926 s against the recorder's 5.693 s (0.77 s
  short), and 58.963 s against 59.919 s (0.96 s short): inside the second, the second barely.
  Safari measures shorter than its recorder's clock, so the gap can't make a note too long.
  Before them, a Playwright Chromium fake-microphone recording measured within 0.05 s (not a real
  browser recording, not committed). The Mac's three browsers are P-773; Safari's MP4 is P-774.
- [ ] P-521 · Voice uploads never sent stay in the private bucket for ever. **Before beta.** Worst
  case: the bucket fills with recordings nobody sent, each a person's voice kept with no message
  to delete it by, against D-500's promise that what a person leaves is erased; and storage grows
  unbounded. A URL from `POST /media/voice-upload-url` whose recording is never sent, or refused
  at the send, leaves `voice-uploads/…`; a send refused after its check (e.g. `ALREADY_EXISTS`)
  leaves a `voice/…` copy no message keeps. Sweep both on a cron: an upload older than its URL's 5
  minutes and a grace, and a `voice/` file no `messages.media_key` names. Filed by Claude building
  T-7.9, 8 October 2026; its session's block.
- [x] P-550 · Say which notification setting governs a gift, and push it. **In T-9.4.** Worst case:
  T-8.9 writes a `gift` notification for every gift a woman receives, and no setting in
  `notification_prefs` names gifts, so when T-9.4 sends pushes, a woman who turned off what she
  thought covered them is still pushed each one, or the gift kind is left out of the push worker
  and none arrives at all. T-9.4's kinds list has no gift. Decide there whether `like` governs it or
  a `gift` column is added (a migration, and `Prefs` in 04-API), and that a paused woman is sent
  nothing (T-9.6). Filed by Claude building T-8.9, 8 October 2026; its session's block, P-550 to
  P-559.
  **Built in T-9.4 (D-851):** a `gift` setting of its own governs a gift's push; the in-app row is
  written either way; a paused woman is sent nothing.
- [ ] P-590 · Notice one face verified on many accounts. **In T-9.2** (fraud signals). Worst
  case: a man with N numbers makes N accounts on his own code, matches each selfie with his own
  face (a man's selfie is optional, so it is the cheap trigger) and is paid N referral rewards in
  one account, up to `referral_rewards_max` (10, D-692): 50 Velas, ten Threads, for ten SIMs and
  an evening. The same face as "women" puts fake profiles into discovery too. The cap bounds the
  Velas; nothing yet notices the face. T-9.2 could compare a new selfie's embedding with the kept
  selfies' and raise a fraud event on a match above the threshold, never refusing on it alone.
  Filed by Claude building T-8.6, 8 October 2026; its session's block, P-590 to P-599.
  **T-9.2, 9 October 2026: noted, not built.** No face embedding is kept anywhere: `verify_selfie`
  compares two photos and keeps the result, so comparing faces across accounts means keeping
  biometric templates, a decision and a `/privacy` line of its own. While referrals are paused
  (D-840) the reward route pays nothing; **P-590 is done before they are turned back on**, as
  P-591 is. When built, scoring takes it as a `face_reused` signal of 30, capped there (monitor at
  most), so it never refuses or freezes anyone on its own (D-900). The fake-"women" half isn't
  paused: at beta the founder's review of every selfie (D-264) is what catches it.
- [ ] P-591 · A referral reward kept after its purchase was charged back. **Before beta, or
  accepted by the founder.** Worst case: a referee buys the smallest pack, the capture rewards
  both men (T-8.6), and he disputes the charge: D-520 takes back the purchase's Velas, never the
  referral's, so his referrer keeps 5 Velas for a sale that never happened. Dominated by the
  selfie route, which costs nothing (P-590), so low in practice. A fix would reverse the reward
  in `_reverse()` when the reversed payment was the referral's trigger, which needs the trigger
  recorded on the referral. Filed by Claude building T-8.6, 8 October 2026.
  **Moot while referrals are paused (D-840, P-740, 9 October 2026), and must be done before they
  are turned back on:** at 0 no reward is paid, so none can outlive a chargeback.
- [x] P-592 · Publish what a worker's transactions queue. **Before T-7.12** (the web's socket
  client). Worst case: a referee's selfie matches in the `verify_selfie` job, the reward credits
  both men (T-8.6), and neither balance moves on screen until a reload, since `wallet.updated`
  is queued on the worker's session and only `get_session` publishes (`core/events.py`: "Code
  outside a request publishes nothing"). The same holds for any credit or event a job writes.
  Fix: the worker's session factory publishes committed events as `get_session` does. Filed by
  Claude building T-8.6, 8 October 2026.
  **Built 9 October 2026 (with T-7.12, its own commit):** `core.db.publishing` wraps any session
  factory so each session publishes its committed events once closed; the socket's
  `session_opener` and the worker's `ctx["sessionmaker"]` both use it. `thread_clock` publishes
  its own already and is unchanged. `tests/workers/test_worker_events.py`: the worker's context
  publishes a committed event and never a rolled-back one, and `verify_selfie` crediting a
  referral's reward sends both men `wallet.updated`. Broken once each (`uv run python -m
  tests.break_guards p592-`, 2 of 2 red, log in the main checkout's `out/p592-break-guards.log`).
  T-7.5's `t75-19` and `t75-20` re-anchored on the shared opener, each red in 1 of 1
  (`out/p592-break-guards-t75.log`). The founder's `selfie_review` tool writes a verdict and
  queues no event, so it is unchanged.
- [ ] P-540 · Decide what the hour means between two men, and between two women. **Before beta,**
  the founder to place it on a task's Needs line. Worst case: two men matched with each other pay
  2 Velas every hour, each, to keep talking, since neither's message restarts the hour (D-097's
  amendment names hers only, and `threads.rules.restarts_the_hour` is an allowlist of women),
  while two women's Thread never stops anyone, since an expired Thread lets a woman through. A
  same-gender pair is something the product allows (`seeking`), and D-097 was written for a man
  and a woman; nothing says whether its asymmetry should hold, flip or fall away for them. As
  built (T-7.6, D-642): the warning and the expiry go to whoever sees the expiry, a man, so both
  men are told. Found writing T-7.6's plan; filed by Claude, 8 October 2026; its session's block,
  P-540 to P-549.
- [ ] P-620 · Undo of a clear restores the previous clear point, not none. **An API change,
  before beta** (the founder, 9 October 2026). Worst case: someone clears a chat, a new message
  brings it back, they clear it again and tap Undo, and the whole history returns, including
  messages they had cleared before and chose not to see again. T-7.10's Undo is `DELETE
  /threads/{id}/clear`, which removes the clearing altogether (D-611), so the earlier one goes
  with it. Wanted: a clear remembers the point it replaced, and Undo puts that point back, or
  none if there was none. Found planning T-7.10; filed by Claude, 9 October 2026, at the
  founder's direction; its session's block, P-620 to P-629.
- [x] P-740 · Pause referrals. **Now** (the founder, 9 October 2026: "referral ka system abhi
  roko, nahi dena abhi referral kisiko", relayed with the advisor's brief; D-840). Worst case if
  not done: T-8.6 is live, so every man on a referral is paid 5 Velas at his selfie or first
  purchase, against the founder's word; and if only the reward stops, a referee who applies a
  code spends his number's one referee slot, ever (D-691), on a referral that pays nothing, so
  he can never be paid when referrals return. A reversible migration sets
  `app_config.referral_reward_velas` to 0 (down: 5); the reward code stays, and at 0 already pays
  nothing (D-692); `POST /referrals/apply` refuses while the reward isn't above 0, before any
  slot is taken; T-8.8 builds no referral field or invite card while paused; P-591 must be done
  before referrals return. Filed by Claude, 9 October 2026; its session's block, P-740 to P-749.
  **Done (9 October 2026):** migration `b53383c8e9b6`; apply's check and its warning in
  `referrals/service.py`, before every other; `tests/modules/referrals/test_paused.py`; five
  breaking cases (`p740-`), each red with its guard gone (`out/p-740-break-guards.log`). The
  referrals tests run at 5 through their `conftest.py`. **How it is built is Open (D-840):** the
  advisor's recommendation, relayed without the founder's review; the pause itself is Locked.
- [ ] P-690 · The referral screens, when referrals return. **With the decision that turns
  referrals back on (D-840), after P-591.** Worst case: referrals are switched on again and the web
  still has no field to apply a code and no card to share one, so no referee can ever apply one
  (`POST /referrals/apply` works only before onboarding is `done`, D-691) and every man who
  signs up meanwhile is past the window for good. T-8.8's line asked for both (the optional code
  field in onboarding, the share card in You) and built neither, as D-840 requires while paused;
  `web/src/i18n/referrals-paused.test.ts` must change with them, its allowlist naming the new
  words. Filed by Claude building T-8.8, 9 October 2026; its session's block, P-690 to P-699.
- [ ] P-660 · "Most popular" once purchases make it true. **After launch, when there are
  purchases to count.** Worst case without it: none. The store says "Best value" on the cheapest
  Vela (D-760) and no pack says "Most popular". What's missing is only the tag the founder kept on
  the ₹4,500 pack (D-231), which needs a rule over real purchases: which pack, over what window,
  and how many sales before the words are true. Filed by Claude building T-8.7, 9 October 2026;
  its session's block, P-660 to P-669.
- [ ] P-661 · Razorpay's CSP, checked on staging with test keys. **Before the first real sale.**
  Worst case: a step of a real payment (3-D Secure, a UPI intent, a bank's page) asks the page for
  a source T-8.7's list lacks, the browser refuses it, and the checkout fails in a way that looks
  like Razorpay's bug, silently until T-9.12 reports CSP violations. T-8.7's list is what
  Checkout asked of a page with a key and an order that don't exist (D-761,
  `web/bench/razorpay-csp.spec.ts`). Razorpay's window never showed, so nothing past it was seen.
  Needs Razorpay test keys on staging (P-0.8's account), set by the founder, never asked for:
  then a test payment by card and by UPI, with the browser's violations read, as T-3.14 did for
  Firebase. **And re-check whether Razorpay still needs inline styles** (D-762, the founder,
  9 October 2026): run the payment with `style-src 'self' 'unsafe-inline'` removed. If its window
  keeps its phone layout, drop the allowance. Filed by Claude building T-8.7, 9 October 2026.
- [ ] P-662 · A claim from the wallet's history, and a claim's outcome. **Before beta** (the
  founder, 9 October 2026). Worst case: a man who closes the app inside the checkout's 60 s, or
  finds a duplicate charge on his bank statement next week, has no way in the product to claim:
  T-8.7's claim form (P-481) lives only on the checkout's sheets, where the payment's id is known,
  and a ledger entry carries no payment id (04-API). He is left with the support email `/refunds`
  names. Needs `GET /payments` (his own, a page at a time, D-270) so the history can offer "Report
  a problem" on a payment, including one that granted nothing; and `GET /refund-requests` (his
  own) if a claim's status is to be shown. Filed by Claude building T-8.7, 9 October 2026.
- [ ] P-663 · One sign-up helper for the E2E. **Whenever the next journey needs a signed-up
  man.** Worst case: a change to an onboarding screen is fixed in J1's steps and not in J8's and
  J9's copy, which then fail for a reason that isn't theirs. `web/e2e/store.spec.ts` signs a man up
  through the screens in steps of its own, shortened from J1's helpers in `signup.spec.ts`, which
  aren't exported, and moving them would have reshaped T-3.13's file mid-task. Fix: move them to
  `e2e/onboarding.ts`, used by both. Filed by Claude building T-8.7, 9 October 2026.
  **A third copy waits (T-8.10, 9 October 2026):** the gifts journey held by P-680 repeats J1's
  steps for a man and J2's for a woman, her face photo and selfie included, for the same reason.
  The move takes it too.
  **In part, T-9.1 (9 October 2026):** `signUpMan` moved from `store.spec.ts` to `e2e/fixtures.ts`,
  used by J8, J9 and J10; J1's helpers in `signup.spec.ts` are still their own.
  **And the woman's, T-7.13 (18 October 2026):** `signUpWoman`, with `asFarAsLocation`,
  `usernameAndAbout` and `pickInterests`, moved from `gifts.spec.ts` to `e2e/fixtures.ts`, used
  by J13 and J4 to J7. Left: J1's and J2's own steps in `signup.spec.ts`, and J13's man, who
  still signs up by steps of his own in `gifts.spec.ts`.
- [x] P-680 · Give the E2E room for another sign-in, then land T-8.10's gifts journey.
  **Before the next journey that signs anyone in.** Worst case: every new sign-in journey turns
  CI's E2E red at someone else's sign-in, as T-8.10's did (run 37859041045: J3, J8 and J9 on
  desktop never got a code). The API allows 20 OTP sends an hour per client IP
  (`OTP_SENDS_PER_IP`, D-066), every journey signs in from one address, and the suite already
  sent exactly 20 a run before T-8.10 (ten a project: three in `session.spec.ts`, J1, J2 and
  J1 refused, J3's two, J8 and J9). T-8.10's journey needs four more. A fix keeps production's
  limit as it is and gives each journey its own budget: for example, the E2E API server alone
  (`api/tests/e2e_server.py`, never a deployed build) takes the client address from a test header
  each Playwright context sets, behind an allowlist gate. Then restore the journey: it is
  `web/e2e/gifts.spec.ts` in commit 1fddbdc on branch `t-8.10-web-gifts`, kept on origin for it,
  and it passed locally on both projects on 9 October 2026. Filed by Claude building T-8.10, 9
  October 2026, at the founder's direction (dropped from T-8.10 to land it).
  **J10 waits here too (T-9.1, 9 October 2026):** its two sign-ups took CI's run 37863825770 past
  the cap the same way (J3, J8 and J9 on desktop got no code), so T-9.1 landed without it. It is
  `web/e2e/safety.spec.ts`, with `unlock` in `e2e/fixtures.ts`, in commit 46e23c0 on branch
  `t-9.1-j10`, kept on origin for it; it passed locally on both projects on 9 October 2026.
  **As built (P-680, 9 October 2026, D-890):** `e2e/fixtures.ts` gives every browser context an
  address of its own in 198.18.0.0/15, the test's own and any `browser.newContext` opens, added
  by `context.route` to its requests to the API alone; the launcher reads it from
  `X-E2E-Client-IP`, its `CLIENT_IP_HEADER`. Outside local, Settings now refuse any
  `CLIENT_IP_HEADER` but `Fly-Client-IP` (`PROXY_CLIENT_IP_HEADERS`), `X-Forwarded-For`
  included. Both journeys restored, the gifts one as J13 and J10 as it was, and `make e2e`
  passed 30 of 30 on both projects, 28 codes sent (`out/p680-e2e-green.log`). With the route
  switched off, the first 20 sends went through and every sign-in after them was refused: 7 of
  30 red, desktop's last seven sign-ins, each at "Enter the code"
  (`out/p680-e2e-break-no-address.log`). Tested in
  `test_e2e_server.py` and `test_config.py`; three guards broken
  (`uv run python -m tests.break_guards p680-`, 3 of 3 red, `out/p680-break-guards.log`).
- [ ] P-681 · Swipes' ledger reads sort by `created_at` alone, so a tie fails a landing at
  random. **Soon: it costs a full `make test` each time it fires.** Worst case: a red `make test`
  that isn't the change's, blocking a landing (or, worse, teaching sessions to rerun until
  green). Seen once on 9 October 2026, building T-8.10, in its marking run:
  `test_a_mans_super_like_debits_five_through_the_wallet` read the grant `make_user` wrote as
  the last entry, not the debit; alone it passed 15 of 15. A ledger row's `created_at` is
  Postgres' `now()`, the transaction's start, and rows from one transaction share it (as
  `wallet/repository.py` says), so `_ledger` in `tests/modules/swipes/test_swipe.py`, ordered
  by `created_at` with no tie-break, can return them in either order. Fix: assert on the debit
  row found by its reason, or order by something that can't tie; grep the suite for the same
  pattern (`order_by(LedgerEntry.created_at)` alone: three in `api/tests`). Filed by Claude
  building T-8.10, 9 October 2026.
- [x] P-631 · Tell her when someone asks to see her album. **In T-9.4.** Worst case: a man pays a
  Vela for a request that sits unseen in her incoming list until she happens to open it, so the
  request reads to him as ignored and to her as nothing at all; T-8.4 writes no event and no
  notification for a new request (D-732), only `album.decided` back to him. Add an
  `album.requested` event and an `album_request` notification at the request's commit, a setting
  in `notification_prefs` that governs its push (as P-550 asks for gifts), and nothing to a paused
  woman. Filed by Claude building T-8.4, 9 October 2026, at the founder's direction; its session's
  block, P-630 to P-639.
  **Built in T-9.4 (D-851):** `album.requested` and an `album_request` notification at the
  request's commit, `album_decided` back to him, both under an `album` setting; nothing to a paused
  woman.
- [x] P-670 · The "Knot tied ✦" sheet and the web's tie and untie hooks go to T-7.11 — 08-DESIGN
  §8 heads the sheet T-7.7, but T-7.7's items are the API alone, and the knot bar that leads to
  the sheet is T-7.11's. Placed on T-7.11 as an item, the founder's answer (D-770); open until
  T-7.11 builds the sheet and ticks it. Filed by Claude building T-7.7, 9 October 2026; its
  session's block, P-670 to P-679. **Built by T-7.11, 9 October 2026:** `KnotTiedSheet.tsx`, shown
  when a tap's answer is `knotted`, hers without the hour, Velas or footer (D-871); `useTieKnot` and
  `useUntieKnot` in `src/lib/queries/threads.ts`.
- [ ] P-770 · The match sheet's "Open thread" should open the Thread it made. **Whenever the
  discover screen is next touched.** Worst case: a man pays 5 Velas to open a Thread from the
  match sheet and lands on the chats list, where he has to find the row he just paid for, the
  moment he is most likely to write. `MatchSheet.tsx` pushes `/chats`, because `/chats/[id]`
  didn't exist when T-6.5 built it; `POST /threads` answers the Thread, so it can push
  `/chats/{id}`. Filed by Claude building T-7.11, 9 October 2026; its session's block, P-770 to
  P-779.
- [ ] P-771 · The conversation's words assume a man and a woman. **With P-540's answer.** Worst
  case: two men matched with each other read "her reply restarts the hour", "She wrote back. The
  hour had run out." and "Free, if she ties it too", and two women "He has to tie it too": wrong
  about the other person, and, in two men's Thread, a promise the rules don't keep (P-540). T-7.11
  draws 08-DESIGN §8's copy, chosen by the viewer's gender; `CardLite` carries no gender, so the
  screen can't pick neutral words for a same-gender pair. Wanted, once P-540 decides the rule:
  words for each pairing, and the other person's gender (or a neutral flag) where the screen
  needs it. Filed by Claude building T-7.11, 9 October 2026; its session's block.
- [ ] P-772 · A long chat's voice notes can outrun their link's rate limit. **Before beta.**
  Worst case: someone scrolls back through a chat with more than 60 voice notes they can hear, and
  the ones past the 60th show a play button that does nothing until a tap a minute later asks
  again. T-7.11 asks each unlocked note's link as it is drawn (`GET /messages/{id}/media`, 60 a
  minute), so a tap plays at once, without a wait a browser may refuse to play after. Fix: ask as
  a note scrolls into view, or a batch endpoint for a page's links. Filed by Claude building
  T-7.11, 9 October 2026; its session's block.
- [ ] P-773 · Real recordings from the Mac's browsers: Chrome, Firefox and Safari. **Before beta**
  (the founder, 9 October 2026). Worst case: Chrome's or Firefox's own recording measures longer
  than the recorder's minute and a 59-second note is refused as `AUDIO_TOO_LONG`, or a desktop
  browser's file is one `core/audio.py` can't read and every voice note from it is refused as
  `UNSUPPORTED_AUDIO`. P-520 was closed with iPhone Safari's two recordings alone. Record 5 s and
  59 s in each at `http://127.0.0.1:3000/dev/voice` under `make dev`, set the page's browser and
  device first (its defaults name every file `chrome-mac`), check each file's writer in its header
  (`WebKit`, Chrome's, Firefox's), and add them to `tests/core/test_audio_recordings.py`'s list.
  A Playwright Chromium recording with a fake microphone measured within 0.05 s on 9 October 2026,
  which is not a real browser's. Filed by Claude building T-7.11, 9 October 2026, at the founder's
  direction; its session's block, P-770 to P-779.
- [ ] P-774 · Safari's MP4 has never been recorded for real. **Before beta.** Worst case: an
  iPhone on a Safari that records MP4 but not WebM sends a fragmented MP4 that `core/audio.py`,
  tested only on MP4s built by hand (`tests/audio_samples.py`), can't read, and every voice note
  from it is refused as `UNSUPPORTED_AUDIO`. P-520's worst case named it, but the founder's
  iPhone recorded WebM: its Safari records WebM Opus, which `voice-recorder.ts` asks for first, so
  the MP4 path never ran. Record on a Safari that offers only MP4, or with the recorder made to
  ask for `audio/mp4` on `/dev/voice` alone, and add the files to the recordings test. Filed by
  Claude building T-7.11, 9 October 2026; its session's block.
- [ ] P-750 · A bell in the header for the in-app list. **With a design** (08-DESIGN §8 has none).
  Worst case: a gift or a request to see her private pictures sits in a list two taps deep under
  You, so to her it reads as nothing and to him as ignored, the worst case P-631 was filed for,
  only moved. T-9.4 links `/notifications` from You (D-859), and the shell's structure is
  `AppShell.tsx`'s alone, held by `look.test.ts`, so a bell is a design change, never a drive-by.
  Filed by Claude building T-9.4, 9 October 2026; its session's block, P-750 to P-759.
- [ ] P-751 · Tell a person when their photo is decided. **Whenever moderation's outcome needs
  telling.** Worst case: a rejected photo is noticed only by opening the photos screen, so a
  profile stays without a picture for days. 02-ARCHITECTURE §4 said notifying the user was
  T-9.4's, but T-9.4's kinds never listed it. A `photo_decided` kind, its setting, and its words.
  Filed by Claude building T-9.4, 9 October 2026.
- [x] P-752 · A Thread's push opens the conversation. **In T-7.11**, once a conversation has a route.
  Worst case: a message push opens the chats list, one tap short of the message. `web/src/lib/
  notification-view.ts`'s `ROUTES` sends every Thread kind to `/chats`. Change that one table
  (and its test) when `/chats/[id]` exists. Filed by Claude building T-9.4, 9 October 2026.
  **Done in T-9.4's landing, 9 October 2026:** T-7.11 landed first with `/chats/[id]`, so every
  Thread kind now opens `/chats/{thread_id}` (`push-worker.test.ts` holds it).
- [ ] P-753 · See real pushes arrive, on staging, on real devices. **Once the founder has set the
  VAPID secrets.** Worst case: every push service refuses ours (a 403 from a wrong pair, a 400
  from a malformed token), each is tried three times and dropped, and nobody is ever told
  anything, with every test green. The encryption matches RFC 8291's own example and a browser's
  decryption in the tests, but no push service has yet accepted one of ours. Check Chrome on
  Android, Chrome on a desktop, Firefox, and an iPhone with the app on its Home Screen: each
  turned on through the match sheet's ask, sent a match, a message with the app closed, and none
  with it open. Read the outcome from `push_subscriptions.last_ok_at`, not Fly's logs. Count
  Upstash's commands for a day of it against D-091. Filed by Claude building T-9.4, 9 October
  2026.
- [ ] P-754 · Names in the in-app list. **With P-750's design.** Worst case: ten rows of "You have a
  new match" and none says who, so the list sends her to each profile to find out. `Notification`
  carries ids only, so the list says each kind's plain sentence. Either the API adds the other
  person's `CardLite` (not across a block, D-858), or the web reads it. Filed by Claude building
  T-9.4, 9 October 2026.
- [ ] P-755 · Turn staging push on after the founder sets the VAPID pair (STAGING.md §4). **After
  D-857 is decided in the founder's own words** (push stays off everywhere until then, the founder,
  9 October 2026). Worst case: push stays off unnoticed, and every notification waits in a list
  people rarely open. That is P-631's and P-550's worst case again, built and then switched off.
  The steps: set `VAPID_PRIVATE_KEY` and `VAPID_PUBLIC_KEY` on both staging apps (STAGING.md §4),
  change `PUSH_PROVIDER` to `"webpush"` in `fly.api.toml` and `fly.worker.toml`, and change
  `test_push_stays_off_everywhere_until_d857_is_decided` with them. Then P-753's check on real
  devices. Production follows with its own pair. Filed by Claude building T-9.4, 9 October 2026, at
  the founder's direction; its session's block.
- [x] P-760 · Notifications across a block. **In T-9.4** (its session is building now). Worst
  case: a woman blocks a man, then opens her notifications and finds "Kabir sent you a rose" from
  before the block, his name and photo shown, with a tap that leads to a profile that isn't
  there; or a push queued before the block arrives after it. T-9.1 stops every new event and
  notification across a block (D-862), but `notifications` rows written before it stay, and the
  list and pushes are T-9.4's. Fix: the list leaves out, and the push sender drops, any
  notification naming someone a standing block lies between (`blocked_either_way`, by number,
  D-861), and an unblock brings the list's back. Filed by Claude building T-9.1, 9 October 2026;
  its session's block, P-760 to P-769.
  **Built by T-9.4 (9 October 2026, D-858),** which read it from T-9.1's session before it
  landed: the list and the sender leave out anything about someone blocked either way, through
  `blocked_either_way`, so by number too (D-861).
- [x] P-761 · The report sheet's "A moderator reviews this within 24 hours". **In T-9.5.** Worst
  case: if the line ships before moderators have a queue, a woman reporting harassment is promised
  a review in 24 hours that nothing in the product makes happen. The prototype's sent state says
  it; T-9.1 leaves it out (D-863). Add it to `profile.reportSentBody` (`en.ts`) when T-9.5's
  report queue and its 24-hour timer exist, in the same words as the SLA it enforces. Filed by
  Claude building T-9.1, 9 October 2026.
  **Done in T-9.5:** `profile.reportSentBody` says "A moderator reviews this within 24 hours.",
  the queue's `due_at` (D-921); `ReportSheet.test.tsx` reads the literal.
- [x] P-762 · The block sheet's "You can undo this from the You tab". **In T-9.8.** Worst case: a
  person who blocked someone by mistake has no way back in the product until the You tab's blocked
  list exists: `DELETE /blocks/{user_id}` and `GET /blocks` are built (T-9.1), the screen isn't.
  T-9.1 leaves the line out rather than promise a screen that doesn't exist. Add it to the block
  sheet (`BlockSheet.tsx`, `en.ts`) with T-9.8's list. Filed by Claude building T-9.1, 9 October
  2026. **Built in T-9.8** (D-913).
- [ ] P-763 · Time the feed with blocks in it, on a quiet machine. **Before beta.** Worst case:
  D-861's by-number match makes Discover's feed slower than its 80 ms p95 target at beta's scale
  and nobody sees it, because T-6.2's benchmark seeds no blocks, so the block check never runs
  there. T-9.1 measured it with none (`out/t-9.1-bench/`, git-ignored), the old helper and the new
  run alternately, on a machine other sessions were loading (load average 5 to 7): spread p50
  32.9–43.6 ms old against 36.4–52.8 ms new, and the 80 ms p95 target met in both old runs but
  missed in one round of five in each new run (102.9 and 181.6 ms). The plans are the same shape,
  and the block nodes never executed on an empty table; planning took about 0.5 ms more per
  statement. Fix: seed the bench's viewer with blocks (some made by them, some of them, some of
  numbers with an erased account) and run old and new interleaved, ten rounds each, on a quiet
  machine; if the new one misses, give the viewer's blocked numbers to the query as a constant.
  Filed by Claude building T-9.1, 9 October 2026; its session's block, P-760 to P-769.
- [x] P-764 · Report and Block in the conversation's ⋯ menu. **Before beta.** Worst case: a woman
  being harassed in a chat opens its ⋯ menu to block him and finds only "View profile", "Clear
  chat" and "Untie the knot"; she has to open his profile and use its ⋯ menu, one more step at the
  moment it matters, and none at all once his account is deleted (no profile link). The prototype's
  conversation ⋯ opens the profile's menu, Report and Block included. T-9.1 built them in the
  profile's menu (P-442) and the approved plan stopped there; T-7.11's `ConversationMenu.tsx`
  landed meanwhile, its comment saying they "join with T-9.1". Fix: the same `ReportSheet` and
  `BlockSheet`, with the Thread's id as the report's `thread_id`, and after a block the chat left
  for the chats list; update that comment. Filed by Claude building T-9.1, 9 October 2026; its
  session's block.
  **Built in T-7.12 (the founder, 9 October 2026):** "Report" and "Block {name}" in the
  conversation's ⋯ menu, T-9.1's own sheets; the report sends the Thread as `thread_id`, a block
  is silent (D-862) and leaves the chat for `/chats`; both stay for a deleted account, which has
  no profile to open (`ConversationScreen.test.tsx`, three cases; `t712-web-19`, `t712-web-20`).
- [ ] P-780 · The API's access log prints each socket's ticket. **Before beta.** Worst case: a
  socket refused before it opens (another origin, 4403) leaves its ticket unspent in Fly's logs
  for up to its 30 seconds, and anyone reading those logs live could open that person's socket
  and hear their messages as they arrive. uvicorn's default access log writes every handshake's
  path with its query, `WebSocket /ws?ticket=…`, against rule 15 (never log tokens); a spent
  ticket opens nothing, so the accepted ones are only noise. Seen in T-7.12's E2E output, the
  first time a real client connected. Fix: drop the query from the access log (a filter on
  `uvicorn.access`), or turn it off where structlog already logs requests, with a test that
  reads the log. Filed by Claude building T-7.12, 9 October 2026; its session's block, P-780 to
  P-789.
- [ ] P-810 · Set a PIN after onboarding. **Before beta.** Worst case: someone who skipped the PIN
  at sign-up (D-069's `/me/pin/skip`) never gets the lock: the You tab offers "Lock now" only with
  a PIN (T-9.8), and nothing in the web sets one after onboarding, though `POST /auth/pin/set`
  takes one (no `current_pin` needed when none is set, within D-069's rules). A row in Privacy and
  account, the onboarding step's `PinPad` reused. Filed by Claude building T-9.8, 9 October 2026;
  its session's block, P-810 to P-819.
- [ ] P-811 · The selfie check from the You tab, for a man who skipped it. **Before beta.** Worst
  case: a man who tapped "Skip for now" at the selfie step (D-008) can never carry the badge, and
  the You tab can only tell him "No selfie check yet" (T-9.8): `POST /verification/start` works
  after onboarding (D-068) but no screen reaches it. The selfie step's camera and states, reused
  outside the onboarding frame. Filed by Claude building T-9.8, 9 October 2026; its session's
  block.
- [ ] P-812 · Add photos to the private album from the web. **Before beta.** Worst case: no
  screen uploads a `private` photo, so every album is empty: "Ask to view" is refused as
  `empty_album` (D-732) and an album request, a priced action, has nothing to sell. The API takes
  them (`POST /photos/upload-url` with kind `private`, up to 6, D-700's scored copy), and T-9.8's
  `/you/photos` shows public places and the face photo only. Found building T-9.8, outside its
  plan; filed by Claude, 9 October 2026; its session's block.
- [ ] P-800 · Tell the admins of an automatic freeze, and list them. **In T-9.5.** Worst case: a
  woman frozen by three colluding reporters (D-901 makes it harder, not impossible) waits
  frozen until someone happens to read the audit log or a Fly log line that rotates out in
  about 25 minutes, since "admin notified" is only those two today (D-904). Fix in T-9.5: the
  automatic freezes in its queue, and a push to every active admin (a notification kind of its
  own, which no user-facing setting governs, opening `/admin/users/{id}`). Filed by Claude
  building T-9.2, 9 October 2026; its session's block, P-800 to P-809.
  **Half done in T-9.5 (D-928):** `/admin/freezes` lists them, the automatic ones marked. The push
  is P-820.
- [ ] P-801 · Index what fraud scoring reads before beta scale. **Before beta.** Worst case: the
  10-minute sweep and the per-message checks slow as the tables grow, a sweep running past its
  10 minutes and a send waiting on its first-message check. `due_for_scoring` reads
  `fraud_events` by `created_at`, which has no index of its own (only `(user_id, created_at)`);
  `same_first_messages` reads a sender's messages through `(sender_id, client_msg_id)`, filtering
  by time after. Both are fine at today's sizes. Measure at 50,000 people as T-6.2 did, then add
  `fraud_events (created_at)` and `messages (sender_id, created_at)` if the plans say so. Filed by
  Claude building T-9.2, 9 October 2026.
- [x] P-802 · ChatsScreen's cap test times out on a loaded machine. **Now: it fails unrelated
  landings.** Worst case: every session's `make test` goes red at "takes at most 100 at a time, as
  the API does" (T-7.10) while another session tests, as D-902's docs commit did twice on 10
  October 2026 (9.7 s and 22.4 s at load averages 16 and 85, against vitest's 5 s; about 0.5 s
  alone), and sessions learn to rerun until green. Filed by Claude, 14 October 2026, at the
  direction of the founder on the advisor's recommendation (Claude, in a separate chat); its
  session's block, P-800 to P-809.
  **Fixed, 14 October 2026:** the test can't be made cheaper and keep its claim: it needs a hundred
  real selections, and React renders after each click whatever wraps them (one `act()` around all
  hundred measured the same, about 335 ms of its 550). So that test alone has its own timeout,
  30 s; vitest's global 5 s is unchanged. `t710-17-select-past-the-cap` (the cap's `>=` made `>`)
  still red in 1 of 1, the file restored byte for byte (`out/p-802-break-guards.log`).
- [x] P-850 · /login sends a code before a live session has restored. **Before beta; first of
  the founder's staging feedback.** Worst case: someone signed in already opens /login, types
  their number and taps "Send code" while `/auth/refresh` is still on its way to Singapore (1 to
  2 s); an SMS is spent, then the restore lands and moves them on before the code arrives, so
  they think sign-in is broken. The founder's words (14 October 2026, relayed by the advisor):
  "dubara login karte hai to otp baad mei aa rha login phele ho jata hai" (signing in again,
  the OTP comes later; the login has already happened). Cause: `/login` renders `SignIn` at
  once (T-3.10) and `SignedInRedirect` moves on only when `restoreSession` settles; nothing in
  `PhoneStage` reads the session. Fix: "Send code" can't send until the restore has settled as
  signed out or failed. **Checked, no separate bug:** an explicit Sign out clears both cookies
  (`test_logout_works_with_an_expired_access_token_and_clears_both_cookies`, E2E "sign-out
  clears both cookies"; every Sign out is `SignOutButton`, one mutation). Filed by Claude, 14
  October 2026; its session's block, P-850 to P-859.
  **Built, 14 October 2026 (D-950):** `PhoneStage`'s "Send code" is busy until the restore has
  settled as signed out or failed (no signal, a 5xx), on both sign-in paths; a restore that finds a
  session sends nothing and moves on. Held by `app/(auth)/login/page.test.tsx` (four cases: held,
  no signal, a 503, restored) and the E2E "a signed-in person on /login sends no code before the
  restore lands"; broken once each (`node scripts/break-guards.mts p850`, two cases, both red).
  The submit handler's own check, in the plan, was left out: with it removed every test stayed
  green, since the busy button already refuses a tap and Enter.
- [x] P-851 · The bio becomes optional. **Before beta.** Worst case: people who'd finish
  sign-up stop at the about screen, which asks for 40 characters before it lets anyone on. The
  founder's words (14 October 2026, relayed by the advisor): "bio mei 40 character likhna needed
  nahi hona chaiye they can skip". Today: `ABOUT_MIN, ABOUT_MAX = 40, 300` (`profiles/rules.py:21`),
  copied in `AboutStep.tsx:18` and `EditProfile.tsx:33`; `ck_profiles_about_length` (40 to 300,
  migration `3571ffd8d110`); onboarding's `done` needs it (`onboarding/rules.py:94`,
  `PROFILE_INCOMPLETE`); 03-SCHEMA:147. Becomes: none, or 1 to 300 after trimming, with "Skip" on
  the step (a write that advances past `about` with none) and a way to clear it in Edit
  profile. A new migration replaces the CHECK (null or 1 to 300); never edit `3571ffd8d110`.
  **Ranking and completeness: unchanged.** Completeness counts approved photos only
  (`onboarding/rules.py:116-121`, D-310) and the score reads no bio (D-491), so an empty bio
  costs nobody a place; cards already show a missing bio as none (`discovery/rules.py:82`). Found
  beside it, to fix in the same change: a length refusal shows "Leave out links and phone
  numbers." (`errorCopy.ts:51` ignores the server's `problem`), and the browser counts UTF-16
  units where the server counts code points, so an emoji bio can pass the counter and be
  refused. Filed by Claude, 14 October 2026; its session's block.
  **Built, 19 October 2026 (D-951):** none, or 1 to 300 characters; none is null, never `''`
  (`ck_profiles_about_length`, migration `ac292d16611f`, its downgrade refused while a bio is under
  40); `PATCH /me/profile` with an empty `about` skips the step or clears the bio; finishing no
  longer needs one. The step's "Skip for now" shows only while the box is empty; Edit profile
  saves an emptied bio as none. The seed has Tanvi and Kabir with none and Nandini's under 40.
  Broken once each: `uv run python -m tests.break_guards p851-`, four cases, all red
  (`out/p-851-break-guards.log`), and `node scripts/break-guards.mts p851`, three, all red. T-4.8's
  `t48-about-not-required` left with the requirement. The emoji-counting mismatch went with the
  minimum: at 300 the browser's limit is the stricter, so `errorCopy.ts` is unchanged.
- [ ] P-852 · Onboarding: back visible, and forward to where you'd reached. **Before beta.**
  Worst case: someone who goes back to fix their name can't get forward again without saving
  the screen they went back to. The founder's words (14 October 2026, relayed by the advisor):
  "apna personal detail bharte time previous page pe jane ka option rakho left arrow right
  arrow". Today: a 22 px `ChevronLeft` in `text-mute` (`StepFrame.tsx:51-58`) on every screen
  from Name on; none on birthday, gender and looking-for, by design (D-080). There's no forward:
  `onboarding_step` only moves forward, so it is already the furthest step reached, and saving
  an earlier screen jumps to it (`useAdvance`). Proposed: a clearer back (the arrow with "Back"
  beside it, in ink, not mute), and a forward arrow on any screen behind `placeOf(me)` that goes
  there without writing anything; what to do with unsaved edits on that screen is the plan's to
  say. **Never** a back arrow onto birthday or gender (D-080; gender can't change, CLAUDE.md).
  Filed by Claude, 14 October 2026; its session's block.
- [ ] P-853 · The area picker lists India's major cities. **Before beta.** Worst case: anyone
  outside Phagwara with location off can't finish sign-up truthfully: the picker offers only 17
  Phagwara neighbourhoods (migration `bc589ac265c2`, P-38), so a woman in Delhi either picks one
  and appears 1,000 km from where she is, or stops. The founder's words (14 October 2026,
  relayed by the advisor): "phagwara mei start kar rhe hai but pick my area mei sirf phagwara ke
  area mat rakho ... bade shehron ke naam, aur yeh bhi ki gps off hai to bade sheron ke naam".
  D-013 stays (Phagwara is the launch city for marketing); only the picker's data changes: about
  100 cities (every state and UT capital and the large cities), each with a centroid, in a new
  data migration that names its coordinate source (Wikidata, CC0, preferred). To settle in the
  plan: profiles on a Phagwara area (`area_id` is `ON DELETE RESTRICT`; their `location` is the
  copied centroid and stays); D-220's "nearest area within 2 km", which city centroids would
  almost never meet; the copy that says Phagwara (`en.ts:925` `cityPlaceholder`, `en.ts:1426`
  the waitlist line, held by `page.test.tsx:166`); a search box in a 100-row list. Found beside
  it: 03-SCHEMA:680 still says "40 neighbourhoods", and D-013 still calls Phagwara the
  registered office, which D-058 superseded. Filed by Claude, 14 October 2026; its session's
  block.
- [ ] P-854 · Discovery across India. **Before beta, and before P-391's trigger.** Worst case,
  of doing it plainly: the feed scores every eligible person in India on every page, so it slows
  as the country grows, not as a city does (D-495, about 200 ms a page at 50,000; P-391's
  cell-first fix assumes a city), and someone 2,000 km away who was active today ranks above
  someone in your street who wasn't. The founder's words (14 October 2026, relayed by the
  advisor): "ladke ladki sirf 25km ke andar wale nahi show karo jitna bhi user hai sara dikhana
  hai, specific gender wala rule rakhna". Today: `discovery_radius_km` 25 (`app_config`,
  migration `fa16c0908c2c`; `discovery/service.py:54`), read by the feed and text search only
  (D-540); no upper bound on it. D is `1 / (1 + km / 5)`, a fixed 5 km, not the radius
  (`discovery/rules.py:42`, D-491), so a huge radius doesn't flatten anyone's score: everyone
  far is near 0 (0.048 at 100 km), and R + V + C (up to 0.60) orders them. To settle in the plan:
  the radius (a value covering India's box, about 4,600 km corner to corner, or none); whether
  nearest-first must be strict (distance bands first, then the score) or stays a weight; the
  card's "1900 km"; text search going India-wide; T-6.2's bench re-run at an India spread before
  landing, with P-390 and P-391 re-read. The seeking filter stays exactly as it is. Filed by
  Claude, 14 October 2026; its session's block.
- [ ] P-855 · Where the founder saw men while seeking women. **Investigation only; before
  P-854.** Worst case: a surface that should filter by seeking doesn't, and women seeking men
  are shown women. The founder's words (14 October 2026, relayed by the advisor): "specific
  gender wala rule rakhna yeh nahi ki ladka bola sirf ladki dekhna hai but usko ladke bhi aa
  rhe"; and of the profile by link and search, **his decision**: "yeh dono jagha jaisa hai
  wohi rakho" (keep both as they are, D-493, D-540). Read on `6f4a74c`: the feed, text search,
  liked-you (and its count), swipes, DMs, gifts and album asks all apply seeking both ways
  (`discovery/repository.py:197-201`; a man seeking women never sees a man seeking everyone);
  `@username` search, the profile by id or username, the share page, the chats list and the
  album view don't, by design. No server cache holds a feed; the deck's client pages are
  `staleTime: Infinity`, but no screen changes seeking. Seed has no `everyone` account. Next:
  ask the founder which screen and which two accounts, and read their rows on staging
  read-only; report the cause, propose a fix only if it was a filtering surface. Filed by
  Claude, 14 October 2026; its session's block.
- [x] P-856 · The Knot test reads the real clock. **Now: it fails CI every night.** Worst case:
  every session landing between 00:00 and 00:10 UTC (05:30 to 05:40 IST, when sessions land) gets
  a red CI on a commit that broke nothing, and learns to rerun until green. Seen on 16 October
  2026: D-857's docs-only commit `b30bdc0` failed CI run 38827085059 at 00:02:59 UTC on
  `ConversationScreen.test.tsx` › "shows a Knot as permanent", which expected "Knotted today" and
  found "Knotted yesterday": `knotted_at` was `inMinutes(-10)` from the real clock, and
  `knottedAgo` counts days in the reader's zone, UTC on CI. Reproduced locally at 00:02:30 UTC.
  Filed by Claude, 16 October 2026, at the direction of the founder on the advisor's
  recommendation (Claude, in a separate chat); its session's block, P-850 to P-859.
  **Fixed, 16 October 2026:** the test fakes `Date` alone at local midday today
  (`vi.useFakeTimers({ toFake: ["Date"] })`, undone in the file's `afterEach`). Broken once:
  `p856-web-01-the-knot-test-just-after-midnight` moves the pin to 00:02:30 and the test goes red
  (`node scripts/break-guards.mts p856`). **Swept:** the web's only day-boundary code is
  `conversation/format.ts` (the Knot header and the message dividers). The whole web suite run in
  UTC with its clock moved to 12:00, 00:02:30, 00:30, 01:30, 03:00, 05:45 and 23:58 failed only
  this test, at 00:02:30, and passed whole at 00:02:30 with the fix (1,701); the conversation tests
  passed at eleven times from 23:50 to 00:45 (`out/p-856-clock-sweep/`, the scratch clock shift
  beside its logs). No other web test needed fixing. The API's are P-857.
- [ ] P-857 · API tests that depend on when they run. **Before 2033; the rest is noted, not
  urgent.** Worst case: from 1 January 2033 00:00 IST, `test_a_code_applied_then_an_under_18_date_
  deletes_the_referral` (`referrals/test_apply.py:252`, `@critical`, D-078) fails on every run: its
  `"dob": "2015-01-01"` is checked against the real `today_ist()` and that person turns 18. Fix:
  freeze the clock first, as `safety/test_fraud_signals.py:354` does for the same date. Found by
  P-856's sweep of `api/tests` (a read, not a run: the API's clock can be frozen but Postgres's
  `now()` can't be moved), which found no test failing over a window the way the web's did. Also
  noted: (1) a few tests make two requests unfrozen and expect one IST day, week or financial year,
  so they fail, or pass wrongly, only if 18:30 UTC (or Monday 00:00 IST, or 1 April IST) falls
  between the two requests: milliseconds, about 2 s for `gifts/test_race.py:182`
  (`swipes/test_swipe.py:199, 229`; `discovery/test_feed.py:575`; `threads/test_open.py:628,
  643`; `messages/test_send.py:610, 639, 655, 669`; `gifts/test_lists.py:65`;
  `payments/test_reversals.py:546`); freezing each would close it. (2) `safety/support.py:100` takes
  the UTC year for a dob where conftest takes the IST one, so the age is 26, not 25, from 18:30 to
  24:00 UTC on 31 December; nothing reads it today. (3) `core/test_security.py:313` puts one instant
  in 2040 to sit after the wall clock; from 2040 it still passes and proves less. Filed by Claude,
  16 October 2026; its session's block.
- [ ] P-890 · Rename `build_engine`'s `hide_parameters` to say what it now does. **No deadline.**
  Worst case if never done: none in behaviour; a reader takes the flag for SQLAlchemy's option of
  that name, which hides only the parameters line, and trusts it to hide values alone, which is
  P-80's mistake made again. Since D-990 the flag also installs `_withhold_values`. A rename
  (`hide_values`, say) touches `core/db.py`, `main.py`, `workers/main.py`, `tools/unfreeze.py`,
  `tools/selfie_review.py` and `tests/break_guards.py`'s anchors; kept out of P-80 at the
  founder's direction (16 October 2026). Filed by Claude building P-80; its session's block.
- [ ] P-891 · Two tests order ledger rows by a `created_at` that ties. **Before the next busy
  landing day.** Worst case: a good commit's `make test` goes red at random, and landing is held,
  or a session learns to rerun reds until green, which is how a real red gets through.
  `test_swipe.py`'s and `threads/test_open.py`'s `_ledger` sort by `LedgerEntry.created_at`; the
  `db` fixture runs every write in one rolled-back transaction, where `now()` is fixed, so the
  setup's `admin_grant` and the request's debit carry the same time and either may come last.
  Seen once, on 16 October 2026: `test_a_mans_super_like_debits_five_through_the_wallet` read
  `admin_grant` as the last entry on P-80's landing run, having passed on that code twice before.
  Fix: order by something that follows insertion, or assert on the set. Filed by Claude landing
  P-80; its session's block.
- [ ] P-820 · Tell every active admin by push when an account is frozen automatically. **Before
  real users** (P-800's other half). Worst case: a woman frozen by three colluding reporters (D-901)
  waits until someone opens `/admin/freezes`, which now lists her (D-928), or the audit log; nobody
  is told it happened. Fix: a notification kind of its own, sent to every `admin` who is `active`,
  which no user-facing setting governs, opening `/admin/users/{id}`; pushes are off until D-857 and
  P-755, so it may land as an in-app row first. Filed by Claude building T-9.5, 16 October 2026; its
  session's block, P-820 to P-829.
- [ ] P-821 · An E2E journey through `/admin`. **Before real users.** Worst case: the panel's gate,
  its nonce CSP and its sign-in are proved only by unit tests, never by a real browser, so a build
  that serves `/admin` without its nonce (D-541) or lets the 404 slip (P-30) passes CI. Today:
  `AdminGate.test.tsx`, `security-headers.test.ts` and `proxy.test.ts` hold them in vitest; no
  Playwright journey signs in as a moderator, and `api/tests/e2e_server.py` has no way to make one.
  Fix: an e2e helper that sets a test number's role, and a journey that opens `/admin` as a user
  (the 404 page) and as a moderator (the dashboard, no CSP violation), within the OTP budget
  (P-680). Filed by Claude building T-9.5, 16 October 2026.
- [ ] P-822 · Page the user detail's lists. **Before beta.** Worst case: support reads an account
  with more than 50 ledger entries, reports or Threads and sees only the newest 50, with nothing
  saying more exist, and misses the entry that matters. Today `GET /admin/users/{id}` returns the
  newest 50 of each (`admin.rules.DETAIL_LIMIT`, D-920). Fix: a `next_cursor` per list, or routes of
  their own (`/admin/users/{id}/ledger`, and so on). Filed by Claude building T-9.5, 16 October 2026.
- [ ] P-823 · A staff-approved public photo never gets its face compared. **Before real users.**
  Worst case: a photo the worker couldn't score, approved by a moderator, is someone's main photo,
  and their badge (D-393) never comes, since only the worker's approval queues `match_photo`, from
  the faces Sightengine counted; staff approval has no face count (D-925). Fix: queue the comparison
  on a staff approval when the owner is verified, and let `match_photo` find the face itself, or
  send the photo back through the worker for its scores first. Filed by Claude building T-9.5,
  16 October 2026.
- [ ] P-920 · Remove Fly from Velora. **After `api.staging` serves from Mumbai and the founder's
  phone test passes, on his word.** Worst case if left: two deploy paths for one environment, a
  Fly app billing for nothing, and `Fly-Client-IP` still allowed, a header any later Fly-shaped
  mistake could configure where the client writes it. One small commit: `infra/fly.*.toml`, Fly's
  jobs in `deploy.yml` and `deploy-production.yml`'s Fly path, `Fly-Client-IP` out of
  `PROXY_CLIENT_IP_HEADERS` (and the tests and break cases that allow it), the tools' `flyctl
  ssh` lines (`selfie_review`, `unfreeze`, `storage_probe`, `sightengine_shape`) to `gcloud compute
  ssh … docker compose exec`, `infra/STAGING.md`'s Fly sections, `CLAUDE.md`'s stack and infra
  lines, `scripts/migrate-with-url`'s comment, `README.md`. Then the founder removes
  `FLY_API_TOKEN` and `FLY_WORKER_API_TOKEN` from GitHub's `staging` environment and destroys
  `velora-api-staging`, `velora-worker-staging` and the empty `velora-api` on Fly. Filed by Claude
  building P-49, 18 October 2026.
  **Two commits, not one** (the founder, 18 October 2026, on the advisor's recommendation, relayed;
  built by Claude in P-49's block):
  1. **Now** (T-9.12 waits on it): `deploy.yml` deploys nothing to Fly. Its `api — Fly` job goes;
     `web` waits for `vm`, and `smoke` for `vm` and `web`, with `EXPECT_API_VIA=Caddy`, so
     `api.staging` is proved to be the VM's Caddy and a record pointed back at Fly fails it.
     `infra/STAGING.md`, `CLAUDE.md`'s hosting line and `scripts/staging-smoke`'s comment say so.
     Fly's three apps stay up, untouched, the rollback: degraded, since Fly's API keeps the last
     image Fly built (`infra/STAGING.md`, "Rollback before P-920"). **Done when** `main`'s staging
     deploy of it is green with no Fly job, `web` started after `vm`, and `smoke` logging `API
     answered through Caddy` at `api.staging`; and Fly's apps, read without changing them, as they
     were (`velora-api-staging` with its machine, `velora-worker-staging` at 0).
  2. **On the founder's word, after a day of staging on Mumbai, and only once P-921's production
     path exists** (asked before it starts): the rest of the list above, `deploy-production.yml`'s
     Fly path and `Fly-Client-IP` among them. `Fly-Client-IP` waits for it, though D-1021 ties it
     to Fly's staging deploy, because `deploy-production.yml`'s Fly config still reads it. The Fly
     apps are destroyed and `FLY_API_TOKEN` removed with Fly's worker app and the token last.
  **Not counted until commit 2:** Fly's idle API may still hold `velora_api` connections from before
  the cutover, beside the VM's 17 under the role's 20 (`infra/STAGING.md`'s budget; unmeasured).
- [ ] P-921 · Production on its Mumbai VM. **Before REL-1.** Worst case: a release tag deploys to
  Fly's empty `velora-api`, or to a VM whose secrets are half set, and fails on release day.
  `deploy-production.yml` deploys the exact image staging ran (its digest, copied from staging's
  registry, which production's deploy account may read, D-1022) to `velora-api-prod` on a `v*` tag
  only (D-075), and its smoke checks `api.veloraapp.co.in` with `EXPECT_API_VIA=Caddy`.
  Before it: production's `DATABASE_URL` (the `velora_api` role on `velora-prod` first), `REDIS_URL`,
  Razorpay's three and Sightengine's two into Secret Manager by `scripts/gcp-secrets production`,
  and **`SENTRY_DSN`** (the `velora-api` Sentry project's DSN, empty in `velora-ic-prod` on 18
  October 2026; required in `infra/gce/secrets.api` and `secrets.worker`, so the deploy stops
  without it, T-9.12, D-1001), and the Apple Passwords copies; `NEXT_PUBLIC_SENTRY_DSN` on the
  `velora-production` Vercel project, as Config (`infra/OBSERVABILITY.md` §1); the `production` environment's three GCP variables; the
  Cloudflare record `api` from Fly's CNAME to an A record for `34.180.56.204`, DNS only; the
  worker on (`/etc/velora/worker-on`); and `/privacy`'s "Every request you make is handled by our
  servers in Singapore" changed to Mumbai **in the same change** that moves production's path (the
  founder, 17 October 2026), with `infra/PRODUCTION.md` rewritten. Filed by Claude building P-49,
  18 October 2026.
  **Production's Fly path must be replaced before P-920's second commit removes it** (the founder,
  18 October 2026); the release gate also refuses today without Vercel Pro and Supabase Pro.
- [ ] P-922 · Nobody is told when a VM is down. **Before real users.** Worst case: production's
  only VM stops, or Caddy can't renew its certificate, and the first to notice is a user. Fly
  didn't alert either. An uptime check on `/readyz` from outside (Google Cloud Monitoring's, or
  any), alerting the founder; and a disk-space alert. Filed by Claude building P-49, 18 October
  2026.
- [ ] P-923 · Clean up the setup wizard's projects. **When convenient; before any new project is
  needed.** Worst case: projects billing for nothing, an organisation-wide log sink copying logs to
  a `global` bucket, and no free slot on the billing account (5 projects at most, D-1023), so a new
  project can't be linked. Created 16 October 2026 by Google Cloud's setup wizard: organisations
  `312879430450` and `760891178918` (both `shubhamom0820-org`), four folders, and the projects
  `cs-project-enarzzsb` (development), `cs-project-hnou8upo` (central-logging-monitoring, still
  billed), `cs-project-imxxsyf5` (prod), `cs-project-p1ikf4nc` (nonprod) and three `google-mpf-*`;
  also `project-07f07992-5151-4c8d-8ad` (My First Project, 3 October 2026, still billed) and
  `project-379ffb37-d51c-4141-8d2` (14 September 2026). The founder unlinked billing from
  `cs-project-enarzzsb` and `cs-project-imxxsyf5` on 17 October 2026. The founder decides what goes.
  Filed by Claude building P-49, 18 October 2026, at the founder's request.
- [ ] P-924 · Images are built and pushed by CI, never from the founder's Mac. **Noted, nothing to
  build.** On 18 October 2026, pushing P-49's image from the Mac to Artifact Registry broke twice
  on the same 150 MB layer inside Docker Desktop's own proxy (`http.docker.internal:3128`: a broken
  pipe, then a timeout); Google refused nothing. Restarting Docker Desktop to change its upload
  settings would stop every session's shared Postgres, Redis and S3 (`restart=no`), so it wasn't
  done. If a hand push is ever needed, from somewhere other than Docker Desktop. Filed by Claude
  building P-49, 18 October 2026.
- [x] P-925 · Staging's smoke check expects `/admin` to be a 404, and T-9.5 made it a page.
  **Now: every staging deploy since `cc04268` is red.** Worst case: production's release gate
  refuses every release, since it needs a green staging deploy of the commit (D-075), and a real
  failure in the smoke check hides behind the known one. Run 38904036696 (16 October 2026): every
  job green but `smoke`, which says `web /admin hidden (P-30): …/admin returned 200, want 404`.
  `scripts/staging-smoke` should check what P-30 meant now that the panel exists: the page shows
  nothing but its gate to a visitor without a moderator's session. Found by Claude building P-49,
  18 October 2026; outside P-49, so not changed there.
  **Built, 18 October 2026 (the founder's approval of the plan):** `/admin` must answer 200 with
  none of the panel's own words outside its scripts, `noindex, nofollow` and `no-store`;
  `robots.txt` must not name it; and the real protection, `GET /v1/admin/metrics` without a token,
  must be a 401 `AUTH_REQUIRED` with no data (D-024). With it, P-49's own fix: the VM's check
  reads `Via: 1.1 Caddy` (`EXPECT_API_VIA`), since Caddy passes the API's `Server: uvicorn` through,
  and a literal carriage return P-49 left in the script is the text `'\r'` again.
  `scripts/staging-smoke-test` runs it against a stub broken one way at a time; CI runs it. Both
  paths passed against live staging before landing. **Ticks when** `main`'s staging deploy is
  green, both smoke jobs included.
  **Done, 18 October 2026:** landed as `cfc8419`; `main`'s staging deploy, run 39121926134, green
  in every job, `smoke` and `vm-smoke` included: the first green staging deploy since `cc04268`.
- [ ] P-926 · Switch LLMNR off on the VMs. **Before real users; not urgent.** Worst case: if the
  firewall ever opened UDP or TCP 5355 by mistake, the VM would answer link-local name queries
  from the internet. Read on the staging VM, 18 October 2026: `systemd-resolved` listens on
  `0.0.0.0:5355` and `[::]:5355`; the firewall blocks it (only 80 and 443 answered from outside).
  `infra/gce/startup.sh` writes `LLMNR=no` (and `MulticastDNS=no`) into
  `/etc/systemd/resolved.conf.d/`, restarts `systemd-resolved`, and a check from the VM shows
  nothing on 5355; the metadata set again and the VMs rebooted, on the founder's word. Filed by
  Claude building P-49, at the founder's direction.
- [x] P-927 · Photo moderation through the Mumbai VM's worker, end to end: **closed as a note, the
  founder's call, not proved** (18 October 2026, on the advisor's recommendation, relayed): not a
  blocker, and P-920 doesn't wait for it; the first real photo will show it. What stays unproved:
  moderation (Sightengine and R2) has run on the VM only in tests and its settings check, so a fault
  there (an egress rule, a key, a memory peak on a 12-megapixel photo; P-49 read 1,013 MB with the
  worker idle) would show first as new photos stuck at `pending`. The founder's photo attempts on 18
  October never reached staging's servers (P-49's record). Filed by Claude building P-49, 18 October
  2026.
- [ ] P-830 · Two parts of a Thread's expiry that no browser journey has seen. **Before beta.**
  Worst case: a man watching his open Thread when the hour runs out keeps his composer and its
  countdown at "Ran out" until he reloads, with nothing telling him why his send fails; or he
  sends into it and is shown nothing at all. T-7.13's J7 reloads his screen after
  `POST /v1/test/threads/{id}/expire` (D-930), because waiting on the worker's sweep could take a
  minute, so two paths stay unseen in a browser: (a) the sweep's `thread.expired` event reaching
  an open conversation and replacing his composer with the expired panel (T-7.12's handler, tested
  only in vitest); and (b) his send into a Thread that ran out while his screen still showed it
  live, refused `THREAD_EXPIRED`: the composer shows "The hour ran out before that was sent." and
  asks the Thread again (`ConversationScreen.tsx`), which then replaces the composer with the
  panel, so the note may be gone as soon as it appears, and his draft's fate is unchecked. The API
  half of (b) is tested (`test_expire_thread.py`). Fix: a journey (or a step in J7) that expires
  the Thread while both screens are open and waits for the sweep (up to a minute, the worker's
  loop), then one where he sends before it; decide with the founder whether the note should
  survive the panel. Filed by Claude building T-7.13, 18 October 2026, at the founder's direction;
  its session's block, P-830 to P-839.
- [ ] P-841 · Cap the reconciliation's alert lines. **Before real users; not urgent.** Worst case:
  one bug that moves many balances (a migration, a bad backfill) makes `reconcile_ledger` log one
  `wallet.ledger_mismatch` error per wallet, and T-9.12 forwards each to Sentry, so a single
  morning could spend the month's error quota and hide every other alert after it. T-9.9 logs
  every mismatch, as its approved plan says (D-940). Decide with T-9.12's Sentry plan in hand: a
  cap of lines per run with a count in a summary, or Sentry grouping and a rate limit on that
  event. Filed by Claude building T-9.9, 18 October 2026.
- [x] P-842 · `scripts/ci-gate` (or `/done`) tries once more on exit 4, after a short wait, and
  records that it did. **Before more sessions land at once; small.** Worst case: a gate that exits
  4 on a moment's trouble reading GitHub sends a session down `/done`'s manual path, so a commit
  lands on `main` with only the local half of the landing guard (`VELORA_PUSH_GATE_MANUAL_PATH=1`)
  when CI could have vouched for it a minute later; at best it stops a landing that was fine.
  Three gates hit it on 18 October 2026 while several sessions polled GitHub together (the
  founder's count). T-9.9's was one: run 39132083066, CI for `afb2be2` on `t-9.9-ledger-audit`;
  `gh auth status` was fine, `gh api rate_limit` read 4,978 of 5,000 moments later, and the gate
  run again for the same commit went green on the same run, as both occurrences `/done` records
  did (4 and 14 October). Fix: on exit 4, wait (30 s or so) and read the same run once more, never
  a new run and never on exits 1, 2, 3, 5 or 6; print a line saying it retried, with the run id
  and time, so each occurrence is on the record; a second exit 4 is final. `scripts/ci-gate-test`
  covers both: a flake that clears on the retry, and one that doesn't. `/done`'s exit-4 paragraph
  then says the gate retries itself. Filed by Claude after T-9.9 landed, at the founder's
  direction, 18 October 2026. **Done 19 October 2026:** the gate's own, after
  `CI_GATE_RETRY_WAIT` (30 s): the same request once more, its line naming what it was reading and
  the time; a second exit 4 is final and says so; exit 5 never retries. `scripts/ci-gate-test`'s
  `flake-clears`, `flake-persists` and `github-answers-with-an-error` hold it (red on the gate
  before it; a gate that retried exit 5 too was caught). `/done` says it. A network failure the
  gate reads as exit 5 is P-881.
- [ ] P-880 · `/login` tells people it is protected by reCAPTCHA, as Google requires. **Before
  REL-1** (on its Needs line). Worst case: a Firebase build's `/login` runs Google's invisible
  reCAPTCHA (T-3.14) with its badge hidden and no notice in its place, which breaks reCAPTCHA's
  terms, and someone signing in is never told on that screen that Google checks them. Google's
  terms allow hiding the badge only if the page says instead that the site "is protected by
  reCAPTCHA and the Google Privacy Policy and Terms of Service apply", with both linked. Not
  checked: whether our build shows the badge or hides it. Check it on staging, in the browser, the
  way a person sees it; if it shows, record that and close this; if it is hidden (by our CSS or by
  Firebase's settings), show Google's notice near "Send code", on Firebase builds only, as the
  Google consent line is (D-081), with a test. `/privacy` names reCAPTCHA already (P-71). Found
  planning P-71; filed by Claude at the founder's direction, 18 October 2026, from this session's
  block (P-880 to P-889).
- [ ] P-860 · A hand check with real screen readers: VoiceOver on an iPhone and TalkBack on an
  Android phone, sign-up to a Thread. **Before launch.** Worst case: a screen that passes axe and
  T-9.11's keyboard walk still reads out wrongly or traps a screen-reader user (a gesture that
  never reaches the page, an announcement said twice or never), and nobody would know until a
  person who relies on one complains. Automation checks names, roles and focus, not what a reader
  says. Record what each one said per screen in `out/`. Filed by Claude building T-9.11, 18
  October 2026; its block, P-860 to P-869.
- [ ] P-861 · Say new messages, the hour running out and "Not sent" in the conversation.
  **Before launch.** Worst case: a screen-reader user in a Thread never hears her reply arrive,
  or that his hour ran out, and goes on typing into a read-only Thread; the message list is a
  plain `<ol>` and `Countdown`, `ExpiredPanel` and a failed bubble announce nothing
  (`MessageList.tsx`, `ExpiredPanel.tsx`). Outside T-9.11's list ("screen-reader names for swipe
  actions"), so filed, not built. Fix: a polite live region for an arrival while the screen is
  open, one for the panel appearing, and the failed bubble's words in its name; vitest for each.
  Filed by Claude building T-9.11, 18 October 2026.
- [ ] P-862 · The voice note's record button starts on press-and-hold only, with Enter and
  Space beside it, and has no click. **Before launch; small.** Worst case: a screen-reader user
  can't record at all, if their reader's double-tap sends a click and no pointer down
  (`MicButton.tsx`, `onPointerDown`). Unconfirmed: settle it in P-860's hand check, then add a
  click that toggles recording if it fails. Filed by Claude building T-9.11, 18 October 2026.
- [ ] P-863 · The public page's photo has `alt=""` (`SharedProfileView.tsx`). **Before launch;
  small.** Worst case: a screen-reader visitor to `/@username` is told nothing of the one photo
  the page exists to show. `(share)` is outside T-9.11's `(app)` and admin walk. Fix: `alt` as the
  profile's gallery says it ("Photo of Priya"), and the page added to an axe run. Filed by Claude
  building T-9.11, 18 October 2026.
- [ ] P-864 · Field borders below WCAG 1.4.11's 3:1. **Before launch** (the founder, 18 October
  2026). Worst case: a person with low vision can't see where to type: a field's only edge is
  `--line`, 1.35:1 on `--surface` (`--line-strong` 1.57:1), and nothing else marks it until it
  has focus. T-9.11 left it, at the founder's direction, since it changes the prototype's look on
  every field. Fix: a border token at 3:1 or more for inputs (and the toggle's off track), checked
  in `contrast.test.ts` as a non-text pair, D-014's palette otherwise unchanged. Filed by Claude
  building T-9.11, 18 October 2026.
- [ ] P-865 · The API's access log records the socket's ticket. **Before REL-1** (the founder,
  18 October 2026). Worst case: anyone who can read the API's logs (Fly's log stream, a support
  export, a log drain) holds a ticket that opens a person's socket, their messages and events
  arriving live, for as long as it is still unused (single use, 30 s, T-7.4). Seen in T-9.11's
  E2E runs: uvicorn's access log prints the path and query, `"WebSocket /ws?ticket=…" [accepted]`,
  against rule 15 (no tokens in logs). Fix: the access log strips or redacts the query string,
  for `/ws` at least or for every path (the ticket is the one secret a URL carries by design;
  D-080 keeps numbers out of URLs),
  with a test that a socket's ticket, and a query on any other path, never reach the log line.
  Filed by Claude building T-9.11, 18 October 2026, at the founder's direction; its block, P-860
  to P-869.
- [x] P-881 · `scripts/ci-gate` reads a network failure as "couldn't reach" (exit 4), not "GitHub
  answered" (exit 5). **Before more sessions land at once; small.** Worst case: a TLS timeout or a
  dropped connection while the gate reads a run exits 5, "never a case for the manual path" and
  never retried (P-842), so a session either stops a good landing or reruns a gate whose exit is
  meant to forbid it. The gate tells 4 from 5 only by whether `gh api rate_limit` fails a moment
  later; a network blip that has cleared by then reads as an error GitHub gave. Seen 18 October
  2026: P-222's gate exited 5 with "TLS handshake timeout" from `gh run view`, and was rerun once
  by the rule for network errors. Fix: also read gh's own error text, so transport failures (TLS
  handshake timeout, connection reset or refused, a timeout awaiting headers, no such host) are
  exit 4 and go through P-842's one more try, while anything GitHub answered (an HTTP status) stays
  5; tests in `scripts/ci-gate-test` for each. Filed by Claude building P-842, at the founder's
  direction, 19 October 2026, from this session's block (P-880 to P-889).
  **Done 19 October 2026:** `NETWORK_ERRORS` in the gate: gh's text for a request that got no
  answer, read only when the text has no HTTP status; it goes through P-842's one more try, and
  exit 4 names the error. A 5xx and text the gate doesn't know stay 5. `ci-gate-test` holds eight
  transport texts clearing, one persisting, a 502, an HTTP 404 that says "timeout", unknown text
  and a refused token (each transport case red on the gate before it; the HTTP rule checked by a
  break).
- [ ] P-930 · T-9.10 on the test phone, read by the founder. **Before launch** (the founder, 19
  October 2026), **once P-0.9's phone is bought.** Worst case: `/discover` loads in under 2 s on
  a desktop slowed four times and takes far longer on the phones men in Phagwara carry, over the
  4G they actually get, and the first screen of the paid product feels broken before anyone
  swipes. T-9.10's readings are a desktop
  stand-in (`web/bench/first-load.spec.ts`, D-1030), kinder than the street: no TLS, an API that
  answers at once. On the phone, by Chrome's remote debugging over USB: `/discover` cold, ten
  times, on DevTools' Fast 4G and on the phone's own 4G in the launch city, its LCP from the
  performance panel; record the range in T-9.10's tick, beside the stand-in's. T-9.10's box waits
  for this, P-931 and P-500. Filed by Claude building T-9.10, 19 October 2026, at the founder's
  direction; its block, P-930 to P-939.
- [ ] P-931 · Right-sized photos. **Before launch** (the founder, 16 October 2026). Worst case: a
  man opening Chats on mobile data downloads twelve 281 KB photos, about 3.4 MB, to fill twelve
  48-pixel avatars (10.16 times the pixels they show, T-9.10's bench), every time the list is
  fresh; Liked you 2.71 times. On a prepaid pack that is money, and on a slow line it is the list
  arriving last. Every approved photo is one 1,600-pixel copy (D-092). Fix: the worker writes
  smaller copies beside each public photo (sizes from the screens' boxes at 3×: about 160, 480
  and 960 pixels), their keys in `core/storage_keys.py`, and the API returns them where it
  returns `main_photo_url` and `photo_urls`. **Every deletion path deletes them too:** D-093's
  minor (every copy, read back as gone), `delete_files`, the erasure (D-503) and a ban; a copy
  that outlives its photo is the worst of it. Existing photos backfilled. Proved by T-9.10's
  bench, every screen within D-1030's 2×. Filed by Claude building T-9.10, 19 October 2026.
- [ ] P-932 · One 183 ms frame in the deck's first drag. **Before beta, with P-500.** Worst case:
  the first swipe after the deck loads stutters, the one that sets how the app feels. Seen once
  in four sessions of `web/bench/deck-fps.spec.ts` on T-9.10's branch, in its first run at 4×,
  never in four of `main`'s (`out/t-9.10-deck-fps*.log`); unsettled whether T-9.10's change
  causes it. A likely cause, unproved: the photos behind the top card (D-1031) first decoded when
  the drag uncovers them. Settle it with a Chrome performance trace of a first drag on each
  side; if it is the decode, decode them before they are shown (`img.decode()`, or
  `decoding="async"`), and measure again. Filed by Claude building T-9.10, 19 October 2026.
- [ ] P-933 · The first load measured against staging. **Before beta.** Worst case: production's
  first load is a second slower than T-9.10's reading and nobody knows, since the bench's API
  answers at once and nothing in it is TLS: each origin's handshake (the API and the CDN, one or
  two round trips each, 165 to 562 ms on the presets) and the API's database time in Mumbai are
  missing. Run `first-load.spec.ts`'s readings against staging's web, API and CDN (the same
  presets, the phone's screen), and try `preconnect` to the API and the CDN, which the bench can't
  measure. Filed by Claude building T-9.10, 19 October 2026.
- [ ] P-934 · The deck's frame bench serves a 480 × 600 photo, and says 1,200 pixels. **Small;
  with P-500.** Worst case: T-6.5's and T-9.10's 60 fps readings decode a photo with a
  seventh of a real one's pixels (51 KB against 281 KB, `chari_2017.jpg`), so a decode that
  drops frames on a real 1,280 × 1,600 photo never shows. `deck-fps.spec.ts`'s comment says "a
  real 1,200-pixel photo".
  Fix: serve `bench/fixtures/photo-1600.jpg` (T-9.10's, through our own re-encode), correct the
  comment, read it again. Filed by Claude building T-9.10, 19 October 2026.
- [ ] P-935 · `scripts/ci-gate main` vouches for the local `main`, not `origin/main`. **Before
  REL-1** (the founder, 19 October 2026). Worst case: a session checks `main` after landing, the
  gate prints "CI is green", and the green belongs to an older commit, while the commit just
  landed on `origin/main` is red or never ran; nobody looks again, and a release is tagged on
  trust in a check that read the wrong commit. The gate resolves its ref with `git rev-parse` and
  never fetches (`sha="$(git rev-parse --verify "${ref}^{commit}")"`), so `main` is whatever the
  checkout last pulled. Seen 19 October 2026, landing T-9.10: from the main checkout, still at
  `74c9d46`, `scripts/ci-gate main` went green on run 39158733238, T-9.11's, while `origin/main`
  was `10b6f6a`; that commit's own run (39226466374) was read from `gh run list --commit`. Fix:
  for a branch argument, fetch it and gate `origin/<branch>`'s SHA, or refuse loudly, naming both
  SHAs, when the local branch is behind or apart from `origin/<branch>`; tests in
  `scripts/ci-gate-test` that a stale local `main` never goes green for an older commit, and the
  /done text's manual-path step 4 checked against it. Filed by Claude after landing T-9.10, at
  the founder's direction, 19 October 2026, from T-9.10's block (P-930 to P-939).
- [ ] P-866 · Make T-9.11's accessibility walk shorter, so CI's E2E fits comfortably. **Before
  REL-1** (the founder, 19 October 2026). Worst case: every landing's CI run outlasts
  `scripts/ci-gate`'s wait and each session waits it out twice, or a run near the limit is cut
  off and read as a failure, so landings slow and gates get re-run by habit. Measured landing
  T-9.11: `e2e/a11y.spec.ts` takes 3.6 min on each project, against the plan's 1 to 2 (two
  sign-ups, then 14 `(app)` screens walked as him and again as her, 9 admin screens as staff, and
  his PIN paced under the API's 10 checks a minute); CI's runs for `806bd7d` and `74c9d46` took
  about 23 minutes, past the gate's 20, and both went green on the gate's second wait. Fix: walk
  each `(app)` screen as one person (`walkers` in `e2e/a11y-routes.ts`, its test changed to
  match), keeping both only where the screen differs by gender (wallet, the chat's countdown,
  the deck's prices), and fewer full loads, so fewer PIN unlocks to pace; measure the spec before
  and after, both projects, and record both. The gate's own wait (20 to 35 minutes) is the
  Proposed-tasks session's, with P-881: not this. Filed by Claude after T-9.11 landed, at the
  founder's direction; its block, P-860 to P-869.
- [x] P-882 · `scripts/ci-gate` waits long enough for a run with the E2E. **Now; small.** Worst
  case: every landing whose run includes the E2E exits 3 ("didn't finish"), on a run that goes
  green, and each session waits and runs the gate again, or stops to ask. The gate waited 20
  minutes; since T-9.11's accessibility walk joined the E2E, a branch's whole run took 23, 21, 25
  and 25 minutes (18-19 October 2026; 12 to 18 before it), its E2E starting only once the API's
  job is done. P-842's landing exited 3 that way on run 39160922836. Filed by Claude at the
  founder's direction, 19 October 2026, from this session's block (P-880 to P-889). **Done 19
  October 2026:** `FINISH_TIMEOUT_DEFAULT=2100` (35 minutes) in the gate, its reasons, P-866 and
  P-883 in its comment; the gate's waiting line states its limit, and `ci-gate-test`'s
  `default-wait` pins the literal (red with 1200).
- [ ] P-883 · Lower `scripts/ci-gate`'s wait once P-866 has shortened the walk. **Needs:** P-866
  landed. **Before more sessions land at once; small.** Worst case: the gate keeps waiting 35
  minutes for a run that takes far less, so a run that hangs holds the landing lock that much
  longer before anyone is told, while sessions queue behind it. P-882 raised it from 20 to fit
  T-9.11's walk; P-866 shortens the walk and leaves the gate's wait to this. Fix: after P-866
  lands, measure ten branch runs with the E2E from start to finish, set `FINISH_TIMEOUT_DEFAULT`
  in `scripts/ci-gate` to the longest plus headroom, and `ci-gate-test`'s `default-wait` literal
  with it. Filed by Claude at the founder's direction, 19 October 2026, from this session's block
  (P-880 to P-889); narrowed the same day to the half P-866 doesn't cover.
- [ ] P-900 · Upload the web's source maps to Sentry. **Before the first real users, or the first
  web error nobody can read.** Worst case: a browser error in production arrives as a type and a
  minified stack (`a.js:1:23456`), with its message blanked by design (D-1003), so nobody can tell
  where it happened, and the fix waits for a user to describe it. Skipped in T-9.12 by the
  founder's call (D-1000): it needs `withSentryConfig` and a `SENTRY_AUTH_TOKEN` with
  `project:releases` in Vercel's build environment, a secret where today there is none; the maps
  must be uploaded and then deleted from the deploy, never served. Filed by Claude building
  T-9.12, 16 October 2026; its session's block, P-900 to P-909.
- [ ] P-901 · Move the uptime monitor to production's `/readyz`. **On the production checklist,
  before `v0.1.0`.** Worst case: production's API goes down and nothing says so, since the free
  plan's one uptime monitor watches staging's `https://api.staging.veloraapp.co.in/readyz`
  (D-1005, the founder, 16 October 2026). Change `UPTIME` in `api/ops/sentry_alerts.py` to
  `https://api.veloraapp.co.in/readyz`, environment `production`, run `scripts/sentry-alerts
  --apply` and `--check`, and add the line to 07-CHECKLISTS' production list. Filed by Claude
  building T-9.12, 16 October 2026; its session's block.
- [ ] P-903 · `AuditList.test.tsx`'s "names the system user as System, and filters by one action"
  can exceed vitest's 5 s limit under load. **Before the next busy landing day.** Worst case: a
  good commit's `make test` goes red at random and its landing waits, or a session learns to rerun
  reds until green, which is how a real red gets through (P-891's kind). Seen once, 19 October 2026,
  on T-9.12's rebased commit `a6d005a`: "Test timed out in 5000ms" in the web suite (`make test`,
  1 failed, 1,918 passed), while other sessions ran checks on this machine; CI passed the same
  commit, and the test passed in the morning's run. Alone, the same day, at load 2.6: 105, 105 and
  106 ms in three runs, so the test isn't slow by itself; something in it waits on contention.
  Fix it in that test: find what it waits on (a `findBy` timing out its retry, a fake timer, the
  filter's debounce), never by raising the global `testTimeout`. Filed by Claude landing T-9.12;
  its session's block, P-900 to P-909.
- [ ] P-940 · Install the app on real phones, on staging. **Before REL-1** (the founder, 19 October
  2026), alongside P-930's check on the test phone. Worst case: the banner never appears on a real
  Android phone (Chrome fires `beforeinstallprompt` only on its own engagement rules, before or
  after the page has drawn the banner) or an iPhone installs the app with the wrong name, icon or
  colours, and the first people told to add it to their Home Screen can't, with every test green.
  T-9.7 proved the manifest, the worker and the offline page in desktop Chromium (`e2e/pwa.spec.ts`)
  and the banner in vitest; no phone has installed it. On staging: Chrome on an Android phone (the
  banner appears, Install opens Chrome's dialog, the app opens standalone at `/discover` with the
  V icon and a black title bar, and in airplane mode a reload shows "You're offline", whose "Try
  again" loads the page once back online); Safari on an iPhone (the banner says the Share steps,
  Add to Home Screen gives the V icon and the name, it opens standalone, and the offline page
  shows the same way); closing the banner keeps it closed after a reload. Record each phone, its
  OS and browser versions, and what it showed. Filed by Claude building T-9.7, 19 October 2026,
  at the founder's direction; its block, P-940 to P-949.
