import { ActionIcon, Alert, Badge, Button, CopyButton, Group, Paper, Skeleton, Stack, Text, Tooltip } from "@mantine/core";
import { IconAlertTriangle, IconCheck, IconCopy, IconMessage2, IconSparkles } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";

import { explainCustomerAi, retentionMessageAi } from "../../api/chat";
import classes from "./AiAssist.module.css";

function ProviderTag({ provider }: { provider: string }) {
  return (
    <Badge size="xs" variant="outline" color="gray" radius="sm" styles={{ root: { textTransform: "none", fontWeight: 500 } }}>
      {provider === "demo" ? "Mode démonstration" : "Gemini"}
    </Badge>
  );
}

function Copy({ value, label }: { value: string; label: string }) {
  return (
    <CopyButton value={value} timeout={1600}>
      {({ copied, copy }) => (
        <Tooltip label={copied ? "Copié" : label} withArrow>
          <ActionIcon variant="subtle" color={copied ? "accent" : "gray"} size="sm" onClick={copy} aria-label={label}>
            {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
          </ActionIcon>
        </Tooltip>
      )}
    </CopyButton>
  );
}

function Warnings({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <Stack gap={4}>
      {warnings.map((w) => (
        <Alert key={w} variant="light" color="orange" radius="md" p="xs" icon={<IconAlertTriangle size={14} />} styles={{ message: { fontSize: 12 } }}>
          {w}
        </Alert>
      ))}
    </Stack>
  );
}

/**
 * Boutons IA de la fiche client : explication en langage clair et messages de rétention
 * (SMS + email copiables). Les textes viennent de l'API (assistant ou mode démonstration).
 */
export function AiAssist({ customerId, inactive }: { customerId: number; inactive: boolean }) {
  const explain = useMutation({ mutationFn: () => explainCustomerAi(customerId) });
  const offer = useMutation({ mutationFn: () => retentionMessageAi(customerId) });
  return (
    <Stack gap="sm" mt="md">
      <Group gap="xs">
        <Button size="xs" variant="light" leftSection={<IconSparkles size={14} />} loading={explain.isPending}
          onClick={() => { explain.mutate(); }}>
          {explain.data ? "Réexpliquer" : "Expliquer"}
        </Button>
        <Button size="xs" variant="default" leftSection={<IconMessage2 size={14} />} loading={offer.isPending}
          onClick={() => { offer.mutate(); }}>
          {inactive ? "Rédiger un message de vérification" : offer.data ? "Réécrire l'offre" : "Rédiger une offre"}
        </Button>
      </Group>

      {explain.isPending && <Skeleton height={64} radius="md" />}
      {explain.error && (
        <Alert variant="light" color="red" radius="md" p="xs" styles={{ message: { fontSize: 12 } }}>
          {explain.error.message}
        </Alert>
      )}
      {explain.data && (
        <Paper p="sm" radius="md" className={classes.result}>
          <Group justify="space-between" mb={6} wrap="nowrap">
            <Text size="xs" fw={650} tt="uppercase" c="var(--app-text-muted)" style={{ letterSpacing: "0.05em" }}>Explication pour le conseiller</Text>
            <Group gap={4} wrap="nowrap">
              <ProviderTag provider={explain.data.provider} />
              <Copy value={explain.data.text} label="Copier l'explication" />
            </Group>
          </Group>
          <Text size="sm" lh={1.55}>{explain.data.text}</Text>
          <Warnings warnings={explain.data.warnings} />
        </Paper>
      )}

      {offer.isPending && <Skeleton height={140} radius="md" />}
      {offer.error && (
        <Alert variant="light" color="red" radius="md" p="xs" styles={{ message: { fontSize: 12 } }}>
          {offer.error.message}
        </Alert>
      )}
      {offer.data && (
        <Paper p="sm" radius="md" className={classes.result}>
          <Group justify="space-between" mb={8} wrap="nowrap">
            <Text size="xs" fw={650} tt="uppercase" c="var(--app-text-muted)" style={{ letterSpacing: "0.05em" }}>Messages de rétention</Text>
            <ProviderTag provider={offer.data.provider} />
          </Group>
          <Stack gap="sm">
            <div className={classes.message}>
              <Group justify="space-between" wrap="nowrap" mb={4}>
                <Text size="xs" fw={600}>SMS</Text>
                <Group gap={6} wrap="nowrap">
                  <Text size="xs" c={offer.data.sms_length > 300 ? "var(--app-danger)" : "var(--app-text-muted)"} style={{ fontVariantNumeric: "tabular-nums" }}>
                    {offer.data.sms_length} / 300 caractères
                  </Text>
                  <Copy value={offer.data.sms} label="Copier le SMS" />
                </Group>
              </Group>
              <Text size="sm" lh={1.5}>{offer.data.sms}</Text>
            </div>
            <div className={classes.message}>
              <Group justify="space-between" wrap="nowrap" mb={4}>
                <Text size="xs" fw={600}>Email · {offer.data.email_subject}</Text>
                <Copy value={`${offer.data.email_subject}\n\n${offer.data.email_body}`} label="Copier l'email (objet et corps)" />
              </Group>
              <Text size="sm" lh={1.5} style={{ whiteSpace: "pre-line" }}>{offer.data.email_body}</Text>
            </div>
            <Text size="xs" c="var(--app-text-muted)">
              Aucune promesse chiffrée : le conseiller précise l'offre. Adaptés à l'action « {offer.data.action} ».
            </Text>
            <Warnings warnings={offer.data.warnings} />
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
