# Staging

> **Region (D-048):** the API runs on Fly in **Singapore**, because Fly retired Mumbai. Postgres and
> Redis stay in **Mumbai**, so Indian users' data stays in India — and every query crosses Singapore
> to Mumbai and back, the latency D-048 accepts for now.

How staging is built, deployed and checked (T-1.22, D-046). Production follows the same shape, on
a page of its own that names its pieces and says what differs: `infra/PRODUCTION.md` (T-2.6).

## What runs where

| Piece | Where | Name |
|---|---|---|
| API | Fly.io, `sin` (Singapore; D-048) | app `velora-api-staging` → `https://api.staging.veloraapp.co.in` |
| Worker | Fly.io, `sin`, its own app (T-4.4, D-095) | app `velora-worker-staging`: the API's image as the ARQ worker, no HTTP |
| Moderation | Sightengine, plain image API (T-4.4) | the worker's `check.json` calls; files deleted after processing, by default |
| Web | Vercel, its own project | `velora-staging` → `https://staging.veloraapp.co.in` |
| DNS | Cloudflare | zone `veloraapp.co.in`, records DNS-only (§6) |
| Postgres | Supabase, Mumbai (`ap-south-1`) | project `velora-staging` |
| Redis | Upstash, Mumbai | database `velora-staging` |
| Objects | Cloudflare R2 | buckets `velora-staging-public`, `velora-staging-private`; public photos at `https://cdn.staging.veloraapp.co.in` |
| Phone sign-in | Firebase | **production's** project `velora-ic`, until P-66 (D-065): a change in its console changes production too (`infra/PRODUCTION.md` §8) |

## How a deploy happens

`.github/workflows/deploy.yml`, after CI passes on `main` (or by hand, from the Actions tab, for
any commit whose CI passed):

1. **gate** runs `scripts/ci-gate` on the exact commit. Anything but a passed CI run stops here.
2. **migrate** runs `alembic upgrade head` from CI **as the database owner**
   (`scripts/migrate-with-url`). The owner's credentials live only in GitHub, never on Fly: the app
   runs as `velora_api`, which can't disable the ledger's triggers, and a code-execution bug in the
   app mustn't be one step from doing so (P-18). Then it asks the database where it is, not
   Alembic (P-65): after the commit, `alembic_version` must hold the repo's single head, D-076's
   two triggers must be present and enabled, and D-077's index present, unique and valid. The log
   says what it read (`migrate: alembic_version holds …`). Anything else fails the job, naming
   what it found, so **api** never deploys onto it. The migration is committed by then: a red
   here doesn't undo it, it says the database isn't where the repo thinks.
3. **api** runs `flyctl deploy`. Fly builds `api/Dockerfile` with `api/` as the context, and only
   routes to the new machine once `/readyz` passes.
4. **worker** (T-4.4) runs `flyctl deploy` with `infra/fly.worker.toml`, after the API, with a
   token for the worker's app only (`FLY_WORKER_API_TOKEN`). Its release command,
   `python -m app.workers --check`, runs on a one-off machine with the app's settings and secrets
   first: a missing key stops the deploy with the setting's name. It runs beside **web**; a red
   worker job fails the run, so a release waits for it (D-075).
5. **web** builds and deploys with the Vercel CLI. The project has no Git connection
   (`web/vercel.json` also turns Git deploys off), so the web can't go live around the gate.
   **A red `web — Vercel` job on green code** is most likely Vercel's Hobby upload cap: look for
   `api-upload-free` in its log (P-0.15). The web stays on the last build that uploaded.
6. **smoke** runs `scripts/staging-smoke` against staging from the outside, bodies included:
   `/readyz`, the hidden schema and docs, the web (it must be our build, calling this API), the
   hidden `/admin` and `/dev/*`, and CORS.

**The first deploy happens after T-1.22 merges.** GitHub only triggers a workflow that exists on
the default branch — `workflow_run`, `workflow_dispatch`, and `gh run list --workflow <file>` all
resolve against `main` — so `deploy.yml` can't run from a branch until it's merged (06-TESTING).

## Database connections: the budget

The pool is per process, and the image runs **2 uvicorn workers**, each with its own pool:

| Who | Connects as | How | At most |
|---|---|---|---|
| API | `velora_api` | direct connection, IPv6 (Fly has it) | 2 workers × (`DB_POOL_SIZE` 5 + `DB_MAX_OVERFLOW` 2) = **14** |
| Migrations | the owner (`postgres`) | session pooler, IPv4 (GitHub's runners have no IPv6) | 1, during a deploy |
| Worker | `velora_api` | direct, IPv6 | 1 process × (`DB_POOL_SIZE` 2 + `DB_MAX_OVERFLOW` 1) = **3** (T-4.4, `infra/fly.worker.toml`) |

**17 at most, under the role's 20.** Each app is **one machine**: `deploy.yml` passes `--ha=false`
to both, because Fly's default of two would double each sum (and run the worker's poll twice,
D-091). Supabase's smallest compute allows 60 direct connections, and its own services use some.
Change
`DB_POOL_SIZE` / `DB_MAX_OVERFLOW` in `infra/fly.api.toml`, never the image, and redo this sum
whenever workers, machines or pools change — two machines doubles it. Production starts from this
table, not from a guess.

**`velora_api` has a connection limit of 20**, set on the role itself, so the database enforces the
budget even if a pool setting drifts. 20 sits above the 14 the pools allow, so normal load never
reaches it, and well under the instance's 60, so a runaway pool can't starve the migrations or
Supabase's own services. The worker (T-4.4) brings the sum to 17, still under 20, so the limit is
unchanged. When a second machine or a bigger pool raises the sum past it, raise the limit with it
(`alter role velora_api connection limit N`) and record the new number and reason here.

## How secrets get set

A secret is never printed, never a command-line argument (`ps` shows arguments to every process),
and never taken from the clipboard by a command you copied.

- **A value only you have** (a Redis URL, a token): paste it at a hidden prompt that checks it
  before writing anything. Nothing echoes as you paste; press Enter. In zsh:

  ```
  read -rs 'v?Paste the rediss:// URL (nothing will show), then Enter: '; echo
  if [[ $v == rediss://* ]]; then printf 'REDIS_URL=%s\n' "$v" | fly secrets import --stage -a velora-api-staging; else echo "Not a rediss:// URL, nothing changed."; fi; unset v

  read -rs 'v?Paste the token (nothing will show), then Enter: '; echo
  if [[ -n $v ]]; then printf '%s' "$v" | gh secret set VERCEL_TOKEN --env staging; fi; unset v
  ```

  In bash, `read -rsp 'prompt' v`. **Never `"$(pbpaste)"`:** to run such a command you copy it,
  which replaces the secret on the clipboard, so it can only hand over the command text. In T-1.22
  that put the command itself into Fly's `REDIS_URL`.
- **A value we generate:** straight into your login Keychain (service `velora-staging`), then piped
  from there into Fly or GitHub. Store with `security -i` reading the command on stdin. Never pipe
  into `security add-generic-password … -w`: it prompts twice, so a pipe stores an **empty**
  password and still exits 0.
- **What the Keychain holds** (`security find-generic-password -s velora-staging -a <account> -w`):
  `db-owner` (the database owner's password, which you set), `velora-api-db`, `jwt-secret`,
  `phone-pepper`, `phone-enc-key`, `code-pepper`; R2's token, `r2-access-key-id` and
  `r2-secret-access-key` (§3); Sightengine's, `sightengine-api-user` and `sightengine-api-secret`
  (T-4.4); and the app's `database-url` and `redis-url`, as Fly holds them (T-4.4, added 4
  October 2026 at the founder's direction: anything needed to recreate the environment has a
  second copy outside the platform holding it). `phone-pepper` never changes once a number is
  banned; `phone-enc-key` rotates by putting a new key first, `new,old` (D-061); a new
  `code-pepper` makes every stored PIN fail until it is set again (D-062). The worker's app
  (T-4.4) holds the same four values: **a key changed on one app is changed on both, the same
  day**, or the worker can't read what the API wrote.
- **Settings check URLs, and never echo a value:** a wrong scheme stops the container before uvicorn
  starts, naming the setting (`DATABASE_URL` must be `postgresql+asyncpg://`; `REDIS_URL` must be
  `rediss://` outside local), and a validation error never prints what it was given.

## First-time setup (the founder, in each dashboard)

Nothing here goes in git. Generate every secret fresh for staging; never reuse a local one.

### 1. Supabase

1. New project `velora-staging`, region Mumbai (`ap-south-1`). Keep the database password in your
   password manager.
2. **Database → Extensions:** enable `postgis`, `pg_trgm` and `citext` (`pgcrypto` is on already).
   Supabase installs them in the `extensions` schema. Never downgrade this database to base: T-1.8's
   `downgrade()` drops extensions Supabase manages.
3. **Turn the Data API off** (Project Settings → Data API). Left on, Supabase serves every table in
   `public` over its REST API to anyone with the project's anon key, which Supabase treats as
   public. The first migration also strips `anon` and `authenticated` of every privilege on our
   tables; the check in step 7 proves both halves.
4. Copy two connection strings, as `postgresql+asyncpg://…`:
   - the **direct** connection (`db.<ref>.supabase.co:5432`) — the app's, as `velora_api`, below;
   - the **session pooler** (`aws-…pooler.supabase.com:5432`, user `postgres.<ref>`) — the owner's,
     for migrations.

   Add `?ssl=require` to both.
5. **Before the first deploy**, open the **SQL editor** and create the app's roles. The login role
   gets a generated password (`openssl rand -hex 32`):

   ```sql
   -- The group the migrations grant privileges to. The first migration would create it; making it
   -- now lets the login role join it before that migration runs.
   create role velora_app nologin;
   create role velora_api login connection limit 20 password '<generated>' in role velora_app;
   -- PostGIS and citext live in `extensions` on Supabase; without this the app can't see them.
   alter role velora_api set search_path = public, extensions;
   ```

   Without `velora_api`, the API can't connect, its `/readyz` never passes, and Fly refuses the
   deploy.
6. After the first deploy, check the app role — **every row must say `true`**:

   ```sql
   select check_name, ok from (values
     ('velora_api is not a superuser',
        not (select rolsuper from pg_roles where rolname = 'velora_api')),
     ('velora_api cannot create roles',
        not (select rolcreaterole from pg_roles where rolname = 'velora_api')),
     ('velora_api is capped at 20 connections',
        (select rolconnlimit from pg_roles where rolname = 'velora_api') = 20),
     ('the app cannot update the ledger',
        not has_table_privilege('velora_app', 'ledger_entries', 'UPDATE')),
     ('the app cannot delete payments',
        not has_table_privilege('velora_app', 'payments', 'DELETE')),
     -- Supabase keeps the extensions here, and a new role gets no USAGE; without it the app
     -- can't use citext, geography or PostGIS (67e81c6c203d grants it).
     ('the app can use the extensions schema',
        has_schema_privilege('velora_app', 'extensions', 'USAGE'))
   ) as checks(check_name, ok);
   ```
7. Check Supabase's API roles hold nothing of ours — this must return **no rows**:

   ```sql
   select grantee, table_name, privilege_type
   from information_schema.role_table_grants
   where table_schema = 'public' and grantee in ('anon', 'authenticated');
   ```

### 2. Upstash

New Redis database `velora-staging`, region Mumbai, TLS on. Copy its `rediss://…` URL.

### 3. Cloudflare R2

Buckets `velora-staging-public` and `velora-staging-private`, location hint **Asia-Pacific
(APAC)**, Standard storage class: nearest to users and the Singapore worker. A hint is best effort,
not a guarantee, so the Privacy page says only "stored by Cloudflare, outside India" (D-048).

**Set up by the founder on 4 October 2026 (T-4.1).** Each line is something a later change must not
undo without a decision:

- **The public bucket is served only at `cdn.staging.veloraapp.co.in`**, its custom domain
  (`PUBLIC_CDN_URL`). The private bucket has no domain and no public access; `r2.dev` access is off
  for both (the founder's report: the `r2.dev` address isn't known here, so nothing can check it).
- **That domain's minimum TLS is 1.2, not Cloudflare's default 1.0.** 1.0 is broken, and these
  serve users' photos; 1.3 would have excluded older Android phones that only speak 1.2. It is a
  setting someone could lower, or raise, without realising what it costs, so it is written here
  and on T-4.1. Read by Claude from outside on 4 October 2026, by the server's own answer: TLS 1.0
  and 1.1 refused with a protocol-version alert, 1.2 and 1.3 accepted.
- **One Account API token, Object Read & Write, scoped to these two buckets only**, never "all
  buckets", so it can't touch production's. Proved by its effect (T-4.1's probe, below): a HEAD of
  an absent key is a 404 in these two buckets and a 403 in `velora-prod-public` and
  `velora-prod-private`. Its two values are Fly secrets (§4), set with `flyctl secrets import`, and
  in the Keychain as `r2-access-key-id` and `r2-secret-access-key`: the same values, compared by
  Claude on 4 October 2026 by SHA-256 prefix on the machine and from the Keychain (T-4.1).
- **`R2_ENDPOINT_URL` is never set here.** Settings refuse it anywhere but local, so storage goes to
  R2's own endpoint for the account in `R2_ACCOUNT_ID` (`infra/fly.api.toml`; not a secret).
- **The private bucket's CORS rule, or no browser can upload a photo** (T-4.6). The web PUTs each
  photo straight to `velora-staging-private` on R2's endpoint, from another origin with a
  `Content-Type`, so the browser asks first, and R2 refuses without a rule. Our token is Object
  Read & Write and can't set one, so the founder sets it, in R2 → `velora-staging-private` →
  Settings → CORS policy, exactly this and nothing wider:
  `[{"AllowedOrigins": ["https://staging.veloraapp.co.in"], "AllowedMethods": ["PUT"], "AllowedHeaders": ["Content-Type"], "MaxAgeSeconds": 3600}]`.
  The public bucket needs none: an `<img>` needs no CORS. **Checked by a preflight**, R2's own
  answer: from `https://staging.veloraapp.co.in` for `PUT` with `content-type`, a 200 naming that
  origin, `PUT` and `content-type`; from any other origin, R2's 403.
  **Set by the founder on 4 October 2026, with `GET` as well as `PUT`,** added for the signed links
  pending photos are shown by. Checked by Claude from outside at 15:48 UTC: from the staging
  origin, `PUT` with `content-type` answered 204 naming that origin, `content-type`, `PUT, GET` and
  3600; another site, production's origin, plain `http://` staging and the local web each got R2's
  `403 … CORS not configured for this bucket`, and so did `DELETE`, `POST` and an extra header.
  (At 14:49 UTC, before it was set, the staging origin got that 403 too.) **`GET` is wider than
  the photos need:** an `<img>` sends no preflight and needs no rule, which the local S3 shows,
  where the rule allows `PUT` only and a pending photo still shows by its signed link (T-4.6).
  **Proved by a real browser's upload** the same day (T-4.6): a PUT signed inside the API machine
  for a key under `probe/`, sent by Chromium from the staging origin, answered 200 with that origin
  allowed, its bytes read back and then deleted. **`GET` removed by the founder that night,** so the
  rule is now exactly T-4.6's: checked by Claude at 19:12 UTC, the staging origin's `PUT` preflight
  with `content-type` answered 204 naming that origin, `content-type`, `PUT` and 3600; a `GET`
  preflight, `DELETE`, an extra header, production's origin and another site each got R2's 403.

**The proof is the probe, run inside the machine with its own keys** (T-4.1), after any change to
the token, the buckets or the domain:

```
flyctl ssh console -a velora-api-staging -C \
  "python -m app.tools.storage_probe --refused-bucket velora-prod-public --refused-bucket velora-prod-private"
```

It writes under `probe/` in both buckets and deletes everything it wrote: a presigned PUT stored,
the same PUT with another type refused, the bytes read back three ways, a copy from private to public
served at the CDN, the private key not served there, the scope refusals above (each beside a 404
control), every object gone at the end. It prints step names only, never a URL, and exits 1 if
any step failed. It runs only where `ENV` is local or staging: production's copy refuses.

### 4. Fly

1. Create the app `velora-api-staging` (organisation on the paid plan). Its region, `sin`, comes from
   `infra/fly.api.toml`: Fly retired `bom` (D-048).
2. **Secrets** (Dashboard → the app → Secrets). The non-secret settings are in
   `infra/fly.api.toml`.

   | Secret | Value |
   |---|---|
   | `DATABASE_URL` | the **direct** connection, as `velora_api` |
   | `REDIS_URL` | Upstash's `rediss://…` |
   | `JWT_SECRET` | `openssl rand -hex 64` (64 bytes, 02-ARCHITECTURE §11) |
   | `PHONE_PEPPER` | `openssl rand -hex 32` |
   | `PHONE_ENC_KEY` | `openssl rand -hex 32` |
   | `CODE_PEPPER` | `openssl rand -hex 32` (T-3.1: PINs, and OTP codes from T-3.2) |
   | `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | the staging pair's R2 token (§3), from the Keychain. Without them the API refuses to start (T-4.1) |

   The API checks the four keys' shape before it starts and refuses the repo's public test keys
   (D-060), so a wrong one stops the deploy with the setting's name. On 3 October 2026 Claude read
   the first three on the machine, lengths only, never the values: `JWT_SECRET` 128 lowercase hex
   characters, `PHONE_PEPPER` and `PHONE_ENC_KEY` 64 each. `CODE_PEPPER` was generated into the
   Keychain and staged the same day (T-3.1). A key's shape says nothing about whether the Keychain
   copy is the same value as Fly's, so compare them by SHA-256 computed in each place, first 8 hex
   characters (the value never leaves either). A copy that was never the same value fails only on
   the day it's restored: every stored PIN, or every phone number, at once. Compared by Claude on
   3 October 2026, after deploy run 37079492855: all four match.

   The owner's credentials are **not** a Fly secret.
3. Create a **deploy token** for this app only (Tokens → Create deploy token).
4. **The worker's app, `velora-worker-staging`** (T-4.4, D-095), in the same organisation and
   region. Its settings are in `infra/fly.worker.toml`; its secrets are the API's, the same
   values, plus Sightengine's:

   | Secret | Value |
   |---|---|
   | `DATABASE_URL`, `REDIS_URL` | the API's own: the Keychain's `database-url` and `redis-url` (first piped from the API's machine, never printed) |
   | `JWT_SECRET`, `PHONE_PEPPER`, `PHONE_ENC_KEY`, `CODE_PEPPER` | the Keychain's, the API's values (D-060, D-061): with others, it can't read what the API wrote |
   | `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | the Keychain's, the API's token (§3) |
   | `SIGHTENGINE_API_USER`, `SIGHTENGINE_API_SECRET` | the Keychain's `sightengine-api-user`, `sightengine-api-secret` |

   Each is compared with its source by SHA-256, first 8 hex characters, computed in each place
   (as T-4.1 did): a copy that was never the same value fails only when it's used. Its deploy
   token is its own, scoped to this app, in GitHub's `staging` environment as
   `FLY_WORKER_API_TOKEN`; the API's token can't deploy it.

   **Set up by Claude on 4 October 2026 (T-4.4),** first deployed by deploy run 37218077335;
   the secrets compared that day by the prefixes recorded on T-4.4.

   **Sightengine is checked where it runs:**
   `flyctl ssh console -a velora-worker-staging -C "python -m app.tools.sightengine_shape"` sends
   Sightengine's two documentation examples, re-encoded as the worker sends a photo, and compares
   each answer's shape with the fake the tests use (D-094). It prints field names and types, never
   a value or a key; exit 0 when they match. 6 operations a run, on the free plan's allowance.

### 5. Vercel

1. New project `velora-staging`, **not connected to Git**, framework Next.js, root directory left
   empty (the workflow deploys from `web/`), Node 24.
2. **Environment Variables → Production:** `NEXT_PUBLIC_API_URL` = `https://api.staging.veloraapp.co.in`
   (exactly, with no trailing slash: the smoke check looks for that string in the web's scripts),
   and `APP_ENV` = `staging`. `next build` refuses an `APP_ENV` it doesn't know (T-2.6), so the
   staging deploy fails until it's set. From the CLI, in `web/`:
   `printf staging | pnpm dlx vercel env add APP_ENV production --no-sensitive`. Production sets
   `production` (`infra/PRODUCTION.md`). **Both must be Config, not Secret.** The CLI stores a value
   as a Secret by default, and `vercel pull` can't read a Secret back: it writes the literal
   `[SENSITIVE]`, so the build sees `APP_ENV=[SENSITIVE]` and refuses it. That happened on the
   first T-2.2 deploy (run 36903641112), when D-053's legal-facts gate caught it; with every fact
   known that gate no longer can, which is why the build checks `APP_ENV` itself.
3. **The web's address is `staging.veloraapp.co.in`** (Settings → Domains, for Production; its DNS
   is in §6). Vercel also gives every project a `<name>.vercel.app` address, adding a suffix when
   the name is taken: `velora-staging.vercel.app` belongs to another company's project, so ours is
   `velora-staging-black.vercel.app`. That address **redirects** to `staging.veloraapp.co.in` (P-33):
   left serving, it would be a live URL that looks like our product while CORS quietly refuses its
   API calls. The custom domain goes in `CORS_ORIGINS` (`infra/fly.api.toml`) and in
   `STAGING_WEB_URL` below. The smoke check fails if the URL serves anything other than this build
   calling this API, and its CORS line fails until the two settings agree.
4. Create an **access token** (Account → Tokens). Copy the org and project IDs from the project's
   settings.

### 6. DNS, on Cloudflare

The zone `veloraapp.co.in` is on Cloudflare's free plan: the nameservers moved from Hostinger on
2 October 2026 (P-0.3). Staging puts its web and API on one site, so the refresh cookie can flow
between them (P-33):

| Type | Name | Target | Read from |
|---|---|---|---|
| CNAME | `api.staging` | `rkq9qd8.velora-api-staging.fly.dev` | `fly certs setup api.staging.veloraapp.co.in -a velora-api-staging` |
| CNAME | `staging` | `09ad61298fe347ed.vercel-dns-017.com` | Vercel's API, below |

- **Read each target from the platform; don't assume it.** Both are specific to the app or the
  project: Fly's isn't plain `velora-api-staging.fly.dev`, and Vercel's CLI (`vercel domains
  inspect`) offers only a fallback A record. Vercel's own ranking comes from its API, in `web/`:
  `pnpm dlx vercel api "/v6/domains/staging.veloraapp.co.in/config?projectIdOrName=velora-staging"`,
  `recommendedCNAME` rank 1.
- **CNAMEs, not A records:** a CNAME follows the platform when its IPs change; an A record would go
  stale and take staging down.
- **DNS only (grey cloud), never proxied:** Fly and Vercel each issue their own Let's Encrypt
  certificate, which a proxy gets in the way of, and it keeps Cloudflare out of the path of users'
  requests.
- **`api.staging.` sits under `staging.`** so staging's CSRF cookie, scoped to
  `staging.veloraapp.co.in`, covers both and never reaches production (D-055).
- **Order:** add the host on the platform first (`fly certs add api.staging.veloraapp.co.in -a
  velora-api-staging`; the Vercel domain in step 5.3), then the record. Fly's certificate is ready
  when `fly certs check api.staging.veloraapp.co.in -a velora-api-staging` says `Issued`.

### 7. GitHub

Settings → Environments → **new environment `staging`**.

| Kind | Name | Value |
|---|---|---|
| Secret | `STAGING_MIGRATION_DATABASE_URL` | the **session pooler** connection, as the owner |
| Secret | `FLY_API_TOKEN` | Fly's deploy token for `velora-api-staging` |
| Secret | `FLY_WORKER_API_TOKEN` | Fly's deploy token for `velora-worker-staging` only (T-4.4) |
| Secret | `VERCEL_TOKEN` | a Vercel access token **scoped to the `velora-staging` project, with no expiry** |
| Secret | `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from the Vercel project |
| Variable | `STAGING_API_URL` | `https://api.staging.veloraapp.co.in` |
| Variable | `STAGING_WEB_URL` | `https://staging.veloraapp.co.in` |

**`VERCEL_TOKEN`'s tradeoff, chosen on purpose:** it reaches only the `velora-staging` project, so a
leak can't touch anything else, but it never expires, so nothing retires it on its own. Revoke it at
any suspicion and create a fresh one, as was done on 2026-10-01 after two earlier tokens were
pasted into a terminal by mistake (both revoked). Production's token expires after a year instead,
and its release gate warns 30 days ahead (`infra/PRODUCTION.md`, D-075). The Vercel CLI's own login
token won't do: it's a short-lived OAuth token, expiring within the hour and refreshed only on your
machine, so CI would break as soon as it lapsed.

## After a deploy

The **smoke** job is the check. To run it by hand:

```
scripts/staging-smoke https://api.staging.veloraapp.co.in https://staging.veloraapp.co.in
```

A configuration error (a missing secret, a fake provider) stops the container with the message
instead of crash-looping: the image checks settings once before uvicorn starts its workers. Read
it in Fly's logs. The worker's is stopped earlier, by its release command, before any machine is
replaced: read it in the deploy job's log.

**The worker is working** when a photo uploaded on staging reaches `approved` within a poll and a
Sightengine call (T-4.4): its machine's log says `worker.started` once, then `moderation.decided`
for each photo, by the photo's id, never a key.

## Before any T-3 auth work: close the CORS hole

Until 1 October 2026, `CORS_ORIGINS` named `https://velora-staging.vercel.app`, which is another
company's site, not ours (Vercel section, step 3). The API allows credentials
(`allow_credentials=True`), so it would accept credentialed requests from their pages and let
those pages read the answers. Staging has no sign-in and no users yet, so there was nothing to
read. **This must be closed, and checked closed, before any T-3 auth work lands.** Closed means
their origin gets no `access-control-allow-origin` back:

```
curl -s -o /dev/null -D - -X OPTIONS https://velora-api-staging.fly.dev/healthz \
  -H 'Origin: https://velora-staging.vercel.app' -H 'Access-Control-Request-Method: GET' \
  | grep -i '^access-control-allow-origin' || echo closed
```

**Closed and checked on 1 October 2026**, after deploy run 36845884410: that command printed
`closed`, and the smoke check, run by hand against their URL, failed on both the web and CORS.

## What staging can't do yet

- **A session surviving a reload isn't proved yet.** Since P-33 the web and API share a site
  (`veloraapp.co.in`), so the `SameSite=Lax` refresh cookie (D-024) can flow between them, but
  nothing sets a cookie until T-3.3. T-3.14's Done-when is the proof: sign in on staging, reload,
  and the session is still there.
- **Every provider is a real one that isn't built yet** (D-045): each raises if called, and
  nothing calls one before its task. Built and called on staging: storage (R2, T-4.1) and
  moderation (Sightengine, T-4.4).
