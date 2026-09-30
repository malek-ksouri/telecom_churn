import {
  IconAdjustmentsHorizontal, IconChartDonut3, IconLayoutDashboard, IconMessageChatbot, IconUsers,
  type Icon,
} from "@tabler/icons-react";

export interface NavItem {
  path: string;
  label: string;
  /** Question à laquelle la page répond (infobulle en mode replié, sous-titre d'en-tête). */
  purpose: string;
  icon: Icon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Pilotage",
    items: [
      { path: "/pilotage/vue-ensemble", label: "Vue d'ensemble", purpose: "Où en est le portefeuille ?", icon: IconLayoutDashboard },
      { path: "/pilotage/segments", label: "Segments et facteurs", purpose: "Où se concentre le risque, et pourquoi ?", icon: IconChartDonut3 },
      { path: "/pilotage/simulateur", label: "Simulateur", purpose: "Que rapporterait une campagne ?", icon: IconAdjustmentsHorizontal },
    ],
  },
  {
    label: "Opérations",
    items: [
      { path: "/operations/clients", label: "Clients à risque", purpose: "Qui contacter, et avec quelle action ?", icon: IconUsers },
      { path: "/operations/assistant", label: "Assistant", purpose: "Poser une question sur le portefeuille", icon: IconMessageChatbot },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export function findNavItem(pathname: string): { item: NavItem; group: NavGroup } | undefined {
  for (const group of NAV_GROUPS) {
    const item = group.items.find((i) => pathname.startsWith(i.path));
    if (item) return { item, group };
  }
  return undefined;
}
