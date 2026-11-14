"""Hidden-death finder: reports whose text says the patient died but which are not coded as deaths.

Usage:
  python -m pipeline.deaths sample     # write eval/to_label.csv (the reports to label)
  python -m pipeline.deaths train      # train on eval/labels.csv, print and save metrics
  python -m pipeline.deaths score      # score every report not coded as a death, fill the database

How it works: each narrative is cut into short passages. A small sentence-embedding model turns
each passage into a vector, and logistic regression gives the probability that the passage says
this patient died. A report's score is its highest passage score.

Every report not coded as a death is scored, not only those containing a death-related word, so the
model can find wording a word list does not cover.
"""
import argparse
import csv
import json
import os
import pickle
import random
import re

import numpy as np

from .store import connect

HERE = os.path.dirname(__file__)
EVAL = os.path.join(HERE, "..", "eval")
TO_LABEL = os.path.join(EVAL, "to_label.csv")
LABELS = os.path.join(EVAL, "labels.csv")          # report_number, label (1/0), quote, source
METRICS = os.path.join(EVAL, "death_metrics.json")
MODEL = os.path.join(HERE, "..", "data", "death_model.pkl")
EMBEDDER = "sentence-transformers/all-MiniLM-L6-v2"   # 80 MB, runs on a laptop CPU
MAX_CHARS, MAX_PASSAGES = 500, 10

# Broad on purpose: it also matches "the battery expired" and "risk of death".
DEATH_WORDS = re.compile(
    r"\b(died|dies|dead|death|deceased|expired?|expir\w+|passed away|fatal\w*|demise|did not survive|"
    r"not survive|not be revived|unable to revive|could not be resuscitated|resuscitation (was |efforts? )?"
    r"(were |was )?(unsuccessful|ceased|stopped|terminated)|pronounced|autopsy|succumbed|mortality)\b", re.I)


PATIENT_LIVED = re.compile(r"surviv|resuscitat|recovered|discharged|transported|stable|no (adverse|harm|injur)", re.I)
# Wording that may describe a death without using a death word; kept out of the assumed negatives.
UNCLEAR_OUTCOME = re.compile(r"not (be |been )?(resuscitat|reviv)|unsuccessful|ceased|asystole|outcome (is|was) unknown", re.I)


def has_death_word(text: str) -> bool:
    return bool(DEATH_WORDS.search(text or ""))


def passages(narrative: str) -> list[str]:
    """Cut a narrative into passages of whole sentences, about 500 characters each.

    The event description goes first: it is where the outcome is usually stated.
    """
    parts = re.split(r"\n(?=\[)", narrative or "")
    parts.sort(key=lambda p: 0 if p.startswith("[Description") else 1)
    out = []
    for part in parts:
        text = re.sub(r"^\[[^\]]*\]\s*", "", part)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        cur = ""
        for sent in re.split(r"(?<=[.;])\s+", text):
            while len(sent) > MAX_CHARS:                 # a run-on sentence: cut it hard
                out.append(sent[:MAX_CHARS]); sent = sent[MAX_CHARS:]
            if cur and len(cur) + len(sent) + 1 > MAX_CHARS:
                out.append(cur); cur = sent
            else:
                cur = f"{cur} {sent}".strip()
        if cur:
            out.append(cur)
    return out[:MAX_PASSAGES]


_embedder = None


def embed(texts: list[str]) -> np.ndarray:
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBEDDER)
    return _embedder.encode(texts, batch_size=64, normalize_embeddings=True,
                            show_progress_bar=len(texts) > 5000, convert_to_numpy=True)


class Features:
    """Passage -> features: the sentence embedding plus counts of short word sequences.

    The embedding carries meaning. The word sequences carry negation, which small embedding models
    blur: "the patient survived" and "the patient did not survive" land close together.
    """

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.tfidf = TfidfVectorizer(ngram_range=(1, 3), min_df=2, max_features=60000,
                                     sublinear_tf=True, lowercase=True)

    def fit(self, texts):
        self.tfidf.fit(texts)
        return self

    def transform(self, texts):
        from scipy.sparse import csr_matrix, hstack
        return hstack([csr_matrix(embed(texts)), self.tfidf.transform(texts)]).tocsr()


def load_model() -> dict:
    """Load the saved classifier. Training runs as `python -m pipeline.deaths`, so the pickle names its
    feature class as __main__.Features; make that name resolve from any entry point."""
    import __main__
    if not hasattr(__main__, "Features"):
        __main__.Features = Features
    with open(MODEL, "rb") as f:
        return pickle.load(f)


def ensure_columns(con):
    have = {r[1] for r in con.execute("PRAGMA table_info(reports)")}
    for col, kind in [("death_excerpt", "TEXT"), ("death_word", "INTEGER"), ("outcomes", "TEXT"),
                      ("patient_problems", "TEXT")]:
        if col not in have:
            con.execute(f"ALTER TABLE reports ADD COLUMN {col} {kind}")
    con.commit()


# ---------------------------------------------------------------- sample

def sample(n_word: int, n_noword: int, n_coded: int, seed: int = 0):
    """Pick the reports to label: mostly ones with a death-related word (where the hard cases are),
    plus random reports without one and some coded deaths, so the labels cover the whole range."""
    con = connect()
    rng = random.Random(seed)
    rows = con.execute("SELECT report_number, product_code, event_type, narrative FROM reports "
                       "WHERE length(narrative) > 40").fetchall()
    word, noword, coded = [], [], []
    for r in rows:
        if r["event_type"] == "Death":
            coded.append(r)
        elif has_death_word(r["narrative"]):
            word.append(r)
        else:
            noword.append(r)
    picked = ([(r, "death_word") for r in rng.sample(word, min(n_word, len(word)))] +
              [(r, "no_death_word") for r in rng.sample(noword, min(n_noword, len(noword)))] +
              [(r, "coded_death") for r in rng.sample(coded, min(n_coded, len(coded)))])
    rng.shuffle(picked)
    os.makedirs(EVAL, exist_ok=True)
    with open(TO_LABEL, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["report_number", "product_code", "pool", "narrative"])
        for r, pool in picked:
            w.writerow([r["report_number"], r["product_code"], pool, r["narrative"]])
    print(f"not coded as death: {len(word)} with a death word, {len(noword)} without; coded deaths: {len(coded)}")
    print(f"wrote {len(picked)} reports to {TO_LABEL}")


# ---------------------------------------------------------------- train

def gold_numbers() -> set:
    path = os.path.join(EVAL, "gold_key.csv")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {r["report_number"] for r in csv.DictReader(f)}


def load_labels() -> list[dict]:
    with open(LABELS, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Reports in the hand-check set are never used for training or threshold choice.
    rows = [r for r in rows if r["report_number"] not in gold_numbers()]
    con = connect()
    out = []
    for r in rows:
        rep = con.execute("SELECT narrative, event_type FROM reports WHERE report_number=?",
                          (r["report_number"],)).fetchone()
        if rep and r["label"] in ("0", "1"):
            out.append({"id": r["report_number"], "y": int(r["label"]), "quote": r.get("quote", ""),
                        "source": r.get("source", ""), "narrative": rep["narrative"],
                        "coded_death": rep["event_type"] == "Death"})
    return out


def training_passages(row: dict) -> list[tuple[str, int]]:
    """A 'no' report: every passage is a negative. A 'yes' report: only the passage that holds the
    quoted evidence is a positive, because the other passages may say nothing about the outcome."""
    ps = passages(row["narrative"])
    if not row["y"]:
        return [(p, 0) for p in ps]
    quote = re.sub(r"\s+", " ", row["quote"] or "").strip().lower()
    strong = lambda p: any(not m.group(0).lower().startswith("expir") for m in DEATH_WORDS.finditer(p))
    hits = [p for p in ps if quote and quote[:60] in p.lower()] or [p for p in ps if strong(p)]
    return [(p, 1) for p in hits[:2]]


def distant_rows(n: int, seed: int, exclude: set) -> list[dict]:
    """Free training examples that need no labelling.

    Positives: reports the FDA already codes as deaths whose text uses a death-related word.
    Negatives: reports not coded as deaths, with no death-related word and no death outcome.
    These are only ever used for training, never for measuring accuracy.
    """
    con = connect()
    rng = random.Random(seed)
    rows = con.execute("SELECT report_number, product_code, event_type, outcomes, narrative FROM reports "
                       "WHERE length(narrative) > 40").fetchall()
    pools = {}      # (product code, kind) -> rows.  Sampling per pool stops one device type or one
    for r in rows:  # kind of report from swamping the rest.
        if r["report_number"] in exclude:
            continue
        word = DEATH_WORDS.search(r["narrative"])
        if r["event_type"] == "Death" and word and not word.group(0).lower().startswith("expir"):
            kind, y = "coded_death", 1
        elif (r["event_type"] != "Death" and not word and "Death" not in (r["outcomes"] or "")
              and not UNCLEAR_OUTCOME.search(r["narrative"])):
            # Reports about a patient who lived are the negatives the model most needs to see.
            kind, y = ("patient_lived" if PATIENT_LIVED.search(r["narrative"]) else
                       "injury" if r["event_type"] == "Injury" else "no_death_word"), 0
        else:
            continue
        pools.setdefault((r["product_code"], kind), []).append(
            {"id": r["report_number"], "y": y, "quote": "", "narrative": r["narrative"],
             "source": "coded_death" if y else "assumed_negative", "coded_death": bool(y)})
    codes = sorted({c for c, _ in pools})
    out = []
    for (code, kind), pool in sorted(pools.items()):
        # take three times as many "patient lived" reports: they are rare and they are the hard cases
        want = (3 if kind == "patient_lived" else 1) * n // len(codes)
        out += rng.sample(pool, min(want, len(pool)))
    return out


def limit_templates(pairs: list[tuple[str, int]], per_template: int = 12) -> list[tuple[str, int]]:
    """Manufacturers reuse stock sentences thousands of times. Keep a few copies of each."""
    seen, out = {}, []
    for p, y in pairs:
        key = (re.sub(r"[^a-z]+", " ", p.lower())[:70], y)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= per_template:
            out.append((p, y))
    return out


def train(test_share: float = 0.4, n_distant: int = 1500, seed: int = 0):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, precision_recall_curve

    rows = load_labels()
    rng = random.Random(seed)
    rng.shuffle(rows)
    # Hand-checked rows are always test rows. The rest is split at random, by report.
    gold = [r for r in rows if r["source"] == "hand"]
    rest = [r for r in rows if r["source"] != "hand"]
    cut = int(len(rest) * test_share)
    test, fit = rest[:cut] + gold, rest[cut:]
    fit = fit + distant_rows(n_distant, seed, {r["id"] for r in rows})

    pairs = limit_templates([pl for r in fit for pl in training_passages(r)])
    feats = Features().fit([p for p, _ in pairs])
    X = feats.transform([p for p, _ in pairs])
    y = np.array([l for _, l in pairs])
    clf = LogisticRegression(C=4.0, class_weight="balanced", max_iter=3000, solver="liblinear").fit(X, y)

    def report_scores(rs):
        ps = [passages(r["narrative"]) or [""] for r in rs]
        prob = clf.predict_proba(feats.transform([p for group in ps for p in group]))[:, 1]
        out, i = [], 0
        for group in ps:
            out.append(float(prob[i:i + len(group)].max())); i += len(group)
        return np.array(out)

    def measure(rs, threshold):
        if not rs:
            return None
        s, t = report_scores(rs), np.array([r["y"] for r in rs])
        pred = s >= threshold
        tp, fp, fn = int((pred & (t == 1)).sum()), int((pred & (t == 0)).sum()), int((~pred & (t == 1)).sum())
        return {"n": len(rs), "positives": int(t.sum()), "tp": tp, "fp": fp, "fn": fn,
                "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                "recall": round(tp / (tp + fn), 3) if tp + fn else None}

    # The question that matters is asked of reports NOT coded as deaths, so measure there.
    uncoded = [r for r in test if not r["coded_death"]]
    s, t = report_scores(uncoded), np.array([r["y"] for r in uncoded])
    prec, rec, thr = precision_recall_curve(t, s)
    ok = [i for i in range(len(thr)) if prec[i] >= 0.90]
    threshold = float(thr[ok[0]]) if ok else 0.9      # lowest threshold that reaches 90% precision
    word_only = lambda rs: {"precision": round(float(np.mean([r["y"] for r in rs if has_death_word(r["narrative"])])), 3),
                            "recall": round(sum(r["y"] for r in rs if has_death_word(r["narrative"])) /
                                            max(1, sum(r["y"] for r in rs)), 3)}
    metrics = {
        "labelled_reports": len(rows), "training_reports": len(fit), "training_passages": len(pairs),
        "threshold": round(threshold, 3),
        "test_not_coded_as_death": measure(uncoded, threshold),
        "test_average_precision": round(float(average_precision_score(t, s)), 3),
        "baseline_any_death_word_on_same_test": word_only(uncoded),
        "hand_checked_only": measure([r for r in gold if not r["coded_death"]], threshold),
        "label_sources": {k: sum(r["source"] == k for r in rows) for k in sorted({r["source"] for r in rows})},
    }
    with open(MODEL, "wb") as f:
        pickle.dump({"clf": clf, "feats": feats, "threshold": threshold, "embedder": EMBEDDER}, f)
    with open(METRICS, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(json.dumps(metrics, indent=2))


# ---------------------------------------------------------------- score

def cached_embeddings(unique: list[str]) -> np.ndarray:
    """Embedding every passage takes about half an hour, and it does not change when the classifier
    is retrained. Keep the vectors on disk; only passages not seen before are embedded."""
    emb_path, key_path = os.path.join(HERE, "..", "data", "passage_emb.npy"), os.path.join(HERE, "..", "data", "passage_keys.pkl")
    old_keys, old = [], None
    if os.path.exists(emb_path) and os.path.exists(key_path):
        with open(key_path, "rb") as f:
            old_keys = pickle.load(f)
        old = np.load(emb_path, mmap_mode="r")
        if old_keys == unique:
            return old
    where = {k: i for i, k in enumerate(old_keys)}
    out = np.zeros((len(unique), 384), dtype=np.float16)
    known = [(i, where[p]) for i, p in enumerate(unique) if p in where]
    if known:
        dst, src = map(np.array, zip(*known))
        out[dst] = old[src]
    todo = [i for i, p in enumerate(unique) if p not in where]
    print(f"  {len(known)} passages reused from disk, {len(todo)} to embed", flush=True)
    for j in range(0, len(todo), 20000):
        part = todo[j:j + 20000]
        out[part] = embed([unique[i] for i in part])
        print(f"  embedded {min(j + 20000, len(todo))} of {len(todo)} new passages", flush=True)
    np.save(emb_path, out)
    with open(key_path, "wb") as f:
        pickle.dump(unique, f)
    return out


def score():
    """Score every report not coded as a death. Identical passages are embedded once."""
    con = connect()
    ensure_columns(con)
    m = load_model()
    clf, feats, threshold = m["clf"], m["feats"], m["threshold"]
    rows = con.execute("SELECT report_number, narrative FROM reports WHERE event_type != 'Death'").fetchall()
    per_report = [passages(r["narrative"]) for r in rows]
    unique = sorted({p for ps in per_report for p in ps})
    print(f"{len(rows)} reports, {sum(map(len, per_report))} passages, {len(unique)} distinct", flush=True)
    from scipy.sparse import csr_matrix, hstack
    emb = cached_embeddings(unique)
    prob = {}
    for i in range(0, len(unique), 50000):
        chunk = unique[i:i + 50000]
        X = hstack([csr_matrix(emb[i:i + 50000].astype(np.float32)), feats.tfidf.transform(chunk)]).tocsr()
        prob.update(zip(chunk, clf.predict_proba(X)[:, 1]))
        print(f"  scored {min(i + 50000, len(unique))} passages", flush=True)
    updates = []
    for r, ps in zip(rows, per_report):
        if not ps:
            updates.append((None, 0, None, 0, r["report_number"])); continue
        best = max(ps, key=prob.get)
        p = float(prob[best])
        updates.append((round(p, 4), int(p >= threshold), best if p >= threshold else None,
                        int(has_death_word(r["narrative"])), r["report_number"]))
    con.executemany("UPDATE reports SET death_prob=?, hidden_death=?, death_excerpt=?, death_word=? "
                    "WHERE report_number=?", updates)
    con.commit()
    q = lambda sql: con.execute(sql).fetchone()[0]
    summary = {
        "reports_scored": len(rows),
        "coded_deaths": q("SELECT COUNT(*) FROM reports WHERE event_type='Death'"),
        "hidden_deaths_flagged": q("SELECT COUNT(*) FROM reports WHERE hidden_death=1"),
        "flagged_without_any_death_word": q("SELECT COUNT(*) FROM reports WHERE hidden_death=1 AND death_word=0"),
        "flagged_where_outcome_field_says_death": q(
            "SELECT COUNT(*) FROM reports WHERE hidden_death=1 AND outcomes LIKE '%Death%'"),
        "outcome_field_says_death_but_not_flagged": q(
            "SELECT COUNT(*) FROM reports WHERE event_type!='Death' AND COALESCE(hidden_death,0)=0 "
            "AND outcomes LIKE '%Death%'"),
    }
    with open(os.path.join(EVAL, "death_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


def gold(seed: int = 7):
    """Write the hand-check set. Two people label it without seeing the model's answer.

    eval/gold_blind.csv  what the checkers open: the text and an empty "died" column.
    eval/gold_key.csv    where each report came from and its model score. Open only afterwards.
    The first 30 rows go to both checkers, to measure how often two people agree.
    """
    con = connect()
    rng = random.Random(seed)
    with open(LABELS, encoding="utf-8") as f:
        used = {r["report_number"] for r in csv.DictReader(f)}
    base = "SELECT report_number, product_code, narrative, death_prob, hidden_death FROM reports WHERE event_type != 'Death' AND "
    strata = [("flagged_by_model", "hidden_death = 1", 80),
              ("death_word_not_flagged", "death_word = 1 AND hidden_death = 0", 60),
              ("outcome_field_death_not_flagged", "outcomes LIKE '%Death%' AND hidden_death = 0", 30),
              ("random_other", "death_word = 0 AND hidden_death = 0", 30)]
    picked, seen = [], set(used)
    for name, where, n in strata:
        pool = [r for r in con.execute(base + where) if r["report_number"] not in seen]
        for code in ("MKJ", "BZD"):                      # half from each device type
            part = [r for r in pool if r["product_code"] == code]
            for r in rng.sample(part, min(n // 2, len(part))):
                seen.add(r["report_number"]); picked.append((name, r))
    rng.shuffle(picked)
    with open(os.path.join(EVAL, "gold_blind.csv"), "w", newline="", encoding="utf-8") as fb, \
         open(os.path.join(EVAL, "gold_key.csv"), "w", newline="", encoding="utf-8") as fk:
        wb, wk = csv.writer(fb), csv.writer(fk)
        wb.writerow(["row", "checker", "report_number", "died (1 = this patient died, 0 = no, ? = cannot tell)",
                     "note", "narrative"])
        wk.writerow(["row", "report_number", "stratum", "death_prob", "hidden_death"])
        rest = len(picked) - 30
        for i, (name, r) in enumerate(picked, 1):
            who = "both" if i <= 30 else ("A" if i <= 30 + rest // 2 else "B")
            wb.writerow([i, who, r["report_number"], "", "", r["narrative"]])
            wk.writerow([i, r["report_number"], name, r["death_prob"], r["hidden_death"]])
    print(f"wrote {len(picked)} reports to eval/gold_blind.csv (key in eval/gold_key.csv)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["sample", "train", "score", "gold"])
    ap.add_argument("--n-word", type=int, default=1400)
    ap.add_argument("--n-noword", type=int, default=400)
    ap.add_argument("--n-coded", type=int, default=200)
    args = ap.parse_args()
    if args.step == "sample":
        sample(args.n_word, args.n_noword, args.n_coded)
    elif args.step == "train":
        train()
    elif args.step == "gold":
        gold()
    else:
        score()


if __name__ == "__main__":
    main()
