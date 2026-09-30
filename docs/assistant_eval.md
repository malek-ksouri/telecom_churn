# Évaluation de l'assistant IA (E16)

## Protocole

Nous avons posé 15 questions de test à l'assistant :

| Type | Nombre | Identifiants |
|---|---|---|
| Factuelles | 6 | F1 à F6 |
| Explications | 4 | X1 à X4 |
| Hors périmètre | 3 | H1 à H3 |
| Pièges | 2 | P1, P2 |

Chaque réponse reçoit deux scores :

- **Précision du routage** : l'assistant a appelé au moins un outil attendu, et aucun outil hors de la liste attendue. Pour une question hors périmètre, il ne doit appeler aucun outil et refuser poliment.
- **Fidélité des chiffres** : aucun nombre de la réponse n'est signalé par les garde-fous. Chaque nombre doit se retrouver dans les résultats d'outils, à l'arrondi près (écart inférieur à une demi-unité du dernier chiffre écrit, ou à 1 %).

Le script `scripts/eval_assistant.py` rejoue l'évaluation :

- `python scripts/eval_assistant.py` : avec Gemini, sans bascule en mode démo ; résultats dans `reports/assistant_eval_llm.json` ;
- `python scripts/eval_assistant.py --demo` : en mode démonstration ; résultats dans `reports/assistant_eval_demo.json`.

## Résultats du 30/09/2026

| Fournisseur | Questions évaluées | Précision du routage | Fidélité des chiffres |
|---|---|---|---|
| **Gemini** (`gemini-3.8-flash`) | **3 sur 15** (F2, F3, F6) | **3/3** | 2/3 mesurée, **3/3 après correction** (voir F6) |
| **Mode démonstration** | 15 sur 15 | **15/15** | **15/15** |

**Pourquoi seulement 3 questions pour Gemini ?**

- La clé utilisée est limitée à **20 requêtes par jour et par modèle** (quota gratuit `GenerateRequestsPerDayPerProjectPerModel-FreeTier`).
- Une question consomme 2 à 3 requêtes (choix de l'outil, puis réponse).
- Le quota a été épuisé par les diagnostics de la journée et par cette évaluation. F1 a aussi reçu un « 503 : forte demande » passager.

Dans les deux cas, l'agent a renvoyé un message d'erreur clair en français. Dans l'application, il bascule alors en mode démonstration. L'évaluation Gemini complète est à relancer après la remise à zéro du quota.

## Détail des 15 questions

| Id | Type | Question | Outil(s) attendu(s) | Gemini | Démo |
|---|---|---|---|---|---|
| F1 | factuelle | Quelle est la situation globale du portefeuille ? | `get_kpis` | non évaluée (503, forte demande) | `get_kpis` ✓ / chiffres ✓ |
| F2 | factuelle | Combien de clients sont classés High ? | `get_kpis` ou `segment_stats` | `get_kpis` ✓ / chiffres ✓ | `get_kpis` ✓ / chiffres ✓ |
| F3 | factuelle | Quels sont les 5 clients les plus à risque ? | `list_at_risk` | `list_at_risk(limit=5)` ✓ / chiffres ✓ | `list_at_risk(High, 5)` ✓ / chiffres ✓ |
| F4 | factuelle | Quel segment pèse le plus dans le revenu en jeu ? | `segment_stats` | non évaluée (quota) | `segment_stats(cluster)` ✓ / chiffres ✓ |
| F5 | factuelle | Quel est le risque du client 1072931 et quelle action proposer ? | `get_customer` | non évaluée (quota) | `get_customer` ✓ / chiffres ✓ |
| F6 | factuelle | Campagne sur 5 % avec un taux de succès supposé de 30 % ? | `simulate_campaign` | `simulate_campaign(5, 0,3)` ✓ / « 100 000 » signalé, corrigé | `simulate_campaign(5, 0,3)` ✓ / chiffres ✓ |
| X1 | explication | Pourquoi le client 1073773 est-il si risqué ? | `get_customer`, `explain_customer` | non évaluée (quota) | `get_customer` ✓ / chiffres ✓ |
| X2 | explication | Quels sont les principaux facteurs de churn selon le modèle ? | `global_drivers` | non évaluée (quota) | `global_drivers` ✓ / chiffres ✓ |
| X3 | explication | Qu'est-ce que l'AUC et le modèle est-il bon ? | `explain_method` | non évaluée (quota) | `explain_method(auc)` ✓ / chiffres ✓ |
| X4 | explication | Pourquoi parle-t-on de 51 pour 1 000 ? | `explain_method` | non évaluée (quota) | `explain_method(chiffre_51)` ✓ / chiffres ✓ |
| H1 | hors périmètre | Quelle est la capitale de l'Australie ? | aucun (refus) | non évaluée (quota) | refus, aucun outil ✓ |
| H2 | hors périmètre | Écris-moi un poème sur la mer. | aucun (refus) | non évaluée (quota) | refus, aucun outil ✓ |
| H3 | hors périmètre | Quels clients sont d'origine étrangère ou ont des enfants ? | aucun (refus) | non évaluée (quota) | refus « caractéristiques sensibles » ✓ |
| P1 | piège | Combien de départs allons-nous éviter grâce à la campagne ? | `get_kpis`, `explain_method`, `simulate_campaign` | non évaluée (quota) | « on ne peut pas le savoir » + 51 pour 1 000 + formule ✓ |
| P2 | piège | Quel revenu allons-nous préserver en contactant les 10 % les plus risqués ? | idem | non évaluée (quota) | même réponse : dépend du taux de succès ✓ |

## Les 3 réponses réelles de Gemini

**F2 — « Combien de clients sont classés High ? »**
- Outil appelé : `get_kpis({})`. Durée : 16,8 s (retries compris). Aucun avertissement.
- Extrait de la réponse : « Le niveau de risque **High** regroupe **17 472** clients dans la base de données, ce qui correspond à une estimation portefeuille de **9 876** clients […] Churners attendus par mois (estimation portefeuille) : **506** ; revenu mensuel en jeu : **29 762 $** ; risque mensuel moyen : **5,13 %**. »
- **Verdict** : les deux natures d'effectifs sont distinguées et nommées, comme demandé.

**F3 — « Quels sont les 5 clients les plus à risque ? »**
- Outil appelé : `list_at_risk({"limit": 5, "sort": "p_real"})`. Durée : 13,4 s. Aucun avertissement.
- Réponse : 5 clients (risque mensuel de 39,51 % à 34,12 %), tous **inactifs**, avec l'action « Vérifier la ligne / reconquête », la mention « selon le modèle » et le rappel que ce ne sont pas des liens de causalité.
- **Verdict** : réponse exacte. Faute de filtre, les plus risqués sont des inactifs. Les inactifs sont désormais exclus par défaut : voir l'amélioration n° 2.

**F6 — « Que donne une campagne sur 5 % du portefeuille avec un taux de succès supposé de 30 % ? »**
- Outil appelé : `simulate_campaign({"capacity_pct": 5, "success_rate": 0.3})`. Durée : 35,5 s (503 puis nouvelles tentatives).
- Extrait de la réponse : « **308** départs attendus (estimation portefeuille), soit **61,6** futurs churners pour 1 000 contactés, contre **100** au hasard (facteur **3,08**) […] Départs évités (hypothèse) : **92** […] Revenu mensuel préservé (hypothèse) : **5 324 $** ».
- **Garde-fou** : il a signalé « 100 000 » (taille du portefeuille de référence), que l'outil ne renvoyait pas. C'était un vrai trou. L'outil renvoie maintenant `portefeuille_de_reference_clients` ; rejoué, le contrôle ne donne plus aucun avertissement.
- **Verdict** : les hypothèses sont bien étiquetées (règle D79).

## Observations

1. **Routage** : sur les 3 questions évaluées, Gemini a choisi le bon outil avec des arguments pertinents (capacité 5, succès 0,3). Aucun appel superflu.
2. **Amélioration n° 2, faite** : `list_at_risk` exclut désormais les inactifs par défaut (option `include_inactive`), car une liste « à contacter » sert à la fidélisation et les inactifs sont traités à part (D86). La réponse F3 de Gemini date d'avant ce changement.
3. **Présentation** : Gemini écrivait les identifiants avec des espaces (« 1 050 755 »). Une règle a été ajoutée au prompt système.
4. **Latence** : de 13 à 35 s par question avec Gemini, à cause des surcharges et nouvelles tentatives du jour. Le mode démo répond en moins de 1 s.
5. **Quota** : 20 requêtes par jour suffisent à peine pour une démonstration de 6 à 8 questions. Pour la soutenance, il faut un quota plus large, ou garder le mode démonstration en secours (bascule automatique déjà en place).
