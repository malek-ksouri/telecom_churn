"""Modèle final livrable : LightGBM calibré + correction vers le taux de churn réel (E10).

Ce qui est sauvegardé dans ``models/final_model.joblib`` et chargé par l'API (E13).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV

from churn.evaluation.calibration import adjust_prior


@dataclass
class FinalChurnModel:
    """Modèle calibré et hypothèse de taux réel.

    Attributes:
        calibrated: pipeline LightGBM calibré (``CalibratedClassifierCV``, ajusté sur le train).
        method: méthode de calibration (``sigmoid`` ou ``isotonic``).
        sample_rate: taux de churn de l'échantillon d'apprentissage (~0,496).
        real_rate: taux de churn réel supposé (**hypothèse**, 2 % par mois, D47).
        trained_at: date d'entraînement.
    """

    calibrated: CalibratedClassifierCV
    method: str
    sample_rate: float
    real_rate: float
    trained_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="minutes"))

    def proba_sample(self, X: pd.DataFrame) -> np.ndarray:
        """Probabilité calibrée **sur l'échantillon équilibré** (sert au classement)."""
        return self.calibrated.predict_proba(X)[:, 1]

    def proba_real(self, X: pd.DataFrame, real_rate: float | None = None) -> np.ndarray:
        """Probabilité ramenée au taux réel supposé (``real_rate`` par défaut : celui du modèle)."""
        rate = self.real_rate if real_rate is None else real_rate
        return adjust_prior(self.proba_sample(X), rate, self.sample_rate)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Interface sklearn : probabilités au taux réel, colonnes (non-churn, churn)."""
        p = self.proba_real(X)
        return np.column_stack([1 - p, p])
