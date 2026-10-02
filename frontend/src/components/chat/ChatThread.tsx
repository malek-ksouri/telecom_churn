import { ActionIcon, Button, Group, ScrollArea, SimpleGrid, Stack, Text, Textarea, Tooltip, UnstyledButton } from "@mantine/core";
import { IconArrowUp, IconPlayerStopFilled, IconReload } from "@tabler/icons-react";
import { useEffect, useRef, useState } from "react";

import { SUGGESTIONS } from "../../lib/chatSuggestions";
import { useChatStore } from "../../store/chat";
import classes from "./Chat.module.css";
import { MessageView } from "./MessageView";

interface ChatThreadProps {
  /** Version compacte (panneau latéral) : suggestions en liste, moins de marges. */
  compact?: boolean;
  height: string;
}

/** Conversation partagée : messages, suggestions et zone de saisie. */
export function ChatThread({ compact = false, height }: ChatThreadProps) {
  const messages = useChatStore((s) => s.messages);
  const busy = useChatStore((s) => s.busy);
  const send = useChatStore((s) => s.send);
  const stop = useChatStore((s) => s.stop);
  const reset = useChatStore((s) => s.reset);
  const [draft, setDraft] = useState("");
  const viewport = useRef<HTMLDivElement>(null);

  // Défilement automatique vers la dernière réponse (pendant le streaming aussi).
  const last = messages[messages.length - 1];
  useEffect(() => {
    viewport.current?.scrollTo({ top: viewport.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, last?.content, last?.status]);

  const submit = (text: string) => {
    if (!text.trim() || busy) return;
    setDraft("");
    void send(text);
  };

  return (
    <Stack gap={0} h={height} className={classes.thread}>
      <ScrollArea viewportRef={viewport} style={{ flex: 1 }} type="auto" offsetScrollbars>
        <Stack gap="md" p={compact ? "md" : "lg"}>
          {messages.length === 0 ? (
            <Stack gap="md" py={compact ? "xs" : "lg"}>
              <Stack gap={4}>
                <Text fw={650} size={compact ? "md" : "lg"}>Posez une question sur le portefeuille</Text>
                <Text size="sm" c="var(--app-text-muted)">
                  Les réponses s'appuient uniquement sur les outils (indicateurs, clients, segments, simulateur) ;
                  chaque chiffre est vérifié. Les explications décrivent le modèle, pas des causes.
                </Text>
              </Stack>
              <SimpleGrid cols={compact ? 1 : { base: 1, sm: 2 }} spacing="sm">
                {SUGGESTIONS.map(({ icon: Icon, text }) => (
                  <UnstyledButton key={text} className={classes.suggestion} onClick={() => { submit(text); }} disabled={busy}>
                    <Group gap={10} wrap="nowrap" align="flex-start">
                      <span className={classes.suggestionIcon}><Icon size={16} stroke={1.8} /></span>
                      <Text size="sm" fw={500} lh={1.35}>{text}</Text>
                    </Group>
                  </UnstyledButton>
                ))}
              </SimpleGrid>
            </Stack>
          ) : (
            messages.map((m) => <MessageView key={m.id} message={m} onRetry={submit} />)
          )}
        </Stack>
      </ScrollArea>

      <div className={classes.composer}>
        <Group gap="xs" align="flex-end" wrap="nowrap">
          <Textarea
            style={{ flex: 1 }}
            autosize
            minRows={1}
            maxRows={5}
            maxLength={2000}
            radius="md"
            placeholder="Votre question (Entrée pour envoyer, Maj+Entrée pour aller à la ligne)"
            value={draft}
            onChange={(e) => { setDraft(e.currentTarget.value); }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(draft);
              }
            }}
            aria-label="Question à l'assistant"
          />
          {busy ? (
            <Tooltip label="Interrompre la réponse">
              <ActionIcon size={36} variant="default" onClick={stop} aria-label="Interrompre la réponse">
                <IconPlayerStopFilled size={14} />
              </ActionIcon>
            </Tooltip>
          ) : (
            <Tooltip label="Envoyer">
              <ActionIcon size={36} variant="filled" color="accent" onClick={() => { submit(draft); }} disabled={!draft.trim()} aria-label="Envoyer la question">
                <IconArrowUp size={18} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>
        <Group justify="space-between" mt={6}>
          <Text size="xs" c="var(--app-text-muted)">5 appels d'outils au plus par question · 10 derniers messages gardés</Text>
          {messages.length > 0 && (
            <Button size="compact-xs" variant="subtle" color="gray" leftSection={<IconReload size={12} />} onClick={reset}>
              Nouvelle conversation
            </Button>
          )}
        </Group>
      </div>
    </Stack>
  );
}
