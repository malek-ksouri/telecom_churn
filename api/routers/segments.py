"""Analyse par segment (drill-down) et croisements."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_filters
from api.schemas import Dimension, Heatmap, SegmentProfiles, Segments
from churn.services import Filters, get_heatmap, get_segment_profiles, get_segments

router = APIRouter(tags=["segments"])


# Déclarée avant /segments/{dimension} : sinon « heatmap » serait lu comme une dimension.
@router.get("/segments/heatmap", response_model=Heatmap, summary="Taux de churn croisé")
def heatmap(filters: Annotated[Filters, Depends(get_filters)],
            x: Annotated[Dimension, Query(description="Dimension en colonnes.")] = "tenure_band",
            y: Annotated[Dimension, Query(description="Dimension en lignes.")] = "handset_age_band",
            ) -> dict:
    """Churn observé dans la base et risque attendu par cellule (x × y). Taux masqués (null)
    pour les cellules de moins de 30 lignes."""
    return get_heatmap(x, y, filters)


@router.get("/segments/profiles", response_model=SegmentProfiles,
            summary="Profils K-means : taille, risque, traits distinctifs")
def segment_profiles(filters: Annotated[Filters, Depends(get_filters)]) -> dict:
    """Un profil par segment comportemental (appris sans la cible) : effectifs, risque, revenu
    en jeu, action la plus fréquente et 3 traits (médianes comparées à la base entière)."""
    return get_segment_profiles(filters)


@router.get("/segments/{dimension}", response_model=Segments,
            summary="Indicateurs par modalité d'une dimension")
def segments(dimension: Dimension, filters: Annotated[Filters, Depends(get_filters)]) -> dict:
    """Effectifs, taux de churn, revenu en jeu et part de High par modalité. Chaque modalité
    porte le filtre à ajouter pour un drill-down."""
    return get_segments(dimension, filters)
