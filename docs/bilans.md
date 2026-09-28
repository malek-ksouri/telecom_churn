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
