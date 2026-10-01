# Staging

> **Region (D-048):** the API runs on Fly in **Singapore**, because Fly retired Mumbai. Postgres and
> Redis stay in **Mumbai**, so Indian users' data stays in India — and every query crosses Singapore
> to Mumbai and back, the latency D-048 accepts for now.

How staging is built, deployed and checked (T-1.22, D-046). Production (T-2.6) follows the same
shape; copy these steps and change the names.

## What runs where

| Piece | Where | Name |
|---|---|---|
| API | Fly.io, `sin` (Singapore; D-048) | app `velora-api-staging` → `https://velora-api-staging.fly.dev` |
| Web | Vercel, its own project | `velora-staging` → `https://velora-staging.vercel.app` |
| Postgres | Supabase, Mumbai (`ap-south-1`) | project `velora-staging` |
| Redis | Upstash, Mumbai | database `velora-staging` |
| Objects | Cloudflare R2 | buckets `velora-staging-public`, `velora-staging-private` |

## How a deploy happens

`.github/workflows/deploy.yml`, after CI passes on `main` (or by hand, from the Actions tab, for
any commit whose CI passed):

1. **gate** runs `scripts/ci-gate` on the exact commit. Anything but a passed CI run stops here.
2. **migrate** runs `alembic upgrade head` from CI **as the database owner**
   (`scripts/migrate-with-url`). The owner's credentials live only in GitHub, never on Fly: the app
   runs as `velora_api`, which can't disable the ledger's triggers, and a code-execution bug in the
   app mustn't be one step from doing so (P-18).
3. **api** runs `flyctl deploy`. Fly builds `api/Dockerfile` with `api/` as the context, and only
   routes to the new machine once `/readyz` passes.
4. **web** builds and deploys with the Vercel CLI. The project has no Git connection
   (`web/vercel.json` also turns Git deploys off), so the web can't go live around the gate.
5. **smoke** runs `scripts/staging-smoke` against staging from the outside, bodies included:
   `/readyz`, the hidden schema and docs, the web, the hidden `/admin` and `/dev/*`, and CORS.

**The first deploy happens after T-1.22 merges.** GitHub only triggers a workflow that exists on
the default branch — `workflow_run`, `workflow_dispatch`, and `gh run list --workflow <file>` all
resolve against `main` — so `deploy.yml` can't run from a branch until it's merged (06-TESTING).

## Database connections: the budget

The pool is per process, and the image runs **2 uvicorn workers**, each with its own pool:

| Who | Connects as | How | At most |
|---|---|---|---|
| API | `velora_api` | direct connection, IPv6 (Fly has it) | 2 workers × (`DB_POOL_SIZE` 5 + `DB_MAX_OVERFLOW` 2) = **14** |
| Migrations | the owner (`postgres`) | session pooler, IPv4 (GitHub's runners have no IPv6) | 1, during a deploy |
| Worker | `velora_api` | direct | arrives with T-4.4; add its pool here |

That's **one machine**: `deploy.yml` passes `--ha=false`, because Fly's default of two would double
the sum. Supabase's smallest compute allows 60 direct connections, and its own services use some.
Change
`DB_POOL_SIZE` / `DB_MAX_OVERFLOW` in `infra/fly.api.toml`, never the image, and redo this sum
whenever workers, machines or pools change — two machines doubles it. Production starts from this
table, not from a guess.

**`velora_api` has a connection limit of 20**, set on the role itself, so the database enforces the
budget even if a pool setting drifts. 20 sits above the 14 the pools allow, so normal load never
reaches it, and well under the instance's 60, so a runaway pool can't starve the migrations or
Supabase's own services. When the worker (T-4.4) or a second machine raises the sum, raise the limit
with it (`alter role velora_api connection limit N`) and record the new number and reason here.

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

Buckets `velora-staging-public` and `velora-staging-private`. Their API token and the public
bucket's CDN domain are set with T-4.1, when storage is built.

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

   The owner's credentials are **not** a Fly secret.
3. Create a **deploy token** for this app only (Tokens → Create deploy token).

### 5. Vercel

1. New project `velora-staging`, **not connected to Git**, framework Next.js, root directory left
   empty (the workflow deploys from `web/`), Node 24.
2. **Environment Variables → Production:** `NEXT_PUBLIC_API_URL` = `https://velora-api-staging.fly.dev`.
3. If Vercel gives the project a URL other than `https://velora-staging.vercel.app`, change
   `CORS_ORIGINS` in `infra/fly.api.toml` and `STAGING_WEB_URL` below to match. The smoke check's
   CORS line fails until they agree.
4. Create an **access token** (Account → Tokens). Copy the org and project IDs from the project's
   settings.

### 6. GitHub

Settings → Environments → **new environment `staging`**.

| Kind | Name | Value |
|---|---|---|
| Secret | `STAGING_MIGRATION_DATABASE_URL` | the **session pooler** connection, as the owner |
| Secret | `FLY_API_TOKEN` | Fly's deploy token |
| Secret | `VERCEL_TOKEN` | a Vercel access token **scoped to the `velora-staging` project, with no expiry** |
| Secret | `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from the Vercel project |
| Variable | `STAGING_API_URL` | `https://velora-api-staging.fly.dev` |
| Variable | `STAGING_WEB_URL` | `https://velora-staging.vercel.app` |

**`VERCEL_TOKEN`'s tradeoff, chosen on purpose:** it reaches only the `velora-staging` project, so a
leak can't touch anything else, but it never expires, so nothing retires it on its own. Revoke it at
any suspicion and create a fresh one, as was done on 2026-10-01 after two earlier tokens were
pasted into a terminal by mistake (both revoked). Production (T-2.6) gets its own token; decide its
expiry then. The Vercel CLI's own login token won't do: it's a short-lived OAuth token, expiring
within the hour and refreshed only on your machine, so CI would break as soon as it lapsed.

## After a deploy

The **smoke** job is the check. To run it by hand:

```
scripts/staging-smoke https://velora-api-staging.fly.dev https://velora-staging.vercel.app
```

A configuration error (a missing secret, a fake provider) stops the container with the message
instead of crash-looping: the image checks settings once before uvicorn starts its workers. Read
it in Fly's logs.

## What staging can't do yet

- **Sign-in can't keep a session on staging** until the web and API share a site: the refresh
  cookie is `SameSite=Lax` (D-024), and `*.vercel.app` and `*.fly.dev` are different sites. P-33
  fixes it with `velora.app` subdomains, which needs the domain (P-0.3), which waits on the
  trademark search (P-0.1, D-015). T-3.4 needs P-33.
- **Every provider is a real one that isn't built yet** (D-045): each raises if called, and
  nothing calls one before its task.
