import { MantineProvider, localStorageColorSchemeManager } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { queryClient } from "./api/queries";
import { AppLayout } from "./layout/AppLayout";
import { OverviewPage } from "./pages/OverviewPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { cssVariablesResolver, mantineTheme } from "./theme/mantineTheme";

const colorSchemeManager = localStorageColorSchemeManager({ key: "churn-color-scheme" });

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/pilotage/vue-ensemble" replace /> },
      { path: "pilotage/vue-ensemble", element: <OverviewPage /> },
      { path: "pilotage/segments", element: <PlaceholderPage step="E15" /> },
      { path: "pilotage/simulateur", element: <PlaceholderPage step="E15" /> },
      { path: "operations/clients", element: <PlaceholderPage step="E15" /> },
      { path: "operations/assistant", element: <PlaceholderPage step="E17" /> },
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
