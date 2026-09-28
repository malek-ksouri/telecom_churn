"""Tests des métriques, du prétraitement de la LR améliorée, des baselines et de la CV."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from churn.evaluation import metrics as m
from churn.models.baselines import SegmentRateClassifier
from churn.models.preprocessing import Winsorizer, log1p_nonneg, signed_log1p
from churn.models.train import cross_validate_model


def test_ranking_metrics_on_known_case() -> None:
    y = np.array([1, 1, 0, 0, 1, 0, 0, 0, 0, 0])
    score = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0])
    assert m.precision_at_k(y, score, 0.2) == 1.0          # 2 premiers : 2 churners
    assert m.recall_at_k(y, score, 0.2) == pytest.approx(2 / 3)
    assert m.lift_at_k(y, score, 0.2) == pytest.approx(1.0 / 0.3)
    assert m.roc_auc(y, score) == pytest.approx(19 / 21)
    assert 0 <= m.brier(y, score) <= 1


def test_compute_metrics_keys() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 500)
    out = m.compute_metrics(y, rng.random(500))
    for k in ("5", "10", "20"):
        assert {f"lift@{k}%", f"precision@{k}%", f"recall@{k}%"} <= set(out)
    assert {"roc_auc", "pr_auc", "brier"} <= set(out)


def test_winsorizer_learns_bounds_in_fit_only() -> None:
    train = np.arange(1, 101, dtype=float).reshape(-1, 1)
    w = Winsorizer(0.01, 0.99).fit(train)
    low, high = w.lower_bounds_[0], w.upper_bounds_[0]
    out = w.transform(np.array([[-1000.0], [50.0], [1e6], [np.nan]]))
    assert out[0, 0] == low and out[2, 0] == high and out[1, 0] == 50.0
    assert np.isnan(out[3, 0])
    w.transform(np.array([[1e9]]))                           # transform n'apprend rien
    assert w.upper_bounds_[0] == high


def test_winsorizer_keeps_rare_indicator() -> None:
    rare = np.r_[np.ones(5), np.zeros(995)].reshape(-1, 1)   # indicateur présent à 0,5 %
    out = Winsorizer(0.01, 0.99).fit_transform(rare)
    assert out.sum() == 5                                     # les 1 ne sont pas écrêtés à 0


def test_log_transforms_keep_nan_and_sign() -> None:
    x = np.array([-10.0, 0.0, 10.0, np.nan])
    assert np.isnan(log1p_nonneg(x)[3]) and log1p_nonneg(x)[0] == 0.0
    assert signed_log1p(x)[0] == pytest.approx(-np.log1p(10))


def _segment_frame(n: int = 600) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(1)
    X = pd.DataFrame({"months": rng.integers(6, 40, n).astype(float),
                      "mou_Mean": rng.gamma(2, 250, n), "eqpdays": rng.integers(0, 900, n) * 1.0})
    y = pd.Series((rng.random(n) < np.where(X["months"].isin([11, 12]), 0.8, 0.4)).astype(int))
    return X, y


def test_segment_rate_classifier_uses_training_rates_only() -> None:
    X, y = _segment_frame()
    model = SegmentRateClassifier().fit(X.iloc[:300], y.iloc[:300])
    proba = model.predict_proba(X.iloc[300:])[:, 1]
    assert proba.shape == (300,) and ((proba >= 0) & (proba <= 1)).all()
    assert set(np.round(proba, 10)) <= set(np.round(model.rates_.to_numpy(), 10)) | {
        round(model.global_rate_, 10)}


def test_cross_validate_model_returns_oof_and_train_auc() -> None:
    X, y = _segment_frame()
    folds = [(np.arange(300, 600), np.arange(0, 300)), (np.arange(0, 300), np.arange(300, 600))]
    result = cross_validate_model(LogisticRegression(), X, y, folds)
    assert result.oof.notna().all()
    assert {"roc_auc", "train_roc_auc", "fit_seconds"} <= set(result.per_fold.columns)
    assert list(result.summary().columns) == ["moyenne", "ecart_type"]
