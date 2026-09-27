import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import { Spinner } from "./Spinner";

describe("Spinner", () => {
  it("is a status that says it is loading", () => {
    render(<Spinner />);

    expect(screen.getByRole("status")).toHaveTextContent(t("ui.loading"));
  });

  it("says what is loading when given a label", () => {
    render(<Spinner label="Loading chats" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading chats");
  });
});
