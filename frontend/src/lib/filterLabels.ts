import type { GlobalFilterKey } from "../api/types";

export const FILTER_LABELS: Record<GlobalFilterKey, string> = {
  risk_level: "Niveau",
  cluster: "Segment",
  area: "Région",
  tenure_band: "Ancienneté",
  handset_age_band: "Âge du terminal",
  usage_band: "Usage",
  action: "Action",
};

/** Présentation d'une valeur de filtre (régions en casse lisible). */
export function filterValueLabel(key: GlobalFilterKey, value: string): string {
  if (key === "area") {
    return value
      .toLowerCase()
      .replace(/\barea\b/, "")
      .replace(/\b\w/g, (c) => c.toUpperCase())
      .trim();
  }
  return value;
}
