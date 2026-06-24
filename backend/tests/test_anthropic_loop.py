from dataclasses import dataclass

import pytest

from app.agent import anthropic_loop
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
class FakeBlock:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict | None = None

    def model_dump(self):
        d = {"type": self.type}
        if self.type == "text":
            d["text"] = self.text
        else:
            d.update({"id": self.id, "name": self.name, "input": self.input})
        return d


@dataclass
class FakeResponse:
    content: list


class FakeMessages:
    def __init__(self, turns: list[list[FakeBlock]]):
        self._turns = turns
        self.calls = 0

    async def create(self, **kwargs):
        blocks = self._turns[self.calls]
        self.calls += 1
        return FakeResponse(content=blocks)


class FakeClient:
    def __init__(self, turns: list[list[FakeBlock]]):
        self.messages = FakeMessages(turns)

    def __call__(self, *args, **kwargs):
        return self


@pytest.fixture(autouse=True)
def stub_openfda(monkeypatch):
    async def no_flags(name):
        return []

    monkeypatch.setattr(live_enrich, "fetch_enforcement", no_flags)


@pytest.mark.asyncio
async def test_agent_loop_executes_tool_then_returns_final_text(monkeypatch):
    graph = build_test_graph()
    turns = [
        [FakeBlock(type="tool_use", id="t1", name="resolve_drug", input={"drug_name": "Butalbital, Acetaminophen and Caffeine"})],
        [FakeBlock(type="text", text="Found the drug and rendered a table.")],
    ]
    fake_client = FakeClient(turns)
    monkeypatch.setattr(anthropic_loop, "AsyncAnthropic", lambda api_key: fake_client)
    reset_session("test-session")

    result = await anthropic_loop.run_anthropic_turn(graph, "test-session", "find acetaminophen and caffeine")

    assert result["agent_response"] == "Found the drug and rendered a table."
    assert result["tool_calls"][0]["name"] == "resolve_drug"
    assert "Agent did not call render_component" in " ".join(result["warnings"])


@pytest.mark.asyncio
async def test_agent_loop_captures_render_component_output(monkeypatch):
    graph = build_test_graph()
    turns = [
        [
            FakeBlock(
                type="tool_use",
                id="t1",
                name="render_component",
                input={"component": "risk_card", "data": {"risk": "low"}},
            )
        ],
        [FakeBlock(type="text", text="Here's the risk summary.")],
    ]
    fake_client = FakeClient(turns)
    monkeypatch.setattr(anthropic_loop, "AsyncAnthropic", lambda api_key: fake_client)
    reset_session("test-session-2")

    result = await anthropic_loop.run_anthropic_turn(graph, "test-session-2", "is this drug at risk?")

    assert result["component"] == "risk_card"
    assert result["component_data"] == {"risk": "low"}
    assert result["warnings"] == []
