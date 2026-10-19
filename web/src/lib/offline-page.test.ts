import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { render } from "@testing-library/react";
import { WifiOff } from "lucide-react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import { APP_NAME } from "./app";
import { WIFI_OFF_PATHS, offlinePage } from "./offline-page";

const TOKENS = readFileSync("src/styles/tokens.css", "utf8");
const PAGE = offlinePage(TOKENS);

function parsed(): Document {
  return new DOMParser().parseFromString(PAGE.html, "text/html");
}

describe("the offline page (T-9.7, D-1040)", () => {
  it("says the founder's words, from en.ts", () => {
    const page = parsed();
    expect(page.querySelector("h1")?.textContent).toBe(t("offline.title"));
    expect(page.querySelector("p")?.textContent).toBe(
      t("offline.body", { app: APP_NAME }),
    );
    expect(page.title).toBe(`${t("offline.title")} · ${APP_NAME}`);
    expect(page.documentElement.lang).toBe("en");
  });

  it("tries again at its own address, writing no URL into the page", () => {
    const links = parsed().querySelectorAll("a");
    expect(links).toHaveLength(1);
    expect(links[0]?.getAttribute("href")).toBe("");
    expect(links[0]?.textContent).toBe(t("offline.retry"));
  });

  it("runs no script and loads nothing", () => {
    const page = parsed();
    expect(page.querySelectorAll("script, link, img, iframe")).toHaveLength(0);
    expect(PAGE.html).not.toMatch(/\son\w+=/i);
    expect(PAGE.html).not.toMatch(/\sstyle=/i);
  });

  it("allows nothing but its one style block, by its hash", () => {
    const styles = parsed().querySelectorAll("style");
    expect(styles).toHaveLength(1);
    const hash = createHash("sha256")
      .update(styles[0]?.textContent ?? "", "utf8")
      .digest("base64");
    expect(PAGE.csp).toBe(
      `default-src 'none'; style-src 'sha256-${hash}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
    );
  });

  it("is drawn with tokens.css itself, adding no colour of its own", () => {
    const style = parsed().querySelector("style")?.textContent ?? "";
    expect(style.startsWith(TOKENS)).toBe(true);
    const own = style.slice(TOKENS.length);
    expect(own).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    for (const token of ["--chrome", "--chrome-ink", "--chrome-mute"]) {
      expect(own).toContain(`var(${token})`);
    }
  });

  it("draws Lucide's wifi-off exactly as lucide-react does", () => {
    const { container } = render(createElement(WifiOff));
    const lucide = [...container.querySelectorAll("path")].map((path) =>
      path.getAttribute("d"),
    );
    expect(WIFI_OFF_PATHS).toEqual(lucide);
  });
});
