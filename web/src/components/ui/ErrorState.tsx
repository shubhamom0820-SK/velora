import { CircleAlert } from "lucide-react";

import { t } from "@/i18n/t";

import { Button } from "./Button";
import { Icon } from "./Icon";

type ErrorStateProps = {
  /** Defaults to "Something went wrong". */
  title?: string;
  body?: string;
  /** Shows "Try again". */
  onRetry?: () => void;
};

/** What a screen shows when its data failed to load. Announced as an alert. */
export function ErrorState({ title, body, onRetry }: ErrorStateProps) {
  return (
    <section
      role="alert"
      className="flex flex-col items-center px-8 py-10 text-center"
    >
      <Icon icon={CircleAlert} size={28} className="text-accent mb-3" />
      <h2 className="text-title-2 text-ink">{title ?? t("ui.errorTitle")}</h2>
      {body && <p className="text-small text-mute mt-1.5">{body}</p>}
      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry} className="mt-5">
          {t("ui.retry")}
        </Button>
      )}
    </section>
  );
}
