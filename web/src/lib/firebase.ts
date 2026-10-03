import type {
  Auth,
  ConfirmationResult,
  RecaptchaVerifier,
} from "firebase/auth";

import { firebaseConfig } from "@/lib/firebase-config";

/**
 * Firebase phone sign-in, Path A (T-3.14, D-085): the only code that touches
 * the Firebase SDK (ESLint enforces it). Loaded on demand, so the SDK is
 * downloaded only by a Firebase build's sign-in screen; marketing pages never
 * ship it.
 *
 * - `initializeAuth` with in-memory persistence: Firebase's user lives in this
 *   tab's memory, never IndexedDB, and is signed out the moment our API has
 *   exchanged its token. We keep our own session (D-024).
 * - No popup or redirect resolver: phone sign-in needs neither, and without
 *   one the SDK never loads Google's apis.google.com iframe, so the CSP needs
 *   only reCAPTCHA's hosts and the two Firebase APIs (security-headers.ts).
 * - Invisible reCAPTCHA, rendered as the screen opens, so the first tap is
 *   quick. Rendering sends no SMS; `sendCode` does.
 */

/** One sign-in screen's Firebase: a reCAPTCHA widget and the code just sent. */
export type FirebasePhoneSignIn = {
  /** Text a code to `phone`, an E.164 number. Resolves once Firebase sent it. */
  sendCode: (phone: string) => Promise<void>;
  /** The ID token for the code last sent, once Firebase accepts `code`. */
  confirm: (code: string) => Promise<string>;
  /** Forget Firebase's user in this tab. */
  signOut: () => Promise<void>;
  /** Take the reCAPTCHA widget down, when the screen goes. */
  dispose: () => void;
};

let firebaseAuth: Promise<{
  auth: Auth;
  sdk: typeof import("firebase/auth");
}> | null = null;

/** The page's one Firebase Auth: `initializeAuth` may run only once. */
function loadAuth() {
  firebaseAuth ??= (async () => {
    const config = firebaseConfig();
    if (!config) throw new Error("This build has no Firebase config (D-085).");
    const [{ getApps, initializeApp }, sdk] = await Promise.all([
      import("firebase/app"),
      import("firebase/auth"),
    ]);
    const app = getApps()[0] ?? initializeApp(config);
    const auth = sdk.initializeAuth(app, {
      persistence: sdk.inMemoryPersistence,
    });
    // en.ts is English only for now (D-033); the SMS is worded in it too.
    auth.languageCode = "en";
    return { auth, sdk };
  })();
  firebaseAuth.catch(() => {
    firebaseAuth = null; // a chunk that failed to load is tried again next time
  });
  return firebaseAuth;
}

/**
 * Start Firebase on a sign-in screen. The widget renders into a child of
 * `container` of its own, so a screen opened twice never renders twice into
 * one element.
 */
export async function startFirebaseSignIn(
  container: HTMLElement,
): Promise<FirebasePhoneSignIn> {
  const { auth, sdk } = await loadAuth();
  const host = document.createElement("div");
  container.appendChild(host);
  let verifier: RecaptchaVerifier | null = new sdk.RecaptchaVerifier(
    auth,
    host,
    {
      size: "invisible",
    },
  );
  let sent: ConfirmationResult | null = null;
  try {
    await verifier.render();
  } catch (error) {
    verifier.clear();
    host.remove();
    throw error;
  }

  return {
    async sendCode(phone) {
      if (!verifier) throw new Error("This sign-in screen has closed.");
      // The SDK resets the widget after every send, so a resend reuses it.
      sent = await sdk.signInWithPhoneNumber(auth, phone, verifier);
    },
    async confirm(code) {
      if (!sent) throw new Error("No code has been sent.");
      const { user } = await sent.confirm(code);
      return user.getIdToken();
    },
    signOut: () => sdk.signOut(auth),
    dispose() {
      verifier?.clear();
      verifier = null;
      sent = null;
      host.remove();
    },
  };
}
