"""Raisons actionnables, contexte et action suggérée pour chaque client (E12).

Chaque variable d'origine (après regroupement SHAP, E11) appartient à une **famille
actionnable** (terminal, fin d'engagement, usage, forfait, qualité réseau, service client,
lignes) ou au **contexte** (classe de crédit, région, durée de résidence, socio-démographie,
et toute variable non répertoriée, D83-D84). L'ancienneté n'est actionnable que dans la
fenêtre de fin d'engagement (11-12 mois, D85).

- **Raisons affichées** : les 3 facteurs actionnables qui augmentent le plus le risque,
  selon le modèle.
- **Action suggérée** : celle de la famille du facteur actionnable dominant (le premier).
- **Contexte** : les 2 facteurs non actionnables les plus influents, dans un sens ou l'autre.

Les phrases décrivent la situation du client ; elles ne disent pas qu'elle cause le départ.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from churn.business.scoring import HIGH, INACTIVE, MEDIUM
from churn.explain.reason_codes import DECREASES, INCREASES, describe
from churn.explain.shap_utils import ShapResult, label

TERMINAL, ENGAGEMENT, USAGE, PLAN = "terminal", "engagement", "usage", "forfait"
NETWORK, CARE, LINES, CONTEXT = "reseau", "service_client", "lignes", "contexte"

FAMILIES: dict[str, list[str]] = {
    TERMINAL: ["eqpdays", "hnd_price", "hnd_webcap", "refurb_new", "dualband", "phones",
               "models"],
    ENGAGEMENT: ["months"],
    USAGE: ["mou_Mean", "change_mou", "avg3mou", "avg6mou", "avgmou", "avgqty", "avg3qty",
            "avg6qty", "adjmou", "adjqty", "totmou", "totcalls", "attempt_Mean",
            "complete_Mean", "comp_vce_Mean", "comp_dat_Mean", "plcd_vce_Mean",
            "plcd_dat_Mean", "mou_cvce_Mean", "mou_cdat_Mean", "mou_rvce_Mean",
            "mou_opkv_Mean", "mou_opkd_Mean", "mou_peav_Mean", "mou_pead_Mean",
            "peak_vce_Mean", "peak_dat_Mean", "opk_vce_Mean", "opk_dat_Mean", "recv_vce_Mean",
            "recv_sms_Mean", "inonemin_Mean", "owylis_vce_Mean", "mouowylisv_Mean",
            "iwylis_vce_Mean", "mouiwylisv_Mean", "unan_vce_Mean", "unan_dat_Mean",
            "threeway_Mean", "callwait_Mean", "callfwdv_Mean", "da_Mean", "roam_Mean"],
    PLAN: ["totmrc_Mean", "rev_Mean", "ovrrev_Mean", "ovrmou_Mean", "vceovr_Mean",
           "datovr_Mean", "avgrev", "avg3rev", "avg6rev", "adjrev", "totrev", "change_rev",
           "asl_flag"],
    NETWORK: ["drop_vce_Mean", "drop_dat_Mean", "blck_vce_Mean", "blck_dat_Mean",
              "drop_blk_Mean"],
    CARE: ["custcare_Mean", "cc_mou_Mean", "ccrndmou_Mean"],
    LINES: ["actvsubs", "uniqsubs"],
}
FAMILY_OF: dict[str, str] = {v: f for f, variables in FAMILIES.items() for v in variables}

FAMILY_LABELS: dict[str, str] = {
    TERMINAL: "Terminal", ENGAGEMENT: "Fin d'engagement", USAGE: "Usage", PLAN: "Forfait",
    NETWORK: "Qualité réseau", CARE: "Service client", LINES: "Lignes", CONTEXT: "Contexte",
}
ACTIONS: dict[str, str] = {
    TERMINAL: "Offre de renouvellement du terminal",
    ENGAGEMENT: "Offre de réengagement",
    USAGE: "Offre adaptée à l'usage",
    PLAN: "Changement de forfait",
    NETWORK: "Geste commercial + ticket technique",
    CARE: "Contact de fidélisation (suivi service client)",
    LINES: "Contact de fidélisation (offre multi-lignes)",
}
DEFAULT_ACTION = "Contact de fidélisation"
INACTIVE_ACTION = "Vérifier la ligne / reconquête"
NO_ACTION = "Pas d'action de campagne (suivi)"


def family(variable: str, in_contract_end: bool = False) -> str:
    """Famille d'une variable d'origine ; ``contexte`` si elle n'est pas actionnable.

    L'ancienneté n'est actionnable que dans la fenêtre de fin d'engagement (D85).
    """
    fam = FAMILY_OF.get(variable, CONTEXT)
    if fam == ENGAGEMENT and not in_contract_end:
        return CONTEXT
    return fam


def suggest_action(tier: str, dominant_family: str | None) -> str:
    """Action suggérée selon le niveau et la famille du facteur actionnable dominant."""
    if tier == INACTIVE:
        return INACTIVE_ACTION
    if tier not in (HIGH, MEDIUM):
        return NO_ACTION
    return ACTIONS.get(dominant_family or "", DEFAULT_ACTION)


def _families_matrix(grouped: pd.DataFrame, in_contract_end: pd.Series) -> np.ndarray:
    """Famille de chaque (client, variable) : tableau de chaînes de même forme que ``grouped``."""
    static = np.array([FAMILY_OF.get(v, CONTEXT) for v in grouped.columns], dtype=object)
    fams = np.tile(static, (len(grouped), 1))
    if "months" in grouped.columns:
        j = grouped.columns.get_loc("months")
        fams[:, j] = np.where(in_contract_end.to_numpy() == 1, ENGAGEMENT, CONTEXT)
    return fams


def _top(values: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Indices des ``k`` plus grandes valeurs par ligne (décroissant) et masque des valeurs > 0."""
    idx = np.argsort(-values, axis=1, kind="stable")[:, :k]
    return idx, np.take_along_axis(values, idx, axis=1) > 0


def explain_clients(result: ShapResult, n_reasons: int = 3, n_context: int = 2,
                    n_factors: int = 8, chunk: int = 5000) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raisons actionnables, contexte et facteurs principaux d'un lot de clients.

    Args:
        result: valeurs SHAP du lot (``ShapExplainer.explain``).
        n_reasons: nombre de raisons actionnables affichées.
        n_context: nombre de facteurs de contexte conservés.
        n_factors: nombre de facteurs (toutes familles) du tableau long.
        chunk: taille des paquets de clients pour la rédaction des phrases.

    Returns:
        ``(par_client, facteurs)`` : une ligne par client (``raison_1..n``, ``contexte_1..n``,
        variable et famille dominantes) ; et un tableau long des ``n_factors`` premiers
        facteurs de chaque client (rang, variable, phrase, contribution, famille).
    """
    grouped = result.grouped()
    variables = np.asarray(grouped.columns)
    G = grouped.to_numpy()
    ice = result.features.get("in_contract_end", pd.Series(0, index=grouped.index))
    fams = _families_matrix(grouped, ice)
    actionable = fams != CONTEXT

    r_idx, r_ok = _top(np.where(actionable & (G > 0), G, 0.0), n_reasons)
    c_idx, c_ok = _top(np.where(~actionable, np.abs(G), 0.0), n_context)
    f_idx, _ = _top(np.abs(G), n_factors)

    needed = [c for c in result.features.columns
              if c in set(variables) | {"in_contract_end", "ratio_mou_3m_6m", "uniqsubs"}]
    wide_rows, long_rows = [], []
    for start in range(0, len(G), chunk):
        rows = result.features.iloc[start:start + chunk][needed].to_dict("records")
        for offset, row in enumerate(rows):
            i = start + offset
            client = grouped.index[i]
            out: dict[str, object] = {"client": client}
            for k in range(n_reasons):
                v = variables[r_idx[i, k]]
                out[f"raison_{k + 1}"] = describe(v, row) if r_ok[i, k] else None
            dominant = r_idx[i, 0] if r_ok[i, 0] else None
            out["facteur_dominant"] = None if dominant is None else label(variables[dominant])
            out["famille_dominante"] = None if dominant is None else fams[i, dominant]
            for k in range(n_context):
                j = c_idx[i, k]
                sens = INCREASES if G[i, j] > 0 else DECREASES
                out[f"contexte_{k + 1}"] = (f"{describe(variables[j], row)} ({sens})"
                                           if c_ok[i, k] else None)
            wide_rows.append(out)
            for rank, j in enumerate(f_idx[i], start=1):
                long_rows.append({
                    "client": client, "rang": rank, "variable": variables[j],
                    "libelle": label(variables[j]), "phrase": describe(variables[j], row),
                    "contribution": float(G[i, j]),
                    "effet": INCREASES if G[i, j] > 0 else DECREASES,
                    "famille": fams[i, j], "actionnable": bool(actionable[i, j])})
    wide = pd.DataFrame(wide_rows).set_index("client")
    wide.index.name = None
    return wide, pd.DataFrame(long_rows)
