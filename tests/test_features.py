"""Tests du FeatureBuilder : pas d'inf, lignes conservées, colonnes par famille, sans état."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.features.build import (
    ALL_GROUPS,
    FEATURE_GROUPS,
    NEGATIVE_FLAGS,
    FeatureBuilder,
    safe_divide,
)


@pytest.fixture
def clients() -> pd.DataFrame:
    """Petit jeu couvrant les cas limites : zéros, NaN, négatif neutralisé par clean()."""
    rng = np.random.default_rng(0)
    n = 50
    df = pd.DataFrame({
        "months": rng.integers(6, 30, n).astype(float), "eqpdays": rng.integers(0, 900, n) * 1.0,
        "avg3mou": rng.gamma(2, 100, n), "avg6mou": rng.gamma(2, 100, n),
        "avg3rev": rng.gamma(2, 20, n), "avg6rev": rng.gamma(2, 20, n),
        "drop_blk_Mean": rng.gamma(2, 3, n), "attempt_Mean": rng.gamma(2, 50, n),
        "complete_Mean": rng.gamma(2, 40, n), "custcare_Mean": rng.choice([0.0, 1.0, 3.0], n),
        "mou_Mean": rng.gamma(2, 200, n), "ovrrev_Mean": rng.gamma(1, 5, n),
        "rev_Mean": rng.gamma(2, 25, n), "totmrc_Mean": rng.gamma(2, 20, n),
        "actvsubs": rng.integers(0, 3, n) * 1.0, "uniqsubs": rng.integers(1, 4, n) * 1.0,
        "phones": rng.integers(1, 4, n) * 1.0, "change_mou": rng.normal(0, 50, n),
        "Customer_ID": np.arange(n), "churn": rng.integers(0, 2, n),
    })
    for col in ["numbcars", "dwllsize", "HHstatin", "ownrent", "dwlltype", "lor", "income",
                "adults", "infobase", "hnd_webcap", "prizm_social_one", "truck", "hnd_price",
                "area"]:
        df[col] = rng.choice([1.0, np.nan], n)
    for flag in NEGATIVE_FLAGS:
        df[flag] = np.int8(0)
    # Cas limites : dénominateurs nuls, usage absent, négatif mis à NaN par clean().
    df.loc[0, ["avg6mou", "attempt_Mean", "rev_Mean", "uniqsubs"]] = 0.0
    df.loc[1, ["rev_Mean", "mou_Mean", "change_mou"]] = np.nan
    df.loc[2, "rev_Mean"] = np.nan
    df.loc[2, "rev_Mean_was_negative"] = 1
    return df


def test_safe_divide_never_returns_inf() -> None:
    out = safe_divide(pd.Series([1.0, 1.0, np.nan, 0.0]), pd.Series([0.0, np.nan, 1.0, 2.0]))
    assert out.isna().tolist() == [True, True, True, False]


def test_no_inf_and_same_rows(clients: pd.DataFrame) -> None:
    out = FeatureBuilder(drop_columns=["Customer_ID", "churn"]).fit_transform(clients)
    assert len(out) == len(clients)
    assert (out.index == clients.index).all()
    assert not np.isinf(out.select_dtypes("number").to_numpy()).any()
    assert "Customer_ID" not in out and "churn" not in out


@pytest.mark.parametrize("group", ALL_GROUPS)
def test_columns_follow_active_groups(clients: pd.DataFrame, group: str) -> None:
    out = FeatureBuilder([group]).fit_transform(clients)
    expected = set(FEATURE_GROUPS[group])
    others = {f for g, feats in FEATURE_GROUPS.items() if g != group for f in feats}
    assert expected <= set(out.columns)
    assert not (others - expected) & set(out.columns)


def test_reference_has_no_added_features(clients: pd.DataFrame) -> None:
    out = FeatureBuilder([]).fit_transform(clients)
    assert not set(NEGATIVE_FLAGS) & set(out.columns)
    assert set(out.columns) == set(clients.columns) - set(NEGATIVE_FLAGS)


def test_already_gone_ignores_nan_created_by_clean(clients: pd.DataFrame) -> None:
    out = FeatureBuilder(["deja_parti"]).fit_transform(clients)
    assert out.loc[1, "sans_usage"] == 1          # usage absent dans la source
    assert out.loc[2, "sans_usage"] == 0          # NaN issu d'un négatif corrigé
    assert out.loc[1, "change_manquant"] == 1


def test_contract_end_flag(clients: pd.DataFrame) -> None:
    out = FeatureBuilder(["cycle_engagement"]).fit_transform(clients)
    assert (out["in_contract_end"] == clients["months"].isin([11, 12])).all()
    assert (out["handset_old"] == (clients["eqpdays"] >= 300)).all()


def test_transformer_is_stateless(clients: pd.DataFrame) -> None:
    fb = FeatureBuilder()
    before = dict(fb.__dict__)
    first = fb.transform(clients)                  # utilisable sans fit
    fb.fit(clients.sample(frac=0.5, random_state=1))
    assert fb.__dict__ == before                   # fit n'ajoute aucun attribut appris
    pd.testing.assert_frame_equal(first, fb.transform(clients))


def test_unknown_group_is_rejected(clients: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="inconnues"):
        FeatureBuilder(["inexistante"]).fit(clients)


def test_feature_names_out_matches_transform(clients: pd.DataFrame) -> None:
    fb = FeatureBuilder(drop_columns=["Customer_ID", "churn"])
    assert list(fb.get_feature_names_out(clients.columns)) == list(fb.transform(clients).columns)
