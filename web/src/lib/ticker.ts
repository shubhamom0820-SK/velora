import { useSyncExternalStore } from "react";

/** How often every countdown on the page moves together (T-7.10). */
export const TICK_MS = 1000;

let now = Date.now();
let timer: ReturnType<typeof setInterval> | undefined;
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (timer === undefined) {
    now = Date.now();
    timer = setInterval(() => {
      now = Date.now();
      for (const notify of listeners) notify();
    }, TICK_MS);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer !== undefined) {
      clearInterval(timer);
      timer = undefined;
    }
  };
}

function snapshot(): number {
  return now;
}

/**
 * The time now, in ms, moving once a second: one shared ticker for the whole
 * page, never one per row (T-7.10). It runs while anything reads it and stops
 * when the last reader leaves.
 */
export function useNow(): number {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
