"""Entraînement et validation croisée des modèles (réutilisé en E7 et E8)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline

from churn.evaluation.cv import Folds
from churn.evaluation.metrics import compute_metrics, roc_auc, summarize_folds

logger = logging.getLogger(__name__)


@dataclass
class CVResult:
    """Résultat d'une validation croisée.

    Attributes:
        per_fold: métriques de validation par fold, plus l'AUC sur la partie apprentissage
            (``train_roc_auc``) pour mesurer le surapprentissage et la durée d'ajustement.
        oof: probabilités « out-of-fold » : chaque client est prédit par le modèle qui ne
            l'a pas vu à l'entraînement.
    """

    per_fold: pd.DataFrame
    oof: pd.Series

    def summary(self) -> pd.DataFrame:
        """Moyenne ± écart-type de chaque métrique."""
        return summarize_folds(self.per_fold)


def cross_validate_model(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series, folds: Folds,
                         name: str = "") -> CVResult:
    """Ajuste une copie du pipeline sur chaque fold d'apprentissage et l'évalue sur le fold de
    validation.

    Le pipeline est cloné à chaque fold : tout ce qu'il apprend (imputation, winsorisation,
    encodage, modèle) ne voit que la partie apprentissage du fold.

    Args:
        pipeline: estimateur sklearn non ajusté (``predict_proba`` requis).
        X: données du train (toutes colonnes ; le pipeline choisit les siennes).
        y: cible.
        folds: folds figés (``churn.evaluation.cv.make_folds``).
        name: libellé pour le journal.
    """
    rows = []
    oof = pd.Series(np.nan, index=y.index, name="proba")
    for i, (train_idx, valid_idx) in enumerate(folds):
        start = time.perf_counter()
        model = clone(pipeline).fit(X.iloc[train_idx], y.iloc[train_idx])
        fit_seconds = time.perf_counter() - start
        proba_valid = model.predict_proba(X.iloc[valid_idx])[:, 1]
        proba_train = model.predict_proba(X.iloc[train_idx])[:, 1]
        oof.iloc[valid_idx] = proba_valid
        rows.append({"fold": i, **compute_metrics(y.iloc[valid_idx].to_numpy(), proba_valid),
                     "train_roc_auc": roc_auc(y.iloc[train_idx].to_numpy(), proba_train),
                     "fit_seconds": fit_seconds})
    per_fold = pd.DataFrame(rows)
    logger.info("%s : AUC %.4f ± %.4f (train %.4f)", name or type(pipeline).__name__,
                per_fold["roc_auc"].mean(), per_fold["roc_auc"].std(),
                per_fold["train_roc_auc"].mean())
    return CVResult(per_fold=per_fold, oof=oof)
