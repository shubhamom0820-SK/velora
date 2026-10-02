import { describe, expect, it } from "vitest";

import {
  assertLegalFactsComplete,
  LEGAL,
  type LegalFacts,
  missingFacts,
  OFFICE_ADDRESS,
  REGISTERED_OFFICE,
} from "./legal";

// D-053, proved both ways: a missing legal fact builds only where it's allowed,
// and every refusal names each missing fact and what brings it.
// P-0.2's four facts are in (D-058); only the two emails are still to come.
const EVERY_GAP = [
  "the Grievance Officer's email (P-0.3)",
  "the support email (P-0.3)",
];

const KNOWN: LegalFacts = {
  companyName: "Example Private Limited",
  registeredOffice: "1 Example Road, Example Town 100001, India",
  court: "Example court",
  grievanceOfficerName: "A. Person",
  grievanceOfficerEmail: "grievance@example.in",
  supportEmail: "support@example.in",
};

describe("the legal facts", () => {
  it("are missing only where the mailboxes (P-0.3) bring them", () => {
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

// D-058's guard. When one of these fails, the reasoning is in D-058
// (docs/01-DECISIONS.md), not here: read it before changing either side.
const READ_D058 =
  "D-058: the registered office is Hajipur and the launch city is Phagwara, on purpose. " +
  "Read D-058 in docs/01-DECISIONS.md before changing this; a real change needs a new " +
  "decision that supersedes it, not an edit that makes the two agree.";

describe("the registered office (D-058)", () => {
  it("is the address the founder gave, word for word", () => {
    expect(OFFICE_ADDRESS, READ_D058).toBe(
      "Shubham Kumar, House No. 163, Anwarpur Chowk, Hajipur, Vaishali, Bihar – 844101",
    );
    expect(LEGAL.registeredOffice, READ_D058).toBe(OFFICE_ADDRESS);
  });

  it("is not the launch city: the two differ on purpose", () => {
    expect(REGISTERED_OFFICE.city, READ_D058).not.toBe("Phagwara");
    expect(OFFICE_ADDRESS, READ_D058).not.toMatch(/Phagwara|Punjab/);
  });

  it("decides the court: it follows the registered office, not the launch city", () => {
    expect(LEGAL.court, READ_D058).toBe(
      "The courts at Hajipur, Vaishali district, Bihar",
    );
    expect(LEGAL.court, READ_D058).toContain(REGISTERED_OFFICE.city);
    expect(LEGAL.court, READ_D058).toContain(REGISTERED_OFFICE.state);
  });
});

describe("who runs the app (D-058)", () => {
  it("is named exactly as the proprietor's PAN and bank account are", () => {
    expect(
      LEGAL.companyName,
      "D-058: this must match the proprietor's PAN and bank account exactly; Razorpay's " +
        "KYC compares them, and a mismatch stalls payouts. Don't tidy it.",
    ).toBe("Shubham Kumar, sole proprietor");
    expect(LEGAL.grievanceOfficerName).toBe("Shubham Kumar");
  });
});
