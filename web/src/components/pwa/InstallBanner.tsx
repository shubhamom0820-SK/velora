"use client";

import { Download, X } from "lucide-react";
import { useSyncExternalStore } from "react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { dismiss, install, offer, subscribe } from "@/lib/install-prompt";

/**
 * The install banner (T-9.7, D-1042): the prototype's strip under the header,
 * on a touch-first device that hasn't installed the app. On Android, Install
 * opens the browser's own dialog; on an iPhone it says the steps instead,
 * since Safari has no prompt. Closed once, it stays closed in that browser.
 * Nothing at all on a desktop, once installed, or before the browser offers.
 */
export function InstallBanner() {
  const shown = useSyncExternalStore(
    subscribe,
    () => offer(),
    () => "none" as const,
  );
  if (shown === "none") return null;
  return (
    <div className="bg-surface border-line flex items-center gap-3 border-b py-0.5 pr-2 pl-5">
      <Icon icon={Download} size={15} className="text-accent" />
      <p className="text-small text-ink flex-1">
        {t(shown === "ios" ? "install.ios" : "install.banner", {
          app: APP_NAME,
        })}
      </p>
      {shown === "android" && (
        <button
          type="button"
          onClick={() => void install()}
          className="text-small text-accent min-h-11 px-2 font-bold"
        >
          {t("install.action")}
        </button>
      )}
      <button
        type="button"
        aria-label={t("install.dismiss")}
        onClick={() => dismiss()}
        className="text-mute rounded-pill flex size-11 shrink-0 items-center justify-center"
      >
        <Icon icon={X} size={14} />
      </button>
    </div>
  );
}
