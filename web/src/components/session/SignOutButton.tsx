"use client";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import { useSignOut } from "@/lib/queries/session";

type SignOutButtonProps = {
  /** "Sign out" unless given, as on the lock screen's "Forgot your PIN?". */
  label?: string;
  /** `chrome` on the black lock screen (08-DESIGN §1). */
  tone?: "light" | "chrome";
};

/**
 * A quiet way out (T-3.10): on the lock screen, which D-069's forgotten PIN
 * needs, and in the onboarding frame (T-3.11). Until it hears back, the
 * session stays: a sign-out the API never heard isn't one.
 */
export function SignOutButton({ label, tone = "light" }: SignOutButtonProps) {
  const signOut = useSignOut();
  const chrome = tone === "chrome";
  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        aria-busy={signOut.isPending || undefined}
        onClick={() => {
          if (!signOut.isPending) signOut.mutate();
        }}
        className={cx(
          "text-small underline underline-offset-2",
          chrome ? "text-chrome-mute" : "text-mute",
          "focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2",
        )}
      >
        {label ?? t("session.signOut")}
      </button>
      {signOut.isError && (
        <p
          role="alert"
          className={cx(
            "text-small",
            chrome ? "text-chrome-accent" : "text-accent",
          )}
        >
          {t("session.signOutFailed")}
        </p>
      )}
    </div>
  );
}
