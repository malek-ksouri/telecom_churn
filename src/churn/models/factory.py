"""Point d'entrée unique pour construire un modèle par son nom (E7, E8).

Chaque pipeline commence par ``FeatureBuilder`` (familles de la config) et contient tout ce
qui apprend des données : il peut être passé tel quel à ``cross_validate_model``.

Prétraitement selon la famille de modèle :

- **linéaires** (``logreg_simple``, ``logreg``) : imputation, log, écrêtage, standardisation,
  splines, one-hot, liste de retrait de E5 (colinéarité) ;
- **arbres scikit-learn** (``decision_tree``, ``random_forest``) : NaN **conservés** (gérés
  nativement depuis scikit-learn 1.3 / 1.4), catégorielles en ``OrdinalEncoder`` (un arbre
  découpe sur l'ordre des codes ; modalité inconnue -> -1, manquante -> NaN) ; pas de
  standardisation ni de log, inutiles pour un arbre ; toutes les variables gardées ;
- **boosting** : ``lightgbm`` gère nativement NaN et type ``category`` ; ``catboost`` gère
  nativement les catégorielles (texte, NaN -> « Manquant ») et les NaN numériques.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier

from churn.config import get_config
from churn.features.build import FeatureBuilder
from churn.models.baselines import SegmentRateClassifier, make_dummy
from churn.models.leakage import LeakNeutralizer
from churn.models.pipelines import (
    MISSING_CATEGORY,
    load_logreg_drop_list,
    make_logreg_pipeline,
    non_feature_columns,
)
from churn.models.preprocessing import CategoricalColumns, make_improved_logreg_pipeline

LINEAR_MODELS = ("logreg_simple", "logreg")
TREE_MODELS = ("decision_tree", "random_forest", "lightgbm", "catboost")
BASELINES = ("dummy", "rules")
MODEL_NAMES: tuple[str, ...] = BASELINES + LINEAR_MODELS + TREE_MODELS

# Hyperparamètres de départ, raisonnables sans réglage fin (E8). Arbre : profondeur 5 (lisible,
# à but pédagogique) ; arbre et forêt : feuilles d'au moins 100 / 50 clients pour limiter le
# surapprentissage sur un signal faible.
DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "logreg": {"C": 0.01, "l1_ratio": 0.0, "dedupe_missing": True},   # finaliste E8 (D69)
    "decision_tree": {"max_depth": 5, "min_samples_leaf": 100},
    "random_forest": {"n_estimators": 300, "min_samples_leaf": 50, "max_features": "sqrt"},
    "lightgbm": {},
    "catboost": {"iterations": 500, "verbose": 0},
}


class NumericPassthrough:
    """Sélecteur : toutes les colonnes numériques (NaN laissés en place)."""

    def __call__(self, X: pd.DataFrame) -> list[str]:
        return list(X.select_dtypes("number").columns)


def categories_as_object(X: pd.DataFrame) -> pd.DataFrame:
    """Catégorielles -> objets Python, NaN conservés (``OrdinalEncoder`` les garde en NaN)."""
    return X.astype(object).where(X.notna(), np.nan)


def tree_preprocessor() -> ColumnTransformer:
    """Numériques telles quelles (NaN compris), catégorielles en codes ordinaux."""
    ordinal = Pipeline([
        ("object", FunctionTransformer(categories_as_object, feature_names_out="one-to-one")),
        ("ordinal", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                                   encoded_missing_value=np.nan)),
    ])
    return ColumnTransformer([("num", "passthrough", NumericPassthrough()),
                              ("cat", ordinal, CategoricalColumns())],
                             verbose_feature_names_out=False)


class CatBoostWithCategories(ClassifierMixin, BaseEstimator):
    """CatBoost avec ses catégorielles natives, détectées à partir du type ``category``.

    CatBoost exige des catégorielles en texte sans NaN : elles sont converties et les NaN
    deviennent « Manquant ». Les NaN numériques sont gérés nativement.
    """

    def __init__(self, random_state: int | None = None, **params: Any) -> None:
        self.random_state = random_state
        self.params = params

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {"random_state": self.random_state, **self.params}

    def set_params(self, **params: Any) -> CatBoostWithCategories:
        self.random_state = params.pop("random_state", self.random_state)
        self.params.update(params)
        return self

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        for col in self.cat_features_:
            X[col] = X[col].astype(object).where(X[col].notna(), MISSING_CATEGORY).astype(str)
        return X

    def fit(self, X: pd.DataFrame, y: pd.Series) -> CatBoostWithCategories:
        self.cat_features_ = list(X.select_dtypes("category").columns)
        self.model_ = CatBoostClassifier(random_seed=self.random_state, allow_writing_files=False,
                                         **self.params)
        self.model_.fit(self._prepare(X), y, cat_features=self.cat_features_)
        self.classes_ = np.array(self.model_.classes_)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model_.predict_proba(self._prepare(X))

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def build_pipeline(model_name: str, groups: Sequence[str] | None = None,
                   neutralize_leak: bool = False, **params: Any) -> BaseEstimator:
    """Construit un modèle non ajusté à partir de son nom.

    Args:
        model_name: un nom de ``MODEL_NAMES``.
        groups: familles de features (``None`` = celles de la config).
        neutralize_leak: si vrai, les colonnes « déjà parti » (bloc d'usage, ``change_*``)
            sont imputées par leur médiane en tête de pipeline (test de fuite D32, E8).
        **params: hyperparamètres du modèle, qui complètent ou remplacent ``DEFAULT_PARAMS``.

    Raises:
        ValueError: nom de modèle inconnu, ou neutralisation demandée pour une baseline.
    """
    if model_name not in MODEL_NAMES:
        raise ValueError(f"Modèle inconnu : {model_name} ; disponibles : {MODEL_NAMES}")
    if neutralize_leak and model_name in BASELINES:
        raise ValueError("La neutralisation ne s'applique qu'aux modèles appris sur les features.")
    cfg = get_config()
    seed = cfg.random_state
    groups = cfg.features.groups if groups is None else list(groups)
    merged = {**DEFAULT_PARAMS.get(model_name, {}), **params}
    features = FeatureBuilder(groups, drop_columns=non_feature_columns())

    if model_name == "dummy":
        return make_dummy(seed)
    if model_name == "rules":
        return SegmentRateClassifier()
    if model_name == "logreg_simple":
        pipeline = make_logreg_pipeline(groups, load_logreg_drop_list())
    elif model_name == "logreg":
        pipeline = make_improved_logreg_pipeline(groups, load_logreg_drop_list(), **merged)
    elif model_name == "decision_tree":
        pipeline = Pipeline([("features", features), ("preprocess", tree_preprocessor()),
                             ("model", DecisionTreeClassifier(random_state=seed, **merged))])
    elif model_name == "random_forest":
        model = RandomForestClassifier(random_state=seed, n_jobs=-1, **merged)
        pipeline = Pipeline([("features", features), ("preprocess", tree_preprocessor()),
                             ("model", model)])
    elif model_name == "lightgbm":
        model = LGBMClassifier(random_state=seed, verbose=-1, n_jobs=-1, **merged)
        pipeline = Pipeline([("features", features), ("model", model)])
    else:
        model = CatBoostWithCategories(random_state=seed, **merged)
        pipeline = Pipeline([("features", features), ("model", clone(model))])
    if neutralize_leak:
        pipeline = Pipeline([("neutralize", LeakNeutralizer()), *pipeline.steps])
    return pipeline
