"""Génération de la fiche du modèle (``models/model_card.md``).

La fiche est construite à partir de la configuration (modèle, paramètres, familles de
features, variables exclues), des métriques enregistrées par le notebook 06 :
``reports/selection_grid_cv.csv`` (CV) et ``reports/final_metrics.json`` (test), et, s'il
existe, de ``artifacts/kpis.json`` (niveaux de risque et campagne, E12). Elle est écrite par
``make train`` puis complétée par ``make artifacts``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from churn.config import get_config

MODEL_LABELS = {"lightgbm": "LightGBM (boosting de gradient)",
                "logreg": "Régression logistique améliorée (L2)"}
FINAL_METRICS_FILE = "final_metrics.json"
CV_GRID_FILE = "selection_grid_cv.csv"


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{value:.{digits}f}".replace(".", ",") if isinstance(value, float) else str(value)


def _int(value: float) -> str:
    """Entier arrondi avec espace des milliers (« 17 472 »)."""
    return f"{round(value):,}".replace(",", " ")


def _pct(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f} %".replace(".", ",")


def _business_section(kpis_path: Path) -> list[str]:
    """Niveaux de risque et chiffre de campagne (E12), lus dans ``artifacts/kpis.json``."""
    if not kpis_path.is_file():
        return ["## Usage métier", "",
                "*Niveaux de risque et campagne : lancer `make artifacts` pour compléter.*", ""]
    kpis = json.loads(kpis_path.read_text(encoding="utf-8"))
    seuils = kpis["seuils"]
    lines = [
        "## Usage métier (niveaux de risque et campagne)",
        "",
        f"- **High** : probabilité calibrée ≥ {_fmt(seuils['high'])} (capacité de campagne : "
        f"{_pct(seuils['capacity'], 0)} du portefeuille). **Medium** : ≥ {_fmt(seuils['medium'])} "
        f"(bandes de 5 % dont le lift reste > {_fmt(seuils['min_lift'], 1)}). **Low** : le reste. "
        "**Inactif** (0 minute ou usage non mesuré) : à part, action « vérifier la ligne / "
        "reconquête », jamais ciblé par une offre de fidélisation.",
        "- Seuils fixés sur les scores hors fold du train, portefeuille repondéré au taux réel "
        "supposé.",
        "- Deux effectifs : **clients dans la base** (lignes réelles, environ 50 % de churners) "
        "et **estimation portefeuille** (équivalent dans un portefeuille réel de 100 000 "
        "clients au taux supposé).",
        "",
        "| Niveau | Clients dans la base | Estimation portefeuille | Risque mensuel moyen "
        "(taux supposé) | Churn observé dans la base |",
        "|---|---|---|---|---|",
        *[f"| {n['niveau']} | {_int(n['n_rows'])} | {_int(n['n_portfolio_equiv'])} | "
          f"{_pct(n['proba_reelle_moyenne'])} | {_pct(n['churn_observe_base'])} |"
          for n in kpis["niveaux"]],
        "",
    ]
    top = next((c for c in kpis["campagne"] if c.get("capacite") == seuils["capacity"]), None)
    if top is not None:
        per_1000 = 1000 / top["n_portfolio_equiv"]
        lines += [
            f"- **Chiffre officiel de campagne** : en contactant les "
            f"{_pct(seuils['capacity'], 0)} de clients actifs les plus risqués, environ "
            f"**{_int(top['churners_attendus'] * per_1000)} futurs churners pour 1 000 clients "
            f"contactés**, contre {_int(top['churners_hasard'] * per_1000)} au hasard (facteur "
            f"{_fmt(top['facteur_vs_hasard'], 2)}) ; revenu mensuel en jeu de "
            f"{_int(top['revenu_en_jeu'])} $ pour un portefeuille de 100 000 clients.",
            "- Ce sont des churners **atteints**, pas des départs évités : ceux-ci dépendent du "
            "taux de succès de l'offre, inconnu (à mesurer avec un groupe témoin).",
            "",
        ]
    return lines


def build_model_card(n_train: int) -> str:
    """Texte Markdown de la fiche du modèle final."""
    cfg = get_config()
    final = cfg.models.final
    if final is None:
        raise ValueError("Aucun modèle final dans configs/config.yaml (models.final).")
    params = cfg.models.params.get(final, {})
    reports = cfg.paths.reports_dir
    rate = cfg.business.real_churn_rate

    lines = [
        "# Fiche du modèle de churn",
        "",
        f"*Générée le {date.today():%d/%m/%Y} par `scripts/train.py`.*",
        "",
        "## Modèle",
        "",
        f"- **Type** : {MODEL_LABELS.get(final, final)} (`build_pipeline(\"{final}\")`).",
        "- **Usage prévu** : classer les clients par risque de départ pour cibler une campagne "
        "de rétention à budget limité. Aide à la décision, pas décision automatique.",
        ("- **Sortie** : probabilité calibrée sur l'échantillon équilibré (sert au classement) "
         "et probabilité mensuelle ramenée au taux de churn réel **supposé** (sert aux chiffres "
         "métier)." if cfg.models.calibration else
         "- **Sortie** : score de risque (probabilité sur l'échantillon équilibré, **non "
         "calibrée**)."),
        "",
        "### Hyperparamètres",
        "",
        "| Paramètre | Valeur |",
        "|---|---|",
        *[f"| `{k}` | {_fmt(v, 6)} |" for k, v in params.items()],
        "",
        "## Données",
        "",
        f"- **Entraînement** : `data/processed/train.parquet`, {n_train} clients (80 % du CSV, "
        "split stratifié, graine 42).",
        "- **Test** : `data/processed/test.parquet`, 20 000 clients, jamais utilisé pour un "
        "choix : lu pour l'évaluation finale (classement en E9, calibration en E10, modèle figé "
        "avant chaque lecture), puis pour noter ses clients comme de nouveaux clients (E12).",
        "- **Cible** : `churn` = 1 si le client part dans la fenêtre d'observation, soit "
        f"{rate.target_window}. Échantillon **équilibré** (49,6 % de churners), "
        f"non représentatif du taux réel (hypothèse : {100 * rate.value:.0f} % {rate.unit}).",
        "- **Features** : variables d'origine nettoyées + familles "
        f"`{', '.join(cfg.features.groups)}`.",
        f"- **Variables exclues** : {', '.join(f'`{c}`' for c in cfg.non_feature_columns)} "
        "(identifiant, cible, et `ethnic` pour raison éthique et réglementaire).",
        "",
        "## Performance",
        "",
    ]
    grid_path = reports / CV_GRID_FILE
    if grid_path.is_file():
        grid = pd.read_csv(grid_path, index_col=0)
        lines += ["### Validation croisée (5 folds, train)", "",
                  "| Modèle | AUC | Écart-type | Écart train-validation | Brier | lift@10 % |",
                  "|---|---|---|---|---|---|"]
        for name, row in grid.iterrows():
            lines.append(f"| {name} | {_fmt(row['AUC CV'])} | {_fmt(row['écart-type'])} | "
                         f"{_fmt(row['écart train-validation'])} | {_fmt(row['Brier'])} | "
                         f"{_fmt(row['lift@10 %'], 3)} |")
        lines.append("")
    metrics_path = reports / FINAL_METRICS_FILE
    if metrics_path.is_file():
        test = json.loads(metrics_path.read_text(encoding="utf-8"))["test"]
        lines += ["### Jeu de test (évaluation unique)", "",
                  "| Modèle | AUC [IC 95 %] | PR-AUC | Brier | lift@10 % | Precision@10 % | "
                  "AUC clients actifs |",
                  "|---|---|---|---|---|---|---|"]
        for name, m in test.items():
            lines.append(f"| {name} | {_fmt(m['roc_auc'])} [{_fmt(m['ic_bas'])} ; "
                         f"{_fmt(m['ic_haut'])}] | {_fmt(m['pr_auc'])} | {_fmt(m['brier'])} | "
                         f"{_fmt(m['lift@10%'], 3)} | {_fmt(m['precision@10%'], 3)} | "
                         f"{_fmt(m['auc_clients_actifs'])} |")
        lines.append("")
    else:
        lines += ["*Métriques de test non disponibles (notebook 06 non exécuté).*", ""]
    calib = (json.loads(metrics_path.read_text(encoding="utf-8")).get("calibration")
             if metrics_path.is_file() else None)
    if calib and cfg.models.calibration:
        lines += [
            "## Calibration et taux réel",
            "",
            f"- **Méthode** : calibration {cfg.models.calibration} (`CalibratedClassifierCV`, "
            "CV interne à 5 folds sur le train), choisie en CV avant la lecture du test (E10).",
            f"- **Test** : Brier {_fmt(calib['brier_brut'])} (brut) → "
            f"{_fmt(calib['brier_calibre'])} (calibré) ; ECE {_fmt(calib['ece_brut'])} → "
            f"{_fmt(calib['ece_calibre'])}.",
            "- **Correction du prior** : p' = p·(r/s) / [p·(r/s) + (1 − p)·((1 − r)/(1 − s))], "
            f"s = {_fmt(calib['sample_rate'])} (échantillon), r = taux réel **supposé**. "
            "Transformation monotone : l'AUC et le classement sont inchangés.",
            "- **Modèle livré** : `models/final_model.joblib` (`FinalChurnModel` : probabilité "
            "sur l'échantillon pour le classement, probabilité au taux réel pour les chiffres "
            "métier).",
            "",
            "| Taux réel (hypothèse) | Probabilité moyenne corrigée | Precision@10 % attendue | "
            "Lift@10 % attendu |",
            "|---|---|---|---|",
            *[f"| {100 * float(r):.0f} % par mois | {_fmt(v['proba_moyenne'])} | "
              f"{_fmt(v['precision_top10_production'], 3)} | "
              f"{_fmt(v['lift_top10_production'], 2)} |"
              for r, v in calib["sensibilite"].items()],
            "",
            "- **Lecture** : à 2 % de churn mensuel (hypothèse), le top 10 % de **tous** les "
            "clients contient environ 56 futurs churners pour 1 000, contre 20 au hasard : c'est "
            "la performance du modèle. Le chiffre de **campagne** (inactifs exclus de l'offre) "
            "est de 51 pour 1 000 (section suivante). Les départs évités dépendent du taux de "
            "succès de l'offre, à mesurer (il n'est pas dans les données).",
            "",
        ]
    lines += _business_section(cfg.paths.artifacts_dir / "kpis.json")
    from churn.business.actions import SENSITIVE_VARIABLES  # import tardif (SHAP)

    sensitive = sorted(SENSITIVE_VARIABLES - set(cfg.non_feature_columns), key=str.lower)
    lines += [
        "## Explicabilité",
        "",
        "- SHAP (`TreeExplainer`, en log-odds) sur le LightGBM, contributions regroupées sur la "
        "variable d'origine. Facteurs dominants : âge du terminal, évolution de l'usage, "
        "ancienneté (pic à 11-12 mois, fin d'engagement).",
        "- Par client : 3 **raisons actionnables** (terminal, engagement, usage, forfait, "
        "réseau, service client, lignes) qui augmentent le risque, une **action suggérée** "
        "déduite de la première, et 2 facteurs de **contexte** non actionnables.",
        "- Les raisons décrivent le modèle (« selon le modèle »), **pas des causes** du départ.",
        "",
        "## Segmentation (descriptive)",
        "",
        "- K-means à 5 segments sur 11 variables d'usage, de facture, d'ancienneté et de "
        "terminal, sans la cible, ajusté sur le train (`models/segmentation.joblib`, refait par "
        "`make train`). Sert à décrire le portefeuille ; le modèle de churn ne l'utilise pas.",
        "",
        "## Considérations éthiques",
        "",
        "- `ethnic` est exclue du modèle.",
        f"- {len(sensitive)} autres variables socio-démographiques sensibles restent des "
        "entrées du modèle (elles proviennent du jeu de données) : "
        f"{', '.join(f'`{v}`' for v in sensitive)}. Elles ne sont **jamais** affichées, "
        "jamais utilisées comme raison ou action, et jamais transmises à l'assistant IA "
        "(filtrées dans ses outils).",
        "- Le score sert à prioriser une offre de fidélisation, pas à refuser un service.",
        "",
        "## Limites",
        "",
        "- **Chiffres absolus conditionnels** : les probabilités mensuelles et les effectifs "
        "« estimation portefeuille » dépendent du taux de churn réel **supposé** (2 %, "
        "sensibilité 1-3 %) ; le classement, lui, n'en dépend pas.",
        "- **Signal faible** : aucune variable n'explique seule le churn (corrélation maximale "
        "0,13) ; le modèle combine de nombreux petits effets.",
        "- **Seuils issus de l'EDA** (11-12 mois, 300 jours) choisis sur le train : la CV est "
        "légèrement optimiste ; le test donne la mesure impartiale.",
        "- **Associations, pas causes** : un facteur associé au churn n'est pas forcément un "
        "levier d'action.",
        "- **Clients « déjà partis »** (sans usage ou sans variation d'usage) : signal réel mais "
        "de poids négligeable (test de fuite E8, D67).",
        "- **Pas de dimension temporelle** : split aléatoire, pas de validation sur une période "
        "future ; la dérive des données n'est pas suivie (hors périmètre).",
        "- **Équité non auditée** : les écarts de score selon les variables sensibles n'ont pas "
        "été mesurés.",
        "",
        "## Suivi recommandé avant un usage réel",
        "",
        "- Mesurer le vrai taux de churn mensuel et le taux de succès de l'offre (groupe "
        "témoin), puis remplacer les hypothèses de `configs/config.yaml`.",
        "- Valider sur une période future et suivre la dérive des variables et du score.",
        "- Réentraîner sans les variables socio-démographiques sensibles et mesurer le coût en "
        "AUC.",
    ]
    return "\n".join(lines) + "\n"


def write_model_card(n_train: int, path: Path | None = None) -> Path:
    """Écrit ``models/model_card.md`` et renvoie son chemin."""
    path = path or get_config().paths.models_dir / "model_card.md"
    path.write_text(build_model_card(n_train), encoding="utf-8")
    return path
