import { describe, expect, it } from "vitest";

import {
  assertLegalFactsComplete,
  LEGAL,
  type LegalFacts,
  missingFacts,
} from "./legal";

// D-053, proved both ways: a missing legal fact builds only where it's allowed,
// and every refusal names each missing fact and what brings it.
const EVERY_GAP = [
  "the company's registered name (P-0.2)",
  "the registered office's street address (P-0.2)",
  "the court with jurisdiction over the registered office (P-0.2)",
  "the Grievance Officer's name (P-0.2)",
  "the Grievance Officer's email (P-0.3)",
  "the support email (P-0.3)",
];

const KNOWN: LegalFacts = {
  companyName: "Example Private Limited",
  registeredOffice: "1 Example Road, Phagwara, Punjab 144401, India",
  court: "Example court",
  grievanceOfficerName: "A. Person",
  grievanceOfficerEmail: "grievance@example.in",
  supportEmail: "support@example.in",
};

describe("the legal facts", () => {
  it("are missing only where registration (P-0.2) or the domain (P-0.3) brings them", () => {
    expect(missingFacts().map((gap) => `${gap.what} (${gap.waitsOn})`)).toEqual(
      EVERY_GAP,
    );
  });
});

describe("assertLegalFactsComplete", () => {
  it.each(["local", "ci", "staging"])(
    "lets a missing fact show where APP_ENV is %s",
    (appEnv) => {
      expect(() =>
        assertLegalFactsComplete(LEGAL, {
          NODE_ENV: "production",
          APP_ENV: appEnv,
        }),
      ).not.toThrow();
    },
  );

  it("lets a missing fact show under next dev", () => {
    expect(() =>
      assertLegalFactsComplete(LEGAL, { NODE_ENV: "development" }),
    ).not.toThrow();
  });

  it.each([
    ["production", "APP_ENV=production"],
    ["prod", "APP_ENV=prod"],
    ["Staging", "APP_ENV=Staging"],
    [undefined, "APP_ENV unset"],
  ])(
    "refuses where APP_ENV is %s, naming every missing fact",
    (appEnv, where) => {
      expect(() =>
        assertLegalFactsComplete(LEGAL, {
          NODE_ENV: "production",
          APP_ENV: appEnv,
        }),
      ).toThrow(
        `The legal pages can't be built with ${where}. Still missing: ${EVERY_GAP.join("; ")}. ` +
          "A missing fact may show only where APP_ENV is local, ci or staging (D-053).",
      );
    },
  );

  it("lets production build once every fact is known", () => {
    expect(() =>
      assertLegalFactsComplete(KNOWN, {
        NODE_ENV: "production",
        APP_ENV: "production",
      }),
    ).not.toThrow();
  });

  it("names only the facts still missing", () => {
    expect(() =>
      assertLegalFactsComplete(
        { ...KNOWN, supportEmail: LEGAL.supportEmail },
        { NODE_ENV: "production", APP_ENV: "production" },
      ),
    ).toThrow("Still missing: the support email (P-0.3).");
  });
});
