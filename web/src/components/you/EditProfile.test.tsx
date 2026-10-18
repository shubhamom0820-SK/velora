import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";

import { EditProfile } from "./EditProfile";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const ABOUT = "Reads on trains, cooks on Sundays, walks everywhere she can.";

function me() {
  return {
    id: "u1",
    status: "active",
    gender: "female",
    profile: {
      first_name: "Priya",
      hometown: "Jalandhar",
      city: "Phagwara",
      about: ABOUT,
      seeking: "men",
      intent_ids: [1],
      interest_ids: [1, 2, 3, 4, 5],
    },
  };
}

const INTENTS = [1, 2, 3, 4].map((id) => ({ id, label: `Intent ${id}` }));
const INTERESTS = [1, 2, 3, 4, 5, 6].map((id) => ({
  id,
  label: `Interest ${id}`,
}));

/** A chip's words: `en.ts`'s by id (P-26), as the screen reads them. */
const intent = (id: keyof typeof en.intents) => en.intents[id];
const interest = (id: keyof typeof en.interests) => en.interests[id];

function routes(overrides: Record<string, Route> = {}) {
  return fakeApi({
    "GET /v1/intents": () => json(200, INTENTS),
    "GET /v1/interests": () => json(200, INTERESTS),
    ...overrides,
  });
}

function renderEdit() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(queryKeys.me(), me());
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <EditProfile />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  push.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("edit profile (T-9.8)", () => {
  it("sends only what changed, then goes back to You", async () => {
    const api = routes({
      "PATCH /v1/me/profile": () => json(200, me()),
    });
    renderEdit();

    const city = screen.getByLabelText(t("onboarding.name.city"));
    await userEvent.clear(city);
    await userEvent.type(city, "Jalandhar");
    await userEvent.click(
      screen.getByRole("button", { name: t("you.editSave") }),
    );

    await waitFor(() => expect(push).toHaveBeenCalledWith("/you"));
    expect(api.sent()).toEqual(
      expect.arrayContaining(["PATCH /v1/me/profile"]),
    );
    expect(api.sent()).not.toContain("POST /v1/me/seeking");
    expect(api.sent()).not.toContain("PUT /v1/me/interests");
    expect(api.calls.find((c) => c.method === "PATCH")?.body).toEqual({
      city: "Jalandhar",
    });
  });

  it("sends new intents with the seeking as it is, and new interests", async () => {
    const api = routes({
      "POST /v1/me/seeking": () => json(200, me()),
      "PUT /v1/me/interests": () => json(200, me()),
    });
    renderEdit();

    await userEvent.click(
      await screen.findByRole("button", { name: intent("2") }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: interest("5") }),
    );
    await userEvent.click(screen.getByRole("button", { name: interest("6") }));
    await userEvent.click(
      screen.getByRole("button", { name: t("you.editSave") }),
    );

    await waitFor(() => expect(push).toHaveBeenCalledWith("/you"));
    expect(api.calls.find((c) => c.path === "/v1/me/seeking")?.body).toEqual({
      seeking: "men",
      intent_ids: [1, 2],
    });
    expect(api.calls.find((c) => c.path === "/v1/me/interests")?.body).toEqual({
      interest_ids: [1, 2, 3, 4, 6],
    });
    expect(api.sent()).not.toContain("PATCH /v1/me/profile");
  });

  it("can't save with fewer than five interests", async () => {
    routes();
    renderEdit();

    await userEvent.click(
      await screen.findByRole("button", { name: interest("5") }),
    );
    expect(
      screen.getByRole("button", { name: t("you.editSave") }),
    ).toBeDisabled();
  });

  it.each([
    ["", "an emptied bio as none"],
    ["Chai.", "a short bio as written"],
  ])("saves %j: %s (D-951)", async (written) => {
    const api = routes({ "PATCH /v1/me/profile": () => json(200, me()) });
    renderEdit();

    const about = screen.getByLabelText(t("onboarding.about.label"));
    await userEvent.clear(about);
    if (written) await userEvent.type(about, written);
    await userEvent.click(
      screen.getByRole("button", { name: t("you.editSave") }),
    );

    await waitFor(() => expect(push).toHaveBeenCalledWith("/you"));
    expect(api.calls.find((c) => c.method === "PATCH")?.body).toEqual({
      about: written,
    });
  });

  it("shows the server's refusal beside its field (VALIDATION_ERROR), and stays", async () => {
    routes({
      "PATCH /v1/me/profile": () =>
        envelope(400, "VALIDATION_ERROR", { fields: [{ field: "about" }] }),
    });
    renderEdit();

    const about = screen.getByLabelText(t("onboarding.about.label"));
    await userEvent.type(about, " Call me on 98765 43210 any time at all.");
    await userEvent.click(
      screen.getByRole("button", { name: t("you.editSave") }),
    );

    expect(
      await screen.findByText(t("apiErrors.fields.about")),
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("says when the catalogues didn't load", async () => {
    routes({
      "GET /v1/intents": () => envelope(500, "INTERNAL"),
      "GET /v1/interests": () => envelope(500, "INTERNAL"),
    });
    renderEdit();

    expect(
      await screen.findAllByRole("button", { name: t("ui.retry") }),
    ).toHaveLength(2);
  });
});
