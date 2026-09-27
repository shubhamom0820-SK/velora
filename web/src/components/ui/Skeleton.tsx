import { cx } from "@/lib/cx";

type SkeletonProps = {
  variant?: "line" | "card" | "avatar";
  /** Layout only, e.g. a shorter line: `w-2/3`. */
  className?: string;
};

const SHAPES = {
  line: "h-3 rounded-pill",
  card: "aspect-[4/3] rounded-card",
  avatar: "size-[46px] rounded-pill",
} as const;

/**
 * A grey placeholder while content loads. Hidden from screen readers: the
 * screen that shows it marks itself `aria-busy` instead.
 */
export function Skeleton({ variant = "line", className }: SkeletonProps) {
  return (
    <span
      aria-hidden
      className={cx(
        "bg-surface-2 block motion-safe:animate-pulse",
        SHAPES[variant],
        className,
      )}
    />
  );
}
