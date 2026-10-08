import { Check } from "lucide-react";
import Link from "next/link";
import type { MouseEvent, ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import type { Card } from "@/lib/queries/discover";

import { NoPhoto } from "./NoPhoto";

/** The in-app profile, T-6.8's screen at this one route (agreed 8 October 2026). */
export function profileHref(id: string): string {
  return `/people/${id}`;
}

/** "Simran, 24", or "Simran" when she hides her age. */
export function nameAge(card: Pick<Card, "first_name" | "age">): string {
  return card.age === null
    ? card.first_name
    : t("discover.card.nameAge", { name: card.first_name, age: card.age });
}

/** "Phagwara · 3 km", each part left out when it is hidden or unknown. */
export function placeOf(card: Pick<Card, "city" | "distance_km">): string {
  return [
    card.city,
    card.distance_km === null
      ? null
      : t("discover.card.km", { km: card.distance_km }),
  ]
    .filter(Boolean)
    .join(" · ");
}

/** An intent's words from `en.ts` by id (P-26); an id not there shows nothing. */
function intentWords(id: number): string | undefined {
  const words: Readonly<Record<string, string>> = en.intents;
  return words[String(id)];
}

type SwipeCardProps = {
  card: Card;
  /** The LIKE, PASS and SUPER stamps, on the top card only. */
  stamps?: ReactNode;
  /** Stops the name's link when the press was a drag, not a tap. */
  onNameClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
};

/**
 * One person on the deck (08-DESIGN §8): the photo on top, 336 of the card's
 * 560 px; the thread, a thin red line; the words below. Text never sits on the
 * photo. Everything here is what the API sent (T-6.2's `Card`); React escapes
 * it, and nothing is drawn as HTML.
 */
export function SwipeCard({ card, stamps, onNameClick }: SwipeCardProps) {
  const photo = card.main_photo_url;
  // D-393: no shown face, no badge. The server's rule already says so; the
  // card holds to it too, so a badge can never sit on a silhouette.
  const badge = card.shows_badge && photo !== null;
  const place = placeOf(card);
  const intents = card.intent_ids
    .map(intentWords)
    .filter((words) => words !== undefined);

  return (
    <article
      aria-label={card.first_name}
      className="rounded-swipe bg-surface shadow-2 relative flex size-full flex-col overflow-hidden select-none"
    >
      <div className="bg-surface-2 relative h-3/5 shrink-0">
        {photo ? (
          // A plain <img>, as Avatar's: the photo host is the CSP's (T-4.6).
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photo}
            alt=""
            draggable={false}
            className="size-full object-cover"
          />
        ) : (
          <NoPhoto name={card.first_name} />
        )}
        {card.is_new && (
          <span className="rounded-pill bg-ink text-micro text-chrome-ink absolute top-4 left-4 px-2.5 py-1">
            {t("discover.card.new")}
          </span>
        )}
        {stamps}
      </div>
      <div aria-hidden className="bg-accent h-0.5 shrink-0" />
      <div className="flex min-h-0 flex-1 flex-col gap-2 px-5 pt-4 pb-5">
        <div className="flex items-center gap-2">
          <h2 className="text-title-1 text-ink truncate">
            <Link
              href={profileHref(card.id)}
              onClick={onNameClick}
              draggable={false}
              aria-label={t("discover.card.openProfile", {
                name: card.first_name,
              })}
              className="focus-visible:outline-accent rounded-input focus-visible:outline-2"
            >
              {nameAge(card)}
            </Link>
          </h2>
          {badge && (
            <span
              role="img"
              aria-label={t("ui.selfieMatched")}
              className="rounded-pill bg-accent text-on-accent flex size-5 shrink-0 items-center justify-center"
            >
              <Icon icon={Check} size={13} />
            </span>
          )}
        </div>
        {(place || card.is_online) && (
          <div className="flex flex-wrap items-center gap-2">
            {place && <p className="text-small text-mute">{place}</p>}
            {card.is_online && (
              <span className="rounded-pill bg-accent-soft text-micro text-accent px-2 py-0.5">
                {t("discover.card.online")}
              </span>
            )}
          </div>
        )}
        {intents.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {intents.map((words) => (
              <li
                key={words}
                className="rounded-pill bg-surface-2 text-ui text-ink px-3 py-1"
              >
                {words}
              </li>
            ))}
          </ul>
        )}
        {card.bio_line && (
          <p className="text-body text-ink line-clamp-2">{card.bio_line}</p>
        )}
      </div>
    </article>
  );
}
