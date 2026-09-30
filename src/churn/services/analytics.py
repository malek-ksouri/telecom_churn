"""Services d'analyse du portefeuille : KPI, distribution du risque, segments, facteurs (E13).

Fonctions pures sur les artefacts en cache (``get_store``), sans recalcul de modèle. Chaque
effectif est double : ``n_rows`` (lignes réelles de la base) et ``n_portfolio_equiv``
(estimation pour un portefeuille réel au taux de churn supposé, hypothèse). Les montants
(churners attendus, revenu en jeu) sont exprimés en équivalent portefeuille.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from churn.business.actions import CONTEXT, ENGAGEMENT, FAMILY_LABELS, family
from churn.business.campaign import PORTFOLIO_WEIGHT, campaign_curve
from churn.business.scoring import HIGH, TIERS
from churn.config import get_config
from churn.evaluation.calibration import adjust_prior
from churn.explain.shap_utils import label
from churn.features.build import CONTRACT_END_MONTHS
from churn.services.filters import (
    DIMENSION_LABELS,
    DIMENSIONS,
    Filters,
    dimension_values,
    filter_mask,
)
from churn.services.store import Store, get_store

MIN_ROWS_FOR_RATE = 30          # en dessous, un taux de cellule n'est pas affiché
HISTOGRAM_STEP_PCT = 0.5        # largeur des classes de probabilité (points de %)
HISTOGRAM_MAX_PCT = 15.0        # dernière classe : « 15 % et plus »


def num(x: Any) -> float | None:
    """Nombre JSON : flottant Python, NaN -> None."""
    if x is None:
        return None
    x = float(x)
    return None if np.isnan(x) else x


def hypothesis(store: Store | None = None) -> dict[str, Any]:
    """Hypothèses à afficher avec tout chiffre en équivalent portefeuille."""
    store = store or get_store()
    cfg = get_config()
    rate = cfg.business.real_churn_rate
    return {
        "real_churn_rate": rate.value,
        "real_churn_rate_is_hypothesis": True,
        "portfolio_size": cfg.business.campaign.portfolio_size,
        "note": store.kpis.get("note_effectifs", {}).get("n_portfolio_equiv", ""),
    }


def _weighted(sub: pd.DataFrame) -> pd.DataFrame:
    """Colonnes pondérées par l'équivalent portefeuille (pour des sommes par groupe)."""
    w = sub[PORTFOLIO_WEIGHT]
    return pd.DataFrame({
        "n_rows": 1,
        "n_portfolio_equiv": w,
        "expected_churners": w * sub["proba_reelle"],
        "revenue_at_risk": w * sub["revenu_en_jeu"],
        "monthly_bill": w * sub["rev_Mean"].fillna(0),
        "high_equiv": w * (sub["niveau"] == HIGH),
        "observed_churn": sub["churn"],
    }, index=sub.index)


def _group_rows(sub: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Sommes par groupe (une ou deux dimensions) et indicateurs dérivés."""
    parts = _weighted(sub)
    for k in keys:
        parts[k] = sub[DIMENSIONS[k]].to_numpy()
    g = parts.groupby(keys, observed=True).sum()
    total_expected = parts["expected_churners"].sum()
    total_revenue = parts["revenue_at_risk"].sum()
    total_w = parts["n_portfolio_equiv"].sum()
    g["share_of_portfolio"] = g["n_portfolio_equiv"] / total_w
    g["observed_churn_rate_in_base"] = g["observed_churn"] / g["n_rows"]
    g["expected_churn_rate"] = g["expected_churners"] / g["n_portfolio_equiv"]
    g["share_high"] = g["high_equiv"] / g["n_portfolio_equiv"]
    g["share_of_expected_churners"] = g["expected_churners"] / total_expected
    g["share_of_revenue_at_risk"] = g["revenue_at_risk"] / total_revenue
    return g.drop(columns=["observed_churn", "high_equiv"])


def _row_dict(row: pd.Series) -> dict[str, Any]:
    out = {k: num(v) for k, v in row.items()}
    out["n_rows"] = int(row["n_rows"])
    return out


def get_kpis(filters: Filters | None = None) -> dict[str, Any]:
    """KPI du périmètre filtré : effectifs, risque attendu, revenu en jeu, niveaux, campagne
    officielle (capacité de la config, inactifs à part)."""
    store = get_store()
    cfg = get_config()
    sub = store.scores[filter_mask(store.scores, filters)]
    parts = _weighted(sub)
    n_equiv = float(parts["n_portfolio_equiv"].sum())
    expected = float(parts["expected_churners"].sum())
    revenue = float(parts["revenue_at_risk"].sum())
    bill = float(parts["monthly_bill"].sum())

    levels = _group_rows(sub, ["risk_level"]) if len(sub) else pd.DataFrame()
    by_level = [{"risk_level": t, **(_row_dict(levels.loc[t]) if t in levels.index else {
        "n_rows": 0, "n_portfolio_equiv": 0.0})} for t in TIERS]

    capacity = cfg.business.campaign.capacity
    campaign = None
    if len(sub) and (~sub["inactif"]).any():
        c = campaign_curve(sub, [capacity]).iloc[0]
        campaign = {
            "capacity_pct": 100 * capacity,
            "targeted_n_rows": int(c["n_rows"]),
            "targeted_n_portfolio_equiv": num(c["n_portfolio_equiv"]),
            "expected_churners": num(c["churners_attendus"]),
            "churners_per_1000_contacted": num(1000 * c["churners_attendus"]
                                                / c["n_portfolio_equiv"]),
            "random_churners_per_1000_contacted": 1000 * cfg.business.real_churn_rate.value,
            "lift_vs_random": num(c["facteur_vs_hasard"]),
            "revenue_at_risk_monthly": num(c["revenu_en_jeu"]),
        }
    controls = store.kpis.get("controles", {})
    return {
        "filters": filters.active() if filters else {},
        "hypothesis": hypothesis(store),
        "n_rows": len(sub),
        "n_rows_total": len(store.scores),
        "n_portfolio_equiv": n_equiv,
        "share_of_portfolio": n_equiv / store.total_portfolio,
        "expected_churners": expected,
        "expected_churn_rate": expected / n_equiv if n_equiv else None,
        "observed_churn_rate_in_base": num(sub["churn"].mean()) if len(sub) else None,
        "revenue_at_risk_monthly": revenue,
        "monthly_bill": bill,
        "revenue_at_risk_share_of_bill": revenue / bill if bill else None,
        "inactive_n_rows": int(sub["inactif"].sum()),
        "by_risk_level": by_level,
        "official_campaign": campaign,
        "model": {
            "name": store.kpis.get("modele"),
            "calibration": store.kpis.get("calibration"),
            "auc_out_of_fold_train": num(controls.get("train_oof", {}).get("auc_proba_calibree")),
            "auc_test": num(controls.get("test", {}).get("auc_proba_calibree")),
        },
    }


def get_filter_options() -> dict[str, Any]:
    """Modalités de chaque filtre (ordre d'affichage) avec leur nombre de lignes."""
    store = get_store()
    scores = store.scores
    dims = []
    for dim, column in DIMENSIONS.items():
        counts = scores[column].value_counts()
        dims.append({"dimension": dim, "label": DIMENSION_LABELS[dim],
                     "values": [{"value": v, "n_rows": int(counts.get(v, 0))}
                                for v in dimension_values(scores, dim)]})
    return {"dimensions": dims,
            "customer_sort_fields": ["p_real", "revenue_at_risk_monthly", "monthly_bill",
                                     "tenure_months", "handset_age_days", "customer_id"],
            "capacity_pct_range": [1, 50]}


def _threshold_real(store: Store, p_calibrated: float) -> float:
    s = store.kpis["taux_churn_echantillon_train"]
    return float(adjust_prior(np.array([p_calibrated]), store.kpis["seuils"]["real_rate"], s)[0])


def get_risk_distribution(filters: Filters | None = None) -> dict[str, Any]:
    """Histogramme de la probabilité mensuelle corrigée (taux supposé) et répartition par
    niveau, par classe de probabilité."""
    store = get_store()
    sub = store.scores[filter_mask(store.scores, filters)]
    pct = 100 * sub["proba_reelle"].to_numpy()
    edges = np.arange(0, HISTOGRAM_MAX_PCT + HISTOGRAM_STEP_PCT, HISTOGRAM_STEP_PCT)
    idx = np.minimum(np.floor(pct / HISTOGRAM_STEP_PCT).astype(int), len(edges) - 1)
    frame = pd.DataFrame({"bin": idx, "level": sub["niveau"].to_numpy(),
                          "w": sub[PORTFOLIO_WEIGHT].to_numpy()})
    rows = frame.groupby("bin").agg(n_rows=("w", "size"), n_portfolio_equiv=("w", "sum"))
    by_level = frame.pivot_table(index="bin", columns="level", values="w", aggfunc="sum",
                                 fill_value=0.0)
    bins = []
    for i, lo in enumerate(edges):
        last = i == len(edges) - 1
        bins.append({
            "p_real_min_pct": float(lo),
            "p_real_max_pct": None if last else float(lo + HISTOGRAM_STEP_PCT),
            "n_rows": int(rows["n_rows"].get(i, 0)),
            "n_portfolio_equiv": float(rows["n_portfolio_equiv"].get(i, 0.0)),
            "n_portfolio_equiv_by_risk_level": {
                t: float(by_level.loc[i, t]) if (i in by_level.index and t in by_level.columns)
                else 0.0 for t in TIERS},
        })
    w = sub[PORTFOLIO_WEIGHT].to_numpy()
    quantiles = {}
    if len(sub):
        order = np.argsort(pct)
        cum = np.cumsum(w[order]) / w.sum()
        for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99):
            quantiles[f"p{int(100 * q)}"] = float(pct[order][np.searchsorted(cum, q)])
    thr = store.kpis["seuils"]
    levels = _group_rows(sub, ["risk_level"]) if len(sub) else pd.DataFrame()
    return {
        "filters": filters.active() if filters else {},
        "hypothesis": hypothesis(store),
        "unit": "probabilité mensuelle de départ corrigée vers le taux réel supposé, en %",
        "bins": bins,
        "quantiles_portfolio_equiv_pct": quantiles,
        "thresholds": {
            "high_p_calibrated": thr["high"], "medium_p_calibrated": thr["medium"],
            "high_p_real_pct": 100 * _threshold_real(store, thr["high"]),
            "medium_p_real_pct": 100 * _threshold_real(store, thr["medium"]),
        },
        "by_risk_level": [{"risk_level": t, **(_row_dict(levels.loc[t]) if t in levels.index
                                               else {"n_rows": 0, "n_portfolio_equiv": 0.0})}
                          for t in TIERS],
    }


def get_segments(dimension: str, filters: Filters | None = None) -> dict[str, Any]:
    """Par modalité d'une dimension : effectifs, taux de churn, revenu en jeu, part de High.

    Une modalité cliquée devient un filtre (``{dimension: [value]}``) : drill-down.
    """
    if dimension not in DIMENSIONS:
        raise ValueError(f"Dimension inconnue : {dimension}")
    store = get_store()
    sub = store.scores[filter_mask(store.scores, filters)]
    g = _group_rows(sub, [dimension]) if len(sub) else pd.DataFrame()
    items = [{"value": v, "filter": {dimension: [v]}, **_row_dict(g.loc[v])}
             for v in dimension_values(sub, dimension) if v in g.index] if len(sub) else []
    return {"dimension": dimension, "label": DIMENSION_LABELS[dimension],
            "filters": filters.active() if filters else {}, "hypothesis": hypothesis(store),
            "items": items}


def get_heatmap(x: str, y: str, filters: Filters | None = None) -> dict[str, Any]:
    """Taux de churn croisé de deux dimensions (ex. ancienneté × âge du terminal).

    Chaque cellule donne le churn observé dans la base et le risque attendu (portefeuille) ;
    les taux des cellules de moins de ``MIN_ROWS_FOR_RATE`` lignes ne sont pas affichés.
    """
    for dim in (x, y):
        if dim not in DIMENSIONS:
            raise ValueError(f"Dimension inconnue : {dim}")
    if x == y:
        raise ValueError("Les deux dimensions doivent être différentes")
    store = get_store()
    sub = store.scores[filter_mask(store.scores, filters)]
    g = _group_rows(sub, [x, y]) if len(sub) else pd.DataFrame()
    cells = []
    for (xv, yv), row in g.iterrows():
        small = row["n_rows"] < MIN_ROWS_FOR_RATE
        cells.append({
            "x": xv, "y": yv, "n_rows": int(row["n_rows"]),
            "n_portfolio_equiv": num(row["n_portfolio_equiv"]),
            "observed_churn_rate_in_base": None if small else num(
                row["observed_churn_rate_in_base"]),
            "expected_churn_rate": None if small else num(row["expected_churn_rate"]),
            "revenue_at_risk": num(row["revenue_at_risk"]),
            "low_sample": bool(small),
        })
    return {"x": x, "y": y, "x_label": DIMENSION_LABELS[x], "y_label": DIMENSION_LABELS[y],
            "x_values": dimension_values(sub, x) if len(sub) else [],
            "y_values": dimension_values(sub, y) if len(sub) else [],
            "min_rows_for_rate": MIN_ROWS_FOR_RATE, "filters": filters.active() if filters else {},
            "hypothesis": hypothesis(store), "cells": cells}


def get_drivers(filters: Filters | None = None, top: int = 15) -> dict[str, Any]:
    """Importance globale des facteurs (moyenne de |SHAP| sur les clients filtrés), séparée
    entre facteurs actionnables et facteurs de contexte.

    L'ancienneté est scindée : actionnable (fin d'engagement) pour les clients à 11-12 mois,
    contexte pour les autres (D85). SHAP décrit le modèle, pas des causes.
    """
    store = get_store()
    mask = filter_mask(store.scores, filters)
    X = store.shap[mask]
    n = len(X)
    items = []
    if n:
        absx = np.abs(X)
        mean_abs = absx.mean(axis=0)
        mean_signed = X.mean(axis=0)
        share_up = (X > 0).mean(axis=0)
        window = store.scores.loc[mask, "months"].isin(CONTRACT_END_MONTHS).to_numpy()
        for j, var in enumerate(store.shap_columns):
            if var == "months":
                for in_window, fam, name in [(True, ENGAGEMENT, "Fin d'engagement (11-12 mois)"),
                                             (False, CONTEXT, "Ancienneté (hors fin "
                                                              "d'engagement)")]:
                    rows = window if in_window else ~window
                    items.append({
                        "variable": "months" if in_window else "months_outside_window",
                        "label": name, "family": fam,
                        "mean_abs_shap": float(absx[rows, j].sum() / n),
                        "mean_shap": float(X[rows, j].sum() / n),
                        "share_rows_increasing": float((X[rows, j] > 0).sum() / n)})
                continue
            items.append({"variable": var, "label": label(var), "family": family(var),
                          "mean_abs_shap": float(mean_abs[j]), "mean_shap": float(mean_signed[j]),
                          "share_rows_increasing": float(share_up[j])})
    total = sum(i["mean_abs_shap"] for i in items) or 1.0
    for i in items:
        i["share_pct"] = 100 * i["mean_abs_shap"] / total
        i["actionable"] = i["family"] != CONTEXT
        i["family_label"] = FAMILY_LABELS[i["family"]]
    items.sort(key=lambda i: i["mean_abs_shap"], reverse=True)
    families: dict[str, float] = {}
    for i in items:
        families[i["family"]] = families.get(i["family"], 0.0) + i["share_pct"]
    return {
        "filters": filters.active() if filters else {},
        "n_rows": int(n),
        "unit": "moyenne de |contribution SHAP| en log-odds sur les clients filtrés",
        "note": "SHAP explique le modèle, pas la causalité : un facteur important est associé "
                "au risque selon le modèle, agir dessus ne garantit pas de réduire le risque.",
        "actionable": [i for i in items if i["actionable"]][:top],
        "context": [i for i in items if not i["actionable"]][:top],
        "families": [{"family": f, "family_label": FAMILY_LABELS[f], "actionable": f != CONTEXT,
                      "share_pct": v} for f, v in sorted(families.items(),
                                                         key=lambda kv: -kv[1])],
    }
