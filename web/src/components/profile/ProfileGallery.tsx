"use client";

import { User } from "lucide-react";
import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

/**
 * The profile's photos, swiped across, with a dot for each (08-DESIGN §8):
 * their approved public photos in place order, the first the main one. With
 * none, a silhouette and the line D-392 gives. With more than one, the
 * scroller is a named region and a Tab stop, so a keyboard reaches every photo.
 */
export function ProfileGallery({ urls }: { urls: string[] }) {
  const [shown, setShown] = useState(0);
  if (urls.length === 0) {
    return (
      <div className="bg-surface-2 flex h-[390px] flex-col items-center justify-center gap-3">
        <Icon icon={User} size={96} className="text-line-strong" />
        <p className="text-small text-mute">{t("profile.noPhoto")}</p>
      </div>
    );
  }
  return (
    <div className="relative">
      {/* More than one photo: a Tab stop, so the arrow keys scroll it (T-9.11).
          Not left to the browser: only Chromium makes a scroller focusable. */}
      <div
        {...(urls.length > 1 && {
          role: "region",
          "aria-label": t("profile.photos"),
          tabIndex: 0,
        })}
        className="flex h-[390px] snap-x snap-mandatory overflow-x-auto focus-visible:-outline-offset-4"
        onScroll={(event) => {
          const { scrollLeft, clientWidth } = event.currentTarget;
          if (clientWidth > 0) setShown(Math.round(scrollLeft / clientWidth));
        }}
      >
        {urls.map((url, i) => (
          // A plain <img>: the CDN isn't configured for next/image.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={url}
            src={url}
            alt={t("profile.photo", { n: i + 1, total: urls.length })}
            className="bg-surface-2 h-full w-full shrink-0 snap-center object-cover"
          />
        ))}
      </div>
      {urls.length > 1 && (
        <div
          aria-hidden
          className="absolute inset-x-0 bottom-3 flex justify-center gap-1.5"
        >
          {urls.map((url, i) => (
            <span
              key={url}
              className={cx(
                "rounded-pill size-1.5",
                i === shown ? "bg-on-photo" : "bg-on-photo/50",
              )}
            />
          ))}
        </div>
      )}
    </div>
  );
}
