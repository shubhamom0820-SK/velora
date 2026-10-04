import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { AppShell } from "./AppShell";

const nav = vi.hoisted(() => ({ pathname: "/discover" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));

// A brand that is neither the prototype's nor ours: a wordmark typed into the
// component instead of read from APP_NAME can't pass (CLAUDE.md rule 17).
vi.mock("@/lib/app", () => ({ APP_NAME: "Zephyrine" }));

function renderShell() {
  return render(
    <AppShell>
      <p>A screen</p>
    </AppShell>,
  );
}

beforeEach(() => {
  nav.pathname = "/discover";
});

describe("the app shell (T-5.6)", () => {
  it("links to exactly Discover, Chats, Wallet and You, in that order, and nothing else", () => {
    renderShell();

    const menu = screen.getByRole("navigation", { name: t("shell.nav") });
    expect(screen.getAllByRole("navigation")).toEqual([menu]);
    // Every link in the whole shell, not only the nav's: a fifth anywhere fails.
    const links = screen.getAllByRole("link");
    expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["Discover", "/discover"],
      ["Chats", "/chats"],
      ["Wallet", "/wallet"],
      ["You", "/you"],
    ]);
    expect(links.every((a) => menu.contains(a))).toBe(true);
    expect(screen.queryByText(/vibe/i)).not.toBeInTheDocument();
  });

  it("names the app with APP_NAME in the header, never a brand typed in", () => {
    renderShell();

    const header = screen.getByRole("banner");
    expect(within(header).getByText("Zephyrine")).toBeInTheDocument();
    expect(header).not.toHaveTextContent(/velora|knot/i);
  });

  it("puts the screen in the one main landmark, outside the header", () => {
    renderShell();

    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getByRole("main")).toHaveTextContent("A screen");
    expect(screen.getByRole("banner")).not.toHaveTextContent("A screen");
  });

  it.each([
    ["/discover", "Discover"],
    ["/chats", "Chats"],
    ["/chats/some-thread", "Chats"],
    ["/wallet", "Wallet"],
    ["/you", "You"],
  ])("marks only the current place on %s", (pathname, current) => {
    nav.pathname = pathname;
    renderShell();

    const marked = screen
      .getAllByRole("link")
      .filter((a) => a.getAttribute("aria-current") === "page");
    expect(marked.map((a) => a.textContent)).toEqual([current]);
  });

  it("marks nothing on a path that only starts like a place", () => {
    nav.pathname = "/wallets";
    renderShell();

    expect(
      screen.getAllByRole("link").filter((a) => a.hasAttribute("aria-current")),
    ).toEqual([]);
  });
});
