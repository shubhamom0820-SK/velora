"use client";

import { Gift as GiftIcon } from "lucide-react";
import Link from "next/link";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Toggle } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import {
  type ReceivedGift,
  useGifts,
  useReceivedGifts,
} from "@/lib/queries/gifts";
import { useMe, useUpdateSettings } from "@/lib/queries/me";

import { giftNamed } from "./giftNames";

/** When a gift came, in the reader's own time zone: "9 Oct 2026". */
export const receivedDay = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
});

/**
 * Her gifts in the You tab (T-8.10): newest first, who sent each and when,
 * never what he paid or whether it was free (D-652); and the switch that shows
 * or hides their counts on her profile (`show_gifts`, D-016). Hers alone: the
 * You page mounts it for a woman. T-9.8 builds the rest of the tab around it.
 */
export function ReceivedGifts() {
  const toast = useToast();
  const me = useMe();
  const settings = useUpdateSettings();
  const received = useReceivedGifts();
  const catalogue = useGifts();
  const shown = me.data?.profile.show_gifts ?? true;

  function onToggle(on: boolean) {
    settings.mutate(
      { show_gifts: on },
      {
        onError: () =>
          toast.show({ message: t("gifts.saveFailed"), tone: "error" }),
      },
    );
  }

  const items = received.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <section className="flex flex-col gap-3 px-(--shell-gutter) py-5">
      <h2 className="text-title-2 text-ink">{t("gifts.yours")}</h2>
      <Toggle
        label={t("gifts.show")}
        description={t("gifts.showBody")}
        checked={shown}
        disabled={!me.data || settings.isPending}
        onChange={onToggle}
      />
      {received.isPending ? (
        <div aria-busy className="flex flex-col gap-3">
          <Skeleton />
          <Skeleton className="w-2/3" />
        </div>
      ) : received.isError ? (
        <ErrorState
          title={t("gifts.listFailed")}
          onRetry={() => void received.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={GiftIcon}
          title={t("gifts.empty")}
          body={t("gifts.emptyBody")}
        />
      ) : (
        <>
          <ul className="flex flex-col">
            {items.map((item) => (
              <Row
                key={item.id}
                item={item}
                gift={giftNamed(catalogue.data?.gifts, item.gift_id)}
              />
            ))}
          </ul>
          {received.hasNextPage && (
            <Button
              variant="ghost"
              size="sm"
              loading={received.isFetchingNextPage}
              onClick={() => void received.fetchNextPage()}
            >
              {t("gifts.more")}
            </Button>
          )}
        </>
      )}
    </section>
  );
}

function Row({
  item,
  gift,
}: {
  item: ReceivedGift;
  gift: { label: string; asset: string | null };
}) {
  const sender = item.sender;
  const name = sender.deleted
    ? t("chats.deletedAccount")
    : (sender.first_name ?? "");
  const body = (
    <>
      <Avatar
        name={name}
        src={sender.main_photo_url ?? undefined}
        size={46}
        online={sender.is_online}
        verified={sender.shows_badge}
      />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-ui text-ink truncate">
          {gift.asset && <span aria-hidden>{gift.asset} </span>}
          {t("gifts.from", { gift: gift.label, name })}
        </span>
        <span className="text-small text-mute">
          {receivedDay.format(new Date(item.created_at))}
        </span>
      </span>
    </>
  );
  return (
    <li className="border-line border-b last:border-b-0">
      {sender.deleted ? (
        <div className="flex items-center gap-3 py-3">{body}</div>
      ) : (
        <Link
          href={`/people/${sender.id}`}
          className="focus-visible:outline-accent flex items-center gap-3 py-3 focus-visible:outline-2"
        >
          {body}
        </Link>
      )}
    </li>
  );
}
