import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { OFFICE_ADDRESS } from "@/lib/legal";

/** The two mailboxes (P-0.3): the only email addresses a legal page may show. */
const MAILBOXES = ["support@veloraapp.co.in", "grievance@veloraapp.co.in"];

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

describe("the legal pages, with every fact known", () => {
  beforeEach(() => {
    vi.stubEnv("APP_ENV", "staging");
  });

  it.each(PAGES)(
    "%s has one h1, no 'not final' note, and links back home",
    (_path, Page, title) => {
      render(<Page />);

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(
        screen.getByRole("heading", { level: 1, name: t(title) }),
      ).toBeInTheDocument();
      // The note shows only while a fact is missing (LegalPage.test.tsx).
      expect(screen.queryByText(t("legal.notFinal"))).toBeNull();
      expect(
        screen.getByRole("link", { name: t("legal.back") }),
      ).toHaveAttribute("href", "/");
    },
  );

  it.each(PAGES)("%s names no price in Velas (D-004)", (_path, Page) => {
    const { container } = render(<Page />);

    expect(container.textContent).not.toMatch(/\d+\s*Velas?\b/);
  });

  it.each(PAGES)(
    "%s shows no email address but our two mailboxes",
    (_path, Page) => {
      const { container } = render(<Page />);

      // Text node by text node: textContent joins neighbouring elements without
      // a space, which would glue a label onto the address beside it.
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      const shown: string[] = [];
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        shown.push(...(node.textContent?.match(/[\w.+-]+@[\w.-]+\w/g) ?? []));
      }
      const linked = [...container.querySelectorAll('a[href^="mailto:"]')].map(
        (a) => a.getAttribute("href"),
      );
      for (const email of shown) expect(MAILBOXES).toContain(email);
      for (const href of linked)
        expect(MAILBOXES.map((m) => `mailto:${m}`)).toContain(href);
    },
  );
});

describe("the legal pages in a production build", () => {
  it.each(PAGES)(
    "%s builds now that every legal fact is known (D-053)",
    (_path, Page) => {
      vi.stubEnv("APP_ENV", "production");

      expect(() => render(<Page />)).not.toThrow();
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
        "Your photos, face photo, selfie, voice notes and private album are stored by Cloudflare, outside India.",
      ),
    ).toBeInTheDocument();
  });

  it("says what fraud scoring reads and that it can freeze an account (T-9.2)", () => {
    render(<PrivacyPage />);

    const line = screen.getByText(t("legal.privacy.collect.safety"));
    expect(line).toHaveTextContent("sign-ins");
    expect(line).toHaveTextContent("scored automatically");
    expect(line).toHaveTextContent(
      "freeze your account until our team looks into it",
    );
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

  it("says signing in again restores an account, Velas and all, before the erasure (D-500, D-504)", () => {
    render(<PrivacyPage />);

    expect(
      screen.getByText(t("legal.privacy.deletion.erased")),
    ).toHaveTextContent("Within 30 days we erase");
    expect(
      screen.getByText(t("legal.privacy.deletion.restore")),
    ).toHaveTextContent("Sign in again within 29 days");
    expect(
      screen.getByText(t("legal.privacy.deletion.velas")),
    ).toHaveTextContent("lost when your account is erased");
    expect(screen.getByText(t("legal.privacy.choices.body"))).toHaveTextContent(
      "download for 24 hours; then we delete it",
    );
  });

  it("says an under-18 sign-up is deleted at once, all but the number's hash (D-072)", () => {
    render(<PrivacyPage />);

    const children = screen.getByText(
      t("legal.privacy.children.body", { app: APP_NAME }),
    );
    expect(children).toHaveTextContent(
      "delete the account and everything in it at once",
    );
    expect(children).toHaveTextContent(
      "We keep only a hashed copy of the phone number",
    );
  });
});

/** D-050's promise of Velas returning by themselves, gone since D-230 (P-130). */
const RETURNS_ON_ITS_OWN = /on their own|come back to your balance|7 days/;

describe("/refunds", () => {
  beforeEach(() => {
    vi.stubEnv("APP_ENV", "staging");
  });

  it("says the four things D-050, D-230 and D-504 decide, in order", () => {
    render(<RefundsPage />);

    expect(sectionTitles()).toEqual([
      t("legal.refunds.final.title"),
      t("legal.refunds.spent.title"),
      t("legal.refunds.deleted.title"),
      t("legal.refunds.broken.title"),
    ]);
  });

  it("says Velas left in a deleted account are lost once it's erased (D-504)", () => {
    render(<RefundsPage />);
    const deleted = section(t("legal.refunds.deleted.title"));

    expect(deleted).toHaveTextContent("lost once it's erased, within 30 days");
    expect(deleted).toHaveTextContent("We don't refund them.");
    expect(deleted).toHaveTextContent("Sign in again within 29 days");
  });

  it("promises no Velas back, on a ban or on a declined request (D-230, P-130)", () => {
    const { container } = render(<RefundsPage />);
    const spent = section(t("legal.refunds.spent.title"));

    expect(spent).toHaveTextContent("Once you spend Velas, they're spent.");
    expect(spent).toHaveTextContent("later banned");
    expect(spent).toHaveTextContent("declines your request");
    // D-050's "When Velas come back on their own" and the opening line's
    // clause are gone: nothing on the page says Velas return by themselves.
    expect(container.textContent).not.toMatch(RETURNS_ON_ITS_OWN);
  });

  it("would catch the title and the two sentences it replaced", () => {
    for (const old of [
      "When Velas come back on their own",
      "the Velas you spent on the request come back to your balance.",
      "the Velas you spent on them in the 7 days before the ban come back to your balance.",
    ])
      expect(old).toMatch(RETURNS_ON_ITS_OWN);
  });
});

describe("/contact", () => {
  it("names who runs it, the registered office and both mailboxes, with nothing left to confirm", () => {
    vi.stubEnv("APP_ENV", "production");
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
    // The mailboxes as mail links (P-0.3), and nothing "to be confirmed".
    expect(
      screen.getByRole("link", { name: "support@veloraapp.co.in" }),
    ).toHaveAttribute("href", "mailto:support@veloraapp.co.in");
    expect(
      screen.getByRole("link", { name: "grievance@veloraapp.co.in" }),
    ).toHaveAttribute("href", "mailto:grievance@veloraapp.co.in");
    expect(screen.queryByText(t("legal.toBeConfirmed"))).toBeNull();
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
