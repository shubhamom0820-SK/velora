import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

import { InstallBanner } from "./InstallBanner";

const ANDROID =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36";
const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1";

function device({ touch = true, standalone = false, agent = ANDROID } = {}) {
  window.matchMedia = ((query: string) => ({
    matches:
      (query === "(hover: none) and (pointer: coarse)" && touch) ||
      (query === "(display-mode: standalone)" && standalone),
  })) as unknown as typeof window.matchMedia;
  vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(agent);
}

function browserOffers(): { prompt: ReturnType<typeof vi.fn> } {
  const event = new Event("beforeinstallprompt", { cancelable: true });
  const prompt = vi.fn(() => Promise.resolve());
  Object.assign(event, {
    prompt,
    userChoice: Promise.resolve({ outcome: "accepted" }),
  });
  window.dispatchEvent(event);
  return { prompt };
}

afterEach(() => {
  window.dispatchEvent(new Event("appinstalled"));
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("InstallBanner (T-9.7)", () => {
  it("offers Android's install, which opens the browser's dialog", async () => {
    device();
    const { prompt } = browserOffers();
    render(<InstallBanner />);

    expect(
      screen.getByText(t("install.banner", { app: APP_NAME })),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: t("install.action") }),
    );

    expect(prompt).toHaveBeenCalledOnce();
    expect(
      screen.queryByText(t("install.banner", { app: APP_NAME })),
    ).not.toBeInTheDocument();
  });

  it("tells an iPhone the steps, with no Install button", () => {
    device({ agent: IPHONE });
    render(<InstallBanner />);

    expect(
      screen.getByText(t("install.ios", { app: APP_NAME })),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("install.action") }),
    ).not.toBeInTheDocument();
  });

  it("closes from its labelled button, by keyboard too, and stays closed", async () => {
    device({ agent: IPHONE });
    const { unmount } = render(<InstallBanner />);

    await userEvent.tab();
    expect(
      screen.getByRole("button", { name: t("install.dismiss") }),
    ).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(
      screen.queryByText(t("install.ios", { app: APP_NAME })),
    ).not.toBeInTheDocument();

    unmount();
    const { container } = render(<InstallBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it.each([
    ["a desktop", { touch: false }],
    ["an installed app", { standalone: true }],
  ])("draws nothing on %s", (_, shape) => {
    device(shape);
    browserOffers();
    const { container } = render(<InstallBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("draws nothing on Android before the browser offers", () => {
    device();
    const { container } = render(<InstallBanner />);
    expect(container).toBeEmptyDOMElement();
  });
});
