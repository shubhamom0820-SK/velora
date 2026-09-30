# Staging

How staging is built, deployed and checked (T-1.22, D-046). Production (T-2.6) follows the same
shape; copy these steps and change the names.

## What runs where

| Piece | Where | Name |
|---|---|---|
| API | Fly.io, `bom` | app `velora-api-staging` → `https://velora-api-staging.fly.dev` |
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

Supabase's smallest compute allows 60 direct connections, and its own services use some. Change
`DB_POOL_SIZE` / `DB_MAX_OVERFLOW` in `infra/fly.api.toml`, never the image, and redo this sum
whenever workers, machines or pools change — two machines doubles it. Production starts from this
table, not from a guess.

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
   create role velora_api login password '<generated>' in role velora_app;
   -- PostGIS and citext live in `extensions` on Supabase; without this the app can't see them.
   alter role velora_api set search_path = public, extensions;
   ```

   Without `velora_api`, the API can't connect, its `/readyz` never passes, and Fly refuses the
   deploy.
6. After the first deploy, check the app role can't reach past its privileges — every row
   should say `false`:

   ```sql
   select 'velora_api is superuser', rolsuper from pg_roles where rolname = 'velora_api'
   union all
   select 'velora_api can create roles', rolcreaterole from pg_roles where rolname = 'velora_api'
   union all
   select 'app can update the ledger', has_table_privilege('velora_app', 'ledger_entries', 'UPDATE')
   union all
   select 'app can delete payments', has_table_privilege('velora_app', 'payments', 'DELETE');
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

1. Create the app `velora-api-staging` (organisation on the paid plan, region `bom`).
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
| Secret | `VERCEL_TOKEN` | Vercel's access token |
| Secret | `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from the Vercel project |
| Variable | `STAGING_API_URL` | `https://velora-api-staging.fly.dev` |
| Variable | `STAGING_WEB_URL` | `https://velora-staging.vercel.app` |

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
