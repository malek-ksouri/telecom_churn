import {
  Alert, Badge, Grid, Group, NumberInput, Paper, SimpleGrid, Skeleton, Slider, Stack, Switch, Text,
  Title, useComputedColorScheme,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import {
  IconAdjustments, IconArrowsExchange, IconCash, IconPhoneCheck, IconPigMoney, IconReceipt,
  IconScale, IconTarget, IconUserOff, IconUsersGroup,
} from "@tabler/icons-react";
import { useMemo, useState } from "react";

import { type CampaignParams, useCampaign } from "../api/queries";
import { balanceOption, gainOption } from "../charts/options";
import { ChartCard } from "../components/ChartCard";
import { EChart } from "../components/EChart";
import { KpiCard } from "../components/KpiCard";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, SkeletonKpiRow } from "../components/States";
import { formatMoney, formatNumber, formatPct, formatShare } from "../lib/format";
import { activeFilterCount, useGlobalFilters } from "../store/filters";
import classes from "./SimulatorPage.module.css";

interface Hypotheses {
  capacity: number;
  successPct: number;
  withCost: boolean;
  cost: number;
  horizon: number;
}

const DEFAULTS: Hypotheses = { capacity: 10, successPct: 20, withCost: false, cost: 5, horizon: 12 };

function SliderField({
  label, help, value, onChange, min, max, step, format, marks,
}: {
  label: string; help: string; value: number; onChange: (v: number) => void;
  min: number; max: number; step: number; format: (v: number) => string;
  marks: { value: number; label: string }[];
}) {
  return (
    <Stack gap={6}>
      <Group justify="space-between" wrap="nowrap">
        <Text size="sm" fw={600}>{label}</Text>
        <Text size="sm" fw={650} c="var(--app-accent-text)" style={{ fontVariantNumeric: "tabular-nums" }}>
          {format(value)}
        </Text>
      </Group>
      <Slider
        value={value}
        onChange={onChange}
        min={min}
        max={max}
        step={step}
        marks={marks}
        label={format}
        thumbLabel={label}
        size="sm"
        mb="md"
        styles={{ markLabel: { fontSize: 11, color: "var(--app-text-muted)" } }}
      />
      <Text size="xs" c="var(--app-text-muted)">{help}</Text>
    </Stack>
  );
}

function HypothesesPanel({ value, onChange }: { value: Hypotheses; onChange: (v: Hypotheses) => void }) {
  const set = <K extends keyof Hypotheses>(k: K, v: Hypotheses[K]) => {
    onChange({ ...value, [k]: v });
  };
  return (
    <Paper p="lg" withBorder className={classes.panel}>
      <Stack gap="lg">
        <Group gap={10}>
          <span className={classes.panelIcon}><IconAdjustments size={16} stroke={1.8} /></span>
          <Stack gap={0}>
            <Title order={3} fz={16} fw={650}>Hypothèses</Title>
            <Text size="xs" c="var(--app-text-muted)">Choix de campagne et hypothèses non mesurées</Text>
          </Stack>
        </Group>
        <SliderField
          label="Capacité de contact"
          help="Part du périmètre contactée, par risque décroissant (clients actifs)."
          value={value.capacity}
          onChange={(v) => { set("capacity", v); }}
          min={1}
          max={50}
          step={1}
          format={(v) => formatPct(v, 0)}
          marks={[{ value: 10, label: "10 %" }, { value: 25, label: "25 %" }, { value: 50, label: "50 %" }]}
        />
        <SliderField
          label="Taux de succès de l'offre"
          help="Part des churners contactés que l'offre retient. Inconnu : à mesurer par un groupe témoin."
          value={value.successPct}
          onChange={(v) => { set("successPct", v); }}
          min={0}
          max={50}
          step={1}
          format={(v) => formatPct(v, 0)}
          marks={[{ value: 0, label: "0 %" }, { value: 25, label: "25 %" }, { value: 50, label: "50 %" }]}
        />
        <SliderField
          label="Horizon de revenu"
          help="Nombre de mois de facture conservés par un client retenu."
          value={value.horizon}
          onChange={(v) => { set("horizon", v); }}
          min={1}
          max={24}
          step={1}
          format={(v) => `${formatNumber(v)} mois`}
          marks={[{ value: 1, label: "1" }, { value: 12, label: "12" }, { value: 24, label: "24" }]}
        />
        <Stack gap={8}>
          <Switch
            checked={value.withCost}
            onChange={(e) => { set("withCost", e.currentTarget.checked); }}
            label="Saisir un coût par contact"
            description="Sans coût saisi, aucun coût ni solde n'est calculé."
            size="sm"
          />
          {value.withCost && (
            <NumberInput
              value={value.cost}
              onChange={(v) => { set("cost", typeof v === "number" ? Math.max(0, v) : 0); }}
              min={0}
              max={500}
              step={0.5}
              decimalScale={2}
              decimalSeparator=","
              thousandSeparator=" "
              suffix=" $"
              aria-label="Coût par contact"
              size="sm"
            />
          )}
        </Stack>
        <Alert variant="light" color="gray" radius="md" p="sm" styles={{ root: { background: "var(--app-raised)", border: "1px dashed var(--app-border-strong)" }, message: { fontSize: 12, color: "var(--app-text-secondary)" } }}>
          Taux de succès, horizon et coût sont des <b>hypothèses</b> : les chiffres qui en dépendent
          (cadres pointillés) ne sont pas des résultats du modèle.
        </Alert>
      </Stack>
    </Paper>
  );
}

export function SimulatorPage() {
  const filters = useGlobalFilters();
  const scheme = useComputedColorScheme("light");
  const [hyp, setHyp] = useState<Hypotheses>(DEFAULTS);
  // Les curseurs restent fluides ; l'API n'est appelée qu'une fois le geste posé (150 ms).
  const [debounced] = useDebouncedValue(hyp, 150);
  const params: CampaignParams = {
    capacity_pct: debounced.capacity,
    success_rate: debounced.successPct / 100,
    offer_cost: debounced.withCost ? debounced.cost : null,
    revenue_horizon_months: debounced.horizon,
  };
  const query = useCampaign(params, filters);
  const data = query.data;
  const res = data?.result;
  const filtered = activeFilterCount(filters) > 0;
  const scope = filtered ? "du périmètre filtré" : "du portefeuille";

  const capacity = debounced.capacity;
  const hasCost = debounced.withCost;
  const gain = useMemo(() => (data ? gainOption(data.curve, capacity, scheme) : null), [data, capacity, scheme]);
  const balance = useMemo(
    () => (data && hasCost ? balanceOption(data.curve, capacity, scheme) : null),
    [data, capacity, hasCost, scheme],
  );

  const conclusion = res
    ? `Avec ces hypothèses, cibler ${formatPct(res.capacity_pct, 0)} ${scope} atteint ${formatNumber(res.expected_churners)} churners, ${formatNumber(res.lift_vs_random, 1)} fois plus qu'au hasard.`
    : "";
  const followUp = res && params.success_rate > 0
    ? `Si l'offre retient ${formatPct(params.success_rate * 100, 0)} d'entre eux (hypothèse) : environ ${formatNumber(res.avoided_departures_hypothesis)} départs évités et ${formatMoney(res.preserved_revenue_horizon_hypothesis)} préservés sur ${formatNumber(params.revenue_horizon_months)} mois${res.net_balance !== null ? `, pour un solde de ${formatMoney(res.net_balance)}` : ""}.`
    : "Avec un taux de succès nul, aucun départ n'est évité : le modèle identifie les clients, l'offre doit les retenir.";
  const stale = query.isFetching;

  return (
    <>
      <PageHeader
        eyebrow="Simulateur de campagne"
        title={conclusion}
        loading={!res}
        description={res ? followUp : undefined}
      />
      <Grid gap="lg" align="flex-start">
        <Grid.Col span={{ base: 12, lg: 4 }} className={classes.sticky}>
          <HypothesesPanel value={hyp} onChange={setHyp} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          {query.error ? (
            <Paper withBorder p="xl" style={{ background: "var(--app-surface)" }}>
              <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
            </Paper>
          ) : (
            <Stack gap="lg" style={{ opacity: stale && !query.isLoading ? 0.85 : 1, transition: "opacity 140ms" }}>
              {!data || !res ? (
                <SkeletonKpiRow count={4} />
              ) : (
                <>
                  <Stack gap={8}>
                    <Group gap={8}>
                      <Badge variant="light" color="accent" radius="sm" styles={{ root: { textTransform: "none" } }}>Résultats du modèle</Badge>
                      <Text size="xs" c="var(--app-text-muted)">estimation portefeuille, taux de churn supposé 2 %/mois</Text>
                    </Group>
                    <SimpleGrid cols={{ base: 1, sm: 2, xl: 4 }} spacing="md">
                      <KpiCard compact label="Clients ciblés" value={res.targeted_n_portfolio_equiv} format={(v) => formatNumber(v)} nature="portfolio"
                        icon={<IconUsersGroup size={16} stroke={1.8} />}
                        detail={<><b>{formatNumber(res.targeted_n_rows)}</b> clients dans la base</>}
                        definition="Clients actifs contactés, par risque décroissant, jusqu'à la capacité choisie (estimation pour un portefeuille réel)." />
                      <KpiCard compact emphasis label="Churners atteints" value={res.expected_churners} format={(v) => formatNumber(v)} nature="portfolio"
                        icon={<IconTarget size={16} stroke={1.8} />}
                        detail={<>contre <b>{formatNumber(res.random_churners)}</b> au hasard</>}
                        definition="Futurs churners parmi les clients ciblés, selon les probabilités du modèle au taux réel supposé. Atteints ne veut pas dire retenus." />
                      <KpiCard compact label="Facteur" value={res.lift_vs_random ?? undefined} format={(v) => `× ${formatNumber(v, 2)}`} nature="model"
                        icon={<IconArrowsExchange size={16} stroke={1.8} />}
                        detail={<>vs hasard · <b>{formatNumber(res.churners_per_1000_contacted, 0)}</b> pour 1 000 contacts</>}
                        definition="Churners atteints divisés par ceux qu'un ciblage au hasard du même nombre de clients atteindrait." />
                      <KpiCard compact label="Revenu en jeu" value={res.revenue_at_risk_monthly} format={(v) => formatMoney(v)} nature="portfolio"
                        icon={<IconCash size={16} stroke={1.8} />}
                        detail={<>par mois · <b>{formatShare(res.share_of_revenue_at_risk, 0)}</b> du total</>}
                        definition="Revenu mensuel qu'on s'attend à perdre chez les clients ciblés si rien n'est fait." />
                    </SimpleGrid>
                  </Stack>
                  <Stack gap={8}>
                    <Group gap={8}>
                      <Badge variant="outline" color="gray" radius="sm" styles={{ root: { textTransform: "none", borderStyle: "dashed" } }}>Selon vos hypothèses</Badge>
                      <Text size="xs" c="var(--app-text-muted)">taux de succès {formatPct(params.success_rate * 100, 0)}, horizon {formatNumber(params.revenue_horizon_months)} mois{params.offer_cost !== null ? `, coût ${formatMoney(params.offer_cost, 2)} par contact` : ""}</Text>
                    </Group>
                    <SimpleGrid cols={{ base: 1, sm: 2, xl: 4 }} spacing="md">
                      <KpiCard compact label="Départs évités" value={res.avoided_departures_hypothesis} format={(v) => formatNumber(v)} nature="hypothesis"
                        icon={<IconPhoneCheck size={16} stroke={1.8} />}
                        detail="churners atteints × taux de succès"
                        definition="Dépend entièrement du taux de succès supposé. À mesurer avec un groupe témoin avant tout engagement." />
                      <KpiCard compact label="Revenu préservé" value={res.preserved_revenue_horizon_hypothesis} format={(v) => formatMoney(v)} nature="hypothesis"
                        icon={<IconPigMoney size={16} stroke={1.8} />}
                        detail={<>sur {formatNumber(params.revenue_horizon_months)} mois ({formatMoney(res.preserved_revenue_monthly_hypothesis)} / mois)</>}
                        definition="Revenu en jeu × taux de succès × horizon. Hypothèse : un client retenu garde sa facture pendant l'horizon." />
                      <KpiCard compact label="Coût" value={res.campaign_cost ?? undefined} format={(v) => formatMoney(v)} nature="hypothesis"
                        icon={<IconReceipt size={16} stroke={1.8} />}
                        detail={res.campaign_cost === null ? "saisissez un coût par contact" : "coût par contact × clients ciblés"}
                        definition="Calculé seulement si un coût par contact est saisi ; aucun coût n'est supposé par défaut." />
                      <KpiCard compact label="Solde" value={res.net_balance ?? undefined} format={(v) => formatMoney(v)} nature="hypothesis"
                        icon={<IconScale size={16} stroke={1.8} />}
                        detail={res.net_balance === null ? "nécessite un coût" : res.net_balance >= 0 ? "revenu préservé > coût" : "coût > revenu préservé"}
                        definition="Revenu préservé sur l'horizon − coût. Dépend de trois hypothèses : succès, horizon et coût." />
                    </SimpleGrid>
                  </Stack>
                </>
              )}

              <ChartCard
                title={res ? `Au-delà de ${formatPct(res.capacity_pct, 0)}, chaque contact supplémentaire atteint moins de churners` : "Courbe de gain"}
                subtitle="Churners atteints selon la capacité (1 à 50 %), ciblage par le modèle contre ciblage au hasard. Point : capacité choisie."
                height={280}
                loading={!data}
              >
                {gain && <EChart option={gain} height={280} ariaLabel="Courbe de gain : churners atteints selon la capacité, modèle contre hasard." />}
              </ChartCard>

              {params.offer_cost !== null && (
                <ChartCard
                  title={(() => {
                    const curve = data?.curve ?? [];
                    const best = curve.reduce<typeof curve[number] | undefined>((a, b) => (!a || (b.net_balance ?? -Infinity) > (a.net_balance ?? -Infinity) ? b : a), undefined);
                    return best?.net_balance !== null && best?.net_balance !== undefined
                      ? `Avec ces hypothèses, le solde est maximal vers ${formatPct(best.capacity_pct, 0)} de capacité (${formatMoney(best.net_balance)})`
                      : "Solde selon la capacité";
                  })()}
                  subtitle="Revenu préservé sur l'horizon − coût, selon la capacité. Entièrement dépendant des hypothèses saisies."
                  height={220}
                  loading={!data}
                >
                  {balance && <EChart option={balance} height={220} ariaLabel="Solde de la campagne selon la capacité, sous les hypothèses saisies." />}
                </ChartCard>
              )}

              {data ? (
                <Paper p="lg" withBorder className={classes.inactive}>
                  <Group gap="md" wrap="nowrap" align="flex-start">
                    <span className={classes.inactiveIcon}><IconUserOff size={18} stroke={1.8} /></span>
                    <Stack gap={4}>
                      <Text fw={650} size="sm">Inactifs : vérifier la ligne ou reconquérir, hors campagne de fidélisation</Text>
                      <Text size="sm" c="var(--app-text-secondary)">
                        <b>{formatNumber(data.inactive.n_rows)}</b> clients dans la base (≈ <b>{formatNumber(data.inactive.n_portfolio_equiv)}</b> en estimation portefeuille),
                        {" "}<b>{formatNumber(data.inactive.expected_churners)}</b> départs attendus et <b>{formatMoney(data.inactive.revenue_at_risk_monthly)}</b> de revenu mensuel en jeu.
                        {" "}Sans aucune minute d'appel, ils sont probablement déjà partis : une offre de fidélisation serait mal ciblée.
                      </Text>
                    </Stack>
                  </Group>
                </Paper>
              ) : (
                <Skeleton height={96} radius="lg" />
              )}
            </Stack>
          )}
        </Grid.Col>
      </Grid>
    </>
  );
}
