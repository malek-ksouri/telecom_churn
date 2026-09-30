import { Paper } from "@mantine/core";
import { IconTools } from "@tabler/icons-react";
import { useLocation } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/States";
import { findNavItem } from "../layout/navigation";

/** Page prévue mais pas encore construite (l'étape qui la livre est indiquée). */
export function PlaceholderPage({ step }: { step: string }) {
  const { pathname } = useLocation();
  const current = findNavItem(pathname);
  return (
    <>
      <PageHeader title={current?.item.label ?? "Page"} description={current?.item.purpose} />
      <Paper withBorder p="xl" style={{ background: "var(--app-surface)" }}>
        <EmptyState
          icon={<IconTools size={22} stroke={1.6} />}
          title="Page en construction"
          description={`Cette page est livrée à l'étape ${step}. Les filtres globaux et le thème s'y appliqueront automatiquement.`}
        />
      </Paper>
    </>
  );
}
