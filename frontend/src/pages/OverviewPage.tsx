import { Grid, Paper, SimpleGrid, Stack, Table, Text, Title, useComputedColorScheme } from "@mantine/core";
import {
  IconActivity, IconCoin, IconTarget, IconTrendingDown, IconUsers, IconChartArrowsVertical,
} from "@tabler/icons-react";
import type { EChartsOption } from "echarts";
import { useMemo } from "react";

import { useKpis } from "../api/queries";
import type { Kpis, LevelMetrics } from "../api/types";
import { RiskBadge } from "../components/Badges";
import { ChartCard } from "../components/ChartCard";
import { EChart } from "../components/EChart";
import { KpiCard } from "../components/KpiCard";
import { PageHeader } from "../components/PageHeader";
import { SummaryCard } from "../components/SummaryCard";
import { ErrorState, SkeletonKpiRow } from "../components/States";
import { formatMoney, formatNumber, formatShare } from "../lib/format";
import { activeFilterCount, useGlobalFilters } from "../store/filters";
import { RISK_LEVELS, type RiskLevel, risk, riskLabel, surfaces } from "../theme/tokens";

function level(kpis: Kpis, name: RiskLevel): LevelMetrics | undefined {
  return kpis.by_risk_level.find((l) => l.risk_level === name);
}

/** Composition par niveau de trois mesures (100 % empilé) : où se concentrent les départs. */
function useConcentrationOption(kpis: Kpis | undefined): EChartsOption | null {
  const scheme = useComputedColorScheme("light");
  return useMemo(() => {
    if (!kpis) return null;
    const measures = [
      { key: "share_of_portfolio", label: "Portefeuille" },
      { key: "share_of_expected_churners", label: "Départs attendus" },
      { key: "share_of_revenue_at_risk", label: "Revenu en jeu" },
    ] as const;
    const surface = surfaces[scheme].surface;
    return {
      grid: { left: 4, right: 12, top: 36, bottom: 4, containLabel: true },
      legend: { top: 0, left: 0, data: RISK_LEVELS.map((l) => l) },
      tooltip: {
        trigger: "item",
        valueFormatter: (v) => formatShare(Number(v) / 100),
      },
      xAxis: { type: "value", max: 100, axisLabel: { formatter: "{value} %" } },
      yAxis: { type: "category", data: measures.map((m) => m.label), inverse: true, axisLine: { show: false } },
      series: RISK_LEVELS.map((name) => {
        const lv = level(kpis, name);
        return {
          name,
          type: "bar",
          stack: "total",
          barWidth: 26,
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
    } satisfies EChartsOption;
  }, [kpis, scheme]);
}

/**
 * Titre-conclusion du graphique, adapté au périmètre : un seul niveau présent -> on le dit ;
 * sinon, le niveau le plus sur-représenté dans les départs attendus par rapport à son poids.
 */
function concentrationTitle(kpis: Kpis, filtered: boolean): string {
  const scope = filtered ? "du périmètre" : "du portefeuille";
  const present = kpis.by_risk_level.filter((l) => l.n_rows > 0);
  if (present.length === 0) return "Aucun client dans ce périmètre";
  if (present.length === 1 && present[0]) {
    return `Périmètre composé uniquement de clients ${present[0].risk_level} (${formatNumber(present[0].n_rows)} clients dans la base)`;
  }
  const ratio = (l: LevelMetrics) => (l.share_of_expected_churners ?? 0) / Math.max(l.share_of_portfolio ?? 0, 1e-9);
  const top = present
    .filter((l) => (l.share_of_portfolio ?? 0) >= 0.02)
    .sort((x, y) => ratio(y) - ratio(x))[0];
  if (!top) return "Concentration des départs attendus par niveau de risque";
  return `Les clients ${top.risk_level} pèsent ${formatShare(top.share_of_portfolio, 0)} ${scope} mais ${formatShare(top.share_of_expected_churners, 0)} des départs attendus`;
}

function LevelBreakdown({ kpis }: { kpis: Kpis }) {
  return (
    <Paper p="lg" withBorder h="100%" style={{ background: "var(--app-surface)", boxShadow: "var(--app-shadow-card)" }}>
      <Stack gap="md">
        <Stack gap={4}>
          <Title order={3} fz={16} fw={600}>Répartition par niveau</Title>
          <Text size="sm" c="var(--app-text-muted)">
            Deux lectures : clients dans la base et estimation pour un portefeuille réel.
          </Text>
        </Stack>
        <Table verticalSpacing={8} horizontalSpacing={0} withRowBorders styles={{ td: { borderColor: "var(--app-border)" }, th: { borderColor: "var(--app-border)" } }}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th><Text size="xs" c="var(--app-text-muted)" fw={600}>Niveau</Text></Table.Th>
              <Table.Th ta="right"><Text size="xs" c="var(--app-text-muted)" fw={600}>Base</Text></Table.Th>
              <Table.Th ta="right"><Text size="xs" c="var(--app-text-muted)" fw={600}>Portefeuille</Text></Table.Th>
              <Table.Th ta="right"><Text size="xs" c="var(--app-text-muted)" fw={600}>Risque/mois</Text></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {RISK_LEVELS.map((name) => {
              const lv = level(kpis, name);
              return (
                <Table.Tr key={name}>
                  <Table.Td><RiskBadge level={name} /></Table.Td>
                  <Table.Td ta="right" style={{ fontVariantNumeric: "tabular-nums" }}>{formatNumber(lv?.n_rows)}</Table.Td>
                  <Table.Td ta="right" style={{ fontVariantNumeric: "tabular-nums" }}>{formatNumber(lv?.n_portfolio_equiv)}</Table.Td>
                  <Table.Td ta="right" style={{ fontVariantNumeric: "tabular-nums" }}>{formatShare(lv?.expected_churn_rate, 1)}</Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
        <Text size="xs" c="var(--app-text-muted)">
          Base : lignes réelles du jeu de données (50 % de churners). Portefeuille : estimation
          pour 100 000 clients au taux supposé de 2 %/mois.
        </Text>
      </Stack>
    </Paper>
  );
}

export function OverviewPage() {
  const filters = useGlobalFilters();
  const { data: kpis, isLoading, error, refetch, isFetching } = useKpis(filters);
  const option = useConcentrationOption(kpis);

  const high = kpis ? level(kpis, "High") : undefined;
  const campaign = kpis?.official_campaign;
  const conclusion = kpis ? concentrationTitle(kpis, activeFilterCount(filters) > 0) : "Concentration des départs attendus par niveau de risque";

  return (
    <>
      <PageHeader
        title="Vue d'ensemble"
        description="Combien de départs attendre le mois prochain, ce qu'ils représentent en revenu, et ce qu'une campagne ciblée atteint."
      />
      {error ? (
        <Paper withBorder p="xl" style={{ background: "var(--app-surface)" }}>
          <ErrorState message={error.message} onRetry={() => void refetch()} />
        </Paper>
      ) : (
        <Stack gap="lg" style={{ opacity: isFetching && !isLoading ? 0.72 : 1, transition: "opacity 140ms" }}>
          {isLoading || !kpis ? (
            <SkeletonKpiRow count={4} />
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
              <KpiCard
                emphasis
                label="Départs attendus / mois"
                value={kpis.expected_churners}
                format={(v) => formatNumber(v)}
                nature="portfolio"
                icon={<IconTrendingDown size={16} stroke={1.8} />}
                detail={<>Risque mensuel moyen <b>{formatShare(kpis.expected_churn_rate, 2)}</b></>}
                definition="Somme des probabilités de départ du mois, ramenées au taux de churn réel supposé (2 %/mois), pour un portefeuille de 100 000 clients. C'est une estimation, pas un comptage."
              />
              <KpiCard
                label="Revenu mensuel en jeu"
                value={kpis.revenue_at_risk_monthly}
                format={(v) => formatMoney(v)}
                nature="portfolio"
                icon={<IconCoin size={16} stroke={1.8} />}
                detail={<>soit <b>{formatShare(kpis.revenue_at_risk_share_of_bill, 1)}</b> de la facture mensuelle</>}
                definition="Probabilité de départ × facture mensuelle, sommée sur les clients : le revenu qu'on s'attend à perdre le mois prochain si rien n'est fait. Ce n'est pas un revenu préservé."
              />
              <KpiCard
                label="Clients High"
                value={high?.n_portfolio_equiv}
                format={(v) => formatNumber(v)}
                nature="portfolio"
                icon={<IconActivity size={16} stroke={1.8} />}
                detail={<><b>{formatNumber(high?.n_rows)}</b> clients High dans la base</>}
                definition="Niveau High : les 10 % du portefeuille au risque le plus élevé (capacité de campagne). Le nombre de lignes de la base est plus élevé car le jeu de données est enrichi en churners."
              />
              <KpiCard
                label="Campagne top 10 %"
                value={campaign?.churners_per_1000_contacted}
                format={(v) => formatNumber(v, 0)}
                nature="portfolio"
                icon={<IconTarget size={16} stroke={1.8} />}
                detail={<>futurs churners pour 1 000 contacts, contre <b>{formatNumber(campaign?.random_churners_per_1000_contacted)}</b> au hasard</>}
                definition="Campagne officielle : ciblage des 10 % de clients actifs les plus risqués, inactifs traités à part. Ce sont des churners atteints ; les départs évités dépendent du taux de succès de l'offre, à mesurer."
              />
            </SimpleGrid>
          )}

          <Grid gap="md">
            <Grid.Col span={{ base: 12, lg: 8 }}>
              <ChartCard
                title={conclusion}
                subtitle="Part de chaque niveau dans le portefeuille, les départs attendus et le revenu en jeu (estimation portefeuille)."
                height={220}
                loading={isLoading}
                empty={!!kpis && kpis.n_rows === 0}
                footer={`Hypothèse : taux de churn réel de 2 %/mois. ${riskLabel.Inactif} : sans usage, traité à part.`}
              >
                {option && (
                  <EChart
                    option={option}
                    height={220}
                    ariaLabel={`${conclusion}. Répartition par niveau de risque du portefeuille, des départs attendus et du revenu en jeu.`}
                  />
                )}
              </ChartCard>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 4 }}>
              {kpis ? <LevelBreakdown kpis={kpis} /> : <SkeletonKpiRow count={1} />}
            </Grid.Col>
          </Grid>

          {kpis && (
            <Grid gap="md">
              <Grid.Col span={{ base: 12, sm: 6, lg: 3 }}>
              <KpiCard
                label="Clients dans la base"
                value={kpis.n_rows}
                format={(v) => formatNumber(v)}
                nature="base"
                icon={<IconUsers size={16} stroke={1.8} />}
                detail={<>dont <b>{formatNumber(kpis.inactive_n_rows)}</b> inactifs (vérifier la ligne)</>}
                definition="Lignes réelles du jeu de données correspondant aux filtres. Sert aux listes et aux filtres ; ne représente pas directement un portefeuille réel."
              />
              </Grid.Col>
              <Grid.Col span={{ base: 12, sm: 6, lg: 3 }}>
              <KpiCard
                label="AUC du modèle (test)"
                value={kpis.model.auc_test}
                format={(v) => formatNumber(v, 3)}
                nature="model"
                icon={<IconChartArrowsVertical size={16} stroke={1.8} />}
                detail={<>hors fold sur le train : <b>{formatNumber(kpis.model.auc_out_of_fold_train, 3)}</b></>}
                definition="Probabilité qu'un churner tiré au hasard soit mieux classé qu'un non-churner (0,5 = hasard). Mesurée sur le jeu de test, qui n'a servi à aucun choix."
              />
              </Grid.Col>
              <Grid.Col span={{ base: 12, lg: 6 }}>
                <SummaryCard scopeNote={activeFilterCount(filters) > 0} />
              </Grid.Col>
            </Grid>
          )}
        </Stack>
      )}
    </>
  );
}
