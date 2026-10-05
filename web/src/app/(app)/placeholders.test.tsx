import { render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import ChatsPage from "./chats/page";
import DiscoverPage from "./discover/page";
import YouPage from "./you/page";

// One route per place in the shell's nav, each a placeholder until its task
// (T-5.6); Wallet's is built (T-5.5). They render inside the shell's <main>,
// so none brings its own.
describe("the app's placeholder routes", () => {
  it.each<[string, ComponentType]>([
    ["Discover", DiscoverPage],
    ["Chats", ChatsPage],
    ["You", YouPage],
  ])("%s says what it is and that it's coming", (name, Page) => {
    render(<Page />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(name);
    expect(screen.getByText(t("placeholder.comingSoon"))).toBeInTheDocument();
    expect(screen.queryByRole("main")).not.toBeInTheDocument();
  });
});
