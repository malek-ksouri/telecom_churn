"""Test de fuite « client déjà parti » (D32, D57, D66).

Hypothèse : un client sans aucune donnée d'usage, ou dont la variation d'usage n'est pas
calculable, est peut-être **déjà parti** au moment de la mesure. Le modèle apprendrait alors
une conséquence du churn, pas un signe avant-coureur.

Deux contrôles :

- **neutralisation** : les colonnes concernées sont imputées par leur médiane (apprise dans
  le fit) **avant** toute construction de features ; l'absence de valeur n'est plus
  observable, ni par un indicateur, ni par un arbre qui sait gérer les NaN, ni par un ratio ;
- **clients actifs** : l'AUC est recalculée sur les seuls clients de validation qui ont un
  usage mesuré et une variation d'usage renseignée.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score

from churn.data.validate import NEGATIVE_FLAG_SUFFIX, USAGE_BLOCK
from churn.evaluation.cv import Folds

LEAK_COLUMNS: tuple[str, ...] = tuple(USAGE_BLOCK) + ("change_mou", "change_rev")


class LeakNeutralizer(BaseEstimator, TransformerMixin):
    """Impute les colonnes « déjà parti » par leur médiane apprise dans ``fit``.

    Placé en tête de pipeline, il supprime toute trace de l'absence de ces valeurs.
    """

    def __init__(self, columns: Sequence[str] = LEAK_COLUMNS) -> None:
        self.columns = columns

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> LeakNeutralizer:
        """Apprend la médiane de chaque colonne sur la partie apprentissage."""
        self.medians_ = X[list(self.columns)].median()
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Remplace les NaN des colonnes concernées par les médianes apprises."""
        X = X.copy()
        X[list(self.columns)] = X[list(self.columns)].fillna(self.medians_)
        return X


def active_client_mask(df: pd.DataFrame) -> pd.Series:
    """Clients « actifs » : usage mesuré dans la source et ``change_mou`` renseigné.

    Un ``rev_Mean`` mis à NaN par ``clean()`` (valeur négative) compte comme mesuré.
    """
    flag = f"rev_Mean{NEGATIVE_FLAG_SUFFIX}"
    usage_missing = df["rev_Mean"].isna()
    if flag in df:
        usage_missing &= df[flag] == 0
    return ~usage_missing & df["change_mou"].notna()


def subset_auc_per_fold(oof: pd.Series, y: pd.Series, folds: Folds,
                        mask: pd.Series) -> np.ndarray:
    """AUC de chaque fold de validation, restreinte aux lignes où ``mask`` est vrai."""
    scores = []
    for _, valid_idx in folds:
        idx = y.index[valid_idx]
        keep = idx[mask.loc[idx].to_numpy()]
        scores.append(roc_auc_score(y.loc[keep], oof.loc[keep]))
    return np.array(scores)
