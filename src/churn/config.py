"""Configuration centrale : lecture de ``configs/config.yaml`` et résolution des chemins.

Tout le code du projet obtient ses paramètres (graine, colonnes, chemins, hypothèses
métier) via :func:`get_config`. Les chemins du YAML sont relatifs à la racine du repo
et sont convertis ici en chemins absolus, ce qui rend le code indépendant du
répertoire courant (notebook, script, API ou tests).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

CONFIG_RELATIVE_PATH = Path("configs") / "config.yaml"


class PathsConfig(BaseModel):
    """Répertoires du projet, en chemins absolus après chargement."""

    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    models_dir: Path
    artifacts_dir: Path
    reports_dir: Path
    figures_dir: Path
    docs_dir: Path


class DataConfig(BaseModel):
    """Description du jeu de données et du split."""

    raw_file: str
    target: str
    id_col: str
    excluded_features: list[str]
    test_size: float = Field(gt=0, lt=1)
    train_file: str
    test_file: str


class ModelingConfig(BaseModel):
    """Paramètres de modélisation."""

    cv_folds: int = Field(ge=2)


class FeaturesConfig(BaseModel):
    """Familles de features actives (validées par ``FeatureBuilder``)."""

    groups: list[str]


class Hypothesis(BaseModel):
    """Valeur métier qui n'est pas issue des données et doit être présentée comme telle."""

    value: float = Field(gt=0, lt=1)
    unit: str
    is_hypothesis: bool
    source: str
    target_window: str | None = None
    sensitivity: list[float] = Field(default_factory=list)


class BusinessConfig(BaseModel):
    """Hypothèses métier."""

    real_churn_rate: Hypothesis


class Config(BaseModel):
    """Configuration complète et validée du projet."""

    root: Path
    project_name: str
    random_state: int
    paths: PathsConfig
    data: DataConfig
    modeling: ModelingConfig
    features: FeaturesConfig
    business: BusinessConfig

    @property
    def raw_path(self) -> Path:
        """Chemin absolu du CSV brut."""
        return self.paths.raw_dir / self.data.raw_file

    @property
    def train_path(self) -> Path:
        """Chemin absolu du jeu d'entraînement après split."""
        return self.paths.processed_dir / self.data.train_file

    @property
    def test_path(self) -> Path:
        """Chemin absolu du jeu de test (réservé à l'évaluation finale)."""
        return self.paths.processed_dir / self.data.test_file

    @property
    def non_feature_columns(self) -> list[str]:
        """Colonnes à retirer avant modélisation : identifiant, cible et exclusions éthiques."""
        cols = [self.data.id_col, self.data.target, *self.data.excluded_features]
        return list(dict.fromkeys(cols))

    def ensure_dirs(self) -> None:
        """Crée les répertoires de travail s'ils n'existent pas (data/ n'est pas versionné)."""
        for directory in self.paths.model_dump().values():
            Path(directory).mkdir(parents=True, exist_ok=True)


def find_project_root() -> Path:
    """Retourne la racine du repo.

    Ordre : variable d'environnement ``CHURN_ROOT``, sinon premier dossier parent de ce
    fichier qui contient ``configs/config.yaml``.

    Raises:
        FileNotFoundError: si aucune racine n'est trouvée.
    """
    env_root = os.environ.get("CHURN_ROOT")
    if env_root:
        return Path(env_root).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / CONFIG_RELATIVE_PATH).is_file():
            return parent
    raise FileNotFoundError(
        f"Impossible de trouver {CONFIG_RELATIVE_PATH} dans les parents de {__file__}. "
        "Définissez CHURN_ROOT ou installez le package en mode éditable (pip install -e .)."
    )


def load_config(path: Path | None = None) -> Config:
    """Charge et valide la configuration.

    Args:
        path: chemin du YAML. Par défaut ``<racine>/configs/config.yaml``.

    Returns:
        La configuration validée, avec des chemins absolus.
    """
    root = find_project_root()
    config_path = path or root / CONFIG_RELATIVE_PATH
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["paths"] = {name: (root / rel).resolve() for name, rel in raw["paths"].items()}
    return Config(root=root, **raw)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Configuration du projet, chargée une seule fois par processus."""
    return load_config()
