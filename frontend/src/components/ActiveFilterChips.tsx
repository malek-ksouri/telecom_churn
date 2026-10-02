import { Button, CloseButton, Group, Text } from "@mantine/core";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { GLOBAL_FILTER_KEYS } from "../api/types";
import { FILTER_LABELS, filterValueLabel } from "../lib/filterLabels";
import { activeFilterCount, useFiltersStore, useGlobalFilters } from "../store/filters";
import { motion as tokens } from "../theme/tokens";
import classes from "./ActiveFilterChips.module.css";

/** Puces des filtres actifs, chacune supprimable ; « Tout effacer » au-delà d'un filtre. */
export function ActiveFilterChips() {
  const filters = useGlobalFilters();
  const remove = useFiltersStore((s) => s.remove);
  const reset = useFiltersStore((s) => s.reset);
  const reduce = useReducedMotion();
  const count = activeFilterCount(filters);

  if (count === 0) {
    return (
      <Text size="xs" c="var(--app-text-muted)" visibleFrom="md" style={{ whiteSpace: "nowrap" }}>
        Aucun filtre : portefeuille entier
      </Text>
    );
  }
  return (
    <Group gap={6} wrap="nowrap">
      <AnimatePresence initial={false}>
        {GLOBAL_FILTER_KEYS.flatMap((key) =>
          filters[key].map((value) => (
            <motion.span
              key={`${key}:${value}`}
              layout={!reduce}
              initial={reduce ? false : { opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.92 }}
              transition={{ duration: tokens.duration.fast, ease: tokens.ease.standard }}
              className={classes.chip}
            >
              <span className={classes.key}>{FILTER_LABELS[key]}</span>
              <span className={classes.value}>{filterValueLabel(key, value)}</span>
              <CloseButton
                size={18}
                iconSize={12}
                aria-label={`Retirer le filtre ${FILTER_LABELS[key]} : ${value}`}
                onClick={() => {
                  remove(key, value);
                }}
                className={classes.close}
              />
            </motion.span>
          )),
        )}
      </AnimatePresence>
      {count > 1 && (
        <Button variant="subtle" color="gray" size="compact-xs" onClick={reset}>
          Tout effacer
        </Button>
      )}
    </Group>
  );
}
