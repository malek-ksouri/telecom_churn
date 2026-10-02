import { Group, Skeleton, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";

interface PageHeaderProps {
  /** Nom de la page (sur-titre). */
  eyebrow?: string;
  /** Titre = la conclusion à retenir, calculée sur le périmètre filtré. */
  title: ReactNode;
  /** Ce que la page permet de décider, en une phrase. */
  description?: ReactNode;
  actions?: ReactNode;
  loading?: boolean;
}

export function PageHeader({ eyebrow, title, description, actions, loading = false }: PageHeaderProps) {
  return (
    <Group justify="space-between" align="flex-end" wrap="wrap" gap="md" mb="lg">
      <Stack gap={6} style={{ minWidth: 0, flex: 1 }}>
        {eyebrow && (
          <Text size="xs" fw={600} tt="uppercase" c="var(--app-accent-text)" style={{ letterSpacing: "0.06em" }}>
            {eyebrow}
          </Text>
        )}
        {loading ? (
          <Skeleton height={30} width="55%" />
        ) : (
          <Title order={1} fz={24} fw={650} lh={1.25} style={{ letterSpacing: "-0.015em", textWrap: "balance" }}>
            {title}
          </Title>
        )}
        {description && (
          <Text size="sm" c="var(--app-text-secondary)" maw={820}>
            {description}
          </Text>
        )}
      </Stack>
      {actions}
    </Group>
  );
}
