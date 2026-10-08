import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { t } from "@/i18n/t";
import type { AlbumRequest } from "@/lib/queries/album";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { IncomingRequests } from "./IncomingRequests";

function request(overrides: Partial<AlbumRequest> = {}): AlbumRequest {
  return {
    id: "r1",
    owner_id: "u1",
    status: "pending",
    created_at: "2026-10-09T10:00:00Z",
    decided_at: null,
    requester: {
      id: "u2",
      first_name: "Arjun",
      username: "arjun.s",
      main_photo_url: "https://cdn.test/p/u2.jpg",
      shows_badge: false,
      is_online: false,
      deleted: false,
    },
    ...overrides,
  };
}

function page(items: AlbumRequest[], next_cursor: string | null = null) {
  return json(200, { items, next_cursor });
}

function routes(list: Route, overrides: Record<string, Route> = {}) {
  return fakeApi({ "GET /v1/album-requests/incoming": list, ...overrides });
}

function renderList() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <IncomingRequests />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const row = async (name: string) =>
  (await screen.findByRole("link", { name })).closest("li") as HTMLElement;

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

describe("album requests (T-8.8, D-732)", () => {
  it("lists who asked, each linking to their profile, never what they paid", async () => {
    routes(() =>
      page([
        request(),
        request({
          id: "r2",
          status: "granted",
          requester: { ...request().requester, id: "u3", first_name: "Kabir" },
        }),
      ]),
    );
    renderList();

    const arjun = await row("Arjun");
    expect(within(arjun).getByRole("link")).toHaveAttribute(
      "href",
      "/people/u2",
    );
    expect(within(arjun).getByText(t("albumRequests.wants"))).toBeVisible();
    const kabir = await row("Kabir");
    expect(within(kabir).getByText(t("albumRequests.sees"))).toBeVisible();
    expect(
      within(kabir).getByRole("button", { name: t("albumRequests.revoke") }),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Vela/);
  });

  it.each([
    [true, "albumRequests.grant", "albumRequests.granted"],
    [false, "albumRequests.decline", "albumRequests.declined"],
  ] as const)(
    "sends grant: %s, says so and asks for the list again",
    async (grant, button, said) => {
      let answered = false;
      const api = routes(() => page(answered && !grant ? [] : [request()]), {
        "POST /v1/album-requests/r1/decide": (call) => {
          expect(call.body).toEqual({ grant });
          answered = true;
          return json(200, request({ status: grant ? "granted" : "declined" }));
        },
      });
      renderList();

      await userEvent.click(
        within(await row("Arjun")).getByRole("button", { name: t(button) }),
      );

      expect(await screen.findByText(t(said))).toBeInTheDocument();
      await waitFor(() =>
        expect(
          api.sent().filter((s) => s === "GET /v1/album-requests/incoming"),
        ).toHaveLength(2),
      );
    },
  );

  it("asks before it stops sharing, and Cancel stops nothing", async () => {
    const api = routes(() => page([request({ status: "granted" })]), {
      "POST /v1/album-requests/r1/revoke": () =>
        new Response(null, { status: 204 }),
    });
    renderList();

    await userEvent.click(
      within(await row("Arjun")).getByRole("button", {
        name: t("albumRequests.revoke"),
      }),
    );
    const sheet = await screen.findByRole("dialog", {
      name: t("albumRequests.revokeTitle", { name: "Arjun" }),
    });
    expect(
      within(sheet).getByText(t("albumRequests.revokeBody")),
    ).toBeVisible();
    await userEvent.click(
      within(sheet).getByRole("button", { name: t("albumRequests.cancel") }),
    );
    expect(api.sent()).not.toContain("POST /v1/album-requests/r1/revoke");

    await userEvent.click(
      within(await row("Arjun")).getByRole("button", {
        name: t("albumRequests.revoke"),
      }),
    );
    await userEvent.click(
      within(
        await screen.findByRole("dialog", {
          name: t("albumRequests.revokeTitle", { name: "Arjun" }),
        }),
      ).getByRole("button", { name: t("albumRequests.revoke") }),
    );

    expect(
      await screen.findByText(t("albumRequests.revoked")),
    ).toBeInTheDocument();
    expect(api.sent()).toContain("POST /v1/album-requests/r1/revoke");
  });

  it("says a request already answered in words, and asks for the list again", async () => {
    const api = routes(() => page([request()]), {
      "POST /v1/album-requests/r1/decide": () =>
        envelope(422, "NOT_ALLOWED", { why: "already_decided" }),
    });
    renderList();

    await userEvent.click(
      within(await row("Arjun")).getByRole("button", {
        name: t("albumRequests.decline"),
      }),
    );

    expect(
      await screen.findByText(t("albumRequests.alreadyAnswered")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/already_decided|NOT_ALLOWED/)).toBeNull();
    await waitFor(() =>
      expect(
        api.sent().filter((s) => s === "GET /v1/album-requests/incoming"),
      ).toHaveLength(2),
    );
  });

  it("says a request that is gone is gone", async () => {
    routes(() => page([request()]), {
      "POST /v1/album-requests/r1/decide": () => envelope(404, "NOT_FOUND"),
    });
    renderList();

    await userEvent.click(
      within(await row("Arjun")).getByRole("button", {
        name: t("albumRequests.grant"),
      }),
    );

    expect(
      await screen.findByText(t("albumRequests.gone")),
    ).toBeInTheDocument();
  });

  it("names a deleted account as one, with no link, and still lets her answer", async () => {
    routes(() =>
      page([
        request({
          requester: {
            id: "u2",
            first_name: null,
            username: null,
            main_photo_url: null,
            shows_badge: false,
            is_online: false,
            deleted: true,
          },
        }),
      ]),
    );
    renderList();

    const item = (
      await screen.findAllByText(t("albumRequests.deleted"))
    )[0]?.closest("li") as HTMLElement;
    expect(within(item).queryByRole("link")).toBeNull();
    expect(
      within(item).getByRole("button", { name: t("albumRequests.decline") }),
    ).toBeInTheDocument();
  });

  it("says when there are none", async () => {
    routes(() => page([]));
    renderList();

    expect(
      await screen.findByText(t("albumRequests.empty")),
    ).toBeInTheDocument();
    expect(screen.getByText(t("albumRequests.emptyBody"))).toBeInTheDocument();
  });

  it("says when it failed, and tries again", async () => {
    let fail = true;
    routes(() => (fail ? envelope(500, "INTERNAL") : page([request()])));
    renderList();

    expect(
      await screen.findByText(t("albumRequests.loadFailed"), undefined, {
        timeout: 5000,
      }),
    ).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: t("ui.retry") }));

    expect(await row("Arjun")).toBeInTheDocument();
  });

  it("asks for a page at a time, from its cursor", async () => {
    const api = routes((call) =>
      call.query.get("cursor") === "c2"
        ? page([
            request({
              id: "r2",
              requester: {
                ...request().requester,
                id: "u3",
                first_name: "Kabir",
              },
            }),
          ])
        : page([request()], "c2"),
    );
    let fire: (() => void) | undefined;
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(
          callback: (entries: { isIntersecting: boolean }[]) => void,
        ) {
          fire = () => callback([{ isIntersecting: true }]);
        }
        observe() {}
        disconnect() {}
      },
    );
    renderList();

    await row("Arjun");
    fire?.();

    expect(await row("Kabir")).toBeInTheDocument();
    expect(api.calls[0]?.query.get("limit")).toBe("20");
    expect(api.calls[1]?.query.get("cursor")).toBe("c2");
  });
});
