"""The patient page.  Run:  streamlit run page/patient.py   (from the repo root)

What a patient or an AED owner sees after texting a photo of their device: is it recalled, what to do,
and what has been reported, in plain words. Phone first, three tabs, little text. Same data and same
look as the device page (page/app.py) for investigators, which it links to.

INVESTIGATOR_URL (env) is where that link points; it defaults to the same host's root.
"""
import html
import json
import os
import re
import sys

import streamlit as st

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from pipeline.deathwords import STATES_DEATH  # noqa: E402
from service import record  # noqa: E402

import style  # noqa: E402

style.page_config("Rap Sheet · Your device", layout="centered")
style.inject()
st.markdown(style.patient_css(), unsafe_allow_html=True)

INVESTIGATOR = os.environ.get("INVESTIGATOR_URL", "/").rstrip("/") + "/"
KIND = {"MKJ": ("Defibrillator (AED)", "AED"), "BZD": ("CPAP / BiPAP machine", "machine")}


@st.cache_data(show_spinner=False)
def build(key):
    return record.build(key)


@st.cache_data(show_spinner=False)
def search(q):
    return record.search(q)


@st.cache_data(show_spinner=False)
def hand_check():
    path = os.path.join(ROOT, "eval", "results", "final_results.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("methods", {}).get("classifier")


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def sentence_with_death(text: str) -> str:
    """The sentence that states the death, highlighted, for a short quote."""
    text = re.sub(r"\s+", " ", text or "").strip()
    for s in re.split(r"(?<=[.;])\s+", text):
        m = STATES_DEATH.search(s)
        if m:
            s = s[:220] + ("…" if len(s) > 220 else "")
            return esc(s).replace(esc(m.group(0)), f"<mark>{esc(m.group(0))}</mark>", 1)
    return esc(text[:200])


def month(iso: str) -> str:
    months = "January February March April May June July August September October November December".split()
    try:
        return f"{months[int(iso[5:7]) - 1]} {iso[:4]}".upper()
    except (ValueError, IndexError, TypeError):
        return esc(iso)


# ---------------------------------------------------------------- which device
st.markdown(f'<div class="brand"><img src="{style.LOGO}" alt="">Rap Sheet</div>', unsafe_allow_html=True)
key = st.query_params.get("d")
if not key:
    q = st.text_input("Search a device", placeholder="Type the name on your device, e.g. LIFEPAK CR2",
                      label_visibility="collapsed")
    matches = search(q) if q else []
    if q and not matches:
        st.caption("No device with that name. Try the model name printed on the label.")
    if matches:
        pick = st.selectbox("Matches", matches, label_visibility="collapsed",
                            format_func=lambda m: f"{m['brand']} · {m['manufacturer'].title()}")
        key = pick["device_key"]
rec = build(key) if key else None
if not rec:
    st.stop()

d, t = rec["device"], rec["totals"]
maker = " ".join(w for w in d["manufacturer"].split() if not w.isdigit()).title()
kind, thing = KIND.get(d["product_code"], ("Medical device", "device"))
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]
is_aed = d["product_code"] == "MKJ"

paper = st.container(key="paper")
paper.markdown(f"""<div class="rec-eyebrow"><span>Your device</span><span>{esc(maker)}</span></div>
  <div class="rec-title">{esc(d['brand'])}</div>
  <div class="rec-note">{esc(kind)} · from the FDA's public reports</div>""", unsafe_allow_html=True)

tab_do, tab_recalls, tab_reports = paper.tabs(
    ["What to do", f"Recalls · {len(open_recalls)}" if open_recalls else "Recalls", "Reports"])

# ---------------------------------------------------------------- what to do
with tab_do:
    n = len(open_recalls)
    if n:
        action = (f'<div class="p-action"><div class="k">ACTION NEEDED</div><div class="t">{n} recall'
                  f'{"s are" if n > 1 else " is"} open. Check if yours is affected.</div></div>')
        steps = [f"Read the recall notice{'s' if n > 1 else ''} (Recalls tab)",
                 f"Ask {maker} if your unit is affected. The serial number is on the {thing}.",
                 ("Keep it in service unless they tell you otherwise" if is_aed
                  else "Keep using it unless your doctor or the maker tells you otherwise")]
    else:
        past = len(rec["recalls"])
        plural = "s" if past > 1 else ""
        headline = f"{past} past recall{plural}, all closed." if past else "No open recalls for this model."
        action = (f'<div class="p-action calm"><div class="k">NO OPEN RECALLS</div><div class="t">{headline}'
                  f'</div></div>')
        steps = [("Keep the pads and battery in date and check the status light" if is_aed
                  else "Keep using it as your doctor prescribed"),
                 "Reply SAVE to our text so we can tell you if anything changes"]
    st.markdown(action + '<div class="p-k">WHAT TO DO</div>' + "".join(
        f'<div class="p-step"><span class="n">{i}</span><span>{esc(s)}</span></div>' for i, s in enumerate(steps, 1))
        + '<div class="p-box"><b>Get alerts.</b> Reply SAVE to our text and we will message you about new recalls.</div>',
        unsafe_allow_html=True)

# ---------------------------------------------------------------- recalls
with tab_recalls:
    if not rec["recalls"]:
        st.markdown('<div class="p-small">No recalls name this model.</div>', unsafe_allow_html=True)
    cards = ""
    for r in rec["recalls"]:
        is_open = r in open_recalls
        link = "https://api.fda.gov/device/recall.json?search=product_res_number:%22" + esc(r["number"]) + "%22"
        cards += (f'<div class="p-recall"><div class="top"><span>{month(r["date"])}</span>'
                  f'<span class="open">{"● Open" if is_open else "Closed"}</span></div>'
                  f'<div class="r">{esc((r["reason"] or "").strip())}</div>'
                  f'<a href="{link}" target="_blank">FDA recall record {esc(r["number"])} ↗</a></div>')
    st.markdown(cards + (f'<div class="p-small">Keep the AED in service unless {esc(maker)} tells you otherwise.</div>'
                         if is_aed and open_recalls else ""), unsafe_allow_html=True)

# ---------------------------------------------------------------- reports
with tab_reports:
    coded, hidden = t["deaths_coded"], (t["deaths_hidden"] if t.get("hidden_death_model_ran") else 0)
    # The text check is reliable for AEDs; for CPAP machines it is not, so only the FDA's own count is shown.
    show_hidden = is_aed and hidden
    total = coded + (hidden if show_hidden else 0)
    since = (rec["period"]["first"] or "")[:4]
    if show_hidden:
        share = round(100 * coded / total) if total else 100
        body = (f'<div class="p-k" style="margin-top:0">REPORTS OF A DEATH</div><div><span class="big">{total:,}</span> since '
                f'{esc(since)}. <span class="big" style="color:{style.CLIP}">{hidden}</span> were filed as a malfunction '
                f'instead.</div><div class="p-split"><div style="width:{share}%;background:{style.NAVY}"></div>'
                f'<div style="width:{100 - share}%;background:{style.CLIP}"></div></div>')
    else:
        body = (f'<div class="p-k" style="margin-top:0">REPORTS OF A DEATH</div><div><span class="big">{coded:,}</span> '
                f'filed as a death since {esc(since)}.</div>')
        if not is_aed:
            body += ('<div class="p-small">Our check for deaths filed as something else is less reliable for CPAP '
                     'machines, so it is not shown here.</div>')
    body += '<div class="p-small">A report is an allegation, not proof the device caused a death.</div>'
    st.markdown(f'<div class="p-deaths">{body}</div>', unsafe_allow_html=True)

    quotes = [sentence_with_death(e.get("excerpt")) for e in rec.get("evidence", [])[:3]] if show_hidden else []
    if quotes:
        st.markdown('<div class="p-k">IN THE REPORTS\' OWN WORDS</div>' + "".join(
            f'<div class="p-quote">"{q}"</div>' for q in quotes), unsafe_allow_html=True)
    clf = hand_check()
    if clf and show_hidden:
        right, total_checked = clf["true_pos"], clf["true_pos"] + clf["false_pos"]
        dots = "".join('<span></span>' if i < right else '<span class="x"></span>' for i in range(total_checked))
        st.markdown(f'<div class="p-trust"><div class="d" role="img" aria-label="{right} of {total_checked}">{dots}</div>'
                    f'<div>Checked by hand: right {right} times out of {total_checked}.</div></div>',
                    unsafe_allow_html=True)
    st.markdown(f'<div class="p-small" style="margin-top:1.2rem"><a href="{INVESTIGATOR}?d={esc(rec["device_key"])}'
                f'&tab=evidence" target="_self">See every report: the full record for investigators</a></div>',
                unsafe_allow_html=True)
