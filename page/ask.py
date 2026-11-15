"""Ask: the Rap Sheet Investigator.  Run:  streamlit run page/ask.py --server.port 8503

A question in, a short case file out, with every cited FDA report checked. Live questions run only when
ENABLE_ASK=1 is set in .env; otherwise the page shows saved example investigations, so a public page cannot
spend API credit.
"""
import json
import os
import re
import sys

import streamlit as st

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
from agent.investigator import REPORT_NO, investigate  # noqa: E402

EXAMPLES = os.path.join(ROOT, "agent", "examples.json")
ENABLED = os.environ.get("ENABLE_ASK", "0").strip() == "1"
QUESTIONS = ["Which AEDs have the most deaths filed as malfunctions, and do their makers also report late?",
             "What do the reports say went wrong with the LIFEPAK CR2 when a patient died?",
             "Which CPAP machines have deaths filed as something else, and how sure can we be?"]
BLUE, RED, GREY, LINE = "#2563eb", "#dc2626", "#6b7280", "#e5e7eb"

st.set_page_config(page_title="Rap Sheet · Ask", page_icon="◉", layout="wide")
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"], p, li {{ font-family: 'Inter', sans-serif; }}
#MainMenu, footer, header [data-testid="stToolbar"] {{ visibility: hidden; }}
.block-container {{ padding: 1rem 2.2rem 2rem; max-width: 100%; }}
.logo {{ font-weight: 800; font-size: 1.15rem; display: flex; align-items: center; gap: .45rem; }}
.logo .dot {{ width: .8rem; height: .8rem; border-radius: 50%; background: {BLUE}; box-shadow: 0 0 0 4px #dbeafe; }}
.sub {{ color: {GREY}; font-size: .9rem; margin: .2rem 0 1rem; }}
.memo {{ background: white; border: 1px solid {LINE}; border-radius: 12px; padding: 1rem 1.3rem; }}
.ptitle {{ font-size: .78rem; font-weight: 700; color: {GREY}; text-transform: uppercase; letter-spacing: .06em; margin: .2rem 0 .5rem; }}
.cite {{ display: flex; gap: .5rem; align-items: center; font-size: .82rem; padding: .35rem 0; border-bottom: 1px solid #f1f5f9; }}
.ok {{ color: #047857; font-weight: 700; }} .bad {{ color: {RED}; font-weight: 700; }}
.step {{ font-size: .8rem; color: #374151; padding: .12rem 0; font-family: ui-monospace, monospace; }}
.how {{ background: #eff6ff; color: #1e3a8a; border-radius: 10px; padding: .7rem .9rem; font-size: .84rem; }}
</style>""", unsafe_allow_html=True)


def load_examples() -> list[dict]:
    if not os.path.exists(EXAMPLES):
        return []
    with open(EXAMPLES, encoding="utf-8") as f:
        return json.load(f)


def linked(memo: str, citations: list[dict]) -> str:
    """Turn each cited report number into a link to the FDA's own copy."""
    urls = {c["report_number"]: c.get("fda_url") for c in citations}
    return REPORT_NO.sub(lambda m: f"[{m.group(0)}]({urls[m.group(0)]})" if urls.get(m.group(0)) else m.group(0),
                         memo)


def show(result: dict):
    left, right = st.columns([2.2, 1], gap="large")
    with left:
        st.markdown('<div class="ptitle">Case file</div>', unsafe_allow_html=True)
        with st.container(border=True):
            memo = re.sub(r"\[report (\S+?)\]", r"[\1]", result["memo"])
            memo = re.sub(r"^#{1,2} ", "#### ", memo, flags=re.M)          # keep headings modest
            st.markdown(linked(memo, result["citations"]))
    with right:
        cites = result["citations"]
        ok = sum(c["exists"] for c in cites)
        deaths = sum(c["states_death"] for c in cites)
        st.markdown('<div class="ptitle">Every citation checked</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="how">{ok} of {len(cites)} cited reports exist in the FDA data, and {deaths} of '
                    f'them state that the patient died. Checked by plain code after the agent finished, on top '
                    f'of the agent\'s own evidence-checker.</div>', unsafe_allow_html=True)
        st.markdown("".join(
            f'<div class="cite"><span class="{"ok" if c["exists"] else "bad"}">{"✓" if c["exists"] else "✗"}</span>'
            f'<a href="{c.get("fda_url") or "#"}" target="_blank">{c["report_number"]}</a>'
            f'<span style="color:{GREY}">{"states a death" if c["states_death"] else "no death stated"}'
            f'{" · filed as " + c["filed_as"] if c.get("filed_as") else ""}</span></div>' for c in cites),
            unsafe_allow_html=True)
        st.markdown('<div class="ptitle" style="margin-top:1rem">What the agent did</div>', unsafe_allow_html=True)
        st.markdown("".join(f'<div class="step">{i + 1}. {s}</div>' for i, s in enumerate(result["steps"])),
                    unsafe_allow_html=True)
        st.caption(f"{result['seconds']} s")


st.markdown('<div class="logo"><span class="dot"></span>Rap Sheet · Ask</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Ask a question about AED or CPAP safety. An agent plans, searches 420,167 FDA '
            'reports, has a second agent check every report it cites, and writes a short case file. It answers '
            'only from the data, and every claim links to the FDA report behind it.</div>', unsafe_allow_html=True)

if ENABLED:
    pick = st.pills("Try one", QUESTIONS, selection_mode="single")
    question = st.text_input("Your question", value=pick or "", placeholder=QUESTIONS[0])
    if st.button("Investigate", type="primary", disabled=not question.strip()):
        with st.status("Investigating…", expanded=True) as status:
            result = investigate(question.strip(), on_step=lambda s: status.write(s))
            status.update(label=f"Done in {result['seconds']} s", state="complete", expanded=False)
        st.session_state["result"] = result
    if st.session_state.get("result"):
        show(st.session_state["result"])
else:
    st.info("Live questions are switched off on this page. Below are investigations the agent ran earlier, "
            "unchanged.")

examples = load_examples()
if examples and not st.session_state.get("result"):
    titles = [e["question"] for e in examples]
    chosen = st.radio("Saved investigations", titles, label_visibility="collapsed") if len(titles) > 1 else titles[0]
    show(next(e for e in examples if e["question"] == chosen))
