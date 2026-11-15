"""Run the example questions once and save the results, so the Ask page can show them with ENABLE_ASK off.

    python -m agent.save_examples
"""
import json
import os

from .investigator import investigate

QUESTIONS = ["Which AEDs have the most deaths filed as malfunctions, and do their makers also report late?",
             "What do the reports say went wrong with the LIFEPAK CR2 when a patient died?",
             "Which CPAP machines have deaths filed as something else, and how sure can we be?"]
OUT = os.path.join(os.path.dirname(__file__), "examples.json")

if __name__ == "__main__":
    results = []
    for q in QUESTIONS:
        print("Q:", q, flush=True)
        r = investigate(q, on_step=lambda s: print("  ·", s, flush=True))
        print(f"  {r['seconds']} s, {len(r['citations'])} citations\n", flush=True)
        results.append(r)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print("saved", OUT)
