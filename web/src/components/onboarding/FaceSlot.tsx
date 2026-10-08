"use client";

import { ImageOff, Plus, ScanFace, X } from "lucide-react";
import { useRef } from "react";

import { Icon } from "@/components/ui/Icon";
import { Toggle } from "@/components/ui/Toggle";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

import { PhotoChecking } from "./PhotoChecking";
import type { useFaceSlot } from "./useFaceSlot";

type FaceSlotProps = {
  slot: ReturnType<typeof useFaceSlot>;
  /** Who may leave without one: the words differ, the rule is the server's. */
  optional: boolean;
  /** The selfie matched this photo: it can't change now (T-4.12, point 4). */
  locked: boolean;
};

const SMALL_BUTTON =
  "relative size-6 before:absolute before:-inset-2.5 before:content-[''] disabled:opacity-40 focus-visible:outline-accent focus-visible:outline-2";

/**
 * The face photo's slot (T-4.12, D-391): the one the selfie is compared
 * with, private unless its owner chooses to show it. One place, beside the
 * grid: empty, uploading, checking, approved, or rejected with its reason and
 * a way on; and the toggle that also shows it on the profile, enabled once it
 * is approved. Replacing it is the picker again; after the selfie matched,
 * neither is offered, and the server refuses both anyway.
 */
export function FaceSlot({ slot, optional, locked }: FaceSlotProps) {
  const picker = useRef<HTMLInputElement>(null);
  const { view } = slot;
  const live = view.kind === "checking" || view.kind === "approved";
  const src = live ? (view.preview ?? view.photo.url) : null;

  return (
    <section
      aria-label={t("onboarding.photos.face.title")}
      className="rounded-input bg-surface mt-5 p-3.5"
    >
      <input
        ref={picker}
        type="file"
        accept="image/*"
        tabIndex={-1}
        aria-hidden
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void slot.add(file);
        }}
      />
      <div className="flex items-start gap-3.5">
        <div className="rounded-input bg-surface-2 relative aspect-[3/4] w-24 shrink-0 overflow-hidden">
          {view.kind === "empty" && (
            <button
              type="button"
              onClick={() => picker.current?.click()}
              className="rounded-input border-line text-mute focus-visible:outline-accent flex size-full items-center justify-center border border-dashed focus-visible:outline-2"
            >
              <Icon
                icon={Plus}
                size={18}
                label={t("onboarding.photos.face.add")}
              />
            </button>
          )}
          {view.kind === "uploading" && (
            <>
              {view.preview && (
                // A plain <img>: next/image would send the photo through the
                // host's image optimiser, outside India (D-048).
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={view.preview}
                  alt=""
                  className="size-full object-cover opacity-60"
                />
              )}
              <div className="bg-scrim absolute inset-0 flex flex-col items-center justify-center gap-2 p-2">
                {view.percent < 100 ? (
                  <progress
                    max={100}
                    value={view.percent}
                    aria-label={t("onboarding.photos.uploading", {
                      percent: view.percent,
                    })}
                    className="rounded-pill [&::-webkit-progress-bar]:bg-surface-2 [&::-webkit-progress-value]:bg-accent [&::-moz-progress-bar]:bg-accent bg-surface-2 h-1 w-3/4 appearance-none overflow-hidden"
                  />
                ) : (
                  <PhotoChecking />
                )}
              </div>
            </>
          )}
          {live && src && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={src}
              alt={t("onboarding.photos.face.slot")}
              className={cx(
                "size-full object-cover",
                view.kind === "checking" && "blur-sm",
              )}
            />
          )}
          {view.kind === "checking" && (
            <div
              role="status"
              aria-label={t("onboarding.photos.face.checking")}
              className="bg-scrim absolute inset-0 flex items-center justify-center"
            >
              <PhotoChecking />
            </div>
          )}
          {view.kind === "approved" && (
            <span className="sr-only">
              {t("onboarding.photos.face.approved")}
            </span>
          )}
          {(view.kind === "rejected" || view.kind === "failed") && (
            <>
              <div className="border-line bg-surface-2 rounded-input relative flex size-full flex-col items-center justify-center gap-1 border p-1 text-center">
                <Icon icon={ImageOff} size={16} className="text-accent" />
                <button
                  type="button"
                  onClick={
                    view.kind === "rejected"
                      ? () => picker.current?.click()
                      : slot.retry
                  }
                  className="text-micro text-accent focus-visible:outline-accent underline underline-offset-2 focus-visible:outline-2"
                >
                  {view.kind === "rejected"
                    ? t("onboarding.photos.chooseAnother")
                    : t("onboarding.photos.tryAgain")}
                </button>
              </div>
              <button
                type="button"
                aria-label={t("onboarding.photos.dismiss", { n: "" }).trim()}
                onClick={slot.dismiss}
                className={cx(
                  "bg-chrome/80 text-on-photo rounded-pill flex items-center justify-center",
                  SMALL_BUTTON,
                  "absolute top-1 right-1",
                )}
              >
                <Icon icon={X} size={12} />
              </button>
            </>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-ui text-ink flex items-center gap-1.5 font-semibold">
            <Icon icon={ScanFace} size={15} className="text-accent" />
            {t("onboarding.photos.face.title")}
          </p>
          <p className="text-small text-mute mt-1">
            {optional
              ? t("onboarding.photos.face.subMan")
              : t("onboarding.photos.face.subWoman")}
          </p>
          {(view.kind === "rejected" || view.kind === "failed") && (
            <p role="alert" className="text-micro text-accent mt-2">
              {view.copy}
            </p>
          )}
          {live && !locked && (
            <button
              type="button"
              onClick={() => picker.current?.click()}
              className="text-small text-accent focus-visible:outline-accent mt-2 underline underline-offset-2 focus-visible:outline-2"
            >
              {t("onboarding.photos.face.replace")}
            </button>
          )}
          {live && locked && (
            <p className="text-small text-mute mt-2">
              {t("onboarding.photos.face.locked")}
            </p>
          )}
        </div>
      </div>
      {live && (
        <div className="border-line mt-2 border-t">
          <Toggle
            label={t("onboarding.photos.face.show")}
            description={t("onboarding.photos.face.showHint")}
            checked={slot.shown}
            disabled={view.kind !== "approved" || slot.toggling}
            onChange={slot.setShown}
          />
          {slot.toggleCopy && (
            <p role="alert" className="text-small text-accent pb-2">
              {slot.toggleCopy}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
