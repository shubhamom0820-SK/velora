/**
 * What a staging or production build needs for Sentry (T-9.12), for tests that
 * build `next.config` as one: a DSN shaped as Sentry writes one, pointing at no
 * real project, and a commit's SHA. Without them such a build refuses.
 */
export const SENTRY_BUILD = {
  NEXT_PUBLIC_SENTRY_DSN:
    "https://0123456789abcdef0123456789abcdef@o4500000000000000.ingest.de.sentry.io/4500000000000001",
  NEXT_PUBLIC_SENTRY_RELEASE: "0123456789abcdef0123456789abcdef01234567",
} as const;
