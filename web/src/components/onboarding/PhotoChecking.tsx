import { Loader } from "lucide-react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";

/** "Checking…" over a photo, as the prototype has it (T-4.6), announced as a status. */
export function PhotoChecking() {
  return (
    <span role="status" className="flex flex-col items-center gap-1">
      <Icon
        icon={Loader}
        size={18}
        className="text-accent motion-safe:animate-spin motion-reduce:animate-pulse"
      />
      <span className="text-micro text-on-photo">
        {t("onboarding.photos.checking")}
      </span>
    </span>
  );
}
