import { create } from "zustand";

type StoreSheetState = {
  /** The store sheet is up (T-5.5; T-8.7 fills it). */
  open: boolean;
  show: () => void;
  hide: () => void;
};

/**
 * Whether the store sheet is open. The balance pill and "Buy Velas" open it,
 * and so does any mutation the API refuses with `INSUFFICIENT_CREDITS`
 * (QueryProvider's mutation cache).
 */
export const useStoreSheet = create<StoreSheetState>()((set) => ({
  open: false,
  show: () => set({ open: true }),
  hide: () => set({ open: false }),
}));
