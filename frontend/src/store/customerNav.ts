/**
 * Fiche client globale : ouverte par `?client=<id>` sur n'importe quelle page (liste, chat…).
 * La page Clients à risque y inscrit la navigation précédent / suivant de sa liste filtrée.
 */
import { useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { create } from "zustand";

interface CustomerNavState {
  onPrev: (() => void) | null;
  onNext: (() => void) | null;
  position: string | null;
  setNav: (nav: { onPrev: (() => void) | null; onNext: (() => void) | null; position: string | null }) => void;
  clearNav: () => void;
}

export const useCustomerNav = create<CustomerNavState>((set) => ({
  onPrev: null,
  onNext: null,
  position: null,
  setNav: (nav) => {
    set(nav);
  },
  clearNav: () => {
    set({ onPrev: null, onNext: null, position: null });
  },
}));

/** Ouvre (ou ferme, avec `null`) la fiche d'un client sur la page courante. */
export function useOpenCustomer(): (id: number | null) => void {
  const navigate = useNavigate();
  const location = useLocation();
  return useCallback(
    (id) => {
      const params = new URLSearchParams(location.search);
      if (id === null) params.delete("client");
      else params.set("client", String(id));
      const search = params.toString();
      void navigate({ pathname: location.pathname, search: search ? `?${search}` : "" });
    },
    [navigate, location.pathname, location.search],
  );
}
