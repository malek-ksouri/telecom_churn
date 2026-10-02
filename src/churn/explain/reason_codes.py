"""Codes de raisons : les 3 facteurs principaux d'un client, en phrases métier (E11).

Chaque facteur est une variable d'origine (les features dérivées sont regroupées), avec sa
contribution SHAP (log-odds) et son sens : « augmente le risque » ou « réduit le risque ».
Les phrases décrivent la **situation du client** qui, **selon le modèle**, pèse sur son
score ; elles ne disent pas que cette situation cause le départ.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from churn.explain.shap_utils import ShapResult, label

DAYS_PER_MONTH = 30.4
INCREASES, DECREASES = "augmente le risque", "réduit le risque"


def _num(x: float, digits: int = 0) -> str:
    """Nombre au format français (espace fine des milliers, virgule décimale)."""
    return f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")


def _is_missing(x: object) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x)


def _months(row: pd.Series) -> str:
    m = int(row["months"])
    if row.get("in_contract_end", 0) == 1:
        return f"Fin d'engagement : {m} mois d'ancienneté"
    return f"Ancienneté : {m} mois"


def _eqpdays(row: pd.Series) -> str:
    if _is_missing(row["eqpdays"]):
        return "Âge du terminal inconnu"
    months = row["eqpdays"] / DAYS_PER_MONTH
    kind = "Terminal ancien" if row["eqpdays"] >= 300 else "Terminal récent"
    return f"{kind} : {_num(months)} mois"


def _change_mou(row: pd.Series) -> str:
    if _is_missing(row["change_mou"]):
        return "Évolution de l'usage non mesurée"
    v = row["change_mou"]
    direction = "baisse" if v < 0 else "hausse"
    return f"Usage en {direction} de {_num(abs(v))} minutes par mois"


def _recent_usage(row: pd.Series) -> str:
    ratio = row.get("ratio_mou_3m_6m", np.nan)
    if _is_missing(ratio):
        return "Tendance d'usage récente non mesurée"
    pct = 100 * (ratio - 1)
    direction = "baisse" if pct < 0 else "hausse"
    return f"Usage en {direction} de {_num(abs(pct))} % (3 derniers mois contre 6 mois)"


def _money(column: str, text: str) -> Callable[[pd.Series], str]:
    def phrase(row: pd.Series) -> str:
        v = row[column]
        return f"{text} inconnu" if _is_missing(v) else f"{text} : {_num(v)} $ par mois"
    return phrase


def _per_month(column: str, text: str, digits: int = 1) -> Callable[[pd.Series], str]:
    def phrase(row: pd.Series) -> str:
        v = row[column]
        if _is_missing(v):
            return f"{text} : non renseigné"
        return f"{text} : {_num(v, digits)} par mois"
    return phrase


def _change_rev(row: pd.Series) -> str:
    if _is_missing(row["change_rev"]):
        return "Évolution de la facture non mesurée"
    v = row["change_rev"]
    direction = "hausse" if v >= 0 else "baisse"
    return f"Facture en {direction} de {_num(abs(v))} $ par mois (3 derniers mois)"


def _recent_bill(row: pd.Series) -> str:
    ratio = row.get("ratio_rev_3m_6m", np.nan)
    if _is_missing(ratio):
        return "Tendance de facture récente non mesurée"
    pct = 100 * (ratio - 1)
    direction = "baisse" if pct < 0 else "hausse"
    return f"Facture en {direction} de {_num(abs(pct))} % (3 derniers mois contre 6 mois)"


def _refurb(row: pd.Series) -> str:
    v = row.get("refurb_new")
    if _is_missing(v):
        return "État du terminal inconnu"
    return "Terminal reconditionné" if str(v) == "R" else "Terminal acheté neuf"


def _webcap(row: pd.Series) -> str:
    v = row.get("hnd_webcap")
    if _is_missing(v) or str(v) == "Unknown":
        return "Capacité web du terminal inconnue"
    return "Terminal compatible web mobile" if str(v) == "WCMB" else "Terminal à accès web limité"


def _lines(row: pd.Series) -> str:
    n = int(row["uniqsubs"])
    return f"{n} ligne ouverte sur le compte" if n <= 1 else f"{n} lignes ouvertes sur le compte"


def _years(row: pd.Series) -> str:
    if _is_missing(row["lor"]):
        return "Durée de résidence inconnue"
    n = int(row["lor"])
    return f"Durée de résidence : {n} an" if n <= 1 else f"Durée de résidence : {n} ans"


PHRASES: dict[str, Callable[[pd.Series], str]] = {
    "months": _months,
    "eqpdays": _eqpdays,
    "change_mou": _change_mou,
    "avg3mou": _recent_usage,
    "mou_Mean": _per_month("mou_Mean", "Minutes d'appel", 0),
    "totmrc_Mean": _money("totmrc_Mean", "Forfait"),
    "rev_Mean": _money("rev_Mean", "Facture"),
    "ovrrev_Mean": _money("ovrrev_Mean", "Dépassements"),
    "drop_vce_Mean": _per_month("drop_vce_Mean", "Appels coupés"),
    "custcare_Mean": _per_month("custcare_Mean", "Appels au service client"),
    "hnd_price": lambda r: ("Prix du terminal inconnu" if _is_missing(r["hnd_price"])
                            else f"Terminal à {_num(r['hnd_price'])} $"),
    "crclscod": lambda r: f"Classe de crédit {r['crclscod']}",
    "area": lambda r: ("Région inconnue" if _is_missing(r["area"])
                       else f"Région : {str(r['area']).title().replace(' Area', '')}"),
    "lor": _years,
    "phones": lambda r: f"{int(r['phones'])} terminaux utilisés depuis l'ouverture",
    "actvsubs": lambda r: f"{int(r['actvsubs'])} ligne(s) active(s) sur {int(r['uniqsubs'])}",
    # Variables fréquentes parmi les raisons, auparavant rédigées par la forme générique (E15b).
    "change_rev": _change_rev,
    "avg3rev": _recent_bill,
    "avgqty": _per_month("avgqty", "Appels depuis l'ouverture", 0),
    "avg3qty": _per_month("avg3qty", "Appels sur 3 mois", 0),
    "avg6qty": _per_month("avg6qty", "Appels sur 6 mois", 0),
    "avgmou": _per_month("avgmou", "Minutes depuis l'ouverture", 0),
    "avg6mou": _per_month("avg6mou", "Minutes sur 6 mois", 0),
    "avgrev": _money("avgrev", "Facture moyenne depuis l'ouverture"),
    "avg6rev": _money("avg6rev", "Facture moyenne sur 6 mois"),
    "drop_blk_Mean": _per_month("drop_blk_Mean", "Appels coupés ou bloqués"),
    "blck_vce_Mean": _per_month("blck_vce_Mean", "Appels bloqués"),
    "unan_vce_Mean": _per_month("unan_vce_Mean", "Appels sans réponse"),
    "mou_cvce_Mean": _per_month("mou_cvce_Mean", "Minutes d'appels aboutis", 0),
    "iwylis_vce_Mean": _per_month("iwylis_vce_Mean", "Appels entrants vers la messagerie"),
    "mouiwylisv_Mean": _per_month("mouiwylisv_Mean", "Minutes d'appels entrants manqués"),
    "inonemin_Mean": _per_month("inonemin_Mean", "Appels entrants de moins d'une minute"),
    "roam_Mean": _per_month("roam_Mean", "Appels en itinérance"),
    "ovrmou_Mean": _per_month("ovrmou_Mean", "Minutes hors forfait", 0),
    "uniqsubs": _lines,
    "refurb_new": _refurb,
    "hnd_webcap": _webcap,
}


# --- Valeurs atypiques --------------------------------------------------------------------------
# Seuils calculés sur le train (``make artifacts``) :
# - haut : quantile 99,9 % de chaque variable numérique non binaire ;
# - bas : quantile 0,1 %, pour les variables qui peuvent être négatives dans le train (évolutions
#   d'usage et de facture) et pour les ratios « 3 mois contre 6 mois » (baisse).
# Au-delà (au-dessus du seuil haut ou en dessous du seuil bas), la phrase est suivie d'une
# mention : la valeur est rare et mérite d'être vérifiée avant d'en parler au client. Seul le
# texte change : contributions, scores et ordre des raisons sont inchangés.
ATYPICAL_NOTE = " (valeur atypique, à vérifier)"
OUTLIER_QUANTILE = 0.999
LOW_OUTLIER_QUANTILE = 0.001
# Colonne dont la valeur est affichée par la phrase, quand ce n'est pas la variable elle-même.
DISPLAYED_COLUMN: dict[str, str] = {"avg3mou": "ratio_mou_3m_6m", "avg3rev": "ratio_rev_3m_6m"}
_OUTLIER_THRESHOLDS: dict[str, dict[str, float]] = {"high": {}, "low": {}}


def compute_outlier_thresholds(features: pd.DataFrame, quantile: float = OUTLIER_QUANTILE,
                               low_quantile: float = LOW_OUTLIER_QUANTILE
                               ) -> dict[str, dict[str, float]]:
    """Seuils haut (toutes les variables numériques non binaires) et bas (variables pouvant être
    négatives, et ratios de baisse), à calculer sur le train."""
    numeric = features.select_dtypes(include="number")
    keep = [c for c in numeric.columns if numeric[c].nunique(dropna=True) > 2]
    high = {c: float(v) for c, v in numeric[keep].quantile(quantile).items() if np.isfinite(v)}
    low_cols = [c for c in keep if numeric[c].min() < 0 or c in DISPLAYED_COLUMN.values()]
    low = {c: float(v) for c, v in numeric[low_cols].quantile(low_quantile).items()
           if np.isfinite(v)}
    return {"high": high, "low": low}


def set_outlier_thresholds(thresholds: dict[str, dict[str, float]]) -> None:
    """Active les seuils utilisés par ``describe`` (``{"high": {...}, "low": {...}}`` ; vide :
    aucune mention)."""
    for side in ("high", "low"):
        _OUTLIER_THRESHOLDS[side] = dict(thresholds.get(side, {}))


def is_atypical(variable: str, row: pd.Series) -> bool:
    """La valeur affichée dépasse-t-elle le seuil haut, ou passe-t-elle sous le seuil bas ?"""
    column = DISPLAYED_COLUMN.get(variable, variable)
    value = row.get(column, np.nan)
    if _is_missing(value) or not isinstance(value, int | float | np.number):
        return False
    high = _OUTLIER_THRESHOLDS["high"].get(column)
    low = _OUTLIER_THRESHOLDS["low"].get(column)
    return (high is not None and float(value) > high) or (low is not None and float(value) < low)


def _describe(variable: str, row: pd.Series) -> str:
    if variable in PHRASES:
        try:
            return PHRASES[variable](row)
        except (KeyError, TypeError, ValueError):
            pass
    value = row.get(variable, np.nan)
    if _is_missing(value):
        return f"{label(variable)} : non renseigné"
    if isinstance(value, float | np.floating):
        return f"{label(variable)} : {_num(value, 1)}"
    return f"{label(variable)} : {value}"


def describe(variable: str, row: pd.Series) -> str:
    """Phrase métier décrivant la situation du client pour une variable d'origine, suivie de
    « (valeur atypique, à vérifier) » si la valeur sort des quantiles 0,1 % / 99,9 % du train."""
    text = _describe(variable, row)
    return text + ATYPICAL_NOTE if is_atypical(variable, row) else text


@dataclass
class Reason:
    """Un facteur explicatif d'un client."""

    variable: str
    libelle: str
    phrase: str
    effet: str
    contribution: float


def reason_codes(result: ShapResult, client: object, top: int = 3,
                 only: str | None = None) -> list[Reason]:
    """Les ``top`` facteurs d'un client, par contribution SHAP absolue décroissante.

    Args:
        result: valeurs SHAP d'un lot de clients contenant ``client``.
        client: index du client dans ``result``.
        top: nombre de facteurs.
        only: ``"increase"`` pour ne garder que les facteurs qui augmentent le risque,
            ``"decrease"`` pour ceux qui le réduisent, ``None`` pour les deux.
    """
    contrib = result.grouped().loc[client]
    if only == "increase":
        contrib = contrib[contrib > 0]
    elif only == "decrease":
        contrib = contrib[contrib < 0]
    row = result.features.loc[client]
    reasons = []
    for variable in contrib.abs().sort_values(ascending=False).index[:top]:
        value = float(contrib[variable])
        reasons.append(Reason(variable=variable, libelle=label(variable),
                              phrase=describe(variable, row),
                              effet=INCREASES if value > 0 else DECREASES,
                              contribution=value))
    return reasons


def reasons_table(reasons: list[Reason]) -> pd.DataFrame:
    """Tableau lisible des codes de raisons."""
    return pd.DataFrame([{"facteur": r.libelle, "situation du client": r.phrase, "effet": r.effet,
                          "contribution (log-odds)": round(r.contribution, 3)} for r in reasons])
