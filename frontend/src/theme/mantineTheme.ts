import {
  type CSSVariablesResolver,
  type MantineColorsTuple,
  createTheme,
  rem,
} from "@mantine/core";

import {
  RISK_LEVELS,
  accent,
  motion,
  neutral,
  radius,
  risk,
  riskSoft,
  riskText,
  shadow,
  space,
  surfaces,
  typography,
} from "./tokens";

const px = (n: number) => rem(n);

/** Échelle « dark » de Mantine (du texte clair au fond le plus sombre), tirée des tokens. */
const darkScale: MantineColorsTuple = [
  surfaces.dark.text, surfaces.dark.textSecondary, surfaces.dark.textMuted, "#5f6a78",
  surfaces.dark.borderStrong, surfaces.dark.border, surfaces.dark.raised,
  surfaces.dark.surface, surfaces.dark.page, "#080b0f",
];

export const mantineTheme = createTheme({
  primaryColor: "accent",
  primaryShade: { light: 6, dark: 4 },
  colors: {
    accent: [...accent] as unknown as MantineColorsTuple,
    gray: [...neutral] as unknown as MantineColorsTuple,
    dark: darkScale,
  },
  white: "#ffffff",
  black: surfaces.light.text,
  fontFamily: typography.fontFamily,
  fontFamilyMonospace: typography.monoFamily,
  headings: {
    fontFamily: typography.fontFamily,
    fontWeight: String(typography.weight.semibold),
    sizes: {
      h1: { fontSize: px(typography.size.h1), lineHeight: "1.2" },
      h2: { fontSize: px(typography.size.h2), lineHeight: "1.25" },
      h3: { fontSize: px(typography.size.h3), lineHeight: "1.3" },
      h4: { fontSize: px(typography.size.lg), lineHeight: "1.35" },
    },
  },
  fontSizes: {
    xs: px(typography.size.xs), sm: px(typography.size.sm), md: px(typography.size.md),
    lg: px(typography.size.lg), xl: px(typography.size.xl),
  },
  spacing: {
    xs: px(space.xs), sm: px(12), md: px(space.sm), lg: px(space.md), xl: px(space.lg),
  },
  radius: { xs: px(4), sm: px(radius.sm), md: px(radius.md), lg: px(radius.lg), xl: px(20) },
  defaultRadius: "md",
  cursorType: "pointer",
  focusRing: "auto",
  respectReducedMotion: true,
  components: {
    Paper: { defaultProps: { radius: "lg" } },
    Card: { defaultProps: { radius: "lg", padding: "lg" } },
    Tooltip: {
      defaultProps: {
        withArrow: true, arrowSize: 6, openDelay: 200, multiline: true, maw: 320,
        transitionProps: { transition: "fade", duration: 120 },
      },
      styles: {
        tooltip: {
          fontSize: px(typography.size.sm), lineHeight: 1.45, padding: `${px(8)} ${px(12)}`,
          background: "var(--app-tooltip-bg)", color: "var(--app-text)",
          border: "1px solid var(--app-border)", boxShadow: "var(--app-shadow-floating)",
        },
        arrow: { background: "var(--app-tooltip-bg)", border: "1px solid var(--app-border)" },
      },
    },
    Badge: { defaultProps: { radius: "sm", variant: "light" } },
    Button: { defaultProps: { radius: "md" } },
    ActionIcon: { defaultProps: { radius: "md", variant: "subtle", color: "gray" } },
    MultiSelect: { defaultProps: { radius: "md", size: "xs", checkIconPosition: "right" } },
    Skeleton: { defaultProps: { radius: "md" } },
  },
  other: { motion },
});

/** Variables CSS de l'application, déclinées par thème (utilisées par tous les composants). */
export const cssVariablesResolver: CSSVariablesResolver = () => {
  const scheme = (s: "light" | "dark") => {
    const c = surfaces[s];
    const vars: Record<string, string> = {
      "--mantine-color-body": c.page,
      "--mantine-color-text": c.text,
      "--mantine-color-dimmed": c.textMuted,
      "--mantine-color-default-border": c.border,
      "--app-page": c.page,
      "--app-surface": c.surface,
      "--app-raised": c.raised,
      "--app-glass": c.glass,
      "--app-glass-border": c.glassBorder,
      "--app-border": c.border,
      "--app-border-strong": c.borderStrong,
      "--app-text": c.text,
      "--app-text-secondary": c.textSecondary,
      "--app-text-muted": c.textMuted,
      "--app-accent": c.accent,
      "--app-accent-text": c.accentText,
      "--app-tooltip-bg": c.tooltipBg,
      "--app-success": c.success,
      "--app-danger": c.danger,
      "--app-shadow-card": shadow[s].card,
      "--app-shadow-floating": shadow[s].floating,
      "--app-focus": shadow[s].focus,
    };
    for (const level of RISK_LEVELS) {
      const key = level.toLowerCase();
      vars[`--risk-${key}`] = risk[s][level];
      vars[`--risk-${key}-text`] = riskText[s][level];
      vars[`--risk-${key}-soft`] = riskSoft[s][level];
    }
    return vars;
  };
  return {
    variables: {
      "--app-radius-card": px(radius.lg),
      "--app-ease": motion.css.standard,
      "--app-transition-fast": motion.css.fast,
      "--app-transition-base": motion.css.base,
    },
    light: scheme("light"),
    dark: scheme("dark"),
  };
};
