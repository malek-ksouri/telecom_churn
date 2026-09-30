"""Entraîne le modèle final sur tout le train et l'enregistre (``make train``).

Le modèle final (``models.final``) et ses paramètres sont lus dans ``configs/config.yaml``.
Le jeu de test n'est jamais lu ici. Sorties : ``models/pipeline.joblib`` (modèle brut),
``models/final_model.joblib`` (modèle calibré + taux réel, si ``models.calibration`` est
défini) et ``models/model_card.md``.
"""

from __future__ import annotations

import logging
import sys
import time

import joblib

from churn.config import get_config
from churn.data.split import load_train
from churn.evaluation.calibration import make_calibrated
from churn.logging_setup import setup_logging
from churn.models.factory import build_pipeline
from churn.models.final import FinalChurnModel
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
    print(f"modèle brut : {model_path}")

    method = cfg.models.calibration
    if method is not None:
        # Modèle livrable (E10) : LightGBM recalibré (CV interne sur tout le train) + hypothèse
        # de taux réel pour la correction du prior.
        start = time.perf_counter()
        calibrated = make_calibrated(build_pipeline(final), method,
                                     random_state=cfg.random_state).fit(train, y)
        final_model = FinalChurnModel(calibrated=calibrated, method=method,
                                      sample_rate=float(y.mean()),
                                      real_rate=cfg.business.real_churn_rate.value)
        final_path = cfg.paths.models_dir / "final_model.joblib"
        joblib.dump(final_model, final_path)
        logger.info("Modèle calibré (%s) entraîné en %.1f s", method, time.perf_counter() - start)
        print(f"modèle final calibré : {final_path}")
    else:
        logger.warning("models.calibration vide : pas de modèle calibré (E10).")

    card_path = write_model_card(n_train=len(train))
    print(f"fiche : {card_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
