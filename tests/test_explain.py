"""Tests de l'explicabilité : additivité SHAP, regroupement, codes de raisons."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.config import get_config
from churn.data.clean import clean
from churn.data.load import load_raw
from churn.explain.reason_codes import INCREASES, describe, reason_codes, reasons_table
from churn.explain.shap_utils import ShapExplainer, global_importance, source_variable
from churn.models.factory import build_pipeline

pytestmark = pytest.mark.skipif(not get_config().raw_path.is_file(), reason="CSV brut absent")


@pytest.fixture(scope="module")
def explained():
    df = clean(load_raw(nrows=3000))
    y = df[get_config().data.target]
    pipe = build_pipeline("lightgbm", n_estimators=30).fit(df, y)
    return pipe, ShapExplainer(pipe).explain(df.iloc[:300])


def test_shap_is_additive(explained) -> None:
    pipe, res = explained
    raw = pipe.named_steps["model"].predict(res.features, raw_score=True)
    assert np.allclose(res.log_odds().to_numpy(), raw, atol=1e-6)


def test_grouping_preserves_totals_and_maps_derived_features(explained) -> None:
    _, res = explained
    g = res.grouped()
    assert np.allclose(g.sum(axis=1), res.values.sum(axis=1))
    assert "in_contract_end" not in g.columns and "months" in g.columns
    assert np.allclose(g["months"], res.values["months"] + res.values["in_contract_end"])
    assert source_variable("handset_old") == "eqpdays"
    assert source_variable("manquant_hnd_webcap") == "hnd_webcap"
    assert source_variable("eqpdays_was_negative") == "eqpdays"
    imp = global_importance(res)
    assert imp["shap_abs_moyen"].is_monotonic_decreasing
    assert imp["part_pct"].sum() == pytest.approx(100, abs=0.5)


def test_reason_codes_top3_sorted_with_consistent_direction(explained) -> None:
    _, res = explained
    client = res.values.index[0]
    reasons = reason_codes(res, client, top=3)
    assert len(reasons) == 3
    contrib = [abs(r.contribution) for r in reasons]
    assert contrib == sorted(contrib, reverse=True)
    assert all((r.effet == INCREASES) == (r.contribution > 0) for r in reasons)
    increases = reason_codes(res, client, top=3, only="increase")
    assert all(r.contribution > 0 for r in increases)
    assert list(reasons_table(reasons).columns)[:2] == ["facteur", "situation du client"]


def test_phrases() -> None:
    row = pd.Series({"months": 11.0, "in_contract_end": 1, "eqpdays": 426.0, "change_mou": -120.0,
                     "ratio_mou_3m_6m": 0.68, "lor": np.nan, "hnd_price": 29.99})
    assert describe("months", row) == "Fin d'engagement : 11 mois d'ancienneté"
    assert describe("eqpdays", row) == "Terminal ancien : 14 mois"
    assert describe("change_mou", row) == "Usage en baisse de 120 minutes par mois"
    assert describe("avg3mou", row).startswith("Usage en baisse de 32 %")
    assert describe("lor", row) == "Durée de résidence inconnue"
    assert describe("hnd_price", row) == "Terminal à 30 $"
