"""Pipelines de modélisation (versions de référence utilisées pour l'ablation E6).

Tout ce qui apprend des données (imputation, standardisation, encodage, modèle) vit dans
le ``Pipeline`` et est donc ajusté dans chaque fold de validation croisée.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from churn.config import get_config
from churn.features.build import FeatureBuilder

MISSING_CATEGORY = "Manquant"


class ColumnDropper(BaseEstimator, TransformerMixin):
    """Retire une liste fixe de colonnes (sans état) ; les colonnes absentes sont ignorées."""

    def __init__(self, columns: Sequence[str] = ()) -> None:
        self.columns = columns

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> ColumnDropper:
        """Aucun apprentissage."""
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Renvoie ``X`` sans les colonnes listées."""
        return X.drop(columns=[c for c in self.columns if c in X])


def categories_as_text(X: pd.DataFrame) -> np.ndarray:
    """Catégorielles -> texte, NaN -> « Manquant » (une modalité à part entière)."""
    return X.astype(object).where(X.notna(), MISSING_CATEGORY).astype(str).to_numpy()


def load_logreg_drop_list(path: Path | None = None) -> list[str]:
    """Variables à retirer pour la régression logistique (redondance + VIF, E5)."""
    path = path or get_config().paths.reports_dir / "logreg_drop_list.json"
    return json.loads(path.read_text(encoding="utf-8"))["toutes"]


def non_feature_columns() -> list[str]:
    """Identifiant, cible et variables exclues (ethnic) : jamais passés au modèle."""
    return get_config().non_feature_columns


def make_lgbm_pipeline(groups: Sequence[str] | None, random_state: int | None = None
                       ) -> Pipeline:
    """Features + LightGBM aux hyperparamètres par défaut.

    LightGBM gère nativement les NaN et le type ``category`` : aucun prétraitement appris.
    """
    seed = get_config().random_state if random_state is None else random_state
    return Pipeline([
        ("features", FeatureBuilder(groups, drop_columns=non_feature_columns())),
        ("model", LGBMClassifier(random_state=seed, verbose=-1, n_jobs=-1)),
    ])


def make_logreg_pipeline(groups: Sequence[str] | None, drop: Sequence[str] = (),
                         random_state: int | None = None) -> Pipeline:
    """Features + régression logistique simple : imputation médiane, standardisation, one-hot.

    ``drop`` : liste de E5 (variables redondantes ou à VIF élevé), appliquée après la
    construction des features. Modalités de moins de 30 clients regroupées par l'encodeur.
    """
    seed = get_config().random_state if random_state is None else random_state
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler())])
    categorical = Pipeline([
        ("text", FunctionTransformer(categories_as_text)),
        ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=30,
                                 sparse_output=False)),
    ])
    preprocess = ColumnTransformer([
        ("num", numeric, make_column_selector(dtype_include="number")),
        ("cat", categorical, make_column_selector(dtype_include="category")),
    ])
    return Pipeline([
        ("features", FeatureBuilder(groups, drop_columns=non_feature_columns())),
        ("drop", ColumnDropper(drop)),
        ("preprocess", preprocess),
        ("model", LogisticRegression(max_iter=2000, random_state=seed)),
    ])
