import json
from dataclasses import dataclass, field

import pytest

from app.agent import openai_loop
from app.agent.sessions import reset_session
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
class FakeFunction:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunction


@dataclass
class FakeMessage:
    content: str | None = None
    tool_calls: list | None = None

    def model_dump(self, exclude_none=True):
        d = {"role": "assistant", "content": self.content, "tool_calls": self.tool_calls}
        return {k: v for k, v in d.items() if not (exclude_none and v is None)}


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list


class FakeCompletions:
    def __init__(self, turns: list[FakeResponse]):
        self._turns = turns
        self.calls = 0

    async def create(self, **kwargs):
        response = self._turns[self.calls]
        self.calls += 1
        return response


class FakeChat:
    def __init__(self, turns):
        self.completions = FakeCompletions(turns)


class FakeOpenAIClient:
    def __init__(self, turns):
        self.chat = FakeChat(turns)


@pytest.fixture(autouse=True)
def stub_openfda(monkeypatch):
    async def no_flags(name):
        return []

    monkeypatch.setattr(live_enrich, "fetch_enforcement", no_flags)


@pytest.mark.asyncio
async def test_openai_loop_executes_tool_then_returns_final_text(monkeypatch):
    graph = build_test_graph()
    turns = [
        FakeResponse(
            choices=[
                FakeChoice(
                    message=FakeMessage(
                        tool_calls=[
                            FakeToolCall(
                                id="call_1",
                                function=FakeFunction(
                                    name="resolve_drug",
                                    arguments=json.dumps({"drug_name": "Butalbital, Acetaminophen and Caffeine"}),
                                ),
                            )
                        ]
                    )
                )
            ]
        ),
        FakeResponse(choices=[FakeChoice(message=FakeMessage(content="Found it."))]),
    ]
    fake_client = FakeOpenAIClient(turns)
    monkeypatch.setattr(openai_loop.openai, "AsyncOpenAI", lambda api_key: fake_client)
    reset_session("openai-session")

    result = await openai_loop.run_openai_turn(graph, "openai-session", "find acetaminophen and caffeine")

    assert result["agent_response"] == "Found it."
    assert result["tool_calls"][0]["name"] == "resolve_drug"
    assert "Agent did not call render_component" in " ".join(result["warnings"])


@pytest.mark.asyncio
async def test_openai_loop_captures_render_component_output(monkeypatch):
    graph = build_test_graph()
    turns = [
        FakeResponse(
            choices=[
                FakeChoice(
                    message=FakeMessage(
                        tool_calls=[
                            FakeToolCall(
                                id="call_1",
                                function=FakeFunction(
                                    name="render_component",
                                    arguments=json.dumps({"component": "risk_card", "data": {"risk": "low"}}),
                                ),
                            )
                        ]
                    )
                )
            ]
        ),
        FakeResponse(choices=[FakeChoice(message=FakeMessage(content="Here's the risk summary."))]),
    ]
    fake_client = FakeOpenAIClient(turns)
    monkeypatch.setattr(openai_loop.openai, "AsyncOpenAI", lambda api_key: fake_client)
    reset_session("openai-session-2")

    result = await openai_loop.run_openai_turn(graph, "openai-session-2", "is this drug at risk?")

    assert result["component"] == "risk_card"
    assert result["component_data"] == {"risk": "low"}
    assert result["warnings"] == []
