"""Tests de l'assistant IA (E16) : outils, boucle d'agent (faux LLM), garde-fous, endpoints en
mode démonstration. Aucun test n'appelle la vraie API Gemini."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from churn.config import get_config

ARTIFACTS = [get_config().paths.artifacts_dir / f for f in
             ("scores.parquet", "shap.parquet", "shap_values.parquet", "kpis.json")]
pytestmark = pytest.mark.skipif(not all(p.is_file() for p in ARTIFACTS),
                                reason="artefacts absents : lancer `make artifacts`")

from churn.assistant.agent import Agent, tool_specs  # noqa: E402
from churn.assistant.guardrails import check_answer, extract_numbers  # noqa: E402
from churn.assistant.llm_client import (  # noqa: E402
    ChatMessage,
    DemoClient,
    LLMClient,
    LLMError,
    StreamChunk,
    ToolCall,
    ToolSpec,
    match_scenario,
)
from churn.assistant.tools import SENSITIVE_VARIABLES, TOOLS, run_tool  # noqa: E402
from churn.explain.shap_utils import LABELS  # noqa: E402

CUSTOMER = 1072931


class ScriptedClient(LLMClient):
    """Faux LLM : rejoue une liste de réponses et enregistre ce qu'il reçoit."""

    provider, model = "fake", "scripted"

    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[list[ChatMessage], list[ToolSpec] | None]] = []

    def stream(self, messages, tools, system) -> Iterator[StreamChunk]:
        self.calls.append((list(messages), tools))
        reply = self.replies.pop(0) if self.replies else "Réponse finale."
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = reply(messages, tools)
        if isinstance(reply, str):
            reply = ChatMessage("assistant", reply)
        for word in reply.content.split(" "):
            yield StreamChunk("text", text=word + " ")
        yield StreamChunk("end", message=reply)


# --- Outils ----------------------------------------------------------------------------------

def test_tools_are_deterministic_and_validated() -> None:
    for name, args in [("get_kpis", {}), ("get_customer", {"customer_id": CUSTOMER}),
                       ("list_at_risk", {"risk_level": ["High"], "limit": 3}),
                       ("segment_stats", {"dimension": "cluster"}), ("global_drivers", {}),
                       ("simulate_campaign", {"capacity_pct": 10, "success_rate": 0.2}),
                       ("explain_method", {"topic": "chiffre_51"})]:
        first, second = run_tool(name, args), run_tool(name, args)
        assert "error" not in first and first == second
    assert run_tool("get_customer", {"customer_id": 1})["error"].endswith("introuvable")
    assert "error" in run_tool("list_at_risk", {"limit": 21})
    assert "error" in run_tool("simulate_campaign", {"success_rate": 2})
    assert "error" in run_tool("unknown_tool", {})
    default = run_tool("list_at_risk", {"limit": 20})["clients"]
    assert {c["niveau"] for c in default} <= {"High", "Medium", "Low"}
    with_inactive = run_tool("list_at_risk", {"limit": 20, "include_inactive": True})["clients"]
    assert "Inactif" in {c["niveau"] for c in with_inactive}
    kpis = run_tool("get_kpis", {})
    per_1000 = kpis["campagne_officielle"]["churners_pour_1000_contactes"]
    assert per_1000 == pytest.approx(51.1, abs=0.2)
    zero = run_tool("simulate_campaign", {"capacity_pct": 10, "success_rate": 0})
    assert zero["resultat"]["HYPOTHESE_departs_evites"] == 0
    assert zero["resultat"]["HYPOTHESE_cout_campagne_dollars"] is None


def test_tool_schemas_are_flat() -> None:
    for spec in tool_specs():
        text = json.dumps(spec.parameters)
        assert "$ref" not in text and "anyOf" not in text and '"title"' not in text
        assert spec.parameters["type"] == "object"
    assert set(TOOLS) == {"get_kpis", "get_customer", "explain_customer", "list_at_risk",
                          "segment_stats", "global_drivers", "simulate_campaign",
                          "explain_method"}


def test_tools_never_expose_sensitive_variables() -> None:
    labels = {LABELS[v] for v in SENSITIVE_VARIABLES if v in LABELS}
    customers = run_tool("list_at_risk", {"limit": 20})["clients"]
    outputs = [run_tool("global_drivers", {"top": 15})]
    for c in customers:
        outputs.append(run_tool("get_customer", {"customer_id": c["client"]}))
        outputs.append(run_tool("explain_customer", {"customer_id": c["client"], "top": 15}))
    text = json.dumps(outputs, ensure_ascii=False)
    assert not any(label in text for label in labels)


# --- Garde-fous ------------------------------------------------------------------------------

def test_extract_numbers_french_formats() -> None:
    values = [n.value for n in extract_numbers(
        "**2 002** départs, 116 162 $, 5,13 %, 0.6955, D79 et 3G ignorés, −43 990 $")]
    assert values == [2002, 116162, 5.13, 0.6955, 43990]


def test_guardrails_tolerance_and_warnings() -> None:
    results = [{"churners": 2002.24, "revenu": 116162.44, "part": 0.0513, "texte": "AUC 0,6955"}]
    ok = check_answer("Environ **2 002** départs, 116 000 $ en jeu, 5,13 % et 5 %, AUC 0,70.",
                      results)
    assert ok.ok, ok.warnings
    bad = check_answer("Nous éviterons 350 départs.", results)
    assert bad.unsupported_numbers == ["350"] and bad.warnings
    assert check_answer("Le client 1072931", results, "Pourquoi 1072931 ?").ok
    sensitive = check_answer("Les clients avec un enfant de 0 à 2 ans partent.", results)
    assert sensitive.sensitive_terms


# --- Boucle d'agent (faux LLM) ---------------------------------------------------------------

def test_agent_loop_calls_tools_then_answers() -> None:
    fake = ScriptedClient([
        ChatMessage("assistant", "", [ToolCall("get_kpis", {})]),
        lambda messages, tools: (
            f"Environ **{messages[-1].tool_result['churners_attendus_par_mois']:.0f}** départs "
            "attendus (estimation portefeuille)."),
    ])
    events = list(Agent(client=fake).run("Situation ?"))
    types = [e.type for e in events]
    assert types.index("tool_call") < types.index("tool_result") < types.index("done")
    done = events[-1].data
    assert [t["name"] for t in done["tool_calls"]] == ["get_kpis"]
    assert done["warnings"] == [] and "2002" in done["answer"]
    assert fake.calls[0][1] is not None       # outils proposés au premier tour


def test_agent_flags_invented_numbers() -> None:
    fake = ScriptedClient([ChatMessage("assistant", "", [ToolCall("get_kpis", {})]),
                           "Nous éviterons exactement 350 départs."])
    result = Agent(client=fake).ask("Combien de départs évités ?")
    assert any("350" in w for w in result.warnings)


def test_agent_limits_tool_calls_to_five() -> None:
    always_tools = [ChatMessage("assistant", "", [ToolCall("explain_method", {"topic": "auc"}),
                                                  ToolCall("explain_method", {"topic": "lift"})])
                    for _ in range(4)]
    fake = ScriptedClient([*always_tools, "Réponse finale."])
    result = Agent(client=fake).ask("Méthode ?")
    assert len(result.tool_calls) == 5
    assert any("Limite de 5" in w for w in result.warnings)
    assert fake.calls[-1][1] is None           # dernier tour : outils retirés


def test_agent_keeps_last_ten_history_messages() -> None:
    fake = ScriptedClient(["Réponse finale."])
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
               for i in range(30)]
    Agent(client=fake).ask("Nouvelle question", history)
    sent = fake.calls[0][0]
    assert len(sent) == 11 and sent[0].content == "message 20"


def test_agent_falls_back_to_demo_on_quota() -> None:
    fake = ScriptedClient([LLMError("quota", "RESOURCE_EXHAUSTED")])
    events = list(Agent(client=fake).run("Quelle est la situation globale du portefeuille ?"))
    error = next(e for e in events if e.type == "error")
    assert error.data["recoverable"] and error.data["kind"] == "quota"
    done = events[-1].data
    assert done["provider"] == "demo" and "429" in done["warnings"][0]
    assert [t["name"] for t in done["tool_calls"]] == ["get_kpis"]


def test_agent_without_fallback_reports_error() -> None:
    fake = ScriptedClient([LLMError("auth")])
    events = list(Agent(client=fake, fallback=False).run("Situation ?"))
    assert events[-1].type == "error" and not events[-1].data["recoverable"]
    assert "clé" in events[-1].data["message"]


# --- Mode démonstration ----------------------------------------------------------------------

@pytest.mark.parametrize(("question", "tools"), [
    ("Quelle est la situation globale du portefeuille ?", ["get_kpis"]),
    ("Qui sont les clients à risque à contacter en priorité ?", ["list_at_risk"]),
    (f"Pourquoi le client {CUSTOMER} est-il à risque ?", ["get_customer"]),
    ("Quels segments concentrent le risque ?", ["segment_stats"]),
    ("Quels sont les principaux facteurs de churn ?", ["global_drivers"]),
    ("Que donnerait une campagne sur 10 % avec 20 % de succès ?", ["simulate_campaign"]),
    ("Combien de départs allons-nous éviter ?", ["get_kpis", "explain_method"]),
    ("Le modèle est-il fiable ? Quelle est son AUC ?", ["explain_method"]),
    ("Quelle est la météo demain ?", []),
    ("Les clients mariés partent-ils plus ?", []),
])
def test_demo_scenarios(question: str, tools: list[str]) -> None:
    result = Agent(client=DemoClient()).ask(question)
    assert [t.name for t in result.tool_calls] == tools
    assert result.warnings == [] and result.answer
    assert result.provider == "demo"


def test_demo_scenario_matching_is_deterministic() -> None:
    assert match_scenario("Combien de départs allons-nous éviter avec une campagne ?").key == \
        "avoided"
    assert match_scenario("Parle-moi de football") is None


# --- Endpoints (mode démonstration) ----------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from api.dependencies import AssistantClient, get_assistant_client
    from api.main import app

    app.dependency_overrides[get_assistant_client] = lambda: AssistantClient(
        DemoClient(), "tests : mode démonstration")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_chat_sse_stream(client) -> None:
    from api.schemas import ChatAnswer

    r = client.post("/api/chat", json={
        "message": "Quelle est la situation globale du portefeuille ?",
        "history": [{"role": "user", "content": "Bonjour"},
                    {"role": "assistant", "content": "Bonjour !"}]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    kinds = [e for e, _ in events]
    assert kinds[0] == "tool_call" and "tool_result" in kinds and "token" in kinds
    assert kinds[-1] == "done"
    done = ChatAnswer.model_validate(events[-1][1])
    assert done.provider == "demo" and done.tool_calls[0].name == "get_kpis"
    assert "".join(d["text"] for e, d in events if e == "token").strip() == done.answer
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_customer_ai_endpoints(client) -> None:
    from api.schemas import AdvisorExplanation, RetentionMessage

    expl = AdvisorExplanation.model_validate(
        client.post(f"/api/customers/{CUSTOMER}/explain-ai").json())
    sentences = [s for s in expl.text.split(". ") if s.strip()]
    assert 3 <= len(sentences) <= 5 and "selon le modèle" in expl.text.lower()
    assert expl.warnings == []
    msg = RetentionMessage.model_validate(
        client.post(f"/api/customers/{CUSTOMER}/retention-message").json())
    assert msg.sms_length <= 300 and len(msg.sms) == msg.sms_length
    assert not extract_numbers(msg.sms + msg.email_body) and msg.warnings == []
    assert msg.action == "Offre de réengagement" and "engagement" in msg.sms
    for path in ("explain-ai", "retention-message"):
        r = client.post(f"/api/customers/999/{path}")
        assert r.status_code == 404 and "introuvable" in r.json()["detail"]


def test_summary_and_status(client) -> None:
    from api.schemas import AssistantStatus, ExecutiveSummary

    first = ExecutiveSummary.model_validate(client.get("/api/summary").json())
    assert 4 <= len(first.bullets) <= 5 and first.warnings == []
    assert ExecutiveSummary.model_validate(client.get("/api/summary").json()).cached
    status = AssistantStatus.model_validate(client.get("/api/assistant/status").json())
    assert status.provider == "demo" and not status.live_llm
    assert status.max_tool_calls == 5
