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
