"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { t } from "@/i18n/t";
import { useChangeCredits } from "@/lib/queries/admin";

import { ConfirmAction } from "./ConfirmAction";

/** At most this many Velas either way in one change (D-923). */
const MAX_DELTA = 1000;

/** A fresh `Idempotency-Key`: 8 to 64 of `A-Za-z0-9_-`. */
function freshKey(): string {
  return `admin-${crypto.randomUUID()}`;
}

/**
 * An admin's grant or correction (D-923), a man's only: a number to add, or
 * with a minus to take back, up to 1,000. The key is made when the sheet
 * opens and kept for its retries, so a second tap or a retry after a timeout
 * is the same change, applied once.
 */
export function CreditsForm({ userId }: { userId: string }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [key, setKey] = useState(freshKey);
  const change = useChangeCredits(userId);
  const delta = Number(typed);
  const valid =
    Number.isInteger(delta) && delta !== 0 && Math.abs(delta) <= MAX_DELTA;

  return (
    <div>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => {
          change.reset();
          setKey(freshKey());
          setTyped("");
          setOpen(true);
        }}
      >
        {t("admin.user.creditsSubmit")}
      </Button>
      <ConfirmAction
        open={open}
        onClose={() => setOpen(false)}
        title={t("admin.user.creditsTitle")}
        confirmLabel={t("admin.user.creditsSubmit")}
        variant="primary"
        pending={change.isPending}
        error={change.error}
        ready={valid}
        onConfirm={(reason) =>
          change.mutate(
            { delta, reason, key },
            { onSuccess: () => setOpen(false) },
          )
        }
      >
        <Field
          label={t("admin.user.delta")}
          inputMode="numeric"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
        />
      </ConfirmAction>
    </div>
  );
}
