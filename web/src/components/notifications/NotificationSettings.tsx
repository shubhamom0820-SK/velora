"use client";

import { useState } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Toggle } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/useToast";
import { type MessageKey, t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import * as push from "@/lib/push";
import { useMe } from "@/lib/queries/me";
import {
  type Prefs,
  useNotificationPrefs,
  usePushKey,
  usePushSubscription,
  useTurnOffPush,
  useTurnOnPush,
  useUpdateNotificationPrefs,
} from "@/lib/queries/notifications";

type Setting = keyof Prefs;

type Row = { setting: Setting; label: MessageKey; hint?: MessageKey };

/**
 * Which kinds each person is offered. An hour running out and a balance reach
 * only a man (D-554, P-460), so only he sees their switches: her screen never
 * says a Thread can run out.
 */
function rowsFor(man: boolean): Row[] {
  return [
    { setting: "match", label: "notifications.settings.match" },
    { setting: "message", label: "notifications.settings.message" },
    { setting: "like", label: "notifications.settings.like" },
    { setting: "gift", label: "notifications.settings.gift" },
    {
      setting: "album",
      label: "notifications.settings.album",
      hint: "notifications.settings.albumHint",
    },
    { setting: "knot", label: "notifications.settings.knot" },
    ...(man
      ? ([
          { setting: "expiry", label: "notifications.settings.expiry" },
          { setting: "balance", label: "notifications.settings.balance" },
        ] satisfies Row[])
      : []),
    {
      setting: "generic_text",
      label: "notifications.settings.genericText",
      hint: "notifications.settings.genericTextHint",
    },
  ];
}

/**
 * Notification settings (T-9.4), at `/you/notifications`: whether this
 * browser gets pushes, then what may push. Built from the existing parts
 * (D-859): no design of its own yet (08-DESIGN §8). A switch turned off still
 * shows in the in-app list.
 */
export function NotificationSettings() {
  const toast = useToast();
  const me = useMe();
  const prefs = useNotificationPrefs();
  const update = useUpdateNotificationPrefs();
  const [saving, setSaving] = useState<Setting | null>(null);

  function onChange(setting: Setting, value: boolean) {
    setSaving(setting);
    update.mutate(
      { [setting]: value },
      {
        onError: () =>
          toast.show({
            message: t("notifications.settings.saveFailed"),
            tone: "error",
          }),
        onSettled: () => setSaving(null),
      },
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-(--shell-gutter)">
      <h1 className="text-title-2 text-ink">
        {t("notifications.settings.title")}
      </h1>
      <DeviceSwitch />
      <section
        aria-label={t("notifications.settings.kindsTitle")}
        aria-busy={prefs.isPending}
        className="flex flex-col"
      >
        <h2 className="text-ui text-mute">
          {t("notifications.settings.kindsTitle")}
        </h2>
        {prefs.data === undefined ? (
          prefs.isError ? (
            <ErrorState
              title={t("notifications.settings.failed")}
              onRetry={() => void prefs.refetch()}
            />
          ) : (
            <div className="flex flex-col gap-2 pt-2">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
          )
        ) : (
          <>
            {rowsFor(me.data?.gender === "male").map((row) => (
              <Toggle
                key={row.setting}
                label={t(row.label)}
                description={row.hint ? t(row.hint) : undefined}
                checked={prefs.data[row.setting]}
                disabled={saving === row.setting}
                onChange={(value) => onChange(row.setting, value)}
              />
            ))}
            <p className="text-small text-mute pt-2">
              {t("notifications.settings.listHint")}
            </p>
          </>
        )}
      </section>
    </div>
  );
}

/** This browser: on or off, or why it can't be. */
function DeviceSwitch() {
  const toast = useToast();
  const key = usePushKey();
  const subscription = usePushSubscription();
  const turnOn = useTurnOnPush();
  const turnOff = useTurnOffPush();
  const support =
    typeof window === "undefined" ? "unsupported" : push.pushSupport();

  if (key.isPending || subscription.isPending) {
    return <Skeleton className="h-12" />;
  }
  if (support === "ios-install") {
    return (
      <p className="text-small text-mute">
        {t("notifications.settings.iosInstall", { app: APP_NAME })}
      </p>
    );
  }
  if (!key.data || support === "unsupported") {
    return (
      <p className="text-small text-mute">
        {t("notifications.settings.unavailable")}
      </p>
    );
  }
  if (support === "denied") {
    return (
      <p className="text-small text-mute">
        {t("notifications.settings.blocked", { app: APP_NAME })}
      </p>
    );
  }

  const on = Boolean(subscription.data);
  const publicKey = key.data;
  async function onChange(value: boolean) {
    try {
      if (value) await turnOn.mutateAsync(publicKey);
      else await turnOff.mutateAsync();
    } catch {
      toast.show({
        message: t(
          value
            ? "notifications.settings.turnOnFailed"
            : "notifications.settings.saveFailed",
        ),
        tone: "error",
      });
    }
  }

  return (
    <Toggle
      label={t("notifications.settings.device")}
      description={t(
        on
          ? "notifications.settings.deviceOn"
          : "notifications.settings.deviceOff",
      )}
      checked={on}
      disabled={turnOn.isPending || turnOff.isPending}
      onChange={(value) => void onChange(value)}
    />
  );
}
