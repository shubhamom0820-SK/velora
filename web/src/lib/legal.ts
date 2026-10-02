/**
 * Every fact the legal pages state about the business (T-2.2), and the gate that
 * keeps a missing one out of production (D-053). A fact is either known or
 * missing, and a missing fact names the plan item that brings it. Pages show a
 * missing fact as "To be confirmed"; nothing here is ever invented.
 */

export type Missing = {
  readonly missing: true;
  /** What the fact is, as the build error names it. */
  readonly what: string;
  /** The plan item that brings it: registration (P-0.2) or the domain (P-0.3). */
  readonly waitsOn: "P-0.2" | "P-0.3";
};

export type Fact = string | Missing;

/** A fact the pages need but we don't have yet: the next one goes through here (D-053). */
export function missing(what: string, waitsOn: Missing["waitsOn"]): Missing {
  return { missing: true, what, waitsOn };
}

export function isMissing(fact: Fact): fact is Missing {
  return typeof fact !== "string";
}

/**
 * The registered office: where legal notice is served (D-058), as the founder
 * gave it. Deliberately not the launch city, Phagwara: the two differ on
 * purpose, so don't make them agree. It's one fact rendered twice: in full on
 * Contact and in Terms, and as its town in the footer, so they can't drift apart.
 */
export const REGISTERED_OFFICE = {
  addressee: "Shubham Kumar",
  street: "House No. 163, Anwarpur Chowk",
  city: "Hajipur",
  district: "Vaishali",
  state: "Bihar",
  pin: "844101",
  country: "India",
} as const;

/** The registered office on one line, word for word as the founder gave it. */
export const OFFICE_ADDRESS = [
  REGISTERED_OFFICE.addressee,
  REGISTERED_OFFICE.street,
  REGISTERED_OFFICE.city,
  REGISTERED_OFFICE.district,
  `${REGISTERED_OFFICE.state} – ${REGISTERED_OFFICE.pin}`,
].join(", ");

export type LegalFacts = {
  /** Who runs the app: a sole proprietorship, so not a company (D-058). */
  readonly companyName: Fact;
  readonly registeredOffice: Fact;
  readonly court: Fact;
  readonly grievanceOfficerName: Fact;
  readonly grievanceOfficerEmail: Fact;
  readonly supportEmail: Fact;
};

// Every fact is known: P-0.2's four (D-058) and P-0.3's two mailboxes, so the
// production build's gate lets the legal pages through (D-053).
export const LEGAL: LegalFacts = {
  // Word for word: it must match the proprietor's PAN and bank account, which
  // Razorpay's KYC compares. A "tidier" name stalls payouts (D-058).
  companyName: "Shubham Kumar, sole proprietor",
  registeredOffice: OFFICE_ADDRESS,
  // The court follows the registered office, not the launch city (D-058).
  court: "The courts at Hajipur, Vaishali district, Bihar",
  grievanceOfficerName: "Shubham Kumar",
  // Aliases on one Zoho Mail user in its India data centre, proven by a
  // message received and a reply sent (P-0.3).
  grievanceOfficerEmail: "grievance@veloraapp.co.in",
  supportEmail: "support@veloraapp.co.in",
};

export function missingFacts(facts: LegalFacts = LEGAL): Missing[] {
  return Object.values(facts).filter(isMissing);
}

/** Where a page may still show a missing fact: an allowlist (CLAUDE.md rule 16). */
const MISSING_FACTS_ALLOWED_IN: ReadonlySet<string> = new Set([
  "local",
  "ci",
  "staging",
]);

type BuildEnv = { readonly NODE_ENV?: string; readonly APP_ENV?: string };

/**
 * Throws unless every legal fact is known, or this build may show a missing
 * one: `next dev`, or `APP_ENV` local, ci or staging. Every legal page calls
 * it as it renders, and the pages are static, so a production build stops
 * here, naming each missing fact (D-053).
 */
export function assertLegalFactsComplete(
  facts: LegalFacts = LEGAL,
  env: BuildEnv = process.env,
): void {
  const gaps = missingFacts(facts);
  if (gaps.length === 0) return;
  if (env.NODE_ENV === "development") return;
  if (env.APP_ENV !== undefined && MISSING_FACTS_ALLOWED_IN.has(env.APP_ENV)) {
    return;
  }
  const where = env.APP_ENV ? `APP_ENV=${env.APP_ENV}` : "APP_ENV unset";
  const list = gaps.map((gap) => `${gap.what} (${gap.waitsOn})`).join("; ");
  throw new Error(
    `The legal pages can't be built with ${where}. Still missing: ${list}. ` +
      "A missing fact may show only where APP_ENV is local, ci or staging (D-053).",
  );
}
