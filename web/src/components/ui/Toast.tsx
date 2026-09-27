import { cx } from "@/lib/cx";

export type ToastTone = "info" | "error";
export type ToastAction = { label: string; onClick: () => void };

type ToastProps = {
  message: string;
  tone: ToastTone;
  action?: ToastAction;
  onDismiss: () => void;
};

/**
 * The pill ToastProvider shows. Info is ink, errors are accent. Screens call
 * `useToast().show(...)` rather than rendering this.
 */
export function Toast({ message, tone, action, onDismiss }: ToastProps) {
  return (
    <div
      className={cx(
        "rounded-pill text-small shadow-2 pointer-events-auto flex items-center gap-3 border px-4 py-2 font-semibold motion-safe:animate-fade-in",
        tone === "error"
          ? "border-accent bg-accent text-on-accent"
          : "border-line bg-ink text-surface",
      )}
    >
      <span>{message}</span>
      {action && (
        <button
          type="button"
          onClick={() => {
            action.onClick();
            onDismiss();
          }}
          className="focus-visible:outline-surface relative font-bold underline underline-offset-2 before:absolute before:-inset-3 focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
