import { MantineProvider, localStorageColorSchemeManager } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { type ReactNode, Suspense, lazy } from "react";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { queryClient } from "./api/queries";
import { AppLayout } from "./layout/AppLayout";
import { PageSkeleton } from "./components/States";
import { cssVariablesResolver, mantineTheme } from "./theme/mantineTheme";

// Pages chargées à la demande : chaque page (et ses graphiques) est un fichier séparé.
const OverviewPage = lazy(() => import("./pages/OverviewPage").then((m) => ({ default: m.OverviewPage })));
const SegmentsPage = lazy(() => import("./pages/SegmentsPage").then((m) => ({ default: m.SegmentsPage })));
const SimulatorPage = lazy(() => import("./pages/SimulatorPage").then((m) => ({ default: m.SimulatorPage })));
const AssistantPage = lazy(() => import("./pages/AssistantPage").then((m) => ({ default: m.AssistantPage })));
const CustomersPage = lazy(() => import("./pages/CustomersPage").then((m) => ({ default: m.CustomersPage })));

const page = (element: ReactNode) => <Suspense fallback={<PageSkeleton />}>{element}</Suspense>;

const colorSchemeManager = localStorageColorSchemeManager({ key: "churn-color-scheme" });

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/pilotage/vue-ensemble" replace /> },
      { path: "pilotage/vue-ensemble", element: page(<OverviewPage />) },
      { path: "pilotage/segments", element: page(<SegmentsPage />) },
      { path: "pilotage/simulateur", element: page(<SimulatorPage />) },
      { path: "operations/clients", element: page(<CustomersPage />) },
      { path: "operations/assistant", element: page(<AssistantPage />) },
      { path: "*", element: <Navigate to="/pilotage/vue-ensemble" replace /> },
    ],
  },
]);

export function App() {
  return (
    <MantineProvider
      theme={mantineTheme}
      cssVariablesResolver={cssVariablesResolver}
      colorSchemeManager={colorSchemeManager}
      defaultColorScheme="auto"
    >
      <MotionConfig reducedMotion="user">
        <QueryClientProvider client={queryClient}>
          <Notifications position="bottom-right" />
          <RouterProvider router={router} />
        </QueryClientProvider>
      </MotionConfig>
    </MantineProvider>
  );
}
