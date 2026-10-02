import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { REGISTERED_OFFICE } from "@/lib/legal";

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

  // One fact rendered twice: the footer reads the town from the same record
  // Contact shows in full, so the two can't drift apart (D-058).
  it("signs the footer with the registered office's town, read from that one record", () => {
    render(
      <MarketingLayout>
        <main />
      </MarketingLayout>,
    );

    const footer = within(screen.getByRole("contentinfo"));
    expect(
      footer.getByText(
        `© ${new Date().getFullYear()} ${APP_NAME} · ${REGISTERED_OFFICE.city}, ${REGISTERED_OFFICE.country}`,
      ),
    ).toHaveTextContent("Hajipur, India");
  });
});
