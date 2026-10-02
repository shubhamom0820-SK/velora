import { Clock, Link2, Shield } from "lucide-react";
import { FeatureCard } from "@/components/marketing/FeatureCard";
import { Hero } from "@/components/marketing/Hero";
import { SiteHeader } from "@/components/marketing/SiteHeader";
import { WaitlistBox } from "@/components/marketing/WaitlistBox";
import { t } from "@/i18n/t";
import { homeTitle, publicPageMetadata } from "@/lib/site";

// The landing intro doubles as the description: it promises thread_hours too.
export const generateMetadata = publicPageMetadata(
  "/",
  homeTitle(),
  t("landing.intro"),
);

// The prototype's own icons: its "Link" is Lucide's link-2.
const FEATURES = [
  { key: "threads", icon: Clock },
  { key: "knot", icon: Link2 },
  { key: "safety", icon: Shield },
] as const;

/**
 * The landing page (T-2.1), from the prototype. Server-rendered; its one
 * client component is the waitlist box's form (T-2.3). The footer comes from
 * the marketing layout.
 */
export default function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        {/* pt-3 matches the gap between the cards, so the first one starts the
            set instead of falling out of the hero. The prototype has them flush;
            the founder changed that on review. */}
        <ul className="mx-auto grid max-w-225 grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3 px-6 pt-3 pb-10">
          {FEATURES.map(({ key, icon }) => (
            <FeatureCard
              key={key}
              icon={icon}
              title={t(`landing.features.${key}.title`)}
              body={t(`landing.features.${key}.body`)}
            />
          ))}
        </ul>
        <WaitlistBox />
      </main>
    </>
  );
}
