import { ActionIcon, Badge, Drawer, Group, Stack, Text, Tooltip } from "@mantine/core";
import { IconArrowsMaximize, IconMessageChatbot, IconX } from "@tabler/icons-react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAssistantStatus } from "../../api/queries";
import { useChatStore } from "../../store/chat";
import classes from "./Chat.module.css";
import { ChatThread } from "./ChatThread";

/** Badge du fournisseur actif : Gemini (modèle réel) ou mode démonstration. */
export function ProviderBadge() {
  const { data, isError } = useAssistantStatus();
  if (isError) return <Badge size="sm" color="red" variant="light" radius="sm">Indisponible</Badge>;
  if (!data) return null;
  return (
    <Tooltip label={data.live_llm ? `Modèle ${data.model}` : `Mode démonstration : ${data.demo_reason ?? "réponses préparées à partir des vrais outils"}`} maw={300} multiline>
      <Badge size="sm" variant="dot" color={data.live_llm ? "accent" : "gray"} radius="sm"
        styles={{ root: { textTransform: "none", fontWeight: 500, cursor: "help" } }} tabIndex={0}>
        {data.live_llm ? "Gemini" : "Démo"}
      </Badge>
    </Tooltip>
  );
}

/** Bouton d'en-tête qui ouvre le panneau de chat (masqué sur la page Assistant). */
export function ChatPanelButton() {
  const setOpen = useChatStore((s) => s.setPanelOpen);
  const busy = useChatStore((s) => s.busy);
  const { pathname } = useLocation();
  if (pathname.startsWith("/operations/assistant")) return null;
  return (
    <Tooltip label="Ouvrir l'assistant (même conversation sur toutes les pages)">
      <ActionIcon variant="default" size="lg" onClick={() => { setOpen(true); }} aria-label="Ouvrir l'assistant" pos="relative">
        <IconMessageChatbot size={18} stroke={1.7} />
        {busy && <span aria-hidden style={{ position: "absolute", top: 5, right: 5, width: 7, height: 7, borderRadius: 4, background: "var(--app-accent)" }} />}
      </ActionIcon>
    </Tooltip>
  );
}

/** Panneau latéral de chat : surface flottante vitrée, conversation partagée avec la page Assistant. */
export function ChatPanel() {
  const open = useChatStore((s) => s.panelOpen);
  const setOpen = useChatStore((s) => s.setPanelOpen);
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  return (
    <Drawer
      opened={open && !pathname.startsWith("/operations/assistant")}
      onClose={() => { setOpen(false); }}
      position="right"
      size={460}
      withCloseButton={false}
      padding={0}
      overlayProps={{ backgroundOpacity: 0.12, blur: 1 }}
      transitionProps={{ transition: "slide-left", duration: 220, timingFunction: "cubic-bezier(0.2, 0, 0, 1)" }}
      classNames={{ content: classes.panel, body: classes.panelBody }}
      aria-label="Assistant"
    >
      <Stack gap={0} h="100%">
        <Group justify="space-between" className={classes.panelHeader} wrap="nowrap">
          <Group gap={10} wrap="nowrap">
            <IconMessageChatbot size={20} stroke={1.7} color="var(--app-accent-text)" />
            <Stack gap={0}>
              <Text fw={650} size="sm">Assistant</Text>
              <Text size="xs" c="var(--app-text-muted)">Chiffres issus des outils, vérifiés</Text>
            </Stack>
            <ProviderBadge />
          </Group>
          <Group gap={4} wrap="nowrap">
            <Tooltip label="Ouvrir en pleine page">
              <ActionIcon variant="subtle" size="lg" aria-label="Ouvrir l'assistant en pleine page"
                onClick={() => { setOpen(false); void navigate({ pathname: "/operations/assistant", search }); }}>
                <IconArrowsMaximize size={17} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Fermer (Échap)">
              <ActionIcon variant="subtle" size="lg" onClick={() => { setOpen(false); }} aria-label="Fermer l'assistant">
                <IconX size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
        <ChatThread compact height="calc(100vh - 66px)" />
      </Stack>
    </Drawer>
  );
}
