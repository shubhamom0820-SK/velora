"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { t } from "@/i18n/t";
import { useDeleteAccount } from "@/lib/queries/account";
import type { Me } from "@/lib/queries/me";

import { YouSection } from "./YouSection";

/**
 * Who holds Velas, so who is told what deleting does to them (D-504): men
 * only (D-076's triggers keep a woman's balance at 0). An allowlist, so a new
 * gender value never shows a balance by mistake.
 */
const HOLDS_VELAS: ReadonlySet<Me["gender"]> = new Set(["male"]);

/**
 * Delete the account (T-9.6's `DELETE /me`, D-500), behind a sheet that says
 * what happens in `/privacy`'s words, and, for him, his balance in plain
 * words: the number from the API (`Me.balance`), never written into the copy
 * (D-504). Confirmed, the tab is signed out (`useDeleteAccount`).
 */
export function DeleteAccount({ me }: { me: Me }) {
  const [open, setOpen] = useState(false);
  const remove = useDeleteAccount();
  const velas = HOLDS_VELAS.has(me.gender) ? me.balance : null;

  return (
    <YouSection title={t("settings.delete.title")}>
      <div>
        <Button variant="danger" size="sm" onClick={() => setOpen(true)}>
          {t("settings.delete.button")}
        </Button>
      </div>
      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title={t("settings.delete.sheetTitle")}
        footer={
          <div className="flex flex-col gap-2">
            {remove.isError && (
              <p role="alert" className="text-small text-accent">
                {t("settings.delete.failed")}
              </p>
            )}
            <Button
              variant="danger"
              fullWidth
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {t("settings.delete.confirm")}
            </Button>
            <Button variant="ghost" fullWidth onClick={() => setOpen(false)}>
              {t("settings.delete.cancel")}
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          {velas !== null && (
            <p className="text-body text-ink font-semibold">
              {t(
                velas === 1
                  ? "settings.delete.velas.one"
                  : "settings.delete.velas.other",
                { count: velas },
              )}
            </p>
          )}
          <p className="text-body text-mute">{t("settings.delete.gone")}</p>
          <p className="text-body text-mute">{t("settings.delete.restore")}</p>
          <p className="text-body text-mute">{t("settings.delete.erased")}</p>
        </div>
      </Sheet>
    </YouSection>
  );
}
