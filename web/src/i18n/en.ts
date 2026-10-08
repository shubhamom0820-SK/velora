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
    discover: "Discover",
    chats: "Chats",
    you: "You",
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
    // Until T-8.7 builds the store. Says plainly that buying hasn't started,
    // with no promise of when (the advisor directing T-5.5, relayed by the
    // founder, 5 October 2026).
    store: {
      title: "Buy Velas",
      body: "Buying Velas hasn't started on {app} yet. Until it does, there's no way to add Velas to your balance.",
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
    // headlineThreads ("a day"), intro and features.threads.title ("24-hour")
    // promise app_config.thread_hours, seeded 24. Copy, not a computation, so
    // it's written out rather than read: change it with the setting (T-2.1).
    // The headline is also baked into the share image's pixels: change it, and
    // regenerate src/app/opengraph-image.png and its alt text (T-2.4,
    // 08-DESIGN §7). A test fails until the alt text matches.
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
        // D-003; reopening price: D-004. "lasts a day" promises
        // app_config.thread_hours, seeded 24: change it with the setting.
        body: "Every conversation starts as a Thread, which lasts a day. If you both tap “Tie the knot”, it becomes a Knot: permanent, and free for both of you, forever. Only the other person can make a conversation permanent; it can never be bought. A Thread that runs out is kept, read-only, and can be reopened for the price shown before you pay.",
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
        body: "Google (sign-in codes), Razorpay (payments), Sightengine (photo checks), Cloudflare (storing photos and voice notes), Supabase (our database), Upstash (our cache), Fly.io (our servers), Vercel (our website) and Zoho (our support and grievance email).",
      },
      cookies: {
        title: "Cookies",
        // D-024.
        body: "We use cookies only to keep you signed in.",
      },
      choices: {
        title: "Your choices",
        // D-010, T-9.6.
        body: "In your settings you can hide your profile, your age or your distance, pause your account, download a copy of your data, or delete your account.",
      },
      deletion: {
        title: "Deleting your account",
        // D-051; the timing: T-9.6.
        erased:
          "When you delete your account, your profile disappears straight away. Within 30 days we erase your profile, your photos, your private album and everything else other people can see of you, except your messages.",
        messages:
          "Your messages stay in the other person's chat, shown as from “Deleted account”, and we keep them as moderation records. Otherwise, deleting an account could be used to destroy evidence someone has reported.",
        kept: "We also keep your history of Velas and payments, any reports and moderation records about you, and a hashed copy of your phone number, so that deleting an account can't be used to escape a ban or a report.",
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
    // matched the face photo, and a shown face matched the selfie; one line
    // for both genders (the founder, 8 October 2026).
    selfieMatched: "Selfie matched",
    errorTitle: "Something went wrong",
    retry: "Try again",
    pinProgress: "{count} of {max} digits entered",
    pinDelete: "Delete",
    otpDigit: "Digit {n} of {total}",
  },
} as const;
