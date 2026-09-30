import { Badge, Group, List, Paper, Skeleton, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";

import { useSummary } from "../api/queries";
import { ErrorState } from "./States";

/** Rend le gras Markdown (**texte**) produit par l'assistant, sans interpréter de HTML. */
function withBold(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <b key={i}>{part.slice(2, -2)}</b> : part,
  );
}

/** Résumé exécutif « Ce qu'il faut retenir » (API /summary, mis en cache côté serveur). */
export function SummaryCard({ scopeNote = false }: { scopeNote?: boolean }) {
  const { data, isLoading, error, refetch } = useSummary();
  return (
    <Paper p="lg" withBorder h="100%" style={{ background: "var(--app-surface)", boxShadow: "var(--app-shadow-card)" }}>
      <Stack gap="sm">
        <Group justify="space-between" wrap="nowrap">
          <Title order={3} fz={16} fw={600}>
            {data?.title ?? "Ce qu'il faut retenir"}
          </Title>
          {data && (
            <Badge variant="light" color="gray" size="sm" radius="sm" styles={{ root: { textTransform: "none", fontWeight: 500 } }}>
              {data.provider === "demo" ? "Rédigé à partir des outils (démo)" : `Rédigé par ${data.model}`}
            </Badge>
          )}
        </Group>
        {scopeNote && (
          <Text size="xs" c="var(--app-text-muted)" mt={-4}>
            Portefeuille entier : ce résumé ne tient pas compte des filtres.
          </Text>
        )}
        {error ? (
          <ErrorState compact message={error.message} onRetry={() => void refetch()} />
        ) : isLoading || !data ? (
          <Stack gap={10}>
            {[90, 80, 85, 70].map((w) => <Skeleton key={w} height={12} width={`${String(w)}%`} />)}
          </Stack>
        ) : (
          <List spacing={8} size="sm" c="var(--app-text-secondary)" styles={{ itemWrapper: { alignItems: "flex-start" } }}>
            {data.bullets.map((b) => (
              <List.Item key={b}>{withBold(b)}</List.Item>
            ))}
          </List>
        )}
        {data && data.warnings.length > 0 && (
          <Text size="xs" c="var(--app-danger)">{data.warnings.join(" ")}</Text>
        )}
      </Stack>
    </Paper>
  );
}
