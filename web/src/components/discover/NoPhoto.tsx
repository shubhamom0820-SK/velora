import { t } from "@/i18n/t";

/**
 * A card with no photo (D-392, 08-DESIGN §8): the initial inside a grey
 * silhouette, a round head and shoulders in `--line-strong`, and the words.
 */
export function NoPhoto({ name }: { name: string }) {
  const initial = Array.from(name.trim())[0]?.toUpperCase() ?? "";
  return (
    <div className="flex size-full flex-col items-center justify-end gap-3 pb-6">
      <div aria-hidden className="relative flex flex-col items-center">
        <div className="rounded-pill bg-line-strong text-title-1 text-surface flex size-24 items-center justify-center">
          {initial}
        </div>
        <div className="bg-line-strong -mt-2 h-14 w-40 rounded-t-full" />
      </div>
      <p className="text-small text-mute">{t("discover.card.noPhoto")}</p>
    </div>
  );
}
