import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { queryKeys } from "@/lib/queries/keys";

import { AdminFrame } from "./AdminFrame";

vi.mock("next/navigation", () => ({ usePathname: () => "/admin/reports" }));

function renderFrame(role: "moderator" | "admin") {
  const client = new QueryClient();
  client.setQueryData(queryKeys.me(), { id: "s1", role });
  render(
    <QueryClientProvider client={client}>
      <AdminFrame>
        <p>Inside</p>
      </AdminFrame>
    </QueryClientProvider>,
  );
}

describe("the panel's frame (D-920)", () => {
  it("marks where staff are, and keeps claims an admin's", () => {
    renderFrame("moderator");

    expect(
      screen.getByRole("link", { name: t("admin.nav.reports") }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.queryByRole("link", { name: t("admin.nav.claims") }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Inside")).toBeInTheDocument();
  });

  it("shows an admin the claims", () => {
    renderFrame("admin");

    expect(
      screen.getByRole("link", { name: t("admin.nav.claims") }),
    ).toHaveAttribute("href", "/admin/claims");
  });
});
