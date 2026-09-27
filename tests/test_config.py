"""Tests de la configuration et du chargement des données brutes."""

from __future__ import annotations

import pytest

from churn.config import get_config
from churn.data.load import load_raw


def test_config_values() -> None:
    cfg = get_config()
    assert cfg.random_state == 42
    assert cfg.data.test_size == 0.2
    assert cfg.modeling.cv_folds == 5
    assert cfg.business.real_churn_rate.is_hypothesis is True


def test_paths_are_absolute() -> None:
    cfg = get_config()
    assert cfg.root.is_absolute()
    assert all(p.is_absolute() for p in cfg.paths.model_dump().values())


def test_excluded_columns() -> None:
    cols = get_config().non_feature_columns
    assert {"Customer_ID", "ethnic", "churn"} <= set(cols)


@pytest.mark.skipif(not get_config().raw_path.is_file(), reason="CSV brut absent")
def test_load_raw_sample() -> None:
    df = load_raw(nrows=100)
    assert len(df) == 100
    assert {"Customer_ID", "churn"} <= set(df.columns)
