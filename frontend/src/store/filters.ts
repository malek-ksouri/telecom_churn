/**
 * Filtres globaux (niveau, segment, région, ancienneté) : store Zustand synchronisé avec
 * l'URL. L'URL fait foi : un lien copié rouvre la même vue, et le bouton « précédent » du
 * navigateur revient au filtre précédent (chaque changement crée une entrée d'historique).
 */
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { create } from "zustand";

import { GLOBAL_FILTER_KEYS, type GlobalFilterKey, type GlobalFilters } from "../api/types";

const EMPTY: GlobalFilters = { area: [], cluster: [], risk_level: [], tenure_band: [] };

interface FiltersState {
  filters: GlobalFilters;
  set: (key: GlobalFilterKey, values: string[]) => void;
  remove: (key: GlobalFilterKey, value: string) => void;
  /** Ajoute une valeur (drill-down depuis un graphique). */
  add: (key: GlobalFilterKey, value: string) => void;
  reset: () => void;
  replaceAll: (filters: GlobalFilters) => void;
}

export const useFiltersStore = create<FiltersState>((set) => ({
  filters: EMPTY,
  set: (key, values) => {
    set((s) => ({ filters: { ...s.filters, [key]: values } }));
  },
  remove: (key, value) => {
    set((s) => ({ filters: { ...s.filters, [key]: s.filters[key].filter((v) => v !== value) } }));
  },
  add: (key, value) => {
    set((s) =>
      s.filters[key].includes(value)
        ? s
        : { filters: { ...s.filters, [key]: [...s.filters[key], value] } },
    );
  },
  reset: () => {
    set({ filters: EMPTY });
  },
  replaceAll: (filters) => {
    set({ filters });
  },
}));

export function useGlobalFilters(): GlobalFilters {
  return useFiltersStore((s) => s.filters);
}

export function activeFilterCount(filters: GlobalFilters): number {
  return GLOBAL_FILTER_KEYS.reduce((n, k) => n + filters[k].length, 0);
}

/** URL -> filtres (valeurs inconnues ignorées côté API, pas ici). */
export function parseFilters(search: string): GlobalFilters {
  const params = new URLSearchParams(search);
  const out: GlobalFilters = { ...EMPTY };
  for (const key of GLOBAL_FILTER_KEYS) {
    out[key] = [...new Set(params.getAll(key).filter(Boolean))].sort();
  }
  return out;
}

/** Filtres -> chaîne de recherche canonique (ordre fixe : comparaison stable). */
export function serializeFilters(filters: GlobalFilters, base = ""): string {
  const params = new URLSearchParams(base);
  for (const key of GLOBAL_FILTER_KEYS) {
    params.delete(key);
    for (const value of [...filters[key]].sort()) params.append(key, value);
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

function sameFilters(a: GlobalFilters, b: GlobalFilters): boolean {
  return serializeFilters(a) === serializeFilters(b);
}

/**
 * Synchronisation bidirectionnelle, à monter une fois sous le routeur :
 * - URL modifiée (lien, précédent/suivant) -> store ;
 * - store modifié (barre de filtres, drill-down) -> nouvelle entrée d'historique.
 */
export function useFiltersUrlSync(): void {
  const location = useLocation();
  const navigate = useNavigate();
  const fromUrl = useRef(false);

  // URL -> store.
  useEffect(() => {
    const parsed = parseFilters(location.search);
    const current = useFiltersStore.getState().filters;
    if (!sameFilters(parsed, current)) {
      fromUrl.current = true;
      useFiltersStore.getState().replaceAll(parsed);
    }
  }, [location.search]);

  // Store -> URL.
  useEffect(
    () =>
      useFiltersStore.subscribe((state, previous) => {
        if (sameFilters(state.filters, previous.filters)) return;
        if (fromUrl.current) {
          fromUrl.current = false;
          return;
        }
        const search = serializeFilters(state.filters, window.location.search);
        if (search !== window.location.search) {
          void navigate({ pathname: window.location.pathname, search });
        }
      }),
    [navigate],
  );
}
