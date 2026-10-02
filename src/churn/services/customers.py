"""Clients : liste paginée, fiche, explication SHAP (E13).

Les listes et les compteurs de pagination sont en **lignes réelles** (``n_rows``) : ce sont
les clients de la base. Les probabilités affichées sont par client ; aucune n'est un
effectif repondéré.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from churn.business.actions import CONTEXT, FAMILY_LABELS, family
from churn.explain.reason_codes import DECREASES, INCREASES
from churn.explain.shap_utils import label
from churn.features.build import CONTRACT_END_MONTHS
from churn.services.filters import Filters, filter_mask
from churn.services.store import Store, get_store

SORT_FIELDS: dict[str, str] = {
    "p_real": "proba_reelle",
    "revenue_at_risk_monthly": "revenu_en_jeu",
    "monthly_bill": "rev_Mean",
    "tenure_months": "months",
    "handset_age_days": "eqpdays",
    "customer_id": "Customer_ID",
}
MAX_PAGE_SIZE = 200
N_REASONS, N_CONTEXT = 3, 2

# Variables de la fiche : (colonne, libellé, unité).
PROFILE_FIELDS: list[tuple[str, str, str]] = [
    ("months", "Ancienneté", "mois"),
    ("eqpdays", "Âge du terminal", "jours"),
    ("hnd_price", "Prix du terminal", "$"),
    ("mou_Mean", "Minutes d'appel par mois", "minutes / mois"),
    ("change_mou", "Évolution de l'usage", "minutes / mois"),
    ("totmrc_Mean", "Forfait mensuel", "$ / mois"),
    ("rev_Mean", "Facture mensuelle", "$ / mois"),
    ("ovrrev_Mean", "Dépassements de forfait", "$ / mois"),
    ("custcare_Mean", "Appels au service client", "appels / mois"),
    ("drop_vce_Mean", "Appels coupés", "appels / mois"),
    ("actvsubs", "Lignes actives", "lignes"),
    ("crclscod", "Classe de crédit", ""),
    ("area", "Région", ""),
]


class CustomerNotFoundError(LookupError):
    """Identifiant client absent des artefacts."""


def _value(x: Any) -> Any:
    if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x):
        return None
    if isinstance(x, np.integer | int):
        return int(x)
    if isinstance(x, np.floating | float):
        return float(x)
    return str(x)


def _summary(row: pd.Series) -> dict[str, Any]:
    """Ligne de liste : ce qu'un conseiller voit avant d'ouvrir la fiche."""
    return {
        "customer_id": int(row["Customer_ID"]),
        "partition": row["partition"],
        "risk_level": row["niveau"],
        "p_real": float(row["proba_reelle"]),
        "p_calibrated": float(row["proba_calibree"]),
        "segment": row["segment"],
        "action": row["action"],
        "top_reason": _value(row["raison_1"]),
        "revenue_at_risk_monthly": float(row["revenu_en_jeu"]),
        "monthly_bill": _value(row["rev_Mean"]),
        "tenure_months": _value(row["months"]),
        "handset_age_days": _value(row["eqpdays"]),
        "area": row["area"],
        "inactive": bool(row["inactif"]),
    }


def _select(filters: Filters | None, sort: str, order: str, search: str | None) -> np.ndarray:
    """Positions des clients filtrés (et recherchés), triées ; manquants toujours en fin."""
    if sort not in SORT_FIELDS:
        raise ValueError(f"Tri inconnu : {sort} (valeurs : {', '.join(SORT_FIELDS)})")
    if order not in ("asc", "desc"):
        raise ValueError("order doit valoir asc ou desc")
    scores = get_store().scores
    mask = filter_mask(scores, filters)
    if search:
        mask &= scores["id_text"].str.contains(search.strip(), regex=False).to_numpy()
    positions = np.flatnonzero(mask)
    values = scores[SORT_FIELDS[sort]].to_numpy(dtype=float)[positions]
    key = np.where(np.isnan(values), np.inf, -values if order == "desc" else values)
    return positions[np.argsort(key, kind="stable")]


def list_customers(filters: Filters | None = None, sort: str = "p_real", order: str = "desc",
                   page: int = 1, size: int = 25, search: str | None = None) -> dict[str, Any]:
    """Liste paginée côté serveur des clients filtrés.

    Args:
        filters: filtres communs.
        sort: champ de tri (``SORT_FIELDS``).
        order: ``asc`` ou ``desc`` ; les valeurs manquantes sont toujours en fin de liste.
        page: numéro de page (à partir de 1).
        size: taille de page (1 à ``MAX_PAGE_SIZE``).
        search: fragment d'identifiant client.

    Raises:
        ValueError: tri, ordre ou pagination invalides.
    """
    if page < 1 or not 1 <= size <= MAX_PAGE_SIZE:
        raise ValueError(f"page >= 1 et 1 <= size <= {MAX_PAGE_SIZE}")
    positions = _select(filters, sort, order, search)
    total = len(positions)
    start = (page - 1) * size
    page_rows = get_store().scores.iloc[positions[start:start + size]]
    return {
        "filters": filters.active() if filters else {},
        "search": search or None,
        "sort": sort, "order": order, "page": page, "size": size,
        "total_n_rows": total,
        "total_pages": max(1, -(-total // size)),
        "items": [_summary(row) for _, row in page_rows.iterrows()],
    }


# Colonnes de l'export (libellés français, unités dans l'en-tête).
EXPORT_COLUMNS: list[tuple[str, str]] = [
    ("Customer_ID", "identifiant"),
    ("niveau", "niveau"),
    ("proba_reelle", "risque_mensuel_pct_taux_suppose_2pct"),
    ("proba_calibree", "probabilite_calibree_echantillon"),
    ("raison_1", "raison_principale"),
    ("raison_2", "raison_2"),
    ("raison_3", "raison_3"),
    ("action", "action_suggeree"),
    ("rev_Mean", "facture_mensuelle_dollars"),
    ("revenu_en_jeu", "revenu_mensuel_en_jeu_dollars"),
    ("segment", "segment"),
    ("area", "region"),
    ("months", "anciennete_mois"),
    ("partition", "partition"),
]


def export_customers(filters: Filters | None = None, sort: str = "p_real", order: str = "desc",
                     search: str | None = None) -> str:
    """Export CSV de toute la sélection filtrée (mêmes filtres, recherche et tri que la liste).

    Format pensé pour Excel en français : séparateur « ; », virgule décimale, BOM UTF-8.
    Une ligne = un client de la base (pas d'équivalent portefeuille).
    """
    positions = _select(filters, sort, order, search)
    rows = get_store().scores.iloc[positions]
    out = pd.DataFrame({label: rows[col].to_numpy() for col, label in EXPORT_COLUMNS})
    out["risque_mensuel_pct_taux_suppose_2pct"] = (
        100 * out["risque_mensuel_pct_taux_suppose_2pct"]).round(2)
    out["probabilite_calibree_echantillon"] = out["probabilite_calibree_echantillon"].round(4)
    out["revenu_mensuel_en_jeu_dollars"] = out["revenu_mensuel_en_jeu_dollars"].round(2)
    bom = chr(0xFEFF)  # Excel reconnaît l'UTF-8 grâce au BOM
    return bom + out.to_csv(sep=";", decimal=",", index=False, lineterminator=chr(10))


def _locate(store: Store, customer_id: int) -> int:
    try:
        return int(store.scores.index.get_loc(int(customer_id)))
    except (KeyError, ValueError, TypeError) as exc:
        raise CustomerNotFoundError(f"Client {customer_id} introuvable") from exc


def _factor(store: Store, pos: int, variable: str, text: str | None,
            in_window: bool) -> dict[str, Any]:
    j = store.shap_columns.index(variable)
    contribution = float(store.shap[pos, j])
    fam = family(variable, in_window)
    return {"variable": variable, "label": label(variable), "text": text,
            "family": fam, "family_label": FAMILY_LABELS[fam], "actionable": fam != CONTEXT,
            "contribution_log_odds": contribution,
            "effect": INCREASES if contribution > 0 else DECREASES}


def get_customer(customer_id: int) -> dict[str, Any]:
    """Fiche client : profil, probabilités, niveau, segment, 3 raisons actionnables, contexte,
    action suggérée.

    Raises:
        CustomerNotFoundError: identifiant inconnu.
    """
    store = get_store()
    pos = _locate(store, customer_id)
    row = store.scores.iloc[pos]
    in_window = int(row["months"]) in CONTRACT_END_MONTHS
    reasons = [_factor(store, pos, row[f"raison_{k}_variable"], row[f"raison_{k}"], in_window)
               for k in range(1, N_REASONS + 1) if _value(row[f"raison_{k}_variable"])]
    context = [_factor(store, pos, row[f"contexte_{k}_variable"],
                       str(row[f"contexte_{k}"]).rsplit(" (", 1)[0], in_window)
               for k in range(1, N_CONTEXT + 1) if _value(row[f"contexte_{k}_variable"])]
    return {
        "customer_id": int(row["Customer_ID"]),
        "partition": row["partition"],
        "scores": {
            "p_raw": float(row["proba_brute"]),
            "p_calibrated": float(row["proba_calibree"]),
            "p_real": float(row["proba_reelle"]),
            "p_real_note": "probabilité mensuelle de départ au taux de churn réel supposé "
                           "(hypothèse)",
        },
        "risk_level": row["niveau"],
        "inactive": bool(row["inactif"]),
        "segment": {"id": int(row["segment_id"]), "name": row["segment"]},
        "bands": {"tenure_band": row["tenure_band"], "handset_age_band": row["handset_age_band"],
                  "usage_band": row["usage_band"]},
        "action": row["action"],
        "dominant_family": _value(row["famille_dominante"]),
        "reasons": reasons,
        "context": context,
        "monthly_bill": _value(row["rev_Mean"]),
        "revenue_at_risk_monthly": float(row["revenu_en_jeu"]),
        "profile": [{"variable": col, "label": lab, "value": _value(row[col]), "unit": unit}
                    for col, lab, unit in PROFILE_FIELDS],
        "historical_churn_label": int(row["churn"]),
        "historical_churn_note": "étiquette historique du jeu de données (départ observé), "
                                 "affichée pour la démonstration ; le score n'en dépend pas "
                                 "(scores hors fold ou modèle final)",
        "note": "Raisons et contexte décrivent ce qui pèse sur le score selon le modèle (SHAP), "
                "pas des causes prouvées du départ.",
    }


def explain_customer(customer_id: int, top: int = 12) -> dict[str, Any]:
    """Contributions SHAP ordonnées d'un client, pour un graphique en cascade.

    De la valeur de base (log-odds moyen du modèle) au log-odds du client : les ``top``
    contributions les plus fortes, puis la somme des autres. ``sigmoid(log-odds)`` redonne la
    probabilité brute du modèle.

    Raises:
        CustomerNotFoundError: identifiant inconnu.
    """
    store = get_store()
    pos = _locate(store, customer_id)
    row = store.scores.iloc[pos]
    values = store.shap[pos].astype(float)
    in_window = int(row["months"]) in CONTRACT_END_MONTHS
    phrases: dict[str, str] = {}
    cid = int(row["Customer_ID"])
    if cid in store.factors.index:
        f = store.factors.loc[[cid]]
        phrases = dict(zip(f["variable"], f["phrase"], strict=True))
    order = np.argsort(-np.abs(values), kind="stable")
    items = []
    for j in order[:top]:
        var = store.shap_columns[j]
        fam = family(var, in_window)
        items.append({"variable": var, "label": label(var), "text": phrases.get(var),
                      "family": fam, "family_label": FAMILY_LABELS[fam],
                      "actionable": fam != CONTEXT, "contribution_log_odds": float(values[j]),
                      "effect": INCREASES if values[j] > 0 else DECREASES})
    base = float(row["valeur_base"])
    log_odds = base + float(values.sum())
    return {
        "customer_id": cid,
        "unit": "log-odds du modèle brut (avant calibration)",
        "base_value_log_odds": base,
        "contributions": items,
        "others_contribution_log_odds": float(values[order[top:]].sum()),
        "others_count": int(len(order) - min(top, len(order))),
        "log_odds": log_odds,
        "p_raw_from_log_odds": float(1 / (1 + np.exp(-log_odds))),
        "p_raw": float(row["proba_brute"]),
        "note": "SHAP explique le modèle, pas la causalité.",
    }
