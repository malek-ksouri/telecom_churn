/**
 * Alias lisibles des types générés depuis l'OpenAPI de FastAPI (`npm run gen:api`).
 * Ne pas modifier schema.d.ts à la main : le régénérer quand l'API change.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Kpis = Schemas["Kpis"];
export type LevelMetrics = Schemas["LevelMetrics"];
export type FilterOptions = Schemas["FilterOptions"];
export type FilterDimension = Schemas["FilterDimension"];
export type RiskDistribution = Schemas["RiskDistribution"];
export type Segments = Schemas["Segments"];
export type Heatmap = Schemas["Heatmap"];
export type Drivers = Schemas["Drivers"];
export type CampaignSimulation = Schemas["CampaignSimulation"];
export type CustomerPage = Schemas["CustomerPage"];
export type CustomerDetail = Schemas["CustomerDetail"];
export type CustomerExplanation = Schemas["CustomerExplanation"];
export type AssistantStatus = Schemas["AssistantStatus"];
export type ExecutiveSummary = Schemas["ExecutiveSummary"];
export type SegmentProfiles = Schemas["SegmentProfiles"];
export type SegmentProfile = Schemas["SegmentProfile"];
export type SegmentItem = Schemas["SegmentItem"];
export type HeatmapCell = Schemas["HeatmapCell"];
export type Driver = Schemas["Driver"];
export type CampaignPoint = Schemas["CampaignPoint"];
export type HistogramBin = Schemas["HistogramBin"];
export type Health = Schemas["Health"];

export type Dimension = FilterDimension["dimension"];
export type RiskLevel = LevelMetrics["risk_level"];

/**
 * Filtres globaux : les 7 dimensions de l'API (plusieurs valeurs d'une dimension = OU). Toute
 * modalité cliquée dans un graphique peut devenir un filtre (drill-down).
 */
export const GLOBAL_FILTER_KEYS = [
  "risk_level", "cluster", "area", "tenure_band", "handset_age_band", "usage_band", "action",
] as const;
export type GlobalFilterKey = (typeof GLOBAL_FILTER_KEYS)[number];
export type GlobalFilters = Record<GlobalFilterKey, string[]>;

/** Filtres proposés dans la barre d'en-tête (les autres apparaissent en puces après un drill-down). */
export const HEADER_FILTER_KEYS = ["risk_level", "cluster", "area", "tenure_band"] as const;
