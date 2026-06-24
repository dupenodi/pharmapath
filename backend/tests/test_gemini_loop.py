from dataclasses import dataclass, field

import pytest

from app.agent import gemini_loop, loop
from app.agent.sessions import reset_session
from app.core.config import settings
from app.graph import live_enrich
from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import parse_ndc_records
from tests.test_ndc_ingestion import load_fixture


def build_test_graph():
    return build_graph(
        ndc_records=parse_ndc_records(load_fixture()),
        distributor_records=load_big3_distributors(),
        geography_records=load_geography_records(),
    )


@dataclass
class FakeFunctionCall:
    name: str
    args: dict


@dataclass
class FakePart:
    function_call: FakeFunctionCall | None = None


@dataclass
class FakeContent:
    role: str
    parts: list = field(default_factory=list)


@dataclass
class FakeCandidate:
    content: FakeContent


@dataclass
class FakeResponse:
    candidates: list
    text: str = ""


class FakeModels:
    def __init__(self, turns: list[FakeResponse]):
        self._turns = turns
        self.calls = 0

    async def generate_content(self, **kwargs):
        response = self._turns[self.calls]
        self.calls += 1
        return response


class FakeAio:
    def __init__(self, turns):
        self.models = FakeModels(turns)


class FakeGeminiClient:
    def __init__(self, turns):
        self.aio = FakeAio(turns)


@pytest.fixture(autouse=True)
def stub_openfda(monkeypatch):
    async def no_flags(name):
        return []

    monkeypatch.setattr(live_enrich, "fetch_enforcement", no_flags)


@pytest.mark.asyncio
async def test_gemini_loop_executes_tool_then_returns_final_text(monkeypatch):
    graph = build_test_graph()
    turns = [
        FakeResponse(
            candidates=[
                FakeCandidate(
                    content=FakeContent(
                        role="model",
                        parts=[
                            FakePart(
                                function_call=FakeFunctionCall(
                                    name="resolve_drug",
                                    args={"drug_name": "Butalbital, Acetaminophen and Caffeine"},
                                )
                            )
                        ],
                    )
                )
            ]
        ),
        FakeResponse(candidates=[FakeCandidate(content=FakeContent(role="model", parts=[]))], text="Found it."),
    ]
    fake_client = FakeGeminiClient(turns)
    monkeypatch.setattr(gemini_loop.genai, "Client", lambda api_key: fake_client)
    reset_session("gemini-session")

    result = await gemini_loop.run_gemini_turn(graph, "gemini-session", "find acetaminophen and caffeine")

    assert result["agent_response"] == "Found it."
    assert result["tool_calls"][0]["name"] == "resolve_drug"
    assert "Agent did not call render_component" in " ".join(result["warnings"])


@pytest.mark.asyncio
async def test_gemini_loop_captures_render_component_output(monkeypatch):
    graph = build_test_graph()
    turns = [
        FakeResponse(
            candidates=[
                FakeCandidate(
                    content=FakeContent(
                        role="model",
                        parts=[
                            FakePart(
                                function_call=FakeFunctionCall(
                                    name="render_component",
                                    args={"component": "risk_card", "data": {"risk": "low"}},
                                )
                            )
                        ],
                    )
                )
            ]
        ),
        FakeResponse(candidates=[FakeCandidate(content=FakeContent(role="model", parts=[]))], text="Here's the risk summary."),
    ]
    fake_client = FakeGeminiClient(turns)
    monkeypatch.setattr(gemini_loop.genai, "Client", lambda api_key: fake_client)
    reset_session("gemini-session-2")

    result = await gemini_loop.run_gemini_turn(graph, "gemini-session-2", "is this drug at risk?")

    assert result["component"] == "risk_card"
    assert result["component_data"] == {"risk": "low"}
    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_dispatcher_routes_to_gemini_when_configured(monkeypatch):
    graph = build_test_graph()

    async def fake_gemini_turn(graph, session_id, message):
        return {"agent_response": "from gemini", "component": None, "component_data": None, "tool_calls": [], "warnings": []}

    monkeypatch.setattr(loop, "run_gemini_turn", fake_gemini_turn)
    monkeypatch.setattr(settings, "agent_provider", "gemini")

    result = await loop.run_agent_turn(graph, "dispatch-session", "hello")

    assert result["agent_response"] == "from gemini"
    monkeypatch.setattr(settings, "agent_provider", "anthropic")
