"""Segmentation comportementale par K-means.

Les clusters sont construits **sans la cible** : on regroupe les clients par profil
(usage, facture, ancienneté, terminal, service client, qualité réseau), puis on mesure
le churn de chaque profil a posteriori.

Pipeline : sélection des variables -> imputation médiane -> log sur les variables
asymétriques -> standardisation -> KMeans. Tout est appris sur le train uniquement ; le
pipeline sauvegardé attribue ensuite un segment à n'importe quel client.
"""

from __future__ import annotations

import logging
from itertools import combinations
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from churn.config import get_config

logger = logging.getLogger(__name__)

# Variables très asymétriques et positives : log(1 + x).
LOG_FEATURES = ["mou_Mean", "rev_Mean", "totmrc_Mean", "ovrrev_Mean", "custcare_Mean",
                "drop_blk_Mean", "uniqsubs"]
# Variable signée à queues lourdes des deux côtés : signe(x) * log(1 + |x|).
SIGNED_LOG_FEATURES = ["change_mou"]
# Distributions proches de la symétrie (|asymétrie| <= 1,1) : pas de transformation.
RAW_FEATURES = ["months", "eqpdays", "hnd_price"]
FEATURES = LOG_FEATURES + SIGNED_LOG_FEATURES + RAW_FEATURES

SEGMENTATION_FILE = "segmentation.joblib"


def log1p_positive(x: np.ndarray) -> np.ndarray:
    """``log(1 + x)`` après écrêtage à 0 (robuste à une valeur négative inattendue)."""
    return np.log1p(np.clip(x, 0, None))


def signed_log1p(x: np.ndarray) -> np.ndarray:
    """Log symétrique ``signe(x) * log(1 + |x|)`` : réduit les deux queues, garde le signe."""
    return np.sign(x) * np.log1p(np.abs(x))


def _branch(func: Any) -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("transform", FunctionTransformer(func, feature_names_out="one-to-one")),
    ])


def build_preprocessor() -> ColumnTransformer:
    """Sélection + imputation médiane + log, sans standardisation.

    Les variables absentes de ``FEATURES`` sont ignorées (``remainder="drop"``) : on peut
    passer le DataFrame complet d'un client.
    """
    return ColumnTransformer(
        [
            ("log", _branch(log1p_positive), LOG_FEATURES),
            ("signed_log", _branch(signed_log1p), SIGNED_LOG_FEATURES),
            ("raw", SimpleImputer(strategy="median"), RAW_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")


def build_segmentation_pipeline(n_clusters: int, random_state: int | None = None,
                                n_init: int = 10) -> Pipeline:
    """Pipeline complet de segmentation (non entraîné).

    Args:
        n_clusters: nombre de segments k.
        random_state: graine de KMeans (par défaut celle de la config).
        n_init: nombre d'initialisations de KMeans ; la meilleure (inertie minimale) est gardée.
    """
    seed = get_config().random_state if random_state is None else random_state
    return Pipeline([
        ("preprocess", build_preprocessor()),
        ("scale", StandardScaler().set_output(transform="pandas")),
        ("kmeans", KMeans(n_clusters=n_clusters, random_state=seed, n_init=n_init)),
    ])


def transform_features(df: pd.DataFrame) -> pd.DataFrame:
    """Matrice standardisée vue par KMeans (prétraitement et scaling ajustés sur ``df``)."""
    pre = Pipeline([("preprocess", build_preprocessor()),
                    ("scale", StandardScaler().set_output(transform="pandas"))])
    return pre.fit_transform(df)


def evaluate_k(
    X: pd.DataFrame,
    ks: range,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4),
    silhouette_sample: int = 10_000,
    random_state: int | None = None,
) -> pd.DataFrame:
    """Critères de choix de k sur une matrice déjà standardisée.

    - inertie (coude) ;
    - silhouette sur un échantillon (coût quadratique en n) ; plus haut = mieux ;
    - Davies-Bouldin sur toutes les lignes ; plus bas = mieux ;
    - stabilité : ARI moyen entre les partitions obtenues avec ``seeds`` ; 1 = identiques.

    Returns:
        Une ligne par k.
    """
    seed = get_config().random_state if random_state is None else random_state
    rows = []
    for k in ks:
        model = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(X)
        labels = model.labels_
        runs = [KMeans(n_clusters=k, random_state=s, n_init=10).fit_predict(X) for s in seeds]
        aris = [adjusted_rand_score(a, b) for a, b in combinations(runs, 2)]
        sizes = np.bincount(labels)
        rows.append({
            "k": k,
            "inertie": model.inertia_,
            "silhouette": silhouette_score(X, labels, sample_size=min(silhouette_sample, len(X)),
                                           random_state=seed),
            "davies_bouldin": davies_bouldin_score(X, labels),
            "ari_moyen": float(np.mean(aris)),
            "ari_min": float(np.min(aris)),
            "plus_petit_cluster_pct": round(100 * sizes.min() / len(X), 1),
        })
        logger.info("k=%d évalué", k)
    return pd.DataFrame(rows).set_index("k")


def cluster_profiles(df: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Médianes des variables d'origine par cluster (lisibles par un métier), avec la taille."""
    profile = df[FEATURES].groupby(labels).median()
    sizes = pd.Series(labels).value_counts().sort_index()
    profile.insert(0, "part_%", (100 * sizes / sizes.sum()).round(1).to_numpy())
    profile.insert(0, "n", sizes.to_numpy())
    profile.index.name = "cluster"
    return profile


def cluster_zscores(X: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Moyenne des variables standardisées par cluster (écart à la moyenne en écarts-types)."""
    z = X.groupby(labels).mean()
    z.index.name = "cluster"
    return z


def save_segmentation(bundle: dict[str, Any], path: Path | None = None) -> Path:
    """Sauvegarde le pipeline entraîné et ses métadonnées (noms métier, variables, k)."""
    path = path or get_config().paths.models_dir / SEGMENTATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    logger.info("Segmentation sauvegardée : %s", path)
    return path


def load_segmentation(path: Path | None = None) -> dict[str, Any]:
    """Charge le bundle ``{"pipeline", "segment_names", "features", "k", ...}``."""
    return joblib.load(path or get_config().paths.models_dir / SEGMENTATION_FILE)


def assign_segments(df: pd.DataFrame, bundle: dict[str, Any] | None = None) -> pd.DataFrame:
    """Attribue un segment (identifiant et nom métier) à chaque client de ``df``."""
    bundle = bundle or load_segmentation()
    ids = bundle["pipeline"].predict(df)
    return pd.DataFrame({"segment_id": ids,
                         "segment": [bundle["segment_names"][i] for i in ids]}, index=df.index)


# --- Modèle retenu (notebook 02b) ----------------------------------------------------------
N_CLUSTERS = 5

NAME_SECONDARY_LINES = "Lignes secondaires à petit forfait"
NAME_HEAVY_DECLINING = "Gros consommateurs en baisse d'usage"
NAME_HEAVY_GROWING = "Gros consommateurs en hausse d'usage"
NAME_MODERATE_RECENT = "Usage modéré, clients récents"
NAME_TENURED_OLD_DEVICE = "Clients anciens à terminal ancien et bon marché"


def name_clusters(profile: pd.DataFrame) -> dict[int, str]:
    """Attribue un nom métier à chaque cluster à partir de son profil médian (k = 5).

    Règles explicites plutôt qu'identifiants codés en dur : les numéros de cluster de
    KMeans sont arbitraires, les règles restent vraies si l'ordre change.

    - ancienneté médiane maximale -> clients anciens à terminal ancien ;
    - abonnement mensuel médian minimal -> lignes secondaires à petit forfait ;
    - parmi les trois autres, les deux plus gros usages -> gros consommateurs, en baisse ou
      en hausse selon le signe de ``change_mou`` ; le dernier -> usage modéré.

    Raises:
        ValueError: si k != 5 ou si les règles ne donnent pas 5 noms distincts.
    """
    if len(profile) != N_CLUSTERS:
        raise ValueError(f"Nommage défini pour k = {N_CLUSTERS}, reçu k = {len(profile)}")
    names: dict[int, str] = {}
    names[int(profile["months"].idxmax())] = NAME_TENURED_OLD_DEVICE
    names[int(profile["totmrc_Mean"].idxmin())] = NAME_SECONDARY_LINES
    rest = profile.drop(index=list(names))
    heavy = rest["mou_Mean"].nlargest(2).index
    for idx in heavy:
        names[int(idx)] = (NAME_HEAVY_DECLINING if rest.loc[idx, "change_mou"] < 0
                           else NAME_HEAVY_GROWING)
    for idx in rest.index.difference(heavy):
        names[int(idx)] = NAME_MODERATE_RECENT
    if len(set(names.values())) != N_CLUSTERS:
        raise ValueError(f"Nommage ambigu : {names}")
    return dict(sorted(names.items()))


def fit_segmentation(train: pd.DataFrame, n_clusters: int = N_CLUSTERS) -> dict[str, Any]:
    """Entraîne la segmentation sur le train et renvoie le bundle à sauvegarder.

    La cible n'est jamais lue : ``FEATURES`` ne la contient pas.
    """
    pipeline = build_segmentation_pipeline(n_clusters).fit(train)
    labels = pipeline.predict(train)
    X = pipeline[:-1].transform(train)
    profile = cluster_profiles(train, labels)
    sil = silhouette_score(X, labels, sample_size=min(10_000, len(X)),
                           random_state=get_config().random_state)
    return {
        "pipeline": pipeline,
        "segment_names": name_clusters(profile),
        "features": FEATURES,
        "k": n_clusters,
        "silhouette": float(sil),
        "profile": profile,
        "trained_on": "data/processed/train.parquet",
    }


def segment_auc_cv(segments: pd.Series, y: pd.Series, n_splits: int = 5,
                   random_state: int | None = None) -> tuple[float, float]:
    """AUC en validation croisée d'un score = taux de churn du segment (appris hors fold).

    Mesure à quel point une segmentation **ordonne** les clients selon leur risque, en
    comparant équitablement des segmentations de tailles différentes : le taux de chaque
    segment est calculé sur les folds d'entraînement et appliqué au fold de validation.

    Returns:
        (AUC moyenne, écart-type entre folds).
    """
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold

    seed = get_config().random_state if random_state is None else random_state
    seg = segments.astype(str).to_numpy()
    y_arr = y.to_numpy()
    aucs = []
    for tr_idx, va_idx in StratifiedKFold(n_splits, shuffle=True,
                                          random_state=seed).split(seg, y_arr):
        rates = pd.Series(y_arr[tr_idx]).groupby(seg[tr_idx]).mean()
        score = pd.Series(seg[va_idx]).map(rates).fillna(y_arr[tr_idx].mean())
        aucs.append(roc_auc_score(y_arr[va_idx], score))
    return float(np.mean(aucs)), float(np.std(aucs))
