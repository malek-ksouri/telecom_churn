import { Group, Paper, Skeleton, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";

import { ErrorState, EmptyState } from "./States";

interface ChartCardProps {
  /** Titre = la conclusion à retenir (« Les High portent 25 % des départs »), pas « Graphique X ». */
  title: string;
  subtitle?: ReactNode;
  /** Actions à droite du titre (bascule, export). */
  actions?: ReactNode;
  /** Hauteur de la zone graphique (réservée aussi pendant le chargement : pas de saut). */
  height: number;
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  empty?: boolean;
  emptyMessage?: string;
  footer?: ReactNode;
  children?: ReactNode;
}

export function ChartCard({
  title, subtitle, actions, height, loading = false, error = null, onRetry, empty = false,
  emptyMessage, footer, children,
}: ChartCardProps) {
  let body: ReactNode;
  if (error) body = <ErrorState compact message={error.message} {...(onRetry ? { onRetry } : {})} />;
  else if (loading) body = <Skeleton height={height} radius="md" />;
  else if (empty)
    body = (
      <EmptyState
        compact
        title="Aucune donnée pour ces filtres"
        description={emptyMessage ?? "Élargissez les filtres pour afficher ce graphique."}
      />
    );
  else body = children;

  return (
    <Paper p="lg" withBorder style={{ background: "var(--app-surface)", boxShadow: "var(--app-shadow-card)" }}>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
          <Stack gap={4}>
            <Title order={3} fz={16} fw={600} lh={1.35}>
              {title}
            </Title>
            {subtitle && (
              <Text size="sm" c="var(--app-text-muted)">
                {subtitle}
              </Text>
            )}
          </Stack>
          {actions}
        </Group>
        <div style={{ minHeight: height, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          {body}
        </div>
        {footer && !loading && !error && (
          <Text size="xs" c="var(--app-text-muted)">
            {footer}
          </Text>
        )}
      </Stack>
    </Paper>
  );
}
