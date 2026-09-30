import { Group, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  /** Ce que la page permet de décider, en une phrase. */
  description?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <Group justify="space-between" align="flex-end" wrap="wrap" gap="md" mb="lg">
      <Stack gap={4}>
        <Title order={1} fz={26} fw={650} lh={1.2} style={{ letterSpacing: "-0.015em" }}>
          {title}
        </Title>
        {description && (
          <Text size="sm" c="var(--app-text-secondary)" maw={760}>
            {description}
          </Text>
        )}
      </Stack>
      {actions}
    </Group>
  );
}
