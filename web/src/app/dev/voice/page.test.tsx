import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DevVoicePage from "./page";
import { fileNameOf } from "./VoiceHarness";

describe("/dev/voice (P-520)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(["production", "test"])("is not found when NODE_ENV is %s", (env) => {
    vi.stubEnv("NODE_ENV", env);

    expect(() => DevVoicePage()).toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
  });

  it("records with the app's recorder under next dev", () => {
    vi.stubEnv("NODE_ENV", "development");

    render(DevVoicePage());

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Voice recordings (P-520)",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record" })).toBeInTheDocument();
  });

  it("names a file for where it was recorded and the recorder's own length", () => {
    expect(
      fileNameOf("safari", "iphone", 59, {
        blob: new Blob(),
        contentType: "audio/mp4",
        durationMs: 58_912.6,
      }),
    ).toBe("safari-iphone-59s-58913ms.m4a");
    expect(
      fileNameOf("firefox", "mac", 5, {
        blob: new Blob(),
        contentType: "audio/ogg",
        durationMs: 5_004,
      }),
    ).toBe("firefox-mac-5s-5004ms.ogg");
  });
});
