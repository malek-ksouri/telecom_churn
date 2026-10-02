import { Alert, Badge, Button, Code, Collapse, Group, Loader, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconAlertTriangle, IconChevronDown, IconRefresh, IconTool } from "@tabler/icons-react";
import { memo, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { formatNumber } from "../../lib/format";
import type { Message } from "../../store/chat";
import { useOpenCustomer } from "../../store/customerNav";
import classes from "./Chat.module.css";

const TOOL_LABELS: Record<string, string> = {
  get_kpis: "Indicateurs du portefeuille",
  get_customer: "Fiche client",
  explain_customer: "Contributions SHAP d'un client",
  list_at_risk: "Clients à risque",
  segment_stats: "Statistiques par segment",
  global_drivers: "Facteurs de risque",
  simulate_campaign: "Simulation de campagne",
  explain_method: "Explication de méthode",
};

/** Identifiants clients (7 chiffres) -> liens qui ouvrent la fiche. */
function linkCustomers(markdown: string): string {
  return markdown.replace(/(?<![\w/#[-])(1\d{6})(?![\w\]])/g, "[$1](#client-$1)");
}

function useMarkdownComponents(): Components {
  const openCustomer = useOpenCustomer();
  return {
    a: ({ href, children }) => {
      if (href?.startsWith("#client-")) {
        const id = Number(href.slice(8));
        return (
          <UnstyledButton
            component="span"
            className={classes.clientLink}
            onClick={() => { openCustomer(id); }}
            role="link"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter") openCustomer(id); }}
            aria-label={`Ouvrir la fiche du client ${String(id)}`}
          >
            {children}
          </UnstyledButton>
        );
      }
      return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
    },
  };
}

function ToolsUsed({ message }: { message: Message }) {
  const [open, setOpen] = useState(false);
  if (!message.tools.length) return null;
  const total = message.tools.reduce((n, t) => n + (t.durationMs ?? 0), 0);
  return (
    <div className={classes.tools}>
      <UnstyledButton onClick={() => { setOpen((o) => !o); }} className={classes.toolsToggle} aria-expanded={open}>
        <Group gap={6} wrap="nowrap">
          <IconTool size={13} stroke={1.8} />
          <Text size="xs" fw={600}>
            Outils utilisés · {message.tools.length}
          </Text>
          <Text size="xs" c="var(--app-text-muted)">{formatNumber(total)} ms</Text>
          <IconChevronDown size={13} className={classes.chevron} data-open={open || undefined} />
        </Group>
      </UnstyledButton>
      <Collapse expanded={open} transitionDuration={160}>
        <Stack gap={6} mt={8}>
          {message.tools.map((t, i) => (
            <div key={`${t.name}-${String(i)}`} className={classes.toolRow}>
              <Group justify="space-between" wrap="nowrap" gap="xs">
                <Text size="xs" fw={600}>{TOOL_LABELS[t.name] ?? t.name} <Text span size="xs" c="var(--app-text-muted)" ff="monospace">{t.name}</Text></Text>
                <Text size="xs" c={t.ok === false ? "var(--app-danger)" : "var(--app-text-muted)"} style={{ whiteSpace: "nowrap" }}>
                  {t.durationMs === null ? <Loader size={10} /> : `${formatNumber(t.durationMs)} ms`}{t.ok === false ? " · erreur" : ""}
                </Text>
              </Group>
              {Object.keys(t.args).length > 0 && (
                <Code block className={classes.toolArgs}>{JSON.stringify(t.args)}</Code>
              )}
            </div>
          ))}
        </Stack>
      </Collapse>
    </div>
  );
}

interface MessageViewProps {
  message: Message;
  onRetry?: (question: string) => void;
}

/** Une bulle de la conversation (mémorisée : seule la réponse en cours se re-rend pendant le streaming). */
export const MessageView = memo(function MessageView({ message, onRetry }: MessageViewProps) {
  const components = useMarkdownComponents();
  if (message.role === "user") {
    return <div className={classes.user}>{message.content}</div>;
  }
  const streaming = message.status === "streaming";
  return (
    <div className={classes.assistant} aria-live={streaming ? "polite" : undefined} aria-busy={streaming}>
      {message.notice && (
        <Alert variant="light" color="yellow" radius="md" p="xs" mb={8} icon={<IconAlertTriangle size={16} />}
          styles={{ message: { fontSize: 12 } }}>
          {message.notice}
        </Alert>
      )}
      {message.content ? (
        <div className={classes.markdown}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {linkCustomers(message.content)}
          </ReactMarkdown>
        </div>
      ) : streaming ? (
        <Group gap={8} c="var(--app-text-muted)">
          <Loader size={14} type="dots" />
          <Text size="sm">{message.tools.length ? "Consultation des outils…" : "Réflexion…"}</Text>
        </Group>
      ) : null}
      {message.status === "error" && (
        <Alert variant="light" color="red" radius="md" p="xs" mt={8} icon={<IconAlertTriangle size={16} />}>
          <Group justify="space-between" gap="xs" wrap="nowrap">
            <Text size="xs">{message.error}</Text>
            {onRetry && message.question && (
              <Button size="compact-xs" variant="subtle" color="red" leftSection={<IconRefresh size={12} />}
                onClick={() => { onRetry(message.question ?? ""); }}>
                Réessayer
              </Button>
            )}
          </Group>
        </Alert>
      )}
      {message.warnings.length > 0 && (
        <Stack gap={4} mt={8}>
          {message.warnings.map((w) => (
            <Alert key={w} variant="light" color="orange" radius="md" p="xs" icon={<IconAlertTriangle size={14} />}
              styles={{ message: { fontSize: 12 } }}>
              {w}
            </Alert>
          ))}
        </Stack>
      )}
      {(message.tools.length > 0 || message.provider) && (
        <Group gap={8} mt={10} justify="space-between" wrap="wrap">
          <ToolsUsed message={message} />
          {message.provider && (
            <Badge size="xs" variant="outline" color="gray" radius="sm" styles={{ root: { textTransform: "none", fontWeight: 500 } }}>
              {message.provider === "demo" ? "Mode démonstration" : "Gemini"}
            </Badge>
          )}
        </Group>
      )}
    </div>
  );
});
