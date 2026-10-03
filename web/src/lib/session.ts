import { ApiError, api, csrfHeader, refreshAccessToken } from "@/lib/api";
import { useSession } from "@/store/session";

/**
 * Restoring and ending a session (T-3.10). The `(auth)` and `(app)` layouts
 * restore one on load; marketing pages never call the API, so they stay static
 * (P-37).
 */

let restoring: Promise<void> | null = null;

/**
 * Restore this page load's session from the refresh cookie, once. The API's
 * answer that there is none signs the tab out (and the screens go to /login);
 * a network failure or a 5xx says nothing about the session, so it leaves the
 * session unknown and marks the restore failed, for the screens to offer a
 * retry. A phone losing signal must not look like being signed out.
 */
export function restoreSession(): Promise<void> {
  if (useSession.getState().status !== "unknown") return Promise.resolve();
  restoring ??= refreshAccessToken()
    .then(
      () => undefined,
      (error: unknown) => {
        if (!(error instanceof ApiError && error.status < 500)) {
          useSession.getState().setRestoreFailed(true);
        }
      },
    )
    .finally(() => {
      restoring = null;
    });
  return restoring;
}

/** Try again after a failed restore. */
export function retryRestore(): Promise<void> {
  useSession.getState().setRestoreFailed(false);
  return restoreSession();
}

/**
 * End the session on the API (revoking its family and clearing both cookies,
 * D-067), then in this tab. Authenticated by the refresh cookie and `X-CSRF`,
 * so it works with an expired access token. A 401 means there was no session
 * left to end, which is what was wanted. Anything else is thrown: if the API
 * never heard, the cookies are still there, and saying "signed out" would be
 * a lie the next reload exposes.
 */
export async function logout(): Promise<void> {
  try {
    await api.post("/v1/auth/logout", { headers: csrfHeader() });
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) throw error;
  }
  useSession.getState().signOut();
}
