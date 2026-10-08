import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { SearchResult } from "@/lib/queries/search";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { SearchScreen } from "./SearchScreen";

function person(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    id: "u1",
    first_name: "Priya",
    age: 24,
    username: "priya",
    city: "Phagwara",
    main_photo_url: null,
    shows_badge: false,
    is_online: false,
    exact: false,
    ...overrides,
  };
}

function routes(search: Route) {
  return fakeApi({ "GET /v1/search": search });
}

function renderSearch() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SearchScreen />
    </QueryClientProvider>,
  );
}

const field = () => screen.getByRole("searchbox", { name: t("search.label") });
/** The results for `q`, once they have loaded (or failed). */
async function results(q: string): Promise<HTMLElement> {
  const region = await screen.findByRole("region", {
    name: t("search.resultsFor", { q }),
  });
  await waitFor(() => expect(region).toHaveAttribute("aria-busy", "false"));
  return region;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
      takeRecords() {
        return [];
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("search (T-6.6)", () => {
  it("says what it searches before anything is typed, and asks nothing", async () => {
    const api = routes(() => json(200, { items: [], next_cursor: null }));
    renderSearch();

    expect(screen.getByText(t("search.hint"))).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(api.sent()).toEqual([]);
  });

  it("asks once typing pauses, not for each letter", async () => {
    const api = routes(() => json(200, { items: [], next_cursor: null }));
    renderSearch();

    await userEvent.type(field(), "Simran");

    await results("Simran");
    expect(api.calls.map((call) => call.query.get("q"))).toEqual(["Simran"]);
  });

  it("finds a username in @ mode, lowercased, the exact one marked", async () => {
    const api = routes(() =>
      json(200, {
        items: [
          person({ id: "a", username: "priya", exact: true }),
          person({ id: "b", username: "priya.k", first_name: "Priyanka" }),
        ],
        next_cursor: null,
      }),
    );
    renderSearch();

    await userEvent.type(field(), "@Priya");

    const list = await results("@priya");
    expect(api.calls.map((call) => call.query.get("q"))).toEqual(["@priya"]);
    expect(
      within(list).getByText(t("search.usernameMode")),
    ).toBeInTheDocument();
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    const [exact, prefix] = rows as [HTMLElement, HTMLElement];
    expect(within(exact).getByText(t("search.exact"))).toBeInTheDocument();
    expect(within(prefix).queryByText(t("search.exact"))).toBeNull();
    expect(
      within(prefix).getByText(
        t("search.usernameCity", { username: "priya.k", city: "Phagwara" }),
      ),
    ).toBeInTheDocument();
  });

  it("says why, and asks nothing, for a query the API would refuse", async () => {
    const api = routes(() => json(200, { items: [], next_cursor: null }));
    renderSearch();

    await userEvent.type(field(), "s");
    expect(
      await screen.findByText(t("search.tooShort", { min: 2 })),
    ).toBeInTheDocument();
    await userEvent.clear(field());
    await userEvent.type(field(), "@pri ya");
    expect(
      await screen.findByText(t("search.badUsername")),
    ).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 400));

    expect(api.sent()).toEqual([]);
  });

  it("shows the name alone when the age is hidden, and the username alone without a city", async () => {
    routes(() =>
      json(200, {
        items: [person({ age: null, city: null, username: "noor_s" })],
        next_cursor: null,
      }),
    );
    renderSearch();

    await userEvent.type(field(), "Priya");

    const row = within(await results("Priya")).getByRole("listitem");
    expect(within(row).getByText("Priya")).toBeInTheDocument();
    expect(within(row).getByText("@noor_s")).toBeInTheDocument();
  });

  it("shows the badge only where the API says it shows (D-393)", async () => {
    routes(() =>
      json(200, {
        items: [
          person({ id: "a", first_name: "Asha", shows_badge: true }),
          person({ id: "b", first_name: "Bina", shows_badge: false }),
        ],
        next_cursor: null,
      }),
    );
    renderSearch();

    await userEvent.type(field(), "Kapur");
    await results("Kapur");

    expect(
      screen.getByRole("img", { name: `Asha, ${t("ui.selfieMatched")}` }),
    ).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Bina" })).toBeInTheDocument();
  });

  it("renders another person's text as text, never as markup", async () => {
    const name = '<img src="x" onerror="window.__pwned=1">';
    routes(() =>
      json(200, {
        items: [person({ first_name: name, age: null })],
        next_cursor: null,
      }),
    );
    renderSearch();

    await userEvent.type(field(), "img");

    const list = await results("img");
    expect(within(list).getByText(name)).toBeInTheDocument();
    expect(list.querySelector('img[src="x"]')).toBeNull();
  });

  it("says when no one is found", async () => {
    routes(() => json(200, { items: [], next_cursor: null }));
    renderSearch();

    await userEvent.type(field(), "Zoravar");

    expect(
      within(await results("Zoravar")).getByText(t("search.empty")),
    ).toBeInTheDocument();
  });

  it("says when the search failed, and tries again", async () => {
    let fail = true;
    routes(() =>
      fail
        ? envelope(500, "INTERNAL")
        : json(200, { items: [person()], next_cursor: null }),
    );
    renderSearch();

    await userEvent.type(field(), "Priya");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(t("search.failed"));
    fail = false;
    await act(async () => {
      await userEvent.click(
        within(alert).getByRole("button", { name: t("ui.retry") }),
      );
    });

    expect(
      within(await results("Priya")).getByRole("listitem"),
    ).toBeInTheDocument();
  });
});
