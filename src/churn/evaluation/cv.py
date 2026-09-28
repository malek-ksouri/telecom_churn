"""Validation croisée avec des folds identiques pour toutes les comparaisons."""

from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

from churn.config import get_config

logger = logging.getLogger(__name__)

Folds = list[tuple[np.ndarray, np.ndarray]]


def make_folds(y: pd.Series, n_splits: int | None = None,
               random_state: int | None = None) -> Folds:
    """Folds stratifiés figés (``cv_folds`` et ``random_state`` de la config).

    Les calculer une fois et les réutiliser garantit que deux configurations sont
    comparées sur exactement les mêmes découpages : l'écart mesuré vient du modèle ou des
    features, pas du hasard du découpage.
    """
    cfg = get_config()
    seed = cfg.random_state if random_state is None else random_state
    skf = StratifiedKFold(n_splits or cfg.modeling.cv_folds, shuffle=True, random_state=seed)
    return list(skf.split(np.zeros(len(y)), y))


def cv_auc(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series, folds: Folds) -> np.ndarray:
    """AUC ROC de chaque fold (pipeline cloné et ajusté sur chaque fold d'entraînement)."""
    scores = []
    for train_idx, valid_idx in folds:
        model = clone(pipeline).fit(X.iloc[train_idx], y.iloc[train_idx])
        proba = model.predict_proba(X.iloc[valid_idx])[:, 1]
        scores.append(roc_auc_score(y.iloc[valid_idx], proba))
    return np.array(scores)


def ablation(configs: dict[str, list[str]],
             factories: dict[str, Callable[[list[str]], Pipeline]],
             X: pd.DataFrame, y: pd.Series, folds: Folds) -> pd.DataFrame:
    """AUC par fold pour chaque configuration de familles et chaque modèle.

    Args:
        configs: nom de configuration -> familles de features actives.
        factories: nom de modèle -> fonction qui construit le pipeline à partir des familles.

    Returns:
        Format long : configuration, modele, fold, auc.
    """
    rows = []
    for model_name, factory in factories.items():
        for config_name, groups in configs.items():
            scores = cv_auc(factory(groups), X, y, folds)
            logger.info("%s | %s : AUC %.4f ± %.4f", model_name, config_name,
                        scores.mean(), scores.std())
            rows += [{"configuration": config_name, "modele": model_name, "fold": i,
                      "auc": s} for i, s in enumerate(scores)]
    return pd.DataFrame(rows)


def summarize_ablation(results: pd.DataFrame, reference: str) -> pd.DataFrame:
    """AUC moyenne ± écart-type par configuration, et gain par rapport à la référence.

    Le gain est aussi calculé **fold par fold** (mêmes folds) : sa moyenne et son écart-type
    mesurent l'apport de la famille plus finement que l'écart entre deux moyennes, car la
    variabilité propre aux folds (certains plus faciles que d'autres) s'annule.
    """
    wide = results.pivot_table(index=["modele", "fold"], columns="configuration", values="auc")
    rows = []
    for model, part in wide.groupby(level="modele"):
        for config in part.columns:
            gain = part[config] - part[reference]
            rows.append({"modele": model, "configuration": config,
                         "auc_moyenne": part[config].mean(),
                         "auc_ecart_type": part[config].std(),
                         "gain_moyen": gain.mean(), "gain_ecart_type": gain.std(),
                         "folds_en_hausse": int((gain > 0).sum())})
    return pd.DataFrame(rows)
