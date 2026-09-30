import { Group, Paper, Skeleton, Stack, Text, Tooltip } from "@mantine/core";
import { IconInfoCircle } from "@tabler/icons-react";
import type { ReactNode } from "react";

import { AnimatedNumber } from "./AnimatedNumber";
import classes from "./KpiCard.module.css";

/** Nature de l'effectif affiché : lignes réelles ou estimation au taux supposé. */
export type CountNature = "base" | "portfolio" | "model" | "none";

const NATURE_LABEL: Record<CountNature, string> = {
  base: "clients dans la base",
  portfolio: "estimation portefeuille",
  model: "mesure du modèle",
  none: "",
};

interface KpiCardProps {
  label: string;
  value: number | null | undefined;
  format: (value: number) => string;
  /** Précise ce que compte le chiffre (obligatoire pour un effectif). */
  nature: CountNature;
  /** Complément sous la valeur (comparaison, contexte). */
  detail?: ReactNode;
  /** Définition affichée dans l'infobulle. */
  definition: string;
  icon?: ReactNode;
  loading?: boolean;
  /** Mise en avant (KPI principal de la page). */
  emphasis?: boolean;
}

export function KpiCard({
  label, value, format, nature, detail, definition, icon, loading = false, emphasis = false,
}: KpiCardProps) {
  return (
    <Paper className={classes.card} data-emphasis={emphasis || undefined} p="lg" withBorder>
      <Stack gap={6}>
        <Group justify="space-between" wrap="nowrap" gap="xs">
          <Group gap={8} wrap="nowrap">
            {icon && <span className={classes.icon}>{icon}</span>}
            <Text size="sm" fw={500} c="var(--app-text-secondary)" lineClamp={2}>
              {label}
            </Text>
          </Group>
          <Tooltip label={definition} position="top-end">
            <span className={classes.info} tabIndex={0} aria-label={`Définition : ${label}`}>
              <IconInfoCircle size={16} stroke={1.6} />
            </span>
          </Tooltip>
        </Group>
        {loading || value === null || value === undefined ? (
          <Skeleton height={34} width="60%" my={2} />
        ) : (
          <Text className={classes.value} component="div">
            <AnimatedNumber value={value} format={format} />
          </Text>
        )}
        {nature !== "none" && (
          <Text size="xs" c="var(--app-text-muted)" className={classes.nature}>
            {NATURE_LABEL[nature]}
          </Text>
        )}
        {detail !== undefined &&
          (loading ? (
            <Skeleton height={12} width="80%" />
          ) : (
            <Text size="sm" c="var(--app-text-secondary)" component="div">
              {detail}
            </Text>
          ))}
      </Stack>
    </Paper>
  );
}
