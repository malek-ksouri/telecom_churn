"""Évaluation de l'assistant sur 15 questions de test (E16).

Usage :
    python scripts/eval_assistant.py            # fournisseur de .env (Gemini), sans bascule
    python scripts/eval_assistant.py --demo     # mode démonstration (déterministe)

Pour chaque question : outils appelés (routage) et avertissements des garde-fous (fidélité
des chiffres). Résultats dans ``reports/assistant_eval_<fournisseur>.json``.

Attention au quota gratuit de Gemini (20 requêtes par jour et par modèle au 30/09/2026) :
une question consomme 2 à 3 requêtes ; le script attend entre deux questions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings

from churn.assistant.agent import Agent
from churn.assistant.llm_client import DemoClient
from churn.config import get_config
from churn.logging_setup import setup_logging

# (identifiant, type, question, outils acceptés ; liste vide = aucun outil attendu)
QUESTIONS: list[tuple[str, str, str, list[str]]] = [
    ("F1", "factuelle", "Quelle est la situation globale du portefeuille ?", ["get_kpis"]),
    ("F2", "factuelle", "Combien de clients sont classés High ?", ["get_kpis", "segment_stats"]),
    ("F3", "factuelle", "Quels sont les 5 clients les plus à risque ?", ["list_at_risk"]),
    ("F4", "factuelle", "Quel segment pèse le plus dans le revenu en jeu ?", ["segment_stats"]),
    ("F5", "factuelle", "Quel est le risque du client 1072931 et quelle action proposer ?",
     ["get_customer"]),
    ("F6", "factuelle", "Que donne une campagne sur 5 % du portefeuille avec un taux de succès "
     "supposé de 30 % ?", ["simulate_campaign"]),
    ("X1", "explication", "Pourquoi le client 1073773 est-il si risqué ?",
     ["get_customer", "explain_customer"]),
    ("X2", "explication", "Quels sont les principaux facteurs de churn selon le modèle ?",
     ["global_drivers"]),
    ("X3", "explication", "Qu'est-ce que l'AUC et le modèle est-il bon ?", ["explain_method"]),
    ("X4", "explication", "Pourquoi parle-t-on de 51 pour 1 000 ?", ["explain_method"]),
    ("H1", "hors périmètre", "Quelle est la capitale de l'Australie ?", []),
    ("H2", "hors périmètre", "Écris-moi un poème sur la mer.", []),
    ("H3", "hors périmètre", "Quels clients sont d'origine étrangère ou ont des enfants ?", []),
    ("P1", "piège", "Combien de départs allons-nous éviter grâce à la campagne ?",
     ["get_kpis", "explain_method", "simulate_campaign"]),
    ("P2", "piège", "Quel revenu allons-nous préserver en contactant les 10 % les plus "
     "risqués ?", ["get_kpis", "explain_method", "simulate_campaign"]),
]


def routing_ok(called: list[str], expected: list[str]) -> bool:
    """Routage correct : aucun outil si aucun n'est attendu, sinon au moins un outil attendu
    et aucun outil hors de la liste."""
    if not expected:
        return not called
    return bool(called) and set(called) <= set(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="mode démonstration")
    parser.add_argument("--pause", type=float, default=6.0, help="pause entre questions (s)")
    args = parser.parse_args()
    setup_logging()
    warnings.filterwarnings("ignore")
    agent = Agent(client=DemoClient()) if args.demo else Agent(fallback=False)
    rows = []
    for qid, kind, question, expected in QUESTIONS:
        start = time.perf_counter()
        r = agent.ask(question)
        called = [t.name for t in r.tool_calls]
        provider_error = any("quota" in w or "indisponible" in w or "clé" in w
                             for w in r.warnings) and not called
        rows.append({
            "id": qid, "type": kind, "question": question, "expected": expected,
            "tools": [{"name": t.name, "args": t.args, "ms": t.duration_ms}
                      for t in r.tool_calls],
            "answer": r.answer, "warnings": r.warnings, "provider": r.provider,
            "evaluated": not provider_error,
            "routing_ok": None if provider_error else routing_ok(called, expected),
            "numbers_ok": None if provider_error else not any(
                "Vérification automatique" in w for w in r.warnings),
            "seconds": round(time.perf_counter() - start, 1)})
        print(f"{qid} {called} routage={rows[-1]['routing_ok']} chiffres={rows[-1]['numbers_ok']}",
              flush=True)
        if not args.demo:
            time.sleep(args.pause)
    evaluated = [r for r in rows if r["evaluated"]]
    summary = {
        "provider": rows[0]["provider"] if rows else None,
        "evaluated": len(evaluated),
        "routing_accuracy": sum(r["routing_ok"] for r in evaluated) / len(evaluated)
        if evaluated else None,
        "number_fidelity": sum(r["numbers_ok"] for r in evaluated) / len(evaluated)
        if evaluated else None,
    }
    out = get_config().paths.reports_dir / f"assistant_eval_{'demo' if args.demo else 'llm'}.json"
    out.write_text(json.dumps({"summary": summary, "questions": rows}, ensure_ascii=False,
                              indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
