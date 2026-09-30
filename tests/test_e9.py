"""Tests de E9 : écriture de la config, métriques du test final, réglage Optuna."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import optuna
import pytest

from churn.config import find_project_root, load_config, write_final_model, write_model_params
from churn.evaluation import metrics as m
from churn.models.tune import suggest_lightgbm_params


@pytest.fixture
def config_copy(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    shutil.copy(find_project_root() / "configs" / "config.yaml", path)
    return path


def test_write_model_params_keeps_comments(config_copy: Path) -> None:
    write_model_params("lightgbm", {"num_leaves": 31, "learning_rate": 0.05}, config_copy)
    write_final_model("lightgbm", config_copy)
    cfg = load_config(config_copy)
    assert cfg.models.params["lightgbm"] == {"num_leaves": 31, "learning_rate": 0.05}
    assert cfg.models.final == "lightgbm"
    assert "HYPOTHÈSE" in config_copy.read_text(encoding="utf-8")   # commentaires conservés
    write_model_params("lightgbm", {"num_leaves": 15}, config_copy)  # réécriture idempotente
    assert load_config(config_copy).models.params["lightgbm"] == {"num_leaves": 15}


def test_bootstrap_ci_contains_auc_and_difference_is_paired() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 2000)
    good = y + rng.normal(0, 1, 2000)
    weak = y + rng.normal(0, 3, 2000)
    ci = m.bootstrap_auc_ci(y, good, n_boot=200)
    assert ci["ic_bas"] <= ci["auc"] <= ci["ic_haut"]
    diff = m.bootstrap_auc_difference(y, good, weak, n_boot=200)
    assert diff["ic_bas"] > 0 and diff["part_positive"] == 1.0


def test_gain_curve_and_confusion() -> None:
    y = np.array([1, 1, 0, 0, 1, 0, 0, 0, 0, 0])
    score = np.arange(10)[::-1].astype(float)          # classement parfait des 2 premiers
    curve = m.gain_curve(y, score, points=10)
    assert curve["gain"].iloc[-1] == pytest.approx(100.0)
    assert curve["gain"].is_monotonic_increasing
    cm = m.confusion_at_top_k(y, score, 0.2)
    assert cm.iloc[0, 0] == 2 and cm.to_numpy().sum() == 10


def test_search_space_is_seeded_and_valid() -> None:
    def first_proposal() -> dict:
        study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=42))
        return suggest_lightgbm_params(study.ask())

    assert first_proposal() == first_proposal()          # même graine, même proposition
    p = first_proposal()
    assert 8 <= p["num_leaves"] <= 128 and 0.01 <= p["learning_rate"] <= 0.2
    assert p["subsample_freq"] == 1
