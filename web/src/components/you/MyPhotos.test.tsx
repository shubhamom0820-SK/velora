import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { Photo } from "@/lib/queries/photos";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { MyPhotos } from "./MyPhotos";

function me(overrides: Record<string, unknown> = {}) {
  return {
    id: "u1",
    status: "active",
    onboarding_step: "done",
    gender: "female",
    is_verified: true,
    profile: {},
    ...overrides,
  };
}

function photo(overrides: Partial<Photo> = {}): Photo {
  return {
    id: "p1",
    kind: "public",
    position: 0,
    status: "approved",
    reject_reason: null,
    url: "https://cdn.test/p/p1.jpg",
    from_photo_id: null,
    ...overrides,
  };
}

const FACE = photo({
  id: "f1",
  kind: "verification",
  position: null,
  url: "https://storage.test/velora-private/raw/u1/f1?sig=s",
});

function renderPhotos(person = me()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(["me"], person);
  render(
    <QueryClientProvider client={client}>
      <MyPhotos />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("your photos (T-9.8)", () => {
  it("shows the photos step's grid and face slot, with the badge's rule (D-910)", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, [photo(), FACE]) });
    renderPhotos();

    expect(
      await screen.findByRole("list", { name: t("onboarding.photos.grid") }),
    ).toBeInTheDocument();
    expect(screen.getByText(t("you.photosHint"))).toBeInTheDocument();
  });

  it("locks a matched person's face photo: no way to swap it (the founder's condition)", async () => {
    const api = fakeApi({
      "GET /v1/me/photos": () => json(200, [photo(), FACE]),
    });
    renderPhotos(me({ is_verified: true }));

    const slot = await screen.findByRole("region", {
      name: t("onboarding.photos.face.title"),
    });
    expect(
      await within(slot).findByText(t("onboarding.photos.face.locked")),
    ).toBeInTheDocument();
    expect(within(slot).queryAllByRole("button")).toEqual([]);
    expect(api.sent().filter((s) => !s.startsWith("GET "))).toEqual([]);
  });

  it("lets a man with no selfie match add or change his face photo", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, [photo()]) });
    renderPhotos(me({ gender: "male", is_verified: false }));

    const slot = await screen.findByRole("region", {
      name: t("onboarding.photos.face.title"),
    });
    expect(
      within(slot).getByRole("button", {
        name: t("onboarding.photos.face.add"),
      }),
    ).toBeInTheDocument();
  });

  it("never leaves the photos step: nothing calls /me/photos/done", async () => {
    const api = fakeApi({
      "GET /v1/me/photos": () => json(200, [photo()]),
      "DELETE /v1/photos/p1": () => new Response(null, { status: 204 }),
    });
    renderPhotos();

    await screen.findByRole("list", { name: t("onboarding.photos.grid") });
    expect(
      screen.queryByRole("button", { name: t("onboarding.continue") }),
    ).toBeNull();
    expect(api.sent()).not.toContain("POST /v1/me/photos/done");
  });

  it("says when the photos didn't load, and tries again", async () => {
    let fail = true;
    fakeApi({
      "GET /v1/me/photos": () =>
        fail ? envelope(500, "INTERNAL") : json(200, [photo()]),
    });
    renderPhotos();

    await screen.findByText(t("onboarding.photos.loadFailed"));
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: t("ui.retry") }));

    await waitFor(() =>
      expect(
        screen.getByRole("list", { name: t("onboarding.photos.grid") }),
      ).toBeInTheDocument(),
    );
  });
});
