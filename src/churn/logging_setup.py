"""Configuration du logging, commune aux scripts, notebooks et à l'API."""

from __future__ import annotations

import logging
import os

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%H:%M:%S"
NOISY_LOGGERS = ("kaleido", "choreographer", "urllib3", "matplotlib")


def setup_logging(level: int | str | None = None) -> None:
    """Configure le logger racine.

    Idempotent : un second appel ne duplique pas les handlers (utile dans un notebook
    où la cellule est réexécutée).

    Args:
        level: niveau de log. Par défaut la variable d'environnement ``LOG_LEVEL``,
            sinon ``INFO``.
    """
    resolved = level or os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=resolved, format=LOG_FORMAT, datefmt=DATE_FORMAT, force=True)
    # Bibliothèques tierces très bavardes au niveau INFO (export PNG de Plotly via Chrome).
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
