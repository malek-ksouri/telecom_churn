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
    "lor": lambda r: ("Durée de résidence inconnue" if _is_missing(r["lor"])
                      else f"Durée de résidence : {int(r['lor'])} ans"),
    "phones": lambda r: f"{int(r['phones'])} terminaux utilisés depuis l'ouverture",
    "actvsubs": lambda r: f"{int(r['actvsubs'])} ligne(s) active(s) sur {int(r['uniqsubs'])}",
}


def describe(variable: str, row: pd.Series) -> str:
    """Phrase métier décrivant la situation du client pour une variable d'origine."""
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
