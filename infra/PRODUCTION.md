# Production

> **Not released yet.** The first release, `v0.1.0`, is its own task, REL-1 in `docs/05-PLAN.md`,
> and it waits on three founder items (P-0.14, P-0.15, P-0.16, below). From that moment the site
> is public and crawled, takes real sign-ups, and is plainly commercial. Production itself was
> built and proved in T-2.6; everything else can be set up ahead of the release.
>
> **Mumbai (P-921, D-1020):** the API and the worker run on a Compute Engine VM in Mumbai,
> `velora-api-prod`, beside Postgres and Redis, exactly as staging's do since P-49. A release
> deploys the image staging ran, by its digest. Fly's `velora-api` is not deployed any more and
> goes with P-920.
>
> **Payments: Razorpay refused the account** (21 October 2026: "Dating or matrimony platform.
> Razorpay doesn't currently support this category."). Other gateways are being applied to, which
> may take weeks. Production deploys only with payments explicitly off until one is live: P-971
> builds that. Until it lands, the VM's deploy stops at the missing Razorpay keys (§4).

How production is set up, released and checked (T-2.6, D-074, D-075). It copies staging's shape
(`infra/STAGING.md`): this page names production's pieces and says what differs. Where it says "as
staging", follow `infra/STAGING.md` with these names.

## What runs where

| Piece | Where | Name |
|---|---|---|
| API and worker | Compute Engine, Mumbai (`asia-south1-a`; D-1020), project `velora-ic-prod` | VM `velora-api-prod`, `e2-medium`, static IP `34.180.56.204`, behind Caddy → `https://api.veloraapp.co.in` (§4) |
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
| The VM `velora-api-prod` | about $35.25 at list prices (D-1020): the `e2-medium` $29.40, its disk and static IP; Secret Manager and Artifact Registry under $1 each | the same: it runs from the day it exists |
| Upstash `velora-prod` | free tier | the API's healthcheck (`infra/gce/compose.yml`, every 15 s) pings Redis, about 173,000 commands a month: check that against the free allowance when creating it |
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
   - **image** copies the image staging deployed for that commit from staging's registry to
     production's, by `skopeo copy --preserve-digests`, and **fails unless production's registry
     reports the same digest**: production runs the bytes staging ran. Staging's registry keeps
     only its 10 newest images, so an older commit's may be gone: the job then says so, and the
     fix is to deploy that commit to staging again (Actions → Deploy staging, its full SHA) and
     push the tag again. Before **migrate**, so a failed copy changes nothing.
   - **migrate**: as staging, with production's owner credentials.
   - **vm** runs `infra/gce/deploy production` on the VM over IAP, as staging's `vm` job (§4).
   - **web**, after **vm**: as staging, with production's project.
   - **smoke** runs `scripts/staging-smoke` against production, bodies included, with
     `EXPECT_API_VIA=Caddy`, so `api.veloraapp.co.in` must be the VM's Caddy. Its canonical
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
- **The worker, after the release's migration, never before** (§4): its minute loops read tables
  an unmigrated database doesn't have.
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

Staging's table (`infra/STAGING.md`), unchanged: the API's 2 uvicorn workers × (`DB_POOL_SIZE` 5
+ `DB_MAX_OVERFLOW` 2) = **14**, set in `infra/gce/production.env`, and the worker's 1 process ×
(2 + 1) = **3**, set in `infra/gce/compose.yml`: **17**, under `velora_api`'s cap of **20** on
the role. One VM, one API container, one worker. Redo the sum whenever workers, containers or
pools change.

## Secrets

The rules are staging's ("How secrets get set"): never printed, never an argument, never from the
clipboard. **They live in Secret Manager in `velora-ic-prod`, stored in `asia-south1` only**
(D-1022), one secret per setting, the names in `infra/gce/secrets.api` and `secrets.worker`; the
VM reads them at each deploy into root-only files. **`scripts/gcp-secrets production`** (the
founder, on his Mac, from the repo root) puts them there with the Keychain's copy, every copy
compared by SHA-256 prefix, and refuses a generated key that equals staging's. Generate
everything fresh; **never copy a value from staging**. Startup refuses the repo's public test
keys, but it can't know a copy of staging's. **Two deliberate exceptions, accounts not keys:**
R2's account (its token is production's own, §3) and Sightengine's, shared with staging for now
(the founder, 21 October 2026; production's own account before real traffic, P-970).

- **The Keychain service is `velora-production`**, with the same accounts as staging's:
  `db-owner`, `velora-api-db`, `jwt-secret`, `phone-pepper`, `phone-enc-key`, `code-pepper`.
- **The four keys and the VAPID pair were generated fresh on 18 October 2026** by
  `scripts/gcp-secrets production` (P-49), into the Keychain and Secret Manager, each compared by
  SHA-256 prefix and checked to differ from staging's. Production has never served a user and
  Fly's `velora-api` held nothing, so nothing was encrypted under any earlier key (the founder,
  21 October 2026).
- **Web Push's pair (T-9.4, D-856):** `VAPID_PRIVATE_KEY` and `VAPID_PUBLIC_KEY`, made fresh by
  staging's commands (STAGING.md §4) with `velora-production` and the production app, never
  staging's pair. Push is off until D-857 is decided (`PUSH_PROVIDER = "off"`, no keys needed).
  Before switching to `"webpush"`, set the pair, or production refuses to start. Keychain
  accounts `vapid-private-key`, `vapid-public-key`.
- **Sentry (T-9.12, D-1001):** `SENTRY_DSN`, the `velora-api` project's DSN, in Secret Manager
  in `velora-ic-prod` (**empty as of 18 October 2026: P-921's checklist**), and
  `NEXT_PUBLIC_SENTRY_DSN`, the `velora-web` project's, on the `velora-production` Vercel project
  as Config. The same Sentry projects as staging's; the environment tells them apart. Without them
  the VM's deploy stops, production refuses to start and the web to build
  (infra/OBSERVABILITY.md §1).
- **The second copy lives in Apple Passwords, synced through iCloud,** never only on this Mac (the
  founder, 3 October 2026). A Keychain on one laptop is one laptop away from every production
  key being unrecoverable. Only the founder reads its contents; nobody else ever asks for them.

## The keys: what exists, what each protects, what losing one costs

Read this before touching any key during an incident. It lists consequences, never values. The
values live in three places: Secret Manager in `velora-ic-prod` (D-1022), the
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
| `DATABASE_URL` (`velora_api`'s password) | Rows, as the app | A new password on the role in Supabase, then a new version in Secret Manager (`scripts/gcp-secrets production`) and the next deploy |
| `PRODUCTION_MIGRATION_DATABASE_URL` (the owner) | The whole database, including switching off the ledger's guards (D-046) | A new database password in Supabase, then GitHub's secret |
| `REDIS_URL` | Rate limits and sign-in codes | Upstash's credential reset, then a new version in Secret Manager and the next deploy |
| `VERCEL_TOKEN` | Deploying anything to the production site | A new one-year token, then GitHub's secret |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Production's two buckets, read and write | A new token in Cloudflare scoped to them (§3), into Secret Manager, then revoke the old one |
| `SUPABASE_ACCESS_TOKEN` | Reading velora-prod and its organisation, nothing else (scoped) | A new scoped token, then GitHub's secret |

**No deploy key exists** (D-1022): GitHub's `production` jobs sign in by Workload Identity
Federation, as `velora-deploy-prod`, which is root on the VM and may read staging's registry, and
nothing else. To stop all deploys at once, remove that account's `workloadIdentityUser` binding.

## First-time setup

### 1. Supabase

**If `velora-prod` doesn't exist yet,** create a new **organisation of its own**, so that
upgrading it to Pro (P-0.16) pays for this project alone, and in it the project `velora-prod`,
region Mumbai (`ap-south-1`), on Free until the release. Keep the database password in the
Keychain (service `velora-production`, account `db-owner`) and Apple Passwords.

**If it exists, use it.** Either way, **before anything else, and before any migration, check
it holds no data** (the founder, 21 October 2026): in its SQL editor, this lists every table in
`public` that has rows, and must return **no rows**. Any row it returns is data production was
never meant to hold: stop there and tell Claude before going further.

```sql
select table_name, row_count from (
  select table_name, (xpath('/row/n/text()', query_to_xml(
           format('select count(*) as n from public.%I', table_name), false, true, '')))[1]::text::bigint as row_count
  from information_schema.tables
  where table_schema = 'public' and table_type = 'BASE TABLE'
) as counted
where row_count > 0;
```

Then staging's steps 2 to 5 (`infra/STAGING.md` §1), with production's names: the extensions
(`postgis`, `pg_trgm`, `citext`); the Data API **off**; the two connection strings, as
`postgresql+asyncpg://…?ssl=require`, the **direct** one (`db.<ref>.supabase.co:5432`, the
app's, as `velora_api`: the VM reaches it over IPv6) and the **session pooler** (the owner's,
for migrations, `PRODUCTION_MIGRATION_DATABASE_URL`, §7); and the two roles, by staging's SQL
exactly, `velora_api` with a fresh password and `connection limit 20`:

```sql
create role velora_app nologin;
create role velora_api login connection limit 20 password '<generated>' in role velora_app;
alter role velora_api set search_path = public, extensions;
```

Generate the password into the Keychain first, never on screen (service `velora-production`,
account `velora-api-db`; `openssl rand -hex 32`, stored by `security -i` reading the command on
stdin, as staging's), then paste it into the SQL editor only. The direct URL then goes into Secret
Manager at `scripts/gcp-secrets production`'s hidden prompt (§4). Staging's steps 6 and 7, the
role's checks and the API roles' grants, run after the release's first migration.

Then, for the release gate (D-075), a **scoped access token** (Account → Access Tokens), never a
classic one, which carries the account's full power over every project. It needs read access to
exactly two things: the project `velora-prod` (the gate reads its organisation from it) and that
organisation (the gate reads its plan). Supabase's API names these `project_admin_read` and
`organization_admin_read`; choose the read-only permissions that match, and nothing else. If it's
short of either, the gate says so and refuses. The project's ref, from its URL, goes in GitHub as
a variable (§7).

### 2. Upstash

**If `velora-prod` doesn't exist yet,** create the Redis database `velora-prod`, region Mumbai,
TLS on. **If it exists, use it**, after checking it is in Mumbai with TLS on. Either way, its
`rediss://…` URL goes into Secret Manager at `scripts/gcp-secrets production`'s hidden prompt
(§4), never on screen.

### 3. Cloudflare R2

Created by the founder on 4 October 2026 (T-4.1), as staging's (`infra/STAGING.md` §3), and each
line is as binding: `velora-prod-public` and `velora-prod-private`, location hint Asia-Pacific
(APAC), Standard storage class.

- **The public bucket is served only at `cdn.veloraapp.co.in`**, its custom domain
  (`PUBLIC_CDN_URL` in `infra/gce/production.env`); the private bucket has no domain.
- **Minimum TLS 1.2 on that domain, not the default 1.0:** 1.0 is broken and these serve users'
  photos; 1.3 would have excluded older Android phones that only speak 1.2. Read from outside by
  Claude on 4 October 2026: 1.0 and 1.1 refused by the server, 1.2 and 1.3 accepted.
- **One Account API token, Object Read & Write, scoped to these two buckets only**: it can't touch
  staging's (the founder's report; not yet proved by its effect, since the token isn't anywhere
  Claude can use it: see below). Staging's token is proved refused here (`infra/STAGING.md` §3).
- **Its two values are in Secret Manager** (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, from the
  login Keychain, service `velora-prod`, accounts `r2-access-key-id` and `r2-secret-access-key`,
  by `scripts/gcp-secrets production` on 18 October 2026). That token's TTL is Forever, so **it is
  rotated before the first deploy to the VM** (the founder, 21 October 2026): in Cloudflare → R2 →
  Manage API tokens, a new Account API token, **Object Read & Write, scoped to
  `velora-prod-public` and `velora-prod-private` only**; its two values into the Keychain's two
  accounts above, replacing the old ones (`security -i`, never on screen); `scripts/gcp-secrets
  production` then stores them as new versions and compares every copy; and only then **revoke
  the old token** in Cloudflare. Proved by its effect, as staging's: a write to staging's bucket
  with the new token is refused.
- **The private bucket's CORS rule, before REL-1** (T-4.6, on REL-1's Needs line): staging's
  (`infra/STAGING.md` §3) with production's origin, set by the founder in R2 →
  `velora-prod-private` → Settings → CORS policy, exactly:
  `[{"AllowedOrigins": ["https://veloraapp.co.in"], "AllowedMethods": ["PUT"], "AllowedHeaders": ["Content-Type"], "MaxAgeSeconds": 3600}]`.
  Without it no browser can upload a photo, so nobody gets past the photos step. Checked as
  staging's is, by a preflight from `https://veloraapp.co.in`.

### 4. The Mumbai VM (P-49, P-921, D-1020 to D-1023)

| Piece | Where | Name |
|---|---|---|
| Project | Google Cloud, billing account `01C4E8-84A5D8-4255F2`, no organisation (D-1023) | `velora-ic-prod` |
| VM | Compute Engine `asia-south1-a`, `e2-medium`, Debian 12 | `velora-api-prod`, static IP `34.180.56.204` |
| On it | Docker Compose (`infra/gce/compose.yml`): `api`, `worker` (only where `/etc/velora/worker-on` exists), `caddy` | Caddy serves the hosts in `infra/gce/production.edge.env` |
| Images | Artifact Registry, `asia-south1` | `asia-south1-docker.pkg.dev/velora-ic-prod/velora/api`, copied from staging's by digest |
| Secrets | Secret Manager, stored in `asia-south1` only | one per setting, the names in `infra/gce/secrets.api` and `secrets.worker` |

Built by the founder's own commands on 16 to 18 October 2026 (P-49, `out/`): the VPC (TCP 80 and
443 in, 22 from IAP only), the static IP, the deploy and VM accounts, the registry, Secret
Manager's slots and WIF for GitHub's `production` environment. Everything else is staging's
("The Mumbai VM", `infra/STAGING.md`), with production's names: how it deploys, getting in, the
tools inside the API's container, and how the VM itself is set up.

**Secrets:** `scripts/gcp-secrets production`, on the founder's Mac, from the repo root. It keeps
what is set, asks at hidden prompts for the rest (Enter skips one not ready), and ends by comparing
every copy. **Before a deploy can pass, every required name has a value:** `DATABASE_URL` (§1),
`REDIS_URL` (§2), `SENTRY_DSN` (`infra/OBSERVABILITY.md` §1), R2's rotated pair (§3),
Sightengine's two (staging's account for now: from the Keychain service `velora-staging`, P-970),
and Razorpay's three until P-971 lets production deploy with payments off. The deploy names the
first one missing (`… has no value in Secret Manager`) and changes nothing. Then copy every
`velora-production` Keychain entry into Apple Passwords.

**The worker:** off until the first release's migration has run, so its minute loops never meet
an empty schema. Then, on the founder's word, over IAP:

```
gcloud compute ssh velora-api-prod --project=velora-ic-prod --zone=asia-south1-a --tunnel-through-iap \
  --command "sudo touch /etc/velora/worker-on && sudo docker compose -p velora --project-directory /opt/velora/current -f /opt/velora/current/compose.yml --profile worker up -d worker"
```

Every later deploy keeps it running; removing the file and the next deploy stops it.

**The rehearsal, before REL-1 (P-921):** the release gate refuses until both paid plans exist,
so the workflow's first run would be the release itself. The founder runs its `image` and `vm`
steps by hand from **Cloud Shell** (Google's network, his own account; never Docker Desktop,
P-924), with the commit `main`'s staging deploy last ran, the worker off:

```
SHA=<main's commit, the full 40 hex, deployed to staging>
src=asia-south1-docker.pkg.dev/velora-ic-staging/velora/api
dst=asia-south1-docker.pkg.dev/velora-ic-prod/velora/api
gcloud auth configure-docker asia-south1-docker.pkg.dev --quiet
sudo apt-get install -y skopeo
digest="$(gcloud artifacts docker images describe "$src:$SHA" --format='value(image_summary.digest)')"
skopeo copy --preserve-digests "docker://$src@$digest" "docker://$dst:$SHA"
[ "$(gcloud artifacts docker images describe "$dst:$SHA" --format='value(image_summary.digest)')" = "$digest" ] && echo "same digest" || echo "STOP: the digest changed"
git clone --filter=blob:none https://github.com/shubhamom0820-SK/velora.git && cd velora && git checkout -q "$SHA"
rel="/tmp/velora-release-$SHA"; mkdir -p "$rel" && git archive "$SHA" infra/gce | tar -x -C "$rel" --strip-components=2
gcloud compute scp --project=velora-ic-prod --zone=asia-south1-a --tunnel-through-iap --recurse --quiet "$rel" velora-api-prod:/tmp/
gcloud compute ssh velora-api-prod --project=velora-ic-prod --zone=asia-south1-a --tunnel-through-iap --command "sudo bash /tmp/velora-release-$SHA/deploy production '$dst@$digest' $SHA"
```

Then Claude checks from outside, read-only: Caddy's certificate for `api.veloraapp.co.in`,
`Via: 1.1 Caddy`, `/readyz` with Postgres and Redis ok (it checks the connections, not the
schema), `/v1/admin/metrics` refused with a 401 and no data, the schema and docs hidden, only 80
and 443 answering. The web's checks wait for release day, when the apex gets its DNS.

### 5. Vercel

1. The project `velora-production`, not connected to Git, framework Next.js, Node 24, in the team
   `knot11`.
2. **Environment Variables → Production:** `NEXT_PUBLIC_API_URL` = `https://api.veloraapp.co.in`
   and `APP_ENV` = `production`, **both Config, not Secret**; and `NEXT_PUBLIC_SENTRY_DSN`, the
   `velora-web` project's DSN, also Config (`infra/OBSERVABILITY.md` §1, its command). `next build` refuses an `APP_ENV`
   it doesn't know, including the `[SENSITIVE]` that a Secret pulls back as.
3. **Domains:** `veloraapp.co.in`; `www.veloraapp.co.in` redirecting to it (308); and the
   project's own `vercel.app` address redirecting to it. Left serving, that address would be an
   indexable second copy of the site.
4. An **access token** for the team, **expiring in one year** (decided 3 October 2026). When it
   lapses, releases stop closed and the site keeps serving; the gate warns 30 days ahead.

### 6. DNS, on Cloudflare

| Type | Name | Target | Read from | When |
|---|---|---|---|---|
| A | `api` | `34.180.56.204` (the VM's static IP), **DNS only**, no AAAA: the VM takes nothing in over IPv6 | `gcloud compute addresses list --project=velora-ic-prod` | before the rehearsal (§4): nothing calls it until the release |
| CNAME | `@` (the apex) | `f5c6be5b7918e5ec.vercel-dns-017.com` | Vercel's API, `recommendedCNAME` rank 1 | release day |
| CNAME | `www` | `f5c6be5b7918e5ec.vercel-dns-017.com` | the same, for `www.veloraapp.co.in` | release day |

The Vercel targets were read by Claude on 3 October 2026 with
`pnpm dlx vercel api "/v6/domains/<domain>/config?projectIdOrName=velora-production"`.

**Moving `api` from Fly's CNAME (P-921), in Cloudflare → `veloraapp.co.in` → DNS:** edit the
existing `api` CNAME (to `nwjo8lz.velora-api.fly.dev`) and set its TTL to 1 min; at least 10
minutes later, delete it and add **A · `api` · `34.180.56.204` · DNS only · TTL 1 min**. Read it
back: `dig +short api.veloraapp.co.in @1.1.1.1` and `@8.8.8.8` answer `34.180.56.204`. Caddy
asks Let's Encrypt for the certificate as soon as the VM's first deploy runs and the name points
there; until then its attempts fail and it retries on a backoff. When the rehearsal passes, the
TTL can go back to Auto.

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
| Secret | `FLY_API_TOKEN` | Fly's deploy token for `velora-api`: unused since P-921, removed by P-920 |
| Secret | `VERCEL_TOKEN` | the one-year token above |
| Secret | `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from the Vercel project |
| Secret | `SUPABASE_ACCESS_TOKEN` | the scoped, read-only token (§1), for the gate's plan check |
| Variable | `PRODUCTION_API_URL` | `https://api.veloraapp.co.in` |
| Variable | `PRODUCTION_WEB_URL` | `https://veloraapp.co.in` |
| Variable | `SUPABASE_PROJECT_REF` | `velora-prod`'s ref, from its URL |
| Variable | `GCP_PROJECT_ID` | `velora-ic-prod` |
| Variable | `GCP_WIF_PROVIDER` | the provider's full name: `gcloud iam workload-identity-pools providers describe velora --location=global --workload-identity-pool=github --project=velora-ic-prod --format='value(name)'` |
| Variable | `GCP_DEPLOY_SA` | `velora-deploy-prod@velora-ic-prod.iam.gserviceaccount.com` |

None of the three is secret: GitHub's token for this environment, from a `v*` tag only, is what
WIF accepts (D-1022). Read on 21 October 2026, names only: the environment held `FLY_API_TOKEN`,
`VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `PRODUCTION_API_URL` and `PRODUCTION_WEB_URL`; the rest of
this table is still to set.

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
EXPECT_API_VIA=Caddy scripts/staging-smoke https://api.veloraapp.co.in https://veloraapp.co.in
```

A configuration error stops the container with the message: read it in the `vm` job's log, or on
the VM (`sudo docker compose -p velora logs api`). The first release's own checks are T-2.6's
Done-when.

## Looking at selfies (D-264)

Until P-160 measures the face-match threshold, the founder looks at every selfie decision
(D-260: face matching alone doesn't stop a man holding a woman's photos and one real selfie of
her). From his own terminal, through IAP by his OS Login (§4):

```
gcloud compute ssh velora-api-prod --project=velora-ic-prod --zone=asia-south1-a --tunnel-through-iap
sudo docker compose -p velora exec -T api python -m app.tools.selfie_review
sudo docker compose -p velora exec -T api python -m app.tools.selfie_review --verdict <id> same
sudo docker compose -p velora exec -T api python -m app.tools.selfie_review --undo <id> --by <your id> --reason '<why>'
```

It lists each decision of the last 7 days without a verdict, newest first, with the selfie and
the face photo it was compared with (D-391, T-4.12) as signed links lasting 10 minutes, and the
shown photos compared with the selfie for the badge (D-393) by their public address; `NEAR` and
`MIXED` mark the ones to look at hardest (`--near` shows only those). `same` or `different`
records whether the selfie and the face photo show the same person: those verdicts are the
measurement P-160 needs. A verdict changes nothing else. `--undo` acts (P-163, D-1051): for an
approved match the review found wrong, the badge goes, a woman goes back to the selfie step,
signed in, to take it again, and a man keeps `done`; `--by` is your own admin id, written to
`audit_log` with the reason. It records `different` where no verdict is, and refuses one recorded
`same`.

The links print, unlike `storage_probe`'s output, on purpose (D-264): never paste them anywhere,
and never run this into a log or a chat. Claude runs it only on its own test accounts' selfies.
