"""Tests du nettoyage par règles fixes et du schéma de validation."""

from __future__ import annotations

import pandas as pd
import pytest

from churn.config import get_config
from churn.data.clean import cast_categories, clean, explicit_unknown, negatives_to_nan
from churn.data.load import load_raw
from churn.data.validate import coherence_report, schema_failures

pytestmark = pytest.mark.skipif(not get_config().raw_path.is_file(), reason="CSV brut absent")


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return load_raw(nrows=3000)


def test_negatives_to_nan_sets_flag() -> None:
    df = pd.DataFrame({"rev_Mean": [-1.0, 5.0], "totmrc_Mean": [1.0, -2.0],
                       "avg6rev": [1.0, 1.0], "eqpdays": [-3.0, None]})
    out = negatives_to_nan(df)
    assert out["rev_Mean"].isna().tolist() == [True, False]
    assert out["rev_Mean_was_negative"].tolist() == [1, 0]
    assert out["totmrc_Mean_was_negative"].tolist() == [0, 1]
    assert out["eqpdays_was_negative"].tolist() == [1, 0]  # NaN d'origine : pas un négatif
    assert df["rev_Mean"].iloc[0] == -1.0  # l'entrée n'est pas modifiée


def test_negatives_flag_is_idempotent() -> None:
    df = pd.DataFrame({"rev_Mean": [-1.0], "totmrc_Mean": [1.0], "avg6rev": [1.0],
                       "eqpdays": [1.0]})
    twice = negatives_to_nan(negatives_to_nan(df))
    assert twice["rev_Mean_was_negative"].tolist() == [1]


def test_unknown_mapping_is_column_specific(raw: pd.DataFrame) -> None:
    out = explicit_unknown(raw)
    assert "U" not in set(out["new_cell"].dropna())
    assert "Unknown" in set(out["kid0_2"].dropna())
    assert "UNKW" not in set(out["hnd_webcap"].dropna())
    # prizm_social_one : U = Urban, ne doit pas être remplacé
    assert (out["prizm_social_one"] == "U").sum() == (raw["prizm_social_one"] == "U").sum()
    # crclscod : U est une classe de crédit
    assert (out["crclscod"] == "U").sum() == (raw["crclscod"] == "U").sum()


def test_nan_is_not_unknown(raw: pd.DataFrame) -> None:
    out = clean(raw)
    assert out["hnd_webcap"].isna().sum() == raw["hnd_webcap"].isna().sum()


def test_cast_categories_rejects_unknown_level(raw: pd.DataFrame) -> None:
    bad = explicit_unknown(raw)
    bad.loc[bad.index[0], "area"] = "ATLANTIS AREA"
    with pytest.raises(ValueError, match="area"):
        cast_categories(bad)


def test_clean_output_passes_clean_schema(raw: pd.DataFrame) -> None:
    out = clean(raw)
    assert len(out) == len(raw)  # aucune ligne supprimée
    assert isinstance(out["marital"].dtype, pd.CategoricalDtype)
    assert schema_failures(out, "clean").empty


def test_clean_is_idempotent(raw: pd.DataFrame) -> None:
    once = clean(raw)
    pd.testing.assert_frame_equal(clean(once), once)


def test_raw_schema_detects_injected_errors(raw: pd.DataFrame) -> None:
    bad = raw.copy()
    bad.loc[bad.index[0], "actvsubs"] = bad.loc[bad.index[0], "uniqsubs"] + 1
    bad.loc[bad.index[1], "marital"] = "Z"
    failures = schema_failures(bad, "raw")
    assert "abonnements actifs <= abonnements uniques" in set(failures["check"])
    assert "marital" in set(failures["column"])


def test_strict_coherence_rules_hold_on_raw(raw: pd.DataFrame) -> None:
    report = coherence_report(raw)
    assert report.loc[report["type"] == "stricte", "violations"].sum() == 0
