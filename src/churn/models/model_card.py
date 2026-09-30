"""Génération de la fiche du modèle (``models/model_card.md``).

La fiche est construite à partir de la configuration (modèle, paramètres, familles de
features, variables exclues) et des métriques enregistrées par le notebook 06 :
``reports/selection_grid_cv.csv`` (CV) et ``reports/final_metrics.json`` (test).
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
        "- **Sortie** : score de risque (probabilité sur l'échantillon équilibré, **non calibrée** "
        "à ce stade : calibration et correction vers le taux réel en E10).",
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
        "- **Test** : `data/processed/test.parquet`, 20 000 clients, lu **une seule fois** (E9).",
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
    lines += [
        "## Limites",
        "",
        "- **Probabilités non calibrées** et issues d'un échantillon équilibré : ne pas les lire "
        "comme des probabilités réelles avant E10.",
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
    ]
    return "\n".join(lines) + "\n"


def write_model_card(n_train: int, path: Path | None = None) -> Path:
    """Écrit ``models/model_card.md`` et renvoie son chemin."""
    path = path or get_config().paths.models_dir / "model_card.md"
    path.write_text(build_model_card(n_train), encoding="utf-8")
    return path
