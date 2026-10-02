import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { OFFICE_ADDRESS } from "@/lib/legal";

import ContactPage from "./contact/page";
import PrivacyPage from "./privacy/page";
import RefundsPage from "./refunds/page";
import TermsPage from "./terms/page";

const PAGES = [
  ["/terms", TermsPage, "legal.terms.title"],
  ["/privacy", PrivacyPage, "legal.privacy.title"],
  ["/refunds", RefundsPage, "legal.refunds.title"],
  ["/contact", ContactPage, "legal.contact.title"],
] as const;

/** The section under the heading `title`, so an assertion reads only that section. */
function section(title: string): HTMLElement {
  const found = screen
    .getByRole("heading", { level: 2, name: title })
    .closest("section");
  if (!found) throw new Error(`No section for "${title}"`);
  return found;
}

function sectionTitles(): Array<string | null> {
  return screen
    .getAllByRole("heading", { level: 2 })
    .map((heading) => heading.textContent);
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("the legal pages, on staging with facts still missing", () => {
  beforeEach(() => {
    vi.stubEnv("APP_ENV", "staging");
  });

  it.each(PAGES)(
    "%s has one h1, says it isn't final, and links back home",
    (_path, Page, title) => {
      render(<Page />);

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(
        screen.getByRole("heading", { level: 1, name: t(title) }),
      ).toBeInTheDocument();
      expect(screen.getByText(t("legal.notFinal"))).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: t("legal.back") }),
      ).toHaveAttribute("href", "/");
    },
  );

  it.each(PAGES)("%s names no price in Velas (D-004)", (_path, Page) => {
    const { container } = render(<Page />);

    expect(container.textContent).not.toMatch(/\d+\s*Velas?\b/);
  });

  it.each(PAGES)("%s invents no email address", (_path, Page) => {
    const { container } = render(<Page />);

    expect(container.textContent).not.toContain("@");
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull();
  });
});

describe("the legal pages in a production build", () => {
  it.each(PAGES)(
    "%s refuses to build while a legal fact is missing (D-053)",
    (_path, Page) => {
      vi.stubEnv("APP_ENV", "production");
      vi.spyOn(console, "error").mockImplementation(() => {});

      expect(() => render(<Page />)).toThrow(
        "The legal pages can't be built with APP_ENV=production. Still missing:",
      );
    },
  );
});

describe("/privacy", () => {
  beforeEach(() => {
    vi.stubEnv("APP_ENV", "staging");
  });

  it("states Google's copy of the phone number first, in a section of its own", () => {
    render(<PrivacyPage />);

    expect(sectionTitles()[0]).toBe(t("legal.privacy.google.title"));
    expect(screen.getByText(t("legal.privacy.google.body"))).toHaveTextContent(
      "We can't delete Google's copy, even if you delete your account.",
    );
  });

  it("never names a region for what Cloudflare stores (D-048)", () => {
    render(<PrivacyPage />);

    expect(
      screen.getByText(
        "Your photos, selfie, voice notes and private album are stored by Cloudflare, outside India.",
      ),
    ).toBeInTheDocument();
  });

  it("says what deleting an account keeps (D-051)", () => {
    render(<PrivacyPage />);

    expect(
      screen.getByText(t("legal.privacy.deletion.messages")),
    ).toHaveTextContent("shown as from “Deleted account”");
    expect(
      screen.getByText(t("legal.privacy.deletion.kept")),
    ).toHaveTextContent("a hashed copy of your phone number");
  });
});

describe("/refunds", () => {
  it("says the three things D-050 decides, in order", () => {
    vi.stubEnv("APP_ENV", "staging");
    render(<RefundsPage />);

    expect(sectionTitles()).toEqual([
      t("legal.refunds.final.title"),
      t("legal.refunds.broken.title"),
      t("legal.refunds.automatic.title"),
    ]);
  });
});

describe("/contact", () => {
  it("names who runs it and the registered office, with only the two emails to come", () => {
    vi.stubEnv("APP_ENV", "staging");
    const { container } = render(<ContactPage />);

    expect(screen.getByText(t("legal.facts.runBy"))).toBeInTheDocument();
    expect(
      screen.getByText("Shubham Kumar, sole proprietor"),
    ).toBeInTheDocument();
    expect(screen.getByText(OFFICE_ADDRESS)).toBeInTheDocument();
    // A proprietorship isn't a company (D-058).
    expect(container.textContent).not.toMatch(/\bcompany\b/i);
    // The registered office isn't the launch city (D-058): no Phagwara line under it.
    expect(container.textContent).not.toMatch(/Phagwara|Punjab/);
    // The support email and the Grievance Officer's email (P-0.3).
    expect(screen.getAllByText(t("legal.toBeConfirmed"))).toHaveLength(2);
  });
});

describe("/terms", () => {
  beforeEach(() => {
    vi.stubEnv("APP_ENV", "staging");
  });

  it("names the business it binds, directly (P-0.2, D-058)", () => {
    render(<TermsPage />);
    const whoWeAre = section(t("legal.terms.whoWeAre.title"));

    expect(whoWeAre).toHaveTextContent("Shubham Kumar, sole proprietor");
    expect(whoWeAre).toHaveTextContent(OFFICE_ADDRESS);
    expect(whoWeAre.textContent).not.toMatch(
      /\bcompany\b|contact page|Phagwara/i,
    );
  });

  it("sends disputes to the Hajipur courts, and tells consumers they can still complain where they live", () => {
    render(<TermsPage />);
    const law = section(t("legal.terms.law.title"));

    expect(law).toHaveTextContent(
      "The courts at Hajipur, Vaishali district, Bihar",
    );
    expect(law).toHaveTextContent(t("legal.terms.law.consumers"));
    expect(law.textContent).not.toMatch(/Phagwara|Punjab/);
  });
});
