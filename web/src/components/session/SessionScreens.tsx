import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

/** The whole screen while the session or `Me` is on its way. */
export function SessionLoading() {
  return (
    <main className="bg-bg flex min-h-dvh items-center justify-center">
      <Spinner size={28} />
    </main>
  );
}

/**
 * Restoring failed for a reason that isn't the API's answer: no signal, a 5xx.
 * The session may well exist, so this offers a retry, never /login (T-3.10).
 */
export function SessionFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="bg-bg flex min-h-dvh items-center justify-center">
      <ErrorState
        title={t("session.restoreFailedTitle", { app: APP_NAME })}
        body={t("session.restoreFailedBody")}
        onRetry={onRetry}
      />
    </main>
  );
}
