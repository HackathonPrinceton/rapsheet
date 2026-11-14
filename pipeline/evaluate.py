"""Score four ways of finding hidden deaths against the hand-checked gold set.

Usage:  python -m pipeline.evaluate            # needs eval/gold_A.csv and eval/gold_B.csv
        python -m pipeline.evaluate --no-llm   # skip the large-model comparison

Methods compared, all on the same hand-checked reports:
  1. death word      any death-related word in the text (what a keyword search gives)
  2. outcome field   the FDA's patient outcome field says "Death" (no text reading at all)
  3. classifier      our small trained model
  4. large model     Claude reading each report directly (the expensive reference)

The gold set over-samples the interesting reports, so each row is also weighted back to how common
its kind of report is in the full data. Both the plain and the weighted figures are written.
"""
import argparse
import csv
import json
import os

from .deaths import EVAL, has_death_word
from .store import connect

OUT = os.path.join(EVAL, "gold_results.json")


def read_gold(name: str) -> dict:
    path = os.path.join(EVAL, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    col = next(c for c in rows[0] if c.lower().startswith("died"))
    return {r["report_number"]: r[col].strip() for r in rows if r[col].strip() in ("0", "1", "?")}


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa: agreement between two people beyond what chance would give."""
    n = len(pairs)
    if not n:
        return None
    agree = sum(a == b for a, b in pairs) / n
    labels = {x for p in pairs for x in p}
    chance = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in labels)
    return round((agree - chance) / (1 - chance), 3) if chance < 1 else 1.0


def large_model_answers(rows: list[dict]) -> dict:
    """Claude's answer for each gold report, saved so a rerun costs nothing."""
    path = os.path.join(EVAL, "gold_large_model.csv")
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            done = {r["report_number"]: r["category"] for r in csv.DictReader(f)}
    todo = [r for r in rows if r["id"] not in done]
    if todo:
        import anthropic
        from concurrent.futures import ThreadPoolExecutor
        from .label import label_one
        client = anthropic.Anthropic()

        def work(r):
            try:
                lab = label_one(client, r["narrative"])
            except anthropic.APIError:
                lab = None
            return r["id"], (lab.category if lab else "unclear")

        with ThreadPoolExecutor(max_workers=8) as pool:
            done.update(pool.map(work, todo))
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["report_number", "category"])
            w.writerows(sorted(done.items()))
    return {k: int(v == "died") for k, v in done.items()}


def measure(rows: list[dict], pred: dict) -> dict:
    def pr(weight):
        tp = sum(weight(r) for r in rows if pred[r["id"]] and r["y"])
        fp = sum(weight(r) for r in rows if pred[r["id"]] and not r["y"])
        fn = sum(weight(r) for r in rows if not pred[r["id"]] and r["y"])
        return (round(tp / (tp + fp), 3) if tp + fp else None, round(tp / (tp + fn), 3) if tp + fn else None, tp, fp, fn)
    p, r, tp, fp, fn = pr(lambda _: 1)
    wp, wr, *_ = pr(lambda row: row["w"])
    return {"precision": p, "recall": r, "true_pos": tp, "false_pos": fp, "false_neg": fn,
            "weighted_precision": wp, "weighted_recall": wr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    a, b = read_gold("gold_A.csv"), read_gold("gold_B.csv")
    if not a and not b:
        raise SystemExit("No hand labels found. Save them as eval/gold_A.csv and eval/gold_B.csv.")
    with open(os.path.join(EVAL, "gold_key.csv"), encoding="utf-8") as f:
        key = {r["report_number"]: r for r in csv.DictReader(f)}
    with open(os.path.join(EVAL, "gold_strata.json"), encoding="utf-8") as f:
        strata = json.load(f)

    both = [(a[k], b[k]) for k in a if k in b]
    con = connect()
    rows, dropped = [], {"cannot_tell": 0, "checkers_disagree": 0}
    for number in sorted(set(a) | set(b)):
        answers = {x[number] for x in (a, b) if number in x}
        if "?" in answers:
            dropped["cannot_tell"] += 1
            continue
        if len(answers) > 1:
            dropped["checkers_disagree"] += 1
            continue
        rep = con.execute("SELECT product_code, narrative, outcomes, death_prob, hidden_death FROM reports "
                          "WHERE report_number = ?", (number,)).fetchone()
        cell = f"{key[number]['stratum']}|{rep['product_code']}"
        rows.append({"id": number, "y": int(answers.pop()), "narrative": rep["narrative"],
                     "outcomes": rep["outcomes"] or "", "hidden": rep["hidden_death"] or 0,
                     "w": strata["population"][cell] / strata["sampled"][cell]})

    methods = {
        "death word": {r["id"]: int(has_death_word(r["narrative"])) for r in rows},
        "outcome field": {r["id"]: int("Death" in r["outcomes"]) for r in rows},
        "classifier": {r["id"]: int(r["hidden"]) for r in rows},
        "classifier or outcome field": {r["id"]: int(r["hidden"] or "Death" in r["outcomes"]) for r in rows},
    }
    if not args.no_llm:
        methods["large model"] = large_model_answers(rows)

    result = {
        "gold_reports_used": len(rows), "say_patient_died": sum(r["y"] for r in rows), "dropped": dropped,
        "two_checkers": {"reports_both_labelled": len(both), "agreed": sum(x == y for x, y in both),
                         "kappa": kappa(both)},
        "methods": {name: measure(rows, pred) for name, pred in methods.items()},
        "note": "Weighted figures scale each report by how common its kind is in the full data. With few "
                "sampled reports standing for hundreds of thousands, weighted recall is a rough estimate.",
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
