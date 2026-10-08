"use client";

import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { type KudosKind, useGiveKudos } from "@/lib/queries/kudos";

import { KUDOS } from "./labels";

/**
 * The kudos prompt on someone's profile (T-8.8, D-790): shown only while their
 * Thread with you says `can_give`, so a tap is never refused for being too
 * early (D-680) nor a second kudos (P-580). One tap gives that kind, once ever;
 * the profile is asked again and the prompt goes. Kudos already given (a tap
 * elsewhere, a second tab) is taken as given, never shown as an error.
 */
export function KudosPrompt({ id, name }: { id: string; name: string }) {
  const toast = useToast();
  const give = useGiveKudos();

  function onGive(kind: KudosKind) {
    give.mutate(
      { toId: id, kind },
      {
        onSuccess: () => toast.show({ message: t("profile.kudosSent") }),
        onError: (error) => {
          if (error instanceof ApiError && error.code === "ALREADY_EXISTS") {
            return;
          }
          const message =
            error instanceof ApiError &&
            error.code === "NOT_ALLOWED" &&
            error.details?.why === "too_early"
              ? t("profile.kudosTooEarly")
              : t("profile.kudosFailed");
          toast.show({ message, tone: "error" });
        },
      },
    );
  }

  return (
    <section
      aria-label={t("profile.kudosAsk", { name })}
      className="bg-surface rounded-card border-line flex flex-col gap-3 border p-4"
    >
      <div className="flex flex-col gap-1">
        <h2 className="text-title-2 text-ink">
          {t("profile.kudosAsk", { name })}
        </h2>
        <p className="text-small text-mute">{t("profile.kudosAskBody")}</p>
      </div>
      <ul className="flex flex-wrap gap-2">
        {KUDOS.map((kind) => (
          <li key={kind}>
            <button
              type="button"
              onClick={() => onGive(kind)}
              disabled={give.isPending}
              className="rounded-pill border-line text-ui text-ink flex h-8 items-center border px-3 disabled:opacity-60"
            >
              {t(`profile.kudosKind.${kind}`)}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
