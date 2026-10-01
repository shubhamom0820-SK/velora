import { ButtonLink } from "@/components/ui/ButtonLink";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

/**
 * The landing hero, on chrome under the red glow. The button stays `--accent`,
 * as in the prototype: white on `--chrome-accent` is too faint for its text
 * (08-DESIGN §1).
 */
export function Hero() {
  return (
    <section className="bg-chrome bg-(image:--chrome-glow) px-6 py-14 text-center">
      {/* Balanced, so a narrow phone breaks the line evenly instead of
          leaving "day." alone on one. */}
      <h1 className="text-display text-chrome-ink text-balance">
        <span className="block">{t("landing.headlineThreads")}</span>{" "}
        <span className="block">{t("landing.headlineKnots")}</span>
      </h1>
      <p className="text-body text-chrome-mute mx-auto mt-4 max-w-115">
        {t("landing.intro")}
      </p>
      <div className="mt-8">
        <ButtonLink href="/login">
          {t("landing.join", { app: APP_NAME })}
        </ButtonLink>
      </div>
      <p className="text-small text-chrome-mute mt-3.5">
        {t("landing.ageNote")}
      </p>
    </section>
  );
}
