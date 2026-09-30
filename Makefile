# Commandes du projet. Sous Windows : `mingw32-make <cible>` (ou installer make via choco).

ifeq ($(OS),Windows_NT)
SHELL := cmd.exe
PYTHON := .venv\Scripts\python.exe
else
PYTHON := .venv/bin/python
endif

.PHONY: help install data train artifacts api front dev test check

help:
	@echo Cibles : install data train artifacts api front dev test check

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

# Nettoyage + split 80/20 -> data/processed/ (E3)
data:
	$(PYTHON) scripts/make_dataset.py

# Entraînement du pipeline final -> models/pipeline.joblib (E9)
train:
	$(PYTHON) scripts/train.py

# Scores, SHAP, KPI -> artifacts/ (E12)
artifacts:
	$(PYTHON) scripts/build_artifacts.py

api:
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

front:
	cd frontend && npm run dev

# API (port 8000) + frontend (port 5173) dans le même terminal (concurrently) ;
# Ctrl+C arrête les deux. Premier lancement : cd frontend && npm install
dev:
	cd frontend && npm run dev:all

test:
	$(PYTHON) -m pytest -q
	$(PYTHON) -m ruff check .

# Vérification du setup (E1) : charge le CSV brut et affiche shape + value_counts
check:
	$(PYTHON) scripts/check_setup.py
