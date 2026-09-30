/**
 * Tokens du design system : source unique des couleurs, typographie, espacements, rayons,
 * ombres et mouvements. Mantine, ECharts et AG Grid sont construits sur ces valeurs.
 *
 * Couleurs de risque (High, Medium, Low, Inactif) : validées par le contrôle de palette du
 * skill dataviz (daltonisme deutan / protan / tritan, écart en vision normale, bande de
 * luminosité, contraste) pour les deux thèmes, toutes paires comparées :
 *   clair  #e34948 #eda100 #2a78d6 #4a3aa7 — tous les contrôles passent ;
 *   sombre #e0474f #bb8700 #2b9fc9 #9d5bd9 — passent ; écart daltonien bleu/violet 6,2
 *   (bande 6-8) : autorisé UNIQUEMENT avec un codage secondaire.
 * Règle qui en découle : une couleur de risque n'est jamais seule, toujours accompagnée de
 * son libellé (badge, légende, étiquette). L'ambre clair (#eda100) a un contraste < 3:1 :
 * jamais utilisé comme couleur de texte (voir riskText).
 *
 * L'accent (vert canard) est volontairement distinct des quatre couleurs de risque.
 */

export type ColorScheme = "light" | "dark";
export type RiskLevel = "High" | "Medium" | "Low" | "Inactif";

export const RISK_LEVELS: readonly RiskLevel[] = ["High", "Medium", "Low", "Inactif"];

/** Couleur de marque (graphiques, barres, aplats). */
export const risk: Record<ColorScheme, Record<RiskLevel, string>> = {
  light: { High: "#e34948", Medium: "#eda100", Low: "#2a78d6", Inactif: "#4a3aa7" },
  dark: { High: "#e0474f", Medium: "#bb8700", Low: "#2b9fc9", Inactif: "#9d5bd9" },
};

/** Couleur de texte lisible (>= 4,5:1) pour un libellé coloré par niveau. */
export const riskText: Record<ColorScheme, Record<RiskLevel, string>> = {
  light: { High: "#b42828", Medium: "#8a5a00", Low: "#1d5fae", Inactif: "#4a3aa7" },
  dark: { High: "#ff8a8a", Medium: "#f0c04d", Low: "#6cc4ec", Inactif: "#c7a4f0" },
};

/** Fond discret d'un badge de niveau. */
export const riskSoft: Record<ColorScheme, Record<RiskLevel, string>> = {
  light: { High: "#fdecec", Medium: "#fdf3dc", Low: "#e8f1fc", Inactif: "#eeebf8" },
  dark: { High: "#3a1c1f", Medium: "#33290f", Low: "#10283a", Inactif: "#2a1f3a" },
};

export const riskLabel: Record<RiskLevel, string> = {
  High: "Risque élevé",
  Medium: "Risque moyen",
  Low: "Risque faible",
  Inactif: "Inactif",
};

/** Accent principal : 10 nuances (format Mantine), index 6 = teinte de référence. */
export const accent = [
  "#e6f6f4", "#c6ebe6", "#98dbd2", "#63c7bb", "#35b2a4",
  "#179a8c", "#0e7c72", "#0b665e", "#09524c", "#063d39",
] as const;

/** Neutres (ardoise) : 10 nuances, du plus clair au plus sombre. */
export const neutral = [
  "#f7f8fa", "#eef0f3", "#e1e5ea", "#cbd2da", "#a3adb9",
  "#7a8594", "#586271", "#3d4653", "#262d37", "#161b22",
] as const;

export interface Surfaces {
  /** Fond de page. */
  page: string;
  /** Cartes, tables, zones de graphique (toujours opaques). */
  surface: string;
  /** Surface en relief (survol, en-têtes de table). */
  raised: string;
  /** Surfaces flottantes vitrées (en-tête, tiroirs, chat, modales). */
  glass: string;
  glassBorder: string;
  border: string;
  borderStrong: string;
  text: string;
  textSecondary: string;
  textMuted: string;
  grid: string;
  axis: string;
  accent: string;
  accentText: string;
  tooltipBg: string;
  success: string;
  danger: string;
}

export const surfaces: Record<ColorScheme, Surfaces> = {
  light: {
    page: "#f5f6f8",
    surface: "#ffffff",
    raised: "#f7f8fa",
    glass: "rgba(255, 255, 255, 0.72)",
    glassBorder: "rgba(22, 27, 34, 0.08)",
    border: "#e4e7ec",
    borderStrong: "#cbd2da",
    text: "#141a21",
    textSecondary: "#4b5563",
    textMuted: "#6b7480",
    grid: "#eceef2",
    axis: "#cbd2da",
    accent: "#0e7c72",
    accentText: "#0b665e",
    tooltipBg: "#ffffff",
    success: "#1f7a3a",
    danger: "#b42828",
  },
  dark: {
    page: "#0d1117",
    surface: "#151a21",
    raised: "#1b2129",
    glass: "rgba(21, 26, 33, 0.72)",
    glassBorder: "rgba(255, 255, 255, 0.08)",
    border: "#262d37",
    borderStrong: "#3d4653",
    text: "#e8ecf1",
    textSecondary: "#b3bcc7",
    textMuted: "#8b95a3",
    grid: "#222932",
    axis: "#3d4653",
    accent: "#35b2a4",
    accentText: "#63c7bb",
    tooltipBg: "#1b2129",
    success: "#4cc47a",
    danger: "#ff8a8a",
  },
};

export const typography = {
  fontFamily:
    "'Inter Variable', Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  monoFamily: "'JetBrains Mono', ui-monospace, 'Cascadia Code', Consolas, monospace",
  /** Tailles en px. */
  size: { xs: 12, sm: 13, md: 14, lg: 16, xl: 20, h3: 18, h2: 22, h1: 28, kpi: 30 },
  weight: { regular: 400, medium: 500, semibold: 600, bold: 700 },
  lineHeight: { tight: 1.2, base: 1.5 },
  /** Chiffres alignés (KPI, tables). */
  tabular: "tabular-nums",
} as const;

/** Espacements : multiples de 8 px (4 px réservé aux ajustements fins dans un composant). */
export const space = { xxs: 4, xs: 8, sm: 16, md: 24, lg: 32, xl: 48 } as const;

export const radius = { sm: 6, md: 10, lg: 14, pill: 999 } as const;

export const shadow: Record<ColorScheme, { card: string; floating: string; focus: string }> = {
  light: {
    card: "0 1px 2px rgba(20, 26, 33, 0.04), 0 1px 3px rgba(20, 26, 33, 0.06)",
    floating: "0 8px 24px rgba(20, 26, 33, 0.10), 0 2px 6px rgba(20, 26, 33, 0.06)",
    focus: "0 0 0 3px rgba(14, 124, 114, 0.28)",
  },
  dark: {
    card: "0 1px 2px rgba(0, 0, 0, 0.30)",
    floating: "0 12px 32px rgba(0, 0, 0, 0.45), 0 2px 6px rgba(0, 0, 0, 0.30)",
    focus: "0 0 0 3px rgba(53, 178, 164, 0.35)",
  },
};

/**
 * Mouvement : chaque animation a un rôle (orientation, retour d'action, continuité) et dure
 * moins de 400 ms, sauf les compteurs de KPI (< 900 ms). Désactivées si
 * prefers-reduced-motion.
 */
export const motion = {
  duration: { instant: 0.08, fast: 0.14, base: 0.2, slow: 0.32, counter: 0.8 },
  /** Courbes (cubic-bezier) : standard pour l'essentiel, entrée pour ce qui apparaît. */
  ease: {
    standard: [0.2, 0, 0, 1] as [number, number, number, number],
    enter: [0, 0, 0, 1] as [number, number, number, number],
    exit: [0.3, 0, 1, 1] as [number, number, number, number],
  },
  css: {
    standard: "cubic-bezier(0.2, 0, 0, 1)",
    fast: "140ms cubic-bezier(0.2, 0, 0, 1)",
    base: "200ms cubic-bezier(0.2, 0, 0, 1)",
  },
} as const;

export const layout = {
  navbarWidth: 248,
  navbarCollapsed: 72,
  headerHeight: 64,
  contentMaxWidth: 1480,
} as const;
