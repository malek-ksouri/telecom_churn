import { useComputedColorScheme } from "@mantine/core";
import { useReducedMotion } from "framer-motion";
import { BarChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";
import ReactEChartsCore from "echarts-for-react/esm/core";

import { ECHARTS_THEME, registerEchartsThemes } from "../theme/echartsTheme";

// Import modulaire : seuls les graphiques et composants utilisés sont embarqués.
echarts.use([
  BarChart, LineChart, ScatterChart, HeatmapChart, GridComponent, TooltipComponent,
  LegendComponent, MarkLineComponent, DatasetComponent, VisualMapComponent, CanvasRenderer,
]);
registerEchartsThemes();

interface EChartProps {
  option: EChartsOption;
  height: number;
  /** Description textuelle du graphique (lecteurs d'écran). */
  ariaLabel: string;
  onEvents?: Record<string, (params: unknown) => void>;
}

/** Graphique ECharts au thème de l'application (clair ou sombre, suit la bascule). */
export function EChart({ option, height, ariaLabel, onEvents }: EChartProps) {
  const scheme = useComputedColorScheme("light");
  const reduce = useReducedMotion();
  return (
    <div role="img" aria-label={ariaLabel}>
      <ReactEChartsCore
        echarts={echarts}
        option={{ animation: !reduce, animationDuration: 300, ...option }}
        theme={ECHARTS_THEME[scheme]}
        style={{ height, width: "100%" }}
        notMerge
        lazyUpdate
        {...(onEvents ? { onEvents } : {})}
      />
    </div>
  );
}
