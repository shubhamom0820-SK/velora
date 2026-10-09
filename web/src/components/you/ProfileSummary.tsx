"use client";

import { BadgeCheck, MapPin } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";
import { ButtonLink } from "@/components/ui/ButtonLink";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import type { Me } from "@/lib/queries/me";
import { useProfile } from "@/lib/queries/profiles";

/** An intent's words from `en.ts` by id (P-26), as the onboarding step reads them. */
function intentLabel(id: number): string | null {
  const labels: Readonly<Record<string, string>> = en.intents;
  return labels[String(id)] ?? null;
}

/**
 * Who you are, as others see you (T-9.8): your main photo, name and age,
 * username, city, intents and about, from `Me`; and the badge as others see
 * it, from your own profile (`GET /users/{id}`, which records no view, D-493),
 * since the badge is the main photo's (D-910), never `is_verified` alone.
 */
export function ProfileSummary({ me }: { me: Me }) {
  const profile = useProfile(me.id);
  const name = me.profile.first_name ?? "";

  return (
    <section
      aria-label={name}
      className="flex flex-col gap-3 px-(--shell-gutter) pt-5 pb-2"
    >
      <div className="flex items-center gap-4">
        <Avatar
          name={name}
          src={profile.data?.main_photo_url ?? undefined}
          size={66}
          verified={profile.data?.shows_badge}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="text-title-1 text-ink truncate">
            {me.age === null
              ? name
              : t("profile.nameAge", { name, age: me.age })}
          </p>
          {me.profile.username && (
            <p className="text-small text-mute truncate">
              {t("you.username", { username: me.profile.username })}
            </p>
          )}
        </div>
      </div>
      {me.profile.city && (
        <p className="text-small text-mute flex items-center gap-1">
          <Icon icon={MapPin} size={12} />
          {me.profile.city}
          {me.profile.hometown &&
            ` · ${t("profile.from", { hometown: me.profile.hometown })}`}
        </p>
      )}
      {me.profile.intent_ids.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {me.profile.intent_ids.map((id) => {
            const label = intentLabel(id);
            return label && <Chip key={id}>{label}</Chip>;
          })}
        </div>
      )}
      {me.profile.about && (
        <p className="text-body text-ink">{me.profile.about}</p>
      )}
      {profile.isPending ? (
        <Skeleton className="w-1/2" />
      ) : profile.isError ? (
        <ErrorState
          title={t("you.summaryFailed")}
          onRetry={() => void profile.refetch()}
        />
      ) : (
        <SelfieLine me={me} badge={profile.data.shows_badge} />
      )}
      <div className="flex flex-wrap gap-2">
        <ButtonLink href="/you/edit" variant="ghost" size="sm">
          {t("you.edit")}
        </ButtonLink>
        <ButtonLink href="/you/photos" variant="ghost" size="sm">
          {t("you.photos")}
        </ButtonLink>
      </div>
    </section>
  );
}

/**
 * The badge in words (D-262, D-910): "Selfie matched" while it shows; the
 * selfie matched but the main photo hasn't yet; or no check made, which only
 * a man can be (D-008).
 */
function SelfieLine({ me, badge }: { me: Me; badge: boolean }) {
  const words = badge
    ? t("ui.selfieMatched")
    : me.is_verified
      ? t("you.selfieMainNotYet")
      : t("you.selfieNone");
  return (
    <p className="text-small text-mute flex items-center gap-1.5">
      <Icon
        icon={BadgeCheck}
        size={15}
        className={badge ? "text-accent" : "text-mute"}
      />
      {words}
    </p>
  );
}
