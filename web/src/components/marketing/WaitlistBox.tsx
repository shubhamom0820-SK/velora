import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { signInOpen } from "@/lib/sign-in-path";

import { WaitlistForm } from "./WaitlistForm";

/**
 * The landing page's waitlist box (T-2.3), from the prototype. Its heading
 * depends on whether this build lets anyone sign in (D-081's flag): while it
 * doesn't, it says the app isn't open yet; once it does, it's for people
 * outside the launch city. Server-rendered, read at build time; only the form
 * inside it is client code. The prototype's 48 px below it is off the spacing scale, exactly
 * between 40 and 56: 40 matches the gap above it, under the feature cards.
 */
export function WaitlistBox() {
  const open = signInOpen();
  return (
    <section
      // /login's "Join the waitlist" lands here while sign-in is closed (D-081).
      id="waitlist"
      aria-labelledby="waitlist-title"
      className="mx-auto max-w-130 px-6 pb-10"
    >
      <div className="border-line rounded-card border p-5">
        <h2 id="waitlist-title" className="text-title-2 text-ink">
          {open
            ? t("landing.waitlist.title")
            : t("landing.waitlist.closedTitle", { app: APP_NAME })}
        </h2>
        <p className="text-body text-mute mt-1.5">
          {open ? t("landing.waitlist.body") : t("landing.waitlist.closedBody")}
        </p>
        <WaitlistForm />
      </div>
    </section>
  );
}
