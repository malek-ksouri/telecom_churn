"""Simulateur de campagne (E13).

Ce qui vient du modèle : clients ciblés, churners attendus, facteur par rapport au hasard,
revenu en jeu (équivalent portefeuille au taux de churn supposé, hypothèse).

Ce qui vient de l'utilisateur, **étiqueté hypothèse** (D79) :

- ``success_rate`` : part des churners ciblés que l'offre retient -> départs évités et revenu
  préservé ;
- ``offer_cost`` (optionnel) : coût de l'offre par client contacté -> coût et solde. Sans
  coût fourni, aucun coût ni solde n'est calculé (aucun chiffre inventé) ;
- ``revenue_horizon_months`` : nombre de mois de revenu préservé comptés dans le solde
  (1 par défaut).

Les inactifs ne sont jamais ciblés par l'offre (D86) : ils sont rapportés à part.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from churn.business.actions import INACTIVE_ACTION
from churn.business.campaign import PORTFOLIO_WEIGHT, campaign_curve
from churn.config import get_config
from churn.services.analytics import hypothesis, num
from churn.services.filters import Filters, filter_mask
from churn.services.store import get_store

CURVE_CAPACITIES_PCT = list(range(1, 51))


def _result(row: Any, success_rate: float, offer_cost: float | None,
            horizon: int, real_rate: float) -> dict[str, Any]:
    n = float(row["n_portfolio_equiv"])
    expected = float(row["churners_attendus"])
    revenue = float(row["revenu_en_jeu"])
    avoided = expected * success_rate
    preserved = revenue * success_rate
    preserved_horizon = preserved * horizon
    cost = None if offer_cost is None else offer_cost * n
    return {
        "capacity_pct": round(100 * float(row["capacite"]), 6),
        "targeted_n_rows": int(row["n_rows"]),
        "targeted_n_portfolio_equiv": n,
        "expected_churners": expected,
        "random_churners": n * real_rate,
        "lift_vs_random": num(row["facteur_vs_hasard"]),
        "churners_per_1000_contacted": 1000 * expected / n if n else None,
        "share_of_expected_churners": num(row["part_churners_attendus"]),
        "revenue_at_risk_monthly": revenue,
        "share_of_revenue_at_risk": num(row["part_revenu_en_jeu"]),
        "observed_churners_check": float(row["churners_observes"]),
        "avoided_departures_hypothesis": avoided,
        "preserved_revenue_monthly_hypothesis": preserved,
        "preserved_revenue_horizon_hypothesis": preserved_horizon,
        "campaign_cost": cost,
        "net_balance": None if cost is None else preserved_horizon - cost,
    }


def simulate_campaign(capacity_pct: float, success_rate: float, offer_cost: float | None = None,
                      filters: Filters | None = None,
                      revenue_horizon_months: int = 1) -> dict[str, Any]:
    """Résultats d'une campagne ciblant ``capacity_pct`` % du périmètre filtré (clients actifs
    par risque décroissant), et courbe complète de 1 à 50 %.

    Args:
        capacity_pct: part du périmètre contactée, en % (0 < x <= 100).
        success_rate: taux de succès **supposé** de l'offre (0 à 1).
        offer_cost: coût de l'offre par client contacté ($), fourni par l'utilisateur.
        filters: périmètre de la campagne.
        revenue_horizon_months: mois de revenu préservé comptés dans le solde.

    Raises:
        ValueError: paramètre hors bornes.
    """
    if not 0 < capacity_pct <= 100:
        raise ValueError("capacity_pct doit être dans ]0 ; 100]")
    if not 0 <= success_rate <= 1:
        raise ValueError("success_rate doit être dans [0 ; 1]")
    if offer_cost is not None and offer_cost < 0:
        raise ValueError("offer_cost doit être positif ou nul")
    if revenue_horizon_months < 1:
        raise ValueError("revenue_horizon_months doit être >= 1")
    store = get_store()
    cfg = get_config()
    r = cfg.business.real_churn_rate.value
    sub = store.scores[filter_mask(store.scores, filters)]
    active = sub[~sub["inactif"]]
    inactive = sub[sub["inactif"]]
    scope = {"n_rows": len(sub), "n_portfolio_equiv": float(sub[PORTFOLIO_WEIGHT].sum())}

    result, curve = None, []
    if len(active):
        caps = np.array([capacity_pct, *CURVE_CAPACITIES_PCT]) / 100
        table = campaign_curve(sub, caps)
        result = _result(table.iloc[0], success_rate, offer_cost, revenue_horizon_months, r)
        curve = [_result(row, success_rate, offer_cost, revenue_horizon_months, r)
                 for _, row in table.iloc[1:].iterrows()]
    wi = inactive[PORTFOLIO_WEIGHT]
    return {
        "filters": filters.active() if filters else {},
        "hypothesis": hypothesis(store),
        "user_hypotheses": {
            "success_rate": success_rate,
            "offer_cost_per_contact": offer_cost,
            "revenue_horizon_months": revenue_horizon_months,
            "note": "Taux de succès et coût sont des hypothèses saisies par l'utilisateur, pas "
                    "des résultats du modèle : départs évités, revenu préservé, coût et solde en "
                    "dépendent directement.",
        },
        "scope": scope,
        "result": result,
        "inactive": {
            "n_rows": len(inactive),
            "n_portfolio_equiv": float(wi.sum()),
            "expected_churners": float((wi * inactive["proba_reelle"]).sum()),
            "revenue_at_risk_monthly": float((wi * inactive["revenu_en_jeu"]).sum()),
            "action": INACTIVE_ACTION,
            "note": "Non ciblés par l'offre de fidélisation : vérification de ligne ou "
                    "reconquête (D86).",
        },
        "curve": curve,
    }
