import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

import LandingPage from "./page";

// The waitlist form needs a query client, as the root layout provides.
function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LandingPage />
    </QueryClientProvider>,
  );
}

describe("/ (landing)", () => {
  it("has one h1, the headline, in the product's nouns rather than the brand", () => {
    renderPage();

    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveAccessibleName(
      `${t("landing.headlineThreads")} ${t("landing.headlineKnots")}`,
    );
    expect(h1).toHaveTextContent(/Knots last\./);
    expect(h1).not.toHaveTextContent(APP_NAME);
  });

  it("lists the three feature cards, each under its own heading, then the waitlist", () => {
    renderPage();

    const headings = screen.getAllByRole("heading", { level: 2 });
    expect(headings.map((h) => h.textContent)).toEqual([
      t("landing.features.threads.title"),
      t("landing.features.knot.title"),
      t("landing.features.safety.title"),
      t("landing.waitlist.closedTitle", { app: APP_NAME }),
    ]);
    const main = screen.getByRole("main");
    expect(within(main).getAllByRole("listitem")).toHaveLength(3);
  });

  it("sends both calls to action to sign-in", () => {
    renderPage();

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
    renderPage();

    expect(screen.getByText(t("landing.ageNote"))).toBeInTheDocument();
  });
});

// The marketing pages and everything they render stay server components, so
// the landing page ships no client JS of its own beyond this: T-2.3's waitlist
// form, its only client component.
const CLIENT_COMPONENTS_ALLOWED = new Set<string>([
  "src/components/marketing/WaitlistForm.tsx",
]);

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
        "src/components/marketing/WaitlistBox.tsx",
        "src/components/marketing/WaitlistForm.tsx",
      ]),
    );
  });

  // An allowlist entry that stops being a client component, or stops existing,
  // would leave a hole the next client component could slip through.
  it.each([...CLIENT_COMPONENTS_ALLOWED])(
    "%s, allowed to be a client component, is one",
    (file) => {
      expect(readFileSync(file, "utf8")).toMatch(/^\s*["']use client["']/m);
    },
  );
});

describe("the waitlist box says which of two people it's for (D-081's flag)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(["firebase", ""])(
    "a %s build, where nobody can sign in, says the app isn't open yet",
    (path) => {
      vi.stubEnv("SIGN_IN_PATH", path);
      renderPage();

      const box = screen.getByRole("region", {
        name: "Velora isn't open yet",
      });
      expect(box).toHaveTextContent(
        "Leave your email and we'll tell you the day it is.",
      );
      // Never the other person's words: that would say it works elsewhere.
      expect(box).not.toHaveTextContent("Not in your city yet?");
      expect(box).not.toHaveTextContent("Knot opens");
      expect(
        within(box).getByRole("button", { name: t("landing.waitlist.join") }),
      ).toBeInTheDocument();
    },
  );

  it("a build where sign-in is open speaks to people outside the launch city", () => {
    vi.stubEnv("SIGN_IN_PATH", "otp");
    renderPage();

    const box = screen.getByRole("region", { name: "Not in your city yet?" });
    expect(box).toHaveTextContent(
      "We're starting in Phagwara. Leave your email and we'll tell you when we reach you.",
    );
    expect(box).not.toHaveTextContent("isn't open yet");
  });
});
