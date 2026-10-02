import {
  Badge, Grid, Group, Paper, SegmentedControl, SimpleGrid, Skeleton, Stack, Text, Title,
  UnstyledButton, useComputedColorScheme,
} from "@mantine/core";
import { IconArrowDownRight, IconArrowUpRight, IconEyeOff } from "@tabler/icons-react";
import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import {
  useDrivers, useHeatmap, useKpis, useSegmentProfiles, useSegments, withoutKeys,
} from "../api/queries";
import type { GlobalFilterKey, SegmentProfile } from "../api/types";
import { driversOption, heatmapOption, segmentBarOption } from "../charts/options";
import { ChartCard } from "../components/ChartCard";
import { EChart } from "../components/EChart";
import { PageHeader } from "../components/PageHeader";
import { ErrorState } from "../components/States";
import { filterValueLabel } from "../lib/filterLabels";
import { formatMoney, formatNumber, formatShare } from "../lib/format";
import { useFiltersStore, useGlobalFilters } from "../store/filters";
import { surfaces } from "../theme/tokens";
import classes from "./SegmentsPage.module.css";

type SegmentDimension = "tenure_band" | "handset_age_band" | "usage_band" | "area" | "cluster" | "action";

const DIMENSIONS: { value: SegmentDimension; label: string }[] = [
  { value: "tenure_band", label: "Ancienneté" },
  { value: "handset_age_band", label: "Terminal" },
  { value: "usage_band", label: "Usage" },
  { value: "area", label: "Région" },
  { value: "cluster", label: "Profil" },
  { value: "action", label: "Action" },
];

const DIM_NOUN: Record<SegmentDimension, string> = {
  tenure_band: "tranche d'ancienneté",
  handset_age_band: "tranche d'âge du terminal",
  usage_band: "tranche d'usage",
  area: "région",
  cluster: "profil",
  action: "action suggérée",
};

function isSegmentDimension(v: string | null): v is SegmentDimension {
  return DIMENSIONS.some((d) => d.value === v);
}

/** Ajoute la modalité aux filtres, ou la retire si elle y est déjà (drill-down réversible). */
function useToggleFilter() {
  const add = useFiltersStore((s) => s.add);
  const remove = useFiltersStore((s) => s.remove);
  const filters = useGlobalFilters();
  return (key: GlobalFilterKey, value: string) => {
    if (filters[key].includes(value)) remove(key, value);
    else add(key, value);
  };
}

function SegmentBars({ dimension }: { dimension: SegmentDimension }) {
  const filters = useGlobalFilters();
  const scheme = useComputedColorScheme("light");
  const toggle = useToggleFilter();
  const query = useSegments(dimension, withoutKeys(filters, [dimension]));
  const overall = useKpis(withoutKeys(filters, [dimension]));
  const items = useMemo(() => query.data?.items ?? [], [query.data]);
  const labelOf = useCallback((v: string) => filterValueLabel(dimension, v), [dimension]);
  const rate = overall.data?.expected_churn_rate ?? null;
  const option = useMemo(
    () => segmentBarOption(items, filters[dimension], rate, labelOf, scheme),
    [items, filters, dimension, rate, labelOf, scheme],
  );
  const top = [...items].filter((i) => i.n_rows >= 30).sort((a, b) => (b.expected_churn_rate ?? 0) - (a.expected_churn_rate ?? 0))[0];
  const title =
    top && rate
      ? `${labelOf(top.value)} : ${formatShare(top.expected_churn_rate, 2)} de risque mensuel, ${formatNumber((top.expected_churn_rate ?? 0) / rate, 1)} fois la moyenne`
      : `Risque par ${DIM_NOUN[dimension]}`;
  const height = Math.max(200, items.length * 34 + 30);
  return (
    <ChartCard
      title={title}
      subtitle={`Risque mensuel moyen par ${DIM_NOUN[dimension]} (estimation au taux supposé de 2 %). Cliquez une barre pour l'ajouter aux filtres ; recliquez pour la retirer.`}
      height={height}
      loading={!query.data}
      error={query.error}
      onRetry={() => void query.refetch()}
      empty={!!query.data && items.length === 0}
      footer="Infobulle : clients dans la base, estimation portefeuille, revenu en jeu. Trait pointillé : moyenne du périmètre."
    >
      <EChart
        option={option}
        height={height}
        ariaLabel={`${title}. Risque mensuel moyen par ${DIM_NOUN[dimension]}.`}
        onEvents={{
          click: (p) => {
            const item = items[(p as { dataIndex: number }).dataIndex];
            if (item) toggle(dimension, item.value);
          },
        }}
      />
    </ChartCard>
  );
}

function RiskHeatmap() {
  const filters = useGlobalFilters();
  const scheme = useComputedColorScheme("light");
  const setFilter = useFiltersStore((s) => s.set);
  const query = useHeatmap("tenure_band", "handset_age_band", withoutKeys(filters, ["tenure_band", "handset_age_band"]));
  const data = query.data;
  const option = useMemo(
    () =>
      data
        ? heatmapOption(
            data.cells, data.x_values, data.y_values,
            { x: filters.tenure_band, y: filters.handset_age_band },
            (v) => v, (v) => v, scheme,
          )
        : null,
    [data, filters.tenure_band, filters.handset_age_band, scheme],
  );
  const top = data?.cells.filter((c) => !c.low_sample).sort((a, b) => (b.expected_churn_rate ?? 0) - (a.expected_churn_rate ?? 0))[0];
  const title = top
    ? `Risque maximal : ancienneté ${top.x} et terminal de ${top.y} (${formatShare(top.expected_churn_rate, 1)} par mois)`
    : "Ancienneté × âge du terminal";
  return (
    <ChartCard
      title={title}
      subtitle="Risque mensuel moyen (%) par ancienneté et âge du terminal. Cliquez une case pour filtrer sur ces deux modalités."
      height={320}
      loading={!data}
      error={query.error}
      onRetry={() => void query.refetch()}
      footer={`Cases grisées : moins de ${String(data?.min_rows_for_rate ?? 30)} clients dans la base, taux non affiché.`}
    >
      {option && data && (
        <EChart
          option={option}
          height={320}
          ariaLabel={`${title}. Carte de chaleur du risque mensuel par ancienneté et âge du terminal.`}
          onEvents={{
            click: (p) => {
              const cell = (p as { data?: { cell?: { x: string; y: string } } }).data?.cell;
              if (!cell) return;
              const same = filters.tenure_band.length === 1 && filters.tenure_band[0] === cell.x &&
                filters.handset_age_band.length === 1 && filters.handset_age_band[0] === cell.y;
              setFilter("tenure_band", same ? [] : [cell.x]);
              setFilter("handset_age_band", same ? [] : [cell.y]);
            },
          }}
        />
      )}
    </ChartCard>
  );
}

function DriversBlock() {
  const filters = useGlobalFilters();
  const scheme = useComputedColorScheme("light");
  const query = useDrivers(filters);
  const data = query.data;
  const actionable = data?.actionable.slice(0, 8) ?? [];
  const contextAll = data?.context ?? [];
  const context = contextAll.filter((d) => !d.sensitive).slice(0, 6);
  const hidden = contextAll.filter((d) => d.sensitive).length;
  const c = surfaces[scheme];
  const top3 = actionable.slice(0, 3).map((d) => d.label.toLowerCase());
  const title = top3.length === 3
    ? `Selon le modèle, ${top3[0] ?? ""}, ${top3[1] ?? ""} et ${top3[2] ?? ""} pèsent le plus parmi les leviers actionnables`
    : "Facteurs de risque selon le modèle";
  const hA = actionable.length * 30 + 16;
  const hC = context.length * 30 + 16;
  if (query.error) {
    return <Paper withBorder p="lg"><ErrorState compact message={query.error.message} onRetry={() => void query.refetch()} /></Paper>;
  }
  return (
    <Paper p="lg" withBorder style={{ background: "var(--app-surface)", boxShadow: "var(--app-shadow-card)" }}>
      <Stack gap="md">
        <Stack gap={4}>
          <Title order={3} fz={16} fw={600} lh={1.35}>{title}</Title>
          <Text size="sm" c="var(--app-text-muted)">
            Part de l'importance SHAP (moyenne des contributions absolues) sur les clients du périmètre.
            Associations apprises par le modèle, pas des causes.
          </Text>
        </Stack>
        <Grid gap="xl">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Group gap={8} mb={6}>
              <Badge variant="light" color="accent" radius="sm" styles={{ root: { textTransform: "none" } }}>Actionnables</Badge>
              <Text size="xs" c="var(--app-text-muted)">leviers d'une action commerciale</Text>
            </Group>
            {data ? (
              <EChart option={driversOption(actionable, c.accent, scheme)} height={hA} ariaLabel="Importance des facteurs actionnables selon le modèle." />
            ) : (
              <Skeleton height={250} />
            )}
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Group gap={8} mb={6}>
              <Badge variant="light" color="gray" radius="sm" styles={{ root: { textTransform: "none" } }}>Contexte</Badge>
              <Text size="xs" c="var(--app-text-muted)">à connaître, sans levier direct</Text>
            </Group>
            {data ? (
              <EChart option={driversOption(context, c.textMuted, scheme)} height={hC} ariaLabel="Importance des facteurs de contexte selon le modèle." />
            ) : (
              <Skeleton height={180} />
            )}
            {hidden > 0 && (
              <Group gap={6} mt={8} wrap="nowrap" align="flex-start">
                <IconEyeOff size={14} stroke={1.8} color="var(--app-text-muted)" style={{ flexShrink: 0, marginTop: 2 }} />
                <Text size="xs" c="var(--app-text-muted)">
                  {hidden} variables socio-démographiques sensibles masquées : elles ne servent ni au ciblage ni aux messages.
                </Text>
              </Group>
            )}
          </Grid.Col>
        </Grid>
      </Stack>
    </Paper>
  );
}

function ProfileCard({ profile, selected, dimmed, onToggle }: {
  profile: SegmentProfile; selected: boolean; dimmed: boolean; onToggle: () => void;
}) {
  return (
    <UnstyledButton
      onClick={onToggle}
      className={classes.profile}
      data-selected={selected || undefined}
      data-dimmed={dimmed || undefined}
      aria-pressed={selected}
      aria-label={`${profile.name} : ${selected ? "retirer du filtre" : "filtrer sur ce profil"}`}
    >
      <Stack gap={10}>
        <Text fw={600} size="sm" lh={1.3} lineClamp={2} mih={36}>{profile.name}</Text>
        <Group gap={6} align="baseline">
          <Text className={classes.rate}>{formatShare(profile.expected_churn_rate, 2)}</Text>
          <Text size="xs" c="var(--app-text-muted)">risque / mois</Text>
        </Group>
        <Stack gap={2}>
          <Text size="xs" c="var(--app-text-secondary)">
            <b>{formatNumber(profile.n_rows)}</b> clients dans la base · <b>{formatShare(profile.share_of_portfolio, 0)}</b> du portefeuille
          </Text>
          <Text size="xs" c="var(--app-text-secondary)">
            <b>{formatShare(profile.share_high, 0)}</b> de High · <b>{formatShare(profile.share_of_revenue_at_risk, 0)}</b> du revenu en jeu
          </Text>
        </Stack>
        <Stack gap={4} className={classes.traits}>
          {profile.traits.map((t) => (
            <Group key={t.variable} gap={6} wrap="nowrap" align="flex-start">
              {t.direction === "higher" ? (
                <IconArrowUpRight size={14} stroke={2} className={classes.up} style={{ marginTop: 1 }} />
              ) : (
                <IconArrowDownRight size={14} stroke={2} className={classes.down} style={{ marginTop: 1 }} />
              )}
              <Text size="xs" c="var(--app-text-secondary)" lineClamp={2}>
                {t.label} {formatNumber(t.segment_median)} {t.unit}
                <Text span size="xs" c="var(--app-text-muted)"> (médiane {formatNumber(t.overall_median)})</Text>
              </Text>
            </Group>
          ))}
        </Stack>
        {profile.main_action && (
          <Text size="xs" c="var(--app-accent-text)" fw={600} lineClamp={2}>{profile.main_action}</Text>
        )}
      </Stack>
    </UnstyledButton>
  );
}

function ProfilesGrid() {
  const filters = useGlobalFilters();
  const toggle = useToggleFilter();
  const query = useSegmentProfiles(withoutKeys(filters, ["cluster"]));
  const profiles = query.data?.profiles ?? [];
  const selected = filters.cluster;
  const riskiest = profiles[0];
  return (
    <Stack gap="sm">
      <Stack gap={4}>
        <Title order={3} fz={16} fw={600}>
          {riskiest
            ? `Profil le plus risqué : ${riskiest.name.toLowerCase()} (${formatShare(riskiest.expected_churn_rate, 2)} par mois)`
            : "Profils comportementaux (K-means)"}
        </Title>
        <Text size="sm" c="var(--app-text-muted)">
          5 profils appris sans la cible (E4b). Flèches : écart de la médiane du profil à la médiane de la base. Cliquez une carte pour filtrer.
        </Text>
      </Stack>
      {query.error ? (
        <Paper withBorder p="lg"><ErrorState compact message={query.error.message} onRetry={() => void query.refetch()} /></Paper>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 5 }} spacing="md">
          {query.data
            ? profiles.map((p) => (
                <ProfileCard
                  key={p.name}
                  profile={p}
                  selected={selected.includes(p.name)}
                  dimmed={selected.length > 0 && !selected.includes(p.name)}
                  onToggle={() => {
                    toggle("cluster", p.name);
                  }}
                />
              ))
            : Array.from({ length: 5 }, (_, i) => <Skeleton key={i} height={250} radius="lg" />)}
        </SimpleGrid>
      )}
    </Stack>
  );
}

export function SegmentsPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("dim");
  const dimension: SegmentDimension = isSegmentDimension(raw) ? raw : "tenure_band";
  const filters = useGlobalFilters();
  const overall = useKpis(filters);
  const revenue = overall.data?.revenue_at_risk_monthly;
  return (
    <>
      <PageHeader
        eyebrow="Segments et facteurs"
        title={
          overall.data
            ? `${formatMoney(revenue)} de revenu mensuel en jeu dans ce périmètre : où se concentre le risque, et pourquoi`
            : ""
        }
        loading={!overall.data}
        description="Chaque graphique est cliquable : une modalité cliquée devient un filtre global et toute l'application se met à jour."
      />
      <Stack gap="lg">
        <Grid gap="md">
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <Stack gap="sm">
              <SegmentedControl
                size="xs"
                value={dimension}
                onChange={(v) => {
                  const next = new URLSearchParams(params);
                  next.set("dim", v);
                  setParams(next, { replace: true });
                }}
                data={DIMENSIONS}
                fullWidth
                styles={{ root: { background: "var(--app-raised)", border: "1px solid var(--app-border)" } }}
              />
              <SegmentBars dimension={dimension} />
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <RiskHeatmap />
          </Grid.Col>
        </Grid>
        <DriversBlock />
        <ProfilesGrid />
        <Text size="xs" c="var(--app-text-muted)">
          Risques et revenus : estimations au taux de churn supposé de 2 %/mois (hypothèse, pas une donnée). Effectifs « clients dans la base » : lignes réelles du jeu de données.
        </Text>
      </Stack>
    </>
  );
}
