"""The Investigator end to end with a scripted model: no API key, no network.

The scripted model plays the agent's turns (plan, call a tool, write the case file, answer), so this checks
our wiring: the tools run on the real data, the file is collected, and the citation check works.
"""
from typing import Any

import pytest

pytest.importorskip("deepagents")          # the Investigator is optional; skip its tests if it is not installed

from conftest import needs_data  # noqa: E402
from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402

from agent.investigator import check_citations, investigate  # noqa: E402

MEMO = ("## Answer\nThe LIFEPAK CR2 has reports that describe a death but were filed as a malfunction.\n\n"
        "## Findings\n- The patient did not survive [report 0003015876-2025-01542].\n"
        "- A made-up citation for the check [report 0000000000-2025-00000].\n")


class Scripted(BaseChatModel):
    script: list = []
    idx: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        msg = self.script[self.idx] if self.idx < len(self.script) else AIMessage(content=MEMO)
        self.idx += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def call(i, name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}"}])


@needs_data
def test_investigation_runs_tools_writes_the_case_file_and_checks_citations():
    model = Scripted(script=[
        call(1, "write_todos", todos=[{"content": "Find the device", "status": "in_progress"}]),
        call(2, "search_devices", query="lifepak cr2"),
        call(3, "hidden_death_reports", device_key="physio--lifepak-cr2-defibrillator", limit=2),
        call(4, "write_file", file_path="/case_file.md", content=MEMO),
        AIMessage(content=MEMO),
    ])
    result = investigate("What happened with the LIFEPAK CR2?", model=model)
    assert "## Answer" in result["memo"]
    assert any(s.startswith("Plan:") for s in result["steps"])
    assert any(s.startswith("hidden_death_reports(") for s in result["steps"])
    cites = {c["report_number"]: c for c in result["citations"]}
    assert cites["0003015876-2025-01542"]["exists"] and cites["0003015876-2025-01542"]["states_death"]
    assert not cites["0000000000-2025-00000"]["exists"]          # an invented report number is caught


@needs_data
def test_citation_check_on_plain_text():
    out = check_citations("See [report 0003015876-2025-01542] and [report 1234567-2020-99999].")
    assert [c["exists"] for c in out] == [True, False]
