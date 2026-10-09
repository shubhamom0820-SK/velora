"use client";

import { BellRing } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import * as push from "@/lib/push";
import { usePushKey, useTurnOnPush } from "@/lib/queries/notifications";

/**
 * The ask for notifications (T-9.4), on the match sheet: after the first
 * match, never on load, so it comes when there is someone to hear from. Shown
 * once per browser (`push.askedBefore`), only where push can work: this build
 * has a key and the browser hasn't decided yet. On an iPhone not added to the
 * Home Screen, the note on how instead, since Safari's tab has no push.
 *
 * The browser's own prompt opens from the "Turn on" tap: browsers ignore an
 * ask nobody tapped for.
 */
export function PushAsk() {
  const turnOn = useTurnOnPush();
  const toast = useToast();
  // Read once, on the first render: whether this browser was asked before,
  // and whether it can be. Marked as asked once it has been shown.
  const [shown] = useState(() => {
    if (typeof window === "undefined" || push.askedBefore()) return false;
    const support = push.pushSupport();
    return (
      support === "ios-install" ||
      (support === "ready" && push.permission() === "default")
    );
  });
  // Asked only where the ask could show: elsewhere nothing is requested.
  const key = usePushKey({ enabled: shown });
  const [done, setDone] = useState(false);
  const visible = shown && !done && Boolean(key.data);

  useEffect(() => {
    if (visible) push.rememberAsked();
  }, [visible]);

  if (!visible || !key.data) return null;

  if (push.pushSupport() === "ios-install") {
    return (
      <p className="rounded-card bg-chrome-line text-small text-chrome-ink p-3">
        {t("notifications.settings.iosInstall", { app: APP_NAME })}
      </p>
    );
  }

  async function onTurnOn(publicKey: string) {
    try {
      await turnOn.mutateAsync(publicKey);
    } catch {
      toast.show({
        message: t("notifications.settings.turnOnFailed"),
        tone: "error",
      });
    }
    setDone(true);
  }

  const publicKey = key.data;
  return (
    <section
      aria-label={t("notifications.ask.title")}
      className="rounded-card bg-chrome-line flex flex-col gap-2 p-3"
    >
      <div className="flex items-center gap-2">
        <BellRing aria-hidden className="text-chrome-accent size-5" />
        <h3 className="text-ui text-chrome-ink">
          {t("notifications.ask.title")}
        </h3>
      </div>
      <p className="text-small text-chrome-mute">
        {t("notifications.ask.body")}
      </p>
      <div className="flex gap-2">
        <Button
          size="sm"
          loading={turnOn.isPending}
          onClick={() => void onTurnOn(publicKey)}
        >
          {t("notifications.ask.turnOn")}
        </Button>
        <Button size="sm" variant="chrome" onClick={() => setDone(true)}>
          {t("notifications.ask.notNow")}
        </Button>
      </div>
    </section>
  );
}
