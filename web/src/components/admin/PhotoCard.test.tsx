import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { AdminPhoto } from "@/lib/queries/admin";
import { fakeApi } from "@/lib/testing/fakeApi";

import { PhotoCard } from "./PhotoCard";

const NOTE = "Shows more than the rules allow.";

function photo(overrides: Partial<AdminPhoto> = {}): AdminPhoto {
  return {
    id: "p1",
    user_id: "u1",
    kind: "public",
    position: 1,
    status: "pending",
    reject_reason: null,
    minor_score: 0.12,
    url: "https://photos.test/p1.jpg",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderCard(shown: AdminPhoto) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <PhotoCard photo={shown} />
    </QueryClientProvider>,
  );
}

const decided = () => new Response(null, { status: 204 });

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("a photo for staff (D-925)", () => {
  it("shows the model's minor score (D-101)", () => {
    fakeApi({});
    renderCard(photo());

    expect(
      screen.getByText(t("admin.photos.minorScore", { score: "0.12" })),
    ).toBeInTheDocument();
  });

  it("approves a pending photo with nothing else sent", async () => {
    const api = fakeApi({ "POST /v1/admin/photos/p1/decide": decided });
    renderCard(photo());

    await userEvent.click(
      screen.getByRole("button", { name: t("admin.photos.approve") }),
    );

    await waitFor(() => expect(api.calls[0]?.body).toEqual({ approve: true }));
  });

  it("takes one down only with a reason picked and a note", async () => {
    const api = fakeApi({ "POST /v1/admin/photos/p1/decide": decided });
    renderCard(photo({ status: "approved" }));

    expect(
      screen.queryByRole("button", { name: t("admin.photos.approve") }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: t("admin.photos.reject") }),
    );
    const sheet = screen.getByRole("dialog");
    const confirm = within(sheet).getByRole("button", {
      name: t("admin.photos.reject"),
    });
    await userEvent.type(
      within(sheet).getByLabelText(t("admin.confirm.reason")),
      NOTE,
    );
    expect(confirm).toBeDisabled();
    await userEvent.click(
      within(sheet).getByRole("button", {
        name: t("admin.photos.reasons.nudity"),
      }),
    );
    await userEvent.click(confirm);

    await waitFor(() =>
      expect(api.calls[0]?.body).toEqual({
        approve: false,
        reason: "nudity",
        note: NOTE,
      }),
    );
  });

  it("offers nothing for a photo already taken down", () => {
    fakeApi({});
    renderCard(photo({ status: "rejected", reject_reason: "nudity" }));

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
