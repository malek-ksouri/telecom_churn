"""Graphiques Plotly sobres pour l'EDA, construits à partir de données agrégées.

Charte : bleu d'accent unique pour les grandeurs ; bleu (non-churners) et orange
(churners) pour comparer les deux classes ; palette divergente bleu / gris / rouge centrée
sur le taux moyen pour les taux de churn ; texte en encre neutre ; ligne de référence au
taux moyen ; aucune couleur n'est seule porteuse du sens (étiquettes et survol).

Les figures reçoivent des statistiques déjà calculées (quartiles, histogrammes, taux),
jamais les 80 000 lignes : le notebook reste léger.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from churn.config import get_config

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"
ACCENT = "#2a78d6"
NO_CHURN = "#2a78d6"
CHURN = "#eb6834"
DIVERGING = [[0.0, "#2a78d6"], [0.5, "#f0efec"], [1.0, "#e34948"]]
CLASS_LABELS = {0: "Non-churners", 1: "Churners"}
AXIS_STYLE = {"gridcolor": GRID, "zeroline": False, "linecolor": GRID, "ticks": "",
              "automargin": True}

pio.templates["churn"] = go.layout.Template(layout=go.Layout(
    font={"family": "Inter, Segoe UI, Arial, sans-serif", "size": 12, "color": INK_SECONDARY},
    title={"font": {"size": 15, "color": INK}, "x": 0.0, "xanchor": "left"},
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    colorway=[ACCENT, CHURN],
    xaxis=AXIS_STYLE,
    yaxis=AXIS_STYLE,
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.0, "xanchor": "right", "x": 1},
    margin={"l": 60, "r": 30, "t": 100, "b": 50},
    hoverlabel={"bgcolor": "white", "font": {"color": INK}},
))
pio.templates.default = "churn"


def save_figure(fig: go.Figure, name: str, width: int = 1000, height: int | None = None) -> Path:
    """Enregistre la figure en PNG dans ``reports/figures/`` et renvoie le chemin."""
    path = get_config().paths.figures_dir / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(path, width=width, height=height or fig.layout.height or 500, scale=2)
    return path


def publish(fig: go.Figure, name: str, width: int = 1000) -> go.Figure:
    """Enregistre la figure en PNG puis la renvoie pour affichage dans le notebook."""
    save_figure(fig, name, width=width)
    return fig


def _grid(n: int, cols: int) -> tuple[int, int]:
    return int(np.ceil(n / cols)), min(n, cols)


def _vspace(n_rows: int) -> float:
    """Espacement vertical entre sous-graphiques : ~8 % de la hauteur au total."""
    return 0.08 if n_rows <= 1 else min(0.16, 0.35 / (n_rows - 1))


def target_bar(counts: pd.Series, title: str) -> go.Figure:
    """Répartition de la cible : barres étiquetées (effectif et part)."""
    share = 100 * counts / counts.sum()
    fig = go.Figure(go.Bar(
        x=[CLASS_LABELS[i] for i in counts.index], y=counts.to_numpy(),
        marker_color=[NO_CHURN, CHURN], width=0.5,
        text=[f"{n:,} ({p:.1f} %)".replace(",", " ") for n, p in zip(counts, share, strict=True)],
        textposition="outside",
        hovertemplate="%{x} : %{y:,} clients<extra></extra>",
    ))
    fig.update_layout(title=title, height=420, showlegend=False,
                      yaxis_title="clients", yaxis_range=[0, counts.max() * 1.18])
    return fig


def histograms_grid(df: pd.DataFrame, columns: list[str], title: str,
                    skew_log: float = 2.0, bins: int = 40, cols: int = 2) -> go.Figure:
    """Histogrammes (pré-calculés) ; axe x logarithmique si la variable est très asymétrique.

    En échelle log, les zéros ne peuvent pas être placés : leur part est indiquée dans le
    sous-titre de chaque panneau.
    """
    subtitles, specs = [], []
    for col in columns:
        s = df[col].dropna()
        use_log = abs(s.skew()) > skew_log and (s > 0).any() and s.min() >= 0
        zero_share = 100 * (s == 0).mean()
        note = f" (log ; {zero_share:.0f} % de zéros)" if use_log else ""
        subtitles.append(f"{col}{note}")
        specs.append((col, s, use_log))
    n_rows, n_cols = _grid(len(columns), cols)
    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=subtitles,
                        horizontal_spacing=0.08, vertical_spacing=_vspace(n_rows))
    for i, (col, s, use_log) in enumerate(specs):
        row, c = divmod(i, n_cols)
        values = s[s > 0] if use_log else s
        edges = (np.logspace(np.log10(values.min()), np.log10(values.max()), bins + 1)
                 if use_log else np.histogram_bin_edges(values, bins=bins))
        counts, edges = np.histogram(values, bins=edges)
        centers = np.sqrt(edges[:-1] * edges[1:]) if use_log else (edges[:-1] + edges[1:]) / 2
        fig.add_trace(go.Bar(x=centers, y=counts, width=np.diff(edges), marker_color=ACCENT,
                             marker_line_width=0, name=col, showlegend=False,
                             hovertemplate=f"{col} ≈ %{{x:,.3g}}<br>%{{y:,}} clients"
                                           "<extra></extra>"),
                      row=row + 1, col=c + 1)
        if use_log:
            fig.update_xaxes(type="log", row=row + 1, col=c + 1)
    fig.update_annotations(font_size=11, font_color=INK_SECONDARY)
    fig.update_layout(title=title, height=260 * n_rows + 90, bargap=0.05)
    return fig


def _box_stats(s: pd.Series) -> dict[str, float]:
    s = s.dropna()
    q1, med, q3 = s.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    return {"q1": q1, "median": med, "q3": q3,
            "lowerfence": s[s >= q1 - 1.5 * iqr].min(), "upperfence": s[s <= q3 + 1.5 * iqr].max()}


def boxplots_grid(df: pd.DataFrame, columns: list[str], title: str,
                  by: str | None = None, cols: int = 4) -> go.Figure:
    """Boxplots (quartiles pré-calculés, moustaches de Tukey, points extrêmes non tracés).

    Si ``by`` est fourni (la cible), deux boîtes par variable : non-churners / churners.
    """
    n_rows, n_cols = _grid(len(columns), cols)
    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=columns,
                        horizontal_spacing=0.07, vertical_spacing=_vspace(n_rows))
    groups = [(None, df)] if by is None else [(k, df[df[by] == k]) for k in (0, 1)]
    for i, col in enumerate(columns):
        row, c = divmod(i, n_cols)
        for key, part in groups:
            st = _box_stats(part[col])
            label = col if key is None else CLASS_LABELS[key]
            color = ACCENT if key is None else (NO_CHURN if key == 0 else CHURN)
            fig.add_trace(go.Box(
                x=[label], q1=[st["q1"]], median=[st["median"]], q3=[st["q3"]],
                lowerfence=[st["lowerfence"]], upperfence=[st["upperfence"]],
                name=label, marker_color=color, line_width=1.5, fillcolor=color, opacity=0.8,
                legendgroup=label, showlegend=(i == 0 and key is not None),
            ), row=row + 1, col=c + 1)
        fig.update_xaxes(showticklabels=by is None, row=row + 1, col=c + 1)
    fig.update_annotations(font_size=11, font_color=INK_SECONDARY)
    fig.update_layout(title=title, height=250 * n_rows + 130, boxgap=0.35,
                      legend={"y": 1.0, "yanchor": "bottom", "yref": "container"},
                      margin={"t": 120})
    return fig


def category_bars(freqs: dict[str, pd.DataFrame], title: str, cols: int = 3,
                  max_levels: int = 12) -> go.Figure:
    """Fréquences des catégorielles (une barre horizontale par modalité, part en %)."""
    names = list(freqs)
    n_rows, n_cols = _grid(len(names), cols)
    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=names,
                        horizontal_spacing=0.16, vertical_spacing=_vspace(n_rows))
    for i, name in enumerate(names):
        row, c = divmod(i, n_cols)
        f = freqs[name].head(max_levels).iloc[::-1]
        fig.add_trace(go.Bar(
            y=[str(v) for v in f.index], x=f["pct"], orientation="h", marker_color=ACCENT,
            text=[f"{p:.1f} %" for p in f["pct"]], textposition="outside", cliponaxis=False,
            showlegend=False, hovertemplate="%{y} : %{x:.1f} %<extra></extra>",
        ), row=row + 1, col=c + 1)
        fig.update_xaxes(range=[0, 118], showticklabels=False, row=row + 1, col=c + 1)
    fig.update_annotations(font_size=11, font_color=INK_SECONDARY)
    fig.update_layout(title=title, height=max(230 * n_rows, 400) + 90)
    return fig


def rate_chart(table: pd.DataFrame, title: str, overall: float, x_title: str = "",
               horizontal: bool = False, min_n: int = 30, connect: bool = True) -> go.Figure:
    """Taux de churn par groupe avec IC 95 % (barres d'erreur) et ligne du taux moyen.

    Args:
        table: sortie de ``churn_rate_table`` (colonnes n, taux, ic_bas, ic_haut).
        title: titre qui énonce la conclusion.
        overall: taux de churn moyen du train (%), tracé en référence.
        x_title: libellé de l'axe des groupes.
        horizontal: groupes en ordonnée (catégories nombreuses, triées par taux).
        min_n: groupes plus petits masqués (IC trop larges pour être lisibles).
        connect: relier les points (groupes ordonnés : déciles, classes d'âge).
    """
    t = table[table["n"] >= min_n]
    labels = [str(v) for v in t.index]
    err = {"type": "data", "symmetric": False, "array": t["ic_haut"] - t["taux"],
           "arrayminus": t["taux"] - t["ic_bas"], "color": INK_SECONDARY, "thickness": 1.2,
           "width": 3}
    custom = np.stack([t["n"], t["ic_bas"], t["ic_haut"]], axis=1)
    hover = ("%{customdata[0]:,} clients<br>churn %{" + ("x" if horizontal else "y")
             + ":.1f} % [IC %{customdata[1]:.1f} ; %{customdata[2]:.1f}]<extra></extra>")
    mode = "markers+lines" if connect and not horizontal else "markers"
    trace = go.Scatter(
        x=t["taux"] if horizontal else labels, y=labels if horizontal else t["taux"],
        mode=mode, marker={"size": 8, "color": ACCENT}, line={"width": 2, "color": ACCENT},
        customdata=custom, hovertemplate=hover, showlegend=False,
        **({"error_x": err} if horizontal else {"error_y": err}),
    )
    fig = go.Figure(trace)
    ref = {"line_dash": "dash", "line_color": INK_SECONDARY, "line_width": 1,
           "annotation_text": f"moyenne {overall:.1f} %", "annotation_font_color": INK_SECONDARY}
    if horizontal:
        fig.add_vline(x=overall, annotation_position="top", **ref)
        fig.update_layout(xaxis_title="taux de churn (%)", yaxis_autorange="reversed",
                          height=max(380, 28 * len(t) + 140))
        fig.update_yaxes(type="category")
    else:
        fig.add_hline(y=overall, annotation_position="top left", **ref)
        fig.update_layout(yaxis_title="taux de churn (%)", xaxis_title=x_title, height=440)
        fig.update_xaxes(type="category")
    fig.update_layout(title=title)
    return fig


def rate_heatmap(rate: pd.DataFrame, n: pd.DataFrame, title: str, overall: float,
                 x_title: str, y_title: str, min_n: int = 100) -> go.Figure:
    """Heatmap du taux de churn, couleur divergente centrée sur le taux moyen.

    Chaque cellule affiche le taux et l'effectif ; les cellules de moins de ``min_n``
    clients sont masquées.
    """
    r = rate.where(n.reindex_like(rate) >= min_n)
    text = [[("" if np.isnan(v) else f"{v:.0f} %<br>n={int(k):,}".replace(",", " "))
             for v, k in zip(rv, kv, strict=True)]
            for rv, kv in zip(r.to_numpy(), n.reindex_like(rate).fillna(0).to_numpy(),
                              strict=True)]
    span = np.nanmax(np.abs(r.to_numpy() - overall))
    fig = go.Figure(go.Heatmap(
        z=r.to_numpy(), x=[str(c) for c in r.columns], y=[str(i) for i in r.index],
        text=text, texttemplate="%{text}", textfont={"size": 11, "color": INK},
        colorscale=DIVERGING, zmin=overall - span, zmax=overall + span, xgap=2, ygap=2,
        colorbar={"title": {"text": "churn (%)"}, "thickness": 12},
        hovertemplate=f"{y_title} %{{y}}<br>{x_title} %{{x}}<br>churn %{{z:.1f}} %<extra></extra>",
    ))
    fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title,
                      yaxis_autorange="reversed", height=90 * len(r) + 180)
    fig.update_xaxes(showgrid=False, type="category")
    fig.update_yaxes(showgrid=False, type="category")
    return fig


def correlation_heatmap(corr: pd.DataFrame, title: str) -> go.Figure:
    """Matrice de corrélation (Spearman), palette divergente centrée sur 0, valeurs affichées."""
    fig = go.Figure(go.Heatmap(
        z=corr.to_numpy(), x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1,
        colorscale=DIVERGING, xgap=1, ygap=1, text=corr.to_numpy(), texttemplate="%{text:.2f}",
        textfont={"size": 9, "color": INK}, colorbar={"title": {"text": "rho"}, "thickness": 12},
        hovertemplate="%{y} × %{x}<br>rho = %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(title=title, height=32 * len(corr) + 220, yaxis_autorange="reversed")
    fig.update_xaxes(showgrid=False, tickangle=-45, type="category")
    fig.update_yaxes(showgrid=False, type="category")
    return fig


def k_selection_chart(metrics: pd.DataFrame, chosen_k: int, title: str) -> go.Figure:
    """Critères de choix de k en petits multiples (une courbe par critère, k retenu marqué)."""
    panels = [
        ("inertie", "Inertie (coude)"),
        ("silhouette", "Silhouette (plus haut = mieux)"),
        ("davies_bouldin", "Davies-Bouldin (plus bas = mieux)"),
        ("ari_min", "Stabilité : ARI minimal entre 5 graines"),
    ]
    fig = make_subplots(rows=2, cols=2, subplot_titles=[p[1] for p in panels],
                        horizontal_spacing=0.1, vertical_spacing=0.18)
    for i, (col, _) in enumerate(panels):
        row, c = divmod(i, 2)
        fig.add_trace(go.Scatter(
            x=metrics.index, y=metrics[col], mode="lines+markers", showlegend=False,
            line={"color": ACCENT, "width": 2}, marker={"size": 8, "color": ACCENT},
            hovertemplate="k = %{x}<br>" + col + " = %{y:.3f}<extra></extra>",
        ), row=row + 1, col=c + 1)
        fig.add_vline(x=chosen_k, line_dash="dash", line_color=INK_SECONDARY, line_width=1,
                      row=row + 1, col=c + 1)
        fig.update_xaxes(dtick=1, title_text="k", row=row + 1, col=c + 1)
    fig.update_annotations(font_size=11, font_color=INK_SECONDARY)
    fig.update_layout(title=title, height=620)
    return fig


def diverging_heatmap(values: pd.DataFrame, title: str, colorbar_title: str,
                      limit: float | None = None, fmt: str = ".2f") -> go.Figure:
    """Heatmap signée centrée sur 0 (ex. z-scores moyens par cluster), valeurs affichées."""
    lim = limit or float(np.nanmax(np.abs(values.to_numpy())))
    fig = go.Figure(go.Heatmap(
        z=values.to_numpy(), x=[str(c) for c in values.columns], y=[str(i) for i in values.index],
        zmin=-lim, zmax=lim, colorscale=DIVERGING, xgap=2, ygap=2,
        text=values.to_numpy(), texttemplate="%{text:" + fmt + "}",
        textfont={"size": 11, "color": INK},
        colorbar={"title": {"text": colorbar_title}, "thickness": 12},
        hovertemplate="%{y}<br>%{x} : %{z:" + fmt + "}<extra></extra>",
    ))
    fig.update_layout(title=title, height=70 * len(values) + 220, yaxis_autorange="reversed")
    fig.update_xaxes(showgrid=False, type="category", tickangle=-30)
    fig.update_yaxes(showgrid=False, type="category")
    return fig


def pca_facets(coords: pd.DataFrame, labels: pd.Series, title: str,
               explained: tuple[float, float], cols: int = 3) -> go.Figure:
    """Projection PCA 2D en petits multiples : un panneau par cluster (bleu) sur fond gris.

    Un nuage unique à 5 couleurs dépasserait la limite de lisibilité des palettes
    catégorielles en nuage de points ; un panneau par cluster reste lisible sans couleur.
    """
    groups = list(pd.unique(labels))
    n_rows, n_cols = _grid(len(groups), cols)
    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=[str(g) for g in groups],
                        horizontal_spacing=0.05, vertical_spacing=_vspace(n_rows) + 0.04,
                        shared_xaxes=True, shared_yaxes=True)
    x_title = f"PC1 ({100 * explained[0]:.0f} % de variance)"
    y_title = f"PC2 ({100 * explained[1]:.0f} % de variance)"
    for i, g in enumerate(groups):
        row, c = divmod(i, n_cols)
        mask = (labels == g).to_numpy()
        fig.add_trace(go.Scattergl(x=coords.iloc[~mask, 0], y=coords.iloc[~mask, 1],
                                   mode="markers", marker={"size": 3, "color": GRID},
                                   hoverinfo="skip", showlegend=False),
                      row=row + 1, col=c + 1)
        fig.add_trace(go.Scattergl(x=coords.iloc[mask, 0], y=coords.iloc[mask, 1],
                                   mode="markers", marker={"size": 3, "color": ACCENT,
                                                           "opacity": 0.6},
                                   name=str(g), showlegend=False,
                                   hovertemplate=f"{g}<extra></extra>"),
                      row=row + 1, col=c + 1)
    fig.update_xaxes(title_text=x_title, row=n_rows)
    fig.update_yaxes(title_text=y_title, col=1)
    fig.update_annotations(font_size=11, font_color=INK_SECONDARY)
    fig.update_layout(title=title, height=330 * n_rows + 120)
    return fig


def importance_chart(table: pd.DataFrame, title: str, top: int = 25) -> go.Figure:
    """Variables classées par information mutuelle, étiquetées par effet et écart entre classes.

    Args:
        table: sortie de ``stats.univariate_table`` (triée par information mutuelle).
    """
    t = table.head(top).iloc[::-1]
    text = [f"effet {e:+.3f} · écart {s:.0f} pts" if m == "rank-biserial"
            else f"V {e:.3f} · écart {s:.0f} pts"
            for e, s, m in zip(t["effet"], t["ecart_classes_pts"], t["mesure_effet"],
                               strict=True)]
    fig = go.Figure(go.Bar(
        x=1000 * t["info_mutuelle"], y=list(t.index), orientation="h", marker_color=ACCENT,
        text=text, textposition="outside", cliponaxis=False, textfont={"size": 10},
        hovertemplate="%{y}<br>information mutuelle %{x:.2f} millinats<extra></extra>",
    ))
    fig.update_layout(title=title, xaxis_title="information mutuelle avec le churn (millinats)",
                      height=26 * len(t) + 160,
                      xaxis_range=[0, 1000 * t["info_mutuelle"].max() * 1.6])
    fig.update_yaxes(type="category")
    return fig


def effect_vs_spread_chart(table: pd.DataFrame, title: str, label_top: int = 8,
                           effect_threshold: float = 0.1, spread_threshold: float = 10.0
                           ) -> go.Figure:
    """Effet monotone |rank-biserial| contre écart entre déciles, pour les numériques.

    La zone en haut à gauche (effet négligeable, écart > 10 pts) contient les variables
    qu'une corrélation seule classerait à tort comme sans intérêt. Les points à courbe non
    monotone sont pleins, les autres évidés : la forme n'est jamais portée par la couleur seule.
    """
    t = table[table["type"] == "numérique"]
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, x1=effect_threshold, y0=spread_threshold,
                  y1=t["ecart_classes_pts"].max() * 1.08, fillcolor=GRID, opacity=0.5,
                  line_width=0, layer="below")
    for shape, symbol in [("monotone", "circle-open"), ("non monotone", "circle")]:
        part = t[t["forme_courbe"] == shape]
        fig.add_trace(go.Scatter(
            x=part["effet_abs"], y=part["ecart_classes_pts"], mode="markers",
            marker={"size": 9, "color": ACCENT, "symbol": symbol, "line": {"width": 1.5}},
            name=f"courbe {shape}", text=list(part.index),
            hovertemplate="%{text}<br>|r| = %{x:.3f}<br>écart %{y:.1f} pts<extra></extra>",
        ))
    top = t.nlargest(label_top, "ecart_classes_pts")
    for var, row in top.iterrows():
        fig.add_annotation(x=row["effet_abs"], y=row["ecart_classes_pts"], text=var,
                           showarrow=False, xanchor="left", xshift=8,
                           font={"size": 10, "color": INK_SECONDARY})
    fig.add_vline(x=effect_threshold, line_dash="dash", line_color=INK_SECONDARY, line_width=1)
    fig.add_hline(y=spread_threshold, line_dash="dash", line_color=INK_SECONDARY, line_width=1)
    fig.update_layout(title=title, height=520,
                      xaxis_title="effet monotone |rank-biserial|",
                      yaxis_title="écart de churn entre déciles (points)")
    return fig


def dendrogram_chart(corr: pd.DataFrame, title: str, threshold: float = 0.9) -> go.Figure:
    """Dendrogramme des variables (distance 1 - |ρ|, lien moyen), seuil de redondance tracé."""
    import plotly.figure_factory as ff
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform

    dist = (1 - corr.abs()).clip(lower=0).to_numpy()
    fig = ff.create_dendrogram(
        dist, orientation="left", labels=list(corr.columns),
        distfun=lambda d: squareform(d, checks=False),
        linkagefun=lambda d: linkage(d, method="average"),
        colorscale=[ACCENT] * 8, color_threshold=0,
    )
    fig.add_vline(x=1 - threshold, line_dash="dash", line_color=CHURN, line_width=1.5,
                  annotation_text=f"|ρ| = {threshold}", annotation_position="top",
                  annotation_font_color=INK_SECONDARY)
    fig.update_layout(title=title, template="churn", height=18 * len(corr) + 160,
                      xaxis_title="distance 1 - |ρ| (lien moyen)", showlegend=False)
    fig.update_yaxes(showgrid=False, tickfont={"size": 10})
    return fig


def ablation_chart(summary: pd.DataFrame, reference: str, title: str,
                   order: list[str] | None = None) -> go.Figure:
    """Gain d'AUC par configuration et par modèle, barres d'erreur = écart-type du gain par fold.

    Deux modèles : deux premières couleurs catégorielles, légende et étiquettes directes
    (au-dessus du point pour le premier modèle, au-dessous pour le second).
    """
    colors = [NO_CHURN, CHURN]
    positions = ["top center", "bottom center"]
    t = summary[summary["configuration"] != reference]
    order = [c for c in (order or list(dict.fromkeys(t["configuration"]))) if c != reference]
    fig = go.Figure()
    for i, (model, part) in enumerate(t.groupby("modele", sort=False)):
        part = part.set_index("configuration").loc[order]
        fig.add_trace(go.Scatter(
            x=1000 * part["gain_moyen"], y=order, mode="markers+text", name=model,
            marker={"size": 10, "color": colors[i % 2]},
            error_x={"type": "data", "array": 1000 * part["gain_ecart_type"],
                     "color": colors[i % 2], "thickness": 1.5, "width": 4},
            text=[f"{1000 * g:+.1f}" for g in part["gain_moyen"]],
            textposition=positions[i % 2],
            textfont={"size": 10, "color": INK_SECONDARY},
            hovertemplate="%{y}<br>gain %{x:+.1f} millièmes d'AUC<extra>" + model + "</extra>",
        ))
    fig.add_vline(x=0, line_color=INK_SECONDARY, line_width=1)
    fig.update_layout(title=title, height=58 * len(order) + 200,
                      xaxis_title="gain d'AUC par rapport à la référence (millièmes)")
    fig.update_yaxes(type="category", autorange="reversed")
    return fig


def coefficient_chart(coefs: pd.Series, title: str) -> go.Figure:
    """Coefficients signés (variables standardisées) : rouge = augmente le churn, bleu = le réduit.

    Le signe est aussi écrit sur chaque barre : la couleur n'est jamais seule porteuse du sens.
    """
    c = coefs.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=c.to_numpy(), y=list(c.index), orientation="h",
        marker_color=[DIVERGING[-1][1] if v > 0 else DIVERGING[0][1] for v in c],
        text=[f"{v:+.3f}" for v in c], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>coefficient %{x:+.3f}<extra></extra>",
    ))
    lim = float(np.abs(c).max()) * 1.3
    fig.add_vline(x=0, line_color=INK_SECONDARY, line_width=1)
    fig.update_layout(title=title, height=28 * len(c) + 170, xaxis_range=[-lim, lim],
                      xaxis_title="coefficient en log-odds (continues : par écart-type ; "
                                  "indicateurs : de 0 à 1) ; > 0 : plus de churn")
    fig.update_yaxes(type="category")
    return fig


def spline_effect_chart(effects: dict[str, pd.Series], title: str,
                        x_titles: dict[str, str] | None = None) -> go.Figure:
    """Effet appris par les splines (contribution au log-odds) : un panneau par variable."""
    names = list(effects)
    fig = make_subplots(rows=1, cols=len(names), subplot_titles=names, horizontal_spacing=0.1)
    for i, name in enumerate(names):
        s = effects[name]
        hover = f"{name} = %{{x}}<br>effet %{{y:+.2f}}<extra></extra>"
        fig.add_trace(go.Scatter(x=s.index, y=s.to_numpy(), mode="lines", showlegend=False,
                                 line={"color": ACCENT, "width": 2}, hovertemplate=hover),
                      row=1, col=i + 1)
        fig.add_hline(y=0, line_color=INK_SECONDARY, line_width=1, row=1, col=i + 1)
        fig.update_xaxes(title_text=(x_titles or {}).get(name, name), row=1, col=i + 1)
    fig.update_yaxes(title_text="contribution au log-odds (centrée)", col=1)
    fig.update_annotations(font_size=11, font_color=INK_SECONDARY)
    fig.update_layout(title=title, height=440)
    return fig


def model_comparison_chart(table: pd.DataFrame, title: str, reference: str | None = None,
                           value: str = "auc", error: str = "auc_std") -> go.Figure:
    """AUC moyenne ± écart-type par modèle (points triés), avec le modèle de référence tracé."""
    t = table.sort_values(value)
    fig = go.Figure(go.Scatter(
        x=t[value], y=list(t.index), mode="markers+text", marker={"size": 10, "color": ACCENT},
        error_x={"type": "data", "array": t[error], "color": INK_SECONDARY, "thickness": 1.5,
                 "width": 4},
        text=[f"{v:.3f}" for v in t[value]], textposition="top center",
        textfont={"size": 10, "color": INK_SECONDARY},
        hovertemplate="%{y}<br>AUC %{x:.4f}<extra></extra>",
    ))
    if reference is not None:
        fig.add_vline(x=float(table.loc[reference, value]), line_dash="dash",
                      line_color=INK_SECONDARY, line_width=1,
                      annotation_text=reference, annotation_position="top",
                      annotation_font_color=INK_SECONDARY)
    fig.update_layout(title=title, xaxis_title="ROC-AUC en validation (5 folds, ± écart-type)",
                      height=52 * len(t) + 180)
    fig.update_yaxes(type="category")
    return fig


def tuning_history_chart(trials: pd.DataFrame, title: str) -> go.Figure:
    """AUC de chaque essai Optuna, meilleure AUC cumulée (ligne) ; essais élagués évidés."""
    fig = go.Figure()
    done = trials[trials["state"] == "COMPLETE"]
    pruned = trials[trials["state"] == "PRUNED"]
    fig.add_trace(go.Scatter(x=pruned["number"], y=pruned["auc_cv"], mode="markers",
                             name="essai élagué (AUC partielle)",
                             marker={"size": 7, "color": INK_SECONDARY, "symbol": "circle-open"}))
    fig.add_trace(go.Scatter(x=done["number"], y=done["auc_cv"], mode="markers",
                             name="essai complet", marker={"size": 8, "color": ACCENT}))
    best = done.set_index("number")["auc_cv"].cummax()
    fig.add_trace(go.Scatter(x=best.index, y=best.to_numpy(), mode="lines", name="meilleure AUC",
                             line={"color": ACCENT, "width": 2, "shape": "hv"}))
    fig.update_layout(title=title, xaxis_title="numéro d'essai", yaxis_title="AUC moyenne (CV)",
                      height=460)
    return fig


def cumulative_gain_chart(curves: dict[str, pd.DataFrame], title: str,
                          value: str = "gain", y_title: str = "part des churners captés (%)"
                          ) -> go.Figure:
    """Courbes de gain cumulé (ou de lift) : une ligne par modèle, hasard en pointillés."""
    colors = [NO_CHURN, CHURN, "#1baf7a"]
    fig = go.Figure()
    for i, (name, c) in enumerate(curves.items()):
        fig.add_trace(go.Scatter(x=c["part_ciblee"], y=c[value], mode="lines", name=name,
                                 line={"color": colors[i % 3], "width": 2},
                                 hovertemplate=f"{name}<br>%{{x:.0f}} % ciblés : %{{y:.2f}}"
                                               "<extra></extra>"))
    ref = [0, 100] if value == "gain" else [1, 1]
    fig.add_trace(go.Scatter(x=[0, 100], y=ref, mode="lines", name="hasard",
                             line={"color": INK_SECONDARY, "width": 1, "dash": "dash"}))
    fig.update_layout(title=title, xaxis_title="part des clients ciblés, du plus risqué (%)",
                      yaxis_title=y_title, height=460)
    return fig
