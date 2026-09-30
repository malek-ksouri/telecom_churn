import {
  Badge, Button, Checkbox, Divider, Group, Popover, ScrollArea, Stack, Text, TextInput,
} from "@mantine/core";
import { IconChevronDown, IconSearch } from "@tabler/icons-react";
import { useMemo, useState } from "react";

import type { GlobalFilterKey } from "../api/types";
import { useFiltersStore, useGlobalFilters } from "../store/filters";
import { formatNumber } from "../lib/format";
import { FILTER_LABELS, filterValueLabel } from "../lib/filterLabels";

interface FilterMenuProps {
  dimension: GlobalFilterKey;
  values: { value: string; n_rows: number }[];
}

/**
 * Filtre compact : un bouton (« Niveau · 2 ») qui ouvre une liste à cocher avec, pour chaque
 * modalité, son nombre de clients dans la base. Recherche au-delà de 8 modalités.
 */
export function FilterMenu({ dimension, values }: FilterMenuProps) {
  const selected = useGlobalFilters()[dimension];
  const set = useFiltersStore((s) => s.set);
  const [query, setQuery] = useState("");
  const searchable = values.length > 8;
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? values.filter((v) => filterValueLabel(dimension, v.value).toLowerCase().includes(q)) : values;
  }, [values, query, dimension]);

  return (
    <Popover
      width={300}
      position="bottom-start"
      shadow="md"
      radius="md"
      transitionProps={{ transition: "pop-top-left", duration: 140 }}
      onClose={() => {
        setQuery("");
      }}
    >
      <Popover.Target>
        <Button
          size="xs"
          variant={selected.length ? "light" : "default"}
          color={selected.length ? "accent" : "gray"}
          rightSection={<IconChevronDown size={14} stroke={1.8} />}
          styles={{ root: { fontWeight: 500 } }}
        >
          <Group gap={6} wrap="nowrap">
            {FILTER_LABELS[dimension]}
            {selected.length > 0 && (
              <Badge size="xs" circle variant="filled" color="accent">
                {selected.length}
              </Badge>
            )}
          </Group>
        </Button>
      </Popover.Target>
      <Popover.Dropdown p={0} style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
        <Stack gap={0}>
          <Group justify="space-between" px="sm" py={8}>
            <Text size="xs" fw={600} c="var(--app-text-muted)" tt="uppercase" style={{ letterSpacing: "0.04em" }}>
              {FILTER_LABELS[dimension]}
            </Text>
            {selected.length > 0 && (
              <Button
                size="compact-xs"
                variant="subtle"
                color="gray"
                onClick={() => {
                  set(dimension, []);
                }}
              >
                Effacer
              </Button>
            )}
          </Group>
          {searchable && (
            <TextInput
              px="sm"
              pb={8}
              size="xs"
              placeholder="Rechercher"
              leftSection={<IconSearch size={14} />}
              value={query}
              onChange={(e) => {
                setQuery(e.currentTarget.value);
              }}
              data-autofocus
            />
          )}
          <Divider color="var(--app-border)" />
          <ScrollArea.Autosize mah={300} type="auto" offsetScrollbars>
            <Checkbox.Group
              value={selected}
              onChange={(v) => {
                set(dimension, v);
              }}
            >
              <Stack gap={2} p={6}>
                {visible.map((v) => (
                  <Checkbox.Card
                    key={v.value}
                    value={v.value}
                    radius="sm"
                    withBorder={false}
                    px={8}
                    py={6}
                    style={{ background: "transparent" }}
                  >
                    <Group wrap="nowrap" gap={10} justify="space-between">
                      <Group wrap="nowrap" gap={10}>
                        <Checkbox.Indicator size="xs" />
                        <Text size="sm" lineClamp={1}>
                          {filterValueLabel(dimension, v.value)}
                        </Text>
                      </Group>
                      <Text size="xs" c="var(--app-text-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
                        {formatNumber(v.n_rows)}
                      </Text>
                    </Group>
                  </Checkbox.Card>
                ))}
                {visible.length === 0 && (
                  <Text size="sm" c="var(--app-text-muted)" p="sm">
                    Aucune valeur ne correspond.
                  </Text>
                )}
              </Stack>
            </Checkbox.Group>
          </ScrollArea.Autosize>
          <Divider color="var(--app-border)" />
          <Text size="xs" c="var(--app-text-muted)" px="sm" py={8}>
            Nombres : clients dans la base
          </Text>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}
