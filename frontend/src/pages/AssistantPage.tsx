import { Alert, Grid, Group, List, Paper, Stack, Text, Title } from "@mantine/core";
import { IconInfoCircle, IconShieldCheck } from "@tabler/icons-react";

import { useAssistantStatus } from "../api/queries";
import { ChatThread } from "../components/chat/ChatThread";
import { ProviderBadge } from "../components/chat/ChatPanel";
import { PageHeader } from "../components/PageHeader";

const capitalize = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

function StatusCard() {
  const { data, isError } = useAssistantStatus();
  return (
    <Paper p="lg" withBorder style={{ background: "var(--app-surface)", boxShadow: "var(--app-shadow-card)" }}>
      <Stack gap="sm">
        <Group justify="space-between">
          <Title order={3} fz={15} fw={650}>Fournisseur</Title>
          <ProviderBadge />
        </Group>
        {isError ? (
          <Text size="sm" c="var(--app-danger)">Statut indisponible : l'API ne répond pas.</Text>
        ) : data ? (
          <>
            <Text size="sm" c="var(--app-text-secondary)">
              {data.live_llm
                ? `Modèle ${data.model}. En cas de quota dépassé, de clé invalide ou de délai dépassé, la réponse bascule automatiquement en mode démonstration, avec un message.`
                : `${capitalize(data.demo_reason ?? "mode démonstration")}. Les réponses sont préparées pour le scénario de soutenance ; tous les chiffres viennent des vrais outils.`}
            </Text>
            {data.last_error && (
              <Alert variant="light" color="yellow" p="xs" radius="md" styles={{ message: { fontSize: 12 } }}>
                Dernière erreur du fournisseur : {data.last_error}
              </Alert>
            )}
          </>
        ) : null}
      </Stack>
    </Paper>
  );
}

function RulesCard() {
  return (
    <Paper p="lg" withBorder style={{ background: "var(--app-surface)", boxShadow: "var(--app-shadow-card)" }}>
      <Stack gap="sm">
        <Group gap={8}>
          <IconShieldCheck size={18} stroke={1.8} color="var(--app-accent-text)" />
          <Title order={3} fz={15} fw={650}>Garde-fous</Title>
        </Group>
        <List size="sm" spacing={6} c="var(--app-text-secondary)">
          <List.Item>Chiffres issus des outils uniquement, vérifiés après coup (avertissement sinon).</List.Item>
          <List.Item>Effectifs précisés : clients dans la base ou estimation portefeuille (taux supposé 2 %).</List.Item>
          <List.Item>Explications « selon le modèle » : associations, pas des causes.</List.Item>
          <List.Item>Départs évités seulement avec un taux de succès présenté comme hypothèse.</List.Item>
          <List.Item>Aucune variable socio-démographique sensible.</List.Item>
        </List>
        <Group gap={6} wrap="nowrap" align="flex-start">
          <IconInfoCircle size={14} stroke={1.8} color="var(--app-text-muted)" style={{ flexShrink: 0, marginTop: 2 }} />
          <Text size="xs" c="var(--app-text-muted)">
            Un identifiant client cité dans une réponse est cliquable : il ouvre sa fiche.
          </Text>
        </Group>
      </Stack>
    </Paper>
  );
}

export function AssistantPage() {
  return (
    <>
      <PageHeader
        eyebrow="Assistant"
        title="Posez vos questions sur le portefeuille, réponses chiffrées et vérifiées"
        description="L'assistant interroge les mêmes services que le tableau de bord. La conversation est partagée avec le panneau accessible depuis toutes les pages."
      />
      <Grid gap="lg" align="flex-start">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Paper withBorder style={{ background: "var(--app-page)", overflow: "hidden", boxShadow: "var(--app-shadow-card)" }}>
            <ChatThread height="calc(100vh - 290px)" />
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap="md">
            <StatusCard />
            <RulesCard />
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  );
}
