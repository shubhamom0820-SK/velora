/**
 * Where the web reports its errors (T-9.12): Sentry, on staging and production
 * builds only, an allowlist by `APP_ENV` (CLAUDE.md rule 16). `next.config`
 * puts this build's config in `SENTRY_WEB_CONFIG`, and the CSP names its hosts
 * (security-headers.ts). Local and ci builds have none: nothing they do is
 * sent, and the SDK isn't in their bundle at all (instrumentation-client.ts).
 *
 * A staging or production build needs two variables, or it refuses to finish
 * (`assertSentryConfigured`, D-1001), as the API refuses to start: without
 * them every error the web meets would go nowhere, and nothing would fail.
 * - `NEXT_PUBLIC_SENTRY_DSN`: the web project's DSN, a Vercel variable. Public
 *   by design: it is in every page's code, and lets anyone send events into
 *   the project, nothing more (Sentry's own page on DSNs).
 * - `NEXT_PUBLIC_SENTRY_RELEASE`: the commit's SHA, which both deploys set
 *   from the gate's commit.
 */

/** What the SDK and the CSP need, worked out once from the build's variables. */
export type SentryWebConfig = {
  dsn: string;
  release: string;
  environment: string;
  /** The ingest host's origin: the SDK's connect-src. */
  ingestOrigin: string;
  /** Where the CSP's violations are reported: the project's security endpoint. */
  securityEndpoint: string;
};

type BuildEnv = Readonly<Record<string, string | undefined>>;

/** The builds that report to Sentry. Every other APP_ENV reports nothing. */
export const SENTRY_IN: ReadonlySet<string> = new Set([
  "staging",
  "production",
]);

// As Sentry writes a DSN: https://<public key>@<ingest host>/<project id>. The
// API checks its own the same way (core/config.py).
const DSN = /^https:\/\/([0-9a-f]{32})@([a-z0-9.-]+\.sentry\.io)\/([0-9]+)$/;
const GIT_SHA = /^[0-9a-f]{40}$/;

function reports(env: BuildEnv): boolean {
  return env.APP_ENV !== undefined && SENTRY_IN.has(env.APP_ENV);
}

/** This build's config, or none: none where APP_ENV doesn't report, or where
 *  either variable is missing or malformed. Never throws: the build's own
 *  check, `assertSentryConfigured`, is what refuses. */
export function sentryConfigFor(env: BuildEnv): SentryWebConfig | null {
  if (!reports(env)) return null;
  const dsn = env.NEXT_PUBLIC_SENTRY_DSN ?? "";
  const release = env.NEXT_PUBLIC_SENTRY_RELEASE ?? "";
  const parts = DSN.exec(dsn);
  if (parts === null || !GIT_SHA.test(release)) return null;
  const [, key, host, project] = parts;
  const ingestOrigin = `https://${host}`;
  const query = new URLSearchParams({
    sentry_key: key ?? "",
    sentry_environment: env.APP_ENV ?? "",
    sentry_release: release,
  });
  return {
    dsn,
    release,
    environment: env.APP_ENV ?? "",
    ingestOrigin,
    securityEndpoint: `${ingestOrigin}/api/${project}/security/?${query}`,
  };
}

/** A build that reports refuses to finish without a whole config, naming the
 *  variable and never echoing its value. */
export function assertSentryConfigured(env: BuildEnv): void {
  if (!reports(env)) return;
  const problems: string[] = [];
  if (!DSN.test(env.NEXT_PUBLIC_SENTRY_DSN ?? "")) {
    problems.push(
      env.NEXT_PUBLIC_SENTRY_DSN
        ? "NEXT_PUBLIC_SENTRY_DSN isn't a Sentry DSN (https://<key>@<host>.sentry.io/<project>)"
        : "NEXT_PUBLIC_SENTRY_DSN is unset",
    );
  }
  if (!GIT_SHA.test(env.NEXT_PUBLIC_SENTRY_RELEASE ?? "")) {
    problems.push(
      env.NEXT_PUBLIC_SENTRY_RELEASE
        ? "NEXT_PUBLIC_SENTRY_RELEASE isn't a commit's full SHA"
        : "NEXT_PUBLIC_SENTRY_RELEASE is unset",
    );
  }
  if (problems.length === 0) return;
  throw new Error(
    `A ${env.APP_ENV} build reports its errors to Sentry, and ${problems.join(
      "; and ",
    )} (T-9.12). The DSN is a Vercel variable (infra/OBSERVABILITY.md); the ` +
      "release is the commit, which both deploys set. Without them every error " +
      "the web meets would go nowhere.",
  );
}

/** This build's config, read back from what `next.config` put in the bundle.
 *  Anything that isn't a whole config is none: never a guess. */
export function sentryConfig(
  value: string | undefined = process.env.SENTRY_WEB_CONFIG,
): SentryWebConfig | null {
  if (!value) return null;
  try {
    const parsed: unknown = JSON.parse(value);
    return isConfig(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function isConfig(value: unknown): value is SentryWebConfig {
  if (typeof value !== "object" || value === null) return false;
  const fields = value as Record<string, unknown>;
  return (
    [
      "dsn",
      "release",
      "environment",
      "ingestOrigin",
      "securityEndpoint",
    ] as const
  ).every((name) => typeof fields[name] === "string" && fields[name] !== "");
}
