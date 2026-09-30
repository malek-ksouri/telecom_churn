import { type Theme, colorSchemeDark, colorSchemeLight, themeQuartz } from "ag-grid-community";

import { type ColorScheme, radius, surfaces, typography } from "./tokens";

/** Thème Quartz d'AG Grid paramétré sur les tokens : table dense, lignes fines, chiffres alignés. */
function build(scheme: ColorScheme): Theme {
  const c = surfaces[scheme];
  return themeQuartz
    .withPart(scheme === "light" ? colorSchemeLight : colorSchemeDark)
    .withParams({
      fontFamily: typography.fontFamily,
      fontSize: typography.size.sm,
      headerFontSize: typography.size.xs,
      headerFontWeight: typography.weight.semibold,
      backgroundColor: c.surface,
      foregroundColor: c.text,
      headerBackgroundColor: c.raised,
      headerTextColor: c.textMuted,
      borderColor: c.border,
      rowBorder: { color: c.grid },
      columnBorder: false,
      oddRowBackgroundColor: c.surface,
      rowHoverColor: scheme === "light" ? "#f2f7f6" : "#1c2a2c",
      selectedRowBackgroundColor: scheme === "light" ? "#e6f6f4" : "#153230",
      accentColor: c.accent,
      wrapperBorderRadius: radius.lg,
      borderRadius: radius.sm,
      rowHeight: 40,
      headerHeight: 40,
      spacing: 6,
      cellHorizontalPadding: 12,
    });
}

export const agGridThemes: Record<ColorScheme, Theme> = {
  light: build("light"),
  dark: build("dark"),
};
