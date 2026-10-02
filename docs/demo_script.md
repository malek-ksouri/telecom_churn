# Parcours de démonstration (3 minutes)

Parcours joué de bout en bout par `frontend/scripts/demo_parcours.py` (21/21 vérifications, thèmes
clair et sombre, captures dans `frontend/screenshots/demo/`). Les chiffres ci-dessous sont ceux de
l'application au 1er octobre 2026 (artefacts actuels). Effectifs « estimation portefeuille » : taux
de churn réel **supposé** de 2 %/mois.

## Avant de commencer (5 minutes avant)

1. Lancer l'API et le frontend : `cd frontend && npm run dev:all` (API sur le port 8000, interface
   sur le port 5173). Vérifier `http://localhost:8000/api/health`.
2. Ouvrir `http://localhost:5173` en plein écran (1440 × 900 ou plus), thème clair (plus lisible au
   vidéoprojecteur).
3. Badge en haut à droite : « Assistant : Gemini » (plan A) ou « Assistant : démo » (plan B).
4. Panneau assistant : « Nouvelle conversation » pour partir d'un fil vide.
5. Aucun filtre actif (« Aucun filtre : portefeuille entier »).

## Le parcours

| Temps | Écran | Geste | À dire |
|---|---|---|---|
| 0:00 | Vue d'ensemble | — | « Sur un portefeuille de 100 000 clients, le modèle attend **2 002 départs** le mois prochain, soit **116 162 $** de revenu mensuel en jeu. Les clients High pèsent 10 % du portefeuille mais **25 % des départs attendus**. » Montrer l'encart « Ce qu'il faut retenir » et le badge d'hypothèse (taux réel 2 %). |
| 0:25 | Segments et facteurs | Clic sur la barre « 11-12 mois (fin d'engagement) » | « Chaque graphique est cliquable : la fin d'engagement devient un filtre global. Risque mensuel de **3,51 %**, **1,8 fois la moyenne**. Le pic est à 11-12 mois avec un terminal de 10-12 mois (**3,7 %**). Selon le modèle, la fin d'engagement est le premier levier actionnable. » Dire « selon le modèle » : SHAP n'est pas causal. |
| 0:55 | Simulateur | Retirer le filtre (croix du chip), puis « Simulateur » | Réglages par défaut : capacité **10 %**, succès **20 %**, horizon **12 mois**. « Cibler 10 % du portefeuille avec le modèle atteint **511 churners, contre 200 au hasard (× 2,55)**, soit 51 pour 1 000 contacts. **Si** l'offre en retient 20 %, ce qui est une hypothèse à mesurer par un groupe témoin, cela fait environ **102 départs évités** et **72 143 $** sur 12 mois. Sans coût saisi, aucun solde n'est affiché. » |
| 1:25 | Clients à risque | Clic sur « Clients à risque » | « **98 028 clients** actifs, triés par risque, chacun avec sa raison principale et une action. Les inactifs sont à part : ils relèvent d'une vérification de ligne, pas d'une offre. » |
| 1:40 | Fiche client | Rechercher `1072931`, clic sur la ligne | « Client High : **6,4 %** de risque mensuel, 3,2 fois la moyenne. Action suggérée : **offre de réengagement**, déduite du facteur actionnable dominant, la fin d'engagement (12 mois). » |
| 2:00 | Fiche → « Expliquer » | Clic | « L'IA reformule pour le conseiller ce que les outils ont calculé ; elle ne calcule rien elle-même. » Lire la première phrase. |
| 2:15 | Fiche → « Rédiger une offre » | Clic | « Un SMS de moins de 300 caractères (**179** ici) et un email, prêts à copier. » Montrer le bouton de copie. |
| 2:30 | Assistant (panneau latéral) | Échap, bouton assistant en haut à droite, question suggérée « Si je contacte 10 % des clients avec un taux de succès de 20 % ? » | « Même chiffre que le simulateur : **511 churners, 200 au hasard**. Le taux de succès est annoncé comme hypothèse. » Déplier « Outils utilisés » : un appel, `simulate_campaign`, avec sa durée. |
| 2:55 | — | — | Conclure : « Un modèle calibré, des explications prudentes, des chiffres d'impact toujours conditionnés à une hypothèse affichée. » |

Durée automatisée du parcours : 22 s. Le temps restant sert au commentaire.

## Plan A (Gemini) et plan B (mode démonstration)

- **Plan A** : `.env` avec `LLM_PROVIDER=gemini`, `LLM_MODEL` et `LLM_API_KEY`. Le parcours consomme
  environ **3 requêtes** (Expliquer, Rédiger une offre, une question), ou un peu plus si Gemini
  enchaîne plusieurs tours d'outils, sur un quota gratuit de 20 par jour. Ne pas multiplier les
  répétitions avec Gemini le jour J.
- **Plan B (sans clé, sans réseau)** : `LLM_PROVIDER=demo` dans `.env`, ou clé absente. Redémarrer
  l'API. Le badge passe à « Assistant : démo », et la page Assistant affiche la raison (« Mode
  démonstration demandé » ou « Clé API absente »). Les réponses viennent de scénarios
  déterministes qui appellent **les mêmes outils** : les chiffres sont identiques. C'est la
  version testée à 21/21.
- **En cours de séance** : si Gemini renvoie une erreur de quota ou d'indisponibilité, l'agent
  bascule seul en mode démonstration pour la question en cours, et un message le signale sous la
  réponse. Inutile de redémarrer.
- **Si l'API tombe** : les pages affichent un état d'erreur avec « Réessayer ». Relancer
  `npm run dev:all`.

## Questions de secours pour l'assistant

- « Quels clients cibler en priorité ? » → liste des clients High avec leur action.
- « Pourquoi le client 1072931 est-il à risque ? » → raisons selon le modèle, avec un identifiant
  cliquable qui ouvre la fiche.
- « Quel segment churne le plus ? » → segments classés par risque (outil `segment_stats`).
- « Qu'est-ce que le lift ? » → définition et valeur mesurée sur l'échantillon (outil `explain_method`).
- Question hors périmètre (« Quel temps fera-t-il demain ? ») → refus poli : garde-fou.

## Choix pour la soutenance : mode démonstration (test du 2 octobre 2026)

Un seul test Gemini a été autorisé, avec la question « Combien de clients sont classés High ? » et la règle suivante : Gemini n'est retenu que si la réponse est juste et arrive en moins de 10 s.

| Modèle | Résultat | Temps | Requêtes |
|---|---|---|---|
| gemini-3.8-flash | échec : service indisponible (503), au premier essai et aux 2 réessais | 17,5 s | 3 |
| gemini-3.5-flash-lite | réponse correcte : outil `get_kpis`, 17 472 clients dans la base (environ 9 876 en estimation portefeuille), aucun avertissement des garde-fous | 10,3 s | 2 |

**Décision (D120)** : la soutenance se fait en **mode démonstration** (`LLM_PROVIDER=demo`, badge « Assistant : démo »). C'est la version testée à 21/21. Aucun autre appel Gemini le jour de la soutenance.

À dire si le jury pose la question : « L'assistant fonctionne avec Gemini : nous l'avons testé ce matin, la réponse était juste mais arrivait en 10 s, ce qui est trop lent pour une démonstration en direct. Le mode démonstration appelle les mêmes outils et donne donc les mêmes chiffres ; seule la rédaction est fixe. »
