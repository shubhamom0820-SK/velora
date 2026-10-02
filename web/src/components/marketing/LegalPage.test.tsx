import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { LegalPage } from "./LegalPage";

// Every real legal fact is known now (P-0.2, P-0.3), so these tests stand in a
// missing one: the "not final" note and D-053's refusal are still how the next
// fact the pages need will behave.
vi.mock("@/lib/legal", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/legal")>();
  const gaps = {
    ...actual.LEGAL,
    supportEmail: actual.missing("the support email", "P-0.3"),
  };
  return {
    ...actual,
    missingFacts: () => actual.missingFacts(gaps),
    assertLegalFactsComplete: (
      _facts?: unknown,
      env: Parameters<typeof actual.assertLegalFactsComplete>[1] = process.env,
    ) => actual.assertLegalFactsComplete(gaps, env),
  };
});

function renderPage() {
  render(
    <LegalPage title="Terms" intro="The rules.">
      <p>Body</p>
    </LegalPage>,
  );
}

describe("LegalPage, while a legal fact is missing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("says the page isn't final where a missing fact may show", () => {
    vi.stubEnv("APP_ENV", "staging");
    renderPage();

    expect(screen.getByText(t("legal.notFinal"))).toBeInTheDocument();
  });

  it("refuses to render in a production build, naming the fact (D-053)", () => {
    vi.stubEnv("APP_ENV", "production");
    vi.spyOn(console, "error").mockImplementation(() => {});

    expect(renderPage).toThrow("Still missing: the support email (P-0.3).");
  });
});
