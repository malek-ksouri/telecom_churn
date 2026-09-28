"""Tests de build_pipeline : tous les modèles s'ajustent, les arbres gardent les NaN."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.config import get_config
from churn.data.clean import clean
from churn.data.load import load_raw
from churn.models.factory import MODEL_NAMES, build_pipeline, tree_preprocessor

pytestmark = pytest.mark.skipif(not get_config().raw_path.is_file(), reason="CSV brut absent")


@pytest.fixture(scope="module")
def sample() -> tuple[pd.DataFrame, pd.Series]:
    df = clean(load_raw(nrows=3000))
    return df, df[get_config().data.target]


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_every_model_fits_and_predicts(sample: tuple[pd.DataFrame, pd.Series], name: str) -> None:
    X, y = sample
    params = {"iterations": 20} if name == "catboost" else {}
    params |= {"n_estimators": 20} if name == "random_forest" else {}
    model = build_pipeline(name, **params).fit(X.iloc[:2000], y.iloc[:2000])
    proba = model.predict_proba(X.iloc[2000:])
    assert proba.shape == (1000, 2)
    assert np.isfinite(proba).all() and ((proba >= 0) & (proba <= 1)).all()


def test_tree_preprocessing_keeps_nan(sample: tuple[pd.DataFrame, pd.Series]) -> None:
    X, _ = sample
    pipe = build_pipeline("random_forest", n_estimators=5)
    built = pipe.named_steps["features"].transform(X)
    out = tree_preprocessor().fit(built).transform(built)
    assert np.isnan(out).any()                              # NaN transmis au modèle
    assert out.shape[1] == built.shape[1]                   # aucune colonne ajoutée ni retirée


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="inconnu"):
        build_pipeline("svm")
