"""Tests de la segmentation K-means (données synthétiques : pas de dépendance au CSV)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from churn.segmentation import kmeans as km


@pytest.fixture
def clients() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 600
    df = pd.DataFrame({
        "mou_Mean": rng.gamma(2, 250, n), "rev_Mean": rng.gamma(3, 20, n),
        "totmrc_Mean": rng.choice([10, 30, 45, 60], n).astype(float),
        "ovrrev_Mean": rng.exponential(10, n), "custcare_Mean": rng.exponential(1.5, n),
        "drop_blk_Mean": rng.exponential(8, n), "uniqsubs": rng.integers(1, 4, n).astype(float),
        "change_mou": rng.normal(0, 200, n), "months": rng.integers(6, 60, n).astype(float),
        "eqpdays": rng.integers(0, 1200, n).astype(float),
        "hnd_price": rng.choice([30, 80, 130, 200], n).astype(float),
        "churn": rng.integers(0, 2, n), "autre": rng.random(n),
    })
    df.loc[:9, "rev_Mean"] = np.nan  # manquants : imputés par la médiane
    return df


def test_target_is_not_a_segmentation_feature() -> None:
    assert "churn" not in km.FEATURES
    assert len(km.FEATURES) == len(set(km.FEATURES)) == 11


def test_transforms() -> None:
    x = np.array([-100.0, 0.0, 100.0])
    assert np.allclose(km.signed_log1p(x), [-np.log1p(100), 0, np.log1p(100)])
    assert km.log1p_positive(np.array([-1.0]))[0] == 0.0


def test_preprocessor_ignores_other_columns_and_imputes(clients: pd.DataFrame) -> None:
    X = km.transform_features(clients)
    assert list(X.columns) == km.FEATURES
    assert not X.isna().any().any()
    assert np.allclose(X.mean(), 0, atol=1e-9)


def test_pipeline_is_deterministic_and_ignores_target(clients: pd.DataFrame) -> None:
    a = km.build_segmentation_pipeline(4).fit(clients).predict(clients)
    shuffled = clients["churn"].sample(frac=1, random_state=1).to_numpy()
    shuffled_target = clients.assign(churn=shuffled)
    b = km.build_segmentation_pipeline(4).fit(shuffled_target).predict(shuffled_target)
    assert (a == b).all()


def test_name_clusters_rules() -> None:
    profile = pd.DataFrame({
        "months": [14, 15, 13, 15, 27], "totmrc_Mean": [10, 52, 45, 54, 30],
        "mou_Mean": [92, 769, 220, 781, 165], "change_mou": [-1, -180, -8, 167, -6],
    })
    names = km.name_clusters(profile)
    assert names == {0: km.NAME_SECONDARY_LINES, 1: km.NAME_HEAVY_DECLINING,
                     2: km.NAME_MODERATE_RECENT, 3: km.NAME_HEAVY_GROWING,
                     4: km.NAME_TENURED_OLD_DEVICE}


def test_name_clusters_requires_k5() -> None:
    with pytest.raises(ValueError):
        km.name_clusters(pd.DataFrame({"months": [1, 2], "totmrc_Mean": [1, 2],
                                       "mou_Mean": [1, 2], "change_mou": [1, 2]}))


def test_segment_auc_cv_detects_signal() -> None:
    rng = np.random.default_rng(0)
    seg = pd.Series(rng.choice(["a", "b"], 4000))
    y = pd.Series((rng.random(4000) < np.where(seg == "a", 0.7, 0.3)).astype(int))
    auc, _ = km.segment_auc_cv(seg, y)
    assert auc > 0.65
    auc_noise, _ = km.segment_auc_cv(pd.Series(rng.choice(["a", "b"], 4000)), y)
    assert abs(auc_noise - 0.5) < 0.05


def test_bundle_roundtrip(clients: pd.DataFrame, tmp_path: Path) -> None:
    pipeline = km.build_segmentation_pipeline(3).fit(clients)
    bundle = {"pipeline": pipeline, "segment_names": {0: "a", 1: "b", 2: "c"},
              "features": km.FEATURES, "k": 3}
    path = km.save_segmentation(bundle, tmp_path / "seg.joblib")
    out = km.assign_segments(clients, km.load_segmentation(path))
    assert (out["segment_id"].to_numpy() == pipeline.predict(clients)).all()
    assert set(out["segment"]) <= {"a", "b", "c"}
