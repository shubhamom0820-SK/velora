import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { firebaseConfigFor } from "./firebase-config";

/**
 * src/lib/firebase.ts against a stand-in SDK: what it asks of Firebase, in
 * what order, and what it leaves behind (T-3.14, D-085). The real SDK can't
 * run in jsdom; staging's sign-in is where it runs for real.
 */

const sdk = vi.hoisted(() => {
  const state = {
    initializeAuth: vi.fn(),
    verifiers: [] as {
      host: HTMLElement;
      options: unknown;
      render: ReturnType<typeof vi.fn>;
      clear: ReturnType<typeof vi.fn>;
    }[],
    renderError: null as Error | null,
    signInWithPhoneNumber: vi.fn(),
    confirm: vi.fn(),
    signOut: vi.fn(),
    auth: { languageCode: null as string | null },
  };
  return state;
});

vi.mock("firebase/app", () => ({
  getApps: () => [],
  initializeApp: vi.fn((config: unknown) => ({ config })),
}));

vi.mock("firebase/auth", () => ({
  inMemoryPersistence: { type: "NONE" },
  initializeAuth: (...args: unknown[]) => {
    sdk.initializeAuth(...args);
    return sdk.auth;
  },
  RecaptchaVerifier: class {
    render: ReturnType<typeof vi.fn>;
    clear = vi.fn();
    constructor(_auth: unknown, host: HTMLElement, options: unknown) {
      this.render = vi.fn(async () => {
        if (sdk.renderError) throw sdk.renderError;
        return 0;
      });
      sdk.verifiers.push({
        host,
        options,
        render: this.render,
        clear: this.clear,
      });
    }
  },
  signInWithPhoneNumber: (...args: unknown[]) => {
    sdk.signInWithPhoneNumber(...args);
    return Promise.resolve({ confirm: sdk.confirm });
  },
  signOut: (...args: unknown[]) => {
    sdk.signOut(...args);
    return Promise.resolve();
  },
}));

async function load() {
  vi.resetModules();
  return import("./firebase");
}

beforeEach(() => {
  vi.stubEnv(
    "FIREBASE_WEB_CONFIG",
    JSON.stringify(firebaseConfigFor({ APP_ENV: "staging" })),
  );
  sdk.initializeAuth.mockReset();
  sdk.signInWithPhoneNumber.mockReset();
  sdk.signOut.mockReset();
  sdk.confirm.mockReset();
  sdk.confirm.mockResolvedValue({
    user: { getIdToken: async () => "firebase-id-token" },
  });
  sdk.verifiers = [];
  sdk.renderError = null;
  sdk.auth.languageCode = null;
});

afterEach(() => {
  vi.unstubAllEnvs();
  document.body.replaceChildren();
});

describe("starting Firebase on the sign-in screen", () => {
  it("keeps Firebase's user in memory and loads no popup resolver", async () => {
    const { startFirebaseSignIn } = await load();

    await startFirebaseSignIn(document.body);

    expect(sdk.initializeAuth).toHaveBeenCalledTimes(1);
    const [, deps] = sdk.initializeAuth.mock.calls[0] ?? [];
    expect(deps).toEqual({ persistence: { type: "NONE" } });
    expect(deps).not.toHaveProperty("popupRedirectResolver");
    expect(sdk.auth.languageCode).toBe("en");
  });

  it("renders an invisible reCAPTCHA into a child of its own, sending nothing", async () => {
    const { startFirebaseSignIn } = await load();
    const container = document.createElement("div");
    document.body.append(container);

    await startFirebaseSignIn(container);

    const [verifier] = sdk.verifiers;
    expect(verifier?.options).toEqual({ size: "invisible" });
    expect(verifier?.host.parentElement).toBe(container);
    expect(verifier?.render).toHaveBeenCalledTimes(1);
    expect(sdk.signInWithPhoneNumber).not.toHaveBeenCalled();
  });

  it("initialises Firebase once however many screens open", async () => {
    const { startFirebaseSignIn } = await load();

    await startFirebaseSignIn(document.body);
    await startFirebaseSignIn(document.body);

    expect(sdk.initializeAuth).toHaveBeenCalledTimes(1);
    expect(sdk.verifiers.map((v) => v.host)).toHaveLength(2);
    expect(sdk.verifiers[0]?.host).not.toBe(sdk.verifiers[1]?.host);
  });

  it("refuses on a build with no config, never a guessed project", async () => {
    vi.stubEnv("FIREBASE_WEB_CONFIG", "");
    const { startFirebaseSignIn } = await load();

    await expect(startFirebaseSignIn(document.body)).rejects.toThrow(
      "This build has no Firebase config (D-085).",
    );
    expect(sdk.initializeAuth).not.toHaveBeenCalled();
  });

  it("takes its widget down if reCAPTCHA can't render", async () => {
    sdk.renderError = new Error("blocked");
    const { startFirebaseSignIn } = await load();
    const container = document.createElement("div");

    await expect(startFirebaseSignIn(container)).rejects.toThrow("blocked");
    expect(sdk.verifiers[0]?.clear).toHaveBeenCalledTimes(1);
    expect(container.childElementCount).toBe(0);
  });
});

describe("a sign-in through it", () => {
  it("sends the code, confirms it, hands back the ID token and signs out", async () => {
    const { startFirebaseSignIn } = await load();
    const signIn = await startFirebaseSignIn(document.body);

    await signIn.sendCode("+919876543210");
    const token = await signIn.confirm("123456");
    await signIn.signOut();

    const [auth, phone, verifier] =
      sdk.signInWithPhoneNumber.mock.calls[0] ?? [];
    expect([auth, phone]).toEqual([sdk.auth, "+919876543210"]);
    expect(verifier).toBeDefined();
    expect(sdk.confirm).toHaveBeenCalledWith("123456");
    expect(token).toBe("firebase-id-token");
    expect(sdk.signOut).toHaveBeenCalledWith(sdk.auth);
  });

  it("confirms nothing before a code was sent", async () => {
    const { startFirebaseSignIn } = await load();
    const signIn = await startFirebaseSignIn(document.body);

    await expect(signIn.confirm("123456")).rejects.toThrow(
      "No code has been sent.",
    );
  });

  it("is gone once disposed: the widget cleared and its element removed", async () => {
    const { startFirebaseSignIn } = await load();
    const container = document.createElement("div");
    const signIn = await startFirebaseSignIn(container);

    signIn.dispose();

    expect(sdk.verifiers[0]?.clear).toHaveBeenCalledTimes(1);
    expect(container.childElementCount).toBe(0);
    await expect(signIn.sendCode("+919876543210")).rejects.toThrow(
      "This sign-in screen has closed.",
    );
  });
});
