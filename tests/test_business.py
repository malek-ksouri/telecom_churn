"""Tests du scoring métier : niveaux, actions, campagne (E12)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.business.actions import (
    CONTEXT,
    DEFAULT_ACTION,
    ENGAGEMENT,
    INACTIVE_ACTION,
    NO_ACTION,
    TERMINAL,
    explain_clients,
    family,
    suggest_action,
)
from churn.business.campaign import (
    INACTIVE_ROW,
    PORTFOLIO_WEIGHT,
    campaign_curve,
    campaign_table,
    portfolio_weights,
    revenue_at_risk,
)
from churn.business.scoring import (
    HIGH,
    INACTIVE,
    LOW,
    MEDIUM,
    assign_tiers,
    band_lift,
    choose_tiers,
    is_inactive,
)
from churn.evaluation.calibration import adjust_prior, population_weights
from churn.explain.shap_utils import ShapResult

R, S = 0.02, 0.5


@pytest.fixture(scope="module")
def portfolio() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 20_000
    y = rng.integers(0, 2, n)
    score = 1 / (1 + np.exp(-(0.8 * y + rng.normal(0, 1, n))))
    mou = np.where(rng.random(n) < 0.03, 0.0, rng.gamma(2, 200, n))
    return pd.DataFrame({"churn": y, "proba_calibree": score,
                         "proba_reelle": adjust_prior(score, R, S),
                         "rev_Mean": rng.gamma(3, 20, n), "mou_Mean": mou})


def test_inactive_definition() -> None:
    df = pd.DataFrame({"mou_Mean": [0.0, np.nan, 3.5]})
    assert is_inactive(df).tolist() == [True, True, False]


def test_band_lift_weighted(portfolio: pd.DataFrame) -> None:
    y, p = portfolio["churn"].to_numpy(), portfolio["proba_calibree"].to_numpy()
    bands = band_lift(y, p, band=0.05, real_rate=R, sample_rate=S)
    assert len(bands) == 20
    assert bands["lift_cumule"].iloc[-1] == pytest.approx(1.0)
    assert bands["lift"].iloc[0] > bands["lift"].iloc[-1]
    # Bandes de 5 % du portefeuille repondéré (à un client près).
    w = population_weights(y, R, S)
    order = np.argsort(-p)
    first = w[order][p[order] >= bands["score_min"].iloc[0]].sum() / w.sum()
    assert first == pytest.approx(0.05, abs=0.002)


def test_choose_and_assign_tiers(portfolio: pd.DataFrame) -> None:
    y, p = portfolio["churn"].to_numpy(), portfolio["proba_calibree"].to_numpy()
    thr, bands = choose_tiers(y, p, R, S, capacity=0.10, min_lift=1.2, band=0.05)
    assert thr.high > thr.medium
    medium = bands[bands["niveau"] == MEDIUM]
    assert (medium["lift"] > 1.2).all()
    after = bands[bands["fin_pct"] > 100 * thr.medium_end]
    assert after.empty or after["lift"].iloc[0] <= 1.2
    inactive = is_inactive(portfolio)
    tiers = assign_tiers(portfolio["proba_calibree"], inactive, thr)
    assert (tiers[inactive] == INACTIVE).all()
    w = population_weights(y, R, S)
    high_share = w[(tiers == HIGH).to_numpy() | (inactive & (p >= thr.high)).to_numpy()].sum()
    assert high_share / w.sum() == pytest.approx(0.10, abs=0.002)
    with pytest.raises(ValueError):
        choose_tiers(y, p, R, S, capacity=0.12, band=0.05)


def test_families_and_actions() -> None:
    assert family("months", in_contract_end=True) == ENGAGEMENT
    assert family("months", in_contract_end=False) == CONTEXT
    assert family("phones") == family("eqpdays") == TERMINAL
    assert family("crclscod") == family("lor") == family("variable_inconnue") == CONTEXT
    assert suggest_action(HIGH, TERMINAL) == "Offre de renouvellement du terminal"
    assert suggest_action(MEDIUM, ENGAGEMENT) == "Offre de réengagement"
    assert suggest_action(HIGH, None) == DEFAULT_ACTION
    assert suggest_action(INACTIVE, TERMINAL) == INACTIVE_ACTION
    assert suggest_action(LOW, TERMINAL) == NO_ACTION


def test_explain_clients_uses_only_actionable_increasing_factors() -> None:
    values = pd.DataFrame({"months": [0.9, 0.9], "in_contract_end": [0.0, 0.0],
                           "crclscod": [1.5, -1.5], "eqpdays": [0.4, -0.2],
                           "change_mou": [-0.3, 0.1]})
    features = pd.DataFrame({"months": [11, 30], "in_contract_end": [1, 0],
                             "crclscod": ["A", "EA"], "eqpdays": [426.0, 100.0],
                             "change_mou": [-120.0, 40.0], "ratio_mou_3m_6m": [0.9, 1.1]})
    wide, factors = explain_clients(ShapResult(values, features, 0.0))
    first, second = wide.iloc[0], wide.iloc[1]
    # Client 0 : fin d'engagement (11 mois) actionnable et dominante ; crédit en contexte.
    assert first["famille_dominante"] == ENGAGEMENT
    assert first["raison_1"] == "Fin d'engagement : 11 mois d'ancienneté"
    assert first["raison_2"] == "Terminal ancien : 14 mois"
    assert first["raison_3"] is None
    assert first["contexte_1"].startswith("Classe de crédit A")
    # Client 1 : ancienneté hors fenêtre -> contexte ; seul facteur actionnable aggravant.
    assert second["raison_1"].startswith("Usage en hausse")
    assert "Ancienneté : 30 mois" in {second["contexte_1"].split(" (")[0],
                                      second["contexte_2"].split(" (")[0]}
    assert set(factors.loc[factors["variable"] == "crclscod", "actionnable"]) == {False}


def test_campaign_table(portfolio: pd.DataFrame) -> None:
    df = portfolio.assign(inactif=is_inactive(portfolio))
    df["revenu_en_jeu"] = revenue_at_risk(df["proba_reelle"], df["rev_Mean"])
    table = campaign_table(df, capacities=[0.05, 0.10], real_rate=R,
                           portfolio_size=100_000).set_index("groupe")
    top10 = table.loc["Top 10 % (actifs)"]
    assert top10["n_portfolio_equiv"] == pytest.approx(10_000, rel=0.01)
    assert top10["churners_hasard"] == pytest.approx(top10["n_portfolio_equiv"] * R)
    assert top10["facteur_vs_hasard"] > 1
    total = table.loc["Portefeuille entier"]
    assert total["n_portfolio_equiv"] == pytest.approx(100_000)
    assert total["churners_observes"] == pytest.approx(100_000 * R)
    assert table.loc[INACTIVE_ROW, "n_portfolio_equiv"] > 0
    assert (table["revenu_en_jeu"] >= 0).all()


def test_portfolio_weights_keep_global_scale_when_filtered(portfolio: pd.DataFrame) -> None:
    df = portfolio.assign(inactif=is_inactive(portfolio))
    df["revenu_en_jeu"] = revenue_at_risk(df["proba_reelle"], df["rev_Mean"])
    df[PORTFOLIO_WEIGHT] = portfolio_weights(df["churn"], R, portfolio_size=100_000)
    assert df[PORTFOLIO_WEIGHT].sum() == pytest.approx(100_000)
    half = df.iloc[: len(df) // 2]
    total = campaign_table(half, capacities=[0.10], real_rate=R).set_index("groupe")
    # Un sous-ensemble représente sa part du portefeuille, pas 100 000 clients.
    assert total.loc["Portefeuille entier", "n_portfolio_equiv"] == pytest.approx(
        half[PORTFOLIO_WEIGHT].sum())
    assert total.loc["Portefeuille entier", "n_rows"] == len(half)
    curve = campaign_curve(half, [0.0, 0.10, 0.50, 1.0], real_rate=R)
    assert curve["n_rows"].is_monotonic_increasing and curve["n_rows"].iloc[0] == 0
    assert curve["churners_attendus"].is_monotonic_increasing
    assert curve["n_rows"].iloc[-1] == int((~half["inactif"]).sum())
