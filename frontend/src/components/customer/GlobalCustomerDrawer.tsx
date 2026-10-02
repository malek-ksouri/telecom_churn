import { useSearchParams } from "react-router-dom";

import { useCustomerNav, useOpenCustomer } from "../../store/customerNav";
import { CustomerDrawer } from "./CustomerDrawer";

/** Fiche client ouverte par `?client=<id>`, quelle que soit la page (liste, chat, vue d'ensemble). */
export function GlobalCustomerDrawer() {
  const [params] = useSearchParams();
  const raw = params.get("client");
  const id = raw && /^[0-9]+$/.test(raw) ? Number(raw) : null;
  const { onPrev, onNext, position } = useCustomerNav();
  const open = useOpenCustomer();
  return (
    <CustomerDrawer
      customerId={id}
      onClose={() => { open(null); }}
      onPrev={onPrev}
      onNext={onNext}
      position={position}
    />
  );
}
