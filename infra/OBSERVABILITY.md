# Observability — errors and alerts (T-9.12)

Sentry, EU region, the free Developer plan (D-1000). Where each secret lives and what each alert
means; never a value. The decisions: D-1000 to D-1005.

| | |
|---|---|
| Organisation | the founder's, EU (`de.sentry.io`) |
| Projects | `velora-api`: the API and the worker (tag `component`: `api`, `worker`); `velora-web`: the web (`web-browser`, `web-server`) |
| Environments | `staging`, `production`: from `ENV` and `APP_ENV`. Local and CI send nothing |
| Release | the commit's full SHA: `GIT_SHA` into the image (the deploy's `image` job), `NEXT_PUBLIC_SENTRY_RELEASE` into the web, both set by the deploy workflows |
| Alerts go to | email, to the account's one member |

## 1. The secrets: set before the first deploy of T-9.12

**Staging and production refuse to start, and the web refuses to build, without them** (D-1001).
Values never go in an argument or on screen.

**The API and the worker, on the Mumbai VMs (P-49): `SENTRY_DSN` in Secret Manager**, the
`velora-api` project's DSN, one secret per environment's Google Cloud project:

| Environment | Project | `SENTRY_DSN` |
|---|---|---|
| staging | `velora-ic-staging` | set (the founder, 18 October 2026) |
| production | `velora-ic-prod` | **empty: P-921's checklist** |

`infra/gce/secrets.api` and `secrets.worker` name it **required** (no trailing `?`), so the VM's
`deploy` stops with "SENTRY_DSN has no value in Secret Manager" before either container starts,
rather than starting one that refuses. `scripts/gcp-secrets <env>` asks for it at a hidden prompt
and keeps the Keychain's copy. To check without reading it, names and states only:

```
gcloud secrets versions list SENTRY_DSN --project=velora-ic-staging --format="table(name,state)"
```

`SENTRY_RELEASE` is never a secret: the image carries it (`GIT_SHA`, built by the deploy's `image`
job). There is no Fly secret: staging left Fly at P-49's cutover, and P-920 removes it.

**The web, on Vercel: `NEXT_PUBLIC_SENTRY_DSN`**, the `velora-web` project's DSN, in the
**Production** environment of both Vercel projects, `velora-staging` and `velora-production`, **as
Config, not Secret** (`--no-sensitive`): a Secret reads back as `[SENSITIVE]`, and the build
refuses it as a malformed DSN, as it once refused `APP_ENV` (STAGING.md §5). From `web/`, linked
to each project in turn, the value on stdin:

```
printf '%s' "$SENTRY_DSN_WEB" | pnpm dlx vercel env add NEXT_PUBLIC_SENTRY_DSN production --no-sensitive
```

`NEXT_PUBLIC_SENTRY_RELEASE` is never set in Vercel: the workflow sets it per build.

**The web's DSN is public by design**: it is in every page's code. It lets anyone send events
into the project, nothing more. The API's is kept in Secret Manager anyway.

## 2. The alerts: `scripts/sentry-alerts`

Sentry's side is code (D-1005): `api/ops/sentry_alerts.py` says what must exist, and the script
applies it or checks it. **The token** is a Sentry personal token, kept in the founder's Keychain,
service `velora-sentry-alerts`, never in GitHub or the repo. Scopes, the minimum (`SCOPES` in the
module): `org:read`, `member:read`, `project:read`, `project:write`, `alerts:read`, `alerts:write`
(`--check` needs only the four reads). Without `member:read` Sentry refuses `GET
/organizations/<org>/members/` with 403, which is how the script finds who gets the email (the
founder's first token, 19 October 2026; P-904).

```
SENTRY_AUTH_TOKEN="$(security find-generic-password -s velora-sentry-alerts -w)" scripts/sentry-alerts --apply
SENTRY_AUTH_TOKEN="$(security find-generic-password -s velora-sentry-alerts -w)" scripts/sentry-alerts --check
```

Exit 0 is exactly SPEC; 1 names each difference; 2 is no token; 3 is Sentry refusing, in its own
words. **Proven against a fake of Sentry's API only, until its first real run** (D-1005): if it
refuses there, its output is what to bring back.

What SPEC is:
- **One alert**, an email when an issue in either project is new, or comes back after being
  resolved or archived, or the uptime monitor finds `/readyz` down. Resolve an issue once it is
  dealt with: its next occurrence emails again. An open one doesn't repeat.
- **One uptime monitor**: `https://api.staging.veloraapp.co.in/readyz`, every 60 seconds: the
  Mumbai VM since P-49's cutover (read 18 October 2026 from a public resolver: one `A` record,
  `34.47.244.114`, the VM's static IP, and `/readyz` answering 200 through Caddy). It moves to
  production's for the production checklist (P-901). `/readyz` pings Redis, which Upstash doesn't
  charge (D-091).
- **Scrubbing on Sentry's side** on both projects: IP addresses never stored, the data scrubber on.
- Nothing else. **Sentry makes default alerts on every new project**, and `--check` names each
  as not in SPEC: delete them in Sentry's UI (the script never deletes). Seen on 19 October 2026:
  two "Send a notification for high priority issues" and one "Send a notification when pull
  requests are ready", deleted by the founder, after which `--check` exited 0.

## 3. What reaches Sentry (D-1002)

Every line the API or the worker logs at error level, and three warnings:

| Event | Means |
|---|---|
| `unhandled_exception` | a 500: a bug, with its route |
| `app_error_5xx` | a deliberate 5xx from a `/v1` route: a provider down, keys missing, the SMS cap spent |
| `otp_daily_cap_half_used` (warning) | half the day's SMS cap gone: possibly an attack (D-066) |
| `payments.turnover` (warning, then error) | the year's turnover past ₹15 lakh, then ₹20 lakh: register for GST within 30 days (P-381, P-350) |
| `payments.webhook_refused` (warning) | a webhook with a bad or no signature |
| `storage.delete_failed` | a minor's files that couldn't be deleted after three tries; the `banned_identities` id finds the row (D-090) |
| `job.failed`, each job's own last-try line | a job failed for good: raised, timed out, or ran out of tries |
| `minutely.failing` | a loop the worker runs itself failed three times in a row |
| `queue.depth_high` | more than 1,000 jobs waiting: the worker isn't keeping up, or isn't running (D-1004) |
| `wallet.ledger_mismatch` | from T-9.9's daily reconciliation: a wallet that isn't the sum of its ledger |

The web: any error the browser didn't catch, and the server's own (Next's `onRequestError`).

**No event carries personal data** (D-1003): no request, user, IP address, breadcrumb or local
variable, and an exception by its type and stack, never its message.

## 4. Checking it on staging, after the first deploy

1. Sentry → Releases: the deployed commit's SHA, in both projects.
2. A test error from each component, then its email; record each in the plan. The API's and the
   worker's, from inside their containers on the VM (`app/tools/sentry_probe.py`, P-904), which
   prints the event's id:

   ```
   gcloud compute ssh velora-api-staging --project=velora-ic-staging --zone=asia-south1-a --tunnel-through-iap
   sudo docker compose -p velora exec -T api python -m app.tools.sentry_probe --component api
   sudo docker compose -p velora exec -T worker python -m app.tools.sentry_probe --component worker
   ```

   The web's: an error thrown in a staging page's console, which the SDK's own handler catches.
3. A CSP violation reaching `velora-web` (the security endpoint): a page's console can make one,
   such as an image from a host the policy refuses.
4. `scripts/sentry-alerts --check`: exit 0.

## 5. Not yet

- **Source maps** (P-900): the web's stacks are minified until they're uploaded.
- **Production's uptime monitor** (P-901): staging's `/readyz` until then.
