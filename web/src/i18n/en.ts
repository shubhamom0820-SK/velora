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
    login: "Sign in",
    discover: "Discover",
    admin: "Admin",
  },
  // Thread and Knot are product nouns, not the brand: a rename changes {app}
  // and nothing else here (CLAUDE.md rule 17).
  landing: {
    getStarted: "Get started",
    // headlineThreads ("a day"), intro and features.threads.title ("24-hour")
    // promise app_config.thread_hours, seeded 24. Copy, not a computation, so
    // it's written out rather than read: change it with the setting (T-2.1).
    headlineThreads: "Threads last a day.",
    headlineKnots: "Knots last.",
    intro:
      "Meet people nearby. Every conversation starts as a 24-hour thread. If you both want to keep it, you tie the knot and it becomes permanent.",
    join: "Join {app}",
    ageNote: "18+ only · Free for women, always",
    features: {
      threads: {
        title: "24-hour threads",
        body: "No dead matches sitting for weeks. Talk, or it goes.",
      },
      knot: {
        title: "Tie the knot",
        body: "Both of you choose to keep it. Then it never expires.",
      },
      safety: {
        title: "Verified, moderated",
        body: "Selfie verification, photo checks, and reports that actually remove people.",
      },
    },
    footer: {
      label: "Legal and contact",
      terms: "Terms",
      privacy: "Privacy",
      refunds: "Refunds",
      contact: "Contact",
      copyright: "© {year} {app} · Bengaluru, India",
    },
  },
  ui: {
    close: "Close",
    loading: "Loading",
    remove: "Remove {label}",
    counter: "{count}/{max}",
    online: "Online",
    verified: "Verified",
    errorTitle: "Something went wrong",
    retry: "Try again",
  },
} as const;
