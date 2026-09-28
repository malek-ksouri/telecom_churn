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
- Le χ² utilisait la cible sur 100 % des lignes (D18) : **relancé sur `train.parquet` en E3**, rapport et D18 mis à jour (conclusions inchangées).
- **Fuite possible (D32)** : sans usage (357, 68,6 % de churn) et `change_*` manquants (891, 76,1 %) pourraient signifier « déjà parti ». Test en E8 : modèle avec / sans ces indicateurs.
- `eqpdays` négatif → NaN + indicateur : choix confirmé (écrêtage à 0 écarté).
- Cause des 534 `change_*` manquants hors bloc d'usage et des 213 `avg6*` manquants chez des clients anciens : non documentée.
- Sens exact de `adjrev`, `ovrrev` : à confirmer dans la documentation Cell2Cell.
- Git : `venv/` et l'ancien CSV sont toujours suivis (nettoyage en attente de validation).

**Étape suivante** : E3 — Split 80/20 stratifié (`churn.data.split`, `scripts/make_dataset.py`, `make data`), puis relance du χ² de l'audit sur le train (D18).

## Bilan — Étape 3 : Split train/test

**Fait** :
- `churn.data.split` : split stratifié, contrôles, sauvegarde Parquet, `load_train()` et `load_test(final_evaluation=True)`
- `scripts/make_dataset.py` (`make data`) : chargement → `clean()` → validation du schéma `clean` → split → `data/processed/`
- `tests/test_split.py` : tailles, taux de churn, absence d'ID communs, types après Parquet, reproductibilité, verrou du test
- D18 : χ² « manquant × churn » relancé sur le train seul, sur les NaN de la source ; notebook 01 et rapport régénérés

**Fichiers** :
- Créés : `src/churn/data/split.py`, `scripts/make_dataset.py`, `tests/test_split.py`, `data/processed/{train,test}.parquet` (non versionnés)
- Modifiés : `src/churn/data/audit.py` (`source_missingness_view`), `notebooks/01_data_audit.ipynb`, `reports/data_quality_report.md`, `docs/decisions.md`

**Résultats clés** :
- train : 80 000 lignes, 39 650 churners (49,56 %) ; test : 20 000 lignes, 9 912 churners (49,56 %)
- `Customer_ID` communs : 0 ; `train.parquet` relu : 0 échec du schéma `clean` (21 `category`, 4 `int8` conservés)
- χ² sur le train : 16/16 motifs significatifs (Holm), V ≤ 0,063 ; `change_*` +26,7 pts, sans usage +19,5 pts (293 clients, 68,9 %), `hnd_webcap` +10,4 pts
- Tests : 19 passed ; ruff : OK

**Décisions et justification** : D33 (split après `clean()`, Parquet), D34 (verrou sur le test) ; D18, D22, D32 mises à jour avec les chiffres du train.

**À savoir défendre à l'oral** :
- *Pourquoi nettoyer avant le split ?* `clean()` n'utilise que des règles fixes (aucune statistique apprise) : pas de fuite, et exactement le même traitement pour le train, le test et un nouveau client dans l'API.
- *Pourquoi stratifier alors que la cible est à 50/50 ?* Pour garantir le même taux dans les deux jeux (49,56 % des deux côtés) : sans stratification, l'écart est aléatoire et fausse la comparaison des métriques.
- *Comment garantir que le test n'est pas regardé ?* `load_test()` lève une erreur sans `final_evaluation=True` ; toute analyse passe par `load_train()`.

**Limites / points ouverts** :
- Split aléatoire, pas temporel : le dataset n'a pas de date de mesure, on ne peut pas simuler « entraîner sur le passé, prédire le futur ».
- L'audit descriptif (hors χ²) reste calculé sur 100 000 lignes, car il ne lit pas la cible.
- Git : `venv/` et l'ancien CSV toujours suivis (en attente).

**Étape suivante** : E4 — EDA sur `train.parquet` uniquement.

## Bilan — Étape 4 : Analyse exploratoire (EDA)

**Fait** :
- `notebooks/02_eda.ipynb` en 3 parties (univariée, bivariée, multivariée et segmentation), exécuté sur `train.parquet` uniquement
- `churn.eda` (statistiques par bloc, taux de churn avec IC de Wilson, déciles, contrastes, Spearman, segmentation) et `churn.charts` (Plotly sur données agrégées)
- 27 figures PNG dans `reports/figures/02_*.png`, chacune suivie d'une conclusion ; 8 insights métier chiffrés
- Tests `tests/test_eda.py` (6 tests)

**Fichiers** :
- Créés : `src/churn/eda.py`, `src/churn/charts.py`, `notebooks/02_eda.ipynb`, `tests/test_eda.py`, `reports/figures/02_*.png`
- Modifiés : `src/churn/logging_setup.py` (logs tiers silencieux), `requirements.txt` (kaleido), `docs/decisions.md`

**Résultats clés** :
- Univarié : 68 numériques sur 77 très asymétriques ; 21 à plus de 50 % de zéros ; `kid*` 88-94 % Unknown, `asl_flag` 86 % N
- `months` : 29-40 % de churn à 6-10 mois, **64,8 % à 11 mois**, 61,7 % à 12 mois, ~50 % ensuite
- `eqpdays` : **42,0 % à 300-304 j → 59,0 % à 305-309 j** ; 56,5 % au-delà de 305 j contre 39,5 % en deçà
- `hnd_price` : 57-58 % à 9,99-29,99 $ contre 41 % à 199,99 $ ; `change_mou` : 55,4 % (forte baisse) contre ~45 % (hausse), 76,0 % si manquant
- Service client : 46,9 % si au moins un appel contre 51,7 %, écart maintenu à usage égal
- Région : 45,9 % à 56,1 % ; catégorielle la plus liée : `hnd_webcap` (V = 0,092)
- Spearman : ρ = 1,00 pour `totrev`/`adjrev` et `ovrrev`/`ovrmou` ; plus forte corrélation avec le churn : `eqpdays` 0,129
- Segmentation : 21 segments de 29,5 % à 76,6 % ; les 10 segments ≥ 55 % = 34,9 % des clients, churn 59,8 %
- Tests : 25 passed ; ruff : OK

**Décisions et justification** : D35 à D41 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Pourquoi `months` est-il important alors que sa corrélation avec le churn est quasi nulle ?* La relation est non monotone (bas, pic à 11-12 mois, plateau) : une corrélation mesure une tendance monotone. L'analyse par classes et les modèles à arbres captent ce type d'effet.
- *La fin d'engagement est-elle prouvée ?* Non : c'est une association cohérente sur deux variables (ancienneté et âge du terminal), compatible avec un engagement de 12 mois qui expire pendant la fenêtre de mesure. Il faudrait la date de fin de contrat pour la prouver.
- *Pourquoi les clients qui appellent le service client churnent-ils moins ?* Appeler traduit l'engagement (client actif). L'effet persiste à usage égal, donc ce n'est pas seulement un effet de volume. Aucune conclusion causale : « selon les données ».

**Limites / points ouverts** :
- Taux sur échantillon équilibré : ordres de grandeur relatifs uniquement ; correction du prior en E10.
- Seuils de segmentation (11-12 mois, 300 j) choisis sur le train : légitime, mais le benchmark doit être évalué en CV ou sur le test final, pas sur le train qui a servi à les choisir.
- Le pic d'effectif à 11 mois (6 407 clients) peut refléter la constitution de l'échantillon Cell2Cell.
- Git : `venv/` et l'ancien CSV toujours suivis (en attente).

**Étape suivante** : E5 — Analyse statistique (Mann-Whitney + rank-biserial, χ² + V de Cramér, correction de Holm ou BH), sur le train.
