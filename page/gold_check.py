"""Hand-check the gold set one report at a time.

Run:  streamlit run page/gold_check.py --server.port 8502
Pick A or B at the top. Your answers are saved to eval/hand_check/checker_A.csv or checker_B.csv after every click,
so you can stop and come back. The model's scores are never shown (the check is blind), and
eval/hand_check/answer_key.csv is never opened here.
"""
import csv
import html
import os
import re

import streamlit as st

EVAL = os.path.join(os.path.dirname(__file__), "..", "eval")
BLIND = os.path.join(EVAL, "hand_check", "blind_set.csv")
DIED = "died (1 = this patient died, 0 = no, ? = cannot tell)"
RULES = """
**1 = died**: the text says **this patient** died.

**0 = did not die**, including:
- the patient was already dead before the device was used
- "could cause death", "risk of death", "no death was reported"
- someone else died, not this patient
- a correction saying an earlier "death" entry was a mistake

**? = can't tell**: the text does not say what happened to the patient.
"""

st.set_page_config(page_title="Gold set check", layout="wide")


@st.cache_data
def load_blind():
    with open(BLIND, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def out_path(checker: str) -> str:
    return os.path.join(EVAL, "hand_check", f"checker_{checker}.csv")


def load_answers(checker: str) -> dict:
    path = out_path(checker)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return {r["report_number"]: {"died": r[DIED], "note": r.get("note", "")} for r in csv.DictReader(f)}


def save_answers(checker: str, rows: list[dict], answers: dict) -> None:
    tmp = out_path(checker) + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "checker", "report_number", DIED, "note"])
        for r in rows:
            a = answers.get(r["report_number"], {})
            w.writerow([r["row"], r["checker"], r["report_number"], a.get("died", ""), a.get("note", "")])
    os.replace(tmp, out_path(checker))          # never leaves a half-written file


rows_all = load_blind()
with st.sidebar:
    checker = st.radio("I am checker", ["B", "A"], help="Mrudula is B, Krutika is A. Rows marked 'both' go to both.")
    st.markdown(RULES)

rows = [r for r in rows_all if r["checker"] in (checker, "both")]
answers = load_answers(checker)
done = sum(1 for r in rows if answers.get(r["report_number"], {}).get("died") in ("0", "1", "?"))

if "i" not in st.session_state or st.session_state.get("who") != checker:
    st.session_state.who = checker
    st.session_state.i = next((k for k, r in enumerate(rows)
                               if answers.get(r["report_number"], {}).get("died") not in ("0", "1", "?")), 0)
with st.sidebar:
    st.divider()
    jump = st.number_input("Go to report #", min_value=1, max_value=len(rows), value=None, step=1,
                           placeholder="type a number, press Enter")
    if jump and st.button("Go"):
        st.session_state.i = int(jump) - 1
    if st.button("Go to first unanswered"):
        st.session_state.i = next((k for k, x in enumerate(rows)
                                   if answers.get(x["report_number"], {}).get("died") not in ("0", "1", "?")), 0)
i = min(st.session_state.i, len(rows) - 1)
r = rows[i]
current = answers.get(r["report_number"], {})

st.progress(done / len(rows), text=f"Checker {checker}: {done} of {len(rows)} done · saved to eval/hand_check/checker_{checker}.csv")
st.subheader(f"Report {i + 1} of {len(rows)}  ·  {r['report_number']}" + ("  ·  (both)" if r["checker"] == "both" else ""))
if current.get("died"):
    st.caption(f"Your current answer: **{ {'1': 'Died', '0': 'Did not die', '?': 'Cannot tell'}[current['died']] }**")

PLAIN = {"Description of Event or Problem": "What happened, as first reported",
         "Additional Manufacturer Narrative": "Company's later update",
         "Manufacturer Evaluation Summary": "Company's test of the device"}


def sections(narrative: str) -> list[tuple[str, str]]:
    """'[Label] text [Label] text' -> [(label, text), ...]. Text without a label comes first, unlabelled."""
    parts = re.split(r"\[([^\]]{3,60})\]\s*", narrative or "")
    out = [("", parts[0].strip())] if parts[0].strip() else []
    out += [(parts[k].strip(), parts[k + 1].strip()) for k in range(1, len(parts) - 1, 2)]
    return out


updates = 0
for label, text in sections(r["narrative"]):
    if label == "Additional Manufacturer Narrative":
        updates += 1
    plain = PLAIN.get(label, "")
    if label == "Additional Manufacturer Narrative":
        plain = f"{plain} #{updates}"
    head = f"{html.escape(label)}" + (f" <span style='color:#6b7280; font-weight:400'>· {plain}</span>" if plain else "")
    st.markdown(
        f"<div style='margin:1.1rem 0 .3rem; font-weight:700; font-size:1rem; color:#2f3e6b'>{head}</div>"
        f"<div style='font-size:1.1rem; line-height:1.65; padding:.6rem .9rem; background:rgba(127,127,127,.07); "
        f"border-left:3px solid #9aa5c4; border-radius:4px'>{html.escape(text)}</div>",
        unsafe_allow_html=True)
st.caption("Updates are listed in the order the FDA data gives them, which is not always the order they were sent.")
st.divider()

note = st.text_input("Note (optional, for unclear cases)", value=current.get("note", ""), key=f"note-{checker}-{i}")


def answer(value: str):
    answers[r["report_number"]] = {"died": value, "note": note}
    save_answers(checker, rows, answers)
    st.session_state.i = min(i + 1, len(rows) - 1)


c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1, 1])
c1.button("1 · Died", on_click=answer, args=("1",), width="stretch")   # same style for all: no nudging
c2.button("0 · Did not die", on_click=answer, args=("0",), width="stretch")
c3.button("? · Can't tell", on_click=answer, args=("?",), width="stretch")
c4.button("◀ Back", on_click=lambda: st.session_state.update(i=max(i - 1, 0)), width="stretch")
c5.button("Skip ▶", on_click=lambda: st.session_state.update(i=min(i + 1, len(rows) - 1)), width="stretch")

if done == len(rows):
    st.success(f"All {len(rows)} done. Your file is eval/hand_check/checker_{checker}.csv. Send it to Krutika or push it.")
