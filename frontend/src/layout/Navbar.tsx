import { ActionIcon, Group, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import {
  IconLayoutSidebarLeftCollapse, IconLayoutSidebarLeftExpand,
} from "@tabler/icons-react";
import { NavLink as RouterLink, useLocation } from "react-router-dom";

import { useMediaQuery } from "@mantine/hooks";

import { NARROW_QUERY, useNavCollapsed, useUiStore } from "../store/ui";
import classes from "./Navbar.module.css";
import { NAV_GROUPS } from "./navigation";

/** Barre latérale : 2 groupes (Pilotage, Opérations), repliable en icônes seules. */
export function Navbar() {
  const narrow = useMediaQuery(NARROW_QUERY);
  const collapsed = useNavCollapsed(narrow);
  const toggle = useUiStore((s) => s.toggleNav);
  const { search } = useLocation(); // les filtres suivent la navigation entre pages

  return (
    <Stack h="100%" gap={0} className={classes.root}>
      <Group h={64} px={collapsed ? 0 : "md"} justify={collapsed ? "center" : "flex-start"} gap={10} wrap="nowrap" className={classes.brand}>
        <span className={classes.logo} aria-hidden>
          <svg viewBox="0 0 32 32" width="28" height="28">
            <rect width="32" height="32" rx="8" fill="currentColor" />
            <path d="M8 21.5 13.5 15l4 3.5L24 10" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        {!collapsed && (
          <Stack gap={0}>
            <Text fw={650} size="sm" lh={1.2}>Rétention</Text>
            <Text size="xs" c="var(--app-text-muted)" lh={1.2}>Pilotage du churn</Text>
          </Stack>
        )}
      </Group>

      <Stack gap="lg" px={collapsed ? 12 : "sm"} py="md" style={{ flex: 1 }} component="nav" aria-label="Navigation principale">
        {NAV_GROUPS.map((group) => (
          <Stack key={group.label} gap={2}>
            {collapsed ? (
              <div className={classes.groupRule} aria-hidden />
            ) : (
              <Text className={classes.groupLabel}>{group.label}</Text>
            )}
            {group.items.map((item) => {
              const Icon = item.icon;
              const link = (
                <UnstyledButton
                  key={item.path}
                  component={RouterLink}
                  to={{ pathname: item.path, search }}
                  className={classes.link}
                  data-collapsed={collapsed || undefined}
                  aria-label={collapsed ? item.label : undefined}
                >
                  <Icon size={19} stroke={1.7} className={classes.linkIcon} />
                  {!collapsed && <span className={classes.linkLabel}>{item.label}</span>}
                </UnstyledButton>
              );
              return collapsed ? (
                <Tooltip key={item.path} label={`${item.label} — ${item.purpose}`} position="right" withArrow>
                  {link}
                </Tooltip>
              ) : (
                link
              );
            })}
          </Stack>
        ))}
      </Stack>

      {!narrow && (
      <Group p="sm" justify={collapsed ? "center" : "flex-end"} className={classes.footer}>
        <Tooltip label={collapsed ? "Déplier la barre latérale" : "Replier la barre latérale"} position="right">
          <ActionIcon onClick={toggle} size="lg" aria-label={collapsed ? "Déplier la barre latérale" : "Replier la barre latérale"}>
            {collapsed ? <IconLayoutSidebarLeftExpand size={18} stroke={1.7} /> : <IconLayoutSidebarLeftCollapse size={18} stroke={1.7} />}
          </ActionIcon>
        </Tooltip>
      </Group>
      )}
    </Stack>
  );
}
