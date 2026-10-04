# Production

> **Not released yet.** The first release, `v0.1.0`, is its own task, REL-1 in `docs/05-PLAN.md`,
> and it waits on three founder items (P-0.14, P-0.15, P-0.16, below). From that moment the site
> is public and crawled, takes real sign-ups, and is plainly commercial. Production itself was
> built and proved in T-2.6; everything else can be set up ahead of the release.
>
> **The API's half is temporary.** Fly has no region in India, so the API runs in Singapore
> while Postgres and Redis are in Mumbai. P-49 moves it to a Compute Engine VM in Mumbai before
> Sprint 4 and redoes every Fly part of this page (the end of this page lists them).

How production is set up, released and checked (T-2.6, D-074, D-075). It copies staging's shape
(`infra/STAGING.md`): this page names production's pieces and says what differs. Where it says "as
staging", follow `infra/STAGING.md` with these names.

## What runs where

| Piece | Where | Name |
|---|---|---|
| API | Fly.io, `sin`, **until P-49** | app `velora-api` → `https://api.veloraapp.co.in` |
| Web | Vercel, its own project | `velora-production` → `https://veloraapp.co.in`; `www.` and the project's own address, `velora-production-one.vercel.app`, redirect there (308) |
| DNS | Cloudflare | zone `veloraapp.co.in`, records DNS-only (§6) |
| Postgres | Supabase, Mumbai (`ap-south-1`) | project `velora-prod`, in an organisation of its own |
| Redis | Upstash, Mumbai | database `velora-prod` |
| Objects | Cloudflare R2 | `velora-prod-public`, `velora-prod-private` (T-4.1); public photos at `https://cdn.veloraapp.co.in` |

## What it costs

Monthly, before GST. The founder decided on 3 October 2026 that both paid plans wait for the
release, the moment production is public and holds real sign-ups.

| Line | Until `v0.1.0` | From `v0.1.0` |
|---|---|---|
| Vercel, team `knot11` | Hobby, $0 | **Pro, $20**, covering staging's project too (P-0.15). Hobby is "non-commercial personal use only" in Vercel's own terms |
| Supabase `velora-prod` | Free, $0 | **Pro, $25** in its own organisation, whose included compute covers this one project (P-0.16). Free keeps no backups |
| Fly `velora-api` | $0: no machine until the first release | **Temporary:** one `shared-cpu-1x` machine with 512 MB, about $3 to $4 at Fly's published rate, the second Fly machine on the bill after staging's. It goes when P-49 moves the API |
| Upstash `velora-prod` | free tier | Fly's `/readyz` check alone pings Redis every 15 s, about 173,000 commands a month: check that against the free allowance when creating it |
| R2 | $0: the buckets exist, empty (T-4.1) | at Cloudflare's R2 rates, not yet read against what photos will cost: check before the release |

## How a release happens

A release is deliberate: a tag `v*` on a commit of `main`. Nothing else deploys production.

1. The commit merges as every task does (`/done`), and staging deploys it.
2. Tag it and push the tag:

   ```
   git tag v0.1.0 <commit> && git push origin v0.1.0
   ```
3. `.github/workflows/deploy-production.yml` runs:
   - **gate** runs `scripts/release-gate` (D-075), which refuses unless the commit is on `main`,
     CI passed for that exact commit, and staging deployed that exact commit with its smoke check
     passing. Production only gets what staging proved. It then reads the production Vercel
     token's expiry: it refuses a token Vercel won't accept, and **warns on the run's page when
     the token expires within 30 days**. And it **refuses while either paid plan is missing**:
     the Vercel team must be on Pro (P-0.15), and velora-prod's Supabase organisation, read
     through the project itself, on a paid plan with backups (P-0.16).
   - **migrate**, **api**, **web**: as staging, with production's secrets.
   - **smoke** runs `scripts/staging-smoke` against production, bodies included. Its canonical
     check fails if the web was built for any other address: a valid but wrong `APP_ENV`
     (`next build` already refuses an unknown one).

To check a commit before tagging it, run `scripts/release-gate <commit>` by hand. Without the
token it skips only the expiry.

**Staging deploys match by name.** Each staging run is named `Deploy staging <commit>` for the
commit it deployed, which is what the gate matches. A staging deploy started by hand counts only
when started with the commit's full SHA.

## Before the first release (`v0.1.0`, REL-1)

Each blocks the release, not the build:

- **P-0.14:** where the registered office is. `/contact` publishes it, and from `v0.1.0` it is
  crawled and archived, past any later change. A judgement, so no check can enforce it: it is on
  REL-1's Needs line.
- **P-0.15:** Vercel Pro. **P-0.16:** Supabase Pro. The gate refuses without them.
- **Production's keys,** generated with their second copy in Apple Passwords, synced through iCloud
  (see "The keys" below).
- **DNS for the apex and `www`** (§6), added on release day: before then nothing should answer
  at `veloraapp.co.in`.
- **P-70, P-71 and P-69,** found building T-3.14, all on REL-1's Needs line: the phone screen
  saying, before anything is typed, that it takes Indian mobile numbers only, so a foreign
  number's digits never text a stranger in India; `/privacy` naming reCAPTCHA, which `/login`
  loads; and the browser API key restricted to our two sites (§8), after T-3.14's staging check.

And three that block only under their condition, all on REL-1's Needs line with the condition
beside them, so none blocks a release that doesn't need it:

- **P-66, if the tag includes T-3.14.** That tag opens sign-in, and until P-66 staging signs in
  through production's Firebase project, `velora-ic`, into the same user pool: acceptable only
  while there are no real users (the founder, 3 October 2026).
- **P-0.18, if the tag includes T-3.14, or falls on or after 2 December 2026:** the Google Cloud
  billing account converted from its free trial to paid, after App Check (P-68). The trial ends
  on 2 January 2027, or sooner if its credit runs out, and Firebase Auth stops with it: after
  launch, an outage with no warning (the founder, 3 October 2026).
- **P-68, if the tag includes T-3.14:** App Check enforced on Firebase Authentication, proved by
  a refused request, not by the console's switch. No console field caps SMS, and our server's
  limits never see a Firebase send, so App Check is what makes a flood need our web app (the
  founder, 4 October 2026).

## Database connections: the budget

Staging's table, unchanged: 2 workers × (`DB_POOL_SIZE` 5 + `DB_MAX_OVERFLOW` 2) = **14**, one
machine (`--ha=false`), and `velora_api` capped at **20** on the role. Redo the sum whenever
workers, machines or pools change.

## Secrets

The rules are staging's ("How secrets get set"): never printed, never an argument, never from the
clipboard. Generate everything fresh; **never copy a value from staging**. Startup refuses the
repo's public test keys, but it can't know a copy of staging's.

- **The Keychain service is `velora-production`**, with the same accounts as staging's:
  `db-owner`, `velora-api-db`, `jwt-secret`, `phone-pepper`, `phone-enc-key`, `code-pepper`.
- **After setting the four keys,** read their shapes on the machine (lengths only) and compare
  each with its stored copy by SHA-256, first 8 hex characters, as T-3.1 did for staging.
- **The second copy lives in Apple Passwords, synced through iCloud,** never only on this Mac (the
  founder, 3 October 2026). A Keychain on one laptop is one laptop away from every production
  key being unrecoverable. Only the founder reads its contents; nobody else ever asks for them.

## The keys: what exists, what each protects, what losing one costs

Read this before touching any key during an incident. It lists consequences, never values. The
values live in three places: Fly's secrets for `velora-api` (they move, unchanged, with P-49), the
Keychain service `velora-production` on the founder's Mac, and **Apple Passwords, synced through
iCloud** (named by the founder on 3 October 2026, with iCloud sync confirmed on in System
Settings). The Passwords copy depends on the founder's Apple Account, not on this Mac, so it
survives losing the Mac: any device signed in to that account, with Passwords syncing through
iCloud, has it.

**The four that cannot be replaced** without losing something:

| Key | Protects | If it leaks | If it's lost | Changing it |
|---|---|---|---|---|
| `PHONE_PEPPER` | The lookup key of every phone number (`users.phone_hash`, `banned_identities`, D-061) | With a database dump, numbers can be recovered from their hashes: India's mobile range is small enough to try every one | Sign-in can't find any account until every number is re-hashed from its encrypted copy, which needs `PHONE_ENC_KEY`. **Every ban is gone for good**: a ban keeps only the hash, so nothing can rebuild it, and every banned person can sign up again | Never, once any number is banned (D-061). Treat it as permanent |
| `PHONE_ENC_KEY` | The stored copy of every phone number (`users.phone_enc`, Fernet, D-061) | With a database dump, every number is readable | **Every stored number is unreadable forever**: no admin view (T-9.5), no export (T-9.6), and no way back if `PHONE_PEPPER` is ever lost too | Put a new key first, `new,old`, and keep the old one until every row is re-encrypted (D-061) |
| `CODE_PEPPER` | Every PIN (argon2id over an HMAC under it, D-062), and sign-in codes in flight | With a database dump, a 4-digit PIN falls in minutes, and people reuse their UPI and ATM PINs | **Every PIN fails** until its owner sets it again, everyone at once; codes in flight fail too | Only with a migration plan: a new one fails every stored PIN (D-062) |
| `JWT_SECRET` | Every access token (D-060) | Anyone can sign a valid access token for anyone, **an admin included**: replace it at once | Nothing is lost: every access token (15 minutes) stops working, and clients refresh with their refresh tokens, which don't depend on it | Any time; signed-in people just refresh |

**The rest can be replaced** without losing data. Each grants access while it's valid, so revoke
a leaked one first, then make a new one:

| Secret | What it opens | Replace by |
|---|---|---|
| `DATABASE_URL` (`velora_api`'s password) | Rows, as the app | A new password on the role in Supabase, then Fly's secret |
| `PRODUCTION_MIGRATION_DATABASE_URL` (the owner) | The whole database, including switching off the ledger's guards (D-046) | A new database password in Supabase, then GitHub's secret |
| `REDIS_URL` | Rate limits and sign-in codes | Upstash's credential reset, then Fly's secret |
| `VERCEL_TOKEN` | Deploying anything to the production site | A new one-year token, then GitHub's secret |
| `FLY_API_TOKEN` | Deploying anything to `velora-api` | `fly tokens create deploy -a velora-api`, piped into GitHub's secret |
| `SUPABASE_ACCESS_TOKEN` | Reading velora-prod and its organisation, nothing else (scoped) | A new scoped token, then GitHub's secret |

## First-time setup

### 1. Supabase

A new **organisation of its own**, so that upgrading it to Pro (P-0.16) pays for this project
alone, and in it the project `velora-prod`, region Mumbai, on Free until the release. Then staging's
steps 2 to 7 exactly: the extensions, the Data API off, the two connection strings, the roles
(`velora_api` with a fresh password, `connection limit 20`), and both SQL checks after the first
release.

Then, for the release gate (D-075), a **scoped access token** (Account → Access Tokens), never a
classic one, which carries the account's full power over every project. It needs read access to
exactly two things: the project `velora-prod` (the gate reads its organisation from it) and that
organisation (the gate reads its plan). Supabase's API names these `project_admin_read` and
`organization_admin_read`; choose the read-only permissions that match, and nothing else. If it's
short of either, the gate says so and refuses. The project's ref, from its URL, goes in GitHub as
a variable (§7).

### 2. Upstash

Redis database `velora-prod`, region Mumbai, TLS on. Copy its `rediss://…` URL.

### 3. Cloudflare R2

Created by the founder on 4 October 2026 (T-4.1), as staging's (`infra/STAGING.md` §3), and each
line is as binding: `velora-prod-public` and `velora-prod-private`, location hint Asia-Pacific
(APAC), Standard storage class.

- **The public bucket is served only at `cdn.veloraapp.co.in`**, its custom domain
  (`PUBLIC_CDN_URL` in `infra/fly.api.production.toml`); the private bucket has no domain.
- **Minimum TLS 1.2 on that domain, not the default 1.0:** 1.0 is broken and these serve users'
  photos; 1.3 would have excluded older Android phones that only speak 1.2. Read from outside by
  Claude on 4 October 2026: 1.0 and 1.1 refused by the server, 1.2 and 1.3 accepted.
- **One Account API token, Object Read & Write, scoped to these two buckets only**: it can't touch
  staging's (the founder's report; not yet proved by its effect, since the token isn't anywhere
  Claude can use it: see below). Staging's token is proved refused here (`infra/STAGING.md` §3).
- **Its two values are not a Fly secret yet.** They go in before REL-1 (§4): until then
  production's API, if started, refuses to start. They are in the login Keychain, service
  `velora-prod`, accounts `r2-access-key-id` and `r2-secret-access-key` (the founder; the item
  names read by Claude on 4 October 2026, never the values). The token's TTL is Forever, so
  **it is rotated before the first production deploy** (the founder, on REL-1's list), and the
  rotated values are the ones that go to Fly.

### 4. Fly (until P-49)

1. The app `velora-api`, in the paid organisation. Its settings are in
   `infra/fly.api.production.toml`; CI starts the image with them on every push.
2. **Secrets:** `DATABASE_URL` (the direct connection, as `velora_api`), `REDIS_URL`,
   `JWT_SECRET` (`openssl rand -hex 64`), and `PHONE_PEPPER`, `PHONE_ENC_KEY` and `CODE_PEPPER`
   (`openssl rand -hex 32` each); and **before REL-1**, R2's token for production's pair,
   `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` (§3), without which the API refuses to start
   (T-4.1). The owner's credentials are not a Fly secret.
3. A **deploy token for this app only**, into GitHub (§7).

### 5. Vercel

1. The project `velora-production`, not connected to Git, framework Next.js, Node 24, in the team
   `knot11`.
2. **Environment Variables → Production:** `NEXT_PUBLIC_API_URL` = `https://api.veloraapp.co.in`
   and `APP_ENV` = `production`, **both Config, not Secret**. `next build` refuses an `APP_ENV`
   it doesn't know, including the `[SENSITIVE]` that a Secret pulls back as.
3. **Domains:** `veloraapp.co.in`; `www.veloraapp.co.in` redirecting to it (308); and the
   project's own `vercel.app` address redirecting to it. Left serving, that address would be an
   indexable second copy of the site.
4. An **access token** for the team, **expiring in one year** (decided 3 October 2026). When it
   lapses, releases stop closed and the site keeps serving; the gate warns 30 days ahead.

### 6. DNS, on Cloudflare

| Type | Name | Target | Read from | When |
|---|---|---|---|---|
| CNAME | `api` | `nwjo8lz.velora-api.fly.dev` | `fly certs setup api.veloraapp.co.in -a velora-api` | any time: nothing calls it until the release |
| CNAME | `@` (the apex) | `f5c6be5b7918e5ec.vercel-dns-017.com` | Vercel's API, `recommendedCNAME` rank 1 | release day |
| CNAME | `www` | `f5c6be5b7918e5ec.vercel-dns-017.com` | the same, for `www.veloraapp.co.in` | release day |

Each target was read by Claude on 3 October 2026, the Vercel ones with
`pnpm dlx vercel api "/v6/domains/<domain>/config?projectIdOrName=velora-production"`.

- **Read each target from the platform; never assume it,** as staging's.
- **DNS only (grey cloud),** as staging's.
- **The apex already holds the mail records** (MX, SPF, DKIM, DMARC; P-0.3). Cloudflare answers
  an apex CNAME with the target's addresses (CNAME flattening), so they coexist. After adding it,
  read MX and DMARC back from our nameservers: mail is the one thing this record could break.
- **HSTS covers every subdomain (D-074):** once a browser has seen the site, every
  `*.veloraapp.co.in` must serve HTTPS for two years. A new subdomain that can't (a mail service's
  click-tracking domain, say) has to get a certificate first.

### 7. GitHub

Settings → Environments → **new environment `production`**, with **Deployment branches and tags
→ selected → the tag rule `v*`** and nothing else. Only a tag release can deploy to it, so no
branch's workflow can read its secrets. Create it before any tag exists: a workflow that names
an environment that doesn't exist creates it, without the rule.

| Kind | Name | Value |
|---|---|---|
| Secret | `PRODUCTION_MIGRATION_DATABASE_URL` | the **session pooler** connection, as the owner |
| Secret | `FLY_API_TOKEN` | Fly's deploy token for `velora-api` |
| Secret | `VERCEL_TOKEN` | the one-year token above |
| Secret | `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from the Vercel project |
| Secret | `SUPABASE_ACCESS_TOKEN` | the scoped, read-only token (§1), for the gate's plan check |
| Variable | `PRODUCTION_API_URL` | `https://api.veloraapp.co.in` |
| Variable | `PRODUCTION_WEB_URL` | `https://veloraapp.co.in` |
| Variable | `SUPABASE_PROJECT_REF` | `velora-prod`'s ref, from its URL |

### 8. Firebase: `velora-ic`, which staging shares

Set up and read back in the console by the founder, 3 and 4 October 2026 (T-3.14). The
recommendations behind the settings were the advisor's (Claude, in a separate chat): no test
numbers, India only, Analytics and Gemini off, both of the budget's Savings boxes cleared. This
machine has no Google Cloud credentials, so no check reads any of it back: each line is the
founder's reading, dated. **Staging shares this project until P-66 (D-065): a change here changes
staging and production at once.**

- **Authentication: plain Firebase Authentication, not Identity Platform.** The upgrade removes the
  3,000 SMS a day ceiling, the only "how many" bound there is (P-0.18). Never take it without the
  founder, and re-derive P-0.18's bound before, not after.
- **Sign-in method → Phone: enabled.** **Turning it off makes the sign-in screen lie.** (the
  advisor's wording, relayed by the founder) Firebase then refuses every number with
  `auth/operation-not-allowed`, the same code it gives a number outside India, and the web can't
  tell the two apart: every Indian user would be told "Only Indian mobile numbers can sign in for
  now", their number blamed for our switch (T-3.14, its check 8b). It can't
  be fixed in code, so it is fixed here: never switch phone sign-in off while `/login` is open.
  Close sign-in in the web first, by a deploy, then the switch.
- **SMS region policy: Allow, India (IN) only.** A number from anywhere else is refused before any
  SMS (T-3.14). **Taking India off the list lies the same way** as switching phone sign-in off.
- **Test phone numbers: none, ever** (D-065): in this project, one would be a permanent sign-in to
  production for anyone who learned the pair. Staging's own project, with its own, is P-66.
- **Authorised domains, exactly:** `localhost`, `velora-ic.firebaseapp.com` and `velora-ic.web.app`
  (Firebase's defaults), `staging.veloraapp.co.in` and `veloraapp.co.in`. `localhost` can't host
  phone sign-in (Firebase's docs). Taking either of ours off stops sign-in on that site.
- **Google Analytics and Gemini in Firebase: off.**
- **The web app `velora-web`:** its config is committed in `web/src/lib/firebase-config.ts`, public
  by design (D-085). The API names the project in `[env]` (`FIREBASE_PROJECT_ID`); no service
  account exists, and none is needed (D-085).
- **Billing:** Blaze, through the Google Cloud free trial, until 2 January 2027 (P-0.18). **Budget
  alert:** ₹500 a month, at 50, 90 and 100% of actual cost, email to billing admins, both Savings
  boxes cleared, so it counts cost before credits. It alerts; it never caps.
- **App Check: not yet** (P-68).

## After a release

The smoke job is the check. By hand:

```
scripts/staging-smoke https://api.veloraapp.co.in https://veloraapp.co.in
```

The first release's own checks are T-2.6's Done-when.

## What P-49 redoes

Moving the API to Mumbai replaces, for production:

- the Fly app `velora-api` and its machine, and `infra/fly.api.production.toml`;
- its secrets, moved with the **same values**: new keys would make every stored phone number and
  PIN unreadable;
- the `api` record at Cloudflare;
- the `api` and `migrate` jobs in `deploy-production.yml`, and §4 and the Fly line above.

The web, the gate, the smoke check and the domains stay.
