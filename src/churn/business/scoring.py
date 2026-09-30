"""Scores sans fuite et niveaux de risque High / Medium / Low (E12).

**Scores sans fuite** : un client du train n'est jamais noté par un modèle qui l'a vu.
Pour les 80 000 clients du train, on utilise les prédictions **hors fold** (mêmes 5 folds
que depuis E6, modèle final réentraîné et recalibré sur les 4 autres folds) ; pour les
20 000 clients du test, le modèle final (``models/final_model.joblib``).

**Niveaux** (seuils appris sur les scores hors fold du train, puis figés) :

- ``High`` : les ``capacity`` (10 %) du portefeuille au score le plus élevé, soit ce que
  l'équipe peut contacter ;
- ``Medium`` : les bandes de score suivantes (5 % du portefeuille chacune) tant que leur
  **lift** reste supérieur à ``medium_min_lift`` (1,2) ;
- ``Low`` : le reste ;
- ``Inactif`` : clients sans usage (``mou_Mean`` nul ou non mesuré, D86), traités à part.

Les parts s'entendent sur le **portefeuille réel** : l'échantillon (50 % de churners) est
repondéré au taux réel supposé (hypothèse, 2 % par mois), sinon « les 10 % les plus risqués
de l'échantillon » seraient bien plus extrêmes que les 10 % d'un vrai portefeuille.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline

from churn.config import get_config
from churn.evaluation.calibration import adjust_prior, make_calibrated, population_weights
from churn.evaluation.cv import Folds
from churn.models.factory import build_pipeline
from churn.models.final import FinalChurnModel

logger = logging.getLogger(__name__)

HIGH, MEDIUM, LOW, INACTIVE = "High", "Medium", "Low", "Inactif"
TIERS = [HIGH, MEDIUM, LOW, INACTIVE]
TRAIN_OOF, TEST = "train_oof", "test"


def is_inactive(df: pd.DataFrame) -> pd.Series:
    """Clients inactifs (D86) : aucune minute d'appel (``mou_Mean`` = 0) ou usage non mesuré."""
    mou = df["mou_Mean"]
    return (mou.isna() | mou.eq(0)).rename("inactif")


def raw_pipeline(calibrated: CalibratedClassifierCV) -> Pipeline:
    """Pipeline LightGBM brut d'un modèle calibré (``ensemble=False`` : un seul modèle)."""
    return calibrated.calibrated_classifiers_[0].estimator


def score_frame(calibrated: CalibratedClassifierCV, X: pd.DataFrame, sample_rate: float,
                real_rate: float, partition: str) -> pd.DataFrame:
    """Probabilités brute, calibrée et corrigée vers le taux réel des clients de ``X``."""
    p_cal = calibrated.predict_proba(X)[:, 1]
    return pd.DataFrame({
        "partition": partition,
        "proba_brute": raw_pipeline(calibrated).predict_proba(X)[:, 1],
        "proba_calibree": p_cal,
        "proba_reelle": adjust_prior(p_cal, real_rate, sample_rate),
    }, index=X.index)


@dataclass
class FoldModel:
    """Modèle calibré d'un fold et clients de validation qu'il a notés."""

    fold: int
    valid_index: pd.Index
    calibrated: CalibratedClassifierCV


def out_of_fold_scores(X: pd.DataFrame, y: pd.Series, folds: Folds,
                       real_rate: float | None = None) -> tuple[pd.DataFrame, list[FoldModel]]:
    """Scores hors fold du train avec le modèle final (paramètres et calibration de la config).

    Pour chaque fold : LightGBM + calibration (CV interne) appris sur les 4 autres folds, puis
    appliqués aux clients du fold. La correction de prior utilise le taux de churn des folds
    d'apprentissage.

    Returns:
        (scores de tous les clients du train, modèles de chaque fold pour les calculs SHAP).
    """
    cfg = get_config()
    rate = cfg.business.real_churn_rate.value if real_rate is None else real_rate
    frames, models = [], []
    for i, (train_idx, valid_idx) in enumerate(folds):
        X_tr, y_tr, X_va = X.iloc[train_idx], y.iloc[train_idx], X.iloc[valid_idx]
        calibrated = make_calibrated(build_pipeline(cfg.models.final), cfg.models.calibration,
                                     random_state=cfg.random_state).fit(X_tr, y_tr)
        frame = score_frame(calibrated, X_va, float(y_tr.mean()), rate, TRAIN_OOF)
        frames.append(frame.assign(fold=i))
        models.append(FoldModel(fold=i, valid_index=X_va.index, calibrated=calibrated))
        logger.info("Fold %d : %d clients notés hors fold", i, len(X_va))
    return pd.concat(frames).loc[X.index], models


def final_scores(model: FinalChurnModel, X: pd.DataFrame, partition: str = TEST) -> pd.DataFrame:
    """Scores du modèle final livré (pour des clients qu'il n'a pas vus : le test)."""
    return score_frame(model.calibrated, X, model.sample_rate, model.real_rate,
                       partition).assign(fold=-1)


def band_lift(y: np.ndarray, score: np.ndarray, band: float = 0.05,
              real_rate: float | None = None, sample_rate: float | None = None) -> pd.DataFrame:
    """Lift par bande de score : taux de churn de chaque tranche de ``band`` du portefeuille
    (du score le plus élevé au plus faible) rapporté au taux de base.

    Avec ``real_rate``, les clients sont repondérés vers le portefeuille réel
    (``population_weights``) ; sinon, chaque client compte pour 1 (échantillon brut).

    Returns:
        Une ligne par bande : début et fin (% du portefeuille), effectif, taux de churn, lift
        de la bande, lift cumulé (des clients les plus risqués jusqu'à la fin de la bande) et
        score minimal de la bande.
    """
    y, score = np.asarray(y), np.asarray(score)
    w = (np.ones(len(y)) if real_rate is None
         else population_weights(y, real_rate, sample_rate or float(y.mean())))
    order = np.argsort(-score, kind="stable")
    y, score, w = y[order], score[order], w[order]
    start = (np.cumsum(w) - w) / w.sum()
    n_bands = int(round(1 / band))
    bands = np.minimum((start / band + 1e-9).astype(int), n_bands - 1)
    df = pd.DataFrame({"bande": bands, "y": y, "w": w, "wy": w * y, "score": score})
    out = df.groupby("bande").agg(n=("y", "size"), poids=("w", "sum"), churners=("wy", "sum"),
                                  score_min=("score", "min"))
    base = df["wy"].sum() / df["w"].sum()
    out["taux"] = out["churners"] / out["poids"]
    out["lift"] = out["taux"] / base
    out["lift_cumule"] = (out["churners"].cumsum() / out["poids"].cumsum()) / base
    out["debut_pct"] = 100 * band * out.index
    out["fin_pct"] = 100 * band * (out.index + 1)
    return out[["debut_pct", "fin_pct", "n", "taux", "lift", "lift_cumule", "score_min"]]


@dataclass
class TierThresholds:
    """Seuils de score (probabilité calibrée) des niveaux, appris sur les scores hors fold.

    Attributes:
        high: score minimal d'un client High.
        medium: score minimal d'un client Medium (égal à ``high`` si Medium est vide).
        capacity: part du portefeuille classée High.
        medium_end: part cumulée du portefeuille classée High ou Medium.
        min_lift: lift minimal d'une bande Medium.
        band: largeur des bandes (part du portefeuille).
        real_rate: taux réel supposé ayant servi à repondérer le portefeuille (hypothèse).
    """

    high: float
    medium: float
    capacity: float
    medium_end: float
    min_lift: float
    band: float
    real_rate: float

    def to_dict(self) -> dict[str, float]:
        """Dictionnaire sérialisable (``kpis.json``)."""
        return asdict(self)


def choose_tiers(y: np.ndarray, score: np.ndarray, real_rate: float, sample_rate: float,
                 capacity: float | None = None, min_lift: float | None = None,
                 band: float | None = None) -> tuple[TierThresholds, pd.DataFrame]:
    """Fixe les seuils High / Medium à partir de la capacité et du lift par bande.

    À appeler sur les scores **hors fold des clients actifs** du train : les inactifs forment
    une catégorie à part (D86) et ne consomment pas de capacité de fidélisation.

    Returns:
        (seuils, tableau des bandes avec le niveau de chacune).
    """
    camp = get_config().business.campaign
    capacity = camp.capacity if capacity is None else capacity
    min_lift = camp.medium_min_lift if min_lift is None else min_lift
    band = camp.lift_band if band is None else band
    n_high = int(round(capacity / band))
    if not np.isclose(n_high * band, capacity):
        raise ValueError(f"La capacité ({capacity}) doit être un multiple de la bande ({band})")
    table = band_lift(y, score, band, real_rate, sample_rate)
    end = n_high
    while end < len(table) and table["lift"].iloc[end] > min_lift:
        end += 1
    high = float(table["score_min"].iloc[n_high - 1])
    medium = float(table["score_min"].iloc[end - 1])
    table["niveau"] = [HIGH if i < n_high else MEDIUM if i < end else LOW
                       for i in range(len(table))]
    thresholds = TierThresholds(high=high, medium=medium, capacity=capacity,
                                medium_end=end * band, min_lift=min_lift, band=band,
                                real_rate=real_rate)
    logger.info("Seuils : High >= %.4f (%.0f %%), Medium >= %.4f (jusqu'à %.0f %%)", high,
                100 * capacity, medium, 100 * end * band)
    return thresholds, table


def assign_tiers(score: pd.Series, inactive: pd.Series, thresholds: TierThresholds) -> pd.Series:
    """Niveau de chaque client : Inactif d'abord, puis High / Medium / Low selon les seuils."""
    tier = np.select([inactive.to_numpy(), score.to_numpy() >= thresholds.high,
                      score.to_numpy() >= thresholds.medium], [INACTIVE, HIGH, MEDIUM], LOW)
    return pd.Series(pd.Categorical(tier, categories=TIERS), index=score.index, name="niveau")
