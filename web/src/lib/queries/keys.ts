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
  // The store (T-8.7): asked again when a purchase lands, since the
  // first-purchase bonus is gone after one.
  packs: () => ["packs"] as const,
  payment: (id: string) => ["payments", id] as const,
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
  // `threads()` is the prefix of every list's key (T-7.10), so a clearing
  // asks every tab, filter and search again.
  threads: () => ["threads"] as const,
  threadList: (tier: string, filter: string, q: string) =>
    ["threads", "list", tier, filter, q] as const,
  // One Thread's screen (T-7.11). Three keys, none the prefix of another, so
  // asking the Thread again never refetches every page of its messages.
  thread: (id: string) => ["threads", "one", id] as const,
  messages: (id: string) => ["threads", "messages", id] as const,
  // Whether the other person is typing: written by the socket (T-7.12) and
  // read by the screen; never asked of the API.
  typing: (id: string) => ["threads", "typing", id] as const,
  // A voice note's signed link, 10 minutes long (D-027).
  voiceMedia: (messageId: string) => ["messages", messageId, "media"] as const,
  profile: (id: string) => ["profiles", id] as const,
  // The private album (T-8.8): someone's, as the viewer may see it, and the
  // requests to see one's own.
  album: (id: string) => ["album", "of", id] as const,
  albumIncoming: () => ["album", "incoming"] as const,
  // `gifts()` is the prefix of every gift query (T-8.10), so a send asks the
  // catalogue's free sends, a profile's counts and her list again together.
  gifts: () => ["gifts"] as const,
  giftCatalogue: () => ["gifts", "catalogue"] as const,
  giftCounts: (userId: string) => ["gifts", "counts", userId] as const,
  receivedGifts: () => ["gifts", "received"] as const,
  profileByUsername: (username: string) =>
    ["profiles", "by-username", username] as const,
};
