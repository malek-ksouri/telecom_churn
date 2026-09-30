import * as echarts from "echarts/core";

import { type ColorScheme, RISK_LEVELS, radius, risk, surfaces, typography } from "./tokens";

/**
 * Thèmes ECharts clair et sombre, construits sur les mêmes tokens que l'interface :
 * police Inter, texte en encre neutre (jamais la couleur d'une série), grilles fines et
 * discrètes, infobulle au style des surfaces flottantes.
 */
export const ECHARTS_THEME: Record<ColorScheme, string> = {
  light: "churn-light",
  dark: "churn-dark",
};

function build(scheme: ColorScheme): object {
  const c = surfaces[scheme];
  const axis = {
    axisLine: { show: true, lineStyle: { color: c.axis, width: 1 } },
    axisTick: { show: false },
    axisLabel: { color: c.textMuted, fontSize: typography.size.xs, margin: 10 },
    splitLine: { show: true, lineStyle: { color: c.grid, width: 1 } },
    splitArea: { show: false },
    nameTextStyle: { color: c.textMuted, fontSize: typography.size.xs },
  };
  return {
    // Palette catégorielle par défaut : les niveaux de risque, dans l'ordre fixe.
    color: RISK_LEVELS.map((level) => risk[scheme][level]),
    backgroundColor: "transparent",
    textStyle: { fontFamily: typography.fontFamily, color: c.textSecondary },
    title: {
      textStyle: { color: c.text, fontWeight: 600, fontSize: typography.size.lg },
      subtextStyle: { color: c.textMuted, fontSize: typography.size.sm },
    },
    legend: {
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 16,
      textStyle: { color: c.textSecondary, fontSize: typography.size.sm },
    },
    grid: { left: 8, right: 16, top: 32, bottom: 8, containLabel: true },
    categoryAxis: { ...axis, splitLine: { show: false } },
    valueAxis: { ...axis, axisLine: { show: false } },
    logAxis: axis,
    timeAxis: axis,
    tooltip: {
      backgroundColor: c.tooltipBg,
      borderColor: c.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: c.text, fontSize: typography.size.sm },
      extraCssText: `border-radius:${radius.md}px;box-shadow:${
        scheme === "light"
          ? "0 8px 24px rgba(20,26,33,.10)"
          : "0 12px 32px rgba(0,0,0,.45)"
      };`,
      axisPointer: {
        lineStyle: { color: c.borderStrong, width: 1 },
        crossStyle: { color: c.borderStrong },
        shadowStyle: { color: scheme === "light" ? "rgba(20,26,33,0.04)" : "rgba(255,255,255,0.04)" },
      },
    },
    bar: { itemStyle: { borderRadius: [4, 4, 0, 0] }, barMaxWidth: 36 },
    line: { symbolSize: 6, lineStyle: { width: 2 }, smooth: false },
  };
}

let registered = false;

/** Enregistre les deux thèmes (une seule fois). */
export function registerEchartsThemes(): void {
  if (registered) return;
  echarts.registerTheme(ECHARTS_THEME.light, build("light"));
  echarts.registerTheme(ECHARTS_THEME.dark, build("dark"));
  registered = true;
}
