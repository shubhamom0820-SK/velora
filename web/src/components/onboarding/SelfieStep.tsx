"use client";

import { Camera, CameraOff, ScanFace } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { cameraBrowser, type CameraBrowser } from "@/lib/camera";
import { cx } from "@/lib/cx";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";

import { SELFIE_CIRCLE, SelfieCamera } from "./SelfieCamera";
import {
  cameraCopy,
  selfieReasonCopy,
  triesCopy,
  type FinishCopy,
} from "./selfieCopy";
import { StepFrame } from "./StepFrame";
import { useSelfie, type SelfieView } from "./useSelfie";

/** Who may skip the selfie: men only (D-008). Anyone else, a woman, can't. */
const MAY_SKIP: ReadonlySet<Me["gender"]> = new Set(["male"]);

/**
 * The browser, for where it keeps the camera permission, and this site's host,
 * both read on the client: plain strings, so React sees them unchanged.
 */
const neverChanges = () => () => undefined;
const readBrowser = (): CameraBrowser =>
  cameraBrowser(navigator.userAgent, navigator.maxTouchPoints);
const readHost = () => window.location.host;

/** The selfie in its circle, as the person saw it: mirrored. */
function Shot({
  preview,
  matched = false,
}: {
  preview: string | null;
  matched?: boolean;
}) {
  return (
    <div className={cx(SELFIE_CIRCLE, "border-accent", matched && "shadow-2")}>
      {preview ? (
        // A plain <img>: next/image would send the selfie through the host's
        // image optimiser, outside India (D-048). The blob: source is T-4.6's
        // img-src.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={preview}
          alt={t("onboarding.selfie.captured")}
          className="size-full -scale-x-100 object-cover"
        />
      ) : (
        <Icon icon={ScanFace} size={50} className="text-accent" />
      )}
    </div>
  );
}

function Lines({ children }: { children: ReactNode }) {
  return (
    <div className="mt-6 flex max-w-[300px] flex-col items-center gap-1.5 text-center">
      {children}
    </div>
  );
}

const SKIP =
  "text-small text-mute mt-3 w-full py-2 underline underline-offset-2";

/** Why finishing was refused (T-4.8), with the way back when there is one. */
function finishFailure(copy: FinishCopy | null): ReactNode {
  if (!copy) return null;
  return (
    <p role="alert" className="text-small text-accent mt-3 text-center">
      {copy.message}
      {copy.place && (
        <>
          {" "}
          <Link
            href={stepPath(copy.place)}
            className="underline underline-offset-2"
          >
            {t("onboarding.selfie.finish.goThere")}
          </Link>
        </>
      )}
    </p>
  );
}

/**
 * The selfie (T-4.7), the `selfie` step: the front camera, a picture checked
 * before it's sent, and the result, said plainly while it's compared (D-261).
 * It says what is done, the selfie compared with the profile's photos, and
 * never that the person is verified, real or live (D-262). Men may skip it;
 * women can't, and the server holds that (T-4.8), whatever this screen shows:
 * "Skip for now" and "Continue" both ask it to finish sign-up.
 */
export function SelfieStep({ me }: { me: Me }) {
  const selfie = useSelfie({ alreadyMatched: me.is_verified });
  const browser = useSyncExternalStore(
    neverChanges,
    readBrowser,
    (): CameraBrowser => "other",
  );
  const host = useSyncExternalStore(neverChanges, readHost, () => "");
  const maySkip = MAY_SKIP.has(me.gender);
  const { view } = selfie;

  const skip = maySkip ? (
    <button
      type="button"
      className={SKIP}
      disabled={selfie.finishing}
      onClick={selfie.finish}
    >
      {t("onboarding.selfie.skip")}
    </button>
  ) : null;

  return (
    <StepFrame
      index={12}
      title={t("onboarding.selfie.title")}
      sub={
        maySkip
          ? t("onboarding.selfie.subMan")
          : t("onboarding.selfie.subWoman")
      }
      back={stepPath("pin")}
      signedIn
      footer={footer(view, selfie, skip)}
    >
      <div className="flex flex-col items-center pt-2">
        {body(view, selfie, browser, host)}
      </div>
    </StepFrame>
  );
}

type Selfie = ReturnType<typeof useSelfie>;

function body(
  view: SelfieView,
  selfie: Selfie,
  browser: CameraBrowser,
  host: string,
): ReactNode {
  switch (view.kind) {
    case "loading":
      return (
        <div aria-busy className="flex flex-col items-center">
          <Skeleton className="rounded-pill size-[180px]" />
        </div>
      );
    case "failed":
      return (
        <ErrorState
          body={t("onboarding.selfie.loadFailed")}
          onRetry={selfie.retryLoad}
        />
      );
    case "intro": {
      const rejected = view.last?.status === "rejected" ? view.last : null;
      return (
        <>
          <div className={cx(SELFIE_CIRCLE, "border-line border-dashed")}>
            <Icon icon={Camera} size={38} className="text-mute" />
          </div>
          <Lines>
            {rejected && (
              <p role="alert" className="text-small text-accent">
                {selfieReasonCopy(rejected.reject_reason)}{" "}
                {rejected.reject_reason === "no_photos" && (
                  <Link
                    href={stepPath("photos")}
                    className="underline underline-offset-2"
                  >
                    {t("onboarding.selfie.goToPhotos")}
                  </Link>
                )}
              </p>
            )}
            {rejected && (
              <p className="text-small text-mute">
                {triesCopy(rejected.attempts_left)}
              </p>
            )}
            {selfie.notice && (
              <p role="alert" className="text-small text-accent">
                {selfie.notice}
              </p>
            )}
            <p className="text-body text-ink mt-2 font-semibold">
              {t("onboarding.selfie.intro")}
            </p>
            <p className="text-small text-mute">
              {t("onboarding.selfie.private", { app: APP_NAME })}
            </p>
          </Lines>
        </>
      );
    }
    case "camera":
      return (
        <SelfieCamera
          onCapture={selfie.capture}
          onFailure={selfie.cameraFailed}
        />
      );
    case "cameraFailed": {
      const copy = cameraCopy(view.failure, browser, host);
      return (
        <>
          <div className={cx(SELFIE_CIRCLE, "border-line border-dashed")}>
            <Icon icon={CameraOff} size={38} className="text-mute" />
          </div>
          <Lines>
            <p role="alert" className="text-body text-ink font-semibold">
              {copy.title}
            </p>
            {copy.how && <p className="text-small text-mute">{copy.how}</p>}
          </Lines>
        </>
      );
    }
    case "review":
      return (
        <>
          <Shot preview={view.preview} />
          <Lines>
            <p className="text-small text-mute">
              {t("onboarding.selfie.reviewHint")}
            </p>
          </Lines>
        </>
      );
    case "sending":
      return (
        <>
          <Shot preview={view.preview} />
          <Lines>
            <p role="status" className="text-body text-ink font-semibold">
              {t("onboarding.selfie.sending", { percent: view.percent })}
            </p>
          </Lines>
        </>
      );
    case "sendFailed":
      return (
        <>
          <Shot preview={view.preview} />
          <Lines>
            <p role="alert" className="text-small text-accent">
              {view.copy}
            </p>
          </Lines>
        </>
      );
    case "comparing":
      return (
        <>
          <div className="rounded-pill ring-accent-soft motion-safe:animate-pulse ring-8">
            <Shot preview={view.preview} />
          </div>
          <Lines>
            <p role="status" className="text-body text-ink font-semibold">
              {view.stopped
                ? t("onboarding.selfie.comparingStill")
                : t("onboarding.selfie.comparing")}
            </p>
            {view.long && !view.stopped && (
              <p className="text-small text-mute">
                {t("onboarding.selfie.comparingLong")}
              </p>
            )}
          </Lines>
        </>
      );
    case "matched":
      return (
        <>
          <Shot preview={view.preview} matched />
          <Lines>
            <p role="status" className="text-body text-accent font-semibold">
              {t("onboarding.selfie.matched")}
            </p>
          </Lines>
        </>
      );
  }
}

function footer(view: SelfieView, selfie: Selfie, skip: ReactNode): ReactNode {
  switch (view.kind) {
    case "intro":
      return (
        <>
          <Button
            fullWidth
            loading={selfie.starting}
            onClick={() => void selfie.openCamera()}
          >
            {t("onboarding.selfie.openCamera")}
          </Button>
          {skip}
          {finishFailure(selfie.finishFailure)}
        </>
      );
    case "camera":
      return (
        <Button variant="ghost" fullWidth onClick={selfie.cancel}>
          {t("onboarding.selfie.cancel")}
        </Button>
      );
    case "cameraFailed":
      return (
        <>
          <Button fullWidth onClick={selfie.retryCamera}>
            {t("ui.retry")}
          </Button>
          <Button
            variant="ghost"
            fullWidth
            onClick={selfie.cancel}
            className="mt-3"
          >
            {t("onboarding.selfie.cancel")}
          </Button>
        </>
      );
    case "review":
    case "sending":
      return (
        <>
          <Button
            fullWidth
            loading={view.kind === "sending"}
            onClick={selfie.use}
          >
            {t("onboarding.selfie.use")}
          </Button>
          <Button
            variant="ghost"
            fullWidth
            disabled={view.kind === "sending"}
            onClick={selfie.retake}
            className="mt-3"
          >
            {t("onboarding.selfie.retake")}
          </Button>
        </>
      );
    case "sendFailed":
      return (
        <>
          <Button fullWidth onClick={selfie.use}>
            {t("ui.retry")}
          </Button>
          <Button
            variant="ghost"
            fullWidth
            onClick={selfie.retake}
            className="mt-3"
          >
            {t("onboarding.selfie.retake")}
          </Button>
        </>
      );
    case "comparing":
      return view.stopped ? (
        <Button variant="ghost" fullWidth onClick={selfie.checkAgain}>
          {t("onboarding.selfie.checkAgain")}
        </Button>
      ) : null;
    case "matched":
      return (
        <>
          <Button fullWidth loading={selfie.finishing} onClick={selfie.finish}>
            {t("onboarding.continue")}
          </Button>
          {finishFailure(selfie.finishFailure)}
        </>
      );
    case "loading":
    case "failed":
      return null;
  }
}
