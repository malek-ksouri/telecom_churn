"""Revenu en jeu et tableau de campagne (E12).

- **Revenu mensuel en jeu** d'un client = probabilité corrigée vers le taux réel (hypothèse,
  2 % par mois) × facture mensuelle (``rev_Mean``) : le revenu qu'on s'attend à perdre le
  mois prochain si rien n'est fait. Ce n'est **pas** un revenu préservé : celui-ci dépendrait
  du taux de succès de l'offre, inconnu (D79).
- **Tableau de campagne** : pour chaque capacité (5, 10, 20 % du portefeuille), clients
  ciblés, churners attendus parmi eux (contre un ciblage au hasard) et revenu en jeu. Les
  inactifs (D86) sont comptés sur une ligne séparée : ils relèvent d'une vérification de ligne
  ou d'une reconquête, pas d'une offre de fidélisation.

Le jeu de données est équilibré (~50 % de churners) : les clients sont **repondérés** vers un
portefeuille au taux réel supposé (``population_weights``), puis les effectifs sont exprimés
pour un portefeuille de ``portfolio_size`` clients. Aucun coût n'est supposé.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from churn.business.scoring import TIERS
from churn.config import get_config
from churn.evaluation.calibration import population_weights

INACTIVE_ROW = "Inactifs (vérification / reconquête)"


def revenue_at_risk(p_real: pd.Series, revenue: pd.Series) -> pd.Series:
    """Revenu mensuel en jeu = probabilité corrigée × facture mensuelle (facture inconnue : 0)."""
    return (p_real * revenue.fillna(0)).rename("revenu_en_jeu")


def _weights(scores: pd.DataFrame, real_rate: float, sample_rate: float) -> np.ndarray:
    return population_weights(scores["churn"].to_numpy(), real_rate, sample_rate)


def _summary(mask: np.ndarray, scores: pd.DataFrame, w: np.ndarray, scale: float,
             real_rate: float) -> dict[str, float]:
    """Effectifs et montants d'un groupe de clients, exprimés pour le portefeuille réel."""
    wm = w * mask
    n = scale * wm.sum()
    expected = scale * (wm * scores["proba_reelle"]).sum()
    return {
        "clients": n,
        "churners_attendus": expected,
        "churners_hasard": n * real_rate,
        "facteur_vs_hasard": expected / (n * real_rate) if n else np.nan,
        "churners_observes": scale * (wm * scores["churn"]).sum(),
        "revenu_en_jeu": scale * (wm * scores["revenu_en_jeu"]).sum(),
        "facture_mensuelle": scale * (wm * scores["rev_Mean"].fillna(0)).sum(),
    }


def campaign_table(scores: pd.DataFrame, capacities: list[float] | None = None,
                   real_rate: float | None = None, sample_rate: float | None = None,
                   portfolio_size: int | None = None) -> pd.DataFrame:
    """Clients ciblés, churners attendus et revenu en jeu selon la capacité de campagne.

    Les clients **actifs** sont ciblés par probabilité calibrée décroissante jusqu'à la
    capacité (part du portefeuille) ; les inactifs forment une ligne à part.

    Args:
        scores: une ligne par client avec ``proba_calibree``, ``proba_reelle``,
            ``revenu_en_jeu``, ``inactif`` et ``churn`` (étiquette historique, pour la
            repondération et la vérification).
        capacities: parts du portefeuille contactables (config par défaut).
        real_rate: taux réel supposé (hypothèse de la config par défaut).
        sample_rate: taux de churn de l'échantillon (celui de ``scores`` par défaut).
        portfolio_size: taille du portefeuille pour exprimer les effectifs.

    Returns:
        Une ligne par capacité, puis la ligne des inactifs et le portefeuille entier.
        ``churners_attendus`` et ``revenu_en_jeu`` viennent des probabilités corrigées ;
        ``churners_observes`` des étiquettes historiques repondérées (contrôle).
    """
    cfg = get_config()
    capacities = capacities or cfg.business.campaign.capacities
    r = cfg.business.real_churn_rate.value if real_rate is None else real_rate
    s = float(scores["churn"].mean()) if sample_rate is None else sample_rate
    size = portfolio_size or cfg.business.campaign.portfolio_size
    w = _weights(scores, r, s)
    scale = size / w.sum()
    inactive = scores["inactif"].to_numpy()

    order = np.argsort(-scores["proba_calibree"].to_numpy(), kind="stable")
    order = order[~inactive[order]]
    share_before = (np.cumsum(w[order]) - w[order]) / w.sum()
    total = _summary(np.ones(len(scores), dtype=bool), scores, w, scale, r)

    rows = []
    for k in capacities:
        mask = np.zeros(len(scores), dtype=bool)
        mask[order[share_before < k]] = True
        rows.append({"groupe": f"Top {100 * k:.0f} % (actifs)", "capacite": k,
                     **_summary(mask, scores, w, scale, r)})
    rows.append({"groupe": INACTIVE_ROW, "capacite": np.nan,
                 **_summary(inactive, scores, w, scale, r)})
    rows.append({"groupe": "Portefeuille entier", "capacite": np.nan, **total})
    out = pd.DataFrame(rows)
    out["part_churners_attendus"] = out["churners_attendus"] / total["churners_attendus"]
    out["part_revenu_en_jeu"] = out["revenu_en_jeu"] / total["revenu_en_jeu"]
    return out


def group_summary(scores: pd.DataFrame, by: str, order: list[str] | None = None,
                  real_rate: float | None = None, sample_rate: float | None = None,
                  portfolio_size: int | None = None) -> pd.DataFrame:
    """Par groupe (niveau, segment, action...) : part du portefeuille réel et de l'échantillon,
    risque moyen, churn observé dans l'échantillon, churners attendus et revenu en jeu
    (portefeuille réel repondéré)."""
    cfg = get_config()
    r = cfg.business.real_churn_rate.value if real_rate is None else real_rate
    s = float(scores["churn"].mean()) if sample_rate is None else sample_rate
    size = portfolio_size or cfg.business.campaign.portfolio_size
    w = _weights(scores, r, s)
    scale = size / w.sum()
    groups = order or list(pd.unique(scores[by].dropna()))
    rows = []
    for group in groups:
        mask = (scores[by] == group).to_numpy()
        summary = _summary(mask, scores, w, scale, r)
        rows.append({
            by: group,
            "part_portefeuille": w[mask].sum() / w.sum(),
            "part_echantillon": mask.mean(),
            "clients_echantillon": int(mask.sum()),
            "proba_reelle_moyenne": (summary["churners_attendus"] / summary["clients"]
                                     if summary["clients"] else np.nan),
            "churn_observe_echantillon": scores.loc[mask, "churn"].mean(),
            **{k: summary[k] for k in ("clients", "churners_attendus", "revenu_en_jeu",
                                          "facture_mensuelle")},
        })
    out = pd.DataFrame(rows).set_index(by)
    out["part_churners_attendus"] = out["churners_attendus"] / (scale * (w * scores[
        "proba_reelle"]).sum())
    out["part_revenu_en_jeu"] = out["revenu_en_jeu"] / (scale * (w * scores[
        "revenu_en_jeu"]).sum())
    return out


def tier_summary(scores: pd.DataFrame, real_rate: float | None = None,
                 sample_rate: float | None = None,
                 portfolio_size: int | None = None) -> pd.DataFrame:
    """Synthèse par niveau de risque (High, Medium, Low, Inactif) : voir ``group_summary``."""
    return group_summary(scores, "niveau", TIERS, real_rate, sample_rate, portfolio_size)
