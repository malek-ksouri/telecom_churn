"""Prétraitement de la régression logistique améliorée (E7).

Tout ce qui apprend des données est **dans** le pipeline, donc ajusté sur la seule partie
apprentissage de chaque fold :

- médiane d'imputation ;
- bornes de winsorisation (quantiles 1 % et 99 %) ;
- moyenne et écart-type de standardisation ;
- nœuds des splines (quantiles) ;
- modalités retenues par l'encodage one-hot (fréquence >= 1 %).

Les listes de colonnes (log, splines) sont des choix structurels fixes issus de l'EDA (E4).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    FunctionTransformer,
    OneHotEncoder,
    SplineTransformer,
    StandardScaler,
)

from churn.config import get_config
from churn.data.validate import BINARY_COLUMNS, CATEGORICAL_COLUMNS
from churn.features.build import MISSING_PATTERNS, FeatureBuilder
from churn.models.pipelines import ColumnDropper, categories_as_text, non_feature_columns

# Variables à queue droite très longue (asymétrie > 2 et valeurs >= 0 sur le train, critère
# de E4), après construction des features et liste de retrait de E5 : log(1 + x).
LOG_COLUMNS: tuple[str, ...] = (
    "actvsubs", "avgqty", "avgrev", "blck_dat_Mean", "blck_vce_Mean", "callfwdv_Mean",
    "callwait_Mean", "custcare_Mean", "da_Mean", "datovr_Mean", "drop_dat_Mean",
    "drop_vce_Mean", "mou_Mean", "mou_cvce_Mean", "mouiwylisv_Mean", "mouowylisv_Mean",
    "opk_dat_Mean", "ovrrev_Mean", "peak_dat_Mean", "phones", "phones_per_month",
    "recurring_share_rev", "recv_sms_Mean", "recv_vce_Mean", "rev_Mean", "roam_Mean",
    "threeway_Mean", "unan_dat_Mean", "unan_vce_Mean", "uniqsubs",
)
# Variables signées à queues lourdes des deux côtés : signe(x) * log(1 + |x|).
SIGNED_LOG_COLUMNS: tuple[str, ...] = ("change_mou", "change_rev")
# Relations non monotones (E4, E5) : représentées par des B-splines.
SPLINE_COLUMNS: tuple[str, ...] = ("months", "eqpdays")


def log1p_nonneg(x: np.ndarray) -> np.ndarray:
    """log(1 + x) après écrêtage à 0 ; les NaN restent NaN (imputés ensuite)."""
    return np.log1p(np.clip(x, 0, None))


def signed_log1p(x: np.ndarray) -> np.ndarray:
    """signe(x) * log(1 + |x|) : réduit les deux queues, garde le signe ; NaN conservés."""
    return np.sign(x) * np.log1p(np.abs(x))


class Winsorizer(BaseEstimator, TransformerMixin):
    """Écrête chaque colonne à ses quantiles ``lower`` et ``upper`` **appris dans fit**.

    Les bornes sont calculées sur les données d'ajustement (NaN ignorés) puis appliquées
    telles quelles à toute nouvelle donnée : aucune information du fold de validation.

    Si les deux quantiles sont égaux (indicateur 0/1 présent chez moins de 1 % des clients,
    variable nulle à plus de 99 %), la colonne n'est **pas** écrêtée : sinon elle deviendrait
    constante et son information serait effacée. ``keep_degenerate=False`` reproduit l'ancien
    comportement (défaut corrigé en E7), pour mesurer son effet.
    """

    def __init__(self, lower: float = 0.01, upper: float = 0.99,
                 keep_degenerate: bool = True) -> None:
        self.lower = lower
        self.upper = upper
        self.keep_degenerate = keep_degenerate

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> Winsorizer:
        """Apprend les bornes basse et haute de chaque colonne."""
        values = np.asarray(X, dtype=float)
        low = np.nanquantile(values, self.lower, axis=0)
        high = np.nanquantile(values, self.upper, axis=0)
        degenerate = (high <= low) if self.keep_degenerate else np.zeros_like(low, dtype=bool)
        self.lower_bounds_ = np.where(degenerate, -np.inf, low)
        self.upper_bounds_ = np.where(degenerate, np.inf, high)
        self.n_features_in_ = values.shape[1]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Écrête aux bornes apprises ; les NaN restent NaN."""
        return np.clip(np.asarray(X, dtype=float), self.lower_bounds_, self.upper_bounds_)

    def get_feature_names_out(self, input_features: Sequence[str] | None = None) -> np.ndarray:
        """Mêmes noms en sortie qu'en entrée."""
        return np.asarray(input_features, dtype=object)


class ColumnSubset:
    """Sélecteur de colonnes pour ``ColumnTransformer`` : les colonnes listées présentes dans X.

    Contrairement à une liste fixe, il tolère qu'une famille de features soit désactivée.
    """

    def __init__(self, names: Sequence[str]) -> None:
        self.names = tuple(names)

    def __call__(self, X: pd.DataFrame) -> list[str]:
        return [c for c in self.names if c in X.columns]


class CategoricalColumns:
    """Sélecteur : colonnes de type ``category``."""

    def __call__(self, X: pd.DataFrame) -> list[str]:
        return list(X.select_dtypes("category").columns)


def _is_binary(s: pd.Series) -> bool:
    """Colonne numérique dont les valeurs renseignées sont toutes 0 ou 1."""
    return bool(s.dropna().isin([0, 1]).all())


class BinaryColumns:
    """Sélecteur : indicateurs 0/1 (hors listes ``exclude``), laissés tels quels.

    Un indicateur rare, standardisé, prendrait des valeurs énormes (≈ 180 pour 2 clients
    sur 64 000) qui dégradent la convergence du solveur ; il n'a besoin ni de log, ni
    d'écrêtage, ni de standardisation : un coefficient sur 0/1 se lit directement.
    """

    def __init__(self, exclude: Sequence[str] = ()) -> None:
        self.exclude = tuple(exclude)

    def __call__(self, X: pd.DataFrame) -> list[str]:
        numeric = X.select_dtypes("number").columns
        return [c for c in numeric if c not in self.exclude and _is_binary(X[c])]


class OtherNumeric:
    """Sélecteur : colonnes numériques non binaires qui ne sont dans aucune liste ``exclude``."""

    def __init__(self, exclude: Sequence[str], include_binary: bool = False) -> None:
        self.exclude = tuple(exclude)
        self.include_binary = include_binary

    def __call__(self, X: pd.DataFrame) -> list[str]:
        numeric = X.select_dtypes("number").columns
        return [c for c in numeric if c not in self.exclude
                and (self.include_binary or not _is_binary(X[c]))]


def _numeric_branch(transform=None, winsorize: bool = True, add_indicator: bool = False,
                    keep_degenerate: bool = True, scale_before_impute: bool = True) -> Pipeline:
    """Log éventuel -> écrêtage -> standardisation -> imputation médiane (+ indicateurs).

    La standardisation précède l'imputation (``StandardScaler`` ignore les NaN) : la valeur
    imputée est la même (médiane standardisée), et les indicateurs de manquant ajoutés par
    ``add_indicator`` restent en 0/1 au lieu d'être standardisés.
    ``scale_before_impute=False`` reproduit l'ancien ordre (indicateurs standardisés).
    """
    steps = []
    if transform is not None:
        steps.append(("log", FunctionTransformer(transform, feature_names_out="one-to-one")))
    if winsorize:
        steps.append(("winsorize", Winsorizer(0.01, 0.99, keep_degenerate)))
    scale = ("scale", StandardScaler())
    impute = ("impute", SimpleImputer(strategy="median", add_indicator=add_indicator))
    steps += [scale, impute] if scale_before_impute else [impute, scale]
    return Pipeline(steps)


def make_improved_logreg_pipeline(
    groups: Sequence[str] | None = None,
    drop: Sequence[str] = (),
    C: float = 1.0,
    l1_ratio: float = 0.0,
    log_winsorize: bool = True,
    splines: bool = True,
    n_knots: int = 5,
    add_indicator: bool = True,
    separate_binary: bool = True,
    keep_degenerate: bool = True,
    dedupe_missing: bool = False,
    random_state: int | None = None,
) -> Pipeline:
    """Régression logistique améliorée, tout le prétraitement appris dans le pipeline.

    Args:
        groups: familles de features (``None`` = celles de la config).
        drop: colonnes à retirer (liste de E5).
        C: inverse de la force de régularisation.
        l1_ratio: 0 = pénalité L2 (``lbfgs``), 1 = pénalité L1 (``liblinear``).
        log_winsorize: log sur les variables asymétriques et winsorisation 1 %-99 %.
        splines: B-splines cubiques (``n_knots`` nœuds aux quantiles) sur months et eqpdays ;
            sinon ces variables passent dans la branche numérique standard.
        add_indicator: indicateur de manquant par colonne, en plus de la famille
            ``indicateurs_manquants`` (un par motif). Il couvre aussi les NaN créés par les
            ratios de E6 quand un dénominateur est nul (ex. ``avg6mou`` = 0), une information
            que les indicateurs par motif ne portent pas (+1,4 millième d'AUC en E7).
        separate_binary: indicateurs 0/1 dans une branche à part (ni log, ni écrêtage, ni
            standardisation), et indicateurs de manquant laissés en 0/1. ``False`` reproduit
            le défaut corrigé en E7 (binaires standardisés).
        keep_degenerate: ne pas écrêter une colonne dont les quantiles 1 % et 99 % sont
            égaux. ``False`` reproduit le défaut corrigé en E7 (indicateurs rares effacés).
        dedupe_missing: retirer les ``manquant_*`` de la famille ``indicateurs_manquants``
            dont l'information est déjà portée par ``add_indicator`` (source numérique) ou
            par la modalité « Manquant » du one-hot (source catégorielle) : voir
            :func:`duplicate_missing_indicators`.
    """
    cfg = get_config()
    seed = cfg.random_state if random_state is None else random_state
    groups = cfg.features.groups if groups is None else groups
    if dedupe_missing:
        drop = list(drop) + duplicate_missing_indicators(drop, add_indicator)
    special = (SPLINE_COLUMNS if splines else ()) + \
        ((LOG_COLUMNS + SIGNED_LOG_COLUMNS) if log_winsorize else ())
    opts = {"add_indicator": add_indicator, "keep_degenerate": keep_degenerate,
            "scale_before_impute": separate_binary}
    branches = []
    if log_winsorize:
        branches += [
            ("log", _numeric_branch(log1p_nonneg, True, **opts), ColumnSubset(LOG_COLUMNS)),
            ("signed_log", _numeric_branch(signed_log1p, True, **opts),
             ColumnSubset(SIGNED_LOG_COLUMNS)),
        ]
    branches.append(("num", _numeric_branch(None, log_winsorize, **opts),
                     OtherNumeric(special, include_binary=not separate_binary)))
    if separate_binary:
        branches.append(("binary", SimpleImputer(strategy="most_frequent"),
                         BinaryColumns(special)))
    if splines:
        branches.append(("spline", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("spline", SplineTransformer(n_knots=n_knots, degree=3, knots="quantile",
                                         extrapolation="constant")),
        ]), ColumnSubset(SPLINE_COLUMNS)))
    branches.append(("cat", Pipeline([
        ("text", FunctionTransformer(categories_as_text, feature_names_out="one-to-one")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01,
                                 sparse_output=False)),
    ]), CategoricalColumns()))
    solver = "liblinear" if l1_ratio > 0 else "lbfgs"
    return Pipeline([
        ("features", FeatureBuilder(groups, drop_columns=non_feature_columns())),
        ("drop", ColumnDropper(drop)),
        ("preprocess", ColumnTransformer(branches, verbose_feature_names_out=True)),
        ("model", LogisticRegression(C=C, l1_ratio=l1_ratio, solver=solver, max_iter=3000,
                                     random_state=seed)),
    ])


def duplicate_missing_indicators(drop: Sequence[str], add_indicator: bool = True) -> list[str]:
    """Indicateurs ``manquant_*`` redondants dans la régression logistique.

    Un ``manquant_X`` est un doublon quand la colonne source X reste dans le modèle et que
    son absence y est déjà codée : par ``add_indicator`` si X est numérique non binaire, par
    la modalité « Manquant » si X est catégorielle. Restent utiles : ceux dont la source est
    retirée (liste de E5) et ceux d'une source binaire (imputée sans indicateur).
    """
    dropped = set(drop)
    out = []
    for name, source in MISSING_PATTERNS.items():
        if source in dropped or source in BINARY_COLUMNS:
            continue
        if source in CATEGORICAL_COLUMNS or add_indicator:
            out.append(name)
    return out


def spline_contribution(pipeline: Pipeline, column: str, values: np.ndarray) -> pd.Series:
    """Contribution au log-odds d'une variable passée en splines, centrée sur sa moyenne.

    Les valeurs sont transformées par la branche spline ajustée puis multipliées par les
    coefficients correspondants : c'est la forme de l'effet appris, toutes choses égales
    par ailleurs. ``SplineTransformer`` traite chaque colonne séparément : les autres
    colonnes de la branche reçoivent les mêmes valeurs sans influencer le résultat.
    """
    pre = pipeline.named_steps["preprocess"]
    columns = next(cols for name, _, cols in pre.transformers_ if name == "spline")
    branch = pre.named_transformers_["spline"]
    basis = branch.transform(pd.DataFrame({c: values for c in columns}))
    basis_names = [f"spline__{n}" for n in branch.get_feature_names_out(columns)]
    all_names = list(pre.get_feature_names_out())
    coef = pipeline.named_steps["model"].coef_.ravel()
    keep = [i for i, n in enumerate(basis_names) if n.startswith(f"spline__{column}_")]
    contrib = basis[:, keep] @ coef[[all_names.index(basis_names[i]) for i in keep]]
    return pd.Series(contrib - contrib.mean(), index=values, name=column)
