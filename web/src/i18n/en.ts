import type { components } from "@/types/api";

type LedgerReason = components["schemas"]["LedgerReason"];

/**
 * What the wallet's history calls each reason Velas moved (T-5.5): the API
 * sends the enum, never words (D-033, P-26). `satisfies` makes a reason the
 * API adds without words here fail `tsc`, and so do words for a reason it
 * drops. Drafted by Claude, for the founder's review.
 */
const ledgerReasons = {
  purchase: "Velas bought",
  purchase_bonus: "First-purchase bonus",
  referral_reward: "Referral reward",
  admin_grant: "Added by {app}",
  refund: "Refund",
  gift: "Gift sent",
  // Unused since D-230, never repurposed: the words stay for the enum.
  refund_banned_partner: "Returned after a ban",
  refund_album_declined: "Returned: request declined",
  thread_open: "Thread opened",
  dm_open: "First private message",
  thread_reopen: "Thread re-opened",
  voice_unlock: "Voice note unlocked",
  album_request: "Private pictures viewed",
  super_like: "Super Like",
  liked_you_reveal: "Revealed who liked you",
  thread_extend: "Thread extended",
  dm_message: "Private message",
  // T-8.2 (D-521): a refund or chargeback takes a purchase's Velas back, and a
  // refund that fails or a dispute that is won gives them back. The founder's
  // words, 8 October 2026.
  purchase_reversal: "Purchase reversed",
  purchase_restored: "Purchase restored",
  // T-8.11 (D-470): every new man's Velas when he finishes sign-up.
  welcome: "Welcome Velas",
} as const satisfies Record<LedgerReason, string>;

/**
 * Every user-facing string (D-033). A Hindi dictionary joins after beta with the
 * same keys; components never hold copy, they call `t()` from ./t.
 *
 * `{name}` marks a value filled in by `t(key, { name })`.
 */
export const en = {
  meta: {
    description: "A web-first dating app for India.",
    // A page's title in the tab and in search results, "Privacy policy ·
    // Velora". Next fills in %s (T-2.4).
    titleTemplate: "%s · {app}",
    // The home page's title: the brand, then the landing headline.
    homeTitle: "{app} · {headline}",
  },
  placeholder: {
    comingSoon: "Coming soon.",
    login: "Sign in",
    admin: "Admin",
  },
  // Restoring and ending a session (T-3.10).
  session: {
    signOut: "Sign out",
    signOutFailed:
      "We couldn't sign you out. Check your connection and try again.",
    restoreFailedTitle: "We couldn't reach {app}",
    restoreFailedBody: "Check your connection and try again.",
  },
  // The app's header and bottom nav (T-5.6). No Vibe: after beta (D-010).
  shell: {
    nav: "Main",
    discover: "Discover",
    chats: "Chats",
    wallet: "Wallet",
    you: "You",
  },
  // Search (T-6.6, D-540): a name, a city, an intent or an interest nearby,
  // or @ and a username anywhere. Drafted by Claude, for the founder's review.
  search: {
    title: "Search",
    label: "Search people",
    placeholder: "Name, city, interest or @username",
    hint: "Search by name, city, interest or what someone is looking for nearby. Start with @ to find a username anywhere.",
    tooShort: "Type at least {min} letters.",
    badUsername: "Usernames use only a–z, 0–9, dots and underscores.",
    usernameMode: "@ username",
    exact: "Exact",
    resultsFor: "Results for {q}",
    empty: "No one found",
    emptyBody: "Try a different name, or check the spelling.",
    failed: "We couldn't search just now",
    loadingMore: "Loading more",
    // "Simran, 24", or "Simran" when she hides her age.
    nameAge: "{name}, {age}",
    // "@simran.k · Phagwara", or "@simran.k" without a city.
    usernameCity: "@{username} · {city}",
    usernameOnly: "@{username}",
  },
  // The discover deck (T-6.5), drawn from 08-DESIGN §8. Prices are never
  // written here: they come from /prices, as a number ("5") on a button and in
  // words ("5 Velas", wallet.velas) elsewhere. A woman sees no price (D-002).
  // Drafted by Claude, for the founder's review.
  discover: {
    title: "Discover",
    feeds: {
      label: "Feeds",
      foryou: "For you",
      new: "New",
      online: "Online",
    },
    search: "Search",
    // The feed row's Filters button and its sheet (T-6.9). Free for everyone
    // (D-660). "Selfie matched" is D-393's badge in D-262's words: never
    // "verified" (claims.test.ts).
    filters: {
      open: "Filters",
      // The button read out with its badge: "Filters, 2 on".
      openCount: {
        one: "Filters, 1 on",
        other: "Filters, {count} on",
      },
      title: "Filters",
      count: {
        one: "1 on",
        other: "{count} on",
      },
      lookingFor: "Looking for",
      intentsFailed: "We couldn't load what people are looking for",
      selfie: "Selfie matched",
      selfieBody: "Their selfie matched a photo on their profile",
      online: "Online now",
      onlineBody: "Active in the last few minutes",
      clear: "Clear",
      show: "Show people",
    },
    deck: "People nearby",
    card: {
      // "Simran, 24", or "Simran" when she hides her age.
      nameAge: "{name}, {age}",
      openProfile: "Open {name}'s profile",
      // "Phagwara · 3 km": the city, the distance, each left out when hidden.
      km: "{km} km",
      online: "Online now",
      new: "New",
      noPhoto: "Prefers not to show photos yet",
      // The words stamped on the card as it is dragged.
      like: "Like",
      pass: "Pass",
      super: "Super",
    },
    actions: {
      label: "Swipe",
      pass: "Pass",
      like: "Like",
      super: "Super Like",
      // A man's Super Like, read out with its price: "Super Like, 5 Velas".
      superPriced: "Super Like, {velas}",
    },
    swipesLeft: {
      one: "1 swipe left today",
      other: "{count} swipes left today",
    },
    match: {
      title: "You and {name} liked each other",
      // "Open thread · 5 Velas" for him, the number from /prices.
      open: "Open thread · {velas}",
      openFree: "Open thread · Free",
      // His, while the price loads: never a number guessed.
      openPlain: "Open thread",
      keepSwiping: "Keep swiping",
      // Copy follows app_config.thread_hours (P-14): 1 since T-7.6, in
      // 08-DESIGN §8's words.
      footer: "Threads last an hour. Knots last.",
    },
    empty: {
      nobodyTitle: "No one new nearby",
      nobodyBody: "New people join every day. Check back soon.",
      checkAgain: "Check again",
      filtersTitle: "No one matches these filters",
      filtersBody: "Try fewer filters to see more people.",
      clear: "Clear filters",
    },
    failed: "We couldn't load people nearby",
    errors: {
      limit: "That's today's swipes. More at midnight.",
      priceChanged: "The price changed. It's {velas} now.",
      failed: "That didn't go through. Try again.",
      openFailed: "We couldn't open the thread. Try again.",
    },
  },
  // A person's profile in the app (T-6.8, 08-DESIGN §8) and their public page,
  // `/@username` (D-544). Never "verified" (D-262): the tick says what was
  // matched. Drafted by Claude, for the founder's review.
  profile: {
    title: "Profile",
    photo: "Photo {n} of {total}",
    noPhoto: "Prefers not to show photos yet",
    nameAge: "{name}, {age}",
    online: "Online now",
    km: "{km} km",
    from: "from {hometown}",
    selfieNote: "Their selfie matched a photo you see here",
    lookingFor: "Looking for",
    about: "About",
    interests: "Interests",
    kudos: "Kudos",
    kudosKind: {
      great_conversation: "Great conversation",
      // Not "Genuinely": D-262's list refuses the word anywhere (claims.test.ts).
      genuinely_funny: "Truly funny",
      easy_to_talk_to: "Easy to talk to",
      really_thoughtful: "Really thoughtful",
    },
    album: "Private album",
    albumOne: "1 private photo",
    albumOther: "{count} private photos",
    // The album row (T-8.8, D-732): locked, waiting or shown. A decline or a
    // revoke reads as locked, never named (D-230). Drafted by Claude, for the
    // founder's review.
    albumAsk: "Ask to view · {price}",
    albumAsking: "Asking",
    albumPending: "Asked. Waiting for an answer.",
    albumPreparing: "Getting the photos ready",
    albumPhoto: "Private photo {n} of {total}",
    albumNote:
      "Each photo is marked with your username. They're for you alone.",
    albumSent: "Request sent",
    // `recently_declined` (D-731), in words that never say a decline happened
    // nor name the person (the founder, 9 October 2026, D-790);
    // album-copy.test.ts holds it.
    albumTooSoon: "You can't send a request right now. Try again later.",
    albumEmpty: "There's nothing in this album to see right now.",
    albumUnavailable: "You can't ask to see this album.",
    albumPriceChanged: "The price changed. It's {velas} now.",
    albumFailed: "We couldn't send your request. Try again.",
    albumLoadFailed: "We couldn't load the album",
    // The kudos prompt (T-8.8, D-790): only when `POST /kudos` would take it.
    // Drafted by Claude, for the founder's review.
    kudosAsk: "Give {name} kudos",
    kudosAskBody:
      "Pick one. Their profile can show how many people chose each, never who.",
    kudosSent: "Kudos sent",
    kudosTooEarly: "Talk a little more first.",
    kudosFailed: "We couldn't send kudos. Try again.",
    yours: "This is how others see your profile.",
    more: "More",
    share: "Share profile",
    shareText: "{name} on {app}",
    copied: "Link copied",
    copyFailed: "We couldn't copy the link. Try again.",
    like: "Like",
    liked: "Liked",
    matched: "You liked each other.",
    likeRefused: "You can't like this profile.",
    likeLimit: "That's today's swipes. More tomorrow.",
    likeFailed: "We couldn't send that like. Try again.",
    notFound: "This profile isn't available",
    notFoundBody: "It may be hidden, or no longer here.",
    failed: "We couldn't load this profile",
    // Report and Block (T-9.1, P-442), from the prototype's sheets. One of its
    // lines waits for its task: the moderator's 24 hours for T-9.5 (P-761);
    // "undo this from the You tab" came with T-9.8's blocked list (P-762). A
    // block is silent (D-862): nothing here may say the other person is told.
    report: "Report this profile",
    block: "Block {name}",
    reportTitle: "Report {name}",
    reportIntro:
      "This goes to our moderators, in confidence: they're never told who reported them.",
    reportReasons: "What happened?",
    reason: {
      fake: "Fake profile or stolen photos",
      scam: "Asking for money or off-platform payment",
      harass: "Harassment or abusive messages",
      sexual: "Unwanted sexual content",
      minor: "Appears to be under 18",
      other: "Something else",
    },
    reportDetails: "Tell us more",
    reportDetailsHelper: "Optional, but it helps",
    reportDetailsPlaceholder: "What did they say or do?",
    alsoBlock: "Also block {name}",
    reportSend: "Send report",
    reportPick: "Pick a reason first",
    reportSentTitle: "Report sent",
    reportSentBody:
      "They're never told who reported them, and nothing you wrote appears on their profile.",
    reportDone: "Done",
    reportTooMany: "You've sent a lot of reports today. Try again tomorrow.",
    reportFailed: "We couldn't send your report. Try again.",
    blockTitle: "Block {name}?",
    blockTheyWont: "They won't see your profile anywhere in {app}",
    blockYouWont: "You won't see theirs",
    blockThreads: "Any Thread or Knot between you disappears",
    blockSilent: "They're never told they've been blocked",
    blockUndo: "You can undo this from the You tab",
    blockCancel: "Cancel",
    blocked: "{name} blocked",
    blockFailed: "We couldn't block {name}. Try again.",
  },
  // The You tab (T-9.8), built from existing parts (D-913): no design of its
  // own yet (08-DESIGN §8). Drafted by Claude, for the founder's review.
  you: {
    title: "You",
    summaryFailed: "We couldn't load your profile",
    username: "@{username}",
    edit: "Edit profile",
    editSave: "Save",
    editSaved: "Profile saved",
    photos: "Photos",
    // D-910: a new main photo carries no tick until it matches the selfie.
    photosHint:
      "The first photo is your main one. Each new photo is checked before anyone sees it, and the tick shows only while your main photo matches your selfie.",
    // The badge's line (D-262, D-910): what was done, never "verified".
    selfieMainNotYet:
      "Your selfie matched. The tick shows once your main photo matches it too.",
    selfieNone: "No selfie check yet.",
    kudos: {
      title: "Kudos you've received",
      body: "Only positive notes exist. Whether your profile shows them is up to you, in Privacy and account.",
      empty: "None yet.",
      failed: "We couldn't load your kudos.",
      count: "{label} · {count}",
    },
    knots: {
      title: "Your Knots",
      empty: "No Knots yet.",
      failed: "We couldn't load your Knots.",
      untie: "Untie",
      untieName: "Untie the knot with {name}",
      untieTitle: "Untie the knot with {name}?",
      untieBody: "It becomes a Thread again.",
      untieConfirm: "Untie",
      untieCancel: "Keep it",
      untied: "Untied",
      untieFailed: "We couldn't untie it. Try again.",
    },
    blocked: {
      title: "Blocked",
      empty: "You haven't blocked anyone.",
      failed: "We couldn't load who you've blocked.",
      unblock: "Unblock",
      unblockName: "Unblock {name}",
      unblocked: "{name} unblocked",
      unblockFailed: "We couldn't unblock {name}. Try again.",
    },
    // D-911: never a status, never a time (the 24 hours wait on P-761).
    reports: {
      title: "Reports you've filed",
      body: "Our team reviews every report. Nobody is told who reported them.",
      empty: "You haven't filed any reports.",
      failed: "We couldn't load your reports.",
      row: "{reason} · {date}",
    },
    cleared: {
      title: "Cleared chats",
      body: "Hidden from your list only. The other person still has their copy.",
      empty: "No cleared chats.",
      failed: "We couldn't load your cleared chats.",
      restore: "Restore",
      restoreName: "Restore your chat with {name}",
      restored: "Restored",
      restoreFailed: "We couldn't restore it. Try again.",
    },
    settings: "Settings",
    account: "Privacy and account",
    lockNow: "Lock now",
    more: "Show more",
  },
  // Privacy and account (T-9.8, T-9.6's routes), at /you/settings. Drafted by
  // Claude, for the founder's review.
  settings: {
    title: "Privacy and account",
    privacy: "Privacy",
    hidden: "Hide my profile",
    hiddenHint:
      "Out of Discover and search. People you already match or chat with can still open it.",
    hideAge: "Hide my age",
    hideDistance: "Hide my distance",
    showKudos: "Show kudos on my profile",
    // D-544: off until its owner turns it on.
    publicLink: "Public link",
    publicLinkHint:
      "Lets people who aren't signed in see your name, age, city and main photo at {link}.",
    saveFailed: "We couldn't save that. Try again.",
    pause: {
      title: "Pause",
      body: "While paused, nobody sees your profile and we send you no notifications.",
      button: "Pause my account",
      paused: "Your account is paused. Nobody sees your profile.",
      resume: "Resume",
      failed: "We couldn't change that. Try again.",
    },
    // D-502: your own data, a link for 24 hours, then deleted.
    export: {
      title: "A copy of your data",
      body: "A file of your own data: your profile, photos, the messages you sent and your activity. The link works for 24 hours.",
      ask: "Get a copy",
      askAgain: "Get a new copy",
      pending: "Making your copy…",
      ready: "Download your copy",
      until: "The link works until {time}.",
      failed: "We couldn't make your copy. Try again.",
      loadFailed: "We couldn't check on your copy.",
      tooMany: "That's today's copies. Try again tomorrow.",
    },
    // D-500, D-504; /privacy's words (legal.privacy.deletion).
    delete: {
      title: "Delete account",
      button: "Delete my account",
      sheetTitle: "Delete your account?",
      gone: "Your profile disappears straight away and you're signed out everywhere.",
      restore:
        "Changed your mind? Sign in again within 29 days and your account comes back as it was.",
      erased:
        "After that we erase your profile, your photos and your private album. Your messages stay in the other person's chat, shown as from “Deleted account”.",
      // D-504: the number is `Me.balance`, never written here.
      velas: {
        one: "You have {count} Vela. It's lost when your account is erased, unless you sign in again within 29 days.",
        other:
          "You have {count} Velas. They're lost when your account is erased, unless you sign in again within 29 days.",
      },
      confirm: "Delete my account",
      cancel: "Keep my account",
      failed: "We couldn't delete your account. Try again.",
    },
  },
  // The requests to see your private album (T-8.8, D-732), at
  // /you/album-requests. Drafted by Claude, for the founder's review.
  albumRequests: {
    title: "Album requests",
    intro:
      "People who asked to see your private album. Only you decide who sees it.",
    wants: "Asked to see your album",
    sees: "Can see your album",
    grant: "Let them see",
    decline: "Decline",
    revoke: "Stop sharing",
    revokeTitle: "Stop sharing with {name}?",
    revokeBody:
      "Their copies of your photos are deleted, and your album is locked to them again.",
    cancel: "Cancel",
    granted: "They can see your album now",
    declined: "Request declined",
    revoked: "Your album is locked to them again",
    deleted: "Deleted account",
    alreadyAnswered: "That request was already answered.",
    gone: "That request isn't there anymore.",
    failed: "We couldn't save that. Try again.",
    empty: "No requests",
    emptyBody: "When someone asks to see your private album, they'll be here.",
    loadFailed: "We couldn't load your requests",
    loadingMore: "Loading more",
  },
  // Gifts (T-8.10, D-231, D-650, D-652): his sheet on a woman's profile, and
  // what she received. He sees each gift's price, read from `GET /gifts`, never
  // written here; she never sees a price or whether a send was free. Drafted
  // by Claude, for the founder's review.
  gifts: {
    give: "Gift",
    title: "Send {name} a gift",
    free: "Free",
    freeLeft: {
      one: "1 free send left this week",
      other: "{count} free sends left this week",
    },
    // The date is the next Monday, in IST (D-650).
    noneLeft: "No free sends left this week. They come back {date}.",
    tile: "{label}, {price}",
    choose: "Choose a gift",
    send: "Send {gift} · {price}",
    sent: "{gift} sent to {name}",
    // GIFT_COOLDOWN: the same gift to her inside the cooldown (D-016).
    cooldown:
      "You sent {name} a {gift} recently. You can send another in {wait}, or choose a different gift now.",
    waitHours: "{hours}h {minutes}m",
    waitMinutes: "{minutes}m",
    priceChanged: "The price changed. It's {velas} now.",
    nowFree: "The price changed. This one is free now.",
    unavailable: "{name} can't receive gifts right now.",
    failed: "We couldn't send that gift. Try again.",
    loadFailed: "We couldn't load the gifts",
    // Her profile's row: how many of each, never from whom.
    received: "Gifts",
    count: "{label}, {count}",
    onlyYou: "Only you can see these. Turn on Show gifts under You.",
    // The You tab's section (hers).
    yours: "Gifts you've received",
    from: "{gift} from {name}",
    someGift: "A gift",
    empty: "No gifts yet",
    emptyBody: "When someone sends you a gift, it shows up here.",
    listFailed: "We couldn't load your gifts",
    more: "Show more",
    show: "Show gifts on my profile",
    showBody:
      "People who open your profile see how many of each you've received, never who sent them.",
    saveFailed: "We couldn't change that. Try again.",
  },
  // `/@username` for someone not signed in (T-6.8, D-544).
  share: {
    title: "{name} on {app}",
    join: "Join {app} to message",
    unavailable: "This profile isn't public",
    unavailableBody: "Join {app} to meet people near you.",
  },
  // Liked you (T-6.7, D-542): who liked you and is waiting on your swipe. A
  // man reveals each for the price `/prices` gives, never written here; a
  // woman sees everyone. Drafted by Claude, for the founder's review.
  likes: {
    title: "Liked you",
    count: "{count} waiting",
    someone: "Someone who liked you",
    superLike: "Super Like",
    reveal: "Reveal · {price}",
    revealing: "Revealing",
    revealFailed: "We couldn't show who it was just now. Try again.",
    priceChanged: "The price changed. It's {velas} now.",
    entry: "Liked you",
    entryCount: "Liked you, {count} waiting",
    nameAge: "{name}, {age}",
    distance: "{km} km away",
    empty: "No one yet",
    emptyBody: "When someone likes you, they'll be here.",
    failed: "We couldn't load who liked you",
    loadingMore: "Loading more",
  },
  // The chats list (T-7.10, 08-DESIGN §8): Threads and Knots. Her list says
  // nothing about time, expiry or price (D-097, D-554, P-460): no countdown, no
  // "Clear expired", no footer. Drafted by Claude, for the founder's review.
  chats: {
    title: "Chats",
    threads: "Threads",
    knots: "Knots",
    tabCount: "{tab}, {count}",
    tabCountOver: "{tab}, more than {count}",
    filters: "Show",
    filterAll: "All",
    filterUnread: "Unread",
    filterRecent: "Recent",
    search: "Search by name",
    select: "Select",
    done: "Done",
    selectRow: "Select the chat with {name}",
    selectLimit: "You can clear up to {max} at a time.",
    clearSelected: {
      one: "Clear 1 chat",
      other: "Clear {count} chats",
    },
    clearExpired: "Clear expired ({count})",
    clearRow: "Clear the chat with {name}",
    // 08-DESIGN §6: "Cleared from your chats", never "Deleted".
    cleared: "Cleared from your chats",
    clearedMany: {
      one: "1 chat cleared from your chats",
      other: "{count} chats cleared from your chats",
    },
    undo: "Undo",
    clearFailed: "We couldn't clear that just now. Try again.",
    restoreFailed: "We couldn't bring it back just now. Try again.",
    deletedAccount: "Deleted account",
    voiceNote: "Voice note",
    noMessages: "No messages yet",
    unread: {
      one: "1 unread message",
      other: "{count} unread messages",
    },
    knot: "Knot",
    emptyThreads: "No threads yet",
    emptyThreadsBody: "When you match with someone, your Thread shows here.",
    emptyKnots: "No knots yet",
    emptyKnotsBody: "When you both tie the knot, the chat moves here, to stay.",
    emptyAction: "Go to Discover",
    noResults: "No chats match",
    noResultsBody: "Try another name or filter.",
    failed: "We couldn't load your chats",
    loadingMore: "Loading more",
    // His alone (08-DESIGN §8). Copy follows app_config.thread_hours (P-14):
    // 1 since T-7.6, restarted by her messages (D-097).
    footer: "A Thread lasts an hour from her last message. Knots last.",
  },
  // One conversation (T-7.11, 08-DESIGN §8). Her side says nothing about time,
  // expiry or price (D-097, D-554, P-460): no countdown, no Extend, no expired
  // sheet, no hour, no Velas, anywhere, the Knot's sheet included. Copy that
  // names the hour follows app_config.thread_hours (1, P-14) and "24h" or "a
  // day" thread_extend_hours (24): change it with the setting. Drafted by
  // Claude, for the founder's review.
  conversation: {
    title: "Chat",
    back: "Back to chats",
    messages: "Messages",
    online: "Online now",
    deletedAccount: "Deleted account",
    notFound: "This chat isn't available",
    notFoundBody: "Go back to your chats to find another.",
    failed: "We couldn't load this chat",
    loadingOlder: "Loading earlier messages",
    olderFailed: "We couldn't load earlier messages",
    // The header (his): "41m left · her reply restarts the hour".
    restarts: "her reply restarts the hour",
    extend: "Extend 24h · {count}",
    extendLabel: "Extend by a day, for {velas}",
    extended: "Extended by a day",
    extendFailed: "We couldn't extend it just now. Try again.",
    ranOutAt: "The hour ran out · {time}",
    knottedToday: "Knotted today",
    knottedYesterday: "Knotted yesterday",
    knottedDays: "Knotted {days} days ago",
    // His composer's gift button (T-7.12).
    gift: "Send {name} a gift",
    // The ⋯ menu.
    more: "More",
    viewProfile: "View profile",
    clearChat: "Clear chat",
    cleared: "Cleared from your chats",
    clearFailed: "We couldn't clear that just now. Try again.",
    untie: "Untie the knot",
    untieTitle: "Untie the knot?",
    untieBody:
      "It becomes a Thread again. To make it a Knot, you both have to tie it again.",
    untieConfirm: "Untie",
    untieKeep: "Keep the knot",
    untied: "Untied",
    untieFailed: "We couldn't untie it just now. Try again.",
    // The list.
    today: "Today",
    yesterday: "Yesterday",
    ranOutDivider: "The hour ran out",
    tiedDivider: "You tied the knot · {date}",
    newAt: "New · {time}",
    seen: "Seen {time}",
    notSeen: "Not seen yet",
    sending: "Sending",
    notSent: "Not sent",
    retry: "Retry",
    typing: "{name} is typing",
    masked:
      "Phone numbers, emails, UPI IDs and handles are hidden in a Thread's first messages.",
    // An empty Thread: the prototype's icebreakers, three shown.
    emptyTitle: "Say hello",
    emptyBody: "Not sure how to start? Tap one to use it.",
    icebreakers: {
      laugh: "What's the last thing that made you laugh?",
      eaten: "Best thing you've eaten this week?",
      truths: "Two truths and a lie — go.",
    },
    // The knot bar, in each person's words (08-DESIGN §8).
    knotBarHis:
      "Tie the knot and this never runs out. Free, if she ties it too.",
    knotBarHers: "Tie the knot and this stays, always. He has to tie it too.",
    tie: "Tie the knot",
    waiting: "You tied it. Waiting for {name}.",
    tieFailed: "We couldn't tie the knot just now. Try again.",
    // The "Knot tied ✦" sheet (P-670). Hers says nothing of the hour or Velas.
    tied: {
      title: "You and {name} tied the knot",
      bodyHis: "No hour. No Velas. This one stays, because you both chose it.",
      bodyHers: "This one stays, because you both chose it.",
      keepTalking: "Keep talking",
    },
    // His expired Thread's sheet (08-DESIGN §8): never hers.
    expired: {
      titleWrote: "She wrote back. The hour had run out.",
      title: "The hour ran out.",
      bodyWrote: "You can read everything. To reply, open the Thread again.",
      body: "You can read everything. To write again, open the Thread again.",
      reopen: "Re-open · {velas}",
      reopenKeep: "Re-open and keep it for 24h · {velas}",
      note: "Re-open gives you a fresh hour. Extend adds a day, as many times as you like.",
      reopenFailed: "We couldn't re-open it just now. Try again.",
    },
    priceChanged: "The price changed. It's {velas} now.",
    // The composer.
    placeholder: "Message",
    send: "Send",
    sendPriced: "Send, for {velas}",
    // His, when the next message costs something (D-870's send_price).
    priceDm: "Each message here costs {velas}.",
    priceOne: "This message costs {velas}.",
    rejected: {
      abuse:
        "That message has words we don't allow. Change it and send it again.",
      solicitation:
        "Messages can't ask for money or payments. Change it and send it again.",
      other: "That message can't be sent. Change it and send it again.",
    },
    expiredRefused: "The hour ran out before that was sent.",
    accountDeleted: "They deleted their account. You can still read your chat.",
    rateLimited: "That's a lot of messages for now. Try again in a while.",
    sendFailed: "Not sent. Check your connection and retry.",
    // Voice notes: hers to record (D-010), his to unlock (T-7.9).
    voice: {
      label: "Voice note, {duration}",
      play: "Play the voice note",
      pause: "Pause the voice note",
      unlock: "Unlock · {velas}",
      unlockLabel: "Unlock this voice note for {velas}",
      unlockFailed: "We couldn't unlock it just now. Try again.",
      playFailed: "We couldn't play that voice note. Try again.",
      record: "Record a voice note",
      stop: "Stop recording",
      recording: "Recording, {time}",
      hint: "Hold to record, or tap to start and tap again to stop.",
      preview: "Your voice note, {duration}",
      discard: "Discard the voice note",
      send: "Send the voice note",
      uploading: "Sending, {percent}%",
      capped: "A voice note is a minute at most, so it stopped there.",
      tooShort: "A voice note is at least a second. Hold a little longer.",
      denied:
        "Your browser refused the microphone. Allow it for this site in its settings to record.",
      unsupported: "This browser can't record voice notes.",
      failed: "Recording failed. Try again.",
      notSent: "That voice note wasn't sent. Try again.",
      tooLarge: "That recording is too large to send.",
      tooLong: "A voice note is a minute at most.",
      unreadable: "That recording couldn't be read. Record it again.",
    },
  },
  // The balance pill, the wallet screen and the store sheet (T-5.5). Users see
  // Velas, never "credits" (D-049). Drafted by Claude, for the founder's review.
  wallet: {
    title: "Wallet",
    velas: {
      one: "{count} Vela",
      other: "{count} Velas",
    },
    // The unit beside the balance card's number.
    unit: {
      one: "Vela",
      other: "Velas",
    },
    // The pill in the header (men): the button's name for screen readers.
    pill: "{velas}. Buy Velas",
    pillLoading: "Balance loading. Buy Velas",
    pillUnavailable: "Balance unavailable. Buy Velas",
    freeAccess: "Free access",
    balance: "Your balance",
    balanceFailed: "We couldn't load your balance",
    buy: "Buy Velas",
    prices: "What things cost",
    pricesFailed: "We couldn't load the prices",
    free: "Free",
    tieTheKnot: "Tie the knot",
    knotMessages: "Messaging in a knot",
    // The price list's words for each priced action, by its debit reason
    // (pricing.service keys `action_prices` by it).
    action: {
      thread_open: "Open a thread",
      thread_reopen: "Re-open an expired thread",
      thread_extend: "Extend a thread by a day",
      dm_open: "First private message",
      dm_message: "Each private message after it",
      album_request: "View private pictures",
      voice_unlock: "Listen to a voice note",
      super_like: "Super Like",
      liked_you_reveal: "See one person who liked you",
    },
    reason: ledgerReasons,
    history: "History",
    historyFailed: "We couldn't load your history",
    historyEmpty: "Nothing yet",
    historyEmptyBody: "Velas you get and spend show up here.",
    loadingMore: "Loading more",
    // A quiet link: purchases are final, and a broken payment is ours to fix
    // (D-050, D-230). No refund request and no "refundable within 7 days".
    refunds: "Refund policy",
    // Women (D-098): no balance, no prices, no history. No calls (after beta).
    womenTitle: "Everything is free for you",
    womenBody:
      "Threads, knots, voice notes and your private album cost you nothing, and never will.",
    // The store and its checkout (T-8.7). Drafted by Claude, for the founder's
    // review. Never "GST", in any case, anywhere a man looks while Velora is
    // unregistered (D-450, D-482; StoreSheet.test.tsx reads every string), and
    // never "Most popular" until purchases make it true (D-760, P-660).
    store: {
      title: "Buy Velas",
      loading: "Loading packs",
      failed: "We couldn't load the packs",
      emptyTitle: "Nothing to buy right now",
      emptyBody: "There are no packs on sale at the moment.",
      firstPurchase: "Your first purchase comes with bonus Velas",
      bonus: "+{count} bonus",
      rate: "{perVela} a Vela · {perThread} a Thread",
      rateVelaOnly: "{perVela} a Vela",
      // The cheapest Vela, worked out from the packs (D-760): true on day one.
      bestValue: "Best value",
      final: "Purchases are final. A payment that goes wrong is ours to fix.",
      refunds: "Refund policy",
      opening: "Opening the payment window",
      // Before any payment window opens, so nothing was charged.
      priceChanged:
        "This pack's price just changed. Here are the packs again; nothing was charged.",
      packGone:
        "That pack isn't on sale any more. Here are the packs again; nothing was charged.",
      unavailable:
        "Payments aren't working right now, and nothing was charged. Try again in a little while.",
      tooMany:
        "That's a lot of tries in an hour. Wait a while, then try again. Nothing was charged.",
      orderFailed: "We couldn't start that payment. Nothing was charged.",
      windowFailed: "The payment window didn't open. Nothing was charged.",
      notHere: "Payments aren't available here. Nothing was charged.",
      // Local and CI builds only (D-761): stands in for Razorpay's window, and
      // the fake gateway's webhook pays the order. No money moves anywhere.
      standin: {
        title: "Test checkout",
        body: "This build never takes money. The fake payment gateway pays this order or fails it.",
        pay: "Payment went through",
        close: "Close without paying",
      },
      confirming: {
        title: "Confirming your payment",
        body: "This takes a few seconds.",
      },
      paid: "{velas} added to your balance",
      notPaid: {
        title: "Payment didn't go through",
        body: "The payment window closed before the payment finished. If money left your account anyway, report it below.",
        retry: "Try again",
        packs: "Choose another pack",
      },
      waiting: {
        title: "Still confirming your payment",
        body: "The payment gateway hasn't told us yet. If your payment went through, the Velas arrive as soon as it does, so there's no need to pay again: paying again buys a second pack.",
        check: "Check again",
      },
      close: "Close",
      // The man's claim (P-481, D-580): a broken payment only, the two kinds.
      claim: {
        open: "Report a problem with this payment",
        reasons: "What went wrong with this payment",
        missing_velas: "The money went through, but no Velas came",
        duplicate_charge: "I was charged twice for this purchase",
        final: "Changing your mind isn't one of these: purchases are final.",
        send: "Send",
        sentTitle: "We've got your report",
        sentBody:
          "We check what the payment gateway recorded, then add the missing Velas or refund the extra charge to the way you paid.",
        already:
          "You've already reported this payment, and we're looking at it.",
        granted: "The Velas for this payment are already in your balance.",
        notFound: "We couldn't find this payment.",
        tooMany: "You've sent a lot of reports today. Try again tomorrow.",
        failed: "We couldn't send your report. Try again.",
      },
    },
  },
  // Sign-in and onboarding (T-3.11, T-3.12). Drafted by Claude from the
  // prototype where 08-DESIGN's list of its errors leaves it trusted, and from
  // /terms and the decisions where it doesn't; for the founder's review.
  onboarding: {
    progress: "Step {step} of {total}",
    back: "Back",
    continue: "Continue",
    phone: {
      title: "What's your number?",
      sub: "We'll text a code to confirm it. Your number is never shown on your profile.",
      label: "Mobile number",
      prefix: "+91",
      placeholder: "98765 43210",
      send: "Send code",
      // Firebase builds only (T-3.14, D-081), before the number goes to
      // Google: worded as /privacy's "Your phone number and Google" (D-048).
      googleConsent:
        "By tapping Send code, you agree that Google's Firebase sends it. Google processes your number in the United States and keeps it to prevent spam and abuse.",
      googleConsentLink: "How we use your number",
    },
    code: {
      title: "Enter the code",
      sub: "Sent to +91 {phone}.",
      label: "The 6-digit code",
      verify: "Verify",
      resendIn: "Send a new code in {seconds}s",
      resend: "Send a new code",
      changeNumber: "Change number",
    },
    // D-081: a build that signs in by neither path, instead of a form that
    // can't work. Since T-3.14 every known APP_ENV has a path.
    closed: {
      title: "Sign-in isn't open yet",
      body: "{app} is getting ready. Leave your email and we'll tell you when it opens.",
      waitlist: "Join the waitlist",
    },
    birthday: {
      title: "When were you born?",
      sub: "{app} is strictly 18+.",
      label: "Date of birth",
      confirmTitle: "Is this right?",
      confirmBody:
        "You were born on {date}. Your date of birth can't be changed once it's saved.",
      confirm: "Yes, that's right",
      edit: "Change it",
      answered: "You're {age}. Your date of birth can't be changed.",
    },
    // D-072, worded as /terms and /privacy put it.
    underage: {
      title: "You need to be 18 to use {app}",
      body: "We've deleted what you gave us. We keep only a hashed copy of your phone number, so it can't sign up again.",
    },
    gender: {
      title: "I am a",
      sub: "This can't be changed later. It decides how the app works for you.",
      man: "Man",
      manNote: "You'll buy Velas to open threads",
      woman: "Woman",
      womanNote: "Everything is free, always",
      lock: "Locked permanently after signup. This is what keeps fake accounts out.",
      answeredMan: "You signed up as a man. This can't be changed.",
      answeredWoman: "You signed up as a woman. This can't be changed.",
    },
    lookingFor: {
      title: "Who are you here to meet?",
      showMe: "Show me",
      women: "Women",
      men: "Men",
      everyone: "Everyone",
      intents: "I'm looking for",
      intentsHelp: "Pick up to 3.",
    },
    name: {
      title: "Name and hometown",
      sub: "Both places matter: people connect over hometowns as much as neighbourhoods.",
      firstName: "First name",
      firstNamePlaceholder: "Rohit",
      hometown: "Hometown, where you're from",
      hometownPlaceholder: "Amritsar",
      city: "Where you live now",
      cityPlaceholder: "Phagwara",
    },
    // The location question (T-4.10, D-220). What others see is /privacy's
    // own promise, word for word in substance (D-034): a distance, rounded.
    location: {
      title: "Where are you?",
      sub: "We use your location to show you people nearby. Other people see only a distance, rounded to the kilometre.",
      share: "Share my location",
      pickInstead: "Pick my area instead",
      isSet:
        "Your location is set. Share it again, or pick your area, to change it.",
      keep: "Keep it as it is",
      pickTitle: "Pick your area",
      pickSub:
        "Where you live. Distances to you are measured from the middle of it.",
      areas: "Areas",
      useLocation: "Use my location instead",
      noAreas: "There are no areas to pick from yet.",
      areasFailed: "We couldn't load the areas.",
      // Why the picker shows instead: the browser said no, or couldn't say,
      // or the server refused the position (outside India, D-220).
      why: {
        denied:
          "Location is off for {app} in this browser, so pick your area instead.",
        unavailable:
          "We couldn't find your location, so pick your area instead.",
        timeout:
          "Finding your location took too long, so pick your area instead.",
        outside: "That location is outside India, so pick your area instead.",
      },
    },
    username: {
      title: "Pick a username",
      sub: "This becomes your public page. Share it and anyone can find you.",
      label: "Username",
      placeholder: "rohit_a",
      help: "4 to 20 of a–z, 0–9, dots and underscores.",
      page: "Your page: {url}",
      checking: "Checking…",
      available: "That one's free.",
      taken: "That one's taken.",
      suggestion: "Try {name}",
    },
    about: {
      title: "Introduce yourself",
      sub: "A few honest lines beat a clever one-liner.",
      label: "About you",
      placeholder: "What you do, what you're into, who you'd like to meet…",
      moreNeeded: "{count} more characters",
    },
    // The photos step (T-4.6), from the prototype's; the per-photo states and
    // reasons are Claude's, for the founder's review. No reason accuses the
    // person: a possible minor reads as `other`, D-093's own words, and so does
    // any reason not listed here (D-096).
    photos: {
      title: "Add your photos",
      // D-392 (T-4.12): nobody needs a public photo, and none needs a face.
      sub: "Add as many as you like, or none. Nothing here has to show your face. Every photo is checked before it goes live.",
      grid: "Your photos",
      add: "Add a photo",
      slot: "Photo {n}",
      main: "Main",
      uploading: "Uploading {percent}%",
      checking: "Checking…",
      approved: "Approved",
      remove: "Remove photo {n}",
      dismiss: "Clear photo {n}",
      moveEarlier: "Move photo {n} earlier",
      moveLater: "Move photo {n} later",
      chooseAnother: "Choose another",
      tryAgain: "Try again",
      loadFailed: "We couldn't load your photos.",
      privateAlbum:
        "You can add a private album later. Nobody sees it unless you approve them, and you can take access back any time.",
      // The face photo (T-4.12, D-391): the one the selfie is compared with,
      // private unless she chooses to show it. "Face photo" says what it is
      // and claims nothing (D-262; the advisor's recommendation, the
      // founder's choice, 8 October 2026). Never the API's own word for it.
      face: {
        title: "Your face photo",
        subWoman:
          "Needed for the selfie check, and only for that. Nobody sees it unless you choose to show it.",
        subMan:
          "Optional, and only for the selfie check if you take it. Nobody sees it unless you choose to show it.",
        slot: "Face photo",
        add: "Add your face photo",
        replace: "Change your face photo",
        needOne: "Add your face photo to continue",
        show: "Also show it on my profile",
        showHint:
          "It goes in the next free place and is checked like any photo. Switch it off to take it down.",
        locked: "It can't change now that your selfie has matched it.",
        checking: "Checking your face photo…",
        approved: "Face photo approved",
        // The toggle's refusals (`NOT_ALLOWED`): the six places are full, or
        // the photo isn't approved yet.
        noRoom: "Remove a photo to make room first.",
        notYet: "Your face photo has to be approved first.",
      },
      // Why a photo isn't on the profile: the API's `reject_reason`, or what
      // went wrong on the way up. Each says what to do next.
      reasons: {
        unsupported_format:
          "We can't use this file — choose a JPEG, PNG or WebP photo",
        too_large: "This photo is over 8 MB — choose a smaller one",
        abandoned: "This upload didn't finish — try again",
        nudity: "This photo can't go on your profile — try a different one",
        // Only the face photo is refused for this (D-392): a public photo
        // needn't show a face.
        no_face:
          "We couldn't find a face in this photo — try one that shows yours clearly",
        text_overlay:
          "Photos with text over them can't be used — try one without",
        // D-093's wording, fixed: a possible minor, and anything unlisted.
        other: "We couldn't verify this photo — try a different one",
        network:
          "This photo didn't upload — check your connection and try again",
      },
    },
    interests: {
      title: "What are you into?",
      sub: "Pick 5. {count}/5 chosen.",
    },
    pin: {
      setTitle: "Set a 4-digit PIN",
      // What the lock does (T-3.10): on every open of a session it restores,
      // and after this many minutes hidden. Not after a sign-in by code.
      setSub:
        "You'll enter it when you open {app}, and when you come back after {minutes} minutes away.",
      confirmTitle: "Confirm your PIN",
      confirmSub: "Type it once more so we know it stuck.",
      mismatch: "Those PINs didn't match. Try again.",
      skip: "Skip, I'll set it later",
      answered: "Your PIN is set.",
    },
    // The selfie (T-4.7). D-262: it says what is done, the selfie compared
    // with the face photo (D-391, T-4.12), and never that a person is
    // verified, real or live; claims.test.ts holds every line here to that.
    selfie: {
      title: "Quick selfie check",
      // Women can't skip it (D-008); for men it's optional.
      subWoman:
        "Needed before your profile goes live. We compare your selfie with your face photo.",
      subMan: "Optional. We compare your selfie with your face photo.",
      // /privacy's words (D-262): "our team may look" is literally true
      // (D-264), and stays.
      private:
        "Other people on {app} never see your selfie. Our team may look at it to check a comparison.",
      // T-8.11 (D-470, D-530): a toast as a new man finishes, the number
      // his balance from the API, never written here. The founder's
      // approval, 8 October 2026, of Claude's draft.
      welcome: {
        one: "{count} Vela is in your wallet, to start you off.",
        other: "{count} Velas are in your wallet, to start you off.",
      },
      intro: "We'll open your front camera",
      openCamera: "Open camera",
      skip: "Skip for now",
      opening: "Opening your camera…",
      preview: "Your camera",
      // No pose is asked (T-4.5, D-263): the prototype's "Turn your head
      // slightly left" is gone.
      frame:
        "Face the camera in good light, with your whole face in the frame.",
      take: "Take selfie",
      cancel: "Cancel",
      captured: "Your selfie",
      reviewHint:
        "Check that your face is clear and in focus. Each selfie you send uses one of today's tries.",
      use: "Use this selfie",
      retake: "Retake",
      sending: "Sending your selfie… {percent}%",
      sendFailed:
        "Your selfie didn't send — check your connection and try again.",
      // D-261: what is happening, never a bare spinner; after about 15
      // seconds, that it can take a minute and she can leave.
      comparing: "Comparing your selfie with your face photo…",
      comparingLong:
        "This can take up to a minute. You can leave this page — your result will be here when you come back.",
      comparingStill:
        "Still comparing. Come back in a few minutes — your result will be waiting here.",
      checkAgain: "Check again",
      matched: "Your selfie matched your face photo.",
      // "Continue" and "Skip for now" finish sign-up (T-4.8, D-310); when the
      // server says something is still needed, the first thing it names, with
      // the way back to its screen.
      finish: {
        missing: {
          seeking: "Say who you're looking for first.",
          profile: "Add your name, hometown and city first.",
          location: "Add your location first.",
          username: "Choose a username first.",
          about: "Write a few lines about yourself first.",
          interests: "Pick your 5 interests first.",
        },
        incomplete: "Something on your profile isn't finished yet.",
        needsMatch:
          "Your selfie has to match your face photo before you can finish.",
        goThere: "Take me there",
      },
      triesOne: "1 try left today.",
      triesMany: "{count} tries left today.",
      triesNone: "No tries left today.",
      // RATE_LIMITED's retry_after_s: the day's five, or too many starts.
      waitMinutes:
        "You can't send another selfie yet. Try again in about {minutes} minutes.",
      waitHours:
        "You can't send another selfie yet. Try again in about {hours} hours.",
      loadFailed: "We couldn't load your selfie check.",
      goToPhotos: "Go to your photos",
      // Why a selfie didn't match (D-263's list): what to change, never an
      // accusation. Anything unlisted reads as `other`.
      reasons: {
        no_face:
          "We couldn't find a face in your selfie. Face the camera in good light, with your whole face in the frame, and try again.",
        many_faces:
          "We found more than one face. Take your selfie with only you in the frame.",
        no_match:
          "Your selfie didn't match your face photo closely enough. Try again facing the camera in good light, or add a clearer face photo.",
        no_photos:
          "Your face photo isn't ready to compare with: it may still be being checked, or it was refused. Add one that shows your face clearly, then take your selfie.",
        unreadable: "We couldn't read that picture. Take your selfie again.",
        unavailable:
          "We couldn't compare your selfie just now. Try again in a few minutes.",
        other: "We couldn't use this selfie. Try again.",
      },
      // Why the camera didn't open (src/lib/camera.ts), and what to do. Where
      // each browser keeps a site's camera permission, from its own help
      // pages, read 5 October 2026: Chrome Help "Use your camera and
      // microphone in Chrome" (Android and computer), Mozilla's "How to
      // manage your camera and microphone permissions with Firefox", and
      // Apple's Safari User Guide for Mac, "Change Websites settings". The
      // iPhone's steps are Safari's own menus (aA, Website Settings), as
      // help pages beyond Apple's describe them: Apple's guide page didn't
      // show them when read.
      camera: {
        denied: "Your camera is blocked for {app}.",
        how: {
          ios: "In Safari, tap aA in the address bar, then Website Settings, and set Camera to Allow. In another browser, open the Settings app, find that browser and turn on Camera. Then tap Try again.",
          "chrome-android":
            "Tap ⋮ to the right of the address bar, then Settings, Site settings and Camera. Find {host} under Blocked, tap it and choose Allow. Then come back and tap Try again.",
          "chrome-desktop":
            'Open ⋮ at the top right, then Settings, Privacy and security, Site settings and Camera. Under "Not allowed to use your camera", choose {host} and set it to Allow. Then click Try again.',
          "safari-mac":
            "Choose Safari > Settings, click Websites, then Camera, and set {host} to Allow. Then click Try again.",
          firefox:
            "Click the permissions icon at the left of the address bar, then the ✕ beside Blocked to clear it. Then click Try again and allow the camera.",
          other:
            "Allow the camera for {host} in your browser's settings, then tap Try again.",
        },
        none: "We couldn't find a camera. Use a phone or computer with a front camera.",
        busy: "Your camera is in use by another app. Close it, then try again.",
        unsupported:
          "This browser can't open a camera here. Open {app} in Chrome or Safari and try again.",
        other: "Your camera didn't open. Try again.",
      },
    },
  },
  // What the API's error codes say on screen (T-3.11). A code the screen
  // doesn't expect falls back to `unknown`.
  // Notifications (T-9.4): what a push and the in-app list say for each kind,
  // the settings, and asking for permission after the first match. The API
  // sends a kind and ids, never words (D-033); with "Hide names" on, no name.
  // Nothing here tells her of an hour or an expiry (P-460): a Thread running
  // out reaches only him, and its setting is shown only to him. Drafted by
  // Claude, for the founder's review.
  notifications: {
    title: "Notifications",
    open: "Notifications",
    empty: "Nothing yet",
    emptyBody: "Matches, gifts and requests show up here.",
    failed: "We couldn't load your notifications.",
    unread: "Unread",
    kinds: {
      match: {
        named: "You and {name} matched.",
        plain: "You have a new match.",
      },
      thread: {
        named: "{name} started a Thread with you.",
        plain: "Someone started a Thread with you.",
      },
      message: {
        named: "New message from {name}.",
        plain: "You have a new message.",
      },
      like: { named: "{name} liked you.", plain: "Someone liked you." },
      superLike: {
        named: "{name} Super Liked you.",
        plain: "Someone Super Liked you.",
      },
      gift: { named: "{name} sent you a gift.", plain: "You received a gift." },
      albumRequest: {
        named: "{name} asked to see your private pictures.",
        plain: "Someone asked to see your private pictures.",
      },
      albumGranted: {
        named: "{name} said yes: you can see the private pictures.",
        plain: "Your request to see private pictures was accepted.",
      },
      albumDeclined: {
        named: "{name} said no to your request.",
        plain: "Your request to see private pictures was declined.",
      },
      knotRequested: {
        named: "{name} wants to tie the knot.",
        plain: "Someone wants to tie the knot.",
      },
      knotAccepted: {
        named: "You and {name} tied the knot.",
        plain: "You tied the knot.",
      },
      threadExpiring: {
        named: "A Thread of yours is about to run out.",
        plain: "A Thread of yours is about to run out.",
      },
      lowBalance: {
        named: "Your Velas are running low.",
        plain: "Your Velas are running low.",
      },
      other: {
        named: "Something new on {app}.",
        plain: "Something new on {app}.",
      },
    },
    settings: {
      title: "Notifications",
      device: "Notifications on this device",
      deviceOn: "On: this browser gets them.",
      deviceOff: "Off: this browser gets none.",
      blocked:
        "Notifications are blocked for {app} in this browser. Allow them in the browser's site settings, then come back.",
      unavailable: "Notifications aren't available in this browser.",
      iosInstall:
        "On iPhone, notifications need {app} on your Home Screen: tap Share, then Add to Home Screen, and open it from there.",
      kindsTitle: "Tell me about",
      match: "New matches",
      message: "Threads and messages",
      like: "Likes",
      gift: "Gifts",
      album: "Private pictures",
      albumHint: "Requests to see them, and answers to yours.",
      knot: "Knots",
      expiry: "A Thread about to run out",
      balance: "Velas running low",
      genericText: "Hide names",
      genericTextHint: "Say “New message” instead of who it's from.",
      listHint: "Turned off, it still shows in your notifications here.",
      saveFailed: "We couldn't save that. Try again.",
      failed: "We couldn't load your notification settings.",
      turnOnFailed: "We couldn't turn notifications on. Try again.",
    },
    ask: {
      title: "Know when they write back",
      body: "Turn on notifications for messages, matches and requests. You can change this in You.",
      turnOn: "Turn on",
      notNow: "Not now",
    },
    you: {
      settings: "Notification settings",
      list: "Your notifications",
    },
  },
  apiErrors: {
    unknown: "Something went wrong. Try again.",
    network: "We couldn't reach {app}. Check your connection and try again.",
    invalid: "Check what you entered.",
    phoneNotSupported: "Only Indian mobile numbers can sign in for now.",
    rateLimited: "Too many tries. Wait a moment, then try again.",
    providerUnavailable:
      "We couldn't send a code just now. Try again in a few minutes.",
    otpInvalidOne: "That code isn't right. 1 try left.",
    otpInvalidMany: "That code isn't right. {count} tries left.",
    otpExpired: "That code has expired. Send a new one.",
    otpTooMany: "Too many wrong codes. Wait a while, then send a new one.",
    // Firebase's answers on Path A (T-3.14), and our API's to its token.
    // Firebase says nothing of tries left, so neither do these.
    codeInvalid: "That code isn't right.",
    firebaseTooMany: "Too many tries. Wait a while, then try again.",
    codesUnavailable: "We can't send codes right now. Try again later.",
    captchaFailed:
      "We couldn't check this browser. Reload the page and try again.",
    firebaseTokenInvalid: "That sign-in didn't work. Send a new code.",
    // Decision 16: neutral, with a way to reach a person. P-51 may change it.
    cantSignIn: "This account can't sign in.",
    contact: "Contact us",
    immutable: "This can't be changed now.",
    usernameTaken: "That username is taken.",
    // The photos step's exit, refused (T-4.12): the server's rule, said here.
    facePhotoRequired: "Add your face photo first.",
    fields: {
      phone: "Enter a 10-digit Indian mobile number.",
      otp: "Enter the 6-digit code.",
      dob: "Enter a real date of birth.",
      first_name: "Use letters only, with single spaces.",
      hometown: "Use up to 40 characters.",
      city: "Use up to 40 characters.",
      username: "Use 4 to 20 of a–z, 0–9, dots and underscores.",
      intent_ids: "Pick 1 to 3.",
      about: "Leave out links and phone numbers.",
      interest_ids: "Pick exactly 5.",
      // D-069's refusals: one digit four times, runs, pairs, the common ones.
      pin: "That PIN is too easy to guess. Pick another.",
    },
  },
  // The intents catalogue, by id (P-25, D-041). The screen shows these, never the
  // database's label (P-26), which stays the fallback for an id not listed here.
  intents: {
    "1": "Something serious",
    "2": "Long term",
    "3": "Situationship",
    "4": "Casual dating",
    "5": "Just one night",
    "6": "No strings attached",
    "7": "Open relationship",
    "8": "Discreet",
    "9": "Friendship",
    "10": "Go with the flow",
  },
  // The interests catalogue, by id (T-1.14), shown like the intents (P-26).
  interests: {
    "1": "Filter coffee",
    "2": "Trekking",
    "3": "Indie music",
    "4": "Pottery",
    "5": "Dogs",
    "6": "Cats",
    "7": "Old Hindi cinema",
    "8": "Badminton",
    "9": "Street food",
    "10": "Sketching",
    "11": "Reading",
    "12": "Yoga",
    "13": "Baking",
    "14": "Gaming",
    "15": "Anime",
    "16": "Running",
    "17": "Photography",
    "18": "Cricket",
    "19": "Travel",
    "20": "Startups",
    "21": "Cooking",
    "22": "Hopeless romantic",
    "23": "Yapper",
    "24": "Yearner",
  },
  // The PIN lock (T-3.10, D-069): a deterrent, so its words don't promise more.
  lock: {
    title: "Enter your PIN",
    locked: "{app} is locked",
    wrongOne: "Wrong PIN. 1 try left.",
    wrongMany: "Wrong PIN. {count} tries left.",
    resetRequired:
      "Your PIN can't be checked. Sign out, sign in again with your number, and set a new one.",
    tooFast: "Too many tries. Wait a minute, then try again.",
    failed: "We couldn't check your PIN. Check your connection and try again.",
    forgot: "Forgot your PIN? Sign out",
  },
  // Thread and Knot are product nouns, not the brand: a rename changes {app}
  // and nothing else here (CLAUDE.md rule 17).
  landing: {
    getStarted: "Get started",
    // headlineThreads ("an hour"), intro and features.threads.title ("1-hour")
    // promise app_config.thread_hours, 1 since T-7.6 (D-097). Copy, not a
    // computation, so it's written out rather than read: change it with the
    // setting (T-2.1). The headline is also baked into the share image's
    // pixels: change it, and regenerate src/app/opengraph-image.jpg and its alt
    // text (T-2.4, 08-DESIGN §7). A test fails until the alt text matches.
    headlineThreads: "Threads last an hour.",
    headlineKnots: "Knots last.",
    intro:
      "Meet people nearby. Every conversation starts as a 1-hour thread. If you both want to keep it, you tie the knot and it becomes permanent.",
    join: "Join {app}",
    ageNote: "18+ only · Free for women, always",
    features: {
      threads: {
        title: "1-hour threads",
        body: "No dead matches sitting for weeks. Talk, or it goes.",
      },
      knot: {
        title: "Tie the knot",
        body: "Both of you choose to keep it. Then it never expires.",
      },
      // D-262: what is done, never a guarantee. Selfies are compared with the
      // photos, not "verified" (D-260: the threshold is unmeasured). Reports
      // aren't named until removing someone on one is built (T-9.1, T-9.5).
      safety: {
        title: "Checked and moderated",
        body: "Selfies compared with a face photo, and every photo checked.",
      },
    },
    // The waitlist box (T-2.3), for people outside the launch city. Its city is
    // optional and tells us where demand is, the input to choosing a second
    // city; /privacy says both uses (legal.privacy.collect.waitlist).
    // Two different people (D-081's flag, the founder's copy): while nobody can
    // sign in anywhere, the box mustn't suggest it works somewhere else.
    waitlist: {
      closedTitle: "{app} isn't open yet",
      closedBody: "Leave your email and we'll tell you the day it is.",
      // The launch city is D-013's; change it with the decision.
      title: "Not in your city yet?",
      body: "We're starting in Phagwara. Leave your email and we'll tell you when we reach you.",
      email: "Email",
      emailPlaceholder: "you@email.com",
      city: "Your city (optional)",
      join: "Join",
      joined: "You're on the list",
      privacyNote: "We use these only for the waitlist.",
      privacyLink: "Privacy policy",
      invalidEmail: "Enter an email address, like you@email.com.",
      rateLimited: "Too many tries. Wait a minute, then try again.",
      failed: "That didn't go through. Check your connection and try again.",
    },
    footer: {
      label: "Legal and contact",
      terms: "Terms",
      privacy: "Privacy",
      refunds: "Refunds",
      contact: "Contact",
      // {city}, {country}: the registered office's town, read from the same
      // record Contact shows in full (src/lib/legal.ts, D-058), never written
      // separately. Not the launch city: the two differ on purpose.
      copyright: "© {year} {app} · {city}, {country}",
    },
  },
  // The legal pages (T-2.2), written in plain language from our own decisions.
  // Each paragraph's comment names what it states: change that, change this.
  // Facts we don't have yet live in src/lib/legal.ts and show as toBeConfirmed;
  // production can't build while one is missing (D-053).
  legal: {
    back: "Back",
    notFinal:
      "This page isn't final yet: details marked “To be confirmed” are still to come.",
    toBeConfirmed: "To be confirmed",
    // Labels for who runs the app and where notice goes, on Terms and Contact.
    // "Run by", not "Company": a sole proprietorship isn't one (D-058).
    facts: {
      runBy: "Run by",
      office: "Registered office",
    },
    links: {
      terms: "Read our terms and conditions",
      privacy: "Read our privacy policy",
      refunds: "Read our refund policy",
      contact: "See our contact page",
    },
    terms: {
      title: "Terms and conditions",
      intro:
        "These are the rules for using {app}: how it works, what it costs, and what you and we can expect.",
      whoWeAre: {
        title: "Who we are",
        // P-0.2: Terms names the business it binds, directly (D-058).
        body: "These terms are an agreement between you and the business that runs {app}:",
      },
      whoCanJoin: {
        title: "Who can use {app}",
        // D-009; one account per number: D-035.
        body: "You must be 18 or older. If you give a date of birth under 18, we refuse the sign-up and bar that phone number from signing up again. Your account is tied to your phone number: one number, one account.",
      },
      conversations: {
        title: "Threads and Knots",
        // D-003, D-097; reopening and Extend: D-098, D-253. "lasts an hour"
        // promises app_config.thread_hours, 1 since T-7.6, and "extended by a
        // day" thread_extend_hours, 24: change it with the setting.
        body: "Every conversation starts as a Thread, which lasts an hour. If you both tap “Tie the knot”, it becomes a Knot: permanent, and free for both of you, forever. Only the other person can make a conversation permanent; it can never be bought. A Thread that runs out is kept, read-only, and can be reopened, or extended by a day, for the price shown before you pay.",
      },
      paying: {
        title: "Paying",
        // D-002, D-004, D-049.
        prices:
          "Women never pay for anything on {app}. Men pay for some things, like opening a Thread, in Velas: the unit of paid balance on {app}. The price is always shown before you pay, and prices can change.",
        // D-005, D-026, D-050.
        velas:
          "You buy Velas in packs, and they reach your balance once your payment is confirmed. Velas never expire. They have no cash value, and they can't be transferred or given to another account.",
      },
      profile: {
        title: "Your profile",
        // D-008, D-012, D-391; the selfie in D-262's words: what is done, no
        // guarantee.
        body: "You choose your gender once, when you sign up, and you can't change it later. Before a woman's profile goes live, she adds a photo of her face that nobody sees unless she chooses, and takes a selfie, which we compare with it; for men both are optional. You can lock {app} on your device with a 4-digit PIN. After 5 wrong tries we sign you out, and you sign back in with your phone number.",
      },
      safety: {
        title: "Safety",
        // D-030. "first 20 messages" promises app_config.mask_first_n_messages,
        // seeded 20: change it with the setting.
        messages:
          "In a Thread's first 20 messages, we hide phone numbers, email addresses, UPI IDs and social media handles. We refuse messages that are abusive or that ask for money.",
        // Blocks: 06-TESTING's never-skip list (T-9.1). Reports and freezes: D-031.
        reports:
          "You can report or block anyone. A block works both ways: neither of you sees the other anywhere in {app}. Reports go to our moderators, who can freeze or remove an account, and three reports from different people within a day freeze an account straight away.",
      },
      promises: {
        title: "What we promise",
        // D-007, D-037.
        body: "We never run fake profiles. There are no public ratings or reviews of people: the only notes people leave each other are kudos, short positive notes that the person who receives them decides whether to show. And we never hide your profile to push you towards paying.",
      },
      screenshots: {
        title: "Screenshots",
        // D-011.
        body: "We can't stop screenshots on the web. Photos in a private album carry the viewer's username on the image, so a screenshot shows whose it was.",
      },
      chats: {
        title: "Your chats",
        // D-006; deleting an account: D-051, on the privacy page.
        body: "Clearing a chat removes it from your list only. The other person keeps their copy, and we keep the messages so that reports can be checked. What happens when you delete your account is on our privacy page.",
      },
      law: {
        title: "Law and courts",
        // D-052, with D-058's court: the first thing P-0.7's review checks.
        body: "These terms are governed by the laws of India. Any dispute goes to the court named below.",
        court: "The court",
        // D-058. It discloses a right that exists whether we mention it or not;
        // without it, the clause reads as though a user must come to Bihar to
        // complain. Neither the founder nor Claude is a lawyer: if the terms are
        // ever reviewed properly, show this line to one (P-0.7).
        consumers:
          "If you're a consumer, you can still take a complaint to the Consumer Commission where you live, under the Consumer Protection Act, 2019.",
      },
      questions: {
        title: "Questions and complaints",
        body: "Our contact page has our address, our support email and our Grievance Officer.",
      },
    },
    privacy: {
      title: "Privacy policy",
      intro:
        "This page says what {app} collects about you, where it's kept, who else handles it, and what happens when you delete your account.",
      google: {
        // D-035, D-048. First and plain on purpose: the least comfortable fact
        // on the page is the one a reader must not discover later.
        title: "Your phone number and Google",
        body: "To send your sign-in code we use Google's Firebase. Google processes your phone number in the United States and keeps it to prevent spam and abuse across its services. We can't delete Google's copy, even if you delete your account.",
      },
      collect: {
        title: "What we collect, and why",
        // D-035; never in logs: CLAUDE.md rule 15.
        phone:
          "Your phone number, to sign you in: it is your account. We store it hashed and encrypted, it's never shown to other people, and it never appears in our logs.",
        // D-009; hiding your age: D-010.
        birth:
          "Your date of birth, to make sure you're 18 or older. Other people see your age, and you can hide it.",
        // D-008, D-041.
        gender:
          "Your gender and who you want to meet, to show you the right people.",
        // D-010; the public page: T-6.x's `@username` page.
        profile:
          "Your profile: your name, where you live and where you're from, your photos, your interests, what you're looking for and what you write about yourself. Other people see it, which is what a profile is for. Your username also gives you a public page that anyone can see, with your first name, age, city and main photo.",
        // D-034; hiding your distance: D-010.
        location:
          "Your location, to show you people nearby. Other people see only a distance, rounded to the kilometre and never less than 1 km, and you can hide it. If you don't share your location, you pick your area instead.",
        // D-027, D-028; no hidden data: CLAUDE.md rule 15.
        photos:
          "Your photos. We re-encode every photo you upload, which removes hidden data such as where it was taken, and we check each one before it goes live.",
        // D-391 (T-4.12): the one photo kept for the check, and why.
        facePhoto:
          "A photo of your face, which we keep only for the selfie check. Nobody sees it unless you choose to show it on your profile. We keep it so that the photos other people see need not show your face.",
        // D-008, D-262, D-393; never public: 06-TESTING's never-skip list. "Our
        // team may look at it" is literally true and must stay: the founder
        // looks at every comparison until it is measured (D-264, P-160).
        selfie:
          "Your selfie, which we compare with your face photo, and with the photos on your profile that show a face. Other people on {app} never see it; our team may look at it to check a comparison.",
        // D-006, D-030. "first 20 messages" promises
        // app_config.mask_first_n_messages, seeded 20: change it with the setting.
        messages:
          "Your messages and voice notes. We keep them even when you clear a chat, so that reports can be checked. In a Thread's first 20 messages, phone numbers, email addresses, UPI IDs and social media handles are hidden from the other person; we keep the original so that moderators can see it.",
        // D-860 (T-9.1): a lifted block is kept, as "blocked by many" is a
        // moderation signal. Silent: D-862.
        blocks:
          "Who you block and report, for our moderators. We keep a block on record after you undo it, and nobody is ever told who blocked or reported them.",
        // D-026, D-021.
        payments:
          "Your payments. Razorpay handles the payment itself. We keep a record of every payment and a permanent history of your Velas.",
        // T-2.3: the landing page's waitlist box, before anyone has an account.
        waitlist:
          "If you join the waitlist: your email and, if you give it, your city. We use them only to tell you when {app} opens near you and to see where people want it next, and we share them with no one. Ask us through the contact page to take you off the list.",
      },
      where: {
        title: "Where your data is",
        // D-048, as amended on 1 October 2026. R2's location is only a hint,
        // so never name a region for Cloudflare.
        database:
          "Your profile, messages, Velas, payment records and our hashed, encrypted copy of your phone number are stored in Mumbai, India.",
        // T-2.3: the waitlist table is in the same database.
        waitlist:
          "If you joined the waitlist, your email and city are stored in Mumbai, India, too.",
        // P-0.3: one Zoho Mail user in its India data centre (D-048 holds).
        mail: "If you write to our support or grievance address, your email is kept by Zoho, in India.",
        servers:
          "Every request you make is handled by our servers in Singapore.",
        media:
          "Your photos, face photo, selfie, voice notes and private album are stored by Cloudflare, outside India.",
        // Deleted after the check: Sightengine's default, which T-4.4 must
        // never leave (its constraint, and P-71's).
        moderation:
          "Photos are checked by Sightengine, on servers in the United States or Europe, and deleted there after the check.",
        // D-087, D-088: on our own servers, no third party.
        faceMatch:
          "Your selfie is compared with your face photo and your photos on our own servers, not by any other company.",
        phone:
          "Your phone number is also handled by Google, in the United States, as described above.",
      },
      others: {
        title: "Who else handles your data",
        // D-023, D-026, D-027, D-028, D-035, D-048.
        // P-0.3: Zoho holds every support and grievance email.
        // T-9.4: the push services, if you turn notifications on (D-857).
        body: "Google (sign-in codes), Razorpay (payments), Sightengine (photo checks), Cloudflare (storing photos and voice notes), Supabase (our database), Upstash (our cache), Fly.io (our servers), Vercel (our website), Zoho (our support and grievance email) and, if you turn on notifications, your browser's maker (delivering them).",
      },
      // T-9.4 (D-857): what a push carries and who delivers it. The services
      // are outside India; what they carry is encrypted for your browser alone.
      push: {
        title: "Notifications",
        body: "If you turn on notifications, your browser's maker delivers them: Google for Chrome and Android, Apple for Safari on iPhone, iPad and Mac, Mozilla for Firefox, and Microsoft for Edge, from their servers outside India. Each notification is encrypted so that only your browser can read it. It says what happened, which person or Thread it's about, and that person's first name, unless you turn on Hide names. It never carries a message's text. The browser's maker sees only that a notification was sent to your browser, and when.",
        choices:
          "Turn them off, or choose which ones you get, in You, under notification settings, or in your browser's settings. Paused accounts get none.",
      },
      cookies: {
        title: "Cookies",
        // D-024.
        body: "We use cookies only to keep you signed in.",
      },
      choices: {
        title: "Your choices",
        // D-010, T-9.6; the copy's 24 hours: D-502.
        body: "In your settings you can hide your profile, your age or your distance, pause your account, download a copy of your data, or delete your account. A copy of your data is a file you can download for 24 hours; then we delete it.",
      },
      deletion: {
        title: "Deleting your account",
        // D-051; the timing: D-500, whose daily job erases on day 29 or 30.
        erased:
          "When you delete your account, your profile disappears straight away and you're signed out everywhere. Within 30 days we erase your profile, your photos, your private album and everything else other people can see of you, except your messages.",
        // D-500: signing in again before the erasure restores the account. 29,
        // not 30: the job may erase on day 29.
        restore:
          "Changed your mind? Sign in again within 29 days and your account comes back as it was.",
        messages:
          "Your messages stay in the other person's chat, shown as from “Deleted account”, and we keep them as moderation records. Otherwise, deleting an account could be used to destroy evidence someone has reported.",
        // D-051; the welcome Velas: D-470, T-8.11; a block: D-861 (T-9.1).
        kept: "We also keep your history of Velas and payments, any reports and moderation records about you, and a hashed copy of your phone number, so that deleting an account can't be used to escape a ban, a report or someone's block, or to collect the welcome Velas again.",
        // D-504 (the founder, 8 October 2026); /refunds says it too.
        velas:
          "Velas left in your balance are lost when your account is erased: they have no cash value, and we don't refund them. Sign in again before then and they come back with your account.",
        google:
          "Google's copy of your phone number stays with Google, as described above.",
      },
      children: {
        title: "Under-18s",
        // D-009; everything else deleted at once: D-072.
        body: "{app} is only for people aged 18 and over. If someone gives a date of birth under 18, we refuse the sign-up and delete the account and everything in it at once. We keep only a hashed copy of the phone number, so that it can't sign up again.",
      },
      grievance: {
        title: "Questions and complaints",
        // D-052: the IT Rules' timelines exactly, and nothing faster.
        body: "Our Grievance Officer handles questions and complaints about your data. We acknowledge every complaint within 24 hours and resolve it within 15 days.",
        officer: "Grievance Officer",
        email: "Email",
      },
    },
    refunds: {
      title: "Refund policy",
      intro:
        "This page covers your money and your Velas: when a purchase is final, what happens to the Velas you spend, and when we fix a payment.",
      // D-050 for the first and third sections; D-230 for the second: there is
      // no product refund, so nothing comes back on a ban or a declined request
      // (P-130 replaced "When Velas come back on their own" with it).
      final: {
        title: "Purchases are final",
        body: "When you buy Velas, the purchase is final. We don't refund it if you change your mind, whether or not you've spent them.",
      },
      spent: {
        title: "Velas you spend are spent",
        // D-230. The ledger reasons that once served these two returns stay
        // unused (the labels at the top of this file).
        body: "Once you spend Velas, they're spent. They don't come back if the person you spent them on is later banned from {app}, and they don't come back if someone declines your request to see their private album. The price is always shown before you spend.",
      },
      // D-504 (the founder, 8 October 2026); /privacy says it too.
      deleted: {
        title: "Deleting your account",
        body: "If you delete your account, the Velas left in your balance are lost once it's erased, within 30 days. We don't refund them. Sign in again within 29 days and your account comes back, Velas included.",
      },
      broken: {
        title: "A broken payment is ours to fix",
        body: "If your payment went through but the Velas never reached your balance, or you were charged twice for one purchase, that isn't a change of mind: something went wrong on our side, and we fix it. We add the missing Velas, or refund the extra charge to the way you paid.",
        write: "Write to us with the payment details.",
        support: "Support email",
      },
    },
    contact: {
      title: "Contact and grievances",
      intro: "Who runs {app}, how to reach us, and who handles complaints.",
      details: "Our details",
      support: "Support",
      grievanceOfficer: "Grievance Officer",
      grievanceEmail: "Grievance Officer's email",
      // D-052.
      timelines:
        "We acknowledge every complaint within 24 hours and resolve it within 15 days.",
    },
  },
  ui: {
    close: "Close",
    loading: "Loading",
    remove: "Remove {label}",
    counter: "{count}/{max}",
    online: "Online",
    // The badge (D-262, D-393): what was done, never "verified". The selfie
    // matched the face photo, and the main photo's face matched the selfie
    // (D-910); one line for both genders (the founder, 8 October 2026).
    selfieMatched: "Selfie matched",
    errorTitle: "Something went wrong",
    retry: "Try again",
    pinProgress: "{count} of {max} digits entered",
    pinDelete: "Delete",
    otpDigit: "Digit {n} of {total}",
    // A Thread's time left (Countdown, 08-DESIGN §8): "Ran out", never
    // "Expired" (§4's example is the 24-hour Thread's).
    countdown: {
      hours: "{hours}h left",
      minutes: "{minutes}m left",
      out: "Ran out",
    },
  },
} as const;
