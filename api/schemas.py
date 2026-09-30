"""Schémas pydantic des réponses de l'API (E13).

Conventions (reprises dans la documentation OpenAPI, source des types TypeScript du front) :

- ``n_rows`` : **clients dans la base** (lignes réelles du jeu de données, ~50 % de churners),
  utilisés pour les listes, les filtres et la pagination ;
- ``n_portfolio_equiv`` : **estimation** de l'effectif équivalent dans un portefeuille réel de
  100 000 clients au taux de churn supposé (hypothèse, 2 % par mois), utilisée pour les KPI et
  la campagne. Les montants (churners attendus, revenu en jeu) sont dans la même unité ;
- probabilités entre 0 et 1 (sauf champs ``*_pct``, en %) ; montants en $ par mois ;
- contributions SHAP en log-odds du modèle brut.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["High", "Medium", "Low", "Inactif"]
Dimension = Literal["risk_level", "cluster", "area", "tenure_band", "handset_age_band",
                    "usage_band", "action"]
SortField = Literal["p_real", "revenue_at_risk_monthly", "monthly_bill", "tenure_months",
                    "handset_age_days", "customer_id"]

N_ROWS = "Clients dans la base : lignes réelles du jeu de données (listes, filtres)."
N_EQUIV = ("ESTIMATION : effectif équivalent dans un portefeuille réel de 100 000 clients au "
           "taux de churn supposé (hypothèse, 2 % par mois).")
EXPECTED = "Churners attendus sur un mois, en équivalent portefeuille (estimation)."
REVENUE = ("Revenu mensuel en jeu ($ / mois) = probabilité corrigée × facture, équivalent "
           "portefeuille.")


class Schema(BaseModel):
    """Base : interdit les champs inconnus en sortie de service (détecte les dérives)."""

    model_config = ConfigDict(extra="forbid")


# --- Communs ---------------------------------------------------------------------------------

class Hypothesis(Schema):
    """Hypothèses sous lesquelles les effectifs en équivalent portefeuille sont estimés."""

    real_churn_rate: float = Field(description="Taux de churn mensuel réel SUPPOSÉ (hypothèse).",
                                   examples=[0.02])
    real_churn_rate_is_hypothesis: bool = Field(description="Toujours vrai : non issu des données.")
    portfolio_size: int = Field(description="Taille du portefeuille représenté par la base.",
                                examples=[100000])
    note: str = Field(description="Définition de n_portfolio_equiv, à afficher avec les KPI.")


class GroupMetrics(Schema):
    """Indicateurs d'un groupe de clients (niveau, modalité, cellule)."""

    n_rows: int = Field(description=N_ROWS)
    n_portfolio_equiv: float = Field(description=N_EQUIV)
    expected_churners: float | None = Field(None, description=EXPECTED)
    revenue_at_risk: float | None = Field(None, description=REVENUE)
    monthly_bill: float | None = Field(None, description="Facture mensuelle totale ($ / mois), "
                                                         "équivalent portefeuille.")
    share_of_portfolio: float | None = Field(None, description="Part du périmètre (0-1), en "
                                                               "équivalent portefeuille.")
    observed_churn_rate_in_base: float | None = Field(
        None, description="Taux de churn historique observé dans la base (échantillon enrichi à "
                          "~50 % de churners : sert à comparer les groupes, pas à estimer un taux "
                          "réel).")
    expected_churn_rate: float | None = Field(None, description="Probabilité mensuelle moyenne "
                                                                "de départ (0-1), portefeuille.")
    share_high: float | None = Field(None, description="Part de clients High (0-1), portefeuille.")
    share_of_expected_churners: float | None = Field(None, description="Part des churners "
                                                                       "attendus du périmètre.")
    share_of_revenue_at_risk: float | None = Field(None, description="Part du revenu en jeu du "
                                                                     "périmètre.")


class LevelMetrics(GroupMetrics):
    risk_level: RiskLevel


# --- Santé -----------------------------------------------------------------------------------

class Health(Schema):
    status: Literal["ok"]
    n_rows: int = Field(description=N_ROWS)
    artifacts_date: str | None = Field(description="Date de construction des artefacts.")
    model: str | None
    calibration: str | None


# --- KPI -------------------------------------------------------------------------------------

class OfficialCampaign(Schema):
    """Campagne de référence : capacité de la config (10 %), clients actifs, inactifs à part."""

    capacity_pct: float = Field(description="Part du périmètre contactée (%).", examples=[10.0])
    targeted_n_rows: int = Field(description=N_ROWS)
    targeted_n_portfolio_equiv: float = Field(description=N_EQUIV)
    expected_churners: float = Field(description=EXPECTED)
    churners_per_1000_contacted: float = Field(
        description="Futurs churners atteints pour 1 000 clients contactés (51 sur le "
                    "portefeuille entier : chiffre de campagne officiel).", examples=[51.1])
    random_churners_per_1000_contacted: float = Field(description="Au hasard (1 000 × taux "
                                                                  "supposé).", examples=[20.0])
    lift_vs_random: float
    revenue_at_risk_monthly: float = Field(description=REVENUE)


class ModelInfo(Schema):
    name: str | None
    calibration: str | None
    auc_out_of_fold_train: float | None = Field(description="AUC des scores hors fold du train.")
    auc_test: float | None = Field(description="AUC sur le test (évaluation finale E9).")


class Kpis(Schema):
    """KPI du périmètre filtré."""

    filters: dict[str, list[str]] = Field(description="Filtres appliqués.")
    hypothesis: Hypothesis
    n_rows: int = Field(description=N_ROWS)
    n_rows_total: int = Field(description="Clients dans la base, sans filtre.")
    n_portfolio_equiv: float = Field(description=N_EQUIV)
    share_of_portfolio: float = Field(description="Part du portefeuille couverte par les filtres.")
    expected_churners: float = Field(description=EXPECTED)
    expected_churn_rate: float | None = Field(description="Probabilité mensuelle moyenne (0-1).")
    observed_churn_rate_in_base: float | None = Field(description="Churn historique dans la base "
                                                                  "(échantillon enrichi).")
    revenue_at_risk_monthly: float = Field(description=REVENUE)
    monthly_bill: float = Field(description="Facture mensuelle totale, équivalent portefeuille.")
    revenue_at_risk_share_of_bill: float | None
    inactive_n_rows: int = Field(description="Clients inactifs dans la base (" + N_ROWS + ")")
    by_risk_level: list[LevelMetrics]
    official_campaign: OfficialCampaign | None
    model: ModelInfo

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "filters": {}, "n_rows": 100000, "n_portfolio_equiv": 100000.0,
        "expected_churners": 2002.2, "revenue_at_risk_monthly": 116162.4}]})


# --- Filtres ---------------------------------------------------------------------------------

class FilterValue(Schema):
    value: str
    n_rows: int = Field(description=N_ROWS)


class FilterDimension(Schema):
    dimension: Dimension
    label: str
    values: list[FilterValue]


class FilterOptions(Schema):
    dimensions: list[FilterDimension]
    customer_sort_fields: list[SortField]
    capacity_pct_range: list[int] = Field(description="Bornes du curseur de capacité (%).")


# --- Risque ----------------------------------------------------------------------------------

class HistogramBin(Schema):
    p_real_min_pct: float = Field(description="Borne basse de la classe (%).")
    p_real_max_pct: float | None = Field(description="Borne haute (%) ; null = dernière classe.")
    n_rows: int = Field(description=N_ROWS)
    n_portfolio_equiv: float = Field(description=N_EQUIV)
    n_portfolio_equiv_by_risk_level: dict[str, float]


class Thresholds(Schema):
    high_p_calibrated: float = Field(description="Seuil High sur la probabilité calibrée (0-1).")
    medium_p_calibrated: float
    high_p_real_pct: float = Field(description="Même seuil, en probabilité mensuelle corrigée (%).")
    medium_p_real_pct: float


class RiskDistribution(Schema):
    filters: dict[str, list[str]]
    hypothesis: Hypothesis
    unit: str
    bins: list[HistogramBin]
    quantiles_portfolio_equiv_pct: dict[str, float]
    thresholds: Thresholds
    by_risk_level: list[LevelMetrics]


# --- Segments et heatmap ---------------------------------------------------------------------

class SegmentItem(GroupMetrics):
    value: str = Field(description="Modalité de la dimension.")
    filter: dict[str, list[str]] = Field(description="Filtre à ajouter pour un drill-down.")


class Segments(Schema):
    dimension: Dimension
    label: str
    filters: dict[str, list[str]]
    hypothesis: Hypothesis
    items: list[SegmentItem]


class HeatmapCell(Schema):
    x: str
    y: str
    n_rows: int = Field(description=N_ROWS)
    n_portfolio_equiv: float | None = Field(description=N_EQUIV)
    observed_churn_rate_in_base: float | None = Field(description="null si trop peu de lignes.")
    expected_churn_rate: float | None = Field(description="null si trop peu de lignes.")
    revenue_at_risk: float | None = Field(description=REVENUE)
    low_sample: bool


class Heatmap(Schema):
    x: Dimension
    y: Dimension
    x_label: str
    y_label: str
    x_values: list[str]
    y_values: list[str]
    min_rows_for_rate: int
    filters: dict[str, list[str]]
    hypothesis: Hypothesis
    cells: list[HeatmapCell]


# --- Facteurs --------------------------------------------------------------------------------

class Driver(Schema):
    variable: str
    label: str
    family: str
    family_label: str
    actionable: bool
    mean_abs_shap: float = Field(description="Moyenne de |contribution SHAP| (log-odds).")
    mean_shap: float = Field(description="Moyenne signée (> 0 : pousse le risque vers le haut).")
    share_rows_increasing: float = Field(description="Part des clients pour qui le facteur "
                                                     "augmente le risque (0-1).")
    share_pct: float = Field(description="Part de l'importance totale (%).")


class DriverFamily(Schema):
    family: str
    family_label: str
    actionable: bool
    share_pct: float


class Drivers(Schema):
    filters: dict[str, list[str]]
    n_rows: int = Field(description=N_ROWS)
    unit: str
    note: str
    actionable: list[Driver]
    context: list[Driver]
    families: list[DriverFamily]


# --- Campagne --------------------------------------------------------------------------------

class CampaignPoint(Schema):
    capacity_pct: float = Field(description="Part du périmètre contactée (%).")
    targeted_n_rows: int = Field(description=N_ROWS)
    targeted_n_portfolio_equiv: float = Field(description=N_EQUIV)
    expected_churners: float = Field(description=EXPECTED)
    random_churners: float = Field(description="Churners atteints par un ciblage au hasard.")
    lift_vs_random: float | None
    churners_per_1000_contacted: float | None
    share_of_expected_churners: float | None
    revenue_at_risk_monthly: float = Field(description=REVENUE)
    share_of_revenue_at_risk: float | None
    observed_churners_check: float = Field(description="Contrôle : churners historiques "
                                                       "repondérés (doit être proche des "
                                                       "churners attendus).")
    avoided_departures_hypothesis: float = Field(
        description="HYPOTHÈSE : churners attendus × taux de succès saisi par l'utilisateur.")
    preserved_revenue_monthly_hypothesis: float = Field(
        description="HYPOTHÈSE : revenu en jeu × taux de succès ($ / mois).")
    campaign_cost: float | None = Field(description="Coût total, seulement si offer_cost fourni.")
    net_balance: float | None = Field(description="Revenu préservé × horizon − coût ; seulement si "
                                                  "offer_cost fourni.")


class UserHypotheses(Schema):
    success_rate: float
    offer_cost_per_contact: float | None
    revenue_horizon_months: int
    note: str


class Scope(Schema):
    n_rows: int = Field(description=N_ROWS)
    n_portfolio_equiv: float = Field(description=N_EQUIV)


class InactiveSummary(Schema):
    n_rows: int = Field(description=N_ROWS)
    n_portfolio_equiv: float = Field(description=N_EQUIV)
    expected_churners: float = Field(description=EXPECTED)
    revenue_at_risk_monthly: float = Field(description=REVENUE)
    action: str
    note: str


class CampaignSimulation(Schema):
    filters: dict[str, list[str]]
    hypothesis: Hypothesis
    user_hypotheses: UserHypotheses
    scope: Scope
    result: CampaignPoint | None = Field(description="Résultat à la capacité demandée.")
    inactive: InactiveSummary
    curve: list[CampaignPoint] = Field(description="Courbe de 1 à 50 % de capacité.")


# --- Clients ---------------------------------------------------------------------------------

class CustomerSummary(Schema):
    customer_id: int
    partition: Literal["train_oof", "test"] = Field(
        description="train_oof : score hors fold ; test : modèle final.")
    risk_level: RiskLevel
    p_real: float = Field(description="Probabilité mensuelle de départ au taux supposé (0-1).")
    p_calibrated: float = Field(description="Probabilité calibrée sur la base (0-1, classement).")
    segment: str
    action: str
    top_reason: str | None
    revenue_at_risk_monthly: float = Field(description="p_real × facture ($ / mois).")
    monthly_bill: float | None = Field(description="Facture mensuelle ($).")
    tenure_months: float | None
    handset_age_days: float | None
    area: str
    inactive: bool


class CustomerPage(Schema):
    filters: dict[str, list[str]]
    search: str | None
    sort: SortField
    order: Literal["asc", "desc"]
    page: int
    size: int
    total_n_rows: int = Field(description="Clients correspondants dans la base (" + N_ROWS + ")")
    total_pages: int
    items: list[CustomerSummary]


class Factor(Schema):
    variable: str
    label: str
    text: str | None = Field(description="Phrase métier (situation du client).")
    family: str
    family_label: str
    actionable: bool
    contribution_log_odds: float
    effect: str


class CustomerScores(Schema):
    p_raw: float = Field(description="Probabilité du modèle brut (0-1).")
    p_calibrated: float = Field(description="Probabilité calibrée sur la base (0-1).")
    p_real: float = Field(description="Probabilité mensuelle au taux réel supposé (0-1).")
    p_real_note: str


class Segment(Schema):
    id: int
    name: str


class Bands(Schema):
    tenure_band: str
    handset_age_band: str
    usage_band: str


class ProfileField(Schema):
    variable: str
    label: str
    value: float | int | str | None
    unit: str


class CustomerDetail(Schema):
    customer_id: int
    partition: Literal["train_oof", "test"]
    scores: CustomerScores
    risk_level: RiskLevel
    inactive: bool
    segment: Segment
    bands: Bands
    action: str
    dominant_family: str | None
    reasons: list[Factor] = Field(description="Jusqu'à 3 facteurs actionnables qui augmentent "
                                              "le risque.")
    context: list[Factor] = Field(description="Facteurs non actionnables les plus influents.")
    monthly_bill: float | None
    revenue_at_risk_monthly: float
    profile: list[ProfileField]
    historical_churn_label: int
    historical_churn_note: str
    note: str


class CustomerExplanation(Schema):
    customer_id: int
    unit: str
    base_value_log_odds: float
    contributions: list[Factor]
    others_contribution_log_odds: float
    others_count: int
    log_odds: float
    p_raw_from_log_odds: float
    p_raw: float
    note: str


class ErrorResponse(BaseModel):
    detail: str = Field(examples=["Client 123 introuvable"])
