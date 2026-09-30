# Bilans d'étape

Un bilan par étape (E1 à E19), au format défini dans `CLAUDE.md`. Les chiffres cités sont des résultats réellement obtenus.

## Bilan — Étape 1 : Setup du repository

**Fait** :
- Structure du repo créée (package `churn` en layout `src/`, `configs/`, `docs/`, `api/routers/`, `reports/figures/`)
- Configuration centrale `configs/config.yaml` + `churn.config` (validation pydantic, chemins absolus)
- `load_raw()` typé, logging centralisé, script `scripts/check_setup.py` et premiers tests
- Environnement `.venv` neuf, `requirements.txt` figé, `pip install -e .` fonctionnel
- `.gitignore` réécrit en UTF-8 (l'ancien, en UTF-16, n'était pas lu)
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
- Service client : 46,9 % si au moins un appel contre 51,7 %, écart faible (2 à 5 pts) maintenu à usage égal ; interprétation au stade d'hypothèse
- Région : 45,9 % à 56,1 % ; catégorielle la plus liée : `hnd_webcap` (V = 0,092)
- Spearman : ρ = 1,00 pour `totrev`/`adjrev` et `ovrrev`/`ovrmou` ; plus forte corrélation avec le churn : `eqpdays` 0,129
- Segmentation : 21 segments de 29,5 % à 76,6 % ; les 10 segments ≥ 55 % = 34,9 % des clients, churn 59,8 %
- Tests : 25 passed ; ruff : OK

**Décisions et justification** : D35 à D41 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Pourquoi `months` est-il important alors que sa corrélation avec le churn est quasi nulle ?* La relation est non monotone (bas, pic à 11-12 mois, plateau) : une corrélation mesure une tendance monotone. L'analyse par classes et les modèles à arbres captent ce type d'effet.
- *La fin d'engagement est-elle prouvée ?* Non : c'est une association cohérente sur deux variables (ancienneté et âge du terminal), compatible avec un engagement de 12 mois qui expire pendant la fenêtre de mesure. Il faudrait la date de fin de contrat pour la prouver.
- *Les clients qui appellent le service client churnent-ils moins ?* Un peu (46,9 % contre 51,7 %), et l'écart persiste à usage égal, mais il est faible. C'est une **hypothèse**, pas une conclusion : client engagé, offre de rétention faite pendant l'appel ou problème résolu sont trois explications possibles, que les données (sans motif ni issue de l'appel) ne permettent pas de départager.

**Limites / points ouverts** :
- Taux sur échantillon équilibré : ordres de grandeur relatifs uniquement ; correction du prior en E10.
- Seuils de segmentation (11-12 mois, 300 j) choisis sur le train : légitime, mais le benchmark doit être évalué en CV ou sur le test final, pas sur le train qui a servi à les choisir.
- Le pic d'effectif à 11 mois (6 407 clients) peut refléter la constitution de l'échantillon Cell2Cell.

**Étape suivante** : E5 — Analyse statistique (Mann-Whitney + rank-biserial, χ² + V de Cramér, correction de Holm ou BH), sur le train.

## Bilan — Étape 4b : Segmentation clients par K-means

**Fait** :
- `churn.segmentation.kmeans` : pipeline réutilisable (sélection → imputation médiane → log → standardisation → KMeans), critères de choix de k, profilage, nommage par règles, sauvegarde et affectation d'un segment à tout client
- `notebooks/02b_segmentation.ipynb` : choix de k (2 à 10), profils, noms métier, puis seulement ensuite churn par cluster, PCA, comparaison avec les règles E4
- `models/segmentation.joblib` (pipeline entraîné sur le train, noms, variables, silhouette), vérifié identique après rechargement
- Tests `tests/test_segmentation.py` (8 tests, dont : la cible n'influence pas les clusters)

**Fichiers** :
- Créés : `src/churn/segmentation/{__init__,kmeans}.py`, `notebooks/02b_segmentation.ipynb`, `models/segmentation.joblib`, `reports/figures/02b_*.png` (6), `tests/test_segmentation.py`
- Modifiés : `src/churn/charts.py` (choix de k, heatmap signée, PCA en petits multiples), `src/churn/eda.py` (χ² + V de Cramér, étiquettes des segments par règles), `docs/decisions.md`

**Résultats clés** :
- 11 variables, corrélation maximale r = 0,75 : aucune retirée
- Choix de k : silhouette 0,180 (k = 2) puis 0,126 à 0,146 ; k = 5 : silhouette **0,144**, Davies-Bouldin 1,947, ARI minimal **0,996** ; k = 6 et 7 instables (ARI min 0,64 et 0,55)
- 5 profils : usage modéré, clients récents (30,5 %) ; gros consommateurs en baisse d'usage (21,1 %) ; clients anciens à terminal ancien et bon marché (20,1 %) ; gros consommateurs en hausse d'usage (19,4 %) ; lignes secondaires à petit forfait (8,9 %)
- Churn par profil : de **45,4 %** (gros consommateurs en hausse) à **55,9 %** (clients anciens à terminal ancien) ; χ² = 528,7 (ddl 4), p < 10⁻¹¹², **V de Cramér = 0,081**
- À l'intérieur de chaque profil, 11-12 mois d'ancienneté : 59-66 % de churn
- PCA : 47 % de variance sur 2 axes (volume ; ancienneté et terminal), clusters contigus
- Comparaison (AUC en CV d'un score = taux du segment) : règles E4 **0,617** (V = 0,210), ancienneté seule 0,582, K-means **0,544**
- Tests : 33 passed ; ruff : OK

**Décisions et justification** : D42 à D46 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Pourquoi k = 5 alors que k = 2 a la meilleure silhouette ?* k = 2 ne sépare que petits et gros consommateurs, inutile pour un métier. Entre 4 et 6, les silhouettes sont presque égales ; k = 5 est le plus stable (ARI 0,996) et isole la tendance d'usage des gros consommateurs.
- *Pourquoi K-means sépare-t-il moins bien le churn que des règles simples ?* Il ne voit pas la cible : il regroupe des clients qui se ressemblent, et ce qui les distingue le plus (le volume d'usage) est peu lié au churn. Il ne capte pas non plus le pic non monotone à 11-12 mois. Les règles, elles, ont été construites à partir du churn.
- *Pourquoi ne pas ajouter le cluster comme variable du modèle ?* Il apporte peu (V = 0,081) et résume des variables que le modèle possède déjà ; s'il était ajouté, KMeans devrait être ajusté dans chaque fold, sinon il y aurait fuite.

**Limites / points ouverts** :
- Séparation faible (silhouette 0,144) : les noms décrivent des tendances de groupe, beaucoup de clients sont à la frontière de deux profils.
- Le bloc usage-facture (5 variables corrélées de 0,5 à 0,75) pèse plus que les autres dans les distances ; une pondération ou une réduction préalable (PCA) serait une variante à tester si la segmentation devait être affinée.
- L'avantage des règles en AUC est en partie optimiste (seuils choisis sur le churn du train).

**Étape suivante** : E5 — Analyse statistique (Mann-Whitney + rank-biserial, χ² + V de Cramér, correction de Holm ou BH), sur le train.

---

# Bilan de partie — A : Données (E1 à E4b)

## 1. Avancement par rapport au planning

| Étape | Prévu | Réalisé | Statut |
|---|---|---|---|
| E1 Setup | Lun 28/09 | 27/09 | En avance |
| E2 Audit qualité | Lun 28/09 | 28/09 | Dans les temps |
| E3 Split | Lun 28/09 | 28/09 | Dans les temps (+ relance du χ² de E2 sur le train) |
| E4 EDA | Lun 28/09 | 28/09 | Dans les temps |
| E4b Segmentation K-means | Non prévue | 28/09 | Ajoutée, absorbée dans la journée |

**Verdict : dans les temps**, avec une étape de plus que prévu. La partie B (29/09 : E5 à E8) est la plus chargée du planning. Pour la tenir :

- **E5 peut être réduite** : le χ² et le V de Cramér ont déjà été calculés pour les catégorielles (E2, E4, E4b). Il reste Mann-Whitney + rank-biserial sur les numériques et une correction de Holm globale, soit environ une heure.
- **À couper en premier si E8 déborde** : CatBoost (garder LightGBM seul comme modèle avancé), puis le réglage fin des hyperparamètres (Optuna limité à 30 essais).

## 2. Chiffres clés consolidés

| Thème | Résultat |
|---|---|
| Données | 100 000 clients × 100 colonnes ; `Customer_ID` unique ; 0 doublon |
| Cible | 49,56 % de churners (échantillonnage équilibré, taux non réaliste) |
| Split | Train 80 000 / test 20 000, churn 49,56 % des deux côtés, 0 ID commun |
| Anomalies | 164 valeurs négatives impossibles (`eqpdays` 133, `totmrc_Mean` 23, `rev_Mean` 5, `avg6rev` 3) → NaN + indicateur |
| Cohérence | 10 règles strictes, 0 violation ; 4 règles informatives avec écarts explicables |
| Manquants | 18 motifs ; socio-démographie externe de 22 à 49 % ; 357 clients sans aucune donnée d'usage |
| Manquant × churn (train) | 16/16 motifs significatifs (Holm), V ≤ 0,063 ; `change_*` manquant +26,7 pts, sans usage +19,5 pts |
| Distributions | 68 numériques sur 77 très asymétriques ; 21 à plus de 50 % de zéros |
| Fin d'engagement | `months` 11-12 : 63,5 % de churn contre 33,8 % à 6-10 mois ; `eqpdays` : 42 % → 59 % entre 300 et 309 jours |
| Autres signaux | Terminal ≤ 29,99 $ : 57-58 % contre 41 % à 199,99 $ ; forte baisse d'usage : 55,4 % contre ~45 % |
| Force du signal | Corrélation max avec le churn : ρ = 0,13 (`eqpdays`) ; V max : 0,092 (`hnd_webcap`) |
| Redondances | ρ = 1,00 pour `totrev`/`adjrev` et `ovrrev`/`ovrmou` ; 0,98 pour `mou_Mean`/`avg3mou` |
| Segmentation par règles | 21 segments, de 29,5 % à 76,6 % ; AUC en CV 0,617 ; V = 0,210 |
| Segmentation K-means | k = 5, silhouette 0,144, ARI 0,996 ; churn de 45,4 % à 55,9 % ; AUC en CV 0,544 ; V = 0,081 |
| Qualité du code | 33 tests ; ruff sans erreur ; 3 notebooks exécutés ; 35 figures |

## 3. Décisions prises (D13 à D46)

| Thème | Décisions | En une phrase |
|---|---|---|
| Environnement | D13-D17 | `.venv` neuf, versions figées testées, config YAML validée, chemins absolus, une seule source de vérité |
| Nettoyage | D19-D21, D30-D31 | Règles fixes sans apprentissage ; négatifs → NaN + indicateur ; « inconnu » propre à chaque colonne (U = Urban conservé) ; NaN ≠ Unknown ; aucune ligne supprimée |
| Manquants | D22-D25 | Indicateur par motif en E6 ; pas de suppression des colonnes > 40 % ; clients sans usage conservés ; `avg6*` manquant surtout structurel |
| Fuite possible | D32 | Clients sans usage et `change_*` manquant : signal « déjà parti » possible, à tester en E8 (avec / sans) |
| Cohérence, outliers | D26-D29 | Règles strictes gardées comme garde-fou ; outliers conservés, transformations dans le pipeline |
| Split et test | D18, D33-D34 | Split après `clean()` ; χ² relancé sur le train ; `load_test()` verrouillé jusqu'à E9 |
| EDA | D35-D41 | Taux relatifs avec IC de Wilson ; analyse par classes (effets non monotones) ; fin d'engagement = association validée ; pistes de features ; segmentation par règles = benchmark |
| Segmentation | D42-D46 | K-means k = 5 sans la cible ; pas utilisé comme feature ; règles pour cibler, K-means pour décrire ; noms attribués par règles |

## 4. Risques pour la suite

| Risque | Impact | Parade |
|---|---|---|
| **Signal faible** (ρ max 0,13) | AUC probablement modeste (0,65-0,72 attendue) | Mesurer le gain par rapport au Dummy et au benchmark par règles (AUC 0,617) plutôt qu'en absolu |
| **Fuite « déjà parti »** (D32) | AUC gonflée, modèle inutile en pratique | Comparaison avec / sans indicateurs en E8 ; décision documentée |
| **Correction du prior** | Probabilités métier fausses si la fenêtre de la cible (~1-2 mois ?) ne correspond pas à « 2 % par mois » | Trancher l'unité avant E10 et la présenter comme hypothèse |
| **Benchmark par règles optimiste** | Seuils choisis sur le churn du train | Le comparer au modèle sur le test final (E9), pas seulement en CV |
| **Charge de la partie B** | 4 étapes, dont la modélisation | E5 réduite, CatBoost en option |
| **Dépendances d'exécution** | Export PNG via kaleido (Chrome requis) ; notebooks de 2 à 4 min | Figures déjà générées ; documenter la dépendance dans le README (E18) |

## 5. Questions d'oral probables

1. **Pourquoi avoir séparé train et test avant l'EDA, et comment garantir que le test n'a pas été regardé ?**
   Toute décision prise en regardant le test (un seuil, une variable, un regroupement) biaise l'évaluation finale vers l'optimisme. Le split est fait juste après un nettoyage par règles fixes, et `load_test()` lève une erreur sans `final_evaluation=True`. Même le χ² de l'audit a été relancé sur le train seul.

2. **La cible est à 50/50 : pourquoi pas de SMOTE, et que faites-vous de ce déséquilibre artificiel ?**
   Il n'y a pas de déséquilibre à corriger : les classes sont équilibrées. Le vrai problème est inverse : l'échantillon surreprésente les churners par rapport à la réalité (hypothèse : 2 % par mois). Les probabilités du modèle seront donc corrigées vers ce taux réel avant tout calcul métier, et l'accuracy n'est jamais utilisée seule.

3. **Qu'avez-vous appris de plus important dans les données ?**
   La fin d'engagement : 63,5 % de churn à 11-12 mois d'ancienneté contre 33,8 % avant, et un saut de 42 % à 59 % quand le terminal passe 300 jours. C'est une association cohérente sur deux variables indépendantes, compatible avec un engagement de 12 mois qui expire pendant la fenêtre de mesure, mais pas une preuve : il manque la date de fin de contrat.

4. **Presque tous vos tests sont significatifs : est-ce que ça veut dire que tout compte ?**
   Non. Avec 80 000 clients, un écart minuscule devient significatif. On lit donc la taille d'effet : les V de Cramér sont tous inférieurs à 0,1, la plus forte corrélation avec le churn est 0,13. On corrige aussi la multiplicité des tests (Holm). Le signal est réel mais faible et dispersé : la performance viendra de la combinaison des variables.

5. **Pourquoi votre segmentation K-means sépare-t-elle moins bien le churn qu'une règle simple, et à quoi sert-elle alors ?**
   K-means ne voit pas la cible : il regroupe des clients qui se ressemblent, surtout par leur volume d'usage, faiblement lié au churn, et il ne capte pas le pic non monotone à 11-12 mois (AUC 0,544 contre 0,617 pour les règles). Elle sert à décrire la base clients en 5 profils lisibles et à adapter l'action de rétention au profil ; le ciblage du risque revient aux règles puis au modèle.

## Bilan — Étape 5 : Analyse statistique

**Fait** :
- `churn.evaluation.stats` : Mann-Whitney + rank-biserial, χ² / Fisher + V de Cramér, écart entre classes et forme de la courbe, information mutuelle, Holm, redondance (Spearman, clustering hiérarchique, représentantes, VIF itératif), export des sorties
- `churn.data.audit.missing_indicators` : un indicateur par motif de manquants (17), testés avec les 4 indicateurs `_was_negative`
- `notebooks/03_statistical_analysis.ipynb` : démonstrations « p-value et taille d'échantillon » et « corrélation et effet non monotone », tableau final, redondance
- D47 enregistrée (fenêtre de la cible ≈ 1 mois, taux mensuel 2 %, sensibilité 1-2-3 % en E10) et ajoutée à `configs/config.yaml`

**Fichiers** :
- Créés : `src/churn/evaluation/stats.py`, `notebooks/03_statistical_analysis.ipynb`, `tests/test_stats.py`, `reports/stats_univariate.csv`, `reports/top15_importance.csv`, `reports/logreg_drop_list.json`, `reports/figures/03_*.png` (3)
- Modifiés : `src/churn/data/audit.py`, `src/churn/charts.py`, `src/churn/config.py`, `configs/config.yaml`, `docs/decisions.md`

**Résultats clés** :
- 118 tests (74 numériques, 20 catégorielles, 24 binaires) : **93 significatifs** après Holm, **116 effets négligeables**, 2 faibles (`eqpdays` r = +0,149, `hnd_price` r = −0,118), aucun moyen ou fort
- p-value de `change_mou` : 0,03 à n = 500, 10⁻⁴⁹ à n = 80 000, pour un effet stable autour de −0,06
- `months` : rank-biserial 0,053 (négligeable), mais V = 0,173 en 3 classes, écart entre déciles 28,7 pts et **1re en information mutuelle** (0,018 nat)
- Top 4 par information mutuelle : `months`, `eqpdays`, `totmrc_Mean`, `hnd_price` ; au-delà, écarts de l'ordre du bruit de l'estimateur
- 25 variables signalées « effet monotone négligeable, écart > 10 pts », dont 3 à courbe réellement non monotone
- V de Cramér identiques à E4 (écart max 0,0005)
- Redondance : 60 paires > 0,9, 17 groupes, 30 variables redondantes ; VIF : 6 retraits (max initial 134) ; **36 variables à retirer pour la régression logistique, 38 conservées (VIF max 6,7)**
- Tests : 39 passed ; ruff : OK

**Décisions et justification** : D47 à D53 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Pourquoi les p-values ne suffisent-elles pas ?* Elles mesurent la probabilité d'observer un écart par hasard, pas son importance ; à effet constant, elles diminuent avec n (erreur-type en 1/√n). Avec 80 000 clients, 93 tests sur 118 sont significatifs alors que 116 effets sont négligeables.
- *Comment une variable importante peut-elle avoir une corrélation nulle ?* Une corrélation (même de rang) mesure une tendance monotone. `months` a un pic à 11-12 mois : les deux côtés se compensent (r = 0,05). L'écart entre déciles et l'information mutuelle, qui est nulle seulement en cas d'indépendance, le détectent.
- *Pourquoi retirer des variables pour la régression logistique et pas pour les arbres ?* La colinéarité rend les coefficients instables et ininterprétables (VIF jusqu'à 134) ; un arbre choisit une variable à chaque division et n'est pas affecté. Exemple : `totcalls` ≈ `avgqty` × `months`.

**Limites / points ouverts** :
- L'information mutuelle a une précision de l'ordre de 0,001 nat : le classement au-delà du 4e rang est indicatif.
- L'information mutuelle favorise les effets touchant beaucoup de clients : un indicateur rare à fort effet (`manquant_change_mou_bloc`, +26,7 pts, 718 clients) est mal classé ; l'écart entre classes le signale.
- Tout est calculé sur le train complet : pas de fuite pour le test final, mais le choix des variables en E6-E7 devra être validé en CV.
- Le VIF ne porte que sur les numériques ; les catégorielles encodées et les indicateurs seront contrôlés dans le pipeline en E7.

**Étape suivante** : E6 — Feature engineering (indicateurs de fin d'engagement, indicateurs de manquants par motif, transformations log, sur la base de `top15_importance.csv`).

## Bilan — Étape 6 : Feature engineering

**Fait** :
- `churn.features.build.FeatureBuilder` : transformer sans état, 8 familles activables (dont `deja_parti` isolée pour le test de fuite), divisions sécurisées
- `churn.models.pipelines` (LightGBM par défaut ; régression logistique avec imputation, standardisation, one-hot et liste de retrait de E5) et `churn.evaluation.cv` (folds figés, AUC par fold, ablation, gain apparié)
- `notebooks/04_feature_engineering.ipynb` : justification de chaque feature, vérification du pic à 23-24 mois, taux de churn par classe, ablation 5 folds × 2 modèles, décision par famille
- Familles retenues inscrites dans `configs/config.yaml` ; tests `tests/test_features.py` (16 tests)

**Fichiers** :
- Créés : `src/churn/features/build.py`, `src/churn/models/pipelines.py`, `src/churn/evaluation/cv.py`, `notebooks/04_feature_engineering.ipynb`, `tests/test_features.py`, `reports/ablation_features.csv`, `reports/figures/04_*.png` (5)
- Modifiés : `configs/config.yaml`, `src/churn/config.py` (section `features`), `src/churn/charts.py`, `docs/decisions.md`

**Résultats clés** :
- Pas de second pic : 23-24 mois 51,7 %, 35-36 mois 48,4 % (contre 51,3 %) → seul le flag `in_contract_end` est gardé
- `in_contract_end` : 14,1 % des clients, 63,5 % de churn (47,3 % sinon) ; `handset_old` : 56,3 % contre 39,4 % ; `eqpdays_per_tenure_day` : information mutuelle 0,017
- Références (5 folds) : LightGBM **0,690 ± 0,005**, régression logistique **0,623 ± 0,004**
- Ablation, régression logistique : `cycle_engagement` **+28,2 ± 2,7 millièmes (5/5 folds)** ; autres familles de −0,1 à +2,9 ; toutes : +34,9
- Ablation, LightGBM : aucune famille au-delà de l'écart-type (max +1,3) ; `deja_parti` : **0,0 exactement**
- Configuration retenue (5 familles, 28 features) : régression logistique **0,654 ± 0,004** (+31,6), LightGBM **0,692 ± 0,004** (+1,8)
- Tests : 16 nouveaux (transformer sans état, pas d'inf, colonnes selon les familles) ; ruff : OK

**Décisions et justification** : D54 à D58 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Pourquoi le feature engineering n'améliore-t-il pas LightGBM ?* Un arbre découpe lui-même les variables aux bons seuils (11-12 mois, 300 jours) et gère les NaN ; il n'a pas besoin qu'on les lui donne. Une régression logistique, elle, est linéaire : sans l'indicateur `in_contract_end`, elle ne peut pas représenter un pic, d'où +28 millièmes d'AUC.
- *Pourquoi garder des familles qui ne dépassent pas l'écart-type ?* Règle explicite : gain positif dans les 5 folds pour au moins un modèle **et** utilité métier (raison lisible pour expliquer un score, levier d'action). Les familles sans les deux ont été retirées.
- *Le transformer ne fuit-il pas ?* Il n'apprend rien (test : `fit` ne change aucun attribut). En revanche, les seuils 11-12 mois et 300 jours ont été choisis en EDA sur le train entier : la CV est légèrement optimiste pour `cycle_engagement` ; le test final, jamais lu, tranchera.

**Limites / points ouverts** :
- Test de fuite D32 (E8) : pour LightGBM, il faudra neutraliser les NaN d'origine de `rev_Mean` et `change_mou`, pas seulement désactiver `deja_parti`.
- La régression logistique reste loin de LightGBM (0,654 contre 0,692) : préprocessing simple (pas de `log1p`), à améliorer en E7.
- Écart-type de l'AUC entre folds d'environ 0,004-0,005 : des écarts de moins de 5 millièmes entre modèles ne seront pas interprétables sans comparaison appariée.

**Étape suivante** : E7 — Pipeline + baselines (Dummy, régression logistique, arbre, forêt aléatoire), comparés sur les mêmes folds et au benchmark par règles (AUC 0,617).

## Bilan — Étape 7 : Pipeline de prétraitement et baselines

**Fait** :
- `churn.evaluation.metrics` (AUC, PR-AUC, Brier, lift / Precision / Recall à 5-10-20 %, résumé par fold) et `churn.models.train.cross_validate_model` (métriques de validation, AUC train, prédictions hors fold)
- Baselines sur les folds de E6 : `DummyClassifier(stratified)`, règles E4 (`SegmentRateClassifier`, taux appris dans chaque fold), LR simple de E6
- `churn.models.preprocessing` : LR améliorée entièrement dans le pipeline (log, winsorisation apprise, standardisation, imputation + indicateurs, splines, one-hot 1 %, branche binaire séparée), ablation et grille L1 / L2 × C
- `churn.models.factory.build_pipeline(model_name)` : 8 modèles, dont arbres et boosting (NaN conservés, catégorielles ordinales ou natives), pour E8
- `notebooks/05_modeling.ipynb` (1re partie) : fuite démontrée, ablation, deux défauts corrigés et mesurés, tableau comparatif, gain fold par fold, coefficients et splines

**Fichiers** :
- Créés : `src/churn/evaluation/metrics.py`, `src/churn/models/{train,baselines,preprocessing,factory}.py`, `notebooks/05_modeling.ipynb`, `tests/test_modeling.py` (7 tests), `tests/test_factory.py` (10 tests), `reports/figures/05_*.png` (3)
- Modifiés : `src/churn/charts.py` (coefficients, effet des splines, ablation), `docs/decisions.md`

**Résultats clés** (5 folds figés, moyenne ± écart-type) :

| Modèle | AUC | PR-AUC | lift@10 % | Precision@10 % | Brier | AUC train | Gain sur les règles |
|---|---|---|---|---|---|---|---|
| Dummy | 0,503 ± 0,002 | 0,497 | 1,01 | 49,9 % | 0,497 | 0,499 | −114,3 ± 4,1 |
| Règles E4 | 0,617 ± 0,004 | 0,584 | 1,31 | 64,8 % | 0,239 | 0,617 | référence |
| LR simple (E6) | 0,654 ± 0,004 | 0,626 | 1,40 | 69,4 % | 0,232 | 0,659 | +37,4 ± 3,6 |
| **LR améliorée** | **0,668 ± 0,004** | **0,648** | **1,49** | **74,0 %** | **0,229** | 0,671 | **+50,8 ± 1,7 (5/5)** |

- Ablation (gain cumulé sur la LR simple) : prétraitement de base +2,8 ; + log et winsorisation +11,3 ; + splines +14,9 ; C retenu par la règle de l'écart-type +13,5 millièmes. Indicateurs de manquant par colonne : +1,4 ± 0,4
- Grille : 0,6627 à 0,6694 ; L1 et L2 à égalité ; retenu L2, C = 0,01
- Défauts corrigés : AUC inchangée ; 8 colonnes constantes → 0 ; valeur max 253 → 65 ; L1 86 s → 35 s par fold
- Fuite de l'encodage par la cible : +0,4 millième (segments grands)
- Top coefficients : `handset_old` +0,57, `in_contract_end` +0,54, `mou_Mean` −0,37, `avgqty` +0,32 (baisse d'usage à usage récent égal), `crclscod_EA` −0,27 ; tous cohérents avec l'EDA
- Chiffres identiques à ceux attendus (0,50 ; 0,617 ; 0,654 ; 0,668) : aucun écart au-delà de 0,3 millième
- Tests : 72 passed ; ruff : OK

**Décisions et justification** : D59 à D66 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Où serait la fuite si l'imputation, la winsorisation ou l'encodage étaient faits avant le découpage ?* Médiane, quantiles d'écrêtage, moyenne et écart-type, modalités retenues : tout serait calculé en incluant les clients du fold de validation, que le modèle est censé ne pas connaître. Pour un encodage par la cible, c'est pire : le churn du client entre dans son propre score. L'effet est toujours dans le sens de l'optimisme.
- *Pourquoi C = 0,01 et pas la meilleure AUC ?* La grille est plate : les écarts (≤ 1,8 millième) sont sous l'écart-type entre folds (3,8). Entre des modèles indiscernables, on prend le plus régularisé, dont les coefficients sont stables.
- *Comment avez-vous trouvé les deux défauts, alors que l'AUC ne bougeait pas ?* En contrôlant les sorties intermédiaires : 8 coefficients exactement nuls ont révélé des colonnes constantes, puis une exécution anormalement longue a révélé des valeurs standardisées énormes. L'AUC seule ne suffit pas à valider un prétraitement.

**Limites / points ouverts** :
- LightGBM par défaut fait encore mieux (0,690 en E6) : 22 millièmes d'écart, objet de E8.
- `add_indicator` réintroduit le signal « déjà parti » (D66) : à neutraliser dans le test de fuite D32.
- Indicateurs en double (`manquant_hnd_price` et `missingindicator_hnd_price`) : le coefficient se partage entre deux colonnes identiques ; sans effet sur l'AUC, à garder en tête pour l'interprétation.
- Brier et lift calculés sur l'échantillon équilibré : la calibration réelle est traitée en E10.
- La cause exacte du dépassement de 90 minutes n'a pas été mesurée directement (seule la configuration L1, C = 1 l'a été).

**Étape suivante** : E8 — Modèles avancés (arbre, forêt aléatoire, LightGBM, CatBoost) via `build_pipeline`, test de fuite D32 / D66, comparaison appariée avec la LR améliorée.

## Bilan — Étape 8 : Modèles avancés et test de fuite

**Fait** :
- Comparaison de 7 modèles sur les folds figés de E6, via `build_pipeline` et `cross_validate_model` : Dummy, règles, LR améliorée, arbre de décision (profondeur 5), forêt aléatoire (300 arbres, feuilles ≥ 50), LightGBM, CatBoost (catégorielles natives)
- `churn.models.leakage` : `LeakNeutralizer` (imputation par la médiane du fold, en tête de pipeline), masque des clients actifs, AUC par fold sur un sous-ensemble ; option `neutralize_leak` de `build_pipeline`
- Test de fuite « déjà parti » sur les 2 meilleurs modèles, avec la règle de décision fixée avant les résultats
- LR : option `dedupe_missing` (13 indicateurs en double retirés), devenue le réglage par défaut
- `notebooks/05_modeling.ipynb`, 2e partie (sections 6 à 9) ; tests `tests/test_leakage.py` (5 tests)

**Fichiers** :
- Créés : `src/churn/models/leakage.py`, `tests/test_leakage.py`, `reports/figures/05_comparaison_modeles.png`
- Modifiés : `src/churn/models/factory.py` (neutralisation, arbre à profondeur 5, LR sans doublons par défaut), `src/churn/models/preprocessing.py` (`dedupe_missing`, `duplicate_missing_indicators`), `src/churn/charts.py`, `notebooks/05_modeling.ipynb`, `docs/decisions.md`

**Résultats clés** (5 folds, moyenne ± écart-type ; gain fold par fold sur la LR) :

| Modèle | AUC | PR-AUC | lift@10 % | Precision@10 % | Brier | AUC train | Écart train-val. | s / fold | Gain sur la LR | Folds gagnés |
|---|---|---|---|---|---|---|---|---|---|---|
| Dummy | 0,503 ± 0,002 | 0,497 | 1,01 | 49,9 % | 0,497 | 0,499 | −0,003 | 0,0 | −165,1 | 0/5 |
| Règles E4 | 0,617 ± 0,004 | 0,584 | 1,31 | 64,8 % | 0,239 | 0,617 | +0,001 | 8,1 | −50,8 | 0/5 |
| LR améliorée | 0,668 ± 0,004 | 0,648 | 1,49 | 74,0 % | 0,229 | 0,671 | +0,004 | 2,7 | référence | – |
| Arbre (profondeur 5) | 0,639 ± 0,002 | 0,612 | 1,44 | 71,2 % | 0,234 | 0,647 | +0,008 | 2,5 | −28,5 | 0/5 |
| Forêt aléatoire | 0,678 ± 0,006 | 0,660 | 1,52 | 75,1 % | 0,227 | 0,786 | +0,107 | 9,1 | +10,4 | 5/5 |
| **LightGBM** | **0,692 ± 0,004** | 0,677 | 1,57 | 77,9 % | 0,222 | 0,769 | +0,077 | **1,0** | **+24,1** | **5/5** |
| **CatBoost** | **0,693 ± 0,004** | 0,677 | 1,58 | 78,1 % | 0,221 | 0,794 | +0,101 | 48,9 | **+25,2** | **5/5** |

- CatBoost : 48,9 s par fold (maximum 50,3 s), sous la limite de 5 minutes ; itérations non réduites
- Test de fuite : neutralisation −1,5 ± 0,2 millième (LightGBM), +1,0 ± 1,1 (CatBoost) ; sur les clients actifs, −0,6 et +1,6 ; AUC « clients actifs » 2,1 millièmes sous l'AUC globale
- LR sans doublons : 0,6677 contre 0,6676 (écart +0,00 ± 0,04 millième), 189 colonnes au lieu de 202
- Tests : 77 passed ; ruff : OK

**Décisions et justification** : D67 à D71 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Le modèle triche-t-il avec les clients déjà partis ?* Non. Quand on rend l'absence d'usage invisible (imputation par la médiane dans le pipeline), LightGBM ne perd que 1,5 millième d'AUC, moins que la variation entre folds. Le signal existe, mais le modèle n'en dépend pas ; sa performance tient aussi sur les 99,1 % de clients actifs.
- *Pourquoi le boosting bat-il la forêt aléatoire ?* La forêt moyenne des arbres indépendants : elle réduit la variance mais corrige mal les erreurs. Le boosting construit chaque arbre pour corriger les erreurs des précédents : il extrait mieux un signal diffus fait de nombreux petits effets (E5).
- *Pourquoi LightGBM plutôt que CatBoost, alors que CatBoost a la meilleure AUC ?* 1,2 millième d'écart, sous l'écart-type entre folds : ils sont indiscernables. LightGBM est 49 fois plus rapide et surapprend moins, ce qui compte pour le réglage en E9.

**Limites / points ouverts** :
- Surapprentissage des modèles d'arbres (écart train-validation de 0,08 à 0,11) avec leurs réglages par défaut : le réglage en E9 (profondeur, feuilles, taux d'apprentissage, régularisation) devra le réduire.
- La 2e partie du notebook a été exécutée de façon autonome (avec sa propre préparation), puis ajoutée au notebook : c'est aussi le cas de la section « défauts corrigés » de la 1re partie.
- Les clients à usage nul mais mesuré (`mou_Mean` = 0, 79 % de churn) ne sont pas concernés par la neutralisation : ils ont un usage mesuré, donc sont « actifs » au sens du test.
- Brier sur l'échantillon équilibré : la calibration réelle sera traitée en E10.

**Étape suivante** : E9 — Réglage des hyperparamètres des 2 finalistes (LightGBM, LR améliorée) en CV, puis évaluation finale unique sur le jeu de test.

---

# Bilan de partie — B : Modélisation (E5 à E8)

## 1. Avancement par rapport au planning

| Étape | Prévu | Réalisé | Statut |
|---|---|---|---|
| E5 Analyse statistique | Mar 29/09 | 28/09 | En avance |
| E6 Feature engineering | Mar 29/09 | 28/09 | En avance |
| E7 Pipeline + baselines | Mar 29/09 | 28/09 | En avance |
| E8 Modèles avancés + test de fuite | Mar 29/09 | 28/09 | En avance |

**Verdict : environ une journée d'avance.** Les parties A et B sont terminées le 28/09. La partie C (E9 à E13, prévue le 30/09) peut commencer le 29/09.

Ce qui a coûté du temps, et qu'il faut anticiper en partie C :
- les exécutions longues de notebooks (grille L1 de E7 : 15 à 25 minutes, une exécution interrompue au-delà de 90 minutes) ;
- deux défauts de prétraitement découverts puis corrigés en E7.

Pour la suite, les réglages d'hyperparamètres seront lancés en arrière-plan, avec un budget fixé à l'avance.

## 2. Chiffres clés consolidés

**E5 — Analyse statistique**
- 118 tests, 93 significatifs après Holm, **116 effets négligeables**. Seuls `eqpdays` (r = 0,149) et `hnd_price` (r = −0,118) atteignent « faible ».
- `months` : rank-biserial de 0,05 (négligeable), mais 1re en information mutuelle et 28,7 points d'écart entre déciles (relation non monotone).
- Redondance : 60 paires au-delà de |ρ| = 0,9, 17 groupes, **36 variables retirées pour la régression logistique** (VIF maximal ensuite : 6,7).

**E6 — Feature engineering**
- Pas de second pic de churn à 23-24 mois : seul le flag `in_contract_end` est gardé.
- `cycle_engagement` : **+28,2 millièmes pour la régression logistique** (5/5 folds), rien pour LightGBM.
- 5 familles retenues (28 features). `deja_parti` exclue par défaut.

**E7 — Prétraitement et baselines**
- Régression logistique améliorée : **0,668** (log et winsorisation +8,5, splines +3,6 millièmes).
- Grille de C plate : L2 avec C = 0,01 retenu par la règle de l'écart-type.
- Deux défauts corrigés (indicateurs rares effacés par la winsorisation, binaires standardisés) : AUC inchangée, mais 8 colonnes rendues et un ajustement L1 2,5 fois plus rapide.

**E8 — Modèles avancés** : voir le tableau ci-dessous et le test de fuite.

## 3. Tableau comparatif final (5 folds figés, validation croisée sur le train)

| Modèle | AUC | PR-AUC | lift@10 % | Precision@10 % | Brier | Écart train-validation | Temps par fold | Gain sur la LR (millièmes) | Folds gagnés |
|---|---|---|---|---|---|---|---|---|---|
| Dummy | 0,503 ± 0,002 | 0,497 | 1,01 | 49,9 % | 0,497 | −0,003 | 0 s | −165,1 | 0/5 |
| Règles E4 | 0,617 ± 0,004 | 0,584 | 1,31 | 64,8 % | 0,239 | +0,001 | 8 s | −50,8 | 0/5 |
| LR simple (E6) | 0,654 ± 0,004 | 0,626 | 1,40 | 69,4 % | 0,232 | +0,005 | – | −13,5 | 0/5 |
| Arbre de décision (profondeur 5) | 0,639 ± 0,002 | 0,612 | 1,44 | 71,2 % | 0,234 | +0,008 | 2,5 s | −28,5 | 0/5 |
| **LR améliorée** | **0,668 ± 0,004** | 0,648 | 1,49 | 74,0 % | 0,229 | **+0,004** | 2,7 s | référence | – |
| Forêt aléatoire | 0,678 ± 0,006 | 0,660 | 1,52 | 75,1 % | 0,227 | +0,107 | 9,1 s | +10,4 | 5/5 |
| **LightGBM** | **0,692 ± 0,004** | 0,677 | 1,57 | 77,9 % | 0,222 | +0,077 | **1,0 s** | **+24,1** | 5/5 |
| CatBoost | 0,693 ± 0,004 | 0,677 | 1,58 | 78,1 % | 0,221 | +0,101 | 48,9 s | +25,2 | 5/5 |

**Lecture** :
- L'écart-type entre folds est d'environ 4 millièmes : deux modèles séparés de moins de 4 millièmes sont indiscernables (CatBoost et LightGBM).
- La hiérarchie est nette et stable sur les 5 folds : règles < régression logistique < forêt < boosting.
- Le lift@10 % est borné par 2 sur cet échantillon équilibré. Le Brier est calculé avant la correction vers le taux réel (E10).

## 4. Test de fuite « client déjà parti » (D32, D57, D66, D67)

| Modèle | AUC complet (tous / actifs) | AUC neutralisé (tous / actifs) | Perte (tous clients) | Écart-type entre folds |
|---|---|---|---|---|
| LightGBM | 0,6917 / 0,6896 | 0,6902 / 0,6891 | **+1,5 ± 0,2 millième** | 4,3 |
| CatBoost | 0,6929 / 0,6908 | 0,6938 / 0,6924 | −1,0 ± 1,1 millième | 3,8 |

- **Neutralisation** : le bloc d'usage et les `change_*` sont imputés par la médiane du fold, en tête de pipeline. Aucune absence n'est alors observable, ni par un indicateur, ni par un NaN, ni par un ratio.
- **Règle fixée avant les résultats** : si la perte est inférieure à l'écart-type entre folds, on garde la version complète. C'est le cas pour les deux modèles, **la version complète est conservée**.
- **Interprétation** : le signal existe (69 à 76 % de churn chez ces clients), mais il pèse au plus 1,5 millième d'AUC. Le modèle n'en dépend pas, et sa performance tient sur les 99,1 % de clients actifs.

## 5. Finalistes pour E9 et pourquoi

**LightGBM et la régression logistique améliorée (sans doublons).** Le gagnant sera choisi en E9.

- **LightGBM** : la meilleure AUC, à égalité avec CatBoost. Il est **49 fois plus rapide** que CatBoost et surapprend moins (+0,077 contre +0,101), ce qui permet d'explorer plus de configurations au réglage.
- **Régression logistique améliorée** : 25 millièmes d'AUC en moins, mais **aucun surapprentissage** (+0,004), des coefficients **lisibles** et tous cohérents avec l'EDA, et une maintenance simple.
- **Le choix à trancher en E9** : ce que coûtent 25 millièmes d'AUC en clients ciblés à tort, contre la valeur d'une explication directe.
- **Écartés** : la forêt (dominée par le boosting, sans gain de lisibilité), l'arbre de décision (trop faible), et CatBoost (gardé dans le code comme alternative).

## 6. Décisions prises (D47 à D71)

| Thème | Décisions | En une phrase |
|---|---|---|
| Hypothèse métier | D47 | Fenêtre de la cible d'environ 1 mois : taux réel mensuel de 2 % (sensibilité 1-2-3 %) ; le classement ne dépend pas de ce taux |
| Statistiques | D48-D53 | Holm, Fisher pour les petits effectifs, information mutuelle pour les relations non monotones, 36 variables retirées pour la régression logistique |
| Features | D54-D58 | Transformer sans état, 5 familles retenues, `deja_parti` isolée, folds figés |
| Prétraitement | D59-D63 | Tout ce qui est appris est dans le pipeline, règle de l'écart-type pour C, deux défauts corrigés et mesurés |
| Modèles | D64-D66, D68-D71 | `build_pipeline` pour 8 modèles, finalistes LightGBM et régression logistique, test de fuite réussi (D67) |

## 7. Risques pour E9

| Risque | Impact | Parade |
|---|---|---|
| **Surapprentissage du boosting** (écart train-validation de 0,077) | Gain de CV fragile | Régler la profondeur, les feuilles, le taux d'apprentissage et la régularisation ; suivre l'écart train-validation, pas seulement l'AUC |
| **Optimisme du réglage** : les hyperparamètres sont choisis sur les mêmes folds que ceux qui servent à les évaluer | AUC de CV légèrement surestimée | Budget d'essais limité et fixé à l'avance ; jugement final sur le test |
| **Le test n'est lu qu'une fois** | Pas de seconde chance | Écrire le protocole **avant** `load_test(final_evaluation=True)` : modèles réajustés sur tout le train, règle de choix du gagnant fixée à l'avance, les deux finalistes évalués ensemble une seule fois |
| **Bruit du test** (20 000 clients, erreur-type de l'AUC ≈ 0,004) | Un écart de moins de 5 millièmes sur le test n'est pas interprétable | Intervalle de confiance par bootstrap sur le test ; comparaison appariée des deux finalistes |
| **Seuils issus de l'EDA** (11-12 mois, 300 jours) | CV légèrement optimiste pour `cycle_engagement` | Le test, jamais lu, donne la mesure impartiale |
| **Calibration** : les probabilités sont celles d'un échantillon équilibré | Chiffres métier faux sans correction | E10 : calibration dans une CV, puis correction vers le taux réel (D47) |
| **Durée des exécutions** | Débordement de la partie C | Réglage en arrière-plan, nombre d'essais fixé (Optuna, environ 30 essais pour LightGBM) |

## 8. Questions d'oral probables

1. **Comment prouvez-vous que votre modèle ne triche pas ?**
   Trois garde-fous :
   - tout ce qui apprend des données (imputation, écrêtage, encodage, taux des segments) est dans le pipeline et ajusté dans chaque fold ;
   - le jeu de test est verrouillé par le code jusqu'à l'évaluation finale ;
   - le soupçon de fuite « client déjà parti » a été testé en rendant l'absence d'usage invisible : LightGBM ne perd que 1,5 millième d'AUC, moins que la variation entre folds.

2. **Une AUC de 0,69, est-ce bon ?**
   L'AUC est la probabilité qu'un churner tiré au hasard soit mieux classé qu'un non-churner : 0,69 contre 0,50 pour le hasard. Sur ce jeu, c'est un bon résultat : chaque variable a un lien faible avec le churn (corrélation maximale de 0,13), et une règle métier bien construite plafonne à 0,617. En pratique, parmi les 10 % de clients les mieux classés, 78 % sont des churners, contre 50 % en moyenne dans l'échantillon (lift de 1,57).

3. **Pourquoi garder une régression logistique qui fait 25 millièmes de moins ?**
   Parce qu'elle ne surapprend pas (écart train-validation de 0,004 contre 0,077), que chaque coefficient se relie à un constat de l'EDA (fin d'engagement, terminal ancien, baisse d'usage), et qu'elle est simple à expliquer à un métier. Le choix final se fera en E9, en mesurant ce que les 25 millièmes représentent en clients ciblés.

4. **Pourquoi le feature engineering aide-t-il la régression logistique mais pas LightGBM ?**
   Un modèle linéaire ne peut pas représenter un pic : sans l'indicateur `in_contract_end`, il ne voit pas l'effet 11-12 mois, d'où +28 millièmes. Un arbre découpe lui-même les variables aux bons seuils et gère les NaN : les features ne lui apprennent rien de nouveau (+1,8 millième, dans le bruit).

5. **Comment une variable peut-elle être importante avec une corrélation quasi nulle ?**
   La corrélation, même de rang, mesure une tendance monotone. `months` a un pic de churn à 11-12 mois : les deux côtés du pic se compensent, et la corrélation vaut 0,05. L'écart entre déciles (28,7 points) et l'information mutuelle, qui n'est nulle qu'en cas d'indépendance, révèlent cet effet.

## Bilan — Étape 9 : Optimisation, sélection et évaluation finale

**Fait** :
- `churn.models.tune` : réglage de LightGBM par Optuna (50 essais, TPE graine 42, pruning médian) sur les folds figés de E6, sans arrêt précoce sur le fold de validation ; historique `reports/optuna_lightgbm_trials.csv`
- Paramètres réglés et modèle final inscrits dans `configs/config.yaml` (section `models`, écriture ciblée qui conserve les commentaires) ; `build_pipeline` les applique par défaut
- Sélection sur la CV par une règle écrite avant les résultats, décision inscrite (D72, D73) **avant** la lecture du test
- Évaluation finale unique sur le test : AUC avec IC bootstrap (1 000 rééchantillonnages), différences appariées, PR-AUC, Brier, Precision / Recall / lift à 5-10-20 %, gain cumulé et lift, matrice de confusion au top 10 %, AUC clients actifs, comparaison CV / test ; `reports/final_metrics.json`
- `scripts/train.py` (`make train`) → `models/pipeline.joblib` ; `churn.models.model_card` → `models/model_card.md`
- `notebooks/06_evaluation_calibration.ipynb` (1re partie) ; tests `tests/test_e9.py` (4 tests)

**Fichiers** :
- Créés : `src/churn/models/{tune,model_card}.py`, `scripts/train.py`, `notebooks/06_evaluation_calibration.ipynb`, `tests/test_e9.py`, `models/pipeline.joblib`, `models/model_card.md`, `reports/{optuna_lightgbm_trials.csv,selection_grid_cv.csv,final_metrics.json}`, `reports/figures/06_*.png` (3)
- Modifiés : `configs/config.yaml` (section `models`), `src/churn/config.py` (`ModelsConfig`, `write_model_params`, `write_final_model`), `src/churn/models/factory.py` (paramètres lus dans la config), `src/churn/evaluation/metrics.py` (bootstrap, gain, confusion), `src/churn/charts.py`, `docs/decisions.md`

**Résultats clés** :
- Réglage : 42 essais complets, 8 élagués ; meilleure AUC 0,6973 ± 0,0040 (essai 40) mais écart train-validation 0,112 ; **retenu : essai 7**, AUC 0,6942 ± 0,0042, écart **0,0545** (défaut : 0,077), la moins surapprise des 35 configurations à moins d'un écart-type
- Grille (CV) : LightGBM 0,694 / LR 0,668 ; gain **+26,5 ± 3,1 millièmes, 5/5 folds** → **LightGBM** (D73)
- **Test (officiel)** : AUC **0,6955 [0,6881 ; 0,7024]**, PR-AUC 0,683, Brier 0,221, AUC clients actifs 0,693

| k | Precision@k | Recall@k | lift@k |
|---|---|---|---|
| 5 % | 83,3 % | 8,4 % | 1,68 |
| 10 % | 79,2 % | 16,0 % | 1,60 |
| 20 % | 73,6 % | 29,7 % | 1,48 |

- Pour information (test) : LR 0,6686 [0,6610 ; 0,6760], règles 0,6174 ; LightGBM − LR **+26,9 millièmes [+23,0 ; +31,0]**, positif dans 100 % des rééchantillonnages
- Top 10 % : 2 000 clients ciblés, 1 584 churners (79,2 %), 16,0 % des 9 912 churners atteints
- CV / test : **+1,3 millième** (LightGBM), +0,9 (LR) ; lift@10 % 1,57 → 1,60 ; Brier 0,221 → 0,221
- Tests : 81 passed ; ruff : OK

**Décisions et justification** : D72 à D75 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Comment garantir que le test n'a pas influencé le choix ?* La règle de sélection a été écrite avant d'évaluer le modèle réglé ; la décision a été inscrite dans `decisions.md` et la config (16 h 35) avant l'exécution de la section qui lit le test ; le code refuse de lire le test tant que `models.final` n'est pas fixé ; la LR et les règles ne sont évaluées qu'à titre d'information.
- *Pourquoi ne pas avoir pris l'essai à la meilleure AUC ?* Les 35 meilleurs essais sont indiscernables (moins d'un écart-type). Parmi eux, l'essai 7 surapprend deux fois moins (0,055 contre 0,112) pour 3 millièmes d'AUC en moins : un modèle moins surappris est plus robuste face à de nouvelles données. Sur le test, il fait 0,6955, au-dessus même de sa CV.
- *Pourquoi le test est-il si proche de la CV ?* Le train et le test viennent du même échantillon, découpé aléatoirement et de façon stratifiée, et les sources d'optimisme (réglage, seuils d'EDA) étaient faibles : surface de réglage plate, seuils fixés sur 80 000 clients. L'écart de +1,3 millième est sous l'erreur-type du test (3,6).

**Limites / points ouverts** :
- Probabilités non calibrées, issues d'un échantillon équilibré : Brier et Precision@k ne valent que pour cet échantillon (E10).
- Choix de l'essai 7 fait **après** avoir vu les essais (règle D62 appliquée au réglage), mais avant le test.
- Figure de gain cumulé : titre « environ 28 % » pour une valeur exacte de 29,7 % ; figures de gain et de lift enregistrées en PNG, non rendues en interactif dans le notebook (la régénération aurait demandé de relire le test).
- Pas de validation temporelle : la concordance CV / test ne dit rien de la stabilité dans le temps.
- Le notebook 06 a été exécuté en trois sessions (réglage, choix de l'essai, test), assemblées ensuite, pour que la décision précède réellement la lecture du test.

**Étape suivante** : E10 — Calibration (en CV) et correction du prior vers le taux réel mensuel (2 %, sensibilité 1-3 %, D47).

## Bilan — Étape 10 : Calibration et correction vers le taux réel

**Fait** :
- `churn.evaluation.calibration` : `adjust_prior` (formule de Bayes sur les odds), courbe de fiabilité, ECE, `make_calibrated` (`CalibratedClassifierCV`, CV interne à 5 folds, `ensemble=False`), Precision@k attendue en production (repondération des classes)
- Comparaison en CV (folds de E6) du modèle brut, de la calibration sigmoïde et de l'isotonique ; règle de choix fixée avant les résultats ; décision D76 inscrite **avant** la lecture du test
- Rapport de calibration sur le test (2e lecture, sans effet sur les décisions) ; sensibilité au taux réel (1 %, 2 %, 3 %) : distribution des probabilités corrigées, Precision@10 % attendue, vérification de l'AUC
- `churn.models.final.FinalChurnModel` et `make train` → `models/final_model.joblib` ; fiche du modèle complétée (section calibration)
- `notebooks/06_evaluation_calibration.ipynb`, 2e partie (sections 4 à 6) ; tests `tests/test_calibration.py` (6 tests)

**Fichiers** :
- Créés : `src/churn/evaluation/calibration.py`, `src/churn/models/final.py`, `tests/test_calibration.py`, `models/final_model.joblib`, `reports/figures/06_{fiabilite_cv,fiabilite_test,distribution_probas}.png`
- Modifiés : `configs/config.yaml` (`models.calibration: sigmoid`), `src/churn/config.py` (`write_models_field`), `scripts/train.py`, `src/churn/models/model_card.py`, `models/model_card.md`, `reports/final_metrics.json`, `src/churn/charts.py`, `docs/decisions.md`

**Résultats clés** :

| | Brier | ECE | AUC |
|---|---|---|---|
| CV brut | 0,22109 | 0,0129 | 0,69415 |
| CV sigmoïde (retenue) | **0,22093** | **0,0085** | 0,69415 |
| CV isotonique | 0,22100 | 0,0090 | 0,69393 |
| Test brut | 0,22060 | 0,0122 | 0,69547 |
| Test sigmoïde | **0,22042** | **0,0046** | 0,69547 |

- Modèle brut sous-confiant aux extrêmes (décile le plus risqué : 0,766 annoncé, 79,2 % observé) ; la sigmoïde étire les probabilités (0,065 à 0,966) et les ramène sur la diagonale
- Sensibilité (population simulée au taux réel **supposé**) :

| r (hypothèse) | p' médiane | p' 90e centile | Precision@10 % attendue | lift@10 % |
|---|---|---|---|---|
| 1 % par mois | 0,8 % | 1,9 % | 2,8 % | 2,84 |
| **2 % par mois** | **1,6 %** | **3,7 %** | **5,6 %** | **2,80** |
| 3 % par mois | 2,5 % | 5,6 % | 8,3 % | 2,78 |

- AUC identique pour les trois hypothèses (écart 0,0) ; précision annoncée par le modèle 5,5 % contre 5,6 % observée (à 2 %)
- Tests : 87 passed ; ruff : OK

**Décisions et justification** : D76 à D78 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Pourquoi calibrer un modèle qui a déjà une bonne AUC ?* L'AUC mesure le classement, pas la justesse des probabilités. Pour chiffrer une campagne (départs attendus, revenu en jeu), il faut que « 0,7 » veuille dire 70 %. Ici le modèle brut était déjà proche (ECE 0,012), la sigmoïde ramène l'erreur à 0,005 sans toucher au classement.
- *Pourquoi le taux réel ne change-t-il pas les clients ciblés ?* La correction multiplie les odds de tous les clients par la même constante : l'ordre est conservé, donc l'AUC et le top 10 % aussi. L'hypothèse de 2 % ne change que les chiffres absolus : c'est pour cela qu'on peut la présenter avec une sensibilité à 1 % et 3 % sans refaire le modèle.
- *Pourquoi seulement 5,6 % de churners dans le top 10 %, alors qu'on en avait 79 % ?* 79 % était mesuré sur un échantillon où un client sur deux part ; en production, 2 % partent. Cibler les 10 % les plus risqués donne 5,6 %, **2,8 fois** le hasard : pour 1 000 clients contactés, le ciblage atteint environ 56 futurs churners contre 20 au hasard ; les départs évités dépendent du taux de succès de l'offre, à mesurer.
  - *Note (ajoutée en E12)* : 56 pour 1 000 = top 10 % de tout le portefeuille, inactifs compris (performance du modèle) ; le chiffre de campagne officiel est **51 pour 1 000**, inactifs traités à part (E12).

**Limites / points ouverts** :
- Tous les chiffres de production reposent sur l'**hypothèse** de taux réel (D47) et sur la représentativité des classes de l'échantillon ; ils ne sont pas observés.
- Le test a été lu deux fois (E9 : classement ; E10 : calibration) ; modèle et calibration étaient figés avant chaque lecture, aucune décision n'en a dépendu.
- La calibration ne corrige pas une éventuelle dérive dans le temps (pas de validation temporelle).
- Notebook 06, 2e partie : deux sessions (CV, puis test) assemblées, pour que D76 précède réellement la lecture du test.

**Étape suivante** : E11 — Explicabilité SHAP (globale et par client, codes de raisons), sur le modèle final.

## Bilan — Étape 11 : Explicabilité du LightGBM final

**Fait** :
- `churn.explain.shap_utils` : `ShapExplainer` (`TreeExplainer`, log-odds), regroupement des features dérivées sur leur variable d'origine, libellés français, importance globale
- `churn.explain.reason_codes` : top 3 des facteurs d'un client en phrases métier, avec leur sens (augmente / réduit le risque)
- `notebooks/07_explainability.ipynb` : importance par permutation (fold de validation), importance SHAP, beeswarm, dependence plots (top 5, puis ancienneté et âge du terminal regroupés), 3 clients (High, Medium, Low) avec cascade et codes de raisons, confrontation avec E4 et E5
- Tests `tests/test_explain.py` (4 tests : additivité, regroupement, tri et sens des raisons, phrases)

**Fichiers** :
- Créés : `src/churn/explain/{shap_utils,reason_codes}.py`, `notebooks/07_explainability.ipynb`, `tests/test_explain.py`, `reports/figures/07_*.png` (8)
- Modifiés : `src/churn/charts.py` (barres, beeswarm, dependence plots, cascade), `docs/decisions.md`

**Résultats clés** :
- Importance par permutation (baisse d'AUC, fold de validation) : ancienneté 37,7 ; âge du terminal 34,5 ; évolution de l'usage 29,0 ; usage récent 17,7 ; minutes d'appel 13,5 millièmes
- Importance SHAP (variables d'origine) : **âge du terminal 12,2 %**, évolution de l'usage 7,4 %, ancienneté 7,3 %, minutes d'appel 4,7 %, usage récent 4,5 % ; aucune variable au-delà de 13 %
- Formes retrouvées : ancienneté −0,31 (6-9 mois) → **+0,51 (11 mois)**, +0,49 (12 mois) → ≈ 0 ensuite ; âge du terminal −0,31 jusqu'à 299 jours → +0,05 (300-309) → **+0,22 (310-330)** → plateau ≈ +0,20
- `change_mou` : 3,6 % seulement de son importance vient des NaN « déjà parti » ; forte baisse d'usage +0,44, hausse −0,17
- 3 clients : High (97,5e centile, 8,6 % par mois au taux réel supposé ; premier facteur : 0 minute d'appel, +0,68), Medium (2,0 %), Low (0,4 % ; 8 mois d'ancienneté −0,41, terminal de 8 mois −0,38 ; a pourtant churné)
- Surprises (rang E5 → rang SHAP) : appels coupés 103 → 11, durée de résidence 44 → 9, région 39 → 10, classe de crédit 23 → 6
- Tests : 91 passed ; ruff : OK

**Décisions et justification** : D80 à D82 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- *Que dit une valeur SHAP ?* De combien la caractéristique d'un client déplace son score (en log-odds) par rapport au score moyen, **selon le modèle**. Les contributions s'additionnent exactement jusqu'au score du client. Ce n'est pas une cause : agir sur la variable ne garantit pas de changer le risque.
- *Pourquoi les appels coupés sont-ils importants dans le modèle mais pas en E5 ?* Seuls, ils vont avec les gros utilisateurs, qui churnent moins ; à usage égal, plus d'appels coupés va avec plus de churn. Le modèle voit cet effet conditionnel, pas un test univarié.
- *Le modèle a-t-il retrouvé ce que l'EDA montrait ?* Oui : pic de risque à 11-12 mois d'ancienneté et marche vers 300-310 jours d'âge du terminal, sans qu'on lui fournisse ces seuils sous forme de règle (il dispose aussi des variables brutes).

**Limites / points ouverts** :
- SHAP décrit des **associations apprises**, pas des causes ; les codes de raisons ne sont pas des leviers garantis.
- Valeurs SHAP sur l'échelle log-odds du modèle brut ; les probabilités affichées aux utilisateurs sont calibrées et ramenées au taux réel supposé : les deux ne se lisent pas sur la même échelle.
- Le client High a pour premier facteur un usage nul (0 minute) : cas proche des clients « déjà partis », à traiter dans la politique de campagne (E12), car peut-être déjà perdu.
- Variables corrélées (`hnd_price`, `eqpdays`, `phones`) : l'importance se partage entre elles, leur rang individuel est à lire avec prudence.

**Étape suivante** : E12 — Scoring métier et artefacts (niveaux de risque selon la capacité de campagne, actions suggérées, `artifacts/scores.parquet`, `shap.parquet`, `kpis.json`), avec un taux de succès de l'offre présenté comme hypothèse (D79).

## Bilan — Étape 12 : Risk scoring et artefacts

**Fait** :
- Scores sans fuite pour les 100 000 clients :
  - train : **hors fold**, avec les mêmes 5 folds et un modèle final réentraîné et recalibré dans chaque fold ;
  - test : **modèle final livré**.
- `churn.business.scoring` :
  - catégorie Inactif (D86) ;
  - lift par bande sur le portefeuille repondéré au taux réel ;
  - seuils High / Medium / Low (capacité 10 %, lift de bande > 1,2) ;
  - graphique justificatif.
- `churn.business.actions` : familles actionnables / contexte (D83-D85), 3 raisons actionnables, contexte, action selon le facteur dominant.
- `churn.business.campaign` :
  - revenu en jeu = probabilité corrigée × `rev_Mean` ;
  - tableau de campagne (5, 10, 20 %), avec les inactifs sur une ligne à part ;
  - synthèses par niveau, segment et action.
- `scripts/build_artifacts.py` (`make artifacts`, 3 minutes) :
  - `artifacts/scores.parquet` (100 000 × 34) ;
  - `artifacts/shap.parquet` (800 000 lignes, 8 facteurs par client) ;
  - `artifacts/kpis.json`.
- `notebooks/08_business_analysis.ipynb` : réponses chiffrées aux questions métier, illustrations sous hypothèse de taux de succès, sensibilité 1-3 %.
- `tests/test_business.py` : 6 tests.

**Fichiers** :
- Créés : `src/churn/business/{scoring,actions,campaign}.py`, `scripts/build_artifacts.py`, `notebooks/08_business_analysis.ipynb`, `tests/test_business.py`, `artifacts/{scores.parquet,shap.parquet,kpis.json}`, `reports/tier_bands.csv`, `reports/figures/08_{tiers_lift,actions,raisons_high,campagne}.png`
- Modifiés :
  - `configs/config.yaml` et `src/churn/config.py` : section `business.campaign` ;
  - `src/churn/evaluation/calibration.py` : `population_weights` ;
  - `src/churn/explain/shap_utils.py` : libellés ;
  - `src/churn/charts.py` : `tier_lift_chart`, `grouped_bar_chart` ;
  - `docs/decisions.md`.

**Résultats clés** (portefeuille réel de 100 000 clients, taux réel **supposé** de 2 % par mois) :
- **Contrôles** :
  - AUC hors fold 0,6941 (CV E9 : 0,6942), AUC test 0,6955 ;
  - churn observé par niveau identique sur le train et le test (High 72,3 % / 73,0 %, Medium 59,0 % / 58,6 %, Low 37,6 % / 37,3 %) ;
  - 2 002 départs attendus au total pour 2 000 supposés.
- **Seuils** : High si proba calibrée ≥ 0,6484, Medium si ≥ 0,5327. Lift des bandes : 3,11 et 2,13 (High), de 1,78 à 1,29 (Medium), puis 1,13 à 30-35 %.
- **Niveaux** :

  | Niveau | Clients | Part du portefeuille | Risque mensuel moyen | Part des départs attendus | Revenu en jeu |
  |---|---|---|---|---|---|
  | High | 9 876 | 9,9 % | 5,1 % | 25 % | 26 % |
  | Medium | 19 836 | 19,8 % | 2,9 % | 29 % | 29 % |
  | Low | 69 375 | 69,4 % | 1,2 % | 43 % | 45 % |
  | Inactif | 913 | 0,9 % | 7,2 % | 3 % | 1 % |

- **Campagne** :

  | Capacité | Churners attendus | Au hasard | Facteur | Revenu en jeu |
  |---|---|---|---|---|
  | Top 5 % des actifs | 308 | 100 | 3,1 | 17 700 $ par mois |
  | Top 10 % des actifs | 511 | 200 | 2,6 | 30 100 $ par mois |
  | Top 20 % des actifs | 831 | 400 | 2,1 | 48 800 $ par mois |

  - Au top 10 %, cela fait environ **51 futurs churners pour 1 000 clients contactés, contre 20 au hasard**. Les départs évités dépendent du taux de succès de l'offre, à mesurer.
  - Contrôle : 515 churners observés (historique repondéré) contre 511 attendus.
  - Revenu mensuel en jeu du portefeuille : **116 000 $**, soit 2,0 % de la facture mensuelle.
- **Actions des clients High** (échantillon) : offre adaptée à l'usage 7 030, réengagement 5 639, renouvellement du terminal 3 374, changement de forfait 1 142, multi-lignes 251, geste réseau 36. Les inactifs (1 972 clients de l'échantillon) reçoivent « vérifier la ligne / reconquête ».
- **Profil High** (médianes) : usage −45 minutes par mois, terminal de 377 jours à 60 $, 37 % en fin d'engagement (4 % chez les Low).
- **Segments** :
  - clients anciens à terminal ancien : risque le plus élevé (2,7 %, 16 % de High) ;
  - gros consommateurs en baisse d'usage : 32 % du revenu en jeu pour 21 % du portefeuille ;
  - lignes secondaires : 5,4 % d'inactifs.
- **Sensibilité au taux réel** : le facteur par rapport au hasard est stable (2,58 / 2,56 / 2,53 à 1 %, 2 % et 3 %), les montants sont presque proportionnels au taux (revenu en jeu de 58 000 $ à 174 000 $ par mois).
- **Tests** : 97 passed ; ruff : OK.

**Décisions et justification** : D83 à D90 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- **Pourquoi des scores hors fold pour le train ?** Un client ne doit jamais être noté par un modèle qui l'a vu, sinon son score est trop optimiste. L'AUC hors fold (0,694) retrouve celle de la CV, et celle du test celle de l'évaluation finale.
- **Pourquoi repondérer ?** Le jeu contient 50 % de churners, un vrai portefeuille environ 2 %. Sans repondération, « les 10 % les plus risqués » seraient plus extrêmes que dans la réalité et les chiffres de campagne seraient gonflés.
- **Pourquoi le lift de bande plutôt que le lift cumulé ?** Le lift cumulé à x % mélange les clients High du haut de la liste avec ceux situés à x % : il aurait classé Medium des clients moins risqués que la moyenne.
- **Qu'est-ce que le revenu en jeu ?** Le revenu qu'on s'attend à perdre sans action (probabilité × facture). Ce n'est pas un gain : le gain dépend du taux de succès de l'offre, inconnu.

**Limites / points ouverts** :
- Le taux réel de 2 % est une hypothèse. Les montants y sont presque proportionnels ; les niveaux et le classement, non.
- Les seuils sont des probabilités calibrées fixes. Sur un vrai portefeuille, la part de clients High sera proche de 10 % seulement si sa distribution de risque ressemble à celle du portefeuille repondéré : à surveiller en production.
- La définition des inactifs est stricte (0 minute ou usage non mesuré). 673 clients High ont moins de 10 minutes par mois et sont probablement proches de « déjà partis ».
- Les raisons et les actions sont des associations apprises (SHAP), pas des causes. Aucune action n'a été testée : il faut un groupe témoin pour mesurer le taux de succès.
- Il n'y a pas de coût ni de budget, donc pas de capacité optimale : la capacité est un choix métier.

**Étape suivante** : E13 — API FastAPI (routers fins sur `churn.services` : fiche client, liste filtrée par niveau et segment, KPI, tableau de campagne, scoring d'un nouveau client avec raisons et action).

## Bilan — Étape 13 : Couche de services et API FastAPI

**Fait** :
- **Préalables** :
  - lignes réelles par niveau comparées aux effectifs repondérés (tableau ci-dessous) ;
  - note « 56 pour 1 000 » ajoutée en E10 (notebook 06, cellule 47, et bilans), chiffres de E10 inchangés ;
  - `n_rows` / `n_portfolio_equiv` généralisés ;
  - poids de portefeuille stocké par ligne ;
  - note d'hypothèse dans `kpis.json`.
- **`churn.services`** (fonctions pures sur les artefacts en cache) :
  - `store.py` : chargement unique, tranches d'affichage ;
  - `filters.py` : 7 dimensions filtrables ;
  - `analytics.py` : `get_kpis`, `get_filter_options`, `get_risk_distribution`, `get_segments`, `get_heatmap`, `get_drivers` ;
  - `campaign.py` : `simulate_campaign` ;
  - `customers.py` : `list_customers`, `get_customer`, `explain_customer`.
- **`churn.business.campaign`** : `portfolio_weights`, `campaign_curve` (courbe vectorisée en un seul tri), champs `n_rows` / `n_portfolio_equiv`.
- **Artefacts** : nouvel artefact `shap_values.parquet` (100 000 × 97 contributions) ; variables des raisons et du contexte ajoutées à `scores.parquet`.
- **API** : `api/schemas.py` (36 schémas pydantic, unités et natures d'effectifs documentées), `api/dependencies.py` (filtres en paramètres de requête), `api/main.py`.
- **Routers** : 8 routers (health, kpis, filters, risk, segments, drivers, campaign, customers), 11 chemins sous `/api`, CORS pour `http://localhost:5173`, 404 et 422 propres.
- **Tests** : `tests/test_api.py` (22 tests) et 1 test ajouté à `tests/test_business.py`.

**Fichiers** :
- Créés : `src/churn/services/{store,filters,analytics,campaign,customers}.py`, `api/dependencies.py`, `api/routers/{health,kpis,filters,risk,segments,drivers,campaign,customers}.py`, `tests/test_api.py`, `artifacts/shap_values.parquet`
- Modifiés :
  - `api/{main,schemas}.py` (étaient vides), `src/churn/services/__init__.py` ;
  - `src/churn/business/{campaign,actions}.py`, `scripts/build_artifacts.py` ;
  - `tests/test_business.py`, `notebooks/08_business_analysis.ipynb` (réexécuté) ;
  - `notebooks/06_evaluation_calibration.ipynb` (note), `docs/decisions.md`.

**Résultats clés** :
- **Lignes réelles et équivalent portefeuille** :

  | Niveau | `n_rows` (base) | `n_portfolio_equiv` (estimation, 2 %) |
  |---|---|---|
  | High | 17 472 (17,5 %) | 9 876 (9,9 %) |
  | Medium | 24 122 (24,1 %) | 19 836 (19,8 %) |
  | Low | 56 434 (56,4 %) | 69 375 (69,4 %) |
  | Inactif | 1 972 (2,0 %) | 913 (0,9 %) |
  | Total | 100 000 | 100 000 |

- **`GET /api/kpis`** :
  - 2 002 churners attendus, 116 162 $ par mois en jeu (2,0 % de la facture) ;
  - campagne officielle : 17 640 lignes ciblées ≈ 10 000 clients de portefeuille, **51,1 churners pour 1 000 contactés contre 20**, facteur 2,55 ;
  - AUC hors fold 0,6941, test 0,6955.
- **`GET /api/campaign/simulate`** (10 %, succès supposé 20 %, coût supposé 5 $) :
  - 511 churners attendus (515 observés au contrôle) ;
  - 102 départs évités (hypothèse) et 6 012 $ par mois préservés (hypothèse) ;
  - coût 50 002 $, solde sur 1 mois −43 990 $ ; le solde dépend fortement de l'horizon et du coût supposés.
  - Inactifs à part : 1 972 lignes ≈ 913 clients.
- **`GET /api/customers/1072931`** : High, p = 6,4 % par mois, action « Offre de réengagement ». Raisons : fin d'engagement à 12 mois (+0,82), terminal à 30 $ (+0,18), 55 minutes par mois (+0,14). Contexte : classe de crédit AA, région Los Angeles.
- **Temps de réponse** (troisième appel, `make api`) : de 5 à 177 ms, toutes sous l'objectif de 300 ms (fiche client 7 ms, simulateur avec courbe 139 ms, distribution 177 ms).
- **Documentation** : `/docs` → 200, OpenAPI 3.1 avec 11 chemins et 36 schémas.
- **Tests** : 120 passed ; ruff : OK.

**Décisions et justification** : D91 à D95 dans `docs/decisions.md`.

**À savoir défendre à l'oral** :
- **Pourquoi deux effectifs ?** La base contient environ 50 % de churners, un vrai portefeuille environ 2 %. Une liste montre les 17 472 clients High de la base ; un KPI estime qu'un portefeuille réel de 100 000 clients en compterait environ 9 876. Les deux sont justes, à condition de dire lequel on affiche.
- **Pourquoi l'API ne charge-t-elle pas le modèle ?** Tous les scores et toutes les explications sont précalculés et sans fuite (E12) : l'API ne fait que filtrer et agréger, d'où des réponses en quelques dizaines de millisecondes.
- **Pourquoi le simulateur ne donne-t-il pas de gain par défaut ?** Parce que le taux de succès de l'offre et son coût sont inconnus : c'est l'utilisateur qui les saisit, et la réponse les renvoie comme hypothèses.

**Limites / points ouverts** :
- Pas de scoring d'un nouveau client en direct (non demandé en E13) : les 100 000 clients sont précalculés. Un endpoint de scoring chargerait `final_model.joblib`.
- Le solde du simulateur compare un revenu mensuel à un coût ponctuel : l'horizon (paramètre) est une hypothèse de plus, à afficher dans le front.
- Pas d'authentification (démonstration locale). Les données exposées sont celles du jeu de données public.
- Le cache se charge au démarrage (environ 1 s) : après `make artifacts`, il faut redémarrer l'API (ou laisser `--reload` s'en charger).

**Étape suivante** : E14 — squelette du frontend (Vite + React + TypeScript strict, Mantine, TanStack Query, client API généré depuis l'OpenAPI).

---

# Bilan de partie — C : Rendre utile + API (E9 à E13)

## 1. Avancement par rapport au planning

| Étape | Prévu | Réalisé | Statut |
|---|---|---|---|
| E9 Réglage, sélection, test final | Mer 30/09 | 30/09 | Dans les temps |
| E10 Calibration + taux réel | Mer 30/09 | 30/09 | Dans les temps |
| E11 Explicabilité SHAP | Mer 30/09 | 30/09 | Dans les temps |
| E12 Scoring métier + artefacts | Mer 30/09 | 30/09 | Dans les temps |
| E13 Services + API FastAPI | Mer 30/09 | 30/09 | Dans les temps |

**Verdict : partie C terminée le jour prévu.** La partie D (frontend et assistant, jeudi 01/10) peut démarrer à l'heure. La finalisation reste prévue le vendredi 02/10 au matin.

Ce qui a coûté du temps :
- le réglage Optuna (50 essais), lancé en arrière-plan ;
- `make artifacts`, qui prend 3 à 8 minutes pour les scores hors fold et le SHAP des 100 000 clients ;
- les notebooks 06, exécutés en plusieurs sessions pour que chaque décision précède réellement la lecture du test ;
- deux corrections demandées en cours de route : la formulation des départs évités (D79) et les deux natures d'effectifs (D92).

## 2. Chiffres clés consolidés

**E9 — Réglage et test final**
- Optuna : 50 essais (42 complets). L'**essai 7** est retenu par la règle de l'écart-type : AUC 0,6942 ± 0,0042 en CV, écart train-validation 0,0545 (contre 0,112 pour le meilleur essai en AUC).
- **Test : AUC 0,6955 [0,6881 ; 0,7024]**. LightGBM fait +26,9 millièmes de plus que la régression logistique [+23,0 ; +31,0]. L'écart entre CV et test est de +1,3 millième.

**E10 — Calibration**
- Calibration sigmoïde, choisie en CV : ECE 0,0129 → 0,0085 en CV, 0,0122 → 0,0046 sur le test. AUC inchangée.
- Correction vers le taux réel **supposé** de 2 % : Precision@10 % attendue de 5,6 % (lift 2,80), sans changer le classement.

**E11 — Explicabilité**
- Trois facteurs dominent, quelle que soit la méthode : **âge du terminal** (12,2 % de l'importance SHAP), **évolution de l'usage** (7,4 %) et **ancienneté** (7,3 %).
- Formes de l'EDA retrouvées : pic de risque à 11-12 mois (+0,51 en log-odds) et marche entre 300 et 310 jours d'âge du terminal.
- Codes de raisons en phrases métier.

**E12 — Scoring métier**
- Scores sans fuite : AUC 0,6941 hors fold, 0,6955 sur le test.
- Niveaux : High 10 %, Medium jusqu'à 30 %, inactifs à part.
- **51 futurs churners pour 1 000 clients contactés, contre 20 au hasard**.
- 116 000 $ de revenu mensuel en jeu pour 100 000 clients.

**E13 — Services et API**
- 11 endpoints, 36 schémas, réponses de 5 à 177 ms.
- Deux effectifs nommés partout : `n_rows` (base) et `n_portfolio_equiv` (estimation).
- 120 tests.

## 3. Fiche du modèle final

| Rubrique | Contenu |
|---|---|
| **Tâche** | Probabilité qu'un client parte dans la fenêtre de la cible (environ 1 mois, départ entre J+31 et J+60, D47) |
| **Données** | 100 000 clients Cell2Cell ; train 80 000, test 20 000 (split stratifié, graine 42, fait avant l'EDA) ; 49,56 % de churners (échantillon équilibré) |
| **Variables** | Colonnes brutes nettoyées par règles fixes + 5 familles de features (cycle d'engagement, tendance d'usage, forfait, compte et terminal, indicateurs de manquants) ; exclues : `Customer_ID`, `ethnic`, `churn` ; 97 variables d'origine après regroupement SHAP |
| **Modèle** | LightGBM dans un pipeline sklearn (`FeatureBuilder` → modèle) |
| **Calibration** | Sigmoïde (Platt), `CalibratedClassifierCV` avec CV interne à 5 folds, `ensemble=False` (un seul modèle) |
| **Correction du prior** | p' = p·(r/s) / [p·(r/s) + (1 − p)·((1 − r)/(1 − s))], avec s = 0,4956 et r = **2 % par mois (hypothèse)**, sensibilité 1-3 % |
| **Fichiers** | `models/pipeline.joblib` (brut), `models/final_model.joblib` (calibré + taux réel), `models/model_card.md` ; `make train` ne lit jamais le test |

**Paramètres** (Optuna, essai 7, `configs/config.yaml`) :

| num_leaves | max_depth | min_child_samples | learning_rate | n_estimators | subsample (freq 1) | colsample_bytree | reg_alpha | reg_lambda |
|---|---|---|---|---|---|---|---|---|
| 21 | 5 | 113 | 0,015253 | 850 | 0,537275 | 0,992132 | 1,22738 | 0,006235 |

**Métriques** :

| | AUC | PR-AUC | Brier | lift@10 % | Precision@10 % | Autre |
|---|---|---|---|---|---|---|
| CV (5 folds) | 0,6942 ± 0,0042 | – | 0,2211 | 1,57 | – | écart train-validation 0,0545 |
| Hors fold (E12, 80 000) | 0,6941 | – | – | 1,57 | – | contrôle de fuite |
| **Test (20 000)** | **0,6955 [0,6881 ; 0,7024]** | 0,683 | 0,2206 | 1,60 | 79,2 % | AUC clients actifs 0,693 ; LR 0,6686 ; règles 0,6174 |
| Test, calibré | 0,6955 | – | 0,2204 | – | – | ECE 0,0122 → 0,0046 |
| Test, au taux réel supposé de 2 % | 0,6955 | – | – | 2,80 | 5,6 % (attendue) | précision annoncée 5,5 %, observée 5,6 % |

Precision@k sur le test (échantillon) : 83,3 % à 5 %, 79,2 % à 10 %, 73,6 % à 20 %.

**Niveaux de risque** (seuils sur la probabilité calibrée, fixés sur les scores hors fold du train) :

| Niveau | Règle | `n_rows` (base) | `n_portfolio_equiv` (estimation, 2 %) | Risque mensuel moyen | Churn observé dans la base |
|---|---|---|---|---|---|
| High | p ≥ 0,6484 (10 % du portefeuille) | 17 472 | 9 876 | 5,1 % | 72,4 % |
| Medium | p ≥ 0,5327 (lift de bande > 1,2, jusqu'à 30 %) | 24 122 | 19 836 | 2,9 % | 58,9 % |
| Low | le reste | 56 434 | 69 375 | 1,2 % | 37,5 % |
| Inactif | 0 minute ou usage non mesuré | 1 972 | 913 | 7,2 % | 77,8 % |

Le churn observé par niveau est le même sur le train et le test (High 72,3 % contre 73,0 %).

**Chiffre officiel de campagne (D91)** :
- Ciblage des 10 % de clients actifs les plus risqués : **environ 51 futurs churners pour 1 000 clients contactés, contre 20 au hasard** (facteur 2,55), soit 30 059 $ de revenu mensuel en jeu pour un portefeuille de 100 000 clients.
- Les départs évités dépendent du taux de succès de l'offre, à mesurer.
- Le « 56 pour 1 000 » de E10 est la performance du modèle, inactifs compris.

**Usages et limites** : ce modèle sert à **classer** les clients à contacter, pas à prédire un départ certain : au taux supposé de 2 %, seuls 1,7 % des clients dépassent 10 % de risque mensuel, et le maximum est de 39,5 %. Les raisons SHAP décrivent le modèle, pas des causes. Il n'y a pas de validation temporelle, et les chiffres absolus dépendent de l'hypothèse de taux réel.

## 4. Décisions prises (D72 à D95)

| Thème | Décisions | En une phrase |
|---|---|---|
| Sélection | D72-D75 | Règle écrite avant les résultats ; essai 7 retenu par la règle de l'écart-type ; LightGBM choisi en CV avant toute lecture du test ; une seule évaluation finale |
| Calibration et hypothèse | D76-D79 | Sigmoïde choisie en CV ; correction du prior vers 2 % (hypothèse) ; modèle livré `final_model.joblib` ; aucun départ évité sans taux de succès supposé |
| Explicabilité | D80-D82 | TreeExplainer en log-odds, calculé sur le train ; features dérivées regroupées sur leur variable d'origine ; 3 codes de raisons en phrases métier |
| Actionnable ou contexte | D83-D86 | Raisons et actions uniquement sur les facteurs actionnables ; ancienneté actionnable seulement à 11-12 mois ; inactifs à part (vérifier la ligne / reconquête) |
| Scoring | D87-D90 | Scores hors fold pour le train ; niveaux fixés sur le portefeuille repondéré (capacité 10 %, lift de bande > 1,2) ; revenu en jeu = p' × facture, sans coût |
| API | D91-D95 | 51 pour 1 000 officiel ; `n_rows` et `n_portfolio_equiv` ; services purs et API fine ; simulateur sous hypothèses saisies par l'utilisateur ; tranches fixes et drill-down |

**Lectures du test** :
- **Évaluation**, deux fois : en E9 (classement) et en E10 (rapport de calibration). Le modèle et la calibration étaient figés avant chaque lecture.
- **Notation**, à partir de E12 : les clients du test sont notés comme de nouveaux clients, avec des seuils fixés sur le train.

Aucune décision n'a dépendu du test.

## 5. Risques pour la partie D (frontend et assistant)

| Risque | Impact | Parade |
|---|---|---|
| **Confusion entre les deux effectifs** dans le front (17 472 lignes High contre environ 9 876 en équivalent portefeuille) | Chiffres contradictoires à l'écran, perte de crédibilité à l'oral | Types générés depuis l'OpenAPI (noms `n_rows` et `n_portfolio_equiv`) ; libellés fixes « clients dans la base » et « équivalent portefeuille (estimation, 2 %) » ; note d'hypothèse visible sur les KPI |
| **Départs évités présentés comme des résultats** (simulateur, assistant) | Contradiction avec D79 | Curseur de taux de succès étiqueté « hypothèse » ; coût et solde masqués sans coût saisi ; l'assistant répète la formulation officielle |
| **Horizon du solde** : revenu mensuel comparé à un coût ponctuel | Solde négatif mal interprété (−43 990 $ à 1 mois pour un coût supposé de 5 $) | Afficher l'horizon (paramètre) à côté du solde ; le laisser au choix de l'utilisateur |
| **Assistant qui calcule ou invente** | Chiffres faux ou non traçables | Outils de `churn.assistant.tools` qui encapsulent `churn.services` uniquement ; 5 appels maximum ; réponses citant l'outil et les hypothèses |
| **Fournisseur de LLM non choisi** (point ouvert du contexte) | Blocage de E16 | Choisir avant E16 ; clé uniquement dans `.env`, jamais dans le front |
| **Journée D chargée** (4 étapes en un jour) | Retard sur le vendredi | Pages construites sur des endpoints déjà testés ; priorité : vue d'ensemble, liste et fiche client, simulateur ; les finitions ensuite |
| **Artefacts reconstruits alors que l'API tourne** | Données en cache périmées | Redémarrer l'API après `make artifacts` (vérifier `/api/health`, date des artefacts) |
| **Lecture causale des raisons SHAP** | Promesse d'effet d'une action | Mention « selon le modèle » sur la fiche client et dans l'assistant ; action = suggestion, pas garantie |

## 6. Questions d'oral probables

1. **Comment êtes-vous sûrs que le test n'a pas influencé vos choix ?**
   - Toutes les décisions (modèle final, essai 7, calibration sigmoïde, seuils des niveaux) ont été prises en validation croisée sur le train, et inscrites dans `decisions.md` et la config **avant** chaque lecture du test.
   - Le code refuse de lire le test sans `final_evaluation=True`.
   - Le test a été lu deux fois pour évaluer (classement en E9, calibration en E10), puis seulement pour noter des clients en E12.
   - Résultat : le test (0,6955) est dans l'intervalle de la CV (0,6942 ± 0,0042). Il n'y a pas d'optimisme visible.

2. **Vous annoncez 79 % de churners dans le top 10 %, puis 5,6 %, puis 51 pour 1 000. Lequel est vrai ?**
   Les trois, pour trois questions différentes :
   - **79 %** : sur l'échantillon, où un client sur deux part ;
   - **5,6 %** : dans un portefeuille réel au taux supposé de 2 %, on repondère les classes, et le top 10 % en contient 2,8 fois plus que le hasard. C'est la performance du modèle ;
   - **51 pour 1 000** : le chiffre de **campagne**, une fois les inactifs retirés de l'offre, qui sont traités à part.

   Dans les trois cas, ce sont des churners **atteints**, pas des départs évités : ceux-ci dépendent du taux de succès de l'offre, à mesurer.

3. **À quoi sert la calibration, et que se passe-t-il si le vrai taux n'est pas 2 % ?**
   - La calibration fait que « 0,7 » signifie bien 70 % sur l'échantillon (ECE de 0,012 à 0,005). La correction du prior ramène ensuite la probabilité au taux réel.
   - Les deux transformations sont **monotones** : le classement, l'AUC et les clients ciblés ne changent pas.
   - Si le vrai taux est de 1 % ou de 3 %, les montants (churners attendus, revenu en jeu) sont presque proportionnels, mais le facteur par rapport au hasard reste à 2,5-2,6. On présente donc toujours l'hypothèse et sa sensibilité.

4. **Comment avez-vous fixé les niveaux High, Medium et Low ?**
   - **High** = la capacité de la campagne (10 % du portefeuille), un choix métier en config.
   - **Medium** = les bandes de 5 % suivantes, tant que leur taux de churn reste supérieur à 1,2 fois la moyenne. Il s'arrête à 30 %, car la bande 30-35 % tombe à 1,13.
   - On utilise le lift **de la bande** et pas le lift cumulé, qui aurait étendu Medium jusqu'à 75 % en profitant des clients High.
   - Le tout est calculé sur des scores hors fold, repondérés au portefeuille réel, et vérifié sur le test : même churn observé par niveau.

5. **Le modèle dit que la fin d'engagement augmente le risque : une offre de réengagement va-t-elle retenir ces clients ?**
   - On ne le sait pas. SHAP explique **le modèle** : selon lui, être à 11-12 mois d'ancienneté est associé à un risque plus élevé (+0,51 en log-odds). Ce n'est pas une preuve qu'agir sur ce facteur réduit le départ.
   - C'est pourquoi les raisons affichées ne portent que sur des facteurs **actionnables**, l'action est une **suggestion**, et le simulateur demande un taux de succès **supposé**.
   - La vraie réponse viendra d'un test avec un groupe témoin.
   - Même prudence pour les clients inactifs (0 minute) : le modèle les voit très risqués (7,2 %), mais ils sont peut-être déjà perdus, d'où une action distincte (vérifier la ligne, reconquête).
