"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { errorCopy } from "@/components/onboarding/errorCopy";
import { FormError } from "@/components/onboarding/FormError";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { TextArea } from "@/components/ui/TextArea";
import { useToast } from "@/components/ui/useToast";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import { type Me, useMe } from "@/lib/queries/me";
import {
  useIntents,
  useInterests,
  useSetInterests,
  useSetSeeking,
  useUpdateProfile,
} from "@/lib/queries/onboarding";

/**
 * The lengths and counts the onboarding steps hold to (T-3.7, T-3.8, D-041,
 * D-082): the schema's own, so the browser may; every other rule is the
 * server's, and comes back beside its field. The bio is optional (D-951):
 * emptied, it saves as none.
 */
const NAME_MAX = 30;
const PLACE_MAX = 40;
const ABOUT_MAX = 300;
const MAX_INTENTS = 3;
const INTERESTS = 5;

function label(
  labels: Readonly<Record<string, string>>,
  id: number,
  fallback: string,
): string {
  return labels[String(id)] ?? fallback;
}

function toggled(list: number[], id: number, max: number): number[] {
  if (list.includes(id)) return list.filter((x) => x !== id);
  return list.length < max ? [...list, id] : list;
}

function same(a: readonly number[], b: readonly number[]): boolean {
  return a.length === b.length && a.every((x) => b.includes(x));
}

/** Edit profile (T-9.8), at `/you/edit`: the prototype's sheet, as a screen. */
export function EditProfile() {
  const me = useMe();
  if (me.isPending) {
    return (
      <div aria-busy className="flex flex-col gap-3 p-(--shell-gutter)">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
        <Skeleton className="h-24" />
      </div>
    );
  }
  if (me.isError) {
    return (
      <div className="p-(--shell-gutter)">
        <ErrorState onRetry={() => void me.refetch()} />
      </div>
    );
  }
  return <Form me={me.data} />;
}

/**
 * The fields, from `Me`: first name, hometown, city and about
 * (`PATCH /me/profile`), what you're looking for (`POST /me/seeking`, with
 * your seeking as it is) and your five interests (`PUT /me/interests`). Save
 * sends only the parts that changed, one after another; a refusal stops there
 * and says why, beside its field where it names one.
 */
function Form({ me }: { me: Me }) {
  const router = useRouter();
  const toast = useToast();
  const intents = useIntents();
  const interests = useInterests();
  const profile = useUpdateProfile();
  const seeking = useSetSeeking();
  const picks = useSetInterests();
  const [firstName, setFirstName] = useState(me.profile.first_name ?? "");
  const [hometown, setHometown] = useState(me.profile.hometown ?? "");
  const [city, setCity] = useState(me.profile.city ?? "");
  const [about, setAbout] = useState(me.profile.about ?? "");
  const [intentIds, setIntentIds] = useState(me.profile.intent_ids);
  const [interestIds, setInterestIds] = useState(me.profile.interest_ids);
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);
  const copy = failure ? errorCopy(failure) : null;

  const text = {
    first_name: firstName.trim(),
    hometown: hometown.trim(),
    city: city.trim(),
    about: about.trim(),
  };
  const valid =
    text.first_name.length >= 1 &&
    text.hometown.length >= 1 &&
    text.city.length >= 1 &&
    intentIds.length >= 1 &&
    interestIds.length === INTERESTS;

  async function save() {
    setSaving(true);
    setFailure(null);
    try {
      const changed = Object.fromEntries(
        Object.entries(text).filter(
          ([key, value]) =>
            value !== (me.profile[key as keyof typeof text] ?? ""),
        ),
      );
      if (Object.keys(changed).length > 0) await profile.mutateAsync(changed);
      if (!same(intentIds, me.profile.intent_ids) && me.profile.seeking) {
        await seeking.mutateAsync({
          seeking: me.profile.seeking,
          intent_ids: intentIds,
        });
      }
      if (!same(interestIds, me.profile.interest_ids)) {
        await picks.mutateAsync(interestIds);
      }
      toast.show({ message: t("you.editSaved") });
      router.push("/you");
    } catch (error) {
      setFailure(error);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      noValidate
      className="text-ink flex flex-1 flex-col gap-5 p-(--shell-gutter) pb-8"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid && !saving) void save();
      }}
    >
      <h1 className="text-title-1">{t("you.edit")}</h1>
      <div className="flex flex-col gap-3">
        <Field
          label={t("onboarding.name.firstName")}
          autoComplete="given-name"
          maxLength={NAME_MAX}
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          error={copy?.fields.first_name}
        />
        <Field
          label={t("onboarding.name.hometown")}
          maxLength={PLACE_MAX}
          value={hometown}
          onChange={(event) => setHometown(event.target.value)}
          error={copy?.fields.hometown}
        />
        <Field
          label={t("onboarding.name.city")}
          autoComplete="address-level2"
          maxLength={PLACE_MAX}
          value={city}
          onChange={(event) => setCity(event.target.value)}
          error={copy?.fields.city}
        />
        <TextArea
          label={t("onboarding.about.label")}
          rows={6}
          maxLength={ABOUT_MAX}
          value={about}
          onChange={(event) => setAbout(event.target.value)}
          error={copy?.fields.about}
        />
      </div>
      <fieldset className="flex flex-col gap-2.5">
        <legend className="text-small text-mute mb-2.5">
          {t("onboarding.lookingFor.intents")} ·{" "}
          {t("onboarding.lookingFor.intentsHelp")}
        </legend>
        {intents.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : intents.isError ? (
          <ErrorState onRetry={() => void intents.refetch()} />
        ) : (
          <div className="flex flex-wrap gap-2">
            {intents.data.map((intent) => (
              <Chip
                key={intent.id}
                active={intentIds.includes(intent.id)}
                onClick={() =>
                  setIntentIds((ids) => toggled(ids, intent.id, MAX_INTENTS))
                }
              >
                {label(en.intents, intent.id, intent.label)}
              </Chip>
            ))}
          </div>
        )}
      </fieldset>
      <fieldset className="flex flex-col gap-2.5">
        <legend className="text-small text-mute mb-2.5">
          {t("onboarding.interests.sub", { count: interestIds.length })}
        </legend>
        {interests.isPending ? (
          <Skeleton className="h-32 w-full" />
        ) : interests.isError ? (
          <ErrorState onRetry={() => void interests.refetch()} />
        ) : (
          <div className="flex flex-wrap gap-2">
            {interests.data.map((interest) => (
              <Chip
                key={interest.id}
                active={interestIds.includes(interest.id)}
                onClick={() =>
                  setInterestIds((ids) => toggled(ids, interest.id, INTERESTS))
                }
              >
                {label(en.interests, interest.id, interest.label)}
              </Chip>
            ))}
          </div>
        )}
      </fieldset>
      {copy && Object.keys(copy.fields).length === 0 && (
        <FormError copy={copy} />
      )}
      <Button type="submit" fullWidth loading={saving} disabled={!valid}>
        {t("you.editSave")}
      </Button>
    </form>
  );
}
