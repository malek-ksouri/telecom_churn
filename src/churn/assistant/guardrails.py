"""Garde-fous de l'assistant (E16).

1. **Fidélité des chiffres** : chaque nombre de la réponse doit figurer dans les résultats des
   outils (ou dans leurs arguments, ou dans la question), avec une tolérance d'arrondi :
   écart inférieur à une demi-unité du dernier chiffre écrit, ou à 1 % en relatif
   (« environ 116 000 $ » pour 116 162). Une proportion (0-1) peut être citée en %.
2. **Variables sensibles** : aucune variable socio-démographique sensible ne doit apparaître.

En cas d'écart, un avertissement **visible** est ajouté ; la réponse n'est pas bloquée.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from churn.assistant.tools import SENSITIVE_VARIABLES
from churn.explain.shap_utils import LABELS

# Nombre au format français ou anglais : milliers séparés par une espace (normale, insécable ou
# fine), décimales après une virgule ou un point. Pas de lettre collée (ex. « D79 », « 3G »).
NUMBER_RE = re.compile(r"(?<![\w.,])(\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,](\d+))?(?!\w)")
# Petits entiers de rédaction (« 3 raisons », « top 5 ») et bases de lecture (« pour 1 000 »).
ALWAYS_ALLOWED = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 1000.0}
RELATIVE_TOLERANCE = 0.01

SENSITIVE_TERMS = tuple(sorted({
    *(LABELS[v].lower() for v in SENSITIVE_VARIABLES if v in LABELS),
    "ethni", "origine ethnique", "situation familiale", "revenus du foyer", "tranche de revenu",
    "enfant", "propriétaire ou locataire",
}))


@dataclass(frozen=True)
class Number:
    """Nombre lu dans un texte : valeur et nombre de décimales écrites."""

    text: str
    value: float
    decimals: int


def extract_numbers(text: str) -> list[Number]:
    """Nombres d'un texte (valeurs absolues ; le signe ne change pas la vérification)."""
    out = []
    for m in NUMBER_RE.finditer(text):
        integer = re.sub(r"[   ]", "", m.group(1))
        decimals = m.group(2) or ""
        value = float(f"{integer}.{decimals}" if decimals else integer)
        out.append(Number(m.group(0), value, len(decimals)))
    return out


def collect_numbers(obj: Any) -> set[float]:
    """Toutes les valeurs numériques d'un résultat d'outil (y compris dans les textes)."""
    found: set[float] = set()
    if isinstance(obj, bool) or obj is None:
        return found
    if isinstance(obj, int | float):
        v = abs(float(obj))
        found.add(v)
        if v <= 1:
            found.add(100 * v)       # proportion citée en pourcentage
        return found
    if isinstance(obj, str):
        return {n.value for n in extract_numbers(obj)}
    if isinstance(obj, dict):
        for v in obj.values():
            found |= collect_numbers(v)
    elif isinstance(obj, list | tuple):
        for v in obj:
            found |= collect_numbers(v)
    return found


def is_supported(number: Number, allowed: set[float]) -> bool:
    """Le nombre écrit correspond-il à une valeur connue, à l'arrondi près ?"""
    if number.value in ALWAYS_ALLOWED:
        return True
    half_unit = 0.5 * 10 ** (-number.decimals) + 1e-9
    return any(abs(number.value - v) <= max(half_unit, RELATIVE_TOLERANCE * v) for v in allowed)


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


@dataclass
class GuardrailReport:
    """Résultat des contrôles d'une réponse."""

    unsupported_numbers: list[str] = field(default_factory=list)
    sensitive_terms: list[str] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        out = []
        if self.unsupported_numbers:
            out.append("Vérification automatique : ces nombres ne figurent pas dans les résultats "
                       "des outils et peuvent être inexacts : "
                       + ", ".join(self.unsupported_numbers) + ".")
        if self.sensitive_terms:
            out.append("Vérification automatique : la réponse mentionne une caractéristique "
                       "socio-démographique sensible (" + ", ".join(self.sensitive_terms)
                       + "), qui ne doit pas être utilisée.")
        return out

    @property
    def ok(self) -> bool:
        return not self.unsupported_numbers and not self.sensitive_terms


def check_answer(answer: str, tool_results: list[Any], question: str = "") -> GuardrailReport:
    """Contrôle une réponse contre les résultats (et arguments) des outils et la question."""
    allowed = collect_numbers(tool_results) | {n.value for n in extract_numbers(question)}
    unsupported = []
    for number in extract_numbers(answer):
        if not is_supported(number, allowed) and number.text not in unsupported:
            unsupported.append(number.text)
    text = _norm(answer)
    sensitive = [t for t in SENSITIVE_TERMS if _norm(t) in text]
    return GuardrailReport(unsupported_numbers=unsupported, sensitive_terms=sensitive)
