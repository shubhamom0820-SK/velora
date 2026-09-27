import type { LucideIcon } from "lucide-react";

import { Button } from "./Button";
import { Icon } from "./Icon";

type EmptyStateProps = {
  icon?: LucideIcon;
  title: string;
  body?: string;
  action?: { label: string; onClick: () => void };
};

/** What a screen shows when it has nothing to list, and what to do about it. */
export function EmptyState({ icon, title, body, action }: EmptyStateProps) {
  return (
    <section className="flex flex-col items-center px-8 py-10 text-center">
      {icon && <Icon icon={icon} size={28} className="text-mute mb-3" />}
      <h2 className="text-title-2 text-ink">{title}</h2>
      {body && <p className="text-small text-mute mt-1.5">{body}</p>}
      {action && (
        <Button
          variant="ghost"
          size="sm"
          onClick={action.onClick}
          className="mt-5"
        >
          {action.label}
        </Button>
      )}
    </section>
  );
}
