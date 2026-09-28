"""Tests du test de fuite « déjà parti » et de la suppression des indicateurs en double."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.models.factory import build_pipeline
from churn.models.leakage import (
    LEAK_COLUMNS,
    LeakNeutralizer,
    active_client_mask,
    subset_auc_per_fold,
)
from churn.models.preprocessing import duplicate_missing_indicators


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({c: rng.normal(10, 2, 8) for c in LEAK_COLUMNS})
    df.loc[0, ["rev_Mean", "mou_Mean", "change_mou"]] = np.nan     # sans usage
    df.loc[1, "change_mou"] = np.nan                                  # variation absente
    df.loc[2, "rev_Mean"] = np.nan                                    # négatif corrigé par clean()
    df["rev_Mean_was_negative"] = [0, 0, 1, 0, 0, 0, 0, 0]
    return df


def test_neutralizer_learns_median_in_fit_and_removes_nan() -> None:
    df = _frame()
    neutral = LeakNeutralizer().fit(df.iloc[3:])
    out = neutral.transform(df)
    assert not out[list(LEAK_COLUMNS)].isna().any().any()
    assert out.loc[0, "rev_Mean"] == pytest.approx(df["rev_Mean"].iloc[3:].median())


def test_active_mask_ignores_nan_created_by_clean() -> None:
    mask = active_client_mask(_frame())
    assert mask.tolist()[:3] == [False, False, True]


def test_subset_auc_per_fold_uses_only_masked_rows() -> None:
    y = pd.Series([0, 1, 0, 1, 0, 1, 0, 1])
    oof = pd.Series([0.1, 0.9, 0.2, 0.8, 0.9, 0.1, 0.3, 0.7])   # lignes 4 et 5 inversées
    folds = [(np.arange(4, 8), np.arange(0, 4)), (np.arange(0, 4), np.arange(4, 8))]
    everyone = subset_auc_per_fold(oof, y, folds, pd.Series(True, index=y.index))
    keep = pd.Series([True] * 4 + [False, False, True, True])
    without_45 = subset_auc_per_fold(oof, y, folds, keep)
    assert everyone[1] < 1.0 and without_45[1] == 1.0


def test_build_pipeline_prepends_neutralizer_only_on_request() -> None:
    assert build_pipeline("lightgbm", neutralize_leak=True).steps[0][0] == "neutralize"
    assert build_pipeline("lightgbm").steps[0][0] == "features"
    with pytest.raises(ValueError):
        build_pipeline("rules", neutralize_leak=True)


def test_duplicate_indicators_keep_unique_ones() -> None:
    dup = duplicate_missing_indicators(drop=["avg6mou"])
    assert "manquant_avg6mou_bloc" not in dup      # source retirée : indicateur unique
    assert "manquant_truck_bloc" not in dup        # source binaire : pas d'add_indicator
    assert {"manquant_income", "manquant_hnd_webcap"} <= set(dup)
    # sans add_indicator, seules les sources catégorielles restent en double
    assert "manquant_income" not in duplicate_missing_indicators(drop=[], add_indicator=False)
