"""Revenu en jeu et tableau de campagne (E12).

- **Revenu mensuel en jeu** d'un client = probabilité corrigée vers le taux réel (hypothèse,
  2 % par mois) × facture mensuelle (``rev_Mean``) : le revenu qu'on s'attend à perdre le
  mois prochain si rien n'est fait. Ce n'est **pas** un revenu préservé : celui-ci dépendrait
  du taux de succès de l'offre, inconnu (D79).
- **Tableau de campagne** : pour chaque capacité (5, 10, 20 % du portefeuille), clients
  ciblés, churners attendus parmi eux (contre un ciblage au hasard) et revenu en jeu. Les
  inactifs (D86) sont comptés sur une ligne séparée : ils relèvent d'une vérification de ligne
  ou d'une reconquête, pas d'une offre de fidélisation.

**Deux natures d'effectifs**, toujours nommées explicitement :

- ``n_rows`` : lignes réelles de la base (clients du jeu de données, ~50 % de churners) ;
- ``n_portfolio_equiv`` : **estimation** de l'effectif équivalent dans un portefeuille réel de
  ``portfolio_size`` clients au taux de churn supposé (hypothèse, 2 %). Chaque ligne reçoit un
  poids (``PORTFOLIO_WEIGHT``) : churners × r/s, non-churners × (1 - r)/(1 - s), normalisé
  pour que la base entière représente ``portfolio_size`` clients. Un sous-ensemble filtré
  garde ces poids : il représente la part correspondante du portefeuille.

Aucun coût n'est supposé.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from churn.business.scoring import TIERS
from churn.config import get_config
from churn.evaluation.calibration import population_weights

INACTIVE_ROW = "Inactifs (vérification / reconquête)"
PORTFOLIO_WEIGHT = "poids_portefeuille"


def revenue_at_risk(p_real: pd.Series, revenue: pd.Series) -> pd.Series:
    """Revenu mensuel en jeu = probabilité corrigée × facture mensuelle (facture inconnue : 0)."""
    return (p_real * revenue.fillna(0)).rename("revenu_en_jeu")


def portfolio_weights(churn: pd.Series | np.ndarray, real_rate: float | None = None,
                      sample_rate: float | None = None,
                      portfolio_size: int | None = None) -> np.ndarray:
    """Équivalent portefeuille de chaque ligne (somme = ``portfolio_size``).

    Args:
        churn: étiquettes historiques des lignes (0/1).
        real_rate: taux réel supposé (hypothèse de la config par défaut).
        sample_rate: taux de churn de l'échantillon (celui de ``churn`` par défaut).
        portfolio_size: taille du portefeuille représenté (config par défaut).
    """
    cfg = get_config()
    y = np.asarray(churn)
    r = cfg.business.real_churn_rate.value if real_rate is None else real_rate
    s = float(y.mean()) if sample_rate is None else sample_rate
    size = portfolio_size or cfg.business.campaign.portfolio_size
    w = population_weights(y, r, s)
    return w * size / w.sum()


def _weights(scores: pd.DataFrame, real_rate: float, sample_rate: float | None,
             portfolio_size: int | None) -> np.ndarray:
    """Poids stockés (échelle globale, conservée par les filtres) ou calculés sur ``scores``."""
    if PORTFOLIO_WEIGHT in scores.columns:
        return scores[PORTFOLIO_WEIGHT].to_numpy()
    return portfolio_weights(scores["churn"], real_rate, sample_rate, portfolio_size)


def _summary(mask: np.ndarray, scores: pd.DataFrame, w: np.ndarray,
             real_rate: float) -> dict[str, float]:
    """Effectifs (lignes réelles et équivalent portefeuille) et montants d'un groupe."""
    wm = w * mask
    n = wm.sum()
    expected = (wm * scores["proba_reelle"]).sum()
    return {
        "n_rows": int(mask.sum()),
        "n_portfolio_equiv": n,
        "churners_attendus": expected,
        "churners_hasard": n * real_rate,
        "facteur_vs_hasard": expected / (n * real_rate) if n else np.nan,
        "churners_observes": (wm * scores["churn"]).sum(),
        "revenu_en_jeu": (wm * scores["revenu_en_jeu"]).sum(),
        "facture_mensuelle": (wm * scores["rev_Mean"].fillna(0)).sum(),
    }


def campaign_curve(scores: pd.DataFrame, capacities: list[float] | np.ndarray,
                   real_rate: float | None = None, sample_rate: float | None = None,
                   portfolio_size: int | None = None) -> pd.DataFrame:
    """Résultats de campagne pour chaque capacité, en un seul tri (vectorisé).

    Les clients **actifs** sont ciblés par probabilité calibrée décroissante jusqu'à ce que
    leur équivalent portefeuille atteigne ``capacité × équivalent portefeuille de scores``.

    Returns:
        Une ligne par capacité : ``n_rows`` et ``n_portfolio_equiv`` ciblés, churners attendus
        (probabilités corrigées) et au hasard, facteur, churners observés (contrôle), revenu en
        jeu, facture, et parts des churners attendus et du revenu en jeu de ``scores``.
    """
    r = get_config().business.real_churn_rate.value if real_rate is None else real_rate
    w = _weights(scores, r, sample_rate, portfolio_size)
    inactive = scores["inactif"].to_numpy()
    order = np.argsort(-scores["proba_calibree"].to_numpy(), kind="stable")
    order = order[~inactive[order]]
    wo = w[order]
    share_before = (np.cumsum(wo) - wo) / w.sum()
    cum = {name: np.concatenate([[0.0], np.cumsum(wo * scores[col].to_numpy()[order])])
           for name, col in [("expected", "proba_reelle"), ("observed", "churn"),
                             ("revenue", "revenu_en_jeu")]}
    cum["bill"] = np.concatenate([[0.0], np.cumsum(wo * scores["rev_Mean"].fillna(0)
                                                   .to_numpy()[order])])
    cum["n"] = np.concatenate([[0.0], np.cumsum(wo)])
    total_expected = (w * scores["proba_reelle"]).sum()
    total_revenue = (w * scores["revenu_en_jeu"]).sum()
    caps = np.asarray(capacities, dtype=float)
    k = np.searchsorted(share_before, caps, side="left")   # nombre de lignes ciblées
    n = cum["n"][k]
    expected = cum["expected"][k]
    return pd.DataFrame({
        "capacite": caps,
        "n_rows": k,
        "n_portfolio_equiv": n,
        "churners_attendus": expected,
        "churners_hasard": n * r,
        "facteur_vs_hasard": np.divide(expected, n * r, out=np.full(len(k), np.nan),
                                       where=n > 0),
        "churners_observes": cum["observed"][k],
        "revenu_en_jeu": cum["revenue"][k],
        "facture_mensuelle": cum["bill"][k],
        "part_churners_attendus": expected / total_expected,
        "part_revenu_en_jeu": cum["revenue"][k] / total_revenue,
    })


def campaign_table(scores: pd.DataFrame, capacities: list[float] | None = None,
                   real_rate: float | None = None, sample_rate: float | None = None,
                   portfolio_size: int | None = None) -> pd.DataFrame:
    """Clients ciblés, churners attendus et revenu en jeu selon la capacité de campagne.

    Args:
        scores: une ligne par client avec ``proba_calibree``, ``proba_reelle``,
            ``revenu_en_jeu``, ``rev_Mean``, ``inactif`` et ``churn`` (étiquette historique,
            pour la repondération et le contrôle) ; ``poids_portefeuille`` s'il est présent.
        capacities: parts du portefeuille contactables (config par défaut).
        real_rate: taux réel supposé (hypothèse de la config par défaut).
        sample_rate: taux de churn de l'échantillon (celui de ``scores`` par défaut).
        portfolio_size: taille du portefeuille pour exprimer les effectifs.

    Returns:
        Une ligne par capacité, puis la ligne des inactifs et le portefeuille entier.
    """
    cfg = get_config()
    capacities = capacities or cfg.business.campaign.capacities
    r = cfg.business.real_churn_rate.value if real_rate is None else real_rate
    w = _weights(scores, r, sample_rate, portfolio_size)
    curve = campaign_curve(scores, capacities, r, sample_rate, portfolio_size)
    curve.insert(0, "groupe", [f"Top {100 * k:.0f} % (actifs)" for k in capacities])
    total = _summary(np.ones(len(scores), dtype=bool), scores, w, r)
    inactive = _summary(scores["inactif"].to_numpy(), scores, w, r)
    extra = pd.DataFrame([{"groupe": INACTIVE_ROW, "capacite": np.nan, **inactive},
                          {"groupe": "Portefeuille entier", "capacite": np.nan, **total}])
    extra["part_churners_attendus"] = extra["churners_attendus"] / total["churners_attendus"]
    extra["part_revenu_en_jeu"] = extra["revenu_en_jeu"] / total["revenu_en_jeu"]
    return pd.concat([curve, extra], ignore_index=True)


def group_summary(scores: pd.DataFrame, by: str, order: list[str] | None = None,
                  real_rate: float | None = None, sample_rate: float | None = None,
                  portfolio_size: int | None = None) -> pd.DataFrame:
    """Par groupe (niveau, segment, action...) : lignes réelles et équivalent portefeuille,
    risque moyen, churn observé dans la base, churners attendus et revenu en jeu."""
    r = get_config().business.real_churn_rate.value if real_rate is None else real_rate
    w = _weights(scores, r, sample_rate, portfolio_size)
    groups = order or list(pd.unique(scores[by].dropna()))
    total_w = w.sum()
    rows = []
    for group in groups:
        mask = (scores[by] == group).to_numpy()
        summary = _summary(mask, scores, w, r)
        rows.append({
            by: group,
            "part_portefeuille": summary["n_portfolio_equiv"] / total_w,
            "part_lignes": mask.mean(),
            "proba_reelle_moyenne": (summary["churners_attendus"] / summary["n_portfolio_equiv"]
                                     if summary["n_portfolio_equiv"] else np.nan),
            "churn_observe_base": scores.loc[mask, "churn"].mean(),
            **{k: summary[k] for k in ("n_rows", "n_portfolio_equiv", "churners_attendus",
                                       "revenu_en_jeu", "facture_mensuelle")},
        })
    out = pd.DataFrame(rows).set_index(by)
    out["part_churners_attendus"] = out["churners_attendus"] / (w * scores["proba_reelle"]).sum()
    out["part_revenu_en_jeu"] = out["revenu_en_jeu"] / (w * scores["revenu_en_jeu"]).sum()
    return out


def tier_summary(scores: pd.DataFrame, real_rate: float | None = None,
                 sample_rate: float | None = None,
                 portfolio_size: int | None = None) -> pd.DataFrame:
    """Synthèse par niveau de risque (High, Medium, Low, Inactif) : voir ``group_summary``."""
    return group_summary(scores, "niveau", TIERS, real_rate, sample_rate, portfolio_size)
