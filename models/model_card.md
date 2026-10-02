# Fiche du modèle de churn

*Générée le 02/10/2026 par `scripts/train.py`.*

## Modèle

- **Type** : LightGBM (boosting de gradient) (`build_pipeline("lightgbm")`).
- **Usage prévu** : classer les clients par risque de départ pour cibler une campagne de rétention à budget limité. Aide à la décision, pas décision automatique.
- **Sortie** : probabilité calibrée sur l'échantillon équilibré (sert au classement) et probabilité mensuelle ramenée au taux de churn réel **supposé** (sert aux chiffres métier).

### Hyperparamètres

| Paramètre | Valeur |
|---|---|
| `num_leaves` | 21 |
| `max_depth` | 5 |
| `min_child_samples` | 113 |
| `learning_rate` | 0,015253 |
| `n_estimators` | 850 |
| `subsample` | 0,537275 |
| `colsample_bytree` | 0,992132 |
| `reg_alpha` | 1,227380 |
| `reg_lambda` | 0,006235 |
| `subsample_freq` | 1 |

## Données

- **Entraînement** : `data/processed/train.parquet`, 80000 clients (80 % du CSV, split stratifié, graine 42).
- **Test** : `data/processed/test.parquet`, 20 000 clients, jamais utilisé pour un choix : lu pour l'évaluation finale (classement en E9, calibration en E10, modèle figé avant chaque lecture), puis pour noter ses clients comme de nouveaux clients (E12).
- **Cible** : `churn` = 1 si le client part dans la fenêtre d'observation, soit environ 1 mois (départ entre J+31 et J+60). Échantillon **équilibré** (49,6 % de churners), non représentatif du taux réel (hypothèse : 2 % par mois).
- **Features** : variables d'origine nettoyées + familles `cycle_engagement, tendance_usage, forfait, compte_terminal, indicateurs_manquants`.
- **Variables exclues** : `Customer_ID`, `churn`, `ethnic` (identifiant, cible, et `ethnic` pour raison éthique et réglementaire).

## Performance

### Validation croisée (5 folds, train)

| Modèle | AUC | Écart-type | Écart train-validation | Brier | lift@10 % |
|---|---|---|---|---|---|
| LightGBM par défaut (E8) | 0,6917 | 0,0043 | 0,0772 | 0,2216 | 1,572 |
| LightGBM meilleure AUC (essai 40) | 0,6973 | 0,0040 | 0,1118 | 0,2200 | 1,583 |
| LR améliorée | 0,6677 | 0,0038 | 0,0038 | 0,2286 | 1,494 |
| LightGBM retenu (essai 7) | 0,6942 | 0,0042 | 0,0545 | 0,2211 | 1,570 |

### Jeu de test (évaluation unique)

| Modèle | AUC [IC 95 %] | PR-AUC | Brier | lift@10 % | Precision@10 % | AUC clients actifs |
|---|---|---|---|---|---|---|
| LightGBM (modèle final) | 0,6955 [0,6881 ; 0,7024] | 0,6827 | 0,2206 | 1,598 | 0,792 | 0,6932 |
| LR améliorée (information) | 0,6686 [0,6610 ; 0,6760] | 0,6529 | 0,2281 | 1,515 | 0,751 | 0,6667 |
| Règles E4 (information) | 0,6174 [0,6093 ; 0,6248] | 0,5876 | 0,2390 | 1,329 | 0,658 | 0,6179 |

## Calibration et taux réel

- **Méthode** : calibration sigmoid (`CalibratedClassifierCV`, CV interne à 5 folds sur le train), choisie en CV avant la lecture du test (E10).
- **Test** : Brier 0,2206 (brut) → 0,2204 (calibré) ; ECE 0,0122 → 0,0046.
- **Correction du prior** : p' = p·(r/s) / [p·(r/s) + (1 − p)·((1 − r)/(1 − s))], s = 0,4956 (échantillon), r = taux réel **supposé**. Transformation monotone : l'AUC et le classement sont inchangés.
- **Modèle livré** : `models/final_model.joblib` (`FinalChurnModel` : probabilité sur l'échantillon pour le classement, probabilité au taux réel pour les chiffres métier).

| Taux réel (hypothèse) | Probabilité moyenne corrigée | Precision@10 % attendue | Lift@10 % attendu |
|---|---|---|---|
| 1 % par mois | 0,0100 | 0,028 | 2,83 |
| 2 % par mois | 0,0200 | 0,056 | 2,80 |
| 3 % par mois | 0,0300 | 0,083 | 2,78 |

- **Lecture** : à 2 % de churn mensuel (hypothèse), le top 10 % de **tous** les clients contient environ 56 futurs churners pour 1 000, contre 20 au hasard : c'est la performance du modèle. Le chiffre de **campagne** (inactifs exclus de l'offre) est de 51 pour 1 000 (section suivante). Les départs évités dépendent du taux de succès de l'offre, à mesurer (il n'est pas dans les données).

## Usage métier (niveaux de risque et campagne)

- **High** : probabilité calibrée ≥ 0,6484 (capacité de campagne : 10 % du portefeuille). **Medium** : ≥ 0,5327 (bandes de 5 % dont le lift reste > 1,2). **Low** : le reste. **Inactif** (0 minute ou usage non mesuré) : à part, action « vérifier la ligne / reconquête », jamais ciblé par une offre de fidélisation.
- Seuils fixés sur les scores hors fold du train, portefeuille repondéré au taux réel supposé.
- Deux effectifs : **clients dans la base** (lignes réelles, environ 50 % de churners) et **estimation portefeuille** (équivalent dans un portefeuille réel de 100 000 clients au taux supposé).

| Niveau | Clients dans la base | Estimation portefeuille | Risque mensuel moyen (taux supposé) | Churn observé dans la base |
|---|---|---|---|---|
| High | 17 472 | 9 876 | 5,1 % | 72,4 % |
| Medium | 24 122 | 19 836 | 2,9 % | 58,9 % |
| Low | 56 434 | 69 375 | 1,2 % | 37,5 % |
| Inactif | 1 972 | 913 | 7,2 % | 77,8 % |

- **Chiffre officiel de campagne** : en contactant les 10 % de clients actifs les plus risqués, environ **51 futurs churners pour 1 000 clients contactés**, contre 20 au hasard (facteur 2,55) ; revenu mensuel en jeu de 30 059 $ pour un portefeuille de 100 000 clients.
- Ce sont des churners **atteints**, pas des départs évités : ceux-ci dépendent du taux de succès de l'offre, inconnu (à mesurer avec un groupe témoin).

## Explicabilité

- SHAP (`TreeExplainer`, en log-odds) sur le LightGBM, contributions regroupées sur la variable d'origine. Facteurs dominants : âge du terminal, évolution de l'usage, ancienneté (pic à 11-12 mois, fin d'engagement).
- Par client : 3 **raisons actionnables** (terminal, engagement, usage, forfait, réseau, service client, lignes) qui augmentent le risque, une **action suggérée** déduite de la première, et 2 facteurs de **contexte** non actionnables.
- Les raisons décrivent le modèle (« selon le modèle »), **pas des causes** du départ.

## Segmentation (descriptive)

- K-means à 5 segments sur 11 variables d'usage, de facture, d'ancienneté et de terminal, sans la cible, ajusté sur le train (`models/segmentation.joblib`, refait par `make train`). Sert à décrire le portefeuille ; le modèle de churn ne l'utilise pas.

## Considérations éthiques

- `ethnic` est exclue du modèle.
- 19 autres variables socio-démographiques sensibles restent des entrées du modèle (elles proviennent du jeu de données) : `adults`, `creditcd`, `dwllsize`, `dwlltype`, `forgntvl`, `HHstatin`, `income`, `infobase`, `kid0_2`, `kid11_15`, `kid16_17`, `kid3_5`, `kid6_10`, `marital`, `numbcars`, `ownrent`, `prizm_social_one`, `rv`, `truck`. Elles ne sont **jamais** affichées, jamais utilisées comme raison ou action, et jamais transmises à l'assistant IA (filtrées dans ses outils).
- Le score sert à prioriser une offre de fidélisation, pas à refuser un service.

## Limites

- **Chiffres absolus conditionnels** : les probabilités mensuelles et les effectifs « estimation portefeuille » dépendent du taux de churn réel **supposé** (2 %, sensibilité 1-3 %) ; le classement, lui, n'en dépend pas.
- **Signal faible** : aucune variable n'explique seule le churn (corrélation maximale 0,13) ; le modèle combine de nombreux petits effets.
- **Seuils issus de l'EDA** (11-12 mois, 300 jours) choisis sur le train : la CV est légèrement optimiste ; le test donne la mesure impartiale.
- **Associations, pas causes** : un facteur associé au churn n'est pas forcément un levier d'action.
- **Clients « déjà partis »** (sans usage ou sans variation d'usage) : signal réel mais de poids négligeable (test de fuite E8, D67).
- **Pas de dimension temporelle** : split aléatoire, pas de validation sur une période future ; la dérive des données n'est pas suivie (hors périmètre).
- **Équité non auditée** : les écarts de score selon les variables sensibles n'ont pas été mesurés.

## Suivi recommandé avant un usage réel

- Mesurer le vrai taux de churn mensuel et le taux de succès de l'offre (groupe témoin), puis remplacer les hypothèses de `configs/config.yaml`.
- Valider sur une période future et suivre la dérive des variables et du score.
- Réentraîner sans les variables socio-démographiques sensibles et mesurer le coût en AUC.
