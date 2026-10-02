"""Contrôles de finalisation (E18) : pas de fuite dans les imputations, inférence du modèle livré.

Le test n'est lu ici que pour **comparer** des statistiques (aucun ajustement, aucune
décision), comme dans ``test_split.py``.
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.impute import SimpleImputer

from churn.config import get_config
from churn.data.split import load_test, load_train
from churn.segmentation import kmeans as km


@pytest.fixture(scope="module")
def splits() -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = get_config()
    if not (cfg.train_path.is_file() and cfg.test_path.is_file()):
        pytest.skip("Partitions absentes : lancer `make data`")
    return load_train(), load_test(final_evaluation=True)


def _imputers(preprocessor) -> dict[str, tuple[SimpleImputer, list[str]]]:
    """Imputeurs médians du préprocesseur de segmentation, avec leurs colonnes."""
    out = {}
    for name, transformer, columns in preprocessor.transformers_:
        if isinstance(transformer, SimpleImputer):
            out[name] = (transformer, list(columns))
        elif hasattr(transformer, "named_steps") and "impute" in transformer.named_steps:
            out[name] = (transformer.named_steps["impute"], list(columns))
    return out


def _assert_train_statistics_only(preprocessor, train: pd.DataFrame, test: pd.DataFrame) -> None:
    imputers = _imputers(preprocessor)
    assert set(imputers) == {"log", "signed_log", "raw"}
    leaked = pd.concat([train, test])
    discriminant = 0
    for imputer, columns in imputers.values():
        train_median = train[columns].astype(float).median().to_numpy()
        np.testing.assert_allclose(imputer.statistics_, train_median)
        all_median = leaked[columns].astype(float).median().to_numpy()
        discriminant += int((~np.isclose(train_median, all_median)).sum())
    # Le contrôle n'a de sens que si train et train + test ont des médianes différentes.
    assert discriminant >= 1


def test_segmentation_imputers_learn_train_statistics_only(
        splits: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Préprocesseur ajusté sur le train : médianes du train, pas celles de train + test."""
    train, test = splits
    target = get_config().data.target
    preprocessor = km.build_preprocessor().fit(train.drop(columns=[target]))
    _assert_train_statistics_only(preprocessor, train, test)


def test_delivered_segmentation_was_fitted_on_train_only(
        splits: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Même contrôle sur l'artefact livré (``models/segmentation.joblib``)."""
    path = get_config().paths.models_dir / km.SEGMENTATION_FILE
    if not path.is_file():
        pytest.skip("Segmentation absente : lancer `make train`")
    train, test = splits
    _assert_train_statistics_only(km.load_segmentation(path)["pipeline"]["preprocess"], train, test)


@pytest.fixture(scope="module")
def final_model():
    path = get_config().paths.models_dir / "final_model.joblib"
    if not path.is_file():
        pytest.skip("Modèle final absent : lancer `make train`")
    return joblib.load(path)


def test_final_model_learns_no_imputation(final_model) -> None:
    """LightGBM gère les manquants nativement : aucune statistique d'imputation n'est apprise."""
    for fitted in final_model.calibrated.calibrated_classifiers_:
        params = fitted.estimator.get_params(deep=True).values()
        assert not any(isinstance(p, SimpleImputer) for p in params)


def test_final_model_inference_probabilities(final_model) -> None:
    """Inférence sur des clients du train : probabilités dans [0, 1] et classement conservé."""
    X = load_train().sample(1_000, random_state=get_config().random_state)
    p_sample = final_model.proba_sample(X)
    p_real = final_model.proba_real(X)
    proba = final_model.predict_proba(X)

    for p in (p_sample, p_real):
        assert np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()
    assert proba.shape == (len(X), 2)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)
    # Taux réel supposé (2 %) bien inférieur à celui de l'échantillon : probabilités plus basses,
    # même ordre (correction monotone).
    assert (p_real < p_sample).all()
    assert (np.argsort(p_real, kind="stable") == np.argsort(p_sample, kind="stable")).all()
    assert 0.0 < p_real.mean() < 0.1
