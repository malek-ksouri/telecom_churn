/**
 * Options ECharts des pages Pilotage : fonctions pures (données + thème -> option).
 *
 * Règles (skill dataviz) : une seule teinte pour une grandeur (accent), rampe séquentielle à
 * une teinte pour la heatmap, couleurs de risque réservées aux niveaux et toujours
 * accompagnées d'une légende ou d'une étiquette, texte en encre neutre, grilles discrètes,
 * étiquettes directes sélectives, jamais de double axe.
 */
import type { EChartsOption } from "echarts";

import type {
  CampaignPoint, Driver, HeatmapCell, HistogramBin, SegmentItem,
} from "../api/types";
import { formatMoney, formatNumber, formatPct, formatShare } from "../lib/format";
import { type ColorScheme, RISK_LEVELS, risk, surfaces } from "../theme/tokens";

const tooltipBox = (title: string, lines: [string, string][]): string =>
  `<div style="min-width:180px"><div style="font-weight:600;margin-bottom:6px">${title}</div>${lines
    .map(
      ([k, v]) =>
        `<div style="display:flex;justify-content:space-between;gap:16px"><span style="opacity:.72">${k}</span><b style="font-variant-numeric:tabular-nums">${v}</b></div>`,
    )
    .join("")}</div>`;

// --- Distribution des probabilités -------------------------------------------------------------

export function histogramOption(
  bins: HistogramBin[],
  thresholds: { high: number; medium: number },
  scheme: ColorScheme,
): EChartsOption {
  // On coupe la longue traîne vide (au-delà de la dernière classe non vide), sauf la dernière.
  let last = bins.length - 1;
  while (last > 0 && (bins[last]?.n_rows ?? 0) === 0) last -= 1;
  const shown = bins.slice(0, Math.max(last + 1, 2));
  const labels = shown.map((b) =>
    b.p_real_max_pct === null ? `≥ ${formatNumber(b.p_real_min_pct, 1)}` : formatNumber(b.p_real_min_pct, 1),
  );
  const indexOf = (pct: number) =>
    Math.max(0, shown.findIndex((b) => b.p_real_max_pct === null || pct < b.p_real_max_pct));
  const c = surfaces[scheme];
  const line = (pct: number, name: string, distance: number) => ({
    xAxis: indexOf(pct),
    label: {
      formatter: `${name} ≥ ${formatPct(pct, 1)}`,
      color: c.textSecondary,
      fontSize: 11,
      fontWeight: 600,
      position: "end" as const,
      distance,
    },
    lineStyle: { color: c.textSecondary, type: "dashed" as const, width: 1 },
  });
  return {
    grid: { left: 4, right: 12, top: 60, bottom: 28, containLabel: true },
    legend: { top: 0, right: 0 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const list = params as { dataIndex: number; seriesName: string; value: number }[];
        const bin = shown[list[0]?.dataIndex ?? 0];
        if (!bin) return "";
        const range =
          bin.p_real_max_pct === null
            ? `${formatPct(bin.p_real_min_pct, 1)} et plus`
            : `${formatPct(bin.p_real_min_pct, 1)} à ${formatPct(bin.p_real_max_pct, 1)}`;
        return tooltipBox(`Risque mensuel ${range}`, [
          ...list.filter((p) => p.value > 0.5).map((p): [string, string] => [p.seriesName, formatNumber(p.value)]),
          ["Clients dans la base", formatNumber(bin.n_rows)],
        ]);
      },
    },
    xAxis: {
      type: "category",
      data: labels,
      name: "risque mensuel (%)",
      nameLocation: "middle",
      nameGap: 26,
      axisLabel: { interval: 3 },
    },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => formatNumber(v) } },
    series: RISK_LEVELS.map((level, i) => ({
      name: level,
      type: "bar",
      stack: "risk",
      barCategoryGap: "12%",
      itemStyle: { color: risk[scheme][level], borderRadius: 0 },
      emphasis: { focus: "series" },
      data: shown.map((b) => b.n_portfolio_equiv_by_risk_level[level] ?? 0),
      ...(i === 0
        ? {
            markLine: {
              symbol: "none",
              silent: true,
              data: [line(thresholds.high, "High", 4), line(thresholds.medium, "Medium", 20)],
            },
          }
        : {}),
    })),
  };
}

// --- Segments (drill-down) ---------------------------------------------------------------------

export function segmentBarOption(
  items: SegmentItem[],
  selected: string[],
  overallRate: number | null,
  labelOf: (v: string) => string,
  scheme: ColorScheme,
): EChartsOption {
  const c = surfaces[scheme];
  const anySelected = selected.length > 0;
  return {
    grid: { left: 4, right: 56, top: 26, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const item = items[(p as { dataIndex: number }).dataIndex];
        if (!item) return "";
        return tooltipBox(labelOf(item.value), [
          ["Risque mensuel moyen", formatShare(item.expected_churn_rate, 2)],
          ["Churn observé (base)", formatShare(item.observed_churn_rate_in_base, 1)],
          ["Clients dans la base", formatNumber(item.n_rows)],
          ["Estimation portefeuille", formatNumber(item.n_portfolio_equiv)],
          ["Revenu en jeu / mois", formatMoney(item.revenue_at_risk)],
        ]) + `<div style="margin-top:6px;opacity:.6;font-size:11px">Clic : ajouter aux filtres</div>`;
      },
    },
    xAxis: { type: "value", axisLabel: { formatter: (v: number) => `${formatNumber(v, 1)} %` } },
    yAxis: {
      type: "category",
      inverse: true,
      data: items.map((i) => labelOf(i.value)),
      axisLabel: { width: 190, overflow: "truncate" },
      axisLine: { show: false },
    },
    series: [
      {
        type: "bar",
        barWidth: "62%",
        cursor: "pointer",
        data: items.map((i) => ({
          value: 100 * (i.expected_churn_rate ?? 0),
          itemStyle: {
            color: c.accent,
            opacity: anySelected && !selected.includes(i.value) ? 0.3 : 1,
            borderRadius: [0, 4, 4, 0],
          },
        })),
        label: {
          show: true,
          position: "right",
          color: c.textSecondary,
          fontSize: 12,
          formatter: (p: unknown) => `${formatNumber((p as { value: number }).value, 2)} %`,
        },
        emphasis: { itemStyle: { opacity: 1 } },
        ...(overallRate !== null
          ? {
              markLine: {
                symbol: "none",
                silent: true,
                data: [{ xAxis: 100 * overallRate }],
                lineStyle: { color: c.textMuted, type: "dashed", width: 1 },
                label: {
                  formatter: `moyenne ${formatPct(100 * overallRate, 2)}`,
                  color: c.textMuted,
                  fontSize: 11,
                  position: "start",
                  distance: 6,
                },
              },
            }
          : {}),
      },
    ],
  };
}

// --- Heatmap ------------------------------------------------------------------------------------

/** Texte lisible sur une case : sombre sur les teintes claires, clair sur les teintes soutenues. */
function heatLabelColor(rate: number | null, min: number, max: number, scheme: ColorScheme): string {
  if (rate === null) return surfaces[scheme].textMuted;
  const t = max > min ? (100 * rate - min) / (max - min) : 0;
  if (scheme === "light") return t > 0.62 ? "#ffffff" : "#3b1111";
  return t > 0.62 ? "#2a0d0f" : "#f3d6d6";
}

/** Rampe séquentielle à une teinte (rouge) : clair = faible risque, soutenu = fort risque. */
const HEAT_RAMP: Record<ColorScheme, string[]> = {
  light: ["#fdf1f0", "#f8cfcb", "#ef9a93", "#e0605a", "#b42828"],
  dark: ["#2a1b1d", "#4f2328", "#7d2c33", "#b8434a", "#ff8a8a"],
};

export function heatmapOption(
  cells: HeatmapCell[],
  xValues: string[],
  yValues: string[],
  selected: { x: string[]; y: string[] },
  xLabel: (v: string) => string,
  yLabel: (v: string) => string,
  scheme: ColorScheme,
): EChartsOption {
  const c = surfaces[scheme];
  const rates = cells.map((cell) => cell.expected_churn_rate).filter((r): r is number => r !== null);
  const min = rates.length ? Math.min(...rates) * 100 : 0;
  const max = rates.length ? Math.max(...rates) * 100 : 1;
  const anySel = selected.x.length > 0 || selected.y.length > 0;
  const isSel = (cell: HeatmapCell) =>
    (!selected.x.length || selected.x.includes(cell.x)) && (!selected.y.length || selected.y.includes(cell.y));
  return {
    grid: { left: 4, right: 12, top: 8, bottom: 56, containLabel: true },
    tooltip: {
      formatter: (p: unknown) => {
        const cell = (p as { data: { cell: HeatmapCell } }).data.cell;
        return tooltipBox(`${yLabel(cell.y)} · ${xLabel(cell.x)}`, [
          ["Risque mensuel moyen", cell.low_sample ? "trop peu de clients" : formatShare(cell.expected_churn_rate, 2)],
          ["Churn observé (base)", cell.low_sample ? "—" : formatShare(cell.observed_churn_rate_in_base, 1)],
          ["Clients dans la base", formatNumber(cell.n_rows)],
          ["Revenu en jeu / mois", formatMoney(cell.revenue_at_risk)],
        ]) + `<div style="margin-top:6px;opacity:.6;font-size:11px">Clic : filtrer sur cette case</div>`;
      },
    },
    xAxis: {
      type: "category",
      data: xValues.map(xLabel),
      splitArea: { show: false },
      axisLabel: { interval: 0, width: 96, overflow: "break", fontSize: 11 },
    },
    yAxis: { type: "category", data: yValues.map(yLabel), inverse: true, axisLine: { show: false } },
    visualMap: {
      min,
      max,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      itemWidth: 12,
      itemHeight: 160,
      text: [`${formatNumber(max, 1)} %`, `${formatNumber(min, 1)} %`],
      textStyle: { color: c.textMuted, fontSize: 11 },
      inRange: { color: HEAT_RAMP[scheme] },
      dimension: 2,
    },
    series: [
      {
        type: "heatmap",
        cursor: "pointer",
        data: cells.map((cell) => ({
          value: [
            xValues.indexOf(cell.x),
            yValues.indexOf(cell.y),
            cell.expected_churn_rate === null ? "-" : 100 * cell.expected_churn_rate,
          ],
          cell,
          label: { color: heatLabelColor(cell.expected_churn_rate, min, max, scheme) },
          itemStyle: {
            borderColor: c.surface,
            borderWidth: 2,
            borderRadius: 4,
            opacity: anySel && !isSel(cell) ? 0.35 : 1,
            ...(cell.expected_churn_rate === null ? { color: c.raised } : {}),
          },
        })),
        label: {
          show: true,
          fontSize: 11,
          formatter: (p: unknown) => {
            const v = (p as { value: [number, number, number | string] }).value[2];
            return typeof v === "number" ? formatNumber(v, 1) : "";
          },
          color: c.text,
        },
        emphasis: { itemStyle: { borderColor: c.text, borderWidth: 2 } },
      },
    ],
  };
}

// --- Facteurs (SHAP) ------------------------------------------------------------------------

export function driversOption(drivers: Driver[], color: string, scheme: ColorScheme): EChartsOption {
  const c = surfaces[scheme];
  return {
    grid: { left: 4, right: 48, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const d = drivers[(p as { dataIndex: number }).dataIndex];
        if (!d) return "";
        return tooltipBox(d.label, [
          ["Famille", d.family_label],
          ["Part de l'importance", formatPct(d.share_pct, 1)],
          ["Augmente le risque pour", formatShare(d.share_rows_increasing, 0)],
        ]) + `<div style="margin-top:6px;opacity:.6;font-size:11px">Selon le modèle : association, pas cause</div>`;
      },
    },
    xAxis: { type: "value", show: false },
    yAxis: {
      type: "category",
      inverse: true,
      data: drivers.map((d) => d.label),
      axisLine: { show: false },
      axisLabel: { width: 170, overflow: "truncate", color: c.textSecondary },
    },
    series: [
      {
        type: "bar",
        barWidth: "58%",
        itemStyle: { color, borderRadius: [0, 4, 4, 0] },
        label: {
          show: true,
          position: "right",
          color: c.textSecondary,
          fontSize: 12,
          formatter: (p: unknown) => formatPct((p as { value: number }).value, 1),
        },
        data: drivers.map((d) => d.share_pct),
      },
    ],
  };
}

// --- Simulateur ----------------------------------------------------------------------------------

/** Graduations lisibles de l'axe des capacités : 1, 10, 20, 30, 40, 50. */
const capacityTick = (_: number, value: string) => ["1", "10", "20", "30", "40", "50"].includes(value);

export function gainOption(curve: CampaignPoint[], capacity: number, scheme: ColorScheme): EChartsOption {
  const c = surfaces[scheme];
  const idx = curve.findIndex((p) => Math.abs(p.capacity_pct - capacity) < 1e-6);
  const current = idx >= 0 ? curve[idx] : undefined;
  return {
    grid: { left: 4, right: 16, top: 44, bottom: 28, containLabel: true },
    legend: { top: 0, left: 0, data: ["Ciblage par le modèle", "Ciblage au hasard"] },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const list = params as { dataIndex: number }[];
        const p = curve[list[0]?.dataIndex ?? 0];
        if (!p) return "";
        return tooltipBox(`Capacité ${formatPct(p.capacity_pct, 0)}`, [
          ["Churners atteints", formatNumber(p.expected_churners)],
          ["Au hasard", formatNumber(p.random_churners)],
          ["Facteur", `× ${formatNumber(p.lift_vs_random, 2)}`],
          ["Clients ciblés (portefeuille)", formatNumber(p.targeted_n_portfolio_equiv)],
        ]);
      },
    },
    xAxis: {
      type: "category",
      data: curve.map((p) => String(p.capacity_pct)),
      name: "capacité (% du périmètre contacté)",
      nameLocation: "middle",
      nameGap: 26,
      boundaryGap: false,
      axisLabel: { interval: capacityTick, formatter: (v: string) => `${v} %` },
    },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => formatNumber(v) } },
    series: [
      {
        name: "Ciblage par le modèle",
        type: "line",
        showSymbol: false,
        lineStyle: { color: c.accent, width: 2.5 },
        itemStyle: { color: c.accent },
        areaStyle: { color: c.accent, opacity: 0.08 },
        data: curve.map((p) => p.expected_churners),
        markLine: current
          ? {
              symbol: "none",
              silent: true,
              lineStyle: { color: c.borderStrong, type: "dashed", width: 1 },
              label: { show: false },
              data: [{ xAxis: idx }],
            }
          : undefined,
      },
      {
        name: "Ciblage au hasard",
        type: "line",
        showSymbol: false,
        lineStyle: { color: c.textMuted, width: 1.5, type: "dashed" },
        itemStyle: { color: c.textMuted },
        data: curve.map((p) => p.random_churners),
      },
      {
        // Point de la capacité choisie (série à part : toujours visible, étiquette directe).
        name: "Capacité choisie",
        type: "scatter",
        symbolSize: 12,
        z: 5,
        itemStyle: { color: c.accent, borderColor: c.surface, borderWidth: 2 },
        label: {
          show: true,
          position: "top",
          distance: 8,
          color: c.text,
          fontWeight: 600,
          formatter: current ? `${formatNumber(current.expected_churners)} churners` : "",
        },
        tooltip: { show: false },
        data: current ? [[idx, current.expected_churners]] : [],
      },
    ],
  };
}

export function balanceOption(curve: CampaignPoint[], capacity: number, scheme: ColorScheme): EChartsOption {
  const c = surfaces[scheme];
  const idx = curve.findIndex((p) => Math.abs(p.capacity_pct - capacity) < 1e-6);
  return {
    grid: { left: 4, right: 16, top: 24, bottom: 28, containLabel: true },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const p = curve[(params as { dataIndex: number }[])[0]?.dataIndex ?? 0];
        if (!p) return "";
        return tooltipBox(`Capacité ${formatPct(p.capacity_pct, 0)}`, [
          ["Revenu préservé (hyp.)", formatMoney(p.preserved_revenue_horizon_hypothesis)],
          ["Coût (hyp.)", formatMoney(p.campaign_cost)],
          ["Solde (hyp.)", formatMoney(p.net_balance)],
        ]);
      },
    },
    xAxis: {
      type: "category",
      data: curve.map((p) => String(p.capacity_pct)),
      boundaryGap: false,
      name: "capacité (% du périmètre contacté)",
      nameLocation: "middle",
      nameGap: 26,
      axisLabel: { interval: capacityTick, formatter: (v: string) => `${v} %` },
    },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => formatMoney(v) } },
    series: [
      {
        name: "Solde",
        type: "line",
        showSymbol: false,
        lineStyle: { color: c.accent, width: 2.5 },
        data: curve.map((p) => p.net_balance ?? 0),
        markLine: {
          symbol: "none",
          silent: true,
          label: { show: false },
          data: [
            { yAxis: 0, lineStyle: { color: c.textMuted, width: 1, type: "solid" } },
            ...(idx >= 0 ? [{ xAxis: idx, lineStyle: { color: c.borderStrong, width: 1, type: "dashed" as const } }] : []),
          ],
        },
      },
      {
        // Capacité choisie (série à part, étiquette directe du solde).
        name: "Capacité choisie",
        type: "scatter",
        symbolSize: 11,
        z: 5,
        itemStyle: { color: c.accent, borderColor: c.surface, borderWidth: 2 },
        tooltip: { show: false },
        label: {
          show: true,
          position: "top",
          distance: 8,
          color: c.text,
          fontWeight: 600,
          formatter: idx >= 0 ? formatMoney(curve[idx]?.net_balance) : "",
        },
        data: idx >= 0 ? [[idx, curve[idx]?.net_balance ?? 0]] : [],
      },
    ],
  };
}
