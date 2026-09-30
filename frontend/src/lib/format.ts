/** Formats français (espace fine pour les milliers, virgule décimale). */

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
  return formatter({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

/** Montant en dollars (devise du jeu de données). */
export function formatMoney(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value, digits)} $`;
}

/** Proportion 0-1 -> « 12,3 % ». */
export function formatShare(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(100 * value, digits)} %`;
}

/** Valeur déjà en % -> « 12,3 % ». */
export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value, digits)} %`;
}

/** Forme compacte pour les axes : 12 k, 1,2 M. */
export function formatCompact(value: number): string {
  return formatter({ notation: "compact", maximumFractionDigits: 1 }).format(value);
}
