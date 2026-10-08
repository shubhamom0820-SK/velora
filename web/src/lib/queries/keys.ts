/**
 * Every query key, built here so a component can't typo one and an
 * invalidation can't miss one. Each key starts with its feature, so
 * `invalidateQueries({ queryKey: ["threads"] })` reaches every thread query.
 * Features add their keys when they add their hooks.
 */
export const queryKeys = {
  health: () => ["health"] as const,
  me: () => ["me"] as const,
  intents: () => ["intents"] as const,
  interests: () => ["interests"] as const,
  areas: () => ["areas"] as const,
  usernameAvailable: (username: string) =>
    ["usernames", username, "available"] as const,
  myPhotos: () => ["photos", "mine"] as const,
  photo: (id: string) => ["photos", id] as const,
  verificationLatest: () => ["verification", "latest"] as const,
  // `wallet()` is the prefix of the ledger's key too, so one invalidation
  // refreshes the balance and the history together (T-5.5).
  wallet: () => ["wallet"] as const,
  walletLedger: () => ["wallet", "ledger"] as const,
  prices: () => ["prices"] as const,
  search: (q: string) => ["search", q] as const,
  // Each feed and filter set is its own scroll, ranked at its first instant
  // (D-491).
  discover: (
    feed: string,
    filters: {
      intentIds: readonly number[];
      verified: boolean;
      online: boolean;
    },
  ) =>
    [
      "discover",
      feed,
      {
        intentIds: [...filters.intentIds].sort(),
        verified: filters.verified,
        online: filters.online,
      },
    ] as const,
  // `likes()` is the prefix of the count's key too (T-6.7).
  likes: () => ["likes"] as const,
  likesCount: () => ["likes", "count"] as const,
  profile: (id: string) => ["profiles", id] as const,
  profileByUsername: (username: string) =>
    ["profiles", "by-username", username] as const,
};
