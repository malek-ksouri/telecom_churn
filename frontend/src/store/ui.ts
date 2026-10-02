/** Préférences d'interface conservées entre les visites (barre latérale repliée). */
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UiState {
  navCollapsed: boolean;
  toggleNav: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      navCollapsed: false,
      toggleNav: () => {
        set((s) => ({ navCollapsed: !s.navCollapsed }));
      },
    }),
    { name: "churn-ui" },
  ),
);

/** Écran étroit (tablette) : la barre latérale reste repliée pour laisser la place au contenu. */
export const NARROW_QUERY = "(max-width: 1100px)";

export function useNavCollapsed(narrow: boolean): boolean {
  const collapsed = useUiStore((s) => s.navCollapsed);
  return narrow || collapsed;
}
