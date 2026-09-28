"""Calculs de l'analyse exploratoire (EDA), sur le jeu d'entraînement uniquement.

Les fonctions renvoient des tableaux ; les graphiques sont construits par ``churn.charts``.
Les taux de churn sont ceux de l'échantillon équilibré (~50 %) : ils servent à comparer
des groupes entre eux, pas à estimer le taux réel d'un opérateur (voir D3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.stats.proportion import proportion_confint

MISSING_LABEL = "Manquant"

# Variables numériques par bloc métier (hors socio-démographie catégorielle).
VARIABLE_BLOCKS: dict[str, list[str]] = {
    "Revenu / facture": [
        "rev_Mean", "totmrc_Mean", "ovrrev_Mean", "vceovr_Mean", "datovr_Mean", "totrev",
        "adjrev", "avgrev", "avg3rev", "avg6rev",
    ],
    "Usage": [
        "mou_Mean", "ovrmou_Mean", "plcd_vce_Mean", "plcd_dat_Mean", "recv_vce_Mean",
        "recv_sms_Mean", "comp_vce_Mean", "comp_dat_Mean", "mou_cvce_Mean", "mou_cdat_Mean",
        "mou_rvce_Mean", "peak_vce_Mean", "peak_dat_Mean", "mou_peav_Mean", "mou_pead_Mean",
        "opk_vce_Mean", "opk_dat_Mean", "mou_opkv_Mean", "mou_opkd_Mean", "attempt_Mean",
        "complete_Mean", "totcalls", "totmou", "adjmou", "adjqty", "avgmou", "avgqty",
        "avg3mou", "avg3qty", "avg6mou", "avg6qty", "roam_Mean", "da_Mean", "threeway_Mean",
        "callfwdv_Mean", "callwait_Mean", "inonemin_Mean", "owylis_vce_Mean",
        "iwylis_vce_Mean", "mouowylisv_Mean", "mouiwylisv_Mean",
    ],
    "Tendance": ["change_mou", "change_rev"],
    "Qualité réseau": [
        "drop_vce_Mean", "drop_dat_Mean", "blck_vce_Mean", "blck_dat_Mean", "unan_vce_Mean",
        "unan_dat_Mean", "drop_blk_Mean",
    ],
    "Service client": ["custcare_Mean", "ccrndmou_Mean", "cc_mou_Mean"],
    "Terminal": ["eqpdays", "hnd_price", "phones", "models"],
    "Compte": ["months", "uniqsubs", "actvsubs"],
    "Socio-démographie": ["income", "adults", "lor", "numbcars", "truck", "rv", "forgntvl"],
}

# Variables principales de chaque bloc (graphiques).
KEY_VARIABLES: dict[str, list[str]] = {
    "Revenu / facture": ["rev_Mean", "totmrc_Mean", "ovrrev_Mean", "totrev"],
    "Usage": ["mou_Mean", "ovrmou_Mean", "totcalls", "roam_Mean"],
    "Tendance": ["change_mou", "change_rev"],
    "Qualité réseau": ["drop_vce_Mean", "blck_vce_Mean", "unan_vce_Mean", "drop_blk_Mean"],
    "Service client": ["custcare_Mean", "ccrndmou_Mean"],
    "Terminal": ["eqpdays", "hnd_price", "phones", "models"],
    "Compte": ["months", "uniqsubs", "actvsubs"],
}


def describe_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Statistiques descriptives : tendance centrale, dispersion, forme, zéros, manquants."""
    data = df[columns]
    return pd.DataFrame({
        "moyenne": data.mean(),
        "mediane": data.median(),
        "ecart_type": data.std(),
        "min": data.min(),
        "max": data.max(),
        "asymetrie": data.skew(),
        "aplatissement": data.kurt(),
        "pct_zero": 100 * (data == 0).mean(),
        "pct_manquant": 100 * data.isna().mean(),
    }).round(2)


def shape_flags(stats: pd.DataFrame, skew_threshold: float = 2.0,
                zero_threshold: float = 50.0) -> pd.DataFrame:
    """Repère les variables très asymétriques et celles concentrées sur zéro."""
    return pd.DataFrame({
        "tres_asymetrique": stats["asymetrie"].abs() > skew_threshold,
        "concentree_sur_zero": stats["pct_zero"] > zero_threshold,
    })


def category_frequencies(series: pd.Series) -> pd.DataFrame:
    """Effectifs et parts par modalité ; les NaN forment la modalité ``Manquant``."""
    s = series.astype(object).fillna(MISSING_LABEL)
    counts = s.value_counts()
    return pd.DataFrame({"n": counts, "pct": (100 * counts / len(s)).round(2)})


def credit_class(series: pd.Series, min_share: float = 0.01) -> pd.Series:
    """Regroupe ``crclscod`` en classes principales : la lettre initiale du code.

    Les lettres représentant moins de ``min_share`` des clients sont réunies dans « Autres ».
    """
    letter = series.astype(object).str[0]
    share = letter.value_counts(normalize=True)
    rare = share[share < min_share].index
    return letter.where(~letter.isin(rare), "Autres")


def churn_rate_table(
    df: pd.DataFrame, group: pd.Series, target: str = "churn", sort_by_rate: bool = False
) -> pd.DataFrame:
    """Taux de churn par groupe, avec intervalle de confiance de Wilson à 95 %.

    Wilson plutôt que l'approximation normale : correct même pour des petits groupes ou
    des taux proches de 0 ou 1.

    Args:
        df: données contenant la cible.
        group: étiquette de groupe de chaque ligne (NaN -> ``Manquant``).
        target: nom de la cible.
        sort_by_rate: trier par taux décroissant (sinon ordre des catégories).

    Returns:
        Une ligne par groupe : n, churners, taux, ic_bas, ic_haut (en %), part (%).
    """
    labels = group.astype(object).where(group.notna(), MISSING_LABEL)
    if isinstance(group.dtype, pd.CategoricalDtype):
        order = [c for c in group.cat.categories if (labels == c).any()]
    else:
        values = [v for v in labels.unique() if v != MISSING_LABEL]
        numeric = all(isinstance(v, int | float | np.number) for v in values)
        order = sorted(values) if numeric else sorted(values, key=str)
    if (labels == MISSING_LABEL).any() and MISSING_LABEL not in order:
        order.append(MISSING_LABEL)
    grouped = df[target].groupby(labels.to_numpy(), sort=False).agg(["size", "sum"])
    grouped = grouped.reindex(order)
    low, high = proportion_confint(grouped["sum"], grouped["size"], alpha=0.05, method="wilson")
    out = pd.DataFrame({
        "n": grouped["size"].astype(int),
        "churners": grouped["sum"].astype(int),
        "taux": 100 * grouped["sum"] / grouped["size"],
        "ic_bas": 100 * low,
        "ic_haut": 100 * high,
        "part": 100 * grouped["size"] / len(df),
    }).round(2)
    out.index.name = group.name
    return out.sort_values("taux", ascending=False) if sort_by_rate else out


def decile_bins(series: pd.Series, q: int = 10) -> pd.Series:
    """Découpe en quantiles (déciles par défaut), étiquetés par leurs bornes.

    Les quantiles égaux (variables concentrées sur zéro) sont fusionnés. Les NaN restent
    NaN et deviennent ``Manquant`` dans :func:`churn_rate_table`.
    """
    binned = pd.qcut(series, q=q, duplicates="drop")
    labels = [f"[{iv.left:,.4g} ; {iv.right:,.4g}]" for iv in binned.cat.categories]
    return binned.cat.rename_categories(labels).rename(series.name)


def fixed_bins(series: pd.Series, edges: list[float], labels: list[str]) -> pd.Series:
    """Découpe selon des bornes fixes ``[a ; b[`` (intervalle fermé à gauche)."""
    return pd.cut(series, bins=edges, labels=labels, right=False).rename(series.name)


def two_way_rate(
    df: pd.DataFrame, rows: pd.Series, cols: pd.Series, target: str = "churn"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Taux de churn (%) et effectifs pour chaque croisement de deux groupements."""
    grouped = df[target].groupby([rows, cols], observed=True)
    rate = (100 * grouped.mean()).unstack().round(1)
    n = grouped.size().unstack().fillna(0).astype(int)
    return rate, n


def spearman_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Corrélation de Spearman (sur les rangs : robuste aux queues lourdes et aux outliers)."""
    return df[columns].corr(method="spearman").round(2)


def top_correlated_pairs(corr: pd.DataFrame, threshold: float = 0.8) -> pd.DataFrame:
    """Paires de variables dont |rho| dépasse le seuil (triangle supérieur)."""
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    pairs = corr.where(mask).stack()
    pairs = pairs[pairs.abs() >= threshold].sort_values(key=np.abs, ascending=False)
    return pairs.rename("rho").reset_index().rename(columns={"level_0": "var_1",
                                                              "level_1": "var_2"})


# --- Segmentation métier par règles fixes -------------------------------------------------
# Seuils issus de l'EDA du train (partie 2) : saut du churn à 11 mois d'ancienneté et
# vers 305 jours d'âge du terminal, compatibles avec une fin d'engagement à 12 mois.
TENURE_EDGES = [0, 11, 13, np.inf]
TENURE_LABELS = ["6-10 mois", "11-12 mois", ">= 13 mois"]
USAGE_EDGES = [0, 150, 700, np.inf]
USAGE_LABELS = ["Usage faible (< 150 min)", "Usage moyen (150-699 min)", "Usage fort (>= 700 min)"]
DEVICE_EDGES = [0, 300, 730, np.inf]
DEVICE_LABELS = ["Terminal < 300 j", "Terminal 300-729 j", "Terminal >= 730 j"]


def business_segments(df: pd.DataFrame) -> pd.DataFrame:
    """Affecte chaque client à un segment ancienneté x usage x âge du terminal.

    Seuils fixes et lisibles, énonçables à un métier : ancienneté 11 et 13 mois (fenêtre de
    fin d'engagement), usage 150 et 700 minutes/mois (proches des quartiles du train),
    terminal 300 et 730 jours.

    Returns:
        DataFrame avec les colonnes ``anciennete``, ``usage``, ``terminal`` (NaN si la
        variable source manque).
    """
    return pd.DataFrame({
        "anciennete": fixed_bins(df["months"], TENURE_EDGES, TENURE_LABELS),
        "usage": fixed_bins(df["mou_Mean"], USAGE_EDGES, USAGE_LABELS),
        "terminal": fixed_bins(df["eqpdays"], DEVICE_EDGES, DEVICE_LABELS),
    }, index=df.index)


def segment_table(
    df: pd.DataFrame, segments: pd.DataFrame, target: str = "churn", min_size: int = 0
) -> pd.DataFrame:
    """Taille, part, taux de churn (IC 95 % Wilson) et écart à la moyenne de chaque segment."""
    complete = segments.notna().all(axis=1)
    seg, y = segments[complete], df.loc[complete, target]
    grouped = y.groupby([seg[c] for c in seg.columns], observed=True).agg(["size", "sum"])
    low, high = proportion_confint(grouped["sum"], grouped["size"], alpha=0.05, method="wilson")
    overall = df[target].mean()
    out = pd.DataFrame({
        "n": grouped["size"],
        "part": 100 * grouped["size"] / len(df),
        "taux": 100 * grouped["sum"] / grouped["size"],
        "ic_bas": 100 * low,
        "ic_haut": 100 * high,
        "ecart_pts": 100 * (grouped["sum"] / grouped["size"] - overall),
    }).round(2)
    return out[out["n"] >= min_size].sort_values("taux", ascending=False)


def decile_contrast(df: pd.DataFrame, columns: list[str], target: str = "churn") -> pd.DataFrame:
    """Classe les numériques selon l'amplitude du taux de churn entre leurs déciles.

    ``amplitude_pts`` = taux max - taux min parmi les déciles (hors manquants) : une mesure
    simple et non paramétrique de l'intensité du lien, qui capte aussi les relations non
    monotones. ``rho`` (Spearman) en donne le sens et la monotonie.
    """
    rows = []
    for col in columns:
        table = churn_rate_table(df, decile_bins(df[col]), target)
        table = table.drop(index=MISSING_LABEL, errors="ignore")
        rows.append({
            "variable": col,
            "n_classes": len(table),
            "taux_min": table["taux"].min(),
            "taux_max": table["taux"].max(),
            "amplitude_pts": round(table["taux"].max() - table["taux"].min(), 1),
            "rho": round(df[[col, target]].corr(method="spearman").iloc[0, 1], 3),
        })
    return pd.DataFrame(rows).set_index("variable").sort_values("amplitude_pts",
                                                                ascending=False)


def categorical_contrast(df: pd.DataFrame, columns: list[str], target: str = "churn",
                         min_n: int = 500) -> pd.DataFrame:
    """Classe les catégorielles selon l'écart de taux entre modalités et le V de Cramér.

    L'écart ne considère que les modalités d'au moins ``min_n`` clients (taux stables).
    """
    from scipy.stats import chi2_contingency

    rows = []
    for col in columns:
        labels = df[col].astype(object).fillna(MISSING_LABEL)
        table = churn_rate_table(df, labels, target)
        big = table[table["n"] >= min_n]
        crosstab = pd.crosstab(labels, df[target])
        chi2 = chi2_contingency(crosstab, correction=False)[0]
        v = np.sqrt(chi2 / (len(df) * (min(crosstab.shape) - 1)))
        rows.append({
            "variable": col,
            "n_modalites": len(table),
            "modalite_min": big["taux"].idxmin(),
            "taux_min": big["taux"].min(),
            "modalite_max": big["taux"].idxmax(),
            "taux_max": big["taux"].max(),
            "ecart_pts": round(big["taux"].max() - big["taux"].min(), 1),
            "cramers_v": round(float(v), 3),
        })
    return pd.DataFrame(rows).set_index("variable").sort_values("cramers_v", ascending=False)
