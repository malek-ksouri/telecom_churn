/** Graphiques de la fiche client : jauge du risque mensuel et cascade SHAP. */
import type { CustomSeriesRenderItemAPI, CustomSeriesRenderItemParams, EChartsOption } from "echarts";

import type { CustomerExplanation } from "../api/types";
import { formatNumber, formatPct } from "../lib/format";
import { type ColorScheme, type RiskLevel, risk, surfaces } from "../theme/tokens";

/**
 * Jauge du risque mensuel (au taux supposé). L'arc est coloré par zones de niveau (Low,
 * Medium, High) aux seuils réels ; l'échelle s'arrête à `max` (au-delà : jauge pleine).
 */
export function gaugeOption(
  pRealPct: number,
  level: RiskLevel,
  thresholds: { medium: number; high: number },
  scheme: ColorScheme,
): EChartsOption {
  const c = surfaces[scheme];
  const max = Math.max(12, Math.ceil(pRealPct / 4) * 4);
  const r = risk[scheme];
  return {
    series: [
      {
        type: "gauge",
        min: 0,
        max,
        startAngle: 205,
        endAngle: -25,
        radius: "100%",
        center: ["50%", "58%"],
        splitNumber: 4,
        axisLine: {
          lineStyle: {
            width: 10,
            color: [
              [thresholds.medium / max, r.Low],
              [thresholds.high / max, r.Medium],
              [1, r.High],
            ],
          },
        },
        progress: { show: false },
        pointer: { length: "58%", width: 4, itemStyle: { color: c.text } },
        anchor: { show: true, size: 10, itemStyle: { color: c.text, borderColor: c.surface, borderWidth: 2 } },
        axisTick: { show: false },
        splitLine: { length: 6, distance: -10, lineStyle: { color: c.surface, width: 2 } },
        axisLabel: {
          distance: 20,
          color: c.textMuted,
          fontSize: 10,
          formatter: (v: number) => `${formatNumber(v)} %`,
        },
        title: { show: false },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, "56%"],
          fontSize: 24,
          fontWeight: 650,
          color: c.text,
          formatter: () => formatPct(pRealPct, 1),
        },
        data: [{ value: Math.min(pRealPct, max), name: level }],
      },
    ],
  };
}

interface Step {
  label: string;
  start: number;
  end: number;
  kind: "total" | "up" | "down";
  text?: string | null;
  family?: string;
}

/** Étapes de la cascade : score moyen -> contributions -> autres -> score du client. */
export function waterfallSteps(e: CustomerExplanation): Step[] {
  const steps: Step[] = [{ label: "Score moyen du modèle", start: 0, end: e.base_value_log_odds, kind: "total" }];
  let running = e.base_value_log_odds;
  for (const c of e.contributions) {
    steps.push({
      label: c.label, start: running, end: running + c.contribution_log_odds,
      kind: c.contribution_log_odds >= 0 ? "up" : "down", text: c.text, family: c.family_label,
    });
    running += c.contribution_log_odds;
  }
  if (e.others_count > 0) {
    steps.push({
      label: `Autres variables (${formatNumber(e.others_count)})`, start: running,
      end: running + e.others_contribution_log_odds,
      kind: e.others_contribution_log_odds >= 0 ? "up" : "down",
    });
  }
  steps.push({ label: "Score du client", start: 0, end: e.log_odds, kind: "total" });
  return steps;
}

export function waterfallOption(e: CustomerExplanation, scheme: ColorScheme): EChartsOption {
  const c = surfaces[scheme];
  const steps = waterfallSteps(e);
  const color = { up: risk[scheme].High, down: risk[scheme].Low, total: c.textMuted };
  const values = steps.flatMap((s) => [s.start, s.end]);
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const pad = (hi - lo) * 0.18;
  return {
    grid: { left: 4, right: 12, top: 8, bottom: 30, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const s = steps[(p as { dataIndex: number }).dataIndex];
        if (!s) return "";
        const delta = s.end - s.start;
        const body = s.kind === "total"
          ? `log-odds : <b>${formatNumber(s.end, 2)}</b>`
          : `${s.text ? `${s.text}<br/>` : ""}contribution : <b>${delta >= 0 ? "+" : ""}${formatNumber(delta, 3)}</b> (${delta >= 0 ? "augmente" : "réduit"} le risque)`;
        return `<div style="max-width:280px;white-space:normal"><b>${s.label}</b>${s.family ? ` · <span style="opacity:.7">${s.family}</span>` : ""}<br/>${body}</div>`;
      },
    },
    xAxis: {
      type: "value",
      min: lo - pad,
      max: hi + pad,
      name: "score du modèle (log-odds) : à droite, plus de risque",
      nameLocation: "middle",
      nameGap: 22,
      axisLabel: { formatter: (v: number) => formatNumber(v, 1) },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: steps.map((s) => s.label),
      axisLine: { show: false },
      axisLabel: {
        width: 150,
        overflow: "truncate",
        color: c.textSecondary,
        fontWeight: 500,
      },
    },
    series: [
      {
        type: "custom",
        renderItem: (_params: CustomSeriesRenderItemParams, api: CustomSeriesRenderItemAPI) => {
          const idx = api.value(0) as number;
          const s = steps[idx];
          if (!s) return null;
          const a = api.coord([s.start, idx]);
          const b = api.coord([s.end, idx]);
          const size = api.size?.([0, 1]) as number[] | undefined;
          const h = Math.max(8, (size?.[1] ?? 24) * 0.58);
          const x0 = Math.min(a[0] ?? 0, b[0] ?? 0);
          const w = Math.max(2, Math.abs((b[0] ?? 0) - (a[0] ?? 0)));
          const y = (a[1] ?? 0) - h / 2;
          const delta = s.end - s.start;
          const labelText = s.kind === "total" ? formatNumber(s.end, 2) : `${delta >= 0 ? "+" : ""}${formatNumber(delta, 2)}`;
          const right = s.kind === "total" ? s.end >= 0 : delta >= 0;
          return {
            type: "group",
            children: [
              {
                type: "rect",
                shape: { x: x0, y, width: w, height: h, r: 3 },
                style: { fill: color[s.kind] },
              },
              {
                type: "text",
                style: {
                  text: labelText,
                  x: right ? x0 + w + 6 : x0 - 6,
                  y: y + h / 2,
                  align: right ? "left" : "right",
                  verticalAlign: "middle",
                  fill: c.textSecondary,
                  font: "600 11px Inter Variable, Inter, sans-serif",
                },
              },
            ],
          };
        },
        encode: { x: [1, 2], y: 0 },
        data: steps.map((s, i) => [i, s.start, s.end]),
        z: 3,
      },
      {
        // Repère du score moyen (point de départ de la lecture).
        type: "line",
        data: [],
        markLine: {
          symbol: "none",
          silent: true,
          label: { show: false },
          lineStyle: { color: c.borderStrong, type: "dashed", width: 1 },
          data: [{ xAxis: e.base_value_log_odds }],
        },
      },
    ],
  };
}
