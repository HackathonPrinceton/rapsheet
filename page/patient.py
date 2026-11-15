"""The patient page.  Run:  streamlit run page/patient.py   (from the repo root)

What a patient, or the person in charge of an AED, sees after texting a photo of their device. It answers
three questions in plain words: is it OK to use, what is wrong, and what have others reported. Phone first,
three tabs, no jargon. Same data and same look as the device page for investigators (page/app.py).

INVESTIGATOR_URL (env) is where "Read the reports" points; it defaults to the same host's root.
"""
import difflib
import html
import json
import os
import re
import sys

import streamlit as st

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from pipeline.store import connect  # noqa: E402
from service import record  # noqa: E402

import style  # noqa: E402

style.page_config("Rap Sheet · Your device", layout="centered")
style.inject()
st.markdown(style.patient_css(), unsafe_allow_html=True)

INVESTIGATOR = os.environ.get("INVESTIGATOR_URL", "/").rstrip("/") + "/"
KIND = {"MKJ": ("defibrillator (AED)", "AED"), "BZD": ("CPAP / BiPAP breathing machine", "machine")}
MONTHS = "January February March April May June July August September October November December".split()


@st.cache_data(show_spinner=False)
def build(key):
    return record.build(key)


@st.cache_data(show_spinner=False)
def all_devices() -> list[dict]:
    """Every device family people can pick, biggest first. The picker filters as you type, ignoring capitals."""
    rows = connect().execute(
        "SELECT device_key, MAX(brand) brand, MAX(manufacturer) maker, COUNT(*) n FROM reports "
        "WHERE brand != '' AND device_key NOT LIKE '%--unknown%' AND device_key NOT LIKE 'unknown--%' "
        "GROUP BY device_key HAVING n >= 30 ORDER BY n DESC").fetchall()
    return [dict(r) for r in rows]


@st.cache_data(show_spinner=False)
def hand_check():
    path = os.path.join(ROOT, "eval", "results", "final_results.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("methods", {}).get("classifier")


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def tidy_maker(name: str) -> str:
    return " ".join(w for w in (name or "").split() if not w.isdigit()).title()


def month(iso: str) -> str:
    try:
        return f"{MONTHS[int(iso[5:7]) - 1]} {iso[:4]}"
    except (ValueError, IndexError, TypeError):
        return esc(iso)


def clean_name(brand: str) -> str:
    """'LIFEPAK(R) CR2 DEFIBRILLATOR' -> 'LIFEPAK CR2 DEFIBRILLATOR'."""
    return re.sub(r"\s+", " ", re.sub(r"\((r|tm|c)\)|[®™©]|=", "", brand or "", flags=re.I)).strip()


def label(dev: dict) -> str:
    return f"{clean_name(dev['brand'])}  ·  {tidy_maker(dev.get('maker') or dev.get('manufacturer'))}"


@st.cache_data(show_spinner=False)
def vocabulary() -> list[str]:
    """Every word that appears in a device or maker name, for spelling correction."""
    words = set()
    for dev in all_devices():
        words.update(re.findall(r"[a-z0-9]+", f"{dev['brand']} {dev['maker']}".lower()))
    return sorted(w for w in words if len(w) > 1)


def find(q: str) -> tuple[list[dict], str]:
    """Search as typed; if nothing matches, correct each word to the closest known word and try again.
    Returns the matches and the corrected text (empty when no correction was needed)."""
    found = record.search(q)
    if found:
        return found, ""
    vocab = vocabulary()
    fixed = []
    for w in re.findall(r"[a-z0-9]+", q.lower()):
        close = difflib.get_close_matches(w, vocab, n=1, cutoff=0.7)
        fixed.append(close[0] if close else w)
    corrected = " ".join(fixed)
    return (record.search(corrected), corrected) if corrected != q.lower().strip() else ([], "")


# ---------------------------------------------------------------- which device
st.markdown(f'<div class="brand"><img src="{style.LOGO}" alt="">Rap Sheet</div>', unsafe_allow_html=True)
devices = all_devices()
by_key = {d["device_key"]: d for d in devices}
key = st.query_params.get("d")
if key not in by_key and not (key and build(key)):
    key = None

if not key:
    start = st.container(key="home")
    start.markdown('<div class="p-k" style="margin-top:0">FIND YOUR DEVICE</div>'
                   '<div class="p-small" style="margin-top:0">Type the name printed on the front of your device. '
                   'Capitals and small typos are fine.</div>', unsafe_allow_html=True)
    q = start.text_input("Your device", placeholder="For example: LIFEPAK CR2, DreamStation, AED Plus",
                         label_visibility="collapsed")
    if q.strip():
        matches, corrected = find(q)
        if corrected:
            start.markdown(f'<div class="p-small">Showing results for <b>{esc(corrected)}</b></div>',
                           unsafe_allow_html=True)
        if not matches:
            start.markdown('<div class="p-notfound">We couldn\'t find that device. Try the brand or model name '
                           'printed on the front. We cover defibrillators (AEDs) and CPAP machines so far.</div>',
                           unsafe_allow_html=True)
        for i, m in enumerate(matches):
            if start.button(label(m), key=f"pick{i}", use_container_width=True):
                st.query_params["d"] = m["device_key"]
                st.rerun()
    else:
        start.markdown('<div class="p-small">We cover defibrillators (AEDs) and CPAP machines so far.</div>',
                       unsafe_allow_html=True)
    st.stop()

rec = build(key)
d, t = rec["device"], rec["totals"]
maker = tidy_maker(d["manufacturer"])
kind, thing = KIND.get(d["product_code"], ("medical device", "device"))
is_aed = d["product_code"] == "MKJ"
open_recalls = [r for r in rec["recalls"] if "terminated" not in (r["status"] or "").lower()]
numbers = [r["number"] for r in open_recalls]

paper = st.container(key="paper")
paper.markdown(f"""<div class="rec-eyebrow"><span>Your device</span><span>{esc(maker)}</span></div>
  <div class="rec-title">{esc(clean_name(d['brand']))}</div>
  <div class="rec-note">A {esc(kind)} · <a href="?" target="_self">Pick another device</a></div>""",
               unsafe_allow_html=True)

tab_ok, tab_wrong, tab_reported = paper.tabs(["Is it OK to use?", "What's wrong?", "Others' reports"])

# ---------------------------------------------------------------- is it OK to use?
with tab_ok:
    if open_recalls:
        n = len(open_recalls)
        head = ("The maker has found a problem with some of these devices." if n == 1
                else f"The maker has found {n} problems with some of these devices.")
        quote = " or ".join(numbers)
        ask = f'"Is my device affected by recall {esc(quote)}?"'
        html_out = f"""
<div class="p-action"><div class="k">CHECK YOUR DEVICE</div><div class="t">{head}</div></div>
<div class="p-explain">This is called a <span class="p-term">recall</span>: the maker found a problem with some
units and is fixing it. It usually affects only some devices, so check if yours is one of them.</div>
<div class="p-explain"><b>Should I stop using it?</b> {"Keep it in service" if is_aed else "Keep using it"} unless
the maker{"" if is_aed else " or your doctor"} tells you otherwise.</div>
<div class="p-k">WHAT TO DO</div>
<div class="p-step"><span class="n">1</span><span>Find the <b>serial number</b> on the back or bottom of your {thing}.</span></div>
<div class="p-step"><span class="n">2</span><span>Call <b>{esc(maker)}</b> and ask: {ask}</span></div>
<div class="p-step"><span class="n">3</span><span>Text <b>SAVE</b> to us to get a message if anything changes.</span></div>"""
    else:
        past = len(rec["recalls"])
        sub = (f"There {'was' if past == 1 else 'were'} {past} earlier <span class=\"p-term\">recall"
               f"{'' if past == 1 else 's'}</span> (a fix the maker made to some units), and "
               f"{'it is' if past == 1 else 'all are'} finished." if past else "The maker has not reported a problem that needs fixing.")
        html_out = f"""
<div class="p-action calm"><div class="k">NO OPEN PROBLEMS</div><div class="t">No open recalls for this {thing}.</div></div>
<div class="p-explain">{sub}</div>
<div class="p-k">WHAT TO DO</div>
<div class="p-step"><span class="n">1</span><span>{"Check the readiness light, and that the pads and battery are within their dates." if is_aed else "Keep using it as your doctor prescribed."}</span></div>
<div class="p-step"><span class="n">2</span><span>Text <b>SAVE</b> to us to get a message if anything changes.</span></div>"""
    st.markdown(html_out, unsafe_allow_html=True)

# ---------------------------------------------------------------- what's wrong?
with tab_wrong:
    if not rec["recalls"]:
        st.markdown(f'<div class="p-explain">No <span class="p-term">recalls</span> name this {thing}.</div>',
                    unsafe_allow_html=True)
    cards = ""
    for r in rec["recalls"]:
        is_open = r in open_recalls
        reason = (r["reason"] or "").strip()
        reason = reason[:240] + ("…" if len(reason) > 240 else "")
        cards += (f'<div class="p-recall"><div class="top"><span>Started {esc(month(r["date"]))}</span>'
                  f'<span class="open">{"● Still open" if is_open else "Finished"}</span></div>'
                  f'<div class="lbl">The problem, in the FDA\'s words</div><div class="r">{esc(reason)}</div>'
                  f'<div class="num">Recall number to quote: <b>{esc(r["number"])}</b></div></div>')
    if rec["recalls"]:
        cards = ('<div class="p-explain">A <span class="p-term">recall</span> means the maker found a problem with '
                 'some units and is fixing it. Here is each one.</div>') + cards
    st.markdown(cards, unsafe_allow_html=True)

# ---------------------------------------------------------------- what others reported
with tab_reported:
    total, coded = t["reports"], t["deaths_coded"]
    hidden = t["deaths_hidden"] if (is_aed and t.get("hidden_death_model_ran")) else 0
    since = (rec["period"]["first"] or "")[:4]
    out = (f'<div class="p-explain">People and companies have told the FDA about problems with this {thing} '
           f'<b>{total:,} times</b> since {esc(since)}.</div>')
    if hidden:
        died = coded + hidden
        share = round(100 * coded / died)
        out += (f'<div class="p-deaths"><div class="p-k" style="margin-top:0">THE MOST SERIOUS</div>'
                f'<div><span class="big">{died:,}</span> of those reports involve someone who died.</div>'
                f'<div class="p-split"><div style="width:{share}%;background:{style.NAVY}"></div>'
                f'<div style="width:{100 - share}%;background:{style.CLIP}"></div></div>'
                f'<div>In <b style="color:{style.CLIP}">{hidden}</b> of them, the death was filed as a '
                f'"malfunction", so it is easy to miss.</div>'
                f'<div class="p-small">A report does not prove the device caused the death. AEDs are used on people '
                f'in cardiac arrest, and many do not survive even when the device works.</div></div>')
    else:
        out += (f'<div class="p-deaths"><div class="p-k" style="margin-top:0">THE MOST SERIOUS</div>'
                f'<div><span class="big">{coded:,}</span> of those reports were filed as a death.</div>'
                f'<div class="p-small">A report does not prove the device caused the death.</div></div>')
    if is_aed:
        out += ('<div class="p-k">WHAT TO CHECK ON YOUR AED</div>'
                '<div class="p-step"><span class="n">✓</span><span>The readiness light shows it is ready</span></div>'
                '<div class="p-step"><span class="n">✓</span><span>The pads are sealed and within their date</span></div>'
                '<div class="p-step"><span class="n">✓</span><span>The battery is within its date</span></div>')
    clf = hand_check()
    if clf and hidden:
        right, checked = clf["true_pos"], clf["true_pos"] + clf["false_pos"]
        out += (f'<div class="p-small" style="margin-top:.8rem">We found the deaths filed as a malfunction by reading '
                f'every report. People checked our work by hand: right {right} times out of {checked}.</div>')
    out += (f'<div class="p-small" style="margin-top:1rem"><a href="{INVESTIGATOR}?d={esc(rec["device_key"])}'
            f'&tab=evidence" target="_blank">Read the reports yourself</a></div>')
    st.markdown(out, unsafe_allow_html=True)
