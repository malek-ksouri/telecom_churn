import { AppShell } from "@mantine/core";
import { motion, useReducedMotion } from "framer-motion";
import { Outlet, useLocation } from "react-router-dom";

import { ChatPanel } from "../components/chat/ChatPanel";
import { GlobalCustomerDrawer } from "../components/customer/GlobalCustomerDrawer";
import { useFiltersUrlSync } from "../store/filters";
import { useMediaQuery } from "@mantine/hooks";

import { NARROW_QUERY, useNavCollapsed } from "../store/ui";
import { layout, motion as tokens } from "../theme/tokens";
import { Header } from "./Header";
import { Navbar } from "./Navbar";

const HEADER_HEIGHT = 112; // ligne titre (64, alignée sur le logo) + barre de filtres (48)

/**
 * Coquille de l'application. Transition de page : fondu + léger glissement vertical
 * (200 ms) pour signaler le changement de contexte ; simple fondu si mouvement réduit.
 */
export function AppLayout() {
  useFiltersUrlSync();
  const narrow = useMediaQuery(NARROW_QUERY);
  const collapsed = useNavCollapsed(narrow);
  const { pathname } = useLocation();
  const reduce = useReducedMotion();

  return (
    <AppShell
      header={{ height: HEADER_HEIGHT }}
      navbar={{ width: collapsed ? layout.navbarCollapsed : layout.navbarWidth, breakpoint: "sm" }}
      layout="alt"
      padding={0}
      transitionDuration={200}
      transitionTimingFunction="cubic-bezier(0.2, 0, 0, 1)"
      styles={{
        navbar: { borderColor: "var(--app-border)", background: "var(--app-surface)" },
        header: { background: "transparent", border: "none" },
        main: { background: "var(--app-page)" },
      }}
    >
      <AppShell.Header>
        <Header />
      </AppShell.Header>
      <AppShell.Navbar>
        <Navbar />
      </AppShell.Navbar>
      <AppShell.Main>
        <motion.div
          key={pathname}
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: tokens.duration.base, ease: tokens.ease.enter }}
          style={{ padding: "24px 32px 48px", maxWidth: layout.contentMaxWidth, margin: "0 auto" }}
        >
          <Outlet />
        </motion.div>
      </AppShell.Main>
      <ChatPanel />
      <GlobalCustomerDrawer />
    </AppShell>
  );
}
