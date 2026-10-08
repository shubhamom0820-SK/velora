import { render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import YouPage from "./you/page";

// One route per place in the shell's nav, each a placeholder until its task
// (T-5.6); Wallet's is built (T-5.5), Discover's too (T-6.5), a person's
// profile (T-6.8) and Chats (T-7.10). They render inside the shell's <main>,
// so none brings its own.
describe("the app's placeholder routes", () => {
  it.each<[string, ComponentType]>([["You", YouPage]])(
    "%s says what it is and that it's coming",
    (name, Page) => {
      render(<Page />);

      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(name);
      expect(screen.getByText(t("placeholder.comingSoon"))).toBeInTheDocument();
      expect(screen.queryByRole("main")).not.toBeInTheDocument();
    },
  );

  it("links You to your album's requests, for everyone (T-8.8, D-790)", () => {
    render(<YouPage />);

    expect(
      screen.getByRole("link", { name: t("albumRequests.title") }),
    ).toHaveAttribute("href", "/you/album-requests");
  });
});
