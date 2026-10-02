import { IconBulb, IconChartBar, IconTarget, IconUserSearch, IconUsers } from "@tabler/icons-react";

/** Client de démonstration (High, fin d'engagement) cité dans une question suggérée. */
export const DEMO_CUSTOMER_ID = 1072931;

export const SUGGESTIONS = [
  { icon: IconUsers, text: "Quels clients cibler en priorité ?" },
  { icon: IconUserSearch, text: `Pourquoi le client ${String(DEMO_CUSTOMER_ID)} est-il à risque ?` },
  { icon: IconChartBar, text: "Quel segment churne le plus ?" },
  { icon: IconTarget, text: "Si je contacte 10 % des clients avec un taux de succès de 20 % ?" },
  { icon: IconBulb, text: "Qu'est-ce que le lift ?" },
];
