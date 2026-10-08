"use client";

import { Check, MapPin, UserX } from "lucide-react";

import { GiftCounts } from "@/components/gifts/GiftCounts";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { useMe } from "@/lib/queries/me";
import { type PublicProfile, useProfile } from "@/lib/queries/profiles";

import { AlbumSection } from "./AlbumSection";
import { KudosPrompt } from "./KudosPrompt";
import { intentLabel, interestLabel, KUDOS } from "./labels";
import { ProfileActions } from "./ProfileActions";
import { ProfileGallery } from "./ProfileGallery";
import { ProfileMenu } from "./ProfileMenu";

/**
 * A person's profile in the app (T-6.8, 08-DESIGN §8), at `/people/[id]`, the
 * one route a profile has: the deck's tap, search's rows and Liked you's
 * tiles all lead here. Their text is theirs, rendered by React, never as HTML,
 * under the nonce routes' CSP (D-541). Every refusal is the API's one
 * `NOT_FOUND`, shown as one "isn't available".
 */
export function ProfileScreen({ id }: { id: string }) {
  const profile = useProfile(id);
  const meId = useMe().data?.id;

  if (profile.isPending) {
    return (
      <div aria-busy className="flex flex-col gap-4">
        <Skeleton className="h-[390px] rounded-none" />
        <div className="flex flex-col gap-3 px-(--shell-gutter)">
          <Skeleton className="w-1/2" />
          <Skeleton />
          <Skeleton className="w-2/3" />
        </div>
      </div>
    );
  }
  if (profile.isError) {
    return profile.error instanceof ApiError &&
      profile.error.code === "NOT_FOUND" ? (
      <EmptyState
        icon={UserX}
        title={t("profile.notFound")}
        body={t("profile.notFoundBody")}
      />
    ) : (
      <ErrorState
        title={t("profile.failed")}
        onRetry={() => void profile.refetch()}
      />
    );
  }
  return <Profile person={profile.data} own={profile.data.id === meId} />;
}

function Profile({ person, own }: { person: PublicProfile; own: boolean }) {
  const place = [
    person.city,
    person.distance_km === null
      ? null
      : t("profile.km", { km: person.distance_km }),
    person.hometown ? t("profile.from", { hometown: person.hometown }) : null,
  ].filter((part): part is string => Boolean(part));
  const intents = person.intent_ids
    .map(intentLabel)
    .filter((label): label is string => label !== null);
  const interests = person.interest_ids
    .map(interestLabel)
    .filter((label): label is string => label !== null);

  return (
    <article className="flex flex-1 flex-col">
      <div className="relative">
        <ProfileGallery urls={person.photo_urls} />
        <div className="absolute top-3 right-3">
          <ProfileMenu
            username={person.username}
            firstName={person.first_name}
          />
        </div>
      </div>
      <span aria-hidden className="bg-accent block h-0.5" />
      <div className="flex flex-col gap-5 px-(--shell-gutter) py-5">
        <header className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-title-1 text-ink">
              {person.age === null
                ? person.first_name
                : t("profile.nameAge", {
                    name: person.first_name,
                    age: person.age,
                  })}
            </h1>
            {person.shows_badge && (
              <span className="bg-accent text-on-accent rounded-pill flex size-5 items-center justify-center">
                <Icon icon={Check} size={13} label={t("ui.selfieMatched")} />
              </span>
            )}
            {person.is_online && (
              <span className="bg-accent-soft text-accent text-micro rounded-pill px-2 py-0.5">
                {t("profile.online")}
              </span>
            )}
          </div>
          {place.length > 0 && (
            <p className="text-small text-mute flex items-center gap-1">
              <Icon icon={MapPin} size={14} />
              {place.join(" · ")}
            </p>
          )}
          {person.shows_badge && (
            <p className="text-small text-mute flex items-center gap-1">
              <Icon icon={Check} size={14} className="text-accent" />
              {t("profile.selfieNote")}
            </p>
          )}
          {own && <p className="text-small text-mute">{t("profile.yours")}</p>}
        </header>
        {intents.length > 0 && (
          <Section title={t("profile.lookingFor")}>
            <Chips labels={intents} />
          </Section>
        )}
        {person.about && (
          <Section title={t("profile.about")}>
            <p className="text-body text-ink whitespace-pre-line">
              {person.about}
            </p>
          </Section>
        )}
        {interests.length > 0 && (
          <Section title={t("profile.interests")}>
            <Chips labels={interests} />
          </Section>
        )}
        {!own && person.thread?.kudos === "can_give" && (
          <KudosPrompt id={person.id} name={person.first_name} />
        )}
        {person.kudos && (
          <Section title={t("profile.kudos")}>
            <ul className="bg-surface rounded-card border-line grid grid-cols-2 gap-3 border p-4">
              {KUDOS.map((kind) => (
                <li key={kind} className="flex flex-col">
                  <span className="text-title-2 text-ink">
                    {person.kudos?.[kind] ?? 0}
                  </span>
                  <span className="text-small text-mute">
                    {t(`profile.kudosKind.${kind}`)}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        )}
        <GiftCounts userId={person.id} own={own} />
        {person.album_photo_count > 0 && (
          <AlbumSection
            id={person.id}
            count={person.album_photo_count}
            own={own}
          />
        )}
      </div>
      {!own && (
        <ProfileActions
          id={person.id}
          firstName={person.first_name}
          canGift={person.can_gift}
        />
      )}
    </article>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-micro text-mute tracking-wide uppercase">{title}</h2>
      {children}
    </section>
  );
}

function Chips({ labels }: { labels: string[] }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {labels.map((label) => (
        <li
          key={label}
          className="rounded-pill border-line text-ui text-ink flex h-8 items-center border px-3"
        >
          {label}
        </li>
      ))}
    </ul>
  );
}
