import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { SignOutButton } from "@/components/session/SignOutButton";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

/** Phone, code, then the ten steps (08-DESIGN §5). */
export const ONBOARDING_SCREENS = 12;

type StepFrameProps = {
  /** 0 for the phone screen, 11 for the selfie. */
  index: number;
  title: string;
  sub?: string;
  /**
   * Where the back arrow goes: the previous screen, when it's one the person
   * may still change (D-080). None on screens behind which is sign-in or an
   * answer that can't change.
   */
  back?: string | (() => void);
  /** The quiet "Sign out" (T-3.10), on every screen after sign-in. */
  signedIn?: boolean;
  children: ReactNode;
  footer?: ReactNode;
};

const BACK =
  "text-mute -m-2.5 p-2.5 focus-visible:outline-accent focus-visible:outline-2";

/**
 * The onboarding frame (T-3.11), from the prototype's `Step`: back arrow, 12
 * segments of progress, title, body, footer, 520 px. Onboarding only, with no
 * header or nav (T-5.6's are the app's); T-4.6 and T-4.7 reuse it.
 */
export function StepFrame({
  index,
  title,
  sub,
  back,
  signedIn = false,
  children,
  footer,
}: StepFrameProps) {
  return (
    <main className="bg-bg text-ink flex min-h-dvh justify-center">
      <div className="flex w-full max-w-[520px] flex-col px-6 pt-4 pb-6">
        <div className="mb-5 flex items-center gap-3">
          {typeof back === "string" ? (
            <Link
              href={back}
              aria-label={t("onboarding.back")}
              className={BACK}
            >
              <Icon icon={ChevronLeft} size={22} />
            </Link>
          ) : back ? (
            <button
              type="button"
              aria-label={t("onboarding.back")}
              onClick={back}
              className={BACK}
            >
              <Icon icon={ChevronLeft} size={22} />
            </button>
          ) : (
            <span className="size-5.5" />
          )}
          <div
            role="progressbar"
            aria-label={t("onboarding.progress", {
              step: index + 1,
              total: ONBOARDING_SCREENS,
            })}
            aria-valuemin={1}
            aria-valuemax={ONBOARDING_SCREENS}
            aria-valuenow={index + 1}
            className="flex flex-1 gap-1"
          >
            {Array.from({ length: ONBOARDING_SCREENS }, (_, n) => (
              <span
                key={n}
                className={cx(
                  "rounded-pill h-[3px] flex-1",
                  n <= index ? "bg-accent" : "bg-surface-2",
                )}
              />
            ))}
          </div>
          {signedIn && <SignOutButton />}
        </div>
        <h1 className="text-title-1">{title}</h1>
        {sub && <p className="text-small text-mute mt-2">{sub}</p>}
        <div className="mt-5 flex-1">{children}</div>
        {footer && <div className="pt-4">{footer}</div>}
      </div>
    </main>
  );
}
