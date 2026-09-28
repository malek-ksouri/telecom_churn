"""Métriques d'évaluation d'un score de churn.

- Classement : ROC-AUC (probabilité qu'un churner soit mieux classé qu'un non-churner),
  PR-AUC (précision moyenne, sensible au haut du classement).
- Ciblage à capacité fixe : on contacte les k % de clients les mieux classés ;
  Precision@k (part de churners contactés), Recall@k (part des churners atteints),
  lift@k (Precision@k / taux de churn de base : combien de fois mieux que le hasard).
- Calibration : score de Brier (erreur quadratique moyenne des probabilités).

Sur l'échantillon équilibré (~50 %), lift@k est borné par 1 / 0,5 = 2 ; Precision@k et
Brier sont ceux de l'échantillon, pas d'un opérateur réel (correction du prior en E10).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

K_VALUES: tuple[float, ...] = (0.05, 0.10, 0.20)


def roc_auc(y: np.ndarray, score: np.ndarray) -> float:
    """Aire sous la courbe ROC."""
    return float(roc_auc_score(y, score))


def pr_auc(y: np.ndarray, score: np.ndarray) -> float:
    """Aire sous la courbe précision-rappel (précision moyenne)."""
    return float(average_precision_score(y, score))


def brier(y: np.ndarray, proba: np.ndarray) -> float:
    """Score de Brier : moyenne de (p - y)² ; 0 = parfait, 0,25 = toujours 0,5."""
    return float(brier_score_loss(y, proba))


def _top_k(score: np.ndarray, k: float) -> np.ndarray:
    """Indices des ``ceil(k * n)`` clients au score le plus élevé (tri stable)."""
    n_top = int(np.ceil(k * len(score)))
    return np.argsort(-np.asarray(score), kind="stable")[:n_top]


def precision_at_k(y: np.ndarray, score: np.ndarray, k: float) -> float:
    """Part de churners parmi les k % de clients les mieux classés."""
    return float(np.asarray(y)[_top_k(score, k)].mean())


def recall_at_k(y: np.ndarray, score: np.ndarray, k: float) -> float:
    """Part de tous les churners qui se trouvent dans les k % les mieux classés."""
    y = np.asarray(y)
    return float(y[_top_k(score, k)].sum() / y.sum())


def lift_at_k(y: np.ndarray, score: np.ndarray, k: float) -> float:
    """Precision@k divisée par le taux de churn de base."""
    return precision_at_k(y, score, k) / float(np.mean(y))


def compute_metrics(y: np.ndarray, proba: np.ndarray,
                    ks: tuple[float, ...] = K_VALUES) -> dict[str, float]:
    """Toutes les métriques d'un score sur un jeu de validation."""
    out = {"roc_auc": roc_auc(y, proba), "pr_auc": pr_auc(y, proba), "brier": brier(y, proba)}
    for k in ks:
        tag = f"{round(100 * k)}"
        out[f"lift@{tag}%"] = lift_at_k(y, proba, k)
        out[f"precision@{tag}%"] = precision_at_k(y, proba, k)
        out[f"recall@{tag}%"] = recall_at_k(y, proba, k)
    return out


def summarize_folds(per_fold: pd.DataFrame) -> pd.DataFrame:
    """Moyenne et écart-type de chaque métrique sur les folds."""
    numeric = per_fold.drop(columns=["fold"], errors="ignore")
    return pd.DataFrame({"moyenne": numeric.mean(), "ecart_type": numeric.std()})


def evaluate_on_folds(pipeline, X: pd.DataFrame, y: pd.Series, folds) -> dict[str, pd.DataFrame]:
    """Toutes les métriques d'un modèle sur les folds figés : par fold et résumé (moyenne ± σ).

    Délègue l'entraînement à ``churn.models.train.cross_validate_model``.
    """
    from churn.models.train import cross_validate_model

    result = cross_validate_model(pipeline, X, y, folds)
    return {"par_fold": result.per_fold, "resume": summarize_folds(result.per_fold)}
