import { Badge, Group, Text, Tooltip } from "@mantine/core";
import { IconInfoCircle } from "@tabler/icons-react";

import { type RiskLevel, riskLabel } from "../theme/tokens";

interface RiskBadgeProps {
  level: RiskLevel;
  /** Libellé long (« Risque élevé ») au lieu du nom du niveau. */
  long?: boolean;
  size?: "xs" | "sm" | "md";
}

/**
 * Niveau de risque : pastille de couleur + libellé (la couleur ne porte jamais seule
 * l'information, règle issue de la validation de palette).
 */
export function RiskBadge({ level, long = false, size = "sm" }: RiskBadgeProps) {
  const key = level.toLowerCase();
  return (
    <Badge
      size={size}
      radius="sm"
      variant="light"
      styles={{
        root: {
          background: `var(--risk-${key}-soft)`,
          color: `var(--risk-${key}-text)`,
          textTransform: "none",
          fontWeight: 600,
          letterSpacing: 0,
          paddingInline: 8,
        },
      }}
      leftSection={
        <span
          aria-hidden
          style={{
            width: 8, height: 8, borderRadius: 2, display: "inline-block",
            background: `var(--risk-${key})`,
          }}
        />
      }
    >
      {long ? riskLabel[level] : level}
    </Badge>
  );
}

/** Rappel permanent de l'hypothèse de taux réel, avec son explication. */
export function HypothesisBadge() {
  return (
    <Tooltip
      position="bottom"
      maw={340}
      label={
        <>
          <Text size="sm" fw={600} mb={4}>
            Hypothèse de travail
          </Text>
          <Text size="sm">
            Le jeu de données contient environ 50 % de churners. Les probabilités et les
            effectifs « estimation portefeuille » sont ramenés à un taux de churn réel supposé
            de 2 % par mois (sensibilité testée de 1 à 3 %). Ce taux n'est pas issu des
            données ; il ne change pas le classement des clients.
          </Text>
        </>
      }
    >
      <Badge
        variant="outline"
        color="gray"
        radius="sm"
        size="md"
        tabIndex={0}
        styles={{
          root: {
            textTransform: "none", fontWeight: 500, letterSpacing: 0, cursor: "help",
            borderColor: "var(--app-border-strong)", color: "var(--app-text-secondary)",
            background: "transparent",
          },
        }}
        rightSection={<IconInfoCircle size={13} stroke={1.8} />}
      >
        <Group gap={4} wrap="nowrap">
          Hypothèse : taux réel 2 %/mois
        </Group>
      </Badge>
    </Tooltip>
  );
}
