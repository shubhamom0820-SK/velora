# Production

> **Not released yet.** The first release is `v0.1.0`, and it waits on three founder items
> (P-0.14, P-0.15, P-0.16, below): from that moment the site is public and crawled, takes real
> sign-ups, and is plainly commercial. Everything else can be set up ahead of it.
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
| Objects | Cloudflare R2 | `velora-prod-public`, `velora-prod-private`, created with T-4.1 |

## What it costs

Monthly, before GST. The founder decided on 3 October 2026 that both paid plans wait for the
release, the moment production is public and holds real sign-ups.

| Line | Until `v0.1.0` | From `v0.1.0` |
|---|---|---|
| Vercel, team `knot11` | Hobby, $0 | **Pro, $20**, covering staging's project too (P-0.15). Hobby is "non-commercial personal use only" in Vercel's own terms |
| Supabase `velora-prod` | Free, $0 | **Pro, $25** in its own organisation, whose included compute covers this one project (P-0.16). Free keeps no backups |
| Fly `velora-api` | $0: no machine until the first release | **Temporary:** one `shared-cpu-1x` machine with 512 MB, about $3 to $4 at Fly's published rate, the second Fly machine on the bill after staging's. It goes when P-49 moves the API |
| Upstash `velora-prod` | free tier | Fly's `/readyz` check alone pings Redis every 15 s, about 173,000 commands a month: check that against the free allowance when creating it |
| R2 | none until T-4.1 | none until T-4.1 |

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
     the token expires within 30 days**.
   - **migrate**, **api**, **web**: as staging, with production's secrets.
   - **smoke** runs `scripts/staging-smoke` against production, bodies included. Its canonical
     check fails if the web was built for any other address: a valid but wrong `APP_ENV`
     (`next build` already refuses an unknown one).

To check a commit before tagging it, run `scripts/release-gate <commit>` by hand. Without the
token it skips only the expiry.

**Staging deploys match by name.** Each staging run is named `Deploy staging <commit>` for the
commit it deployed, which is what the gate matches. A staging deploy started by hand counts only
when started with the commit's full SHA.

## Before the first release (`v0.1.0`)

Each blocks the release, not the build:

- **P-0.14:** where the registered office is. `/contact` publishes it, and from `v0.1.0` it is
  crawled and archived, past any later change.
- **P-0.15:** Vercel Pro. **P-0.16:** Supabase Pro.
- **Production's keys:** where their second copy lives (T-2.6); generate them after that's decided.
- **DNS for the apex and `www`** (§6), added on release day: before then nothing should answer
  at `veloraapp.co.in`.

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
- **The Keychain must not be the only copy** (T-2.6). Losing `PHONE_ENC_KEY` makes every stored
  phone number unreadable; losing `CODE_PEPPER` makes every PIN unverifiable; losing
  `PHONE_PEPPER` silently unbans every banned number. Where the second copy lives is the
  founder's decision, made before the keys are generated.

## First-time setup

### 1. Supabase

A new **organisation of its own**, so that upgrading it to Pro (P-0.16) pays for this project
alone, and in it the project `velora-prod`, region Mumbai, on Free until the release. Then staging's
steps 2 to 7 exactly: the extensions, the Data API off, the two connection strings, the roles
(`velora_api` with a fresh password, `connection limit 20`), and both SQL checks after the first
release.

### 2. Upstash

Redis database `velora-prod`, region Mumbai, TLS on. Copy its `rediss://…` URL.

### 3. Cloudflare R2

With T-4.1, as staging's: `velora-prod-public` and `velora-prod-private`, location hint `apac`.

### 4. Fly (until P-49)

1. The app `velora-api`, in the paid organisation. Its settings are in
   `infra/fly.api.production.toml`; CI starts the image with them on every push.
2. **Secrets:** `DATABASE_URL` (the direct connection, as `velora_api`), `REDIS_URL`,
   `JWT_SECRET` (`openssl rand -hex 64`), and `PHONE_PEPPER`, `PHONE_ENC_KEY` and `CODE_PEPPER`
   (`openssl rand -hex 32` each). The owner's credentials are not a Fly secret.
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
| Variable | `PRODUCTION_API_URL` | `https://api.veloraapp.co.in` |
| Variable | `PRODUCTION_WEB_URL` | `https://veloraapp.co.in` |

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
