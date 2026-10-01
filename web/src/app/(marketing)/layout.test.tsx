import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

import MarketingLayout from "./layout";

describe("the marketing layout", () => {
  it("puts the footer under every marketing page", () => {
    render(
      <MarketingLayout>
        <main>A marketing page</main>
      </MarketingLayout>,
    );

    expect(screen.getByRole("main")).toHaveTextContent("A marketing page");
    const nav = within(screen.getByRole("contentinfo")).getByRole(
      "navigation",
      { name: t("landing.footer.label") },
    );
    const links = within(nav).getAllByRole("link");
    expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      [t("landing.footer.terms"), "/terms"],
      [t("landing.footer.privacy"), "/privacy"],
      [t("landing.footer.refunds"), "/refunds"],
      [t("landing.footer.contact"), "/contact"],
    ]);
  });

  it("signs the footer with the registered office's city (D-013)", () => {
    render(
      <MarketingLayout>
        <main />
      </MarketingLayout>,
    );

    expect(
      within(screen.getByRole("contentinfo")).getByText(
        `© ${new Date().getFullYear()} ${APP_NAME} · Phagwara, India`,
      ),
    ).toBeInTheDocument();
  });
});
