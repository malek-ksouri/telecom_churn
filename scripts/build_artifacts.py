"""Construit les artefacts de scoring (``make artifacts``, E12).

1. Scores **sans fuite** : hors fold pour les 80 000 clients du train (mêmes folds, modèle
   final réentraîné et recalibré dans chaque fold), modèle final livré pour les 20 000
   clients du test. Colonne ``partition`` : ``train_oof`` / ``test``.
2. Niveaux High / Medium / Low (seuils appris sur les scores hors fold des clients actifs du
   train), catégorie Inactif (D86).
3. SHAP de chaque client avec **le modèle qui l'a noté** (modèle du fold ou modèle final),
   raisons actionnables, contexte et action suggérée.
4. Revenu mensuel en jeu, tableau de campagne, synthèse par niveau.

Sorties :
- ``artifacts/scores.parquet`` : une ligne par client ;
- ``artifacts/shap.parquet`` : les 8 premiers facteurs SHAP de chaque client (avec phrases) ;
- ``artifacts/shap_values.parquet`` : contributions SHAP de toutes les variables d'origine
  (log-odds, float32), une ligne par client, pour agréger les facteurs par filtre (API) ;
- ``artifacts/kpis.json`` : seuils, niveaux, campagne, contrôles, note d'hypothèse ;
- ``reports/tier_bands.csv`` et ``reports/figures/08_tiers_lift.png``.

Le test est lu pour être **noté** (comme le serait un nouveau client), pas pour évaluer ni
choisir quoi que ce soit : les seuils sont fixés sur le train avant sa lecture.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import warnings
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from churn.business.actions import explain_clients, suggest_action
from churn.business.campaign import (
    PORTFOLIO_WEIGHT,
    campaign_table,
    portfolio_weights,
    revenue_at_risk,
    tier_summary,
)
from churn.business.scoring import (
    TEST,
    TRAIN_OOF,
    assign_tiers,
    choose_tiers,
    final_scores,
    is_inactive,
    out_of_fold_scores,
    raw_pipeline,
)
from churn.charts import save_figure, tier_lift_chart
from churn.config import get_config
from churn.data.split import load_test, load_train
from churn.evaluation.cv import make_folds
from churn.evaluation.metrics import lift_at_k, roc_auc
from churn.explain.reason_codes import compute_outlier_thresholds, set_outlier_thresholds
from churn.explain.shap_utils import ShapExplainer
from churn.features.build import FeatureBuilder
from churn.logging_setup import setup_logging
from churn.models.model_card import write_model_card
from churn.segmentation.kmeans import assign_segments

logger = logging.getLogger("build_artifacts")

DISPLAY_COLUMNS = ["months", "eqpdays", "mou_Mean", "change_mou", "totmrc_Mean", "ovrrev_Mean",
                   "hnd_price", "custcare_Mean", "drop_vce_Mean", "actvsubs", "crclscod", "area"]


def explain_partition(pipeline, X: pd.DataFrame
                      ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Raisons, contexte, facteurs principaux et contributions regroupées des clients de ``X``,
    avec le modèle qui les a notés."""
    result = ShapExplainer(pipeline).explain(X)
    wide, factors = explain_clients(result)
    wide["valeur_base"] = result.base_value
    return wide, factors, result.grouped().astype("float32")


def _records(df: pd.DataFrame) -> list[dict]:
    """Tableau -> liste de dictionnaires JSON (NaN -> null, flottants arrondis)."""
    return json.loads(df.round(6).to_json(orient="records", force_ascii=False))


def main() -> int:
    """Point d'entrée."""
    setup_logging()
    warnings.filterwarnings("ignore", message=".*TreeExplainer shap values output has changed")
    cfg = get_config()
    target, id_col = cfg.data.target, cfg.data.id_col
    r = cfg.business.real_churn_rate.value
    start = time.perf_counter()

    # 1. Scores hors fold du train et explications par le modèle de chaque fold.
    train = load_train()
    y = train[target]
    # Seuils des valeurs atypiques (quantile 99,9 %, train seul) pour les phrases des raisons.
    outliers = compute_outlier_thresholds(
        FeatureBuilder(groups=cfg.features.groups).transform(train))
    set_outlier_thresholds(outliers)
    cfg.paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    (cfg.paths.artifacts_dir / "outlier_thresholds.json").write_text(
        json.dumps(outliers, indent=1), encoding="utf-8")
    logger.info("Seuils de valeurs atypiques : %d hauts, %d bas", len(outliers["high"]),
                len(outliers["low"]))
    oof, fold_models = out_of_fold_scores(train, y, make_folds(y))
    logger.info("Scores hors fold : %.0f s", time.perf_counter() - start)
    parts = [explain_partition(raw_pipeline(m.calibrated), train.loc[m.valid_index])
             for m in fold_models]
    train_wide = pd.concat([p[0] for p in parts]).loc[train.index]
    train_factors = pd.concat([p[1] for p in parts])
    train_matrix = pd.concat([p[2] for p in parts]).loc[train.index]

    # 2. Seuils des niveaux, fixés sur les clients actifs du train (avant la lecture du test).
    sample_rate = float(y.mean())
    train_inactive = is_inactive(train)
    active = ~train_inactive.to_numpy()
    thresholds, bands = choose_tiers(y.to_numpy()[active],
                                     oof["proba_calibree"].to_numpy()[active], r, sample_rate)

    # 3. Scores et explications du test par le modèle final livré.
    final_model = joblib.load(cfg.paths.models_dir / "final_model.joblib")
    test = load_test(final_evaluation=True)
    test_scores = final_scores(final_model, test)
    test_wide, test_factors, test_matrix = explain_partition(raw_pipeline(final_model.calibrated),
                                                             test)

    # 4. Assemblage : une ligne par client, identifiée par Customer_ID.
    frames, factor_frames, matrices = [], [], []
    for df, scores, wide, factors, matrix in [
            (train, oof, train_wide, train_factors, train_matrix),
            (test, test_scores, test_wide, test_factors, test_matrix)]:
        matrices.append(matrix.set_axis(df[id_col].to_numpy()).rename_axis(id_col))
        out = pd.concat([df[[id_col]], scores], axis=1)
        out["inactif"] = is_inactive(df)
        out["niveau"] = assign_tiers(out["proba_calibree"], out["inactif"], thresholds)
        out = pd.concat([out, wide], axis=1)
        out["action"] = [suggest_action(t, f) for t, f in
                         zip(out["niveau"], out["famille_dominante"], strict=True)]
        out["rev_Mean"] = df["rev_Mean"]
        out["revenu_en_jeu"] = revenue_at_risk(out["proba_reelle"], df["rev_Mean"])
        out = pd.concat([out, assign_segments(df), df[DISPLAY_COLUMNS]], axis=1)
        out["churn"] = df[target]
        frames.append(out)
        factors = factors.assign(**{id_col: df[id_col].to_numpy()[factors["client"]],
                                    "partition": scores["partition"].iloc[0]})
        factor_frames.append(factors.drop(columns="client"))
    scores_all = pd.concat(frames, ignore_index=True)
    # Équivalent portefeuille de chaque ligne (somme = 100 000 ; hypothèse de taux réel).
    scores_all[PORTFOLIO_WEIGHT] = portfolio_weights(scores_all[target], r, sample_rate)
    shap_matrix = pd.concat(matrices).reset_index()
    factors_all = pd.concat(factor_frames, ignore_index=True)
    factors_all = factors_all[[id_col, "partition", *factors_all.columns[:-2]]]

    # 5. Synthèses métier (portefeuille réel repondéré, hypothèse de taux réel).
    campaign = campaign_table(scores_all, sample_rate=sample_rate)
    tiers = tier_summary(scores_all, sample_rate=sample_rate)
    tiers_by_partition = {p: tier_summary(scores_all[scores_all["partition"] == p],
                                          sample_rate=sample_rate)
                          for p in (TRAIN_OOF, TEST)}
    checks = {}
    for p, g in scores_all.groupby("partition"):
        checks[p] = {"clients": len(g), "auc_proba_calibree": roc_auc(g["churn"],
                                                                      g["proba_calibree"]),
                     "lift@10%_echantillon": lift_at_k(g["churn"].to_numpy(),
                                                       g["proba_calibree"].to_numpy(), 0.10)}

    cfg.paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    scores_path = cfg.paths.artifacts_dir / "scores.parquet"
    shap_path = cfg.paths.artifacts_dir / "shap.parquet"
    matrix_path = cfg.paths.artifacts_dir / "shap_values.parquet"
    shap_matrix.to_parquet(matrix_path, index=False)
    scores_all.to_parquet(scores_path, index=False)
    factors_all.to_parquet(shap_path, index=False)
    bands.to_csv(cfg.paths.reports_dir / "tier_bands.csv")

    hyp = cfg.business.real_churn_rate
    size_text = f"{cfg.business.campaign.portfolio_size:,}".replace(",", " ")
    kpis = {
        "date": datetime.now().isoformat(timespec="minutes"),
        "modele": cfg.models.final,
        "calibration": cfg.models.calibration,
        "hypotheses": {
            "taux_churn_reel": {"valeur": hyp.value, "unite": hyp.unit, "est_une_hypothese": True,
                                "source": hyp.source},
            "taux_succes_offre": "inconnu, à mesurer (A/B test) : aucun départ évité ni revenu "
                                 "préservé n'est calculé (D79)",
            "couts": "aucun coût supposé",
        },
        "note_effectifs": {
            "n_rows": "clients dans la base : lignes réelles du jeu de données (environ 50 % de "
                      "churners), utilisées pour les listes et les filtres",
            "n_portfolio_equiv": "ESTIMATION : équivalent dans un portefeuille réel de "
                                 f"{size_text} clients au taux de churn supposé de "
                                 f"{100 * hyp.value:g} % par mois (hypothèse), obtenu en "
                                 "repondérant chaque ligne ; utilisé pour les KPI et la campagne",
            "montants": "churners attendus et revenu en jeu sont exprimés en équivalent "
                        "portefeuille (estimations sous l'hypothèse de taux réel)",
        },
        "campagne_config": cfg.business.campaign.model_dump(),
        "n_rows": {"total": len(scores_all),
                   **scores_all["partition"].value_counts().to_dict(),
                   "inactifs": int(scores_all["inactif"].sum())},
        "taux_churn_echantillon_train": sample_rate,
        "seuils": thresholds.to_dict(),
        "bandes_lift": _records(bands.reset_index()),
        "niveaux": _records(tiers.reset_index()),
        "niveaux_par_partition": {p: _records(t.reset_index())
                                  for p, t in tiers_by_partition.items()},
        "campagne": _records(campaign),
        "actions": scores_all.loc[scores_all["niveau"].isin(["High", "Medium", "Inactif"]),
                                  "action"].value_counts().to_dict(),
        "controles": checks,
    }
    kpis_path = cfg.paths.artifacts_dir / "kpis.json"
    kpis_path.write_text(json.dumps(kpis, ensure_ascii=False, indent=2), encoding="utf-8")

    fig = tier_lift_chart(bands, thresholds.min_lift,
                          "Niveaux de risque : lift par bande de 5 % du portefeuille "
                          "(scores hors fold, clients actifs)")
    save_figure(fig, "08_tiers_lift")

    logger.info("Artefacts construits en %.0f s", time.perf_counter() - start)
    print(f"scores : {scores_path} ({len(scores_all)} lignes, {scores_all.shape[1]} colonnes)")
    print(f"shap   : {shap_path} ({len(factors_all)} lignes)")
    print(f"matrice: {matrix_path} ({shap_matrix.shape[0]} x {shap_matrix.shape[1] - 1} variables)")
    print(f"kpis   : {kpis_path}")
    print(f"seuils : High >= {thresholds.high:.4f}, Medium >= {thresholds.medium:.4f} "
          f"(High {100 * thresholds.capacity:.0f} %, High + Medium "
          f"{100 * thresholds.medium_end:.0f} % du portefeuille)")
    print(np.round(tiers, 4).to_string())
    # Fiche du modèle complétée par les niveaux et le chiffre de campagne (kpis.json).
    print(f"fiche  : {write_model_card(n_train=len(train))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
