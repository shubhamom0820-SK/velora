import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";
import { useStoreSheet } from "@/store/store-sheet";

import { AppShell } from "./AppShell";

const nav = vi.hoisted(() => ({ pathname: "/discover" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));

// A brand that is neither the prototype's nor ours: a wordmark typed into the
// component instead of read from APP_NAME can't pass (CLAUDE.md rule 17).
vi.mock("@/lib/app", () => ({ APP_NAME: "Zephyrine" }));

/** The shell as a signed-in person sees it; no gender means no pill. */
function renderShell(gender: "male" | "female" | null = null) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), { id: "u1", gender });
  return render(
    <QueryClientProvider client={client}>
      <AppShell>
        <p>A screen</p>
      </AppShell>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  nav.pathname = "/discover";
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  useStoreSheet.setState({ open: false });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
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

describe("the header's balance (T-5.5)", () => {
  it("shows a man his balance from the wallet, as a button that opens the store sheet", async () => {
    fakeApi({ "GET /v1/wallet": () => json(200, { balance: 1250 }) });
    renderShell("male");

    const header = screen.getByRole("banner");
    const pill = await within(header).findByRole("button", {
      name: t("wallet.pill", { velas: "1,250 Velas" }),
    });
    expect(pill).toHaveTextContent("1,250");
    expect(header).not.toHaveTextContent(t("wallet.freeAccess"));

    await userEvent.click(pill);
    expect(useStoreSheet.getState().open).toBe(true);
  });

  it("says one Vela, not one Velas", async () => {
    fakeApi({ "GET /v1/wallet": () => json(200, { balance: 1 }) });
    renderShell("male");

    expect(
      await screen.findByRole("button", {
        name: t("wallet.pill", { velas: "1 Vela" }),
      }),
    ).toBeInTheDocument();
  });

  it("says the balance is loading until the wallet answers", () => {
    fakeApi({ "GET /v1/wallet": () => new Promise<Response>(() => {}) });
    renderShell("male");

    expect(
      screen.getByRole("button", { name: t("wallet.pillLoading") }),
    ).toBeInTheDocument();
  });

  it("says the balance is unavailable when the wallet fails, and still opens the store", async () => {
    fakeApi({ "GET /v1/wallet": () => envelope(500, "INTERNAL") });
    renderShell("male");

    const pill = await screen.findByRole("button", {
      name: t("wallet.pillUnavailable"),
    });
    expect(pill).not.toHaveTextContent(/\d/);
    await userEvent.click(pill);
    expect(useStoreSheet.getState().open).toBe(true);
  });

  it("shows a woman Free access, and never asks for a wallet", async () => {
    const api = fakeApi({});
    renderShell("female");

    const header = screen.getByRole("banner");
    expect(
      within(header).getByText(t("wallet.freeAccess")),
    ).toBeInTheDocument();
    expect(within(header).queryByRole("button")).not.toBeInTheDocument();
    await waitFor(() => expect(api.sent()).toEqual([]));
  });

  it("adds no link: the nav's four stay the shell's only ones", async () => {
    fakeApi({ "GET /v1/wallet": () => json(200, { balance: 3 }) });
    renderShell("male");

    await screen.findByRole("button", {
      name: t("wallet.pill", { velas: "3 Velas" }),
    });
    expect(screen.getAllByRole("link")).toHaveLength(4);
  });
});
