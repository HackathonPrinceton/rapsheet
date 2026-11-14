"""Label report narratives with a large language model, to train and test the small classifier.

Usage:
  python -m pipeline.label                      # label the reports in eval/to_label.csv
  python -m pipeline.label --top-noword 300     # label the model's top-scoring reports that contain
                                                # no death-related word (checks what keywords miss)
  python -m pipeline.label --limit 50           # try a small batch first

Results are appended to eval/labels.csv, so a stopped run can be restarted. Needs ANTHROPIC_API_KEY.
These labels are a starting point: a hand-checked sample is what the accuracy figures rest on.
"""
import argparse
import csv
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from .deaths import LABELS, TO_LABEL, gold_numbers
from .store import connect

load_dotenv()
MODEL = os.environ.get("LABEL_MODEL", "claude-opus-5-5")

INSTRUCTIONS = """You are labelling FDA medical device adverse event reports for a research project.

Question: does the report text say that THE PATIENT IN THIS EVENT DIED?

Pick one category:
- died: the text states this patient died, in any wording (did not survive, expired, passed away,
  could not be resuscitated, resuscitation efforts were stopped, was pronounced, is deceased).
  It does not matter whether the device caused the death.
- dead_before_device_use: the patient was already dead when the device was applied
  (for example a monitor attached to confirm death).
- not_this_patient: a death is mentioned, but of someone else (a relative, another patient).
- hypothetical: death appears only as a risk, a regulatory phrase, or a denial
  ("could cause death or serious injury", "no death or injury was reported").
- equipment: the death-related word describes equipment ("dead battery", "pads expired", "quote expired").
- no_death: a patient is involved and the text says they lived, or says nothing about dying.
- no_patient: no patient was involved.
- unclear: the outcome cannot be determined from the text.

quote: for "died", the shortest exact phrase copied from the report that states the death.
Otherwise an empty string.
reason: one short sentence."""


class Label(BaseModel):
    category: Literal["died", "dead_before_device_use", "not_this_patient", "hypothetical",
                      "equipment", "no_death", "no_patient", "unclear"]
    quote: str
    reason: str


def label_one(client: anthropic.Anthropic, narrative: str) -> Label | None:
    response = client.messages.parse(
        model=MODEL,
        max_tokens=2000,
        output_config={"effort": "low"},
        system=INSTRUCTIONS,
        messages=[{"role": "user", "content": f"Report text:\n\n{narrative}"}],
        output_format=Label,
    )
    if response.stop_reason != "end_turn":      # refusal or cut off: leave this report unlabelled
        return None
    return response.parsed_output


def todo_rows(top_noword: int) -> list[tuple[str, str]]:
    if top_noword:
        con = connect()
        return [(r["report_number"], r["narrative"]) for r in con.execute(
            "SELECT report_number, narrative FROM reports WHERE event_type != 'Death' AND death_word = 0 "
            "ORDER BY death_prob DESC LIMIT ?", (top_noword,))]
    with open(TO_LABEL, encoding="utf-8") as f:
        return [(r["report_number"], r["narrative"]) for r in csv.DictReader(f)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-noword", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    done = set()
    if os.path.exists(LABELS):
        with open(LABELS, encoding="utf-8") as f:
            done = {r["report_number"] for r in csv.DictReader(f)}
    rows = [r for r in todo_rows(args.top_noword) if r[0] not in done and r[0] not in gold_numbers()]
    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} reports to label with {MODEL} ({len(done)} already labelled)")

    client = anthropic.Anthropic()
    lock = threading.Lock()
    new_file = not os.path.exists(LABELS)
    out = open(LABELS, "a", newline="", encoding="utf-8")
    writer = csv.writer(out)
    if new_file:
        writer.writerow(["report_number", "label", "quote", "source", "note"])
    counts = {"labelled": 0, "died": 0, "skipped": 0}
    source = "claude_api_top_noword" if args.top_noword else "claude_api"

    def work(row):
        number, narrative = row
        try:
            lab = label_one(client, narrative)
        except anthropic.RateLimitError:
            lab = None                          # the SDK already retried; pick it up on the next run
        except anthropic.APIStatusError as e:
            print(f"  {number}: API error {e.status_code}")
            lab = None
        except anthropic.APIConnectionError:
            lab = None
        with lock:
            if lab is None or lab.category == "unclear":
                counts["skipped"] += 1
                return
            died = int(lab.category == "died")
            writer.writerow([number, died, lab.quote if died else "", source, f"{lab.category}: {lab.reason}"])
            out.flush()
            counts["labelled"] += 1
            counts["died"] += died
            if counts["labelled"] % 100 == 0:
                print(f"  {counts['labelled']} labelled, {counts['died']} say the patient died", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, rows))
    out.close()
    print(counts)


if __name__ == "__main__":
    main()
