import {
  ActionIcon, Badge, Divider, Group, Skeleton, Stack, Text, Tooltip,
  useComputedColorScheme, useMantineColorScheme,
} from "@mantine/core";
import { IconFilter, IconMoon, IconSun } from "@tabler/icons-react";
import { useLocation } from "react-router-dom";

import { useAssistantStatus, useFilterOptions } from "../api/queries";
import { GLOBAL_FILTER_KEYS } from "../api/types";
import { ActiveFilterChips } from "../components/ActiveFilterChips";
import { HypothesisBadge } from "../components/Badges";
import { FilterMenu } from "../components/FilterMenu";
import classes from "./Header.module.css";
import { findNavItem } from "./navigation";

function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme("light");
  const next = scheme === "dark" ? "light" : "dark";
  const label = next === "dark" ? "Passer en thème sombre" : "Passer en thème clair";
  return (
    <Tooltip label={label}>
      <ActionIcon
        variant="default"
        size="lg"
        aria-label={label}
        onClick={() => {
          setColorScheme(next);
        }}
      >
        {scheme === "dark" ? <IconSun size={18} stroke={1.7} /> : <IconMoon size={18} stroke={1.7} />}
      </ActionIcon>
    </Tooltip>
  );
}

function AssistantStatusBadge() {
  const { data, isLoading, isError } = useAssistantStatus();
  if (isLoading) return <Skeleton height={22} width={120} radius="sm" />;
  const live = data?.live_llm === true;
  const label = isError || !data ? "Assistant indisponible" : live ? "Assistant : Gemini" : "Assistant : démo";
  let tooltip = "Le statut de l'assistant n'a pas pu être lu.";
  if (data && !isError) {
    tooltip = live
      ? `Modèle ${data.model} : réponses générées à partir des outils, chiffres vérifiés.`
      : `Mode démonstration : réponses préparées à partir des vrais outils. ${data.demo_reason ?? ""}`;
  }
  return (
    <Tooltip label={tooltip} maw={300}>
      <Badge
        tabIndex={0}
        variant="dot"
        color={isError ? "red" : live ? "accent" : "gray"}
        size="md"
        radius="sm"
        styles={{
          root: {
            textTransform: "none", fontWeight: 500, letterSpacing: 0, cursor: "help",
            borderColor: "var(--app-border-strong)", color: "var(--app-text-secondary)",
            background: "transparent",
          },
        }}
      >
        {label}
      </Badge>
    </Tooltip>
  );
}

/**
 * En-tête flottant (surface vitrée : le contenu défile dessous) : titre de la page, filtres
 * globaux avec leurs puces, hypothèse de taux réel, état de l'assistant, thème.
 */
export function Header() {
  const { pathname } = useLocation();
  const current = findNavItem(pathname);
  const options = useFilterOptions();

  return (
    <Stack gap={0} h="100%" className={classes.header}>
      <Group h={64} px="lg" justify="space-between" wrap="nowrap" gap="md">
        <Stack gap={0} style={{ minWidth: 0 }}>
          <Group gap={6} wrap="nowrap">
            <Text size="xs" c="var(--app-text-muted)" fw={500}>{current?.group.label ?? ""}</Text>
            <Text size="xs" c="var(--app-text-muted)">/</Text>
            <Text size="sm" fw={600} truncate>{current?.item.label ?? ""}</Text>
          </Group>
          <Text size="xs" c="var(--app-text-muted)" truncate visibleFrom="md">{current?.item.purpose ?? ""}</Text>
        </Stack>
        <Group gap="sm" wrap="nowrap">
          <HypothesisBadge />
          <AssistantStatusBadge />
          <Divider orientation="vertical" color="var(--app-border)" />
          <ThemeToggle />
        </Group>
      </Group>
      <Group h={48} px="lg" gap="sm" wrap="nowrap" className={classes.filters}>
        <Group gap={6} wrap="nowrap" c="var(--app-text-muted)">
          <IconFilter size={15} stroke={1.8} />
          <Text size="xs" fw={600} tt="uppercase" style={{ letterSpacing: "0.05em" }}>Filtres</Text>
        </Group>
        {options.isLoading ? (
          <Group gap={8}>{GLOBAL_FILTER_KEYS.map((k) => <Skeleton key={k} height={30} width={96} />)}</Group>
        ) : (
          <Group gap={8} wrap="nowrap">
            {GLOBAL_FILTER_KEYS.map((key) => {
              const dim = options.data?.dimensions.find((d) => d.dimension === key);
              return <FilterMenu key={key} dimension={key} values={dim?.values ?? []} />;
            })}
          </Group>
        )}
        <Divider orientation="vertical" color="var(--app-border)" />
        <div className={classes.chips}>
          <ActiveFilterChips />
        </div>
      </Group>
    </Stack>
  );
}
