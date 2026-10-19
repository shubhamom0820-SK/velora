import { Globals } from "@react-spring/web";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { createRef } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { Card } from "@/lib/queries/discover";

import { Deck, type DeckHandle } from "./Deck";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/discover",
  useSearchParams: () => new URLSearchParams(),
}));

beforeAll(() => {
  // Springs land at once: a flight's end is what the swipe test waits on.
  Globals.assign({ skipAnimation: true });
});

function card(n: number, photo: string | null = `https://cdn.test/${n}.jpg`) {
  const one: Card = {
    id: `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
    first_name: `Person${n}`,
    age: 24,
    username: `person${n}`,
    city: "Phagwara",
    hometown: "Jalandhar",
    distance_km: 3,
    intent_ids: [1],
    bio_line: "Chai, cricket and long walks.",
    main_photo_url: photo,
    shows_badge: false,
    is_online: false,
    is_new: false,
  };
  return one;
}

/** Every photo the deck has asked for, in the order drawn. */
function asked(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("img"), (img) => img.src);
}

function topPhoto(): HTMLImageElement {
  const img = screen.getByTestId("top-card").querySelector("img");
  if (!img) throw new Error("the top card has no photo");
  return img;
}

function deck(cards: Card[], ref = createRef<DeckHandle>()) {
  const remaining = [...cards];
  const view = render(
    <Deck ref={ref} cards={remaining} onSwipe={() => true} onOpen={() => {}} />,
  );
  return { ...view, ref };
}

describe("the cards behind wait for the top card's photo (T-9.10, D-1031)", () => {
  it("asks for the top card's photo alone at first", () => {
    const { container } = deck([card(1), card(2), card(3)]);

    expect(asked(container)).toEqual(["https://cdn.test/1.jpg"]);
  });

  it("asks for the two behind once the top photo has loaded", () => {
    const { container } = deck([card(1), card(2), card(3)]);

    fireEvent.load(topPhoto());

    expect(asked(container).sort()).toEqual([
      "https://cdn.test/1.jpg",
      "https://cdn.test/2.jpg",
      "https://cdn.test/3.jpg",
    ]);
  });

  it("asks for them too when the top photo fails, never waiting for ever", () => {
    const { container } = deck([card(1), card(2), card(3)]);

    fireEvent.error(topPhoto());

    expect(asked(container)).toHaveLength(3);
  });

  it("doesn't hold them back behind a top card with no photo", () => {
    const { container } = deck([card(1, null), card(2), card(3)]);

    expect(asked(container).sort()).toEqual([
      "https://cdn.test/2.jpg",
      "https://cdn.test/3.jpg",
    ]);
  });

  it("never says a waiting card has no photo: its place is drawn empty", () => {
    deck([card(1), card(2), card(3)]);

    const waiting = screen.getByRole("article", {
      name: "Person2",
      hidden: true,
    });
    expect(waiting.querySelector("img")).toBeNull();
    expect(
      within(waiting).queryByText(t("discover.card.noPhoto")),
    ).not.toBeInTheDocument();
  });

  it("shows the next card's photo at once after a swipe, and stays settled", () => {
    const cards = [card(1), card(2), card(3), card(4)];
    const ref = createRef<DeckHandle>();
    const { container, rerender } = deck(cards, ref);
    fireEvent.load(topPhoto());

    act(() => {
      ref.current?.swipe("like");
    });
    rerender(
      <Deck
        ref={ref}
        cards={cards.slice(1)}
        onSwipe={() => true}
        onOpen={() => {}}
      />,
    );

    expect(topPhoto().src).toBe("https://cdn.test/2.jpg");
    // The new top card's photo hasn't loaded, yet the one now behind it is
    // asked for: settled once is settled.
    expect(asked(container)).toContain("https://cdn.test/4.jpg");
  });
});
