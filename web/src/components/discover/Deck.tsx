"use client";

import { animated, to, useSpring, type Interpolation } from "@react-spring/web";
import { useDrag } from "@use-gesture/react";
import {
  useCallback,
  useImperativeHandle,
  useRef,
  useState,
  type Ref,
} from "react";

import { t } from "@/i18n/t";
import type { Card, SwipeDirection } from "@/lib/queries/discover";

import { SwipeCard } from "./SwipeCard";
import { exitOf, stampsOf, swipeOf, tiltOf } from "./swipeMath";
import { useReducedMotion } from "./useReducedMotion";

/** How many cards are drawn at once (T-6.5): the top and two behind it. */
export const RENDERED = 3;

/** What the action row and the keyboard ask of the deck. */
export type DeckHandle = {
  /** Swipe the top card as a release would: false if nothing was swiped. */
  swipe: (direction: SwipeDirection) => boolean;
};

type DeckProps = {
  /** The cards left, top first. */
  cards: readonly Card[];
  /**
   * The swipe, decided: the parent sends it and takes the card off the deck
   * (optimistically, T-6.5), or returns false to keep it, and the card springs
   * back.
   */
  onSwipe: (card: Card, direction: SwipeDirection) => boolean;
  /** A tap on the card, not a drag: its profile. */
  onOpen: (card: Card) => void;
  ref?: Ref<DeckHandle>;
};

type Leaving = {
  /** Its own, since one person can leave twice: swiped, put back, swiped. */
  key: number;
  card: Card;
  direction: SwipeDirection;
  from: readonly [number, number];
  /** The deck's size when it left, for where off the screen it flies. */
  size: readonly [number, number];
};

/**
 * The swipe deck (T-6.5): three cards drawn, the top one dragged with
 * @use-gesture/react and moved by @react-spring/web's springs, which write
 * the transform straight to the element, never through React, so a drag
 * renders nothing (the 60 fps check). Released past 100 px or flicked it
 * swipes (`swipeOf`); a swiped card flies off on its own layer while the next
 * is already on top.
 *
 * The two cards behind ask for their photos only once the top card's photo
 * has loaded, or failed (T-9.10, D-1031): asked for together, three photos
 * share the line and arrive together, so the one on screen took three times
 * as long, the first load's largest wait. Once settled it stays settled: by
 * then the next photos are what a swipe shows, and they load straight away.
 */
export function Deck({ cards, onSwipe, onOpen, ref }: DeckProps) {
  const reduced = useReducedMotion();
  const [leaving, setLeaving] = useState<readonly Leaving[]>([]);
  const frame = useRef<HTMLDivElement>(null);
  const flights = useRef(0);
  const top = cards[0];
  const [settled, setSettled] = useState(false);
  // A top card without a photo has nothing to wait for (set while rendering,
  // React's pattern for state that follows the props).
  if (!settled && top && top.main_photo_url === null) setSettled(true);

  const decide = useCallback(
    (
      card: Card,
      direction: SwipeDirection,
      from: readonly [number, number],
    ): boolean => {
      if (!onSwipe(card, direction)) return false;
      flights.current += 1;
      const key = flights.current;
      const box = frame.current?.getBoundingClientRect();
      const size = [box?.width || 400, box?.height || 560] as const;
      setLeaving((now) => [...now, { key, card, direction, from, size }]);
      return true;
    },
    [onSwipe],
  );

  useImperativeHandle(
    ref,
    () => ({
      swipe: (direction) => (top ? decide(top, direction, [0, 0]) : false),
    }),
    [top, decide],
  );

  const landed = (key: number) =>
    setLeaving((now) => now.filter((one) => one.key !== key));

  return (
    <div
      ref={frame}
      role="region"
      aria-label={t("discover.deck")}
      className="relative h-[min(35rem,calc(100dvh-17rem))] min-h-96 w-full"
    >
      {cards
        .slice(1, RENDERED)
        .map((card, index) => (
          <div
            key={`behind-${card.id}`}
            aria-hidden
            inert
            className="absolute inset-0 transition-transform duration-150"
            style={{
              transform: `translateY(${(index + 1) * 10}px) scale(${1 - (index + 1) * 0.04})`,
              zIndex: RENDERED - index - 1,
            }}
          >
            <SwipeCard card={card} deferPhoto={!settled} />
          </div>
        ))
        .reverse()}
      {top && (
        <TopCard
          key={`top-${top.id}`}
          card={top}
          reduced={reduced}
          onDecide={(direction, from) => decide(top, direction, from)}
          onOpen={() => onOpen(top)}
          onPhotoSettled={() => setSettled(true)}
        />
      )}
      {leaving.map((one) => (
        <LeavingCard
          key={`leaving-${one.key}`}
          leaving={one}
          reduced={reduced}
          onDone={() => landed(one.key)}
        />
      ))}
    </div>
  );
}

type TopCardProps = {
  card: Card;
  reduced: boolean;
  onDecide: (
    direction: SwipeDirection,
    from: readonly [number, number],
  ) => boolean;
  onOpen: () => void;
  /** Its photo loaded or failed: the cards behind may ask for theirs. */
  onPhotoSettled: () => void;
};

function TopCard({
  card,
  reduced,
  onDecide,
  onOpen,
  onPhotoSettled,
}: TopCardProps) {
  const [{ x, y }, spring] = useSpring(() => ({ x: 0, y: 0 }));
  // Set by a drag, read by the name's link: a drag that ends on the name is
  // not a tap on it.
  const dragged = useRef(false);

  const bind = useDrag(
    ({ active, movement, velocity, direction, tap, event }) => {
      if (tap) {
        // The name is a link of its own, which navigates by itself.
        const target = event.target;
        if (target instanceof Element && target.closest("a")) return;
        onOpen();
        return;
      }
      dragged.current = true;
      const [mx, my] = movement;
      if (active) {
        void spring.start({ x: mx, y: my, immediate: true });
        return;
      }
      const swipe = swipeOf({ movement, velocity, direction });
      if (swipe && onDecide(swipe, [mx, my])) return;
      void spring.start({ x: 0, y: 0, immediate: false });
    },
    { filterTaps: true },
  );

  const stamp = (which: "like" | "pass" | "super") =>
    to([x, y], (dx: number, dy: number) => stampsOf(dx, dy)[which]);

  return (
    <animated.div
      {...bind()}
      data-testid="top-card"
      className="absolute inset-0 z-10 cursor-grab touch-none will-change-transform active:cursor-grabbing"
      style={{ x, y, rotate: x.to((dx) => tiltOf(dx, reduced)) }}
    >
      <SwipeCard
        card={card}
        onPhotoSettled={onPhotoSettled}
        onNameClick={(event) => {
          if (dragged.current) event.preventDefault();
          dragged.current = false;
        }}
        stamps={
          <>
            <Stamp
              word={t("discover.card.like")}
              opacity={stamp("like")}
              className="border-accent text-accent top-6 left-5 -rotate-12"
            />
            <Stamp
              word={t("discover.card.pass")}
              opacity={stamp("pass")}
              className="border-ink text-ink top-6 right-5 rotate-12"
            />
            <Stamp
              word={t("discover.card.super")}
              opacity={stamp("super")}
              className="border-accent text-accent bottom-6 left-1/2 -translate-x-1/2"
            />
          </>
        }
      />
    </animated.div>
  );
}

function Stamp({
  word,
  opacity,
  className,
}: {
  word: string;
  opacity: Interpolation<number>;
  className: string;
}) {
  return (
    <animated.span
      aria-hidden
      style={{ opacity }}
      className={`rounded-button bg-surface text-title-2 absolute border-2 px-3 py-1 tracking-widest uppercase ${className}`}
    >
      {word}
    </animated.span>
  );
}

function LeavingCard({
  leaving,
  reduced,
  onDone,
}: {
  leaving: Leaving;
  reduced: boolean;
  onDone: () => void;
}) {
  const [width, height] = leaving.size;
  const [exitX, exitY] = exitOf(leaving.direction, width, height);
  const [fromX, fromY] = leaving.from;
  const { x, y, opacity } = useSpring({
    from: { x: fromX, y: fromY, opacity: 1 },
    // Under reduced motion it fades where it is: no flight, no tilt.
    to: reduced
      ? { x: fromX, y: fromY, opacity: 0 }
      : { x: exitX, y: exitY, opacity: 1 },
    config: { tension: 260, friction: 30 },
    onRest: onDone,
  });
  return (
    <animated.div
      aria-hidden
      inert
      className="pointer-events-none absolute inset-0 z-20 will-change-transform"
      style={{ x, y, opacity, rotate: x.to((dx) => tiltOf(dx, reduced)) }}
    >
      <SwipeCard card={leaving.card} />
    </animated.div>
  );
}
