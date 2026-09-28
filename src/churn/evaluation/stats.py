"""Tests statistiques univariés (variable x churn) et analyse de redondance.

- Numériques : Mann-Whitney U (non paramétrique, robuste aux queues lourdes) + corrélation
  rank-biserial, taille d'effet d'un **décalage monotone** des distributions.
- Catégorielles et binaires : χ² d'indépendance + V de Cramér.
- Relations non monotones : écart maximal de taux de churn entre classes (déciles ou
  modalités) et information mutuelle, qui détectent un pic ou un creux qu'une corrélation
  (même de rang) ne voit pas.
- Correction de Holm sur l'ensemble des tests.
- Redondance : paires de Spearman, clustering hiérarchique des variables, VIF itératif.

Avec n = 80 000, presque tout est « significatif » : la décision repose sur la taille
d'effet et l'information mutuelle ; la p-value ne sert qu'à écarter le bruit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import chi2_contingency, fisher_exact, mannwhitneyu, spearmanr
from sklearn.feature_selection import mutual_info_classif
from statsmodels.stats.multitest import multipletests

from churn.eda import MISSING_LABEL, churn_rate_table, decile_bins

RARE_LABEL = "Rare"
# Seuils de Cohen, valables pour |r| et pour V quand la cible est binaire (ddl* = 1).
EFFECT_THRESHOLDS = ((0.1, "négligeable"), (0.3, "faible"), (0.5, "moyen"))
NON_MONOTONE_SPREAD_PTS = 10.0
MONOTONE_CURVE_RHO = 0.8
DISCRETE_MAX_LEVELS = 30


def interpret_effect(value: float) -> str:
    """Qualifie une taille d'effet (|rank-biserial| ou V de Cramér) selon Cohen."""
    size = abs(value)
    for threshold, label in EFFECT_THRESHOLDS:
        if size < threshold:
            return label
    return "fort"


# --- Tests -------------------------------------------------------------------------------
def mann_whitney_rank_biserial(x: pd.Series, y: pd.Series) -> dict[str, float]:
    """Mann-Whitney U churners (y = 1) contre non-churners (y = 0), NaN exclus.

    Rank-biserial ``r = 2U / (n1 * n0) - 1`` (U des churners) : probabilité qu'un churner
    ait une valeur plus élevée qu'un non-churner, ramenée sur [-1, 1]. r > 0 : valeurs plus
    élevées chez les churners ; r ≈ 0 : **pas de décalage**, ce qui n'exclut pas un lien
    non monotone.
    """
    mask = x.notna()
    x1, x0 = x[mask & (y == 1)].to_numpy(), x[mask & (y == 0)].to_numpy()
    u, p = mannwhitneyu(x1, x0, alternative="two-sided")
    return {"statistique": float(u), "p_value": float(p),
            "effet": float(2 * u / (len(x1) * len(x0)) - 1), "n": int(mask.sum())}


def _categorical_labels(x: pd.Series, min_count: int) -> pd.Series:
    """NaN -> « Manquant » ; modalités < ``min_count`` -> « Rare » ; « Rare » trop petit -> NaN."""
    labels = x.astype(object).where(x.notna(), MISSING_LABEL)
    counts = labels.value_counts()
    labels = labels.where(~labels.isin(counts[counts < min_count].index), RARE_LABEL)
    if 0 < (labels == RARE_LABEL).sum() < min_count:
        labels = labels.where(labels != RARE_LABEL)
    return labels


def chi2_cramers_v(x: pd.Series, y: pd.Series, min_count: int = 30) -> dict[str, float]:
    """χ² d'indépendance modalité x cible et V de Cramér ; les NaN forment une modalité.

    Catégorielle : les modalités de moins de ``min_count`` clients sont regroupées dans
    « Rare » ; si ce groupe reste sous ``min_count``, ses lignes sont exclues (``n`` =
    lignes testées). Binaire : aucun regroupement (il supprimerait la classe minoritaire) ;
    si un effectif attendu est < 5, la p-value vient du **test exact de Fisher**, valide
    pour les petits effectifs, et V reste calculé à partir du χ².
    """
    raw = x.astype(object).where(x.notna(), MISSING_LABEL)
    labels = raw if raw.nunique() <= 2 else _categorical_labels(x, min_count)
    keep = labels.notna()
    table = pd.crosstab(labels[keep], y[keep])
    chi2, p, dof, expected = chi2_contingency(table, correction=False)
    test = "χ²"
    if table.shape == (2, 2) and (expected < 5).any():
        p = fisher_exact(table.to_numpy())[1]
        test = "Fisher exact"
    v = np.sqrt(chi2 / (table.to_numpy().sum() * (min(table.shape) - 1)))
    return {"test": test, "statistique": float(chi2), "p_value": float(p), "effet": float(v),
            "n": int(table.to_numpy().sum()), "ddl": int(dof),
            "pct_cellules_attendu_lt5": float(100 * (expected < 5).mean())}


# --- Relations non monotones -----------------------------------------------------------
def class_profile(df: pd.DataFrame, col: str, target: str, numeric: bool,
                  min_n: int = 200) -> tuple[float, str]:
    """Écart maximal de taux de churn (points) entre classes, et forme de la courbe.

    Classes = déciles (numérique) ou modalités (catégorielle) ; classes de moins de
    ``min_n`` clients ignorées ; manquants d'une numérique exclus (couverts par les
    indicateurs). Forme (numériques) : « monotone » si le rang des déciles et leur taux
    sont liés par |ρ| >= 0,8, « non monotone » sinon (pic, creux, plateau) ; « sans objet »
    pour une catégorielle (modalités non ordonnées).
    """
    groups = decile_bins(df[col]) if numeric else df[col]
    table = churn_rate_table(df, groups, target)
    if numeric:
        table = table.drop(index=MISSING_LABEL, errors="ignore")
    table = table[table["n"] >= min_n]
    if len(table) < 2:
        return 0.0, "sans objet"
    spread = float(table["taux"].max() - table["taux"].min())
    if not numeric:
        return spread, "sans objet"
    if len(table) < 3:
        return spread, "monotone"
    rho = spearmanr(np.arange(len(table)), table["taux"].to_numpy())[0]
    return spread, "monotone" if abs(rho) >= MONOTONE_CURVE_RHO else "non monotone"


def mutual_information(df: pd.DataFrame, col: str, target: str, numeric: bool,
                       random_state: int = 42) -> float:
    """Information mutuelle (nats) entre une variable et la cible.

    Nulle si et seulement si variable et cible sont indépendantes, **quelle que soit la
    forme du lien** (monotone ou non). Numérique à plus de 30 valeurs distinctes :
    estimateur par plus proches voisins, sur les lignes renseignées ; sinon (catégorielle,
    ou entier à peu de valeurs comme ``uniqsubs``, dont les ex aequo biaisent l'estimateur
    continu) : estimateur discret, NaN = modalité.
    """
    if numeric and df[col].nunique() > DISCRETE_MAX_LEVELS:
        mask = df[col].notna()
        x = df.loc[mask, [col]].to_numpy(dtype=float)
        y = df.loc[mask, target].to_numpy()
        discrete = False
    else:
        codes = pd.factorize(df[col].astype(object).fillna(MISSING_LABEL))[0]
        x, y, discrete = codes.reshape(-1, 1), df[target].to_numpy(), True
    return float(mutual_info_classif(x, y, discrete_features=discrete,
                                     random_state=random_state)[0])


# --- Tableau récapitulatif ---------------------------------------------------------------
def univariate_table(df: pd.DataFrame, target: str, numeric: list[str],
                     categorical: list[str], alpha: float = 0.05,
                     random_state: int = 42) -> pd.DataFrame:
    """Tous les tests variable x cible : Holm, tailles d'effet, écart entre classes, info mutuelle.

    Returns:
        Une ligne par variable, triée par information mutuelle décroissante.
    """
    y = df[target]
    rows = []
    for col in numeric:
        spread, shape = class_profile(df, col, target, numeric=True)
        rows.append({"variable": col, "type": "numérique", "test": "Mann-Whitney U",
                     "mesure_effet": "rank-biserial",
                     **mann_whitney_rank_biserial(df[col], y),
                     "ecart_classes_pts": spread, "forme_courbe": shape,
                     "info_mutuelle": mutual_information(df, col, target, True, random_state)})
    for col in categorical:
        res = chi2_cramers_v(df[col], y)
        spread, shape = class_profile(df, col, target, numeric=False)
        kind = "binaire" if df[col].nunique(dropna=False) <= 2 else "catégorielle"
        rows.append({"variable": col, "type": kind, "mesure_effet": "V de Cramér",
                     **{k: res[k] for k in ("test", "statistique", "p_value", "effet", "n")},
                     "ecart_classes_pts": spread, "forme_courbe": shape,
                     "info_mutuelle": mutual_information(df, col, target, False, random_state)})
    out = pd.DataFrame(rows).set_index("variable")
    reject, p_adj, _, _ = multipletests(out["p_value"], alpha=alpha, method="holm")
    out["p_ajustee_holm"] = p_adj
    out["significatif_holm"] = reject
    out["effet_abs"] = out["effet"].abs()
    out["interpretation"] = out["effet"].map(interpret_effect)
    out["relation_non_monotone"] = ((out["effet_abs"] < EFFECT_THRESHOLDS[0][0])
                                    & (out["ecart_classes_pts"] > NON_MONOTONE_SPREAD_PTS))
    out = out.sort_values("info_mutuelle", ascending=False)
    out.insert(0, "rang", range(1, len(out) + 1))
    return out


def p_value_vs_sample_size(x: pd.Series, y: pd.Series, sizes: list[int],
                           random_state: int = 42) -> pd.DataFrame:
    """Même variable, échantillons croissants : l'effet se stabilise, la p-value s'effondre."""
    rows = []
    for n in sizes:
        idx = y.sample(n=min(n, len(y)), random_state=random_state).index
        res = mann_whitney_rank_biserial(x.loc[idx], y.loc[idx])
        rows.append({"n": n, "p_value": res["p_value"], "rank_biserial": res["effet"]})
    return pd.DataFrame(rows).set_index("n")


# --- Redondance --------------------------------------------------------------------------
def spearman_redundant_pairs(corr: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """Paires de variables dont |ρ| dépasse ``threshold`` (triangle supérieur)."""
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    pairs = corr.where(mask).stack()
    pairs = pairs[pairs.abs() > threshold].sort_values(key=np.abs, ascending=False)
    return (pairs.rename("rho").round(3).reset_index()
            .rename(columns={"level_0": "var_1", "level_1": "var_2"}))


def variable_clusters(corr: pd.DataFrame, threshold: float = 0.9,
                      method: str = "average") -> pd.Series:
    """Clustering hiérarchique des variables sur la distance ``1 - |ρ|`` (lien moyen).

    Un groupe réunit des variables reliées à une distance < ``1 - threshold`` : des
    variables quasi interchangeables, dont une seule représentante suffit.
    """
    dist = squareform((1 - corr.abs()).clip(lower=0).to_numpy(), checks=False)
    groups = fcluster(linkage(dist, method=method), t=1 - threshold, criterion="distance")
    return pd.Series(groups, index=corr.index, name="groupe")


def choose_representatives(groups: pd.Series, importance: pd.Series,
                           preferred: tuple[str, ...] = ()) -> pd.DataFrame:
    """Une représentante par groupe redondant ; les autres sont à retirer.

    Représentante = variable de ``preferred`` présente dans le groupe (choix
    d'interprétabilité), sinon la plus liée au churn (``importance`` maximale).

    Returns:
        Une ligne par variable des groupes de taille > 1 : groupe, représentante, garder.
    """
    rows = []
    for gid, members in groups.groupby(groups):
        cols = list(members.index)
        if len(cols) == 1:
            continue
        pref = [c for c in preferred if c in cols]
        rep = pref[0] if pref else max(cols, key=lambda c: importance.get(c, 0.0))
        rows += [{"variable": c, "groupe": int(gid), "representante": rep,
                  "garder": c == rep, "info_mutuelle": importance.get(c, np.nan)} for c in cols]
    return pd.DataFrame(rows).set_index("variable")


def prepare_for_linear(df: pd.DataFrame, columns: list[str],
                       skew_threshold: float = 2.0) -> pd.DataFrame:
    """Version « régression logistique » des variables : médiane, log si asymétrique, z-score.

    log(1 + x) si positive et |asymétrie| > seuil ; log symétrique si elle a des négatifs.
    Sert au VIF ; le vrai prétraitement sera appris dans le pipeline (E6-E7).
    """
    X = df[columns].astype(float)
    X = X.fillna(X.median())
    for col in columns:
        if abs(X[col].skew()) > skew_threshold:
            has_negatives = (X[col] < 0).any()
            X[col] = (np.sign(X[col]) * np.log1p(X[col].abs())) if has_negatives \
                else np.log1p(X[col])
    return (X - X.mean()) / X.std(ddof=0)


def vif_table(X: pd.DataFrame) -> pd.Series:
    """VIF de chaque variable : diagonale de l'inverse de la matrice de corrélation.

    Équivalent à VIF_j = 1 / (1 - R²_j) (régression de j sur les autres, avec constante),
    en une seule inversion. Repères : > 5 préoccupant, > 10 colinéarité forte.
    """
    corr = np.corrcoef(X.to_numpy(dtype=float), rowvar=False)
    vif = np.diag(np.linalg.pinv(corr))
    return pd.Series(vif, index=X.columns, name="vif").sort_values(ascending=False)


def iterative_vif(X: pd.DataFrame, threshold: float = 10.0) -> tuple[list[str], pd.DataFrame]:
    """Retire la variable au VIF maximal tant qu'il dépasse ``threshold``.

    Returns:
        (variables conservées, historique des retraits : variable, VIF au retrait, étape).
    """
    kept = list(X.columns)
    removed = []
    while len(kept) > 1:
        vif = vif_table(X[kept])
        if vif.iloc[0] <= threshold:
            break
        removed.append({"variable": vif.index[0], "vif": round(float(vif.iloc[0]), 2),
                        "etape": len(removed) + 1})
        kept.remove(vif.index[0])
    return kept, pd.DataFrame(removed, columns=["variable", "vif", "etape"]).set_index("variable")


# --- Sorties pour E6 et E7 ---------------------------------------------------------------
# Représentantes préférées dans un groupe redondant : variables déjà utilisées en EDA et en
# segmentation, lisibles par un métier. Les écarts d'information mutuelle à l'intérieur d'un
# groupe (< 0,001 nat) sont du niveau du bruit de l'estimateur : ils ne départagent pas.
PREFERRED_REPRESENTATIVES = ("mou_Mean", "rev_Mean", "custcare_Mean", "ovrrev_Mean",
                             "totrev", "totcalls", "phones", "recv_vce_Mean")


def export_outputs(univariate: pd.DataFrame, representatives: pd.DataFrame,
                   vif_removed: pd.DataFrame, directory, top_n: int = 15) -> dict[str, str]:
    """Écrit les sorties de l'analyse statistique dans ``directory`` (``reports/``).

    - ``stats_univariate.csv`` : tableau complet ;
    - ``top15_importance.csv`` : guide pour le feature engineering (E6) ;
    - ``logreg_drop_list.json`` : variables à retirer pour la régression logistique (E7),
      avec la raison (redondance ou VIF).

    Returns:
        Chemins écrits, par type de sortie.
    """
    import json
    from pathlib import Path

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "univariate": directory / "stats_univariate.csv",
        "top": directory / f"top{top_n}_importance.csv",
        "drop": directory / "logreg_drop_list.json",
    }
    univariate.to_csv(paths["univariate"], encoding="utf-8")
    redundant = representatives[~representatives["garder"]]
    dropped = set(redundant.index) | set(vif_removed.index)
    cols = ["rang", "type", "test", "effet", "interpretation", "ecart_classes_pts",
            "forme_courbe", "info_mutuelle", "p_ajustee_holm"]
    top = univariate.head(top_n)[cols].copy()
    # Une variable du top peut doubler une autre (même groupe redondant) : à savoir en E6.
    top["a_retirer_logreg"] = top.index.isin(dropped)
    reps = [redundant["representante"].get(v, v) for v in top.index]
    top["representante"] = [f"{r} (retirée, VIF)" if r in vif_removed.index else r for r in reps]
    top.to_csv(paths["top"], encoding="utf-8")
    drop = {
        "description": "Variables numériques à retirer pour la régression logistique (E7). "
                       "Les modèles à arbres peuvent garder toutes les variables.",
        "redondance_spearman_0_9": [
            {"variable": v, "representante": r} for v, r in redundant["representante"].items()],
        "vif_sup_10": [{"variable": v, "vif": float(x)} for v, x in vif_removed["vif"].items()],
    }
    drop["toutes"] = ([d["variable"] for d in drop["redondance_spearman_0_9"]]
                      + [d["variable"] for d in drop["vif_sup_10"]])
    paths["drop"].write_text(json.dumps(drop, ensure_ascii=False, indent=2), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}
