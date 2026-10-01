import type { LucideIcon } from "lucide-react";

import { Icon } from "@/components/ui/Icon";

type FeatureCardProps = {
  icon: LucideIcon;
  title: string;
  body: string;
};

/** One of the landing page's three feature cards, as an item of their list. */
export function FeatureCard({ icon, title, body }: FeatureCardProps) {
  return (
    <li className="border-line rounded-card border p-4">
      <Icon icon={icon} size={18} className="text-accent" />
      <h2 className="text-title-2 text-ink mt-2.5">{title}</h2>
      <p className="text-body text-mute mt-1.5">{body}</p>
    </li>
  );
}
