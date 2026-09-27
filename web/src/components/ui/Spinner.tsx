import { Loader } from "lucide-react";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

import { Icon } from "./Icon";

type SpinnerProps = {
  size?: number;
  /** What is loading, for screen readers. Defaults to "Loading". */
  label?: string;
  className?: string;
};

/** A loading indicator announced to screen readers. Spins, or pulses under reduced motion. */
export function Spinner({ size = 20, label, className }: SpinnerProps) {
  return (
    <span role="status" className={cx("inline-flex", className)}>
      <Icon
        icon={Loader}
        size={size}
        className="motion-safe:animate-spin motion-reduce:animate-pulse"
      />
      <span className="sr-only">{label ?? t("ui.loading")}</span>
    </span>
  );
}
