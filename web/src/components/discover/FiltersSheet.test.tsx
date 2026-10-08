import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { DiscoverFilters } from "@/lib/queries/discover";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";

import { FiltersSheet } from "./FiltersSheet";

/** Three of D-041's ten, with labels the database might say: the chips say en.ts's. */
const INTENTS = [
  { id: 1, slug: "serious", label: "db serious" },
  { id: 2, slug: "long_term", label: "db long term" },
  { id: 4, slug: "casual", label: "db casual" },
];

const NONE: DiscoverFilters = { intentIds: [], verified: false, online: false };

let client: QueryClient;

function open(applied: DiscoverFilters = NONE) {
  const onApply = vi.fn();
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <FiltersSheet applied={applied} onApply={onApply} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { onApply, onClose, dialog: screen.getByRole("dialog") };
}

const chip = (name: string) => screen.findByRole("button", { name });
const selfie = () =>
  screen.getByRole("switch", { name: t("discover.filters.selfie") });
const online = () =>
  screen.getByRole("switch", { name: t("discover.filters.online") });

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  client = makeQueryClient();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the filter sheet (T-6.9, 08-DESIGN §8)", () => {
  it("starts from the filters applied: the intents pressed, the toggles on, the count in its header", async () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    const { dialog } = open({ intentIds: [2], verified: true, online: false });

    expect(dialog).toHaveAccessibleName(t("discover.filters.title"));
    expect(await chip("Long term")).toHaveAttribute("aria-pressed", "true");
    expect(await chip("Something serious")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(selfie()).toHaveAttribute("aria-checked", "true");
    expect(online()).toHaveAttribute("aria-checked", "false");
    expect(
      within(dialog).getByText(t("discover.filters.count.other", { count: 2 })),
    ).toBeInTheDocument();
  });

  it("names each intent in en.ts's words, never the database's", async () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    open();

    expect(await chip("Casual dating")).toBeInTheDocument();
    expect(screen.queryByText(/^db /)).toBeNull();
  });

  it("says what the toggles filter on, in D-262's words", async () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    open();

    expect(selfie()).toHaveAccessibleDescription(
      t("discover.filters.selfieBody"),
    );
    expect(online()).toHaveAccessibleDescription(
      t("discover.filters.onlineBody"),
    );
    expect(screen.getByRole("dialog").textContent).not.toMatch(/verif/i);
  });

  it("holds every change as a draft, and Show people hands over exactly it", async () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    const { onApply, dialog } = open({
      intentIds: [2],
      verified: false,
      online: false,
    });

    await userEvent.click(await chip("Casual dating"));
    await userEvent.click(await chip("Long term"));
    await userEvent.click(await chip("Something serious"));
    await userEvent.click(selfie());
    await userEvent.click(online());
    expect(onApply).not.toHaveBeenCalled();
    expect(
      within(dialog).getByText(t("discover.filters.count.other", { count: 4 })),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: t("discover.filters.show") }),
    );
    expect(onApply).toHaveBeenCalledExactlyOnceWith({
      intentIds: [4, 1],
      verified: true,
      online: true,
    });
  });

  it("counts one filter as one, and none with no pill", async () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    const { dialog } = open({ intentIds: [], verified: false, online: true });

    expect(
      within(dialog).getByText(t("discover.filters.count.one")),
    ).toBeInTheDocument();
    await userEvent.click(online());
    expect(within(dialog).queryByText(/ on$/)).toBeNull();
  });

  it("Clear empties the draft and hands over nothing until Show people", async () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    const { onApply } = open({
      intentIds: [1, 4],
      verified: true,
      online: true,
    });

    await userEvent.click(
      screen.getByRole("button", { name: t("discover.filters.clear") }),
    );
    expect(onApply).not.toHaveBeenCalled();
    expect(await chip("Something serious")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(selfie()).toHaveAttribute("aria-checked", "false");
    expect(online()).toHaveAttribute("aria-checked", "false");

    await userEvent.click(
      screen.getByRole("button", { name: t("discover.filters.show") }),
    );
    expect(onApply).toHaveBeenCalledExactlyOnceWith(NONE);
  });

  it("closes from ✕ and Esc handing over nothing", async () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    const { onApply, onClose } = open();
    await userEvent.click(await chip("Casual dating"));

    await userEvent.click(screen.getByRole("button", { name: t("ui.close") }));
    await userEvent.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(2);
    expect(onApply).not.toHaveBeenCalled();
  });

  it("says when the intents couldn't load, and tries again; the toggles still work", async () => {
    let fail = true;
    fakeApi({
      "GET /v1/intents": () =>
        fail ? envelope(422, "VALIDATION_ERROR") : json(200, INTENTS),
    });
    open();

    const alert = (
      await screen.findByText(t("discover.filters.intentsFailed"))
    ).closest('[role="alert"]') as HTMLElement;
    await userEvent.click(online());
    expect(online()).toHaveAttribute("aria-checked", "true");

    fail = false;
    await userEvent.click(
      within(alert).getByRole("button", { name: t("ui.retry") }),
    );
    expect(await chip("Long term")).toBeInTheDocument();
  });
});
