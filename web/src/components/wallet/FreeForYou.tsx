import { Check } from "lucide-react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";

/**
 * A woman's wallet: nothing to show, because she pays for nothing (D-098) and
 * holds no Velas (D-076). The prototype's line without "calls" (after beta).
 */
export function FreeForYou() {
  return (
    <section className="flex flex-col items-center px-8 py-16 text-center">
      <Icon icon={Check} size={30} className="text-accent" />
      <h2 className="text-title-2 text-ink mt-4">{t("wallet.womenTitle")}</h2>
      <p className="text-body text-mute mt-2 max-w-72">
        {t("wallet.womenBody")}
      </p>
    </section>
  );
}
