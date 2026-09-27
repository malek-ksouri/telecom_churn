"""Style graphique commun (matplotlib) et graphiques réutilisables des notebooks.

Charte : un seul bleu d'accent pour les grandeurs, palette divergente bleu / gris / rouge
pour les valeurs signées, encre neutre pour le texte, grille discrète, pas de dégradé
décoratif ni de 3D.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"
ACCENT = "#2a78d6"
NEGATIVE_POLE = "#2a78d6"
NEUTRAL_MID = "#f0efec"
POSITIVE_POLE = "#c8372d"

DIVERGING = LinearSegmentedColormap.from_list(
    "churn_diverging", [NEGATIVE_POLE, NEUTRAL_MID, POSITIVE_POLE]
)


def apply_style() -> None:
    """Applique la charte aux graphiques matplotlib de la session."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK_SECONDARY,
        "ytick.color": INK_SECONDARY,
        "font.size": 9,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def _save(fig: Figure, path: Path | None) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, facecolor=SURFACE)


def plot_missing_rates(summary: pd.DataFrame, title: str, path: Path | None = None) -> Figure:
    """Barres horizontales du taux de manquants, étiquetées directement.

    Args:
        summary: sortie de ``missing_patterns`` (colonnes ``groupe``, ``n_colonnes``, ``pct``).
        title: titre qui énonce la conclusion.
        path: fichier PNG de sortie (optionnel).
    """
    data = summary.sort_values("pct")
    labels = [
        g if n == 1 else f"{g} (+{n - 1} col.)"
        for g, n in zip(data["groupe"], data["n_colonnes"], strict=True)
    ]
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(data) + 1))
    ax.barh(labels, data["pct"], color=ACCENT, height=0.6)
    for y, pct in enumerate(data["pct"]):
        label = f"{pct:.1f} %" if pct >= 1 else f"{pct:.2f} %"
        ax.text(pct + 0.5, y, label, va="center", color=INK_SECONDARY, fontsize=8)
    ax.set_xlabel("% de clients avec valeur manquante")
    ax.set_title(title)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, data["pct"].max() * 1.15)
    _save(fig, path)
    return fig


def plot_nullity_heatmap(corr: pd.DataFrame, title: str, path: Path | None = None) -> Figure:
    """Heatmap de co-occurrence des valeurs manquantes (corrélation entre indicateurs NaN).

    Palette divergente centrée sur 0 (gris) : bleu = absences opposées, rouge = absences
    simultanées. Chaque cellule est annotée, la couleur n'est jamais seule porteuse du sens.
    """
    n = len(corr)
    fig, ax = plt.subplots(figsize=(0.55 * n + 2.5, 0.5 * n + 1.5))
    im = ax.imshow(corr.to_numpy(), cmap=DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(n), corr.columns, rotation=60, ha="right")
    ax.set_yticks(range(n), corr.index)
    ax.grid(False)
    for i in range(n):
        for j in range(n):
            v = corr.iat[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(v) > 0.6 else INK)
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("corrélation des indicateurs « manquant »", color=INK_SECONDARY)
    ax.set_title(title)
    _save(fig, path)
    return fig
