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


def test_phrases_for_frequent_reasons() -> None:
    row = pd.Series({"change_rev": 12.4, "ratio_rev_3m_6m": 0.8, "avgqty": 127.4, "uniqsubs": 1,
                     "refurb_new": "R", "hnd_webcap": "WC", "roam_Mean": 2.0, "lor": 1.0,
                     "drop_blk_Mean": 3.5})
    assert describe("change_rev", row) == "Facture en hausse de 12 $ par mois (3 derniers mois)"
    assert describe("avg3rev", row).startswith("Facture en baisse de 20 %")
    assert describe("avgqty", row) == "Appels depuis l'ouverture : 127 par mois"
    assert describe("uniqsubs", row) == "1 ligne ouverte sur le compte"
    assert describe("refurb_new", row) == "Terminal reconditionné"
    assert describe("hnd_webcap", row) == "Terminal à accès web limité"
    assert describe("lor", row) == "Durée de résidence : 1 an"
    assert describe("drop_blk_Mean", row) == "Appels coupés ou bloqués : 3,5 par mois"


def test_atypical_values_are_flagged_without_changing_order() -> None:
    from churn.business.actions import explain_clients
    from churn.explain.reason_codes import (
        ATYPICAL_NOTE,
        compute_outlier_thresholds,
        set_outlier_thresholds,
    )
    from churn.explain.shap_utils import ShapResult

    train = pd.DataFrame({"roam_Mean": np.arange(1001, dtype=float), "flag": [0, 1] * 500 + [0],
                          "change_rev": np.arange(-500, 501, dtype=float)})
    thresholds = compute_outlier_thresholds(train)
    assert "flag" not in thresholds["high"]             # binaires ignorées
    assert thresholds["high"]["roam_Mean"] == pytest.approx(999.0)
    assert "roam_Mean" not in thresholds["low"]         # jamais négative : pas de seuil bas
    assert thresholds["low"]["change_rev"] == pytest.approx(-499.0)

    row = pd.Series({"roam_Mean": 3685.2, "ratio_mou_3m_6m": 9.0, "avgqty": 50.0})
    try:
        set_outlier_thresholds({"high": {"roam_Mean": 1000.0, "ratio_mou_3m_6m": 3.0,
                                         "avgqty": 3000.0},
                                "low": {"change_rev": -200.0, "ratio_rev_3m_6m": 0.2}})
        expected = "Appels en itinérance : 3 685,2 par mois" + ATYPICAL_NOTE
        assert describe("roam_Mean", row) == expected
        assert describe("avg3mou", row).endswith(ATYPICAL_NOTE)   # valeur affichée : le ratio
        assert not describe("avgqty", row).endswith(ATYPICAL_NOTE)
        low = pd.Series({"change_rev": -350.0, "ratio_rev_3m_6m": 0.1})
        assert describe("change_rev", low).endswith(ATYPICAL_NOTE)       # forte baisse
        assert describe("avg3rev", low).endswith(ATYPICAL_NOTE)          # ratio très bas
        assert not describe("change_rev", pd.Series({"change_rev": -50.0})).endswith(ATYPICAL_NOTE)

        values = pd.DataFrame({"roam_Mean": [0.5], "avgqty": [0.3], "months": [0.1]})
        features = pd.DataFrame({"roam_Mean": [3685.2], "avgqty": [50.0], "months": [30],
                                 "in_contract_end": [0]})
        result = ShapResult(values, features, 0.0)
        flagged, _ = explain_clients(result)
        set_outlier_thresholds({})
        plain, _ = explain_clients(result)
    finally:
        set_outlier_thresholds({})
    cols = ["raison_1_variable", "raison_2_variable", "raison_3_variable"]
    assert flagged[cols].equals(plain[cols])             # même ordre des raisons
    assert flagged.loc[0, "raison_1"] == plain.loc[0, "raison_1"] + ATYPICAL_NOTE
    assert flagged.loc[0, "raison_2"] == plain.loc[0, "raison_2"]
