# Contexte du projet — Telecom Customer Churn Prediction

> Dernière mise à jour : 27/09/2026.
> Note E1 : le CSV brut présent dans le repo s'appelle `data/raw/telco_churn.csv` (configuré dans `configs/config.yaml`, clé `data.raw_file`).

## 1. Cadre

| Élément | Valeur |
|---|---|
| Étudiant | Malek, 1ère année Data Science, ESSAI Tunis |
| Sujet d'origine | Atelier « Telecom Customer Churn Prediction » : EDA, prétraitement, feature engineering, analyse statistique, dashboard |
| Ambition | Aller plus loin : modèle prédictif calibré, explicabilité, scoring métier, application web React + FastAPI, assistant IA |
| Échéance | **Vendredi 2 octobre 2026** (rendu + soutenance) |
| Niveau | Python / pandas intermédiaire, JavaScript moyen |
| Outils de travail | Claude Code (code dans le repo), projet Claude (mentorat, analyse des résultats) |

**Objectif métier** : classer les clients selon leur risque de départ, pour concentrer un budget de fidélisation limité sur ceux qui en valent la peine, avec pour chacun une explication et une action suggérée.

**Problème Data Science** : classification binaire supervisée. On estime P(churn = 1 | usage, qualité de service, terminal, compte, profil), puis on utilise la probabilité calibrée pour classer et prioriser les clients.

## 2. Données — faits établis

- **Fichier** : `data/raw/Telecom_customer_churn.csv`, 100 000 lignes × 100 colonnes, une ligne par client.
- **Identifiant et cible** : `Customer_ID` est unique (0 doublon). La cible `churn` vaut 1 si le client est parti dans la fenêtre d'observation qui suit la mesure (définition à confirmer, typique de la base Cell2Cell).
- **Cible équilibrée** : 49,6 % de churners. C'est un échantillonnage volontaire, irréaliste pour un opérateur. Donc pas de SMOTE, mais une **correction du taux de base** avant tout calcul métier.
- **Pas de variables de contrat ni de mode de paiement.** Proxy candidat : `eqpdays` (âge du terminal). Le taux de churn passe d'environ 37 % à environ 60 % entre ~300 et ~395 jours, ce qui évoque une fin d'engagement vers 12 mois. **À valider en EDA** ; c'est une hypothèse.
- **Signal faible** : la corrélation maximale avec le churn est de 0,11 (`eqpdays`), puis 0,10 (`hnd_price`). Une AUC réaliste se situe probablement autour de 0,65–0,72, à confirmer.
- **Churn selon l'ancienneté** : environ 38 % pour `months` ≤ 6, puis environ 47 à 53 % au-delà. `months` varie de 6 à 61.
- **Valeurs manquantes** :
  - `numbcars` 49 %, `dwllsize` 38 %, `HHstatin` 38 %, `ownrent` 34 %, `dwlltype` 32 %, `lor` 30 %, `income` 25 %, `adults` 23 %, `infobase` 22 %, `hnd_webcap` 10 %, `prizm_social_one` 7 %, `avg6*` 2,8 % ;
  - un bloc socio-démo (`marital`, `kid*`, `creditcd`, `ethnic`, `rv`, `truck`, `forgntvl`) est absent **en même temps** sur 1,7 % des lignes ;
  - 357 clients n'ont aucune donnée d'usage (`rev_Mean`, `mou_Mean`, … tous NaN).
- **Valeurs invalides** : `rev_Mean` < 0 (5 lignes), `totmrc_Mean` < 0 (23), `eqpdays` < 0 (133). `mou_Mean` = 0 pour 1 615 clients.
- **Cohérence** : `actvsubs ≤ uniqsubs` est toujours respecté.
- **Redondance** : 19 paires numériques avec |r| > 0,95 (ex. `totrev` / `adjrev`, `avg3mou` / `avgmou`).
- **Catégorielles** :
  - `crclscod` (54 modalités, classe de crédit) ;
  - `area` (19 régions) ;
  - `new_cell`, `asl_flag`, `prizm_social_one`, `dualband`, `refurb_new`, `hnd_webcap`, `marital`, `HHstatin`, `dwllsize`, `dwlltype`, `ownrent`, `infobase`, `kid0_2` … `kid16_17`, `creditcd`, `ethnic`.
  - Le code « U » signifie *unknown* et doit être distingué de NaN.

### Blocs de variables

| Bloc | Colonnes principales |
|---|---|
| Revenu / facture | `rev_Mean`, `totmrc_Mean`, `ovrrev_Mean`, `vceovr_Mean`, `datovr_Mean`, `totrev`, `adjrev`, `avgrev`, `avg3rev`, `avg6rev`, `change_rev` |
| Usage | `mou_Mean`, `ovrmou_Mean`, `plcd_*`, `recv_*`, `comp_*`, `mou_cvce_Mean`, `mou_cdat_Mean`, `mou_rvce_Mean`, `peak_*`, `opk_*`, `mou_pea*`, `mou_opk*`, `attempt_Mean`, `complete_Mean`, `totcalls`, `totmou`, `adjmou`, `adjqty`, `avgmou`, `avgqty`, `avg3mou`, `avg3qty`, `avg6mou`, `avg6qty`, `roam_Mean`, `da_Mean`, `threeway_Mean`, `callfwdv_Mean`, `callwait_Mean`, `inonemin_Mean`, `owylis_*`, `iwylis_*`, `mouowylisv_Mean`, `mouiwylisv_Mean` |
| Tendance | `change_mou`, `change_rev` |
| Qualité réseau | `drop_vce_Mean`, `drop_dat_Mean`, `blck_vce_Mean`, `blck_dat_Mean`, `unan_vce_Mean`, `unan_dat_Mean`, `drop_blk_Mean` |
| Service client | `custcare_Mean`, `ccrndmou_Mean`, `cc_mou_Mean` |
| Terminal | `eqpdays`, `hnd_price`, `refurb_new`, `dualband`, `hnd_webcap`, `phones`, `models` |
| Compte | `months`, `uniqsubs`, `actvsubs`, `new_cell`, `crclscod`, `asl_flag`, `area` |
| Socio-démo | `prizm_social_one`, `income`, `marital`, `adults`, `kid*`, `ownrent`, `lor`, `dwlltype`, `dwllsize`, `HHstatin`, `infobase`, `numbcars`, `truck`, `rv`, `forgntvl`, `creditcd`, `ethnic` (exclue) |

## 3. Décisions prises

| # | Décision | Justification |
|---|---|---|
| D1 | Split 80/20 stratifié **avant** l'EDA, `RANDOM_STATE = 42` | Éviter qu'une information du test influence les choix |
| D2 | Pas de rééchantillonnage | Cible à 50/50 |
| D3 | Correction du prior vers un taux réel **hypothétique** (à fixer, ex. 2 % par mois) | Les probabilités sont gonflées par l'échantillonnage équilibré |
| D4 | Exclure `ethnic` et `Customer_ID` des variables du modèle | Éthique et réglementation / identifiant |
| D5 | Mann-Whitney + rank-biserial, χ² + V de Cramér, correction de Holm ou BH | Distributions asymétriques, n très grand |
| D6 | Modèles : Dummy → régression logistique → arbre et RF (comparaison) → LightGBM, CatBoost | Du plus interprétable au plus performant |
| D7 | Sélection multicritère : AUC en CV + écart-type entre folds + calibration + interprétabilité | Pas de choix arbitraire |
| D8 | Niveaux de risque définis par capacité de campagne et courbe de lift | Seuils justifiés, pas « au feeling » |
| D9 | Application web : **FastAPI + React/TypeScript** | Choix de l'étudiant (profil full-stack) |
| D10 | Assistant IA à outils (tool calling), boucle écrite à la main, sans LangChain | Fiabilité et compréhension |
| D11 | Hors périmètre : data drift, CI/CD, Docker, déploiement | Délai |
| D12 | Périmètre réduit pour le 2 octobre : 4 pages, pas de what-if, simulateur simplifié | Délai |

## 4. Architecture

```
CSV brut
 → [src/churn/data] chargement, validation (pandera), nettoyage, split
 → [notebooks 01-08] audit, EDA, statistiques, features, modélisation, évaluation, SHAP, métier
 → [src/churn/features, models, evaluation, explain, business] pipeline sklearn, entraînement, calibration, SHAP, scoring
 → [scripts/build_artifacts.py] models/pipeline.joblib + artifacts/scores.parquet, shap.parquet, kpis.json
 → [src/churn/services] fonctions métier testées (lecture des artefacts)
 → [api/] FastAPI : endpoints REST + /api/chat (streaming SSE)
      └→ [src/churn/assistant] agent LLM : appelle les services via tool calling
 → [frontend/] React + TypeScript + Vite + Mantine + ECharts + AG Grid + TanStack Query
```

Principe clé : **le modèle est entraîné hors ligne.** L'API et l'assistant ne font que lire les artefacts via les services. Chaque chiffre affiché vient du même code testé.

## 5. Structure du repository

```
telecom-churn/
├── CLAUDE.md                 # Contexte pour Claude Code
├── README.md
├── pyproject.toml            # Package Python installable (pip install -e .)
├── requirements.txt
├── Makefile                  # data | train | artifacts | api | front | dev | test
├── .env.example              # LLM_PROVIDER, LLM_API_KEY, LLM_MODEL
├── .gitignore
├── configs/config.yaml       # Chemins, seed, colonnes exclues, CV, hypothèses métier
├── data/{raw,interim,processed}/   # non versionné
├── notebooks/
│   ├── 01_data_audit.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_statistical_analysis.ipynb
│   ├── 04_feature_engineering.ipynb
│   ├── 05_modeling.ipynb
│   ├── 06_evaluation_calibration.ipynb
│   ├── 07_explainability.ipynb
│   └── 08_business_analysis.ipynb
├── src/churn/
│   ├── config.py, logging_setup.py
│   ├── data/           load.py, validate.py, clean.py, split.py
│   ├── features/       build.py
│   ├── models/         pipelines.py, train.py, tune.py, predict.py
│   ├── evaluation/     metrics.py, calibration.py
│   ├── explain/        shap_utils.py, reason_codes.py
│   ├── business/       scoring.py, actions.py, campaign.py
│   ├── services/       customers.py, segments.py, kpis.py, drivers.py
│   └── assistant/      llm_client.py, tools.py, agent.py, prompts.py, guardrails.py
├── api/
│   ├── main.py
│   ├── schemas.py
│   └── routers/        kpis.py, segments.py, customers.py, drivers.py, chat.py
├── frontend/src/
│   ├── api/            client.ts, types.ts
│   ├── pages/          Overview.tsx, Segments.tsx, Customers.tsx (+ fiche), Assistant.tsx
│   ├── components/     KpiCard, ChartCard, RiskBadge, CustomerTable, ChatPanel…
│   ├── store/          filters.ts (Zustand)
│   └── theme.ts
├── scripts/            make_dataset.py, train.py, build_artifacts.py, score.py
├── models/             pipeline.joblib, model_card.md
├── artifacts/          scores.parquet, shap.parquet, kpis.json
├── reports/figures/
├── tests/
└── docs/               data_dictionary.md, decisions.md, bilans.md, assistant_eval.md
```

## 6. Stack

| Couche | Outils |
|---|---|
| Python 3.11 | pandas, pyarrow, pandera, scipy, statsmodels, scikit-learn, lightgbm, catboost, optuna, shap, plotly, seaborn, joblib, pydantic, pydantic-settings, pyyaml |
| API | fastapi, uvicorn, sse-starlette ; tests avec `TestClient` + pytest |
| IA | SDK du fournisseur LLM choisi, derrière une interface `LLMClient` (fournisseur à confirmer : API commerciale, offre gratuite ou Ollama local) |
| Frontend | React 18, TypeScript, Vite, Mantine, echarts-for-react, ag-grid-react, @tanstack/react-query, react-router-dom, zustand |
| Qualité | ruff, pytest, ESLint, Prettier |

## 7. Produit : application web (4 pages pour le 2 octobre)

| Page | Question | Contenu |
|---|---|---|
| Vue d'ensemble | Quelle est la situation ? | 5 KPI (clients, taux de churn, clients High, revenu mensuel en jeu, lift du top 10 %), répartition des niveaux, résumé IA « Ce qu'il faut retenir », tableau capacité → clients ciblés |
| Segments et facteurs | Qui churne et pourquoi ? | Churn par ancienneté, âge du terminal, usage, région ; heatmap ancienneté × terminal ; importance SHAP globale |
| Clients à risque | Qui cibler ? | Table AG Grid (tri, filtres, export) ; clic → tiroir « fiche client » avec probabilité, niveau, cascade SHAP, action, boutons IA « Expliquer » et « Rédiger une offre » |
| Assistant | Poser une question | Chat en streaming, questions suggérées, outils appelés affichés sous chaque réponse |

**Charte** :

- Mantine, clair et sombre, police Inter ;
- un seul bleu d'accent ; rouge = High, ambre = Medium, gris = Low ;
- grille de 12 colonnes, espacements de 8 px ;
- titres qui énoncent une conclusion ;
- pas d'emojis, de dégradés ni de 3D.

**Endpoints** :

- `GET /api/kpis`
- `GET /api/segments?dimension=`
- `GET /api/drivers`
- `GET /api/customers?level=&area=&page=&size=&sort=`
- `GET /api/customers/{id}`
- `GET /api/customers/{id}/explanation`
- `POST /api/customers/{id}/retention-message`
- `GET /api/summary`
- `POST /api/chat` (SSE)

**Outils de l'assistant** : `get_customer`, `explain_customer`, `list_at_risk`, `segment_stats`, `kpi_summary`, `global_drivers`, `explain_method`. Limite de 5 appels par question. Un mode démo permet de fonctionner sans clé API.

## 8. Planning

| Partie | Jour | Étapes |
|---|---|---|
| A — Données | Lun 28/09 | E1 Setup · E2 Audit qualité · E3 Split · E4 EDA |
| B — Modélisation | Mar 29/09 | E5 Statistiques · E6 Features · E7 Pipeline + baselines · E8 Modèles avancés |
| C — Rendre utile + API | Mer 30/09 | E9 Tuning + test final · E10 Calibration · E11 SHAP · E12 Scoring + artefacts · E13 API FastAPI |
| D — Produit + IA | Jeu 01/10 | E14 Squelette frontend · E15 Pages · E16 Assistant (backend) · E17 Chat (frontend) |
| E — Finalisation | Ven 02/10 matin | E18 Tests + README + model card · E19 Soutenance |

## 9. Hypothèses et points ouverts

- Taux de churn réel pour la correction du prior : **hypothèse à fixer** (proposition : 2 % par mois, à citer comme hypothèse).
- Fournisseur LLM : à choisir avant E16.
- Définition exacte de `churn`, `change_mou`, `eqpdays` : à confirmer via la source du dataset (Kaggle / Cell2Cell).
- Validation par l'enseignant de l'ajout de la modélisation et de l'IA.
