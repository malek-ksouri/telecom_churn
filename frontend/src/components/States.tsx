import { Button, Group, Paper, SimpleGrid, Skeleton, Stack, Text, ThemeIcon } from "@mantine/core";
import { IconAlertTriangle, IconInbox, IconRefresh } from "@tabler/icons-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}

/** Aucun résultat : dit pourquoi et, si possible, comment en sortir. */
export function EmptyState({ title, description, icon, action, compact = false }: EmptyStateProps) {
  return (
    <Stack align="center" justify="center" gap={compact ? 6 : 10} py={compact ? "md" : "xl"} ta="center">
      <ThemeIcon size={compact ? 36 : 44} radius="xl" variant="light" color="gray">
        {icon ?? <IconInbox size={compact ? 18 : 22} stroke={1.6} />}
      </ThemeIcon>
      <Text fw={600} size={compact ? "sm" : "md"}>{title}</Text>
      {description && (
        <Text size="sm" c="var(--app-text-muted)" maw={420}>{description}</Text>
      )}
      {action}
    </Stack>
  );
}

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  compact?: boolean;
}

/** Erreur de chargement, avec un bouton Réessayer. */
export function ErrorState({ message, onRetry, compact = false }: ErrorStateProps) {
  return (
    <EmptyState
      compact={compact}
      icon={<IconAlertTriangle size={compact ? 18 : 22} stroke={1.6} color="var(--app-danger)" />}
      title="Impossible de charger ces données"
      description={message ?? "Une erreur est survenue."}
      action={
        onRetry && (
          <Button size="xs" variant="light" leftSection={<IconRefresh size={14} />} onClick={onRetry}>
            Réessayer
          </Button>
        )
      }
    />
  );
}

/** Rangée de cartes KPI en cours de chargement. */
export function SkeletonKpiRow({ count = 4 }: { count?: number }) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, lg: count }} spacing="md">
      {Array.from({ length: count }, (_, i) => (
        <Paper key={i} p="lg" withBorder style={{ background: "var(--app-surface)" }}>
          <Stack gap={10}>
            <Group justify="space-between">
              <Skeleton height={14} width="55%" />
              <Skeleton height={14} width={14} circle />
            </Group>
            <Skeleton height={32} width="60%" />
            <Skeleton height={10} width="45%" />
            <Skeleton height={12} width="80%" />
          </Stack>
        </Paper>
      ))}
    </SimpleGrid>
  );
}
