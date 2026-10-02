# Trace de l'essai Gemini réussi (2 octobre 2026)

Seul essai concluant du test autorisé le jour de la soutenance (décision D120). Ce document ne
contient aucune donnée de clé : la clé est lue depuis `.env` par `churn.assistant.llm_client` et
n'apparaît jamais dans les sorties.

## Conditions

| Élément | Valeur |
|---|---|
| Modèle | `gemini-3.5-flash-lite` (SDK `google-genai`) |
| Boucle | `churn.assistant.agent.Agent`, bascule en mode démo **désactivée** (`fallback=False`), pour qu'un échec ne soit pas masqué |
| Mesure | chronomètre autour de toute la boucle ; compteur sur chaque appel `generate_content_stream`, réessais compris |
| Interface | aucune (appel direct au code Python, sans l'API ni le navigateur) |

## Déroulé

| Étape | Contenu |
|---|---|
| Question | « Combien de clients sont classés High ? » |
| Requête 1 | Gemini choisit un outil : `get_kpis` |
| Paramètres de l'outil | **non enregistrés** (voir la note ci-dessous) |
| Requête 2 | Gemini rédige la réponse à partir du résultat de l'outil |
| Garde-fous | aucun avertissement : chaque nombre de la réponse figure dans le résultat de l'outil |
| Erreurs | aucune |

## Réponse obtenue (texte intégral)

> Il y a **17 472** clients dans la base classés au niveau de risque **High**.
>
> - Cela représente une estimation de **9 876** clients dans l'estimation portefeuille (pour un portefeuille de 100 000 clients).
> - Le revenu mensuel en jeu associé à ce niveau de risque est de **29 762** $ (estimation portefeuille).

Contrôle : ces trois chiffres sont exacts, ce sont ceux des artefacts (niveau High : 17 472 clients
dans la base, environ 9 876 en estimation portefeuille au taux supposé de 2 %, 29 762 $ de revenu
mensuel en jeu).

## Temps et consommation

| Mesure | Valeur |
|---|---|
| Durée totale | **10,3 s** |
| Premier mot de la réponse | 10,0 s après l'envoi de la question |
| Requêtes Gemini consommées | **2** |

Le délai se concentre avant le premier mot, dans les deux allers-retours avec Gemini (choix de
l'outil, puis rédaction). L'outil lui-même répond en quelques millisecondes.

## Note sur les paramètres de l'outil

Le script de test n'affichait que le nom des outils appelés, pas leurs arguments, et aucun journal
ne les a enregistrés. Les paramètres exacts de l'appel à `get_kpis` ne sont donc pas connus, et
aucun nouvel appel n'a été fait pour les retrouver (consigne : plus d'appel Gemini ce jour-là).

Rejoué localement, sans Gemini, l'outil donne les trois chiffres de la réponse avec les deux
paramétrages plausibles :

| Paramètres de `get_kpis` | 17 472 | 9 876 | 29 762 $ |
|---|---|---|---|
| `{}` (portefeuille entier, ligne High du détail par niveau) | oui | oui | oui |
| `{"risk_level": ["High"]}` (périmètre filtré sur High) | oui | oui | oui |

La réponse ne permet pas de trancher entre les deux. Pour un prochain test, le script devra
afficher les arguments de chaque appel d'outil (`tool_call`).

## Pour rappel : l'essai en échec

`gemini-3.8-flash`, même question : service indisponible (503) au premier essai et aux 2 réessais
automatiques ; 3 requêtes, 17,5 s, aucune réponse. Voir D120 et `docs/demo_script.md`.
