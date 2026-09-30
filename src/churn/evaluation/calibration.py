"""Calibration des probabilités et correction vers le taux de churn réel (E10).

Deux problèmes distincts :

1. **Calibration** : un score peut bien classer les clients (bonne AUC) sans que « 0,7 »
   signifie « 70 % de churners parmi les clients notés 0,7 ». On la mesure par la courbe de
   fiabilité, le score de Brier et l'ECE, et on la corrige par une calibration sigmoïde
   (Platt) ou isotonique, apprise sur des prédictions hors échantillon.
2. **Prior** : l'échantillon est équilibré (~50 % de churners) alors que le taux réel d'un
   opérateur est de l'ordre de 2 % par mois (**hypothèse**, D47). Une probabilité bien
   calibrée sur l'échantillon doit être ramenée au taux réel par la formule de Bayes
   (``adjust_prior``). Cette correction est **monotone** : le classement, donc l'AUC,
   ne change pas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold

EPS = 1e-9


def adjust_prior(p: np.ndarray, real_rate: float, sample_rate: float = 0.5) -> np.ndarray:
    """Ramène des probabilités calibrées sur l'échantillon au taux de churn réel.

    Les rapports de chances (*odds*) sont multipliés par le rapport des odds de base :

    p' = p·(r/s) / [p·(r/s) + (1 - p)·((1 - r)/(1 - s))]

    avec r = taux réel, s = taux de l'échantillon. Transformation strictement croissante :
    le classement des clients est inchangé.

    Args:
        p: probabilités calibrées sur l'échantillon (entre 0 et 1).
        real_rate: taux de churn réel supposé (hypothèse, ex. 0,02 par mois).
        sample_rate: taux de churn de l'échantillon d'apprentissage.
    """
    if not (0 < real_rate < 1 and 0 < sample_rate < 1):
        raise ValueError("real_rate et sample_rate doivent être dans ]0 ; 1[")
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    num = p * (real_rate / sample_rate)
    return num / (num + (1 - p) * ((1 - real_rate) / (1 - sample_rate)))


def population_weights(y: np.ndarray, real_rate: float, sample_rate: float) -> np.ndarray:
    """Poids qui transforment l'échantillon équilibré en portefeuille au taux réel.

    Churners : r/s ; non-churners : (1 - r)/(1 - s). La moyenne pondérée de ``y`` vaut
    alors exactement ``real_rate`` ; on suppose que les churners (et les non-churners) de
    l'échantillon sont représentatifs de leur classe.
    """
    y = np.asarray(y)
    return np.where(y == 1, real_rate / sample_rate, (1 - real_rate) / (1 - sample_rate))


def reliability_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Courbe de fiabilité : par classe de probabilité prédite (quantiles), probabilité
    moyenne prédite et taux de churn observé."""
    df = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    df["classe"] = pd.qcut(df["p"], q=n_bins, duplicates="drop")
    out = df.groupby("classe", observed=True).agg(n=("y", "size"), p_moyenne=("p", "mean"),
                                                   taux_observe=("y", "mean"))
    return out.reset_index(drop=True)


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """ECE : moyenne pondérée par l'effectif de |probabilité moyenne - taux observé| par classe."""
    table = reliability_table(y, p, n_bins)
    return float((table["n"] * (table["p_moyenne"] - table["taux_observe"]).abs()).sum()
                 / table["n"].sum())


def make_calibrated(estimator: BaseEstimator, method: str, inner_folds: int = 5,
                    random_state: int = 42) -> CalibratedClassifierCV:
    """Modèle calibré : le calibrateur est appris sur des prédictions hors fold (CV interne).

    ``ensemble=False`` : le modèle de base est réentraîné sur **toutes** les données
    d'apprentissage reçues, et un seul calibrateur est appris sur ses prédictions hors fold ;
    on garde ainsi un seul modèle (celui de E9), et une calibration sigmoïde (monotone)
    conserve exactement son classement.
    """
    inner = StratifiedKFold(inner_folds, shuffle=True, random_state=random_state)
    return CalibratedClassifierCV(estimator, method=method, cv=inner, ensemble=False)


def production_precision_at_k(y: np.ndarray, score: np.ndarray, real_rate: float,
                              sample_rate: float, k: float = 0.10) -> float:
    """Precision@k attendue sur une population au taux de churn ``real_rate``.

    Les clients sont repondérés (churners : r/s, non-churners : (1 - r)/(1 - s)) pour
    simuler la population réelle, en supposant que les churners et non-churners de
    l'échantillon sont représentatifs de leur classe. On cible les k % de cette
    population au score le plus élevé.
    """
    y = np.asarray(y)
    order = np.argsort(-np.asarray(score), kind="stable")
    w = population_weights(y, real_rate, sample_rate)[order]
    cum_w = np.cumsum(w)
    top = cum_w <= k * w.sum()
    return float((w[top] * y[order][top]).sum() / w[top].sum())


def weighted_mean(values: np.ndarray, y: np.ndarray, real_rate: float,
                  sample_rate: float, mask: np.ndarray | None = None) -> float:
    """Moyenne de ``values`` sur la population repondérée au taux réel (éventuellement filtrée)."""
    y = np.asarray(y)
    w = population_weights(y, real_rate, sample_rate)
    if mask is not None:
        values, w = np.asarray(values)[mask], w[mask]
    return float(np.average(values, weights=w))


def top_k_mask_weighted(y: np.ndarray, score: np.ndarray, real_rate: float,
                        sample_rate: float, k: float = 0.10) -> np.ndarray:
    """Masque des clients qui forment les k % les plus risqués de la population repondérée."""
    y = np.asarray(y)
    order = np.argsort(-np.asarray(score), kind="stable")
    w = population_weights(y, real_rate, sample_rate)[order]
    mask = np.zeros(len(y), dtype=bool)
    mask[order[np.cumsum(w) <= k * w.sum()]] = True
    return mask
