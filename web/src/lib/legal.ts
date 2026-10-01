/**
 * Every fact the legal pages state about the company (T-2.2), and the gate that
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

function missing(what: string, waitsOn: Missing["waitsOn"]): Missing {
  return { missing: true, what, waitsOn };
}

export function isMissing(fact: Fact): fact is Missing {
  return typeof fact !== "string";
}

/** The registered office and the launch city (D-013): decided, so not a missing fact. */
export const PLACE = {
  city: "Phagwara",
  state: "Punjab",
  country: "India",
} as const;

export type LegalFacts = {
  readonly companyName: Fact;
  readonly registeredOffice: Fact;
  readonly court: Fact;
  readonly grievanceOfficerName: Fact;
  readonly grievanceOfficerEmail: Fact;
  readonly supportEmail: Fact;
};

export const LEGAL: LegalFacts = {
  companyName: missing("the company's registered name", "P-0.2"),
  registeredOffice: missing("the registered office's street address", "P-0.2"),
  court: missing(
    "the court with jurisdiction over the registered office",
    "P-0.2",
  ),
  grievanceOfficerName: missing("the Grievance Officer's name", "P-0.2"),
  grievanceOfficerEmail: missing("the Grievance Officer's email", "P-0.3"),
  supportEmail: missing("the support email", "P-0.3"),
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
