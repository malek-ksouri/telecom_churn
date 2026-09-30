/**
 * Hooks TanStack Query, un par endpoint. Les clés de cache incluent les filtres : changer un
 * filtre relance la requête, revenir à un filtre déjà vu est instantané (cache).
 */
import { QueryClient, keepPreviousData, useQuery } from "@tanstack/react-query";

import { ApiError, apiGet } from "./client";
import type { Dimension, GlobalFilters } from "./types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000, // artefacts figés : pas de rafraîchissement agressif
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
        failureCount < 2,
    },
  },
});

/** Filtres non vides uniquement (clé de cache stable). */
function clean(filters: Partial<GlobalFilters>): Partial<GlobalFilters> {
  return Object.fromEntries(
    Object.entries(filters)
      .filter(([, v]) => v.length > 0)
      .map(([k, v]) => [k, [...v].sort()]),
  );
}

export const queryKeys = {
  kpis: (f: Partial<GlobalFilters>) => ["kpis", clean(f)] as const,
  filters: ["filters"] as const,
  riskDistribution: (f: Partial<GlobalFilters>) => ["risk-distribution", clean(f)] as const,
  segments: (d: Dimension, f: Partial<GlobalFilters>) => ["segments", d, clean(f)] as const,
  drivers: (f: Partial<GlobalFilters>) => ["drivers", clean(f)] as const,
  assistantStatus: ["assistant-status"] as const,
  summary: ["summary"] as const,
  health: ["health"] as const,
};

export function useKpis(filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: queryKeys.kpis(filters),
    queryFn: ({ signal }) => apiGet("/api/kpis", { query: clean(filters), signal }),
    placeholderData: keepPreviousData,
  });
}

export function useFilterOptions() {
  return useQuery({
    queryKey: queryKeys.filters,
    queryFn: ({ signal }) => apiGet("/api/filters", { signal }),
    staleTime: Infinity,
  });
}

export function useRiskDistribution(filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: queryKeys.riskDistribution(filters),
    queryFn: ({ signal }) => apiGet("/api/risk/distribution", { query: clean(filters), signal }),
    placeholderData: keepPreviousData,
  });
}

export function useSegments(dimension: Dimension, filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: queryKeys.segments(dimension, filters),
    queryFn: ({ signal }) =>
      apiGet("/api/segments/{dimension}", {
        pathParams: { dimension },
        query: clean(filters),
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

export function useDrivers(filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: queryKeys.drivers(filters),
    queryFn: ({ signal }) => apiGet("/api/drivers", { query: clean(filters), signal }),
    placeholderData: keepPreviousData,
  });
}

export function useAssistantStatus() {
  return useQuery({
    queryKey: queryKeys.assistantStatus,
    queryFn: ({ signal }) => apiGet("/api/assistant/status", { signal }),
    staleTime: 60_000,
  });
}

export function useSummary() {
  return useQuery({
    queryKey: queryKeys.summary,
    queryFn: ({ signal }) => apiGet("/api/summary", { signal }),
  });
}
