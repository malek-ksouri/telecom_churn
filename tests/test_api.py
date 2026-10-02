"""Tests de l'API (E13) : statuts, schémas, 404, pagination, filtres, cohérence."""

from __future__ import annotations

import math

import pytest

from churn.config import get_config

ARTIFACTS = [get_config().paths.artifacts_dir / f for f in
             ("scores.parquet", "shap.parquet", "shap_values.parquet", "kpis.json")]
pytestmark = pytest.mark.skipif(not all(p.is_file() for p in ARTIFACTS),
                                reason="artefacts absents : lancer `make artifacts`")

from fastapi.testclient import TestClient  # noqa: E402

from api import schemas  # noqa: E402
from api.main import app  # noqa: E402

DIMENSIONS = ["risk_level", "cluster", "area", "tenure_band", "handset_age_band", "usage_band",
              "action"]


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def high_customer(client: TestClient) -> int:
    page = client.get("/api/customers", params={"risk_level": "High", "size": 1}).json()
    return page["items"][0]["customer_id"]


def get(client: TestClient, url: str, **params) -> dict:
    r = client.get(url, params=params)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize(("url", "model"), [
    ("/api/health", schemas.Health),
    ("/api/kpis", schemas.Kpis),
    ("/api/filters", schemas.FilterOptions),
    ("/api/risk/distribution", schemas.RiskDistribution),
    ("/api/segments/heatmap", schemas.Heatmap),
    ("/api/drivers", schemas.Drivers),
    ("/api/campaign/simulate", schemas.CampaignSimulation),
    ("/api/customers", schemas.CustomerPage),
])
def test_endpoints_ok_and_match_schema(client: TestClient, url: str, model) -> None:
    model.model_validate(get(client, url))


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_segments_every_dimension(client: TestClient, dimension: str) -> None:
    body = schemas.Segments.model_validate(get(client, f"/api/segments/{dimension}"))
    assert body.items and sum(i.n_rows for i in body.items) == 100_000


def test_customer_detail_and_explanation(client: TestClient, high_customer: int) -> None:
    detail = schemas.CustomerDetail.model_validate(get(client, f"/api/customers/{high_customer}"))
    assert detail.risk_level == "High" and detail.reasons
    assert all(r.actionable and r.contribution_log_odds > 0 for r in detail.reasons)
    assert all(not c.actionable for c in detail.context)
    expl = schemas.CustomerExplanation.model_validate(
        get(client, f"/api/customers/{high_customer}/explanation"))
    total = expl.base_value_log_odds + sum(c.contribution_log_odds for c in expl.contributions)
    assert total + expl.others_contribution_log_odds == pytest.approx(expl.log_odds, abs=1e-6)
    assert expl.p_raw_from_log_odds == pytest.approx(expl.p_raw, abs=1e-4)


def test_not_found_and_invalid_parameters(client: TestClient) -> None:
    for url in ("/api/customers/999", "/api/customers/999/explanation"):
        r = client.get(url)
        assert r.status_code == 404 and "introuvable" in r.json()["detail"]
    assert client.get("/api/unknown").status_code == 404
    assert client.get("/api/segments/unknown").status_code == 422
    assert client.get("/api/segments/heatmap", params={"x": "area", "y": "area"}).status_code == 422
    assert client.get("/api/campaign/simulate", params={"success_rate": 1.5}).status_code == 422
    assert client.get("/api/customers", params={"size": 500}).status_code == 422


def test_pagination_and_sort(client: TestClient) -> None:
    p1 = get(client, "/api/customers", size=10, page=1)
    p2 = get(client, "/api/customers", size=10, page=2)
    assert p1["total_n_rows"] == 100_000 and p1["total_pages"] == 10_000
    ids1 = {i["customer_id"] for i in p1["items"]}
    assert len(ids1) == 10 and ids1.isdisjoint(i["customer_id"] for i in p2["items"])
    probs = [i["p_real"] for i in p1["items"] + p2["items"]]
    assert probs == sorted(probs, reverse=True)
    asc = get(client, "/api/customers", sort="tenure_months", order="asc", size=5)
    tenure = [i["tenure_months"] for i in asc["items"]]
    assert tenure == sorted(tenure)
    pages = math.ceil(100_000 / 7)
    last = get(client, "/api/customers", size=7, page=pages)
    assert last["total_pages"] == pages and len(last["items"]) == 100_000 - 7 * (pages - 1)
    assert get(client, "/api/customers", size=7, page=pages + 1)["items"] == []


def test_filters_and_search(client: TestClient, high_customer: int) -> None:
    options = get(client, "/api/filters")
    levels = next(d for d in options["dimensions"] if d["dimension"] == "risk_level")
    n_high = next(v["n_rows"] for v in levels["values"] if v["value"] == "High")
    page = get(client, "/api/customers", risk_level="High", size=50)
    assert page["total_n_rows"] == n_high
    assert {i["risk_level"] for i in page["items"]} == {"High"}
    kpis = get(client, "/api/kpis", risk_level="High")
    assert kpis["n_rows"] == n_high and kpis["filters"] == {"risk_level": ["High"]}
    both = get(client, "/api/kpis", risk_level=["High", "Medium"])
    medium = get(client, "/api/kpis", risk_level="Medium")
    assert both["n_rows"] == n_high + medium["n_rows"]
    found = get(client, "/api/customers", search=str(high_customer))
    assert high_customer in {i["customer_id"] for i in found["items"]}


def test_drill_down_filter_matches_segment(client: TestClient) -> None:
    item = get(client, "/api/segments/tenure_band")["items"][2]
    kpis = client.get("/api/kpis", params=item["filter"]).json()
    assert kpis["n_rows"] == item["n_rows"]
    assert kpis["n_portfolio_equiv"] == pytest.approx(item["n_portfolio_equiv"])


def test_consistency_of_counts(client: TestClient) -> None:
    kpis = get(client, "/api/kpis")
    levels = kpis["by_risk_level"]
    assert sum(lv["n_rows"] for lv in levels) == kpis["n_rows"] == kpis["n_rows_total"]
    assert sum(lv["n_portfolio_equiv"] for lv in levels) == pytest.approx(100_000)
    assert kpis["expected_churners"] == pytest.approx(2_000, rel=0.01)
    assert kpis["official_campaign"]["churners_per_1000_contacted"] == pytest.approx(51, abs=1)
    assert kpis["hypothesis"]["real_churn_rate_is_hypothesis"] is True
    risk = get(client, "/api/risk/distribution")
    assert sum(b["n_rows"] for b in risk["bins"]) == 100_000


def test_campaign_simulator(client: TestClient) -> None:
    zero = get(client, "/api/campaign/simulate", capacity_pct=10, success_rate=0)
    assert zero["result"]["avoided_departures_hypothesis"] == 0
    assert zero["result"]["preserved_revenue_monthly_hypothesis"] == 0
    assert zero["result"]["campaign_cost"] is None and zero["result"]["net_balance"] is None
    assert [p["capacity_pct"] for p in zero["curve"]] == list(range(1, 51))
    curve = [p["expected_churners"] for p in zero["curve"]]
    assert curve == sorted(curve)
    sim = get(client, "/api/campaign/simulate", capacity_pct=10, success_rate=0.2,
              offer_cost=5, revenue_horizon_months=3)
    res = sim["result"]
    assert res["avoided_departures_hypothesis"] == pytest.approx(0.2 * res["expected_churners"])
    assert res["campaign_cost"] == pytest.approx(5 * res["targeted_n_portfolio_equiv"])
    assert res["net_balance"] == pytest.approx(
        3 * res["preserved_revenue_monthly_hypothesis"] - res["campaign_cost"])
    assert res["targeted_n_portfolio_equiv"] == pytest.approx(10_000, rel=0.01)
    assert sim["inactive"]["n_rows"] == get(client, "/api/kpis")["inactive_n_rows"]


def test_campaign_revenue_horizon(client: TestClient) -> None:
    one = get(client, "/api/campaign/simulate", capacity_pct=10, success_rate=0.2)["result"]
    twelve = get(client, "/api/campaign/simulate", capacity_pct=10, success_rate=0.2,
                 offer_cost=5, revenue_horizon_months=12)["result"]
    assert one["preserved_revenue_horizon_hypothesis"] == pytest.approx(
        one["preserved_revenue_monthly_hypothesis"])
    assert twelve["preserved_revenue_horizon_hypothesis"] == pytest.approx(
        12 * twelve["preserved_revenue_monthly_hypothesis"])
    assert twelve["net_balance"] == pytest.approx(
        twelve["preserved_revenue_horizon_hypothesis"] - twelve["campaign_cost"])
    assert client.get("/api/campaign/simulate",
                      params={"revenue_horizon_months": 0}).status_code == 422


def test_segment_profiles(client: TestClient) -> None:
    body = schemas.SegmentProfiles.model_validate(get(client, "/api/segments/profiles"))
    assert len(body.profiles) == 5
    assert sum(p.n_rows for p in body.profiles) == 100_000
    rates = [p.expected_churn_rate for p in body.profiles]
    assert rates == sorted(rates, reverse=True)
    assert all(len(p.traits) == 3 and p.main_action for p in body.profiles)
    first = body.profiles[0]
    filtered = get(client, "/api/kpis", cluster=first.name)
    assert filtered["n_rows"] == first.n_rows


def test_drivers_flag_sensitive_variables(client: TestClient) -> None:
    from churn.business.actions import SENSITIVE_VARIABLES

    body = get(client, "/api/drivers", top=60)
    items = body["actionable"] + body["context"]
    assert all(i["sensitive"] == (i["variable"] in SENSITIVE_VARIABLES) for i in items)
    assert any(i["sensitive"] for i in body["context"])
    assert not any(i["sensitive"] for i in body["actionable"])


def test_customers_export_csv(client: TestClient) -> None:
    import csv
    import io

    params = {"risk_level": "High", "action": "Offre de réengagement"}
    r = client.get("/api/customers/export", params=params)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "clients_a_risque.csv" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("\ufeff")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"))
    listed = get(client, "/api/customers", size=1, **params)
    assert len(rows) == listed["total_n_rows"] > 0
    assert {r["niveau"] for r in rows} == {"High"}
    assert {r["action_suggeree"] for r in rows} == {"Offre de réengagement"}
    risks = [float(r["risque_mensuel_pct_taux_suppose_2pct"].replace(",", ".")) for r in rows]
    assert risks == sorted(risks, reverse=True)
    assert rows[0]["identifiant"] == str(listed["items"][0]["customer_id"])
    one = client.get("/api/customers/export", params={"search": "1072931"}).content.decode()
    assert "1072931" in one and len(one.strip().splitlines()) == 2
