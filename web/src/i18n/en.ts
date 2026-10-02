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
    admin: "Admin",
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
      safety: {
        title: "Verified, moderated",
        body: "Selfie verification, photo checks, and reports that actually remove people.",
      },
    },
    // The waitlist box (T-2.3), for people outside the launch city. Its city is
    // optional and tells us where demand is, the input to choosing a second
    // city; /privacy says both uses (legal.privacy.collect.waitlist).
    waitlist: {
      title: "Not in your city yet?",
      body: "Leave your email and we'll tell you when {app} opens near you.",
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
      // {city}, {country}: the registered office (D-013), from src/lib/legal.ts.
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
        // D-013; the company's name and address are on Contact (D-053).
        body: "{app} is run by the company named on our contact page. Its registered office is in {city}, {state}, {country}.",
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
        // D-008, D-012.
        body: "You choose your gender once, when you sign up, and you can't change it later. Women verify with a selfie before their profile goes live; for men it's optional. You can lock {app} on your device with a 4-digit PIN. After 5 wrong tries we sign you out, and you sign back in with your phone number.",
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
        // D-052: the first thing P-0.7's review checks.
        body: "These terms are governed by the laws of India. Any dispute goes to the courts with jurisdiction over our registered office in {city}, {state}.",
        court: "The court",
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
        // D-008; never public: 06-TESTING's never-skip list.
        selfie:
          "Your selfie, to check that you're really you. It's never shown to anyone.",
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
        servers:
          "Every request you make is handled by our servers in Singapore.",
        media:
          "Your photos, selfie, voice notes and private album are stored by Cloudflare, outside India.",
        // Deleted after the check: T-4.4 turns that on.
        moderation:
          "Photos are checked by Sightengine, on servers in the United States or Europe, and deleted there after the check.",
        faceMatch:
          "Your selfie is compared by Amazon Web Services, in Mumbai, India.",
        phone:
          "Your phone number is also handled by Google, in the United States, as described above.",
      },
      others: {
        title: "Who else handles your data",
        // D-023, D-026, D-027, D-028, D-035, D-048.
        body: "Google (sign-in codes), Razorpay (payments), Sightengine (photo checks), Amazon Web Services (selfie checks), Cloudflare (storing photos and voice notes), Supabase (our database), Upstash (our cache), Fly.io (our servers) and Vercel (our website).",
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
        // D-009.
        body: "{app} is only for people aged 18 and over. If someone gives a date of birth under 18, we refuse the sign-up and keep a hashed copy of the phone number, so that it can't sign up again.",
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
        "This page covers your money and your Velas: when a purchase is final, when we fix a payment, and when Velas come back on their own.",
      // D-050, all three sections.
      final: {
        title: "Purchases are final",
        body: "When you buy Velas, the purchase is final. We don't refund it if you change your mind, whether or not you've spent them.",
      },
      broken: {
        title: "A broken payment is ours to fix",
        body: "If your payment went through but the Velas never reached your balance, or you were charged twice for one purchase, that isn't a change of mind: something went wrong on our side, and we fix it. We add the missing Velas, or refund the extra charge to the way you paid.",
        write: "Write to us with the payment details.",
        support: "Support email",
      },
      automatic: {
        title: "When Velas come back on their own",
        // D-004.
        album:
          "If someone declines your request to see their private album, the Velas you spent on the request come back to your balance.",
        // T-9.3: the 7 days is stated there too; change both together.
        banned:
          "If someone you spent Velas on is banned from {app}, the Velas you spent on them in the 7 days before the ban come back to your balance.",
      },
    },
    contact: {
      title: "Contact and grievances",
      intro: "Who runs {app}, how to reach us, and who handles complaints.",
      details: "Our details",
      company: "Company",
      office: "Registered office",
      place: "{city}, {state}, {country}",
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
    verified: "Verified",
    errorTitle: "Something went wrong",
    retry: "Try again",
  },
} as const;
