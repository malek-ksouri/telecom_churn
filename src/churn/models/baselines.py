"""Modèles de référence : plancher aléatoire et benchmark par règles métier (E4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.dummy import DummyClassifier

from churn.config import get_config
from churn.eda import business_segments, rule_segment_labels


class SegmentRateClassifier(ClassifierMixin, BaseEstimator):
    """Score d'un client = taux de churn de son segment « ancienneté x usage x terminal ».

    Les segments sont les règles fixes de E4 ; le **taux de chaque segment est appris dans
    fit**, donc recalculé sur la seule partie apprentissage de chaque fold. Un segment absent
    de l'apprentissage reçoit le taux global.
    """

    def fit(self, X: pd.DataFrame, y: pd.Series) -> SegmentRateClassifier:
        """Apprend le taux de churn de chaque segment."""
        segments = rule_segment_labels(business_segments(X))
        y = pd.Series(np.asarray(y), index=X.index)
        self.rates_ = y.groupby(segments).mean()
        self.global_rate_ = float(y.mean())
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Probabilité = taux du segment appris."""
        segments = rule_segment_labels(business_segments(X))
        p = segments.map(self.rates_).fillna(self.global_rate_).to_numpy(dtype=float)
        return np.column_stack([1 - p, p])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Classe 1 si le taux du segment dépasse 0,5."""
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def make_dummy(random_state: int | None = None) -> DummyClassifier:
    """Plancher : prédictions tirées au hasard selon la répartition des classes (AUC ≈ 0,5)."""
    seed = get_config().random_state if random_state is None else random_state
    return DummyClassifier(strategy="stratified", random_state=seed)
