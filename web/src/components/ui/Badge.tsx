import { cx } from "@/lib/cx";

type BadgeProps = {
  children: string | number;
  /**
   * `ink`: a status on the light surface ("@ username" in search, "New");
   * `soft`: a quieter one on `--accent-soft` ("Exact", "Online now");
   * `count`: a number on `--chrome-accent`, in the chrome (Liked you's count).
   */
  tone?: "ink" | "soft" | "count";
  /** Read out in place of the text, when the text alone says too little ("3" → "3 people"). */
  label?: string;
};

const TONES = {
  ink: "bg-ink text-chrome-ink",
  soft: "bg-accent-soft text-accent-text",
  count: "bg-chrome-accent text-on-accent min-w-5 justify-center",
} as const;

/** A small pill: a count or a status (08-DESIGN §4). Never a button. */
export function Badge({ children, tone = "ink", label }: BadgeProps) {
  return (
    <span
      className={cx(
        "rounded-pill text-micro inline-flex items-center px-2 py-0.5",
        TONES[tone],
      )}
      {...(label ? { "aria-label": label, role: "img" } : {})}
    >
      {children}
    </span>
  );
}
