import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

import LandingPage from "./page";

describe("/ (landing)", () => {
  it("has one h1, the headline, in the product's nouns rather than the brand", () => {
    render(<LandingPage />);

    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveAccessibleName(
      `${t("landing.headlineThreads")} ${t("landing.headlineKnots")}`,
    );
    expect(h1).toHaveTextContent(/Knots last\./);
    expect(h1).not.toHaveTextContent(APP_NAME);
  });

  it("lists the three feature cards, each under its own heading", () => {
    render(<LandingPage />);

    const headings = screen.getAllByRole("heading", { level: 2 });
    expect(headings.map((h) => h.textContent)).toEqual([
      t("landing.features.threads.title"),
      t("landing.features.knot.title"),
      t("landing.features.safety.title"),
    ]);
    const main = screen.getByRole("main");
    expect(within(main).getAllByRole("listitem")).toHaveLength(3);
  });

  it("sends both calls to action to sign-in", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("link", { name: t("landing.getStarted") }),
    ).toHaveAttribute("href", "/login");
    expect(
      screen.getByRole("link", {
        name: t("landing.join", { app: APP_NAME }),
      }),
    ).toHaveAttribute("href", "/login");
  });

  it("says who it is for", () => {
    render(<LandingPage />);

    expect(screen.getByText(t("landing.ageNote"))).toBeInTheDocument();
  });

  it("links the four legal pages from the footer", () => {
    render(<LandingPage />);

    const nav = screen.getByRole("navigation", {
      name: t("landing.footer.label"),
    });
    const links = within(nav).getAllByRole("link");
    expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      [t("landing.footer.terms"), "/terms"],
      [t("landing.footer.privacy"), "/privacy"],
      [t("landing.footer.refunds"), "/refunds"],
      [t("landing.footer.contact"), "/contact"],
    ]);
    expect(
      within(screen.getByRole("contentinfo")).getByText(
        t("landing.footer.copyright", {
          year: new Date().getFullYear(),
          app: APP_NAME,
        }),
      ),
    ).toBeInTheDocument();
  });
});

// T-2.1 ships no page-level client JS: the landing page and everything it
// renders stay server components. T-2.3's waitlist form will be the one entry
// here, as the landing page's only client component.
const CLIENT_COMPONENTS_ALLOWED = new Set<string>();

const SERVER_ONLY = [
  "src/app/(marketing)/page.tsx",
  "src/components/ui/ButtonLink.tsx",
  "src/components/ui/Icon.tsx",
  ...readdirSync("src/components/marketing")
    .filter((name) => name.endsWith(".tsx") && !name.endsWith(".test.tsx"))
    .map((name) => join("src/components/marketing", name)),
];

describe("the landing page's JavaScript", () => {
  it.each(SERVER_ONLY.filter((file) => !CLIENT_COMPONENTS_ALLOWED.has(file)))(
    "%s is a server component",
    (file) => {
      expect(readFileSync(file, "utf8")).not.toMatch(/^\s*["']use client["']/m);
    },
  );

  it("checks every marketing component", () => {
    expect(SERVER_ONLY).toEqual(
      expect.arrayContaining([
        "src/components/marketing/SiteHeader.tsx",
        "src/components/marketing/Hero.tsx",
        "src/components/marketing/FeatureCard.tsx",
        "src/components/marketing/SiteFooter.tsx",
      ]),
    );
  });
});
