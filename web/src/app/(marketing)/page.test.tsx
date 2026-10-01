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
});

// T-2.1 ships no page-level client JS: the marketing pages and everything they
// render stay server components. T-2.3's waitlist form will be the one entry
// here, as the landing page's only client component.
const CLIENT_COMPONENTS_ALLOWED = new Set<string>();

// Every file under these folders, so a new marketing page or component is
// checked the day it's added (T-2.2 added the legal pages and their layout).
function componentsIn(dir: string): string[] {
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter((name) => name.endsWith(".tsx") && !name.endsWith(".test.tsx"))
    .map((name) => join(dir, name));
}

const SERVER_ONLY = [
  ...componentsIn("src/app/(marketing)"),
  ...componentsIn("src/components/marketing"),
  "src/components/ui/ButtonLink.tsx",
  "src/components/ui/Icon.tsx",
];

describe("the landing page's JavaScript", () => {
  it.each(SERVER_ONLY.filter((file) => !CLIENT_COMPONENTS_ALLOWED.has(file)))(
    "%s is a server component",
    (file) => {
      expect(readFileSync(file, "utf8")).not.toMatch(/^\s*["']use client["']/m);
    },
  );

  it("checks every marketing page and component", () => {
    expect(SERVER_ONLY).toEqual(
      expect.arrayContaining([
        "src/app/(marketing)/layout.tsx",
        "src/app/(marketing)/page.tsx",
        "src/app/(marketing)/terms/page.tsx",
        "src/app/(marketing)/privacy/page.tsx",
        "src/app/(marketing)/refunds/page.tsx",
        "src/app/(marketing)/contact/page.tsx",
        "src/components/marketing/SiteHeader.tsx",
        "src/components/marketing/Hero.tsx",
        "src/components/marketing/FeatureCard.tsx",
        "src/components/marketing/SiteFooter.tsx",
        "src/components/marketing/LegalPage.tsx",
        "src/components/marketing/LegalSection.tsx",
        "src/components/marketing/LegalFact.tsx",
        "src/components/marketing/LegalFactList.tsx",
      ]),
    );
  });
});
