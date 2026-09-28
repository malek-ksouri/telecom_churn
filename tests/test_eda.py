"""Tests des calculs d'EDA (données synthétiques : pas de dépendance au CSV)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn import eda


@pytest.fixture
def df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 2000
    months = rng.integers(6, 40, n)
    return pd.DataFrame({
        "months": months,
        "mou_Mean": rng.gamma(2, 200, n),
        "eqpdays": rng.integers(0, 1000, n).astype(float),
        "churn": (rng.random(n) < np.where(months.clip(11, 12) == months, 0.7, 0.4)).astype(int),
    })


def test_churn_rate_table_matches_manual_rate(df: pd.DataFrame) -> None:
    group = pd.Series(np.where(df["months"] <= 10, "a", "b"), name="g")
    table = eda.churn_rate_table(df, group)
    assert table["n"].sum() == len(df)
    expected = 100 * df.loc[df["months"] <= 10, "churn"].mean()
    assert table.loc["a", "taux"] == pytest.approx(expected, abs=0.01)
    assert (table["ic_bas"] <= table["taux"]).all() and (table["taux"] <= table["ic_haut"]).all()


def test_churn_rate_table_keeps_missing_group(df: pd.DataFrame) -> None:
    s = df["eqpdays"].copy()
    s.iloc[:10] = np.nan
    table = eda.churn_rate_table(df, eda.decile_bins(s))
    assert table.loc[eda.MISSING_LABEL, "n"] == 10
    assert table.index[-1] == eda.MISSING_LABEL


def test_numeric_groups_sorted_numerically(df: pd.DataFrame) -> None:
    table = eda.churn_rate_table(df, df["months"])
    assert list(table.index) == sorted(table.index)


def test_decile_bins_has_ten_classes(df: pd.DataFrame) -> None:
    assert eda.decile_bins(df["mou_Mean"]).cat.categories.size == 10


def test_credit_class_groups_rare_letters() -> None:
    codes = pd.Series(["A"] * 60 + ["AA"] * 30 + ["B"] * 9 + ["Z"])
    groups = eda.credit_class(codes, min_share=0.05)
    assert set(groups) == {"A", "B", "Autres"}


def test_segments_cover_all_complete_rows(df: pd.DataFrame) -> None:
    table = eda.segment_table(df, eda.business_segments(df))
    assert table["n"].sum() == len(df)
    assert table["taux"].is_monotonic_decreasing
