import type { LucideIcon } from "lucide-react";

import { cx } from "@/lib/cx";

type IconProps = {
  /** A Lucide icon, imported by name: `import { Heart } from "lucide-react"`. */
  icon: LucideIcon;
  size?: number;
  /** Names the icon for screen readers. Without one it is decorative and hidden. */
  label?: string;
  className?: string;
};

/** A Lucide icon at the prototype's stroke width, hidden from screen readers unless labelled. */
export function Icon({ icon: Glyph, size = 20, label, className }: IconProps) {
  return (
    <Glyph
      size={size}
      strokeWidth={2}
      className={cx("shrink-0", className)}
      {...(label
        ? { role: "img", "aria-label": label }
        : { "aria-hidden": true })}
    />
  );
}
