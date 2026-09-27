# Bilans d'étape

Un bilan par étape (E1 à E19), au format défini dans `CLAUDE.md`. Les chiffres cités sont des résultats réellement obtenus.

## Bilan — Étape 1 : Setup du repository

**Fait** :
- Structure du repo créée (package `churn` en layout `src/`, `configs/`, `docs/`, `api/routers/`, `reports/figures/`)
- Configuration centrale `configs/config.yaml` + `churn.config` (validation pydantic, chemins absolus)
- `load_raw()` typé, logging centralisé, script `scripts/check_setup.py` et premiers tests
- Environnement `.venv` neuf, `requirements.txt` figé, `pip install -e .` fonctionnel
- `.gitignore` réécrit en UTF-8 (l'ancien, en UTF-16, était ignoré par git)
- Nettoyage : ancienne `config.py` et 10 fichiers vides de l'ancienne arborescence supprimés

**Fichiers** :
- Créés : `pyproject.toml`, `Makefile`, `configs/config.yaml`, `src/churn/{config,logging_setup}.py`, `src/churn/data/load.py`, `src/churn/*/__init__.py`, `scripts/check_setup.py`, `tests/test_config.py`, `.env.example`, `CLAUDE.md`, `docs/{CONTEXTE_PROJET,decisions,bilans}.md`
- Modifiés : `.gitignore`, `requirements.txt`
- Supprimés : `config.py`, stubs vides (`api/utils.py`, `scripts/{evaluate,feature_engineering,preprocessing,utils}.py`, `tests/test_{api,data,model}.py`, `docker-compose.yml`, `.dvcignore`)

**Résultats clés** :
- `data/raw/telco_churn.csv` : 100 000 lignes × 100 colonnes
- `churn` : 0 → 50 438 (50,44 %), 1 → 49 562 (49,56 %)
- `Customer_ID` unique : True
- `pytest` : 4 passed ; `ruff check .` : All checks passed

**Décisions et justification** : voir D13 à D17 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Pourquoi un package installable plutôt que des notebooks ?* Le même code testé sert aux notebooks, aux scripts, à l'API et à l'assistant : un chiffre affiché ne peut pas diverger d'un chiffre calculé.
- *Pourquoi un fichier YAML de config ?* Une seule source de vérité pour la graine, le split, les colonnes exclues et les hypothèses métier ; aucun chemin en dur.
- *Pourquoi `real_churn_rate` est-il marqué hypothèse ?* Le dataset est échantillonné à 50/50 ; le taux réel n'y figure pas. 2 %/mois est un ordre de grandeur supposé, pas une mesure.

**Limites / points ouverts** :
- Cohérence d'unité : la correction du prior doit utiliser le taux de churn sur la **même fenêtre que la cible** ; si `churn` est mesuré sur ~2 mois (Cell2Cell), 2 %/mois n'est pas directement le bon prior. À trancher avant E10.
- `venv/` (84 661 fichiers) et l'ancien CSV sont suivis par git depuis le commit `init` : à retirer de l'index (`git rm -r --cached`).
- `notebooks/00_Setup.ipynb` (ancienne approche) supprimé le 28/09 ; remplacé par `scripts/check_setup.py` puis `01_data_audit.ipynb`.
- `outputs/` et `mlruns/` hors structure cible.
- pandas 3.0 : type `str` par défaut et copy-on-write, à garder en tête pour le nettoyage.
- Les cibles `make data/train/artifacts/api` pointent vers des scripts créés aux étapes E3, E9, E12, E13.

**Étape suivante** : E2 — Audit qualité des données (`01_data_audit.ipynb`, `churn.data.validate`).

## Bilan — Étape 2 : Audit qualité des données

**Fait** :
- Schéma pandera `raw` / `clean` : 100 colonnes attendues, bornes plausibles, modalités autorisées, 10 règles de cohérence strictes
- `clean()` par règles fixes : négatifs → NaN + indicateur, code « inconnu » propre à chaque colonne → `Unknown`, typage `category` à modalités fixes
- Audit des manquants par motif, co-occurrence, χ² « manquant × churn » avec Holm et V de Cramér, doublons, cohérence, outliers
- Notebook `01_data_audit.ipynb` exécuté, rapport `reports/data_quality_report.md`, 2 figures, 14 décisions (D18–D31)

**Fichiers** :
- Créés : `src/churn/data/{validate,clean,audit}.py`, `src/churn/plots.py`, `notebooks/01_data_audit.ipynb`, `reports/data_quality_report.md`, `reports/figures/01_missing_{rates,cooccurrence}.png`, `tests/test_clean_validate.py`
- Modifiés : `configs/config.yaml` et `src/churn/config.py` (`reports_dir`), `requirements.txt` (nbformat, nbclient), `docs/decisions.md`

**Résultats clés** :
- Schéma brut : 4 anomalies seulement, des négatifs (`eqpdays` 133, `totmrc_Mean` 23, `rev_Mean` 5, `avg6rev` 3) ; après `clean()` : 0 échec
- 18 motifs de manquants ; socio externe de 22 à 49 % (`numbcars` 49,4 %), manquants liés entre eux (r de 0,36 à 0,97), indépendants de l'usage
- χ² : 15/16 motifs significatifs après Holm, V ≤ 0,065 ; écarts de churn : `change_*` +26,8 pts, bloc d'usage (357 clients) +19,1 pts, `hnd_webcap` +10,7 pts, `hnd_price` -13,0 pts, `avg6*` -9,6 pts ; bloc socio non significatif
- Cohérence : 10 règles strictes à 0 violation ; informatives : `adjrev > totrev` 48, `ovrrev ≠ somme` 187, `eqpdays > ancienneté` 5 145, `actvsubs = 0` 81
- Outliers : Tukey de 0,26 % (`hnd_price`) à 26 % (`change_rev`) ; maxima isolés `roam_Mean` (×41 le q99,9), `change_rev` (×33), `uniqsubs` = 196 (×28)
- 0 doublon ; tests : 13 passed ; ruff : OK

**Décisions et justification** : D18 à D31 dans `docs/decisions.md`. Les principales : « U » n'est pas remplacé partout (Urban dans `prizm_social_one`), NaN ≠ Unknown, aucune ligne supprimée, tout ce qui apprend va dans le pipeline.

**À savoir défendre à l'oral** :
- *Pourquoi ne pas remplacer tous les « U » par Unknown ?* Le code dépend de la colonne : dans `prizm_social_one`, U = Urban (23 613 clients). Chaque remplacement est déclaré colonne par colonne dans `UNKNOWN_CODES`.
- *Tout est significatif, qu'en conclure ?* Avec n = 100 000, la p-value ne discrimine plus rien ; on lit le V de Cramér (≤ 0,065, effets faibles) et l'écart de taux en points. Holm corrige la multiplicité des 16 tests.
- *Pourquoi ne pas supprimer les outliers ?* Ce sont des clients réels (queues lourdes, pas des erreurs) ; tout écrêtage apprend un seuil, il doit être fitté dans la CV.

**Limites / points ouverts** :
- Le χ² utilise la cible sur 100 % des lignes (D18) : **à relancer sur `train.parquet` après E3**, avec mise à jour du rapport et de D18.
- **Fuite possible (D32)** : sans usage (357, 68,6 % de churn) et `change_*` manquants (891, 76,1 %) pourraient signifier « déjà parti ». Test en E8 : modèle avec / sans ces indicateurs.
- `eqpdays` négatif → NaN + indicateur : choix confirmé (écrêtage à 0 écarté).
- Cause des 534 `change_*` manquants hors bloc d'usage et des 213 `avg6*` manquants chez des clients anciens : non documentée.
- Sens exact de `adjrev`, `ovrrev` : à confirmer dans la documentation Cell2Cell.
- Git : `venv/` et l'ancien CSV sont toujours suivis (nettoyage en attente de validation).

**Étape suivante** : E3 — Split 80/20 stratifié (`churn.data.split`, `scripts/make_dataset.py`, `make data`), puis relance du χ² de l'audit sur le train (D18).
