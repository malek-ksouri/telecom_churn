"""Construit data/processed/{train,test}.parquet : chargement -> clean -> split 80/20 stratifié.

Usage : ``make data`` (ou ``python scripts/make_dataset.py``).
"""

from __future__ import annotations

import logging
import sys

from churn.config import get_config
from churn.data.clean import clean
from churn.data.load import load_raw
from churn.data.split import save_splits, split_summary, split_train_test
from churn.data.validate import schema_failures
from churn.logging_setup import setup_logging

logger = logging.getLogger("make_dataset")


def main() -> int:
    """Point d'entrée. Retourne 1 si les données nettoyées violent le schéma."""
    setup_logging()
    cfg = get_config()

    df = clean(load_raw())
    failures = schema_failures(df, "clean")
    if not failures.empty:
        logger.error("Données nettoyées non conformes :\n%s", failures.to_string())
        return 1

    train, test = split_train_test(df, cfg)
    summary = split_summary(train, test, cfg)
    save_splits(train, test, cfg)

    print(f"train : {summary['n_train']:>6} lignes | churn {summary['churn_train']:.2%}")
    print(f"test  : {summary['n_test']:>6} lignes | churn {summary['churn_test']:.2%}")
    print(f"part du test : {summary['part_test']:.1%} | "
          f"{cfg.data.id_col} communs : {summary['ids_communs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
