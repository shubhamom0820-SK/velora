/**
 * Every user-facing string (D-033). A Hindi dictionary joins after beta with the
 * same keys; components never hold copy, they call `t()` from ./t.
 *
 * `{name}` marks a value filled in by `t(key, { name })`.
 */
export const en = {
  meta: {
    description: "A web-first dating app for India.",
  },
  placeholder: {
    comingSoon: "Coming soon.",
    marketing: "{app}",
    login: "Sign in",
    discover: "Discover",
    admin: "Admin",
  },
} as const;
