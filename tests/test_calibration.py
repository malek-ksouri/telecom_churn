"""Tests de la calibration et de la correction vers le taux réel (E10)."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from churn.evaluation import calibration as cal
from churn.models.final import FinalChurnModel


def test_adjust_prior_formula_and_fixed_points() -> None:
    # p = s : la probabilité devient le taux réel ; odds multipliés par une constante
    assert cal.adjust_prior(np.array([0.5]), 0.02, 0.5)[0] == pytest.approx(0.02)
    p = np.array([0.2, 0.7])
    out = cal.adjust_prior(p, 0.02, 0.5)
    ratio = (out / (1 - out)) / (p / (1 - p))
    assert ratio == pytest.approx(np.full(2, 0.02 / 0.98))
    assert np.array_equal(cal.adjust_prior(p, 0.3, 0.3), cal.adjust_prior(p, 0.3, 0.3))


def test_adjust_prior_is_monotone_so_auc_unchanged() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 500)
    p = np.clip(0.5 + 0.2 * (y - 0.5) + rng.normal(0, 0.2, 500), 0.001, 0.999)
    for rate in (0.01, 0.02, 0.03):
        adj = cal.adjust_prior(p, rate, 0.5)
        assert np.all(np.diff(adj[np.argsort(p)]) >= 0)
        assert roc_auc_score(y, adj) == pytest.approx(roc_auc_score(y, p))


def test_adjust_prior_rejects_invalid_rates() -> None:
    with pytest.raises(ValueError):
        cal.adjust_prior(np.array([0.5]), 0.0, 0.5)


def test_ece_is_zero_for_perfect_calibration_and_positive_otherwise() -> None:
    rng = np.random.default_rng(1)
    p = rng.random(20_000)
    y = (rng.random(20_000) < p).astype(int)
    assert cal.expected_calibration_error(y, p) < 0.02
    assert cal.expected_calibration_error(y, np.clip(p + 0.2, 0, 1)) > 0.1


def test_production_precision_matches_reweighted_population() -> None:
    # Score parfait : le top 10 % d'une population à 2 % de churn ne contient que...
    # des churners jusqu'à épuisement (2 % < 10 %), donc précision = 2 / 10 = 0,2.
    y = np.r_[np.ones(500), np.zeros(500)].astype(int)
    score = np.r_[np.linspace(1, 0.6, 500), np.linspace(0.5, 0, 500)]
    prec = cal.production_precision_at_k(y, score, real_rate=0.02, sample_rate=0.5, k=0.10)
    assert prec == pytest.approx(0.2, abs=0.01)
    mask = cal.top_k_mask_weighted(y, score, 0.02, 0.5, 0.10)
    assert cal.weighted_mean(y, y, 0.02, 0.5, mask) == pytest.approx(prec, abs=1e-9)
    assert cal.weighted_mean(y, y, 0.02, 0.5) == pytest.approx(0.02)


def test_final_model_real_probability_uses_prior() -> None:
    rng = np.random.default_rng(2)
    X = rng.normal(size=(400, 2))
    y = (X[:, 0] + rng.normal(0, 1, 400) > 0).astype(int)
    calibrated = cal.make_calibrated(LogisticRegression(), "sigmoid", inner_folds=3).fit(X, y)
    model = FinalChurnModel(calibrated=calibrated, method="sigmoid", sample_rate=float(y.mean()),
                            real_rate=0.02)
    p_sample, p_real = model.proba_sample(X), model.proba_real(X)
    assert np.allclose(p_real, cal.adjust_prior(p_sample, 0.02, float(y.mean())))
    assert p_real.mean() < 0.1 < p_sample.mean()
    assert model.predict_proba(X).shape == (400, 2)
