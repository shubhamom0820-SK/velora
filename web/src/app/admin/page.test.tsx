import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import AdminPage from "./page";

describe("/admin", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(["production", "test"])("is not found when NODE_ENV is %s", (env) => {
    vi.stubEnv("NODE_ENV", env);

    expect(() => AdminPage()).toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
  });

  it("shows the placeholder under next dev", () => {
    vi.stubEnv("NODE_ENV", "development");

    render(AdminPage());

    expect(
      screen.getByRole("heading", { level: 1, name: t("placeholder.admin") }),
    ).toBeInTheDocument();
  });
});
