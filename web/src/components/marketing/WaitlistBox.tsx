import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

import { WaitlistForm } from "./WaitlistForm";

/**
 * The landing page's waitlist box (T-2.3), from the prototype, for people
 * outside the launch city. Server-rendered; only the form inside it is client
 * code. The prototype's 48 px below it is off the spacing scale, exactly
 * between 40 and 56: 40 matches the gap above it, under the feature cards.
 */
export function WaitlistBox() {
  return (
    <section
      aria-labelledby="waitlist-title"
      className="mx-auto max-w-130 px-6 pb-10"
    >
      <div className="border-line rounded-card border p-5">
        <h2 id="waitlist-title" className="text-title-2 text-ink">
          {t("landing.waitlist.title")}
        </h2>
        <p className="text-body text-mute mt-1.5">
          {t("landing.waitlist.body", { app: APP_NAME })}
        </p>
        <WaitlistForm />
      </div>
    </section>
  );
}
