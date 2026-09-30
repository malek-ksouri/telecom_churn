# Fiche du modèle de churn

*Générée le 30/09/2026 par `scripts/train.py`.*

## Modèle

- **Type** : LightGBM (boosting de gradient) (`build_pipeline("lightgbm")`).
- **Usage prévu** : classer les clients par risque de départ pour cibler une campagne de rétention à budget limité. Aide à la décision, pas décision automatique.
- **Sortie** : score de risque (probabilité sur l'échantillon équilibré, **non calibrée** à ce stade : calibration et correction vers le taux réel en E10).

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
- **Test** : `data/processed/test.parquet`, 20 000 clients, lu **une seule fois** (E9).
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

- **Lecture** : à 2 % de churn mensuel (hypothèse), pour 1 000 clients contactés, le ciblage atteint environ 56 futurs churners contre 20 au hasard ; les départs évités dépendent du taux de succès de l'offre, à mesurer (il n'est pas dans les données).

## Limites

- **Probabilités non calibrées** et issues d'un échantillon équilibré : ne pas les lire comme des probabilités réelles avant E10.
- **Signal faible** : aucune variable n'explique seule le churn (corrélation maximale 0,13) ; le modèle combine de nombreux petits effets.
- **Seuils issus de l'EDA** (11-12 mois, 300 jours) choisis sur le train : la CV est légèrement optimiste ; le test donne la mesure impartiale.
- **Associations, pas causes** : un facteur associé au churn n'est pas forcément un levier d'action.
- **Clients « déjà partis »** (sans usage ou sans variation d'usage) : signal réel mais de poids négligeable (test de fuite E8, D67).
- **Pas de dimension temporelle** : split aléatoire, pas de validation sur une période future ; la dérive des données n'est pas suivie (hors périmètre).
