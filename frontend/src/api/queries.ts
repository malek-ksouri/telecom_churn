/**
 * Hooks TanStack Query, un par endpoint. Les clés de cache incluent les filtres : changer un
 * filtre relance la requête, revenir à un filtre déjà vu est instantané (cache).
 */
import { QueryClient, keepPreviousData, useQuery } from "@tanstack/react-query";

import { ApiError, apiGet, toSearchParams } from "./client";
import type { Dimension, GlobalFilterKey, GlobalFilters } from "./types";

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
  heatmap: (x: Dimension, y: Dimension, f: Partial<GlobalFilters>) =>
    ["heatmap", x, y, clean(f)] as const,
  profiles: (f: Partial<GlobalFilters>) => ["segment-profiles", clean(f)] as const,
  campaign: (p: CampaignParams, f: Partial<GlobalFilters>) => ["campaign", p, clean(f)] as const,
};

/**
 * Filtres sans certaines dimensions : un graphique qui affiche une dimension ignore le filtre
 * posé sur cette même dimension, pour garder toutes ses modalités visibles (celles
 * sélectionnées sont mises en évidence) au lieu de se réduire à une seule barre.
 */
export function withoutKeys(filters: GlobalFilters, keys: readonly GlobalFilterKey[]): Partial<GlobalFilters> {
  const out: Partial<GlobalFilters> = { ...filters };
  for (const k of keys) out[k] = [];
  return out;
}

export interface CampaignParams {
  capacity_pct: number;
  /** Taux de succès supposé (0-1). */
  success_rate: number;
  /** Coût par contact supposé ($) ; null = pas de coût. */
  offer_cost: number | null;
  revenue_horizon_months: number;
}

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

export function useHeatmap(x: Dimension, y: Dimension, filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: queryKeys.heatmap(x, y, filters),
    queryFn: ({ signal }) => apiGet("/api/segments/heatmap", { query: { ...clean(filters), x, y }, signal }),
    placeholderData: keepPreviousData,
  });
}

export function useSegmentProfiles(filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: queryKeys.profiles(filters),
    queryFn: ({ signal }) => apiGet("/api/segments/profiles", { query: clean(filters), signal }),
    placeholderData: keepPreviousData,
  });
}

export function useCampaign(params: CampaignParams, filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: queryKeys.campaign(params, filters),
    queryFn: ({ signal }) =>
      apiGet("/api/campaign/simulate", {
        query: {
          ...clean(filters),
          capacity_pct: params.capacity_pct,
          success_rate: params.success_rate,
          offer_cost: params.offer_cost,
          revenue_horizon_months: params.revenue_horizon_months,
        },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

export type CustomerSort = "p_real" | "revenue_at_risk_monthly" | "monthly_bill" | "tenure_months" | "handset_age_days" | "customer_id";

export interface CustomerListParams {
  page: number;
  size: number;
  sort: CustomerSort;
  order: "asc" | "desc";
  search: string;
}

export function useCustomers(params: CustomerListParams, filters: Partial<GlobalFilters>) {
  return useQuery({
    queryKey: ["customers", params, clean(filters)] as const,
    queryFn: ({ signal }) =>
      apiGet("/api/customers", {
        query: { ...clean(filters), ...params, search: params.search || undefined },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

export function useCustomer(id: number | null) {
  return useQuery({
    queryKey: ["customer", id] as const,
    queryFn: ({ signal }) => apiGet("/api/customers/{customer_id}", { pathParams: { customer_id: id ?? 0 }, signal }),
    enabled: id !== null,
  });
}

export function useCustomerExplanation(id: number | null, top = 10) {
  return useQuery({
    queryKey: ["customer-explanation", id, top] as const,
    queryFn: ({ signal }) =>
      apiGet("/api/customers/{customer_id}/explanation", {
        pathParams: { customer_id: id ?? 0 },
        query: { top },
        signal,
      }),
    enabled: id !== null,
  });
}

/** URL de l'export CSV (mêmes filtres, recherche et tri que la liste affichée). */
export function customersExportUrl(params: Omit<CustomerListParams, "page" | "size">, filters: Partial<GlobalFilters>): string {
  const search = toSearchParams({ ...clean(filters), sort: params.sort, order: params.order, search: params.search || undefined });
  const q = search.toString();
  return q ? `/api/customers/export?${q}` : "/api/customers/export";
}
