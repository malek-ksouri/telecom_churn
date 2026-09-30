"""Réglage des hyperparamètres de LightGBM avec Optuna (E9).

- Évaluation de chaque essai sur les **folds figés de E6** (train uniquement), par AUC moyenne.
- Sampler TPE (graine 42) : il propose les essais suivants là où les précédents ont bien marché.
- Pruning (``MedianPruner``) : l'AUC est rapportée après chaque fold ; un essai dont l'AUC
  cumulée est sous la médiane des essais précédents au même fold est arrêté.
- Pas d'arrêt précoce (*early stopping*) sur le fold de validation : il choisirait le
  nombre d'arbres en regardant les données qui servent à l'évaluer (estimation optimiste).
  ``n_estimators`` est donc un hyperparamètre de l'espace de recherche.

Choisir les hyperparamètres sur les folds qui servent aussi à les évaluer rend l'AUC de CV
légèrement optimiste : le jugement final se fait sur le jeu de test (lu une seule fois).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import optuna
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score

from churn.config import get_config
from churn.evaluation.cv import Folds
from churn.models.factory import build_pipeline

logger = logging.getLogger(__name__)


def suggest_lightgbm_params(trial: optuna.Trial) -> dict[str, Any]:
    """Espace de recherche de LightGBM.

    Bornes choisies pour un signal faible sur 64 000 clients par fold : feuilles assez
    peuplées (``min_child_samples`` jusqu'à 500), régularisation L1 / L2, sous-échantillonnage
    des lignes et des colonnes, qui réduisent l'écart train-validation (0,077 par défaut).
    """
    return {
        "num_leaves": trial.suggest_int("num_leaves", 8, 128, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 500, log=True),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=50),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "subsample_freq": 1,                  # nécessaire pour activer le sous-échantillonnage
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
    }


def make_objective(X: pd.DataFrame, y: pd.Series, folds: Folds):
    """Objectif Optuna : AUC moyenne de validation sur les folds, avec pruning par fold.

    L'AUC d'apprentissage et l'écart train-validation sont enregistrés comme attributs de
    l'essai (suivi du surapprentissage).
    """

    def objective(trial: optuna.Trial) -> float:
        params = suggest_lightgbm_params(trial)
        pipeline = build_pipeline("lightgbm", **params)
        valid_aucs, train_aucs = [], []
        for step, (train_idx, valid_idx) in enumerate(folds):
            model = clone(pipeline).fit(X.iloc[train_idx], y.iloc[train_idx])
            valid_aucs.append(roc_auc_score(y.iloc[valid_idx],
                                            model.predict_proba(X.iloc[valid_idx])[:, 1]))
            train_aucs.append(roc_auc_score(y.iloc[train_idx],
                                            model.predict_proba(X.iloc[train_idx])[:, 1]))
            trial.report(float(np.mean(valid_aucs)), step)
            if trial.should_prune():
                trial.set_user_attr("folds_evalues", step + 1)
                raise optuna.TrialPruned()
        gap = float(np.mean(train_aucs) - np.mean(valid_aucs))
        trial.set_user_attr("auc_std", float(np.std(valid_aucs, ddof=1)))
        trial.set_user_attr("train_auc", float(np.mean(train_aucs)))
        trial.set_user_attr("ecart_train_validation", gap)
        trial.set_user_attr("folds_evalues", len(folds))
        return float(np.mean(valid_aucs))

    return objective


def tune_lightgbm(X: pd.DataFrame, y: pd.Series, folds: Folds, n_trials: int = 50,
                  random_state: int | None = None) -> optuna.Study:
    """Lance l'étude Optuna (TPE, graine fixe, pruning médian) et la renvoie."""
    seed = get_config().random_state if random_state is None else random_state
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1),
        study_name="lightgbm_auc",
    )
    study.optimize(make_objective(X, y, folds), n_trials=n_trials)
    logger.info("Meilleur essai : %d, AUC %.4f", study.best_trial.number, study.best_value)
    return study


def trials_table(study: optuna.Study) -> pd.DataFrame:
    """Historique des essais : état, AUC, écart train-validation, hyperparamètres."""
    df = study.trials_dataframe(attrs=("number", "value", "state", "params", "user_attrs",
                                       "duration"))
    df.columns = [c.replace("params_", "").replace("user_attrs_", "") for c in df.columns]
    df["duration"] = df["duration"].dt.total_seconds().round(1)
    return df.rename(columns={"value": "auc_cv", "duration": "duree_s"})


def best_params(study: optuna.Study) -> dict[str, Any]:
    """Meilleurs hyperparamètres, prêts pour ``build_pipeline("lightgbm", **params)``."""
    return {**study.best_params, "subsample_freq": 1}
