import {
  ActionIcon, Badge, Drawer, Group, Paper, SimpleGrid, Skeleton, Stack, Text, Title,
  Tooltip, useComputedColorScheme,
} from "@mantine/core";
import { useHotkeys } from "@mantine/hooks";
import {
  IconBulb, IconChevronLeft, IconChevronRight, IconUserOff, IconX,
} from "@tabler/icons-react";
import { useMemo } from "react";

import { useCustomer, useCustomerExplanation, useRiskDistribution } from "../../api/queries";
import type { CustomerDetail } from "../../api/types";
import { gaugeOption, waterfallOption, waterfallSteps } from "../../charts/customer";
import { filterValueLabel } from "../../lib/filterLabels";
import { formatMoney, formatNumber, formatPct, formatShare } from "../../lib/format";

/** Valeur d'un champ du profil : région lisible, unités au singulier pour 1. */
function profileValue(variable: string, value: string | number | null, unit: string): string {
  if (value === null) return "—";
  if (typeof value !== "number") return variable === "area" ? filterValueLabel("area", value) : value;
  const digits = Number.isInteger(value) ? 0 : 1;
  const u = Math.abs(value) <= 1 && unit.endsWith("s") && !unit.includes("/") ? unit.slice(0, -1) : unit;
  return `${formatNumber(value, digits)} ${u}`.trim();
}
import { RiskBadge } from "../Badges";
import { AiAssist } from "./AiAssist";
import { EChart } from "../EChart";
import { ErrorState } from "../States";
import classes from "./CustomerDrawer.module.css";

type Factor = CustomerDetail["reasons"][number];

interface CustomerDrawerProps {
  customerId: number | null;
  onClose: () => void;
  onPrev: (() => void) | null;
  onNext: (() => void) | null;
  /** Position dans la liste filtrée (ex. « 3 / 17 472 »). */
  position: string | null;
}

function Section({ title, children, hint }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <Paper p="md" withBorder className={classes.section}>
      <Stack gap="sm">
        <Group justify="space-between" gap="xs" wrap="nowrap">
          <Text fw={650} size="sm">{title}</Text>
          {hint && <Text size="xs" c="var(--app-text-muted)">{hint}</Text>}
        </Group>
        {children}
      </Stack>
    </Paper>
  );
}

function ReasonRow({ factor, index }: { factor: Factor; index: number }) {
  return (
    <Group wrap="nowrap" align="flex-start" gap="sm" className={classes.reason}>
      <span className={classes.rank}>{index + 1}</span>
      <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
        <Text size="sm" fw={600} lh={1.35}>{factor.text ?? factor.label}</Text>
        <Group gap={6}>
          <Badge size="xs" variant="light" color="gray" radius="sm" styles={{ root: { textTransform: "none" } }}>
            {factor.family_label}
          </Badge>
          <Text size="xs" c="var(--app-text-muted)">{factor.effect}, selon le modèle</Text>
        </Group>
      </Stack>
      <Tooltip label="Contribution au score du modèle (log-odds). Plus elle est grande, plus ce facteur pousse le risque.">
        <Text size="sm" fw={650} className={classes.contribution} tabIndex={0}>
          {factor.contribution_log_odds >= 0 ? "+" : ""}{formatNumber(factor.contribution_log_odds, 2)}
        </Text>
      </Tooltip>
    </Group>
  );
}

function ActionCard({ customer }: { customer: CustomerDetail }) {
  const inactive = customer.inactive;
  return (
    <Paper p="md" className={classes.action} data-inactive={inactive || undefined}>
      <Group wrap="nowrap" align="flex-start" gap="md">
        <span className={classes.actionIcon}>{inactive ? <IconUserOff size={20} stroke={1.8} /> : <IconBulb size={20} stroke={1.8} />}</span>
        <Stack gap={4} style={{ flex: 1 }}>
          <Text size="xs" fw={600} tt="uppercase" c="var(--app-text-muted)" style={{ letterSpacing: "0.05em" }}>
            Action suggérée
          </Text>
          <Text fw={700} size="lg" lh={1.25}>{customer.action}</Text>
          <Text size="sm" c="var(--app-text-secondary)">
            {inactive
              ? "Client sans usage : probablement déjà parti. Vérifier la ligne ou tenter une reconquête plutôt qu'une offre de fidélisation."
              : customer.risk_level === "Low"
                ? "Risque faible : pas de campagne ; suivi normal."
                : `Déduite du facteur actionnable dominant (${(customer.reasons[0]?.family_label ?? "aucun").toLowerCase()}). Suggestion, pas garantie d'effet.`}
          </Text>
        </Stack>
      </Group>
      <AiAssist customerId={customer.customer_id} inactive={inactive} />
    </Paper>
  );
}

function DrawerBody({ id }: { id: number }) {
  const scheme = useComputedColorScheme("light");
  const detail = useCustomer(id);
  const explanation = useCustomerExplanation(id, 10);
  const dist = useRiskDistribution({});
  const customer = detail.data;
  const gauge = useMemo(() => {
    if (!customer || !dist.data) return null;
    const thresholds = { medium: dist.data.thresholds.medium_p_real_pct, high: dist.data.thresholds.high_p_real_pct };
    return gaugeOption(100 * customer.scores.p_real, customer.risk_level, thresholds, scheme);
  }, [customer, dist.data, scheme]);
  const waterfall = useMemo(
    () => (explanation.data ? waterfallOption(explanation.data, scheme) : null),
    [explanation.data, scheme],
  );

  if (detail.error) {
    return <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} />;
  }
  if (!customer) {
    return (
      <Stack gap="md">
        <Skeleton height={190} radius="lg" />
        <Skeleton height={150} radius="lg" />
        <Skeleton height={320} radius="lg" />
      </Stack>
    );
  }
  const steps = explanation.data ? waterfallSteps(explanation.data) : [];
  const waterfallHeight = Math.max(260, steps.length * 28 + 50);
  return (
    <Stack gap="md">
      <Paper p="md" withBorder className={classes.section}>
        <Group wrap="nowrap" align="center" gap="md">
          <div style={{ width: 210, flexShrink: 0 }}>
            {gauge ? (
              <EChart option={gauge} height={150} ariaLabel={`Risque mensuel ${formatShare(customer.scores.p_real, 1)} au taux supposé de 2 %.`} />
            ) : (
              <Skeleton height={150} />
            )}
          </div>
          <Stack gap={6} style={{ flex: 1 }}>
            <Text size="xs" fw={600} tt="uppercase" c="var(--app-text-muted)" style={{ letterSpacing: "0.05em" }}>
              Risque de départ sur un mois
            </Text>
            <Text size="sm" c="var(--app-text-secondary)">
              <b>{formatShare(customer.scores.p_real, 1)}</b> au taux de churn supposé de 2 %/mois,
              soit {formatNumber(customer.scores.p_real / 0.02, 1)} fois la moyenne.
            </Text>
            <Text size="xs" c="var(--app-text-muted)">
              Probabilité calibrée sur l'échantillon (50 % de churners) : {formatShare(customer.scores.p_calibrated, 1)}
            </Text>
            <Text size="xs" c="var(--app-text-muted)">
              Facture {formatMoney(customer.monthly_bill, 2)} / mois · revenu en jeu {formatMoney(customer.revenue_at_risk_monthly, 2)} / mois
            </Text>
          </Stack>
        </Group>
      </Paper>

      <ActionCard customer={customer} />

      <Section
        title={customer.risk_level === "Low" ? "Ce qui pèse malgré tout sur son score" : "Pourquoi ce client est à risque"}
        hint="facteurs actionnables, selon le modèle"
      >
        {customer.reasons.length === 0 ? (
          <Text size="sm" c="var(--app-text-muted)">Aucun facteur actionnable n'augmente le risque de ce client.</Text>
        ) : (
          <Stack gap={0}>{customer.reasons.map((f, i) => <ReasonRow key={f.variable} factor={f} index={i} />)}</Stack>
        )}
        {customer.context.length > 0 && (
          <Stack gap={4} className={classes.context}>
            <Text size="xs" fw={600} c="var(--app-text-muted)">Contexte (sans levier direct)</Text>
            {customer.context.map((f) => (
              <Group key={f.variable} justify="space-between" wrap="nowrap" gap="sm">
                <Text size="xs" c="var(--app-text-muted)">{f.text ?? f.label} · {f.effect}</Text>
                <Text size="xs" c="var(--app-text-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {f.contribution_log_odds >= 0 ? "+" : ""}{formatNumber(f.contribution_log_odds, 2)}
                </Text>
              </Group>
            ))}
          </Stack>
        )}
      </Section>

      <Section title="Du score moyen au score du client" hint="contributions SHAP, log-odds">
        {explanation.error ? (
          <ErrorState compact message={explanation.error.message} onRetry={() => void explanation.refetch()} />
        ) : waterfall && explanation.data ? (
          <>
            <EChart option={waterfall} height={waterfallHeight} ariaLabel="Cascade SHAP : contributions des variables, du score moyen du modèle au score du client." />
            <Text size="xs" c="var(--app-text-muted)">
              Rouge : pousse le risque ; bleu : le réduit. Score du client {formatNumber(explanation.data.log_odds, 2)} →
              probabilité du modèle {formatShare(explanation.data.p_raw, 1)} → calibrée {formatShare(customer.scores.p_calibrated, 1)} →
              {" "}{formatPct(100 * customer.scores.p_real, 1)} par mois au taux supposé. Associations apprises, pas des causes.
            </Text>
          </>
        ) : (
          <Skeleton height={300} />
        )}
      </Section>

      <Section title="Profil">
        <SimpleGrid cols={2} spacing="xs" verticalSpacing={6}>
          {customer.profile.map((p) => (
            <Group key={p.variable} justify="space-between" wrap="nowrap" gap="xs" className={classes.profileRow}>
              <Text size="xs" c="var(--app-text-muted)" truncate>{p.label}</Text>
              <Text size="xs" fw={600} style={{ fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                {profileValue(p.variable, p.value, p.unit)}
              </Text>
            </Group>
          ))}
        </SimpleGrid>
        <Text size="xs" c="var(--app-text-muted)">
          Segment : {customer.segment.name} · {customer.bands.tenure_band} · terminal {customer.bands.handset_age_band}
          {" "}· données {customer.partition === "test" ? "de test (modèle final)" : "d'entraînement (score hors fold)"} ·
          départ observé dans l'historique : {customer.historical_churn_label === 1 ? "oui" : "non"} (démonstration).
        </Text>
      </Section>
    </Stack>
  );
}

/**
 * Fiche client en tiroir latéral. Enveloppe vitrée (surface flottante) ; chaque bloc de
 * chiffres ou de graphique est une carte opaque. Précédent / suivant : flèches ← →.
 */
export function CustomerDrawer({ customerId, onClose, onPrev, onNext, position }: CustomerDrawerProps) {
  const detail = useCustomer(customerId);
  useHotkeys([
    ["ArrowLeft", () => onPrev?.()],
    ["ArrowRight", () => onNext?.()],
  ]);
  const customer = detail.data;
  return (
    <Drawer
      opened={customerId !== null}
      onClose={onClose}
      position="right"
      size={620}
      withCloseButton={false}
      padding={0}
      overlayProps={{ backgroundOpacity: 0.18, blur: 1 }}
      transitionProps={{ transition: "slide-left", duration: 220, timingFunction: "cubic-bezier(0.2, 0, 0, 1)" }}
      classNames={{ content: classes.drawer, body: classes.body }}
      aria-label={customerId ? `Fiche du client ${String(customerId)}` : "Fiche client"}
    >
      {customerId !== null && (
        <>
          <div className={classes.header}>
            <Group justify="space-between" wrap="nowrap" gap="sm">
              <Stack gap={4} style={{ minWidth: 0 }}>
                <Text size="xs" fw={600} tt="uppercase" c="var(--app-text-muted)" style={{ letterSpacing: "0.05em" }}>
                  Fiche client{position ? ` · ${position}` : ""}
                </Text>
                <Group gap="sm" wrap="nowrap">
                  <Title order={2} fz={22} fw={700} style={{ fontVariantNumeric: "tabular-nums" }}>{customerId}</Title>
                  {customer && <RiskBadge level={customer.risk_level} long size="md" />}
                </Group>
                {customer && (
                  <Text size="xs" c="var(--app-text-secondary)" truncate>{customer.segment.name}</Text>
                )}
              </Stack>
              <Group gap={4} wrap="nowrap">
                <Tooltip label="Client précédent (←)">
                  <ActionIcon variant="default" size="lg" onClick={() => onPrev?.()} disabled={!onPrev} aria-label="Client précédent">
                    <IconChevronLeft size={18} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Client suivant (→)">
                  <ActionIcon variant="default" size="lg" onClick={() => onNext?.()} disabled={!onNext} aria-label="Client suivant">
                    <IconChevronRight size={18} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Fermer (Échap)">
                  <ActionIcon variant="subtle" size="lg" onClick={onClose} aria-label="Fermer la fiche">
                    <IconX size={18} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          </div>
          <div className={classes.content} tabIndex={-1} data-autofocus style={{ outline: "none" }}>
            <DrawerBody key={customerId} id={customerId} />
          </div>
        </>
      )}
    </Drawer>
  );
}
