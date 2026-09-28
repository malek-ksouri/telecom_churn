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
