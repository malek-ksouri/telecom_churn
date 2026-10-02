/**
 * Formats français : espace insécable pour les milliers et avant % et $, virgule décimale.
 * Espace insécable normale (U+00A0) plutôt que l'espace fine (U+202F) d'Intl : dans Inter,
 * l'espace fine devient presque invisible dans les titres (« 116162$ »).
 */

const NBSP = "\u00a0"; // espace insécable

const cache = new Map<string, Intl.NumberFormat>();

function formatter(options: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = JSON.stringify(options);
  let f = cache.get(key);
  if (!f) {
    f = new Intl.NumberFormat("fr-FR", options);
    cache.set(key, f);
  }
  return f;
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return formatter({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value).replace(/\u202f/g, NBSP);
}

/** Montant en dollars (devise du jeu de données). */
export function formatMoney(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value, digits)}${NBSP}$`;
}

/** Proportion 0-1 -> « 12,3 % ». */
export function formatShare(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(100 * value, digits)}${NBSP}%`;
}

/** Valeur déjà en % -> « 12,3 % ». */
export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value, digits)}${NBSP}%`;
}

/** Forme compacte pour les axes : 12 k, 1,2 M. */
export function formatCompact(value: number): string {
  return formatter({ notation: "compact", maximumFractionDigits: 1 }).format(value);
}
