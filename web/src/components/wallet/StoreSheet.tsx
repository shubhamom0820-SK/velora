"use client";

import { useEffect } from "react";

import { Sheet } from "@/components/ui/Sheet";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { useSession } from "@/store/session";
import { useStoreSheet } from "@/store/store-sheet";

/**
 * The store sheet, until T-8.7 builds the store: it says plainly that buying
 * hasn't started, with no promise of when. Opened by the balance pill, "Buy
 * Velas", and any mutation refused with `INSUFFICIENT_CREDITS`.
 *
 * Behind the PIN lock any sheet is `inert` (P-220); this one closes as well
 * when the lock goes up, since it holds nothing to come back to. It closes
 * when the app's routes unmount too, so a sign-out with it open doesn't bring
 * it back at the next sign-in.
 */
export function StoreSheet() {
  const open = useStoreSheet((state) => state.open);
  const hide = useStoreSheet((state) => state.hide);
  const locked = useSession((state) => state.locked);

  useEffect(() => {
    if (locked) hide();
  }, [locked, hide]);
  useEffect(() => hide, [hide]);

  return (
    <Sheet
      open={open && !locked}
      onClose={hide}
      title={t("wallet.store.title")}
    >
      <p className="text-body text-mute">
        {t("wallet.store.body", { app: APP_NAME })}
      </p>
    </Sheet>
  );
}
