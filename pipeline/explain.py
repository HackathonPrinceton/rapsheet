"""Explain every hidden-death flag, so a reader can see why the model said "this patient died".

Usage:  python -m pipeline.explain        # writes eval/explanations.json

For each flagged report it records:
  - the passage the model scored highest (what it was reading)
  - the words and phrases that pushed the score up, and those that pushed it down. The model is a
    logistic regression, so these contributions are exact, not an approximation: for a word, its
    weight times how strongly it appears in the passage
  - how much came from the overall meaning of the sentence (the sentence-embedding part)
  - the two most similar reports that were confirmed as deaths, by a person or by a large model
  - three witnesses: what the FDA's event type says, what its patient-outcome field says, and what the
    text says

It also records how often a score in each range turned out to be right, using reports labelled
without seeing the model's answer, so "98% confident" can be read as "right N times out of M".

The file is small and goes in the repo, so the page can show explanations on any laptop without
loading the model.
"""
import csv
import json
import os
import re

import numpy as np

from .deaths import EVAL, LABELS, embed, gold_numbers, load_model, passages
from .store import connect

OUT = os.path.join(EVAL, "explanations.json")
STATES_DEATH = re.compile(r"did not survive|not survive|died|passed away|deceased|expired(?! battery| pads)|"
                          r"not (be )?resuscitated|pronounced|cause of death|patient death|death of", re.I)
EMB_DIM = 384


def confirmed_examples(con) -> list[dict]:
    """Reports confirmed as describing a death: hand-checked first, then large-model labels."""
    out = []
    hand = os.path.join(EVAL, "gold_A.csv")
    for path, source in ((hand, "checked by a person"), (os.path.join(EVAL, "gold_B.csv"), "checked by a person")):
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            col = next(c for c in rows[0] if c.lower().startswith("died"))
            out += [{"id": r["report_number"], "quote": "", "source": source} for r in rows if r[col].strip() == "1"]
    with open(LABELS, encoding="utf-8") as f:
        out += [{"id": r["report_number"], "quote": r["quote"], "source": "labelled by a large language model"}
                for r in csv.DictReader(f) if r["label"] == "1"]
    seen, uniq = set(), []
    for e in out:
        if e["id"] in seen:
            continue
        rep = con.execute("SELECT narrative, event_type, product_code FROM reports WHERE report_number=?",
                          (e["id"],)).fetchone()
        if not rep or rep["event_type"] == "Death":
            continue
        seen.add(e["id"])
        # Show the sentence that states the death (the quote, or the first sentence that says it).
        sentences = re.split(r"(?<=[.;!?])\s+", re.sub(r"\[[^\]]*\]|\s+", " ", rep["narrative"] or ""))
        quote = e["quote"].strip().lower()
        text = next((x for x in sentences if quote and quote[:40] in x.lower()), "") or \
            next((x for x in sentences if STATES_DEATH.search(x)), "") or e["quote"] or sentences[0]
        uniq.append(dict(e, text=text.strip()[:260], product_code=rep["product_code"]))
    return uniq


def calibration(con, threshold: float) -> dict:
    """How often each score range was right, on reports labelled without seeing the model's answer."""
    def bands(pairs):
        edges = [(0.0, 0.5), (0.5, 0.9), (0.9, threshold), (threshold, 1.01)]
        out = []
        for lo, hi in edges:
            ys = [y for p, y in pairs if p is not None and lo <= p < hi]
            out.append({"from": round(lo, 3), "to": round(min(hi, 1.0), 3), "n": len(ys), "deaths": sum(ys)})
        return out

    def pairs_from(rows):
        res = []
        for number, y in rows:
            r = con.execute("SELECT death_prob, event_type FROM reports WHERE report_number=?", (number,)).fetchone()
            if r and r["event_type"] != "Death":
                res.append((r["death_prob"], y))
        return res

    hand = []
    for path in (os.path.join(EVAL, "gold_A.csv"), os.path.join(EVAL, "gold_B.csv")):
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            col = next(c for c in rows[0] if c.lower().startswith("died"))
            hand += [(r["report_number"], int(r[col])) for r in rows if r[col].strip() in ("0", "1")]
    gold = gold_numbers()
    with open(LABELS, encoding="utf-8") as f:
        llm = [(r["report_number"], int(r["label"])) for r in csv.DictReader(f)
               if r["source"].startswith("llm_api") and r["report_number"] not in gold]
    return {"hand_checked": bands(pairs_from(dict(hand).items())),
            "large_model_labels": bands(pairs_from(llm))}


def main():
    con = connect()
    m = load_model()
    clf, feats, threshold = m["clf"], m["feats"], m["threshold"]
    coef = clf.coef_[0]
    w_emb, w_words = coef[:EMB_DIM], coef[EMB_DIM:]
    vocab = np.array(feats.tfidf.get_feature_names_out())

    flagged = con.execute("SELECT report_number, product_code, event_type, outcomes, death_prob, death_excerpt "
                          "FROM reports WHERE hidden_death = 1").fetchall()
    texts = [r["death_excerpt"] or "" for r in flagged]
    emb = embed(texts)
    words = feats.tfidf.transform(texts)

    examples = confirmed_examples(con)
    ex_emb = embed([e["text"] for e in examples])

    out = {}
    for i, r in enumerate(flagged):
        row = words.getrow(i)
        contrib = sorted(((float(w_words[j] * v), str(vocab[j])) for j, v in zip(row.indices, row.data)),
                         reverse=True)
        up = [{"term": t, "weight": round(c, 2)} for c, t in contrib if c > 0][:6]
        down = [{"term": t, "weight": round(c, 2)} for c, t in reversed(contrib) if c < 0][:4]
        meaning = float(emb[i] @ w_emb)
        sims = ex_emb @ emb[i]
        near = []
        for j in np.argsort(-sims):
            if examples[j]["id"] == r["report_number"]:
                continue
            near.append({"report_number": examples[j]["id"], "text": examples[j]["text"],
                         "source": examples[j]["source"], "similarity": round(float(sims[j]), 2)})
            if len(near) == 2:
                break
        out[r["report_number"]] = {
            "prob": r["death_prob"],
            "passage": r["death_excerpt"],
            "words_up": up, "words_down": down,
            "meaning": round(meaning, 2), "words_total": round(sum(c for c, _ in contrib), 2),
            "baseline": round(float(clf.intercept_[0]), 2),
            "similar_confirmed": near,
            "witnesses": {"event_type": r["event_type"],
                          "outcome_field_says_death": "Death" in (r["outcomes"] or ""),
                          "text_says_death": True},
        }

    top = np.argsort(w_words)
    meta = {
        "threshold": round(threshold, 4),
        "flagged": len(out),
        "global_words_up": [str(vocab[j]) for j in top[-15:][::-1]],
        "global_words_down": [str(vocab[j]) for j in top[:15]],
        "calibration": calibration(con, threshold),
        "confirmed_examples": len(examples),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "reports": out}, f, indent=1)
    print(f"explained {len(out)} flagged reports -> {OUT}")
    print(json.dumps(meta["calibration"], indent=1))


if __name__ == "__main__":
    main()
