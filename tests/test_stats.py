"""Tests des fonctions statistiques (données synthétiques)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.evaluation import stats as st


@pytest.fixture
def df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 4000
    months = rng.integers(6, 40, n)
    peak = np.isin(months, [11, 12])                     # effet en pic, non monotone
    churn = (rng.random(n) < np.where(peak, 0.75, 0.4)).astype(int)
    shifted = rng.normal(0, 1, n) + 0.8 * churn          # effet monotone
    return pd.DataFrame({"months": months.astype(float), "shifted": shifted,
                         "noise": rng.normal(0, 1, n), "cat": rng.choice(["a", "b", "c"], n),
                         "rare_flag": np.r_[np.ones(3), np.zeros(n - 3)].astype(int),
                         "churn": churn})


def test_interpret_effect_thresholds() -> None:
    assert [st.interpret_effect(v) for v in (0.05, -0.2, 0.4, 0.6)] == \
        ["négligeable", "faible", "moyen", "fort"]


def test_rank_biserial_sign_and_bounds(df: pd.DataFrame) -> None:
    res = st.mann_whitney_rank_biserial(df["shifted"], df["churn"])
    assert 0.3 < res["effet"] <= 1
    assert res["p_value"] < 1e-10


def test_binary_with_rare_positive_uses_fisher(df: pd.DataFrame) -> None:
    res = st.chi2_cramers_v(df["rare_flag"], df["churn"])
    assert res["test"] == "Fisher exact"
    assert res["n"] == len(df)
    assert 0 <= res["effet"] < 0.1


def test_non_monotone_effect_is_detected(df: pd.DataFrame) -> None:
    table = st.univariate_table(df, "churn", ["months", "shifted", "noise"], ["cat"])
    months = table.loc["months"]
    assert months["interpretation"] == "négligeable"      # l'effet monotone rate le pic
    assert months["ecart_classes_pts"] > 10
    assert months["forme_courbe"] == "non monotone"
    assert months["relation_non_monotone"]
    assert table.loc["noise", "info_mutuelle"] < months["info_mutuelle"]
    assert (table["p_ajustee_holm"] >= table["p_value"]).all()


def test_variable_clusters_and_representatives() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(size=500)
    X = pd.DataFrame({"a": a, "a_copy": a * 2 + 0.01 * rng.normal(size=500),
                      "b": rng.normal(size=500)})
    corr = X.corr(method="spearman")
    groups = st.variable_clusters(corr)
    assert groups["a"] == groups["a_copy"] != groups["b"]
    reps = st.choose_representatives(groups, pd.Series({"a": 0.1, "a_copy": 0.2, "b": 0.0}),
                                     preferred=("a",))
    assert reps.loc["a", "garder"] and not reps.loc["a_copy", "garder"]


def test_vif_matches_definition_and_iteration() -> None:
    rng = np.random.default_rng(1)
    x1, x2 = rng.normal(size=2000), rng.normal(size=2000)
    X = pd.DataFrame({"x1": x1, "x2": x2, "x3": x1 + x2 + 0.05 * rng.normal(size=2000)})
    vif = st.vif_table(X)
    r2 = 1 - np.var(X["x3"] - np.poly1d(np.polyfit(x1 + x2, X["x3"], 1))(x1 + x2)) / X["x3"].var()
    assert vif["x3"] == pytest.approx(1 / (1 - r2), rel=0.05)
    kept, removed = st.iterative_vif(X, threshold=10)
    assert len(removed) == 1 and st.vif_table(X[kept]).max() < 10
