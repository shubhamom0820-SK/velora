"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Toggle } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/useToast";
import { t, type MessageKey } from "@/i18n/t";
import { usePause } from "@/lib/queries/account";
import {
  type Me,
  type SettingsPatch,
  useMe,
  useUpdateSettings,
} from "@/lib/queries/me";

import { DataExportSection } from "./DataExportSection";
import { DeleteAccount } from "./DeleteAccount";
import { YouSection } from "./YouSection";

type Switch = keyof SettingsPatch & keyof Me["profile"];

type Row = { setting: Switch; label: MessageKey; hint?: MessageKey };

/**
 * The privacy switches (T-9.6's `PATCH /me/settings`). `show_gifts` isn't
 * here: it stays beside her gifts (T-8.10), where what it hides is shown.
 */
const SWITCHES = [
  {
    setting: "is_hidden",
    label: "settings.hidden",
    hint: "settings.hiddenHint",
  },
  { setting: "hide_age", label: "settings.hideAge" },
  { setting: "hide_distance", label: "settings.hideDistance" },
  { setting: "show_kudos", label: "settings.showKudos" },
  // D-544, P-447: off until its owner turns it on.
  {
    setting: "public_link",
    label: "settings.publicLink",
    hint: "settings.publicLinkHint",
  },
] as const satisfies readonly Row[];

/**
 * Privacy and account (T-9.8), at `/you/settings`, from existing parts
 * (D-913): the five switches, pause and resume, a copy of your data, and
 * delete. Each switch sends only itself; the answer is the new `Me`.
 */
export function SettingsScreen() {
  const me = useMe();
  return (
    <div className="text-ink flex flex-1 flex-col pb-6">
      <h1 className="text-title-1 px-(--shell-gutter) pt-5">
        {t("settings.title")}
      </h1>
      {me.isPending ? (
        <div aria-busy className="flex flex-col gap-3 p-(--shell-gutter)">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : me.isError ? (
        <div className="p-(--shell-gutter)">
          <ErrorState onRetry={() => void me.refetch()} />
        </div>
      ) : (
        <>
          <Switches me={me.data} />
          <Pause me={me.data} />
          <DataExportSection />
          <DeleteAccount me={me.data} />
        </>
      )}
    </div>
  );
}

function Switches({ me }: { me: Me }) {
  const update = useUpdateSettings();
  const toast = useToast();
  const [saving, setSaving] = useState<Switch | null>(null);
  const link = `/@${me.profile.username ?? ""}`;

  function onChange(setting: Switch, value: boolean) {
    setSaving(setting);
    update.mutate(
      { [setting]: value },
      {
        onError: () =>
          toast.show({ message: t("settings.saveFailed"), tone: "error" }),
        onSettled: () => setSaving(null),
      },
    );
  }

  return (
    <YouSection title={t("settings.privacy")}>
      {SWITCHES.map((row) => (
        <Toggle
          key={row.setting}
          label={t(row.label)}
          description={"hint" in row ? t(row.hint, { link }) : undefined}
          checked={me.profile[row.setting]}
          disabled={saving === row.setting}
          onChange={(value) => onChange(row.setting, value)}
        />
      ))}
    </YouSection>
  );
}

/** Pause and resume (T-9.6): hidden from everyone and sent nothing meanwhile. */
function Pause({ me }: { me: Me }) {
  const pause = usePause();
  const toast = useToast();
  const paused = me.status === "paused";

  return (
    <YouSection title={t("settings.pause.title")}>
      <p className="text-body text-mute">
        {paused ? t("settings.pause.paused") : t("settings.pause.body")}
      </p>
      <div>
        <Button
          variant="ghost"
          size="sm"
          loading={pause.isPending}
          onClick={() =>
            pause.mutate(!paused, {
              onError: () =>
                toast.show({
                  message: t("settings.pause.failed"),
                  tone: "error",
                }),
            })
          }
        >
          {paused ? t("settings.pause.resume") : t("settings.pause.button")}
        </Button>
      </div>
    </YouSection>
  );
}
