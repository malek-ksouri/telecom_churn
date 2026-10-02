import { Grid, Paper, SimpleGrid, Stack, Table, Text, useComputedColorScheme } from "@mantine/core";
import { IconCoin, IconFlame, IconTarget, IconTrendingDown, IconUsers } from "@tabler/icons-react";
import type { EChartsOption } from "echarts";
import { useMemo } from "react";

import { useCampaign, useKpis, useRiskDistribution } from "../api/queries";
import type { CampaignPoint, Kpis, LevelMetrics } from "../api/types";
import { histogramOption } from "../charts/options";
import { ChartCard } from "../components/ChartCard";
import { EChart } from "../components/EChart";
import { KpiCard } from "../components/KpiCard";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, SkeletonKpiRow } from "../components/States";
import { SummaryCard } from "../components/SummaryCard";
import { formatMoney, formatNumber, formatPct, formatShare } from "../lib/format";
import { activeFilterCount, useGlobalFilters } from "../store/filters";
import { RISK_LEVELS, type RiskLevel, risk, surfaces } from "../theme/tokens";

function level(kpis: Kpis, name: RiskLevel): LevelMetrics | undefined {
  return kpis.by_risk_level.find((l) => l.risk_level === name);
}

/**
 * Titre-conclusion, adapté au périmètre : un seul niveau présent -> on le dit ; sinon, le
 * niveau le plus sur-représenté dans les départs attendus par rapport à son poids.
 */
function concentrationTitle(kpis: Kpis, filtered: boolean): string {
  const scope = filtered ? "du périmètre" : "du portefeuille";
  const present = kpis.by_risk_level.filter((l) => l.n_rows > 0);
  if (present.length === 0) return "Aucun client dans ce périmètre";
  if (present.length === 1 && present[0]) {
    return `Périmètre composé uniquement de clients ${present[0].risk_level}`;
  }
  const ratio = (l: LevelMetrics) => (l.share_of_expected_churners ?? 0) / Math.max(l.share_of_portfolio ?? 0, 1e-9);
  const top = present.filter((l) => (l.share_of_portfolio ?? 0) >= 0.02).sort((x, y) => ratio(y) - ratio(x))[0];
  if (!top) return "Répartition des départs attendus par niveau";
  return `Les clients ${top.risk_level} pèsent ${formatShare(top.share_of_portfolio, 0)} ${scope} mais ${formatShare(top.share_of_expected_churners, 0)} des départs attendus`;
}

/** Composition par niveau de trois mesures (100 % empilé) : où se concentrent les départs. */
function concentrationOption(kpis: Kpis, scheme: "light" | "dark"): EChartsOption {
  const measures = [
    { key: "share_of_portfolio", label: "Portefeuille" },
    { key: "share_of_expected_churners", label: "Départs attendus" },
    { key: "share_of_revenue_at_risk", label: "Revenu en jeu" },
  ] as const;
  const surface = surfaces[scheme].surface;
  return {
    grid: { left: 4, right: 12, top: 36, bottom: 4, containLabel: true },
    legend: { top: 0, left: 0 },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const { seriesName, name, value } = p as { seriesName: string; name: string; value: number };
        const lv = level(kpis, seriesName as RiskLevel);
        return `<b>${seriesName}</b> · ${name} : <b>${formatPct(value, 1)}</b><br/>` +
          `<span style="opacity:.72">${formatNumber(lv?.n_rows)} clients dans la base · ${formatNumber(lv?.n_portfolio_equiv)} en estimation portefeuille</span>`;
      },
    },
    xAxis: { type: "value", max: 100, axisLabel: { formatter: "{value} %" } },
    yAxis: { type: "category", data: measures.map((m) => m.label), inverse: true, axisLine: { show: false } },
    series: RISK_LEVELS.map((name) => {
      const lv = level(kpis, name);
      return {
        name,
        type: "bar",
        stack: "total",
        barWidth: 24,
        itemStyle: { color: risk[scheme][name], borderColor: surface, borderWidth: 2, borderRadius: 0 },
        label: {
          show: true,
          formatter: (p: { value: unknown }) => (Number(p.value) >= 8 ? `${formatNumber(Number(p.value), 0)} %` : ""),
          color: name === "Medium" ? "#2b1d00" : "#ffffff",
          fontWeight: 600,
          fontSize: 12,
        },
        emphasis: { focus: "series" },
        data: measures.map((m) => 100 * (lv?.[m.key] ?? 0)),
      };
    }),
  };
}

const CAPACITIES = [5, 10, 20];

/** Capacité 5 / 10 / 20 % : clients ciblés, churners attendus, facteur contre le hasard. */
function CapacityTable({ curve, loading }: { curve: CampaignPoint[] | undefined; loading: boolean }) {
  const rows = CAPACITIES.map((cap) => curve?.find((p) => p.capacity_pct === cap)).filter(
    (p): p is CampaignPoint => p !== undefined,
  );
  const num = { style: { fontVariantNumeric: "tabular-nums" as const } };
  return (
    <ChartCard
      title="Chaque point de capacité supplémentaire atteint moins de churners que le précédent"
      subtitle="Clients actifs ciblés par risque décroissant ; inactifs traités à part. Estimation portefeuille (taux supposé 2 %/mois)."
      height={170}
      loading={loading}
      empty={!loading && rows.length === 0}
      footer="Churners atteints, pas départs évités : ceux-ci dépendent du taux de succès de l'offre (voir le simulateur)."
    >
      <Table verticalSpacing={10} horizontalSpacing="xs" styles={{ td: { borderColor: "var(--app-border)" }, th: { borderColor: "var(--app-border)" } }}>
        <Table.Thead>
          <Table.Tr>
            {["Capacité", "Clients ciblés", "Churners atteints", "Au hasard", "Facteur", "Part des départs"].map((h, i) => (
              <Table.Th key={h} ta={i === 0 ? "left" : "right"}>
                <Text size="xs" fw={600} c="var(--app-text-muted)">{h}</Text>
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((p) => (
            <Table.Tr key={p.capacity_pct} style={p.capacity_pct === 10 ? { background: "color-mix(in srgb, var(--app-accent) 7%, transparent)" } : undefined}>
              <Table.Td fw={600}>{formatPct(p.capacity_pct, 0)}{p.capacity_pct === 10 ? " · officielle" : ""}</Table.Td>
              <Table.Td ta="right" {...num}>{formatNumber(p.targeted_n_portfolio_equiv)}</Table.Td>
              <Table.Td ta="right" fw={600} {...num}>{formatNumber(p.expected_churners)}</Table.Td>
              <Table.Td ta="right" c="var(--app-text-muted)" {...num}>{formatNumber(p.random_churners)}</Table.Td>
              <Table.Td ta="right" {...num}>× {formatNumber(p.lift_vs_random, 2)}</Table.Td>
              <Table.Td ta="right" {...num}>{formatShare(p.share_of_expected_churners, 0)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ChartCard>
  );
}

export function OverviewPage() {
  const filters = useGlobalFilters();
  const filtered = activeFilterCount(filters) > 0;
  const scheme = useComputedColorScheme("light");
  const kpisQuery = useKpis(filters);
  const distQuery = useRiskDistribution(filters);
  const capacityQuery = useCampaign(
    { capacity_pct: 10, success_rate: 0, offer_cost: null, revenue_horizon_months: 12 },
    filters,
  );
  const kpis = kpisQuery.data;
  const dist = distQuery.data;

  const concentration = useMemo(() => (kpis ? concentrationOption(kpis, scheme) : null), [kpis, scheme]);
  const histogram = useMemo(
    () =>
      dist
        ? histogramOption(dist.bins, { high: dist.thresholds.high_p_real_pct, medium: dist.thresholds.medium_p_real_pct }, scheme)
        : null,
    [dist, scheme],
  );

  const high = kpis ? level(kpis, "High") : undefined;
  const campaign = kpis?.official_campaign;
  const headline = kpis
    ? `${formatNumber(kpis.expected_churners)} départs attendus le mois prochain, ${formatMoney(kpis.revenue_at_risk_monthly)} de revenu mensuel en jeu`
    : "";
  const dimmed = { opacity: kpisQuery.isFetching && !kpisQuery.isLoading ? 0.72 : 1, transition: "opacity 140ms" };

  if (kpisQuery.error) {
    return (
      <>
        <PageHeader eyebrow="Vue d'ensemble" title="Données indisponibles" />
        <Paper withBorder p="xl" style={{ background: "var(--app-surface)" }}>
          <ErrorState message={kpisQuery.error.message} onRetry={() => void kpisQuery.refetch()} />
        </Paper>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Vue d'ensemble"
        title={headline}
        loading={!kpis}
        description={`${filtered ? "Périmètre filtré. " : ""}Estimations pour un portefeuille réel au taux de churn supposé de 2 %/mois ; les listes et filtres comptent les clients de la base.`}
      />
      <Stack gap="lg" style={dimmed}>
        {!kpis ? (
          <SkeletonKpiRow count={5} />
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3, xl: 5 }} spacing="md">
            <KpiCard
              label="Clients"
              value={kpis.n_rows}
              format={(v) => formatNumber(v)}
              nature="base"
              icon={<IconUsers size={16} stroke={1.8} />}
              detail={<>dont <b>{formatNumber(kpis.inactive_n_rows)}</b> inactifs</>}
              definition="Lignes réelles du jeu de données dans le périmètre. Le jeu est enrichi en churners (50 %) : ce n'est pas la taille d'un vrai portefeuille."
            />
            <KpiCard
              emphasis
              label="Départs"
              value={kpis.expected_churners}
              format={(v) => formatNumber(v)}
              nature="portfolio"
              icon={<IconTrendingDown size={16} stroke={1.8} />}
              detail={<>attendus sur un mois · risque moyen <b>{formatShare(kpis.expected_churn_rate, 2)}</b></>}
              definition="Somme des probabilités de départ du mois, ramenées au taux de churn réel supposé (2 %/mois), pour un portefeuille de 100 000 clients. Une estimation, pas un comptage."
            />
            <KpiCard
              label="Revenu en jeu"
              value={kpis.revenue_at_risk_monthly}
              format={(v) => formatMoney(v)}
              nature="portfolio"
              icon={<IconCoin size={16} stroke={1.8} />}
              detail={<>par mois · <b>{formatShare(kpis.revenue_at_risk_share_of_bill, 1)}</b> de la facture</>}
              definition="Probabilité de départ × facture mensuelle : le revenu qu'on s'attend à perdre le mois prochain sans action. Ce n'est pas un revenu préservé."
            />
            <KpiCard
              label="Clients High"
              value={high?.n_rows}
              format={(v) => formatNumber(v)}
              nature="base"
              icon={<IconFlame size={16} stroke={1.8} />}
              detail={<>≈ <b>{formatNumber(high?.n_portfolio_equiv)}</b> en estimation portefeuille</>}
              definition="Niveau High : les 10 % du portefeuille au risque le plus élevé. La base en compte davantage car elle est enrichie en churners ; l'estimation portefeuille donne l'équivalent dans un vrai portefeuille de 100 000 clients."
            />
            <KpiCard
              label="Campagne 10 %"
              value={campaign?.churners_per_1000_contacted}
              format={(v) => `${formatNumber(v, 0)} / 1 000`}
              nature="portfolio"
              icon={<IconTarget size={16} stroke={1.8} />}
              detail={<>churners atteints pour 1 000 contactés, contre <b>{formatNumber(campaign?.random_churners_per_1000_contacted)}</b> au hasard</>}
              definition="Ciblage des 10 % de clients actifs les plus risqués, inactifs traités à part. Ce sont des churners atteints : les départs évités dépendent du taux de succès de l'offre, à mesurer."
            />
          </SimpleGrid>
        )}

        <Grid gap="md">
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <ChartCard
              title={kpis ? concentrationTitle(kpis, filtered) : "Répartition par niveau de risque"}
              subtitle="Part de chaque niveau dans le portefeuille, les départs attendus et le revenu en jeu (estimation portefeuille)."
              height={230}
              loading={!kpis}
              empty={!!kpis && kpis.n_rows === 0}
              footer="Inactif : aucune minute d'appel ou usage non mesuré ; traité à part (vérifier la ligne)."
            >
              {concentration && (
                <EChart option={concentration} height={230} ariaLabel="Répartition par niveau de risque du portefeuille, des départs attendus et du revenu en jeu." />
              )}
            </ChartCard>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <ChartCard
              title={
                dist?.quantiles_portfolio_equiv_pct.p50 !== undefined
                  ? `La moitié des clients a moins de ${formatPct(dist.quantiles_portfolio_equiv_pct.p50, 1)} de risque mensuel ; 1 % dépasse ${formatPct(dist.quantiles_portfolio_equiv_pct.p99 ?? 0, 1)}`
                  : "Distribution du risque mensuel"
              }
              subtitle="Nombre de clients (estimation portefeuille) par classe de probabilité mensuelle de départ, empilé par niveau."
              height={230}
              loading={!dist}
              error={distQuery.error}
              onRetry={() => void distQuery.refetch()}
              footer="Traits pointillés : seuils des niveaux High et Medium, en probabilité mensuelle au taux supposé."
            >
              {histogram && (
                <EChart option={histogram} height={230} ariaLabel="Histogramme des probabilités mensuelles de départ, par niveau, avec les seuils High et Medium." />
              )}
            </ChartCard>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 7 }}>
            <CapacityTable curve={capacityQuery.data?.curve} loading={!capacityQuery.data} />
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 5 }}>
            <SummaryCard scopeNote={filtered} />
          </Grid.Col>
        </Grid>
      </Stack>
    </>
  );
}
