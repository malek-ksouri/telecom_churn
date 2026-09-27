"""Vérification du setup (E1) : charge le CSV brut, affiche sa forme et la répartition de churn."""

from __future__ import annotations

import logging

from churn.config import get_config
from churn.data.load import load_raw
from churn.logging_setup import setup_logging

logger = logging.getLogger("check_setup")


def main() -> None:
    """Point d'entrée."""
    setup_logging()
    cfg = get_config()
    cfg.ensure_dirs()
    logger.info("Racine du projet : %s", cfg.root)
    logger.info("CSV brut : %s", cfg.raw_path)

    df = load_raw()
    target = cfg.data.target
    counts = df[target].value_counts(dropna=False).sort_index()
    shares = df[target].value_counts(normalize=True, dropna=False).sort_index()

    print(f"shape : {df.shape}")
    print(f"\nvalue_counts({target}) :")
    for value in counts.index:
        print(f"  {value} : {counts[value]:>6} ({shares[value]:.2%})")
    print(f"\n{cfg.data.id_col} unique : {df[cfg.data.id_col].is_unique}")
    print(f"Colonnes hors modèle : {cfg.non_feature_columns}")
    rate = cfg.business.real_churn_rate
    print(f"real_churn_rate = {rate.value} {rate.unit} (hypothèse : {rate.is_hypothesis})")


if __name__ == "__main__":
    main()
