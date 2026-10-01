import { Clock, Link2, Shield } from "lucide-react";

import { FeatureCard } from "@/components/marketing/FeatureCard";
import { Hero } from "@/components/marketing/Hero";
import { SiteFooter } from "@/components/marketing/SiteFooter";
import { SiteHeader } from "@/components/marketing/SiteHeader";
import { t } from "@/i18n/t";

// The prototype's own icons: its "Link" is Lucide's link-2.
const FEATURES = [
  { key: "threads", icon: Clock },
  { key: "knot", icon: Link2 },
  { key: "safety", icon: Shield },
] as const;

/**
 * The landing page (T-2.1), from the prototype. Server-rendered, with no
 * page-level client JS; the waitlist box arrives with its form in T-2.3.
 */
export default function LandingPage() {
  return (
    <div className="bg-bg flex min-h-dvh flex-col">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <ul className="mx-auto grid max-w-225 grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3 px-6 pb-10">
          {FEATURES.map(({ key, icon }) => (
            <FeatureCard
              key={key}
              icon={icon}
              title={t(`landing.features.${key}.title`)}
              body={t(`landing.features.${key}.body`)}
            />
          ))}
        </ul>
      </main>
      <SiteFooter />
    </div>
  );
}
