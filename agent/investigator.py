"""The Rap Sheet Investigator: a deep agent that answers a question about device safety with a short,
cited case file.

    python -m agent.investigator "Which AEDs have the most deaths filed as malfunctions?"

How it works (LangChain deepagents):
  1. It plans with the built-in to-do list.
  2. It investigates with read-only tools over the FDA data (agent/tools.py).
  3. An evidence-checker subagent re-reads every report it plans to cite and confirms the report says
     what the claim says.
  4. It writes the case file to /case_file.md.
After the agent finishes, a plain code check confirms every cited report number exists in the FDA data
and, where a death is claimed, that the report text states one. The result is shown with the memo.

Settings (.env): AGENT_MODEL, a LangChain model string such as "provider:model-name". ENABLE_ASK=1 turns
the page on; it is off by default so a public page cannot spend API credit.
"""
import os
import re
import sys
import time

from dotenv import load_dotenv

from .tools import TOOLS, read_report, states_death

load_dotenv()
REPORT_NO = re.compile(r"\b\d{6,10}-\d{4}-\d{4,6}(?:-\d+)?\b")
MAX_STEPS = 80

SYSTEM_PROMPT = """You are the Rap Sheet Investigator. You answer questions about the safety record of medical
devices using public FDA adverse event reports and recalls for two device types: automated external
defibrillators (AEDs, product code MKJ) and CPAP/BiPAP machines (product code BZD), 2019 to 2026.

Work like an investigator:
1. Your FIRST tool call must be write_todos: a plan of 3 to 6 steps. Mark steps done with write_todos as
   you finish them, so the reader can follow your progress.
2. Use the tools to gather facts. Prefer a few well-chosen calls over many. Never invent a number, a
   device or a report number: every fact must come from a tool result.
3. Before writing, give the evidence-checker every report you intend to cite, with the claim each one
   supports. Drop or reword any claim it does not confirm.
4. Write the case file with write_file to /case_file.md, then reply with the same text.

The case file, in Markdown, under 350 words:
- No title line. Start directly with the sections below.
- "## Answer": two or three sentences that answer the question directly.
- "## Findings": bullet points. Every bullet cites at least one FDA report number in square brackets, like
  [report 0003015876-2025-01542], or names the tool figure it rests on.
- "## How sure we are": call method_accuracy and state the classifier's hand-checked precision and recall
  in plain words. Say that the count of deaths filed as something else is a lower bound.
- "## Limits": one or two bullets.

Rules that always apply:
- A report is an allegation. Write "reports describe a death", never "the device killed" or "caused".
- Never advise anyone to stop using a device. For AEDs, add: keep it in service unless the manufacturer
  says otherwise.
- Only these two device types are in the data. If asked about anything else, say so.
- "Reports rising" is a weak signal, not a prediction of a recall.
"""

CHECKER = {
    "name": "evidence-checker",
    "description": "Checks citations. Give it a list of claims, each with the FDA report numbers that support "
                   "it. It reads every report and says, for each claim, CONFIRMED or NOT CONFIRMED with a "
                   "short quote from the report.",
    "system_prompt": "You check citations in a safety memo. For each claim you are given, call read_report on "
                     "every report number listed and decide whether the report text supports the claim. Answer "
                     "with one line per claim: CONFIRMED or NOT CONFIRMED, the report number, and a quote of at "
                     "most 20 words from the narrative. Be strict: a claim that a patient died needs the "
                     "narrative to say this patient died.",
    "tools": [read_report],
}


def model_name() -> str:
    name = os.environ.get("AGENT_MODEL", "").strip()
    if not name:
        raise SystemExit("Set AGENT_MODEL in .env, for example a LangChain 'provider:model-name' string.")
    return name


def build(model=None):
    """The compiled deep agent. `model` can be a LangChain chat model object (tests pass a scripted one)."""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware
    # This deepagents version does not add the to-do planner on its own, so it is added here.
    return create_deep_agent(model or model_name(), TOOLS, system_prompt=SYSTEM_PROMPT, subagents=[CHECKER],
                             middleware=[TodoListMiddleware()], name="rapsheet-investigator")


def file_text(files: dict, path: str = "/case_file.md") -> str:
    """deepagents stores files in state as {"content": [lines] or str, ...}; return plain text."""
    f = (files or {}).get(path)
    if f is None:
        return ""
    content = f.get("content", f) if isinstance(f, dict) else f
    return "\n".join(content) if isinstance(content, list) else str(content)


def check_citations(memo: str) -> list[dict]:
    """Plain code, no model: does every cited report exist, and does a report cited next to a death claim
    actually state a death."""
    import json
    out = []
    for number in dict.fromkeys(REPORT_NO.findall(memo)):
        data = json.loads(read_report(number))
        if "error" in data:
            out.append({"report_number": number, "exists": False, "states_death": False, "fda_url": None})
            continue
        out.append({"report_number": number, "exists": True, "states_death": states_death(data["narrative"]),
                    "filed_as": data["filed_as"], "fda_url": data["fda_url"]})
    return out


def describe(update: dict) -> list[str]:
    """Readable progress lines from one streamed graph update."""
    lines = []
    for value in (update or {}).values():
        if not isinstance(value, dict):
            continue
        for msg in value.get("messages", []) or []:
            for call in getattr(msg, "tool_calls", None) or []:
                name, args = call.get("name"), call.get("args", {})
                if name == "write_todos":
                    todos = args.get("todos", [])
                    mark = {"completed": "✓", "in_progress": "→"}
                    lines.append("Plan: " + " · ".join(f"{mark.get(t.get('status'), '○')} {t.get('content', '')}"
                                                        for t in todos))
                elif name == "task":
                    lines.append(f"Asked the {args.get('subagent_type', 'subagent')} to check citations")
                elif name in ("write_file", "edit_file"):
                    lines.append(f"Writing {args.get('file_path', 'file')}")
                elif name not in ("read_file", "ls"):
                    short = ", ".join(f"{k}={str(v)[:40]}" for k, v in args.items())
                    lines.append(f"{name}({short})")
    return lines


def investigate(question: str, model=None, on_step=None) -> dict:
    """Run one investigation. Returns the memo, its citation check, the progress steps and the time taken."""
    agent = build(model)
    steps, state, start = [], {}, time.time()
    for update in agent.stream({"messages": [{"role": "user", "content": question}]},
                               config={"recursion_limit": MAX_STEPS}, stream_mode="updates"):
        for line in describe(update):
            steps.append(line)
            if on_step:
                on_step(line)
        for value in update.values():
            if isinstance(value, dict):
                if value.get("files"):
                    state.setdefault("files", {}).update(value["files"])
                if value.get("messages"):
                    state["last"] = value["messages"][-1]
    memo = file_text(state.get("files", {}))
    if not memo and state.get("last") is not None:
        content = getattr(state["last"], "content", "")
        memo = content if isinstance(content, str) else "".join(
            b.get("text", "") for b in content if isinstance(b, dict))
    return {"question": question, "memo": memo.strip(), "citations": check_citations(memo), "steps": steps,
            "seconds": round(time.time() - start, 1)}


def main():
    question = " ".join(sys.argv[1:]).strip() or "Which AEDs have the most deaths filed as malfunctions?"
    result = investigate(question, on_step=lambda s: print("  ·", s, flush=True))
    print("\n" + result["memo"] + "\n")
    ok = sum(c["exists"] for c in result["citations"])
    print(f"Citations: {ok} of {len(result['citations'])} report numbers found in the FDA data; "
          f"{sum(c['states_death'] for c in result['citations'])} state a death. {result['seconds']} s.")


if __name__ == "__main__":
    main()
