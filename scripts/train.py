"""Entraîne le modèle final sur tout le train et l'enregistre (``make train``).

Le modèle final (``models.final``) et ses paramètres sont lus dans ``configs/config.yaml``.
Le jeu de test n'est jamais lu ici. Sorties : ``models/pipeline.joblib`` et
``models/model_card.md``.
"""

from __future__ import annotations

import logging
import sys
import time

import joblib

from churn.config import get_config
from churn.data.split import load_train
from churn.logging_setup import setup_logging
from churn.models.factory import build_pipeline
from churn.models.model_card import write_model_card

logger = logging.getLogger("train")


def main() -> int:
    """Point d'entrée. Retourne 1 si aucun modèle final n'est défini dans la config."""
    setup_logging()
    cfg = get_config()
    final = cfg.models.final
    if final is None:
        logger.error("models.final est vide dans configs/config.yaml : choisir le modèle en E9.")
        return 1

    train = load_train()
    y = train[cfg.data.target]
    start = time.perf_counter()
    pipeline = build_pipeline(final).fit(train, y)
    logger.info("Modèle %s entraîné sur %d clients en %.1f s", final, len(train),
                time.perf_counter() - start)

    cfg.paths.models_dir.mkdir(parents=True, exist_ok=True)
    model_path = cfg.paths.models_dir / "pipeline.joblib"
    joblib.dump(pipeline, model_path)
    card_path = write_model_card(n_train=len(train))
    print(f"modèle : {model_path}")
    print(f"fiche  : {card_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
