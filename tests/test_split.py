"""Tests du split train/test : tailles, taux de churn, absence d'identifiants communs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.config import get_config
from churn.data.split import load_test, load_train, split_train_test

CFG = get_config()


@pytest.fixture(scope="module")
def splits() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not (CFG.train_path.is_file() and CFG.test_path.is_file()):
        pytest.skip("Partitions absentes : lancer `make data`")
    # Lecture du test autorisée ici : on ne contrôle que l'intégrité du split, sans analyse.
    return load_train(), load_test(final_evaluation=True)


def test_sizes(splits: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    train, test = splits
    n = len(train) + len(test)
    assert n == 100_000
    assert len(test) == round(n * CFG.data.test_size)


def test_churn_rate_is_stratified(splits: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    train, test = splits
    target = CFG.data.target
    # Stratifié : écart au plus d'un client sur le plus petit jeu.
    assert abs(train[target].mean() - test[target].mean()) <= 1 / len(test)


def test_no_common_customer_id(splits: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    train, test = splits
    ids_train, ids_test = set(train[CFG.data.id_col]), set(test[CFG.data.id_col])
    assert ids_train.isdisjoint(ids_test)
    assert len(ids_train) + len(ids_test) == len(train) + len(test)


def test_categories_survive_parquet(splits: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    train, _ = splits
    assert isinstance(train["marital"].dtype, pd.CategoricalDtype)
    assert "Unknown" in train["marital"].cat.categories


def test_split_is_reproducible() -> None:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({CFG.data.id_col: range(1000), CFG.data.target: rng.integers(0, 2, 1000)})
    a_train, _ = split_train_test(df)
    b_train, _ = split_train_test(df)
    pd.testing.assert_frame_equal(a_train, b_train)


def test_load_test_requires_confirmation() -> None:
    with pytest.raises(PermissionError):
        load_test()
